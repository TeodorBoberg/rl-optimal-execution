"""
download_data.py
Downloads real intraday OHLCV data from Yahoo Finance.

Usage:
    python download_data.py --ticker AAPL --days 50
"""

import argparse
import sys
import pandas as pd
import numpy as np
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("Run: python -m pip install yfinance")
    sys.exit(1)


def download(ticker: str, days: int = 50) -> pd.DataFrame:
    print(f"Downloading {ticker} (5m bars, last {days} days)...")
    days = min(days, 59)
    tk = yf.Ticker(ticker)
    df = tk.history(period=f"{days}d", interval="5m", auto_adjust=True)

    if df.empty:
        print(f"No data returned for {ticker}.")
        sys.exit(1)

    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    time_col = "datetime" if "datetime" in df.columns else "date"
    df = df.rename(columns={time_col: "timestamp"})
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    df = df.dropna()
    df = df[df["volume"] > 0]

    df["date"] = pd.to_datetime(df["timestamp"]).dt.date
    df["day"] = df.groupby("date").ngroup()
    df["step"] = df.groupby("day").cumcount()

    hl_ratio = (df["high"] - df["low"]) / df["close"]
    df["spread_bps"] = np.clip(hl_ratio * 10_000 * 0.1, 1.0, 50.0)
    half = df["close"] * df["spread_bps"] / 20_000
    df["bid"] = df["close"] - half
    df["ask"] = df["close"] + half
    df["vwap"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4

    df["hour"]   = pd.to_datetime(df["timestamp"]).dt.hour
    df["minute"] = pd.to_datetime(df["timestamp"]).dt.minute
    df = df[
        ((df["hour"] == 9) & (df["minute"] >= 30)) |
        ((df["hour"] >= 10) & (df["hour"] <= 15)) |
        ((df["hour"] == 16) & (df["minute"] == 0))
    ].copy()

    df["date"] = pd.to_datetime(df["timestamp"]).dt.date
    df["day"]  = df.groupby("date").ngroup()
    df["step"] = df.groupby("day").cumcount()

    print(f"Downloaded {len(df)} bars across {df['day'].nunique()} trading days.")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--days",   type=int, default=50)
    args = parser.parse_args()

    Path("data").mkdir(exist_ok=True)
    df = download(args.ticker, args.days)
    out = f"data/{args.ticker.lower()}_5m.csv"
    df.to_csv(out, index=False)
    print(f"Saved to {out}")