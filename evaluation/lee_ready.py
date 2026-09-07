"""
evaluation/lee_ready.py

Lee & Ready (1991) trade classification: labels each individual trade as
buyer-initiated or seller-initiated using:

  1. QUOTE RULE (primary): compare trade price to the prevailing quote
     midpoint at the time of the trade.
       price > midpoint  -> buy  (buyer crossed the spread to hit the ask)
       price < midpoint  -> sell (seller crossed the spread to hit the bid)
       price == midpoint -> ambiguous, fall through to the tick rule

  2. TICK RULE (tie-breaker): compare trade price to the previous trade's
     price.
       price > prev_price -> buy  (uptick)
       price < prev_price -> sell (downtick)
       price == prev_price -> "zero tick": inherit the classification of
                               the most recent NON-zero tick (standard
                               Lee-Ready zero-tick handling)

This requires trade-by-trade data with a contemporaneous quote for each
trade -- e.g. Databento's `tbbo` schema (trades pre-paired with the best
bid/offer at trade time), which is exactly what this module expects.

It will NOT produce a meaningful result on OHLCV bar data (5-min bars,
daily bars, etc.) -- each "trade" in a bar is really hundreds or
thousands of real trades netted together, and there is no valid quote
to compare a bar's close price against. Don't be tempted to feed bar
data into this; the classification would look like it ran but wouldn't
mean anything.

Usage (as a library):
    from evaluation.lee_ready import classify_trades
    classified_df = classify_trades(df)  # df needs: price, bid, ask, timestamp

Usage (CLI, on a Databento tbbo CSV/parquet export):
    python evaluation/lee_ready.py --input data/tbbo_msft.csv --output evaluation/classified_msft.csv
"""

import argparse
import numpy as np
import pandas as pd


def classify_trades(df: pd.DataFrame, price_col="price", bid_col="bid",
                     ask_col="ask", ts_col="ts_event") -> pd.DataFrame:
    """
    Classify each row of df as 'buy' or 'sell' initiated using Lee-Ready.

    df must be sorted chronologically and contain, at minimum:
      - a trade price column (price_col)
      - bid/ask columns representing the prevailing quote AT TRADE TIME
        (bid_col, ask_col) -- e.g. Databento's tbbo schema provides this
        directly, one row per trade, no separate merge needed.
      - a timestamp column (ts_col), used only to verify sort order.

    Returns a copy of df with two new columns:
      - 'midpoint': (bid + ask) / 2
      - 'trade_sign': +1 (buy), -1 (sell)
      - 'classification_method': 'quote_rule' or 'tick_rule'
    """
    required = [price_col, bid_col, ask_col, ts_col]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required column(s) for Lee-Ready classification: {missing}. "
            f"This needs trade-by-trade data with a contemporaneous quote per trade "
            f"(e.g. Databento's 'tbbo' schema), not OHLCV bar data."
        )

    df = df.sort_values(ts_col).reset_index(drop=True).copy()

    df["midpoint"] = (df[bid_col] + df[ask_col]) / 2.0

    trade_sign = np.full(len(df), np.nan)
    method = np.array([""] * len(df), dtype=object)

    prices = df[price_col].values
    midpoints = df["midpoint"].values

    last_nonzero_sign = 0  # for zero-tick inheritance

    for i in range(len(df)):
        price = prices[i]
        mid = midpoints[i]

        if price > mid:
            trade_sign[i] = 1
            method[i] = "quote_rule"
        elif price < mid:
            trade_sign[i] = -1
            method[i] = "quote_rule"
        else:
            # At the midpoint -- fall back to the tick rule.
            if i == 0:
                # No previous trade to compare against; leave unclassified.
                trade_sign[i] = 0
                method[i] = "unclassified_first_trade"
            else:
                prev_price = prices[i - 1]
                if price > prev_price:
                    trade_sign[i] = 1
                    method[i] = "tick_rule"
                elif price < prev_price:
                    trade_sign[i] = -1
                    method[i] = "tick_rule"
                else:
                    # Zero tick: inherit the last non-zero classification.
                    trade_sign[i] = last_nonzero_sign
                    method[i] = "tick_rule_zero_tick"

        if trade_sign[i] != 0:
            last_nonzero_sign = trade_sign[i]

    df["trade_sign"] = trade_sign.astype(int)
    df["classification_method"] = method
    return df


def summarize_classification(df: pd.DataFrame) -> None:
    """Print a quick sanity-check summary of a classified trade set."""
    n = len(df)
    n_buy = (df["trade_sign"] == 1).sum()
    n_sell = (df["trade_sign"] == -1).sum()
    n_unclassified = (df["trade_sign"] == 0).sum()

    print(f"Total trades: {n}")
    print(f"  Buy-classified:  {n_buy} ({n_buy/n:.1%})")
    print(f"  Sell-classified: {n_sell} ({n_sell/n:.1%})")
    if n_unclassified:
        print(f"  Unclassified:    {n_unclassified} ({n_unclassified/n:.1%})")

    print("\nClassification method breakdown:")
    print(df["classification_method"].value_counts().to_string())

    quote_rule_frac = (df["classification_method"] == "quote_rule").mean()
    print(f"\n{quote_rule_frac:.1%} of trades classified directly by the quote rule "
          f"(the rest needed the tick-rule tie-breaker). A healthy, liquid-name "
          f"sample typically sees the large majority resolved by the quote rule "
          f"alone -- if that fraction is low, it's worth checking the quote data "
          f"quality/alignment before trusting the results.")


def validate_against_ground_truth(df: pd.DataFrame, side_col="side") -> None:
    """
    If the source data includes an exchange-reported trade side (e.g.
    Databento's tbbo/trades schemas include a 'side' field: 'B' = buy
    aggressor, 'A' = sell aggressor, 'N' = unspecified), compare our
    Lee-Ready classification against it directly. This is real ground
    truth from the exchange's own matching data, not an approximation --
    a much stronger validation than trusting the algorithm on faith.
    """
    if side_col not in df.columns:
        print(f"\nNo '{side_col}' column found -- skipping ground-truth validation.")
        return

    side_map = {"B": 1, "A": -1}
    ground_truth = df[side_col].map(side_map)
    has_ground_truth = ground_truth.notna()

    n_with_gt = has_ground_truth.sum()
    if n_with_gt == 0:
        print(f"\nNo rows have a usable '{side_col}' value (all 'N'/unspecified or missing) "
              f"-- skipping ground-truth validation.")
        return

    comparable = df[has_ground_truth].copy()
    comparable["ground_truth_sign"] = ground_truth[has_ground_truth]
    agree = (comparable["trade_sign"] == comparable["ground_truth_sign"]).sum()
    accuracy = agree / n_with_gt

    print(f"\n=== Ground-truth validation (vs exchange-reported '{side_col}') ===")
    print(f"{n_with_gt}/{len(df)} trades had a usable exchange-reported side "
          f"({n_with_gt/len(df):.1%} coverage).")
    print(f"Lee-Ready agreement with exchange-reported side: {accuracy:.1%}")
    print("(Published academic studies on Lee-Ready typically report ~80-90% accuracy "
          "against ground truth on liquid names -- useful context for judging this number.)")

    # Break down accuracy by classification method (quote_rule vs tick_rule)
    # to see if the tie-breaker cases are meaningfully less reliable.
    print("\nAccuracy by classification method:")
    for method in comparable["classification_method"].unique():
        subset = comparable[comparable["classification_method"] == method]
        if len(subset) == 0:
            continue
        acc = (subset["trade_sign"] == subset["ground_truth_sign"]).mean()
        print(f"  {method}: {acc:.1%} ({len(subset)} trades)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True,
                         help="CSV with trade-by-trade data: price, bid, ask, timestamp columns")
    parser.add_argument("--output", default=None)
    parser.add_argument("--price-col", default="price")
    parser.add_argument("--bid-col", default="bid")
    parser.add_argument("--ask-col", default="ask")
    parser.add_argument("--ts-col", default="ts_event")
    parser.add_argument("--side-col", default="side",
                         help="Exchange-reported ground-truth side column, if present (Databento: 'side')")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    classified = classify_trades(df, price_col=args.price_col, bid_col=args.bid_col,
                                  ask_col=args.ask_col, ts_col=args.ts_col)

    summarize_classification(classified)
    validate_against_ground_truth(classified, side_col=args.side_col)

    out_path = args.output or args.input.replace(".csv", "_classified.csv")
    classified.to_csv(out_path, index=False)
    print(f"\nClassified trades saved to {out_path}")


if __name__ == "__main__":
    main()