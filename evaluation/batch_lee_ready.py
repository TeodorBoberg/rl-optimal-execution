"""
evaluation/batch_lee_ready.py

Runs lee_ready.py's classify_trades() across every downloaded ticker's
tbbo file in a directory, aggregates classification stats and
ground-truth accuracy across the full universe, and saves one merged
classified dataset for downstream real-impact analysis.

Usage:
    python evaluation/batch_lee_ready.py --input-dir data/tick
"""

import argparse
import glob
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lee_ready import classify_trades


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/tick")
    parser.add_argument("--pattern", default="*_tbbo_*.csv",
                         help="Glob pattern to match downloaded files (skips already-classified output files)")
    parser.add_argument("--price-col", default="price")
    parser.add_argument("--bid-col", default="bid_px_00")
    parser.add_argument("--ask-col", default="ask_px_00")
    parser.add_argument("--ts-col", default="ts_event")
    parser.add_argument("--side-col", default="side")
    parser.add_argument("--output", default="data/tick/all_classified_merged.csv")
    args = parser.parse_args()

    files = sorted(glob.glob(os.path.join(args.input_dir, args.pattern)))
    files = [f for f in files if "_classified" not in f]
    if not files:
        raise SystemExit(f"No files matching {args.pattern} found in {args.input_dir}")

    print(f"Found {len(files)} files to process.\n")

    all_classified = []
    per_ticker_summary = []

    for fpath in files:
        symbol = os.path.basename(fpath).split("_tbbo_")[0].upper()
        print(f"Processing {symbol} ({fpath})...")
        df = pd.read_csv(fpath)

        try:
            classified = classify_trades(df, price_col=args.price_col, bid_col=args.bid_col,
                                          ask_col=args.ask_col, ts_col=args.ts_col)
        except ValueError as e:
            print(f"  SKIPPED: {e}")
            continue

        classified["symbol"] = symbol
        all_classified.append(classified)

        n = len(classified)
        n_buy = (classified["trade_sign"] == 1).sum()
        n_sell = (classified["trade_sign"] == -1).sum()
        quote_rule_frac = (classified["classification_method"] == "quote_rule").mean()

        gt_row = {"symbol": symbol, "n_trades": n, "buy_frac": n_buy / n, "sell_frac": n_sell / n,
                  "quote_rule_frac": quote_rule_frac, "gt_coverage": None, "gt_accuracy": None}

        if args.side_col in classified.columns:
            side_map = {"B": 1, "A": -1}
            gt = classified[args.side_col].map(side_map)
            has_gt = gt.notna()
            if has_gt.sum() > 0:
                gt_row["gt_coverage"] = has_gt.sum() / n
                gt_row["gt_accuracy"] = (classified.loc[has_gt, "trade_sign"] == gt[has_gt]).mean()

        per_ticker_summary.append(gt_row)
        print(f"  {n} trades: {n_buy/n:.1%} buy / {n_sell/n:.1%} sell, "
              f"{quote_rule_frac:.1%} via quote rule"
              + (f", GT accuracy {gt_row['gt_accuracy']:.1%} (coverage {gt_row['gt_coverage']:.1%})"
                 if gt_row['gt_accuracy'] is not None else ""))

    summary_df = pd.DataFrame(per_ticker_summary)
    print("\n=== Per-ticker summary ===")
    print(summary_df.round(4).to_string(index=False))

    # Aggregate across the whole universe
    merged = pd.concat(all_classified, ignore_index=True)
    total_n = len(merged)
    total_buy = (merged["trade_sign"] == 1).sum()
    total_quote_rule = (merged["classification_method"] == "quote_rule").mean()

    print(f"\n=== Aggregate across all {len(files)} tickers, {total_n} total trades ===")
    print(f"Overall buy fraction: {total_buy/total_n:.1%}")
    print(f"Overall quote-rule fraction: {total_quote_rule:.1%}")

    if args.side_col in merged.columns:
        side_map = {"B": 1, "A": -1}
        gt = merged[args.side_col].map(side_map)
        has_gt = gt.notna()
        if has_gt.sum() > 0:
            overall_acc = (merged.loc[has_gt, "trade_sign"] == gt[has_gt]).mean()
            print(f"Overall ground-truth accuracy: {overall_acc:.1%} "
                  f"(coverage: {has_gt.sum()/total_n:.1%} of all trades)")
            print("\nBreakdown by classification method (aggregate):")
            for method in merged.loc[has_gt, "classification_method"].unique():
                mask = has_gt & (merged["classification_method"] == method)
                if mask.sum() == 0:
                    continue
                acc = (merged.loc[mask, "trade_sign"] == gt[mask]).mean()
                print(f"  {method}: {acc:.1%} ({mask.sum()} trades)")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    merged.to_csv(args.output, index=False)
    summary_df.to_csv(args.output.replace(".csv", "_per_ticker_summary.csv"), index=False)
    print(f"\nMerged classified dataset saved to {args.output}")
    print(f"Per-ticker summary saved to {args.output.replace('.csv', '_per_ticker_summary.csv')}")


if __name__ == "__main__":
    main()