"""
evaluation/fetch_tick_data.py

Pulls real trade-by-trade data (with contemporaneous quotes) from Databento
for use with lee_ready.py. Uses the 'tbbo' schema on the EQUS.MINI dataset,
which pairs every trade with the best bid/offer at the exact moment of the
trade -- exactly what Lee-Ready needs, no separate quote/trade merge step.

SETUP (one-time):
    1. Sign up at https://databento.com (comes with $125 in free credit,
       which should easily cover a small proof-of-concept pull -- a few
       days of tbbo data for 1-2 liquid names is typically a few dollars).
    2. pip install databento --break-system-packages
    3. Get your API key from the Databento portal and either:
       - set it as an env var:  set DATABENTO_API_KEY=db-xxxxxxxx   (Windows)
       - or pass it via --api-key

SCOPE NOTE: this is meant for a small proof-of-concept pull (1-2 tickers,
a handful of days) to validate the Lee-Ready methodology on real data, not
to replace or recalibrate the full 19-ticker simulator -- that would need
substantially more data (many days, all tickers) and is a separate,
larger effort.

Usage:
    python evaluation/fetch_tick_data.py --symbols MSFT --start 2026-07-01 --end 2026-07-08
    python evaluation/fetch_tick_data.py --symbols MSFT,GOOGL --start 2026-07-01 --end 2026-07-03 --api-key db-xxxx
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", required=True,
                         help="Comma-separated tickers, e.g. MSFT,GOOGL")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD (exclusive)")
    parser.add_argument("--dataset", default="EQUS.MINI",
                         help="Databento dataset ID (EQUS.MINI is the cost-effective composite BBO dataset)")
    parser.add_argument("--schema", default="tbbo",
                         help="tbbo = trades pre-paired with best bid/offer at trade time")
    parser.add_argument("--api-key", default=None,
                         help="Falls back to DATABENTO_API_KEY env var if not passed")
    parser.add_argument("--output-dir", default="data/tick")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("DATABENTO_API_KEY")
    if not api_key:
        raise SystemExit(
            "No API key found. Either pass --api-key db-xxxx, or set it as an "
            "environment variable first:\n"
            "  Windows (PowerShell): $env:DATABENTO_API_KEY = 'db-xxxx'\n"
            "  Windows (cmd):        set DATABENTO_API_KEY=db-xxxx\n"
            "Get your key from https://databento.com after signing up."
        )

    try:
        import databento as db
    except ImportError:
        raise SystemExit(
            "The 'databento' package isn't installed. Run:\n"
            "  pip install databento --break-system-packages"
        )

    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    os.makedirs(args.output_dir, exist_ok=True)

    client = db.Historical(api_key)

    # Cost check first -- Databento's cost endpoint lets you see the price
    # BEFORE committing to the download, so a mistake here doesn't burn
    # through the free credit unexpectedly.
    print(f"Checking cost for {symbols} from {args.start} to {args.end} "
          f"({args.dataset}/{args.schema})...")
    try:
        cost = client.metadata.get_cost(
            dataset=args.dataset,
            symbols=symbols,
            schema=args.schema,
            start=args.start,
            end=args.end,
        )
        print(f"Estimated cost: ${cost:.4f}")
        confirm = input("Proceed with download? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return
    except Exception as e:
        print(f"Could not fetch cost estimate ({e}); proceeding without confirmation.")

    for symbol in symbols:
        print(f"\nFetching {symbol}...")
        data = client.timeseries.get_range(
            dataset=args.dataset,
            schema=args.schema,
            symbols=[symbol],
            start=args.start,
            end=args.end,
        )
        df = data.to_df(tz="US/Eastern")
        out_path = os.path.join(args.output_dir, f"{symbol.lower()}_tbbo_{args.start}_{args.end}.csv")
        df.to_csv(out_path, index=False)
        print(f"  {len(df)} rows saved to {out_path}")
        print(f"  Columns: {df.columns.tolist()}")
        print(f"  Feed this into lee_ready.py -- check column names match "
              f"(price/bid_px_00/ask_px_00 or similar; may need --price-col/--bid-col/"
              f"--ask-col/--ts-col overrides depending on Databento's exact tbbo schema "
              f"column naming, which can shift between client library versions).")


if __name__ == "__main__":
    main()