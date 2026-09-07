"""
evaluation/calibrate_impact_factors.py

Jointly estimates the three exponents in compute_impact() from real
classified trades:

    temp_impact = eta * participation^impact_exponent
                      * (spread/avg_spread)^spread_impact_exp
                      * realised_vol^vol_impact_exp

Currently impact_exponent (0.65) is calibrated but spread_impact_exp (0.3)
and vol_impact_exp (0.4) are original guesses.

Method: for each quote-rule-classified trade, record participation,
prevailing spread, trailing realised volatility, and realised impact
(signed distance from the pre-trade midpoint). Taking logs makes the
multiplicative model linear:

    log|impact| = log(eta') + a*log(participation)
                            + b*log(spread_ratio)
                            + c*log(realised_vol)

so ordinary least squares recovers all three exponents at once. Estimating
them JOINTLY matters: participation, spread and volatility are correlated
in real data (big trades happen when spreads are wide and volatility is
high), so fitting any one in isolation absorbs the others' effects and
biases it.

This also produces an independent estimate of impact_exponent to compare
against the 0.65 obtained separately.

Only quote_rule trades are used -- the tick-rule fallback measured 51.2%
accuracy against exchange-reported side, so including it would inject sign
noise into the dependent variable.

Usage:
    python evaluation/calibrate_impact_factors.py
    python evaluation/calibrate_impact_factors.py --max-files 26 --horizon-sec 60
"""

import sys
import os
import glob
import argparse
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

import numpy as np
import pandas as pd

from evaluation.lee_ready import classify_trades


def process_file(path, horizon_sec, vol_window, max_trades):
    needed = ["ts_event", "price", "size", "bid_px_00", "ask_px_00"]
    header = pd.read_csv(path, nrows=0)
    if any(c not in header.columns for c in needed):
        return None
    df = pd.read_csv(path, usecols=needed)

    ts = pd.to_datetime(df["ts_event"], errors="coerce", utc=True)
    if ts.isna().all():
        ts = pd.to_datetime(df["ts_event"], unit="ns", errors="coerce", utc=True)
    df["ts_event"] = ts
    df = df.dropna(subset=["ts_event"]).sort_values("ts_event").reset_index(drop=True)

    eastern = df["ts_event"].dt.tz_convert("US/Eastern")
    df = df[(eastern.dt.time >= pd.Timestamp("09:30").time()) &
            (eastern.dt.time < pd.Timestamp("16:00").time())].copy()
    if df.empty:
        return None
    df["trade_date"] = df["ts_event"].dt.tz_convert("US/Eastern").dt.date
    if max_trades and len(df) > max_trades:
        df = df.iloc[:max_trades].copy()

    cl = classify_trades(df, price_col="price", bid_col="bid_px_00",
                          ask_col="ask_px_00", ts_col="ts_event")
    cl = cl[cl["classification_method"] == "quote_rule"].copy()
    if len(cl) < vol_window * 5:
        return None

    cl["spread_bps"] = (cl["ask_px_00"] - cl["bid_px_00"]) / cl["midpoint"] * 1e4
    daily = cl.groupby("trade_date")["size"].transform("sum")
    cl["participation"] = cl["size"] / daily.replace(0, np.nan)

    out = []
    for date, g in cl.groupby("trade_date"):
        g = g.sort_values("ts_event").reset_index(drop=True)
        mid = g["midpoint"].values
        t = g["ts_event"].values.astype("datetime64[s]").astype(np.int64)

        # Trailing realised volatility: std of recent midpoint log-returns.
        lr = np.diff(np.log(mid), prepend=np.log(mid[0]))
        rv = pd.Series(lr).rolling(vol_window, min_periods=vol_window).std().values

        fwd = np.searchsorted(t, t + horizon_sec, side="left")
        ok = (fwd < len(g)) & np.isfinite(rv) & (rv > 0)
        if not ok.any():
            continue
        idx = np.where(ok)[0]

        ret = (mid[fwd[idx]] - mid[idx]) / mid[idx] * 1e4
        ret = ret - ret.mean()          # strip the day's common drift
        signed = g["trade_sign"].values[idx] * ret

        out.append(pd.DataFrame({
            "participation": g["participation"].values[idx],
            "spread_bps": g["spread_bps"].values[idx],
            "realised_vol": rv[idx],
            "impact_bps": signed,
        }))
    return pd.concat(out, ignore_index=True) if out else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/tick")
    parser.add_argument("--pattern", default="*_tbbo_*.csv")
    parser.add_argument("--max-files", type=int, default=26)
    parser.add_argument("--max-trades-per-file", type=int, default=500000)
    parser.add_argument("--horizon-sec", type=int, default=60)
    parser.add_argument("--vol-window", type=int, default=100)
    parser.add_argument("--n-quantiles", type=int, default=5,
                         help="Quantile bins per regressor. Cells = n^3, so this "
                              "trades resolution against cell population.")
    parser.add_argument("--min-cell-n", type=int, default=200)
    parser.add_argument("--avg-spread-bps", type=float, default=2.133,
                         help="Config market.avg_spread_bps, for the spread ratio.")
    parser.add_argument("--output", default="evaluation/plots/impact_factors.csv")
    args = parser.parse_args()

    files = sorted(glob.glob(os.path.join(args.input_dir, args.pattern)))
    files = [f for f in files if "_classified" not in os.path.basename(f)]
    if not files:
        raise SystemExit(f"No files in {args.input_dir}")

    by_ticker = {}
    for f in files:
        by_ticker.setdefault(os.path.basename(f).split("_tbbo_")[0], []).append(f)
    picked = []
    if args.max_files == 0:
        picked = files
    else:
        per = max(1, args.max_files // len(by_ticker))
        for tk in sorted(by_ticker):
            picked.extend(sorted(by_ticker[tk])[:per])

    print(f"Processing {len(picked)} file(s) across {len(by_ticker)} ticker(s)\n")
    frames = []
    for f in picked:
        res = process_file(f, args.horizon_sec, args.vol_window,
                            args.max_trades_per_file)
        print(f"  {os.path.basename(f)}: {0 if res is None else len(res):,} observations")
        if res is not None:
            frames.append(res)

    if not frames:
        raise SystemExit("No usable observations.")
    d = pd.concat(frames, ignore_index=True)

    # Only positive impacts can enter a log-log fit. Impact is a small signal
    # against large price noise, so roughly half of individual observations
    # come out negative; that is noise, not negative impact. Bucketing by the
    # three regressors first and fitting on bucket MEANS averages the noise
    # away, which is what makes the fit possible at all.
    d = d[np.isfinite(d).all(axis=1)]
    d = d[(d["participation"] > 0) & (d["spread_bps"] > 0) & (d["realised_vol"] > 0)]
    print(f"\nTotal: {len(d):,} observations")

    # A 3-way grid needs nq^3 cells populated; nq=8 means 512 cells, which
    # requires enormous data. nq=5 (125 cells) still identifies three
    # exponents while keeping cells well populated.
    nq = args.n_quantiles
    d["p_b"] = pd.qcut(d["participation"], nq, labels=False, duplicates="drop")
    d["s_b"] = pd.qcut(d["spread_bps"], nq, labels=False, duplicates="drop")
    d["v_b"] = pd.qcut(d["realised_vol"], nq, labels=False, duplicates="drop")

    cells = d.groupby(["p_b", "s_b", "v_b"]).agg(
        participation=("participation", "mean"),
        spread_bps=("spread_bps", "mean"),
        realised_vol=("realised_vol", "mean"),
        impact=("impact_bps", "mean"),
        n=("impact_bps", "size"),
        sd=("impact_bps", "std"),
    ).reset_index()
    cells = cells[(cells["n"] >= args.min_cell_n) & (cells["impact"] > 0)]
    cells["se"] = cells["sd"] / np.sqrt(cells["n"])
    cells["t"] = cells["impact"] / cells["se"]
    print(f"{len(cells)} populated cells with positive mean impact "
          f"(of {nq**3} possible); {(cells['t'] > 2).sum()} have |t| > 2")

    if len(cells) < 20:
        raise SystemExit("Too few usable cells to fit three exponents reliably. "
                          "Try --max-files 0 for more data.")

    X = np.column_stack([
        np.ones(len(cells)),
        np.log(cells["participation"]),
        np.log(cells["spread_bps"] / args.avg_spread_bps),
        np.log(cells["realised_vol"]),
    ])
    y = np.log(cells["impact"])

    # Collinearity check. Participation, spread and volatility move together
    # in real markets -- large trades happen when spreads are wide and
    # volatility is high -- so the design matrix can be ill-conditioned and
    # the three exponents may not be separately identifiable. Without this
    # check the regression still returns coefficients, but they are
    # arbitrary splits of a shared effect rather than distinct exponents.
    corr = np.corrcoef(X[:, 1:].T)
    cond = float(np.linalg.cond(X[:, 1:]))
    print("\nCollinearity among regressors (log scale):")
    names = ["participation", "spread_ratio", "realised_vol"]
    for i in range(3):
        for j in range(i + 1, 3):
            print(f"  corr({names[i]}, {names[j]}) = {corr[i, j]:+.3f}")
    print(f"  condition number = {cond:.1f}")
    if cond > 30:
        print("  WARNING: condition number above 30 indicates severe collinearity.")
        print("  The three exponents are NOT separately identifiable from this data;")
        print("  treat the individual coefficients as unreliable even if the overall")
        print("  fit looks reasonable.")

    # Weight by precision so well-measured cells dominate.
    w = np.sqrt(cells["n"].values)
    coef, *_ = np.linalg.lstsq(X * w[:, None], y * w, rcond=None)
    const, a, b, c = coef

    pred = X @ coef
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan

    print("\n" + "=" * 66)
    print("JOINT FIT  log|impact| ~ a*log(participation) + b*log(spread_ratio)")
    print("                        + c*log(realised_vol)")
    print("=" * 66)
    print(f"  impact_exponent   (a): {a:6.3f}   (configured 0.650)")
    print(f"  spread_impact_exp (b): {b:6.3f}   (configured 0.300)")
    print(f"  vol_impact_exp    (c): {c:6.3f}   (configured 0.400)")
    print(f"  R^2: {r2:.3f} over {len(cells)} cells")

    print("\nUnivariate fits, for comparison (each ignores the other two):")
    for name, col, ref in [("participation", "participation", args.avg_spread_bps),
                            ("spread_ratio", "spread_bps", args.avg_spread_bps),
                            ("realised_vol", "realised_vol", 1.0)]:
        xv = cells[col] / (ref if col == "spread_bps" else 1.0)
        s, _ = np.polyfit(np.log(xv), y, 1)
        print(f"  {name:>14}: {s:6.3f}")
    print("  Divergence between joint and univariate estimates is expected --")
    print("  these regressors are correlated in real data, so a univariate fit")
    print("  absorbs the others' effects.")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    cells.to_csv(args.output, index=False)
    print(f"\nCell-level data saved to {args.output}")
    print("\n=== Suggested config ===")
    print("market:")
    print(f"  impact_exponent: {a:.4f}")
    print(f"  spread_impact_exp: {b:.4f}")
    print(f"  vol_impact_exp: {c:.4f}")


if __name__ == "__main__":
    main()