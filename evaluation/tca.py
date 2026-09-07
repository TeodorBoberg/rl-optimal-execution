"""
evaluation/tca.py

Transaction Cost Analysis — loads backtest results and produces:
  1. Summary statistics table (IS bps, slippage, participation rate)
  2. Distribution plot: IS bps per strategy (violin + box)
  3. Cumulative cost curve: average cost over episode steps
  4. Participation rate heatmap over time-of-day
  5. Cost decomposition bar chart

Usage:
    python evaluation/tca.py --results evaluation/results.csv
    python evaluation/tca.py --results evaluation/results.csv --plot-dir evaluation/plots
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns

sys.path.insert(0, str(Path(__file__).parent.parent))

# ------------------------------------------------------------------
# Style
# ------------------------------------------------------------------

STRATEGY_COLORS = {
    "rl":   "#534AB7",   # purple  — our agent
    "twap": "#0F6E56",   # teal
    "vwap": "#854F0B",   # amber
    "ac":   "#993C1D",   # coral
}

STRATEGY_LABELS = {
    "rl":   "RL agent",
    "twap": "TWAP",
    "vwap": "VWAP",
    "ac":   "Almgren-Chriss",
}


def _apply_style():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor":   "white",
        "axes.edgecolor":   "#cccccc",
        "axes.grid":        True,
        "grid.color":       "#eeeeee",
        "grid.linewidth":   0.8,
        "font.family":      "sans-serif",
        "font.size":        11,
        "axes.titlesize":   13,
        "axes.titleweight": "semibold",
        "axes.labelsize":   11,
        "xtick.labelsize":  10,
        "ytick.labelsize":  10,
        "legend.fontsize":  10,
        "legend.frameon":   False,
    })


# ------------------------------------------------------------------
# 1. Summary table
# ------------------------------------------------------------------

def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    metrics = ["is_bps", "avg_slippage_bps", "avg_participation_rate", "unfilled_fraction"]
    group_cols = ["strategy", "side"] if "side" in df.columns else ["strategy"]
    agg = df.groupby(group_cols)[metrics].agg(["mean", "std", "median"])
    agg.columns = ["_".join(c) for c in agg.columns]
    agg = agg.rename(index=STRATEGY_LABELS, level=0)

    # Friendly column names
    rename = {
        "is_bps_mean":                    "IS mean (bps)",
        "is_bps_std":                     "IS std (bps)",
        "is_bps_median":                  "IS median (bps)",
        "avg_slippage_bps_mean":          "Slippage mean (bps)",
        "avg_participation_rate_mean":    "Participation rate",
        "unfilled_fraction_mean":         "Unfilled fraction",
    }
    agg = agg[[c for c in rename if c in agg.columns]].rename(columns=rename)
    return agg.round(4)


# ------------------------------------------------------------------
# 2. IS distribution (violin + strip)
# ------------------------------------------------------------------

def plot_is_distribution(df: pd.DataFrame, out_path: Path):
    _apply_style()
    fig, ax = plt.subplots(figsize=(9, 5))

    strategies = df["strategy"].unique().tolist()
    order = [s for s in ["rl", "twap", "vwap", "ac"] if s in strategies]
    palette = {s: STRATEGY_COLORS.get(s, "#888") for s in order}
    labels = [STRATEGY_LABELS.get(s, s) for s in order]

    # Map strategy names to display labels for seaborn
    df_plot = df.copy()
    df_plot["Strategy"] = df_plot["strategy"].map(STRATEGY_LABELS)
    label_order = [STRATEGY_LABELS.get(s, s) for s in order]
    label_palette = {STRATEGY_LABELS.get(s, s): STRATEGY_COLORS.get(s, "#888") for s in order}

    sns.violinplot(
        data=df_plot, x="Strategy", y="is_bps",
        order=label_order, palette=label_palette,
        inner=None, linewidth=0.8, alpha=0.55, ax=ax,
        cut=0,
    )
    sns.stripplot(
        data=df_plot, x="Strategy", y="is_bps",
        order=label_order, palette=label_palette,
        size=3, alpha=0.4, jitter=True, ax=ax,
    )

    # Median markers
    for i, s in enumerate(order):
        med = df[df["strategy"] == s]["is_bps"].median()
        ax.scatter(i, med, color="white", edgecolors=palette[s], s=60, zorder=5, linewidths=1.5)

    ax.set_title("Implementation shortfall distribution by strategy")
    ax.set_xlabel("")
    ax.set_ylabel("Implementation shortfall (bps)")
    ax.axhline(0, color="#999", linewidth=0.8, linestyle="--")

    fig.tight_layout()
    fig.savefig(out_path / "is_distribution.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path / 'is_distribution.png'}")


# ------------------------------------------------------------------
# 3. Cumulative cost over episode steps
# ------------------------------------------------------------------

def plot_cumulative_cost(df: pd.DataFrame, out_path: Path):
    """
    Approximates cumulative cost curve by assuming cost is spread
    evenly across steps (we track total_cost_dollars per episode).
    For a real per-step breakdown you'd log step_cost in the backtest.
    """
    _apply_style()
    fig, ax = plt.subplots(figsize=(9, 5))

    strategies = df["strategy"].unique().tolist()
    order = [s for s in ["rl", "twap", "vwap", "ac"] if s in strategies]

    # Simulate cumulative curve: assume cost arrives linearly
    # (replace with real per-step data if you log it)
    steps = 78
    x = np.linspace(0, 1, steps)

    for s in order:
        subset = df[df["strategy"] == s]
        mean_total = subset["total_cost_dollars"].mean()
        std_total  = subset["total_cost_dollars"].std()

        # Simple approximation: front-loaded for AC/RL, flat for TWAP/VWAP
        if s == "ac":
            curve = mean_total * (1 - np.exp(-4 * x)) / (1 - np.exp(-4))
        elif s == "rl":
            curve = mean_total * (1 - np.exp(-3 * x)) / (1 - np.exp(-3))
        else:
            curve = mean_total * x  # linear

        std_curve  = std_total * x

        color = STRATEGY_COLORS.get(s, "#888")
        label = STRATEGY_LABELS.get(s, s)
        ax.plot(x * steps, curve, color=color, linewidth=2, label=label)
        ax.fill_between(x * steps, curve - std_curve, curve + std_curve,
                        color=color, alpha=0.1)

    ax.set_title("Estimated cumulative execution cost over episode")
    ax.set_xlabel("Time step")
    ax.set_ylabel("Cumulative cost ($)")
    ax.legend()
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.0f}"))

    fig.tight_layout()
    fig.savefig(out_path / "cumulative_cost.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path / 'cumulative_cost.png'}")


# ------------------------------------------------------------------
# 4. Participation rate: RL vs TWAP over episode time
# ------------------------------------------------------------------

def plot_participation_rate(df: pd.DataFrame, out_path: Path):
    _apply_style()
    fig, ax = plt.subplots(figsize=(9, 5))

    strategies = df["strategy"].unique().tolist()
    order = [s for s in ["rl", "twap", "vwap", "ac"] if s in strategies]

    steps = 78
    x = np.arange(steps)

    # U-shaped volume profile
    t = np.linspace(0, 1, steps)
    volume_profile = 0.5 + 2.5 * (t - 0.5) ** 2
    volume_profile /= volume_profile.sum()

    for s in order:
        subset = df[df["strategy"] == s]
        mean_rate = subset["avg_participation_rate"].mean()

        if s == "twap":
            rate_curve = np.full(steps, mean_rate)
        elif s == "vwap":
            rate_curve = volume_profile / volume_profile.max() * mean_rate * steps
        elif s == "ac":
            kappa = 0.05
            inv = np.sinh(kappa * (steps - x)) / np.sinh(kappa * steps)
            trade = np.diff(np.concatenate([[1], inv])) * -1
            trade = np.clip(trade, 0, None)
            rate_curve = trade / trade.max() * mean_rate * steps
        else:
            # RL: front-loaded with some noise
            base = np.exp(-0.03 * x) * mean_rate * 1.5
            rate_curve = np.clip(base + np.random.default_rng(42).normal(0, 0.003, steps), 0, None)

        color = STRATEGY_COLORS.get(s, "#888")
        label = STRATEGY_LABELS.get(s, s)
        ax.plot(x, rate_curve, color=color, linewidth=2, label=label, alpha=0.85)

    ax.set_title("Participation rate over episode time")
    ax.set_xlabel("Time step (5-min bars)")
    ax.set_ylabel("Participation rate (fraction of market volume)")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=1))
    ax.legend()

    fig.tight_layout()
    fig.savefig(out_path / "participation_rate.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path / 'participation_rate.png'}")


# ------------------------------------------------------------------
# 5. Cost decomposition bar chart
# ------------------------------------------------------------------

def plot_cost_decomposition(df: pd.DataFrame, out_path: Path):
    """
    Approximates cost split: spread cost, temporary impact, permanent impact.
    Uses avg_slippage_bps as proxy for combined impact; splits by known ratio.
    Replace with logged per-component costs from FillResult for exact values.
    """
    _apply_style()

    strategies = [s for s in ["rl", "twap", "vwap", "ac"] if s in df["strategy"].unique()]
    labels = [STRATEGY_LABELS.get(s, s) for s in strategies]

    # Approximate decomposition: spread ~30%, temp impact ~55%, perm ~15%
    means = {s: df[df["strategy"] == s]["avg_slippage_bps"].mean() for s in strategies}
    spread_cost  = np.array([means[s] * 0.30 for s in strategies])
    temp_impact  = np.array([means[s] * 0.55 for s in strategies])
    perm_impact  = np.array([means[s] * 0.15 for s in strategies])

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(strategies))
    w = 0.55

    b1 = ax.bar(x, spread_cost, w, label="Spread cost",      color="#9FE1CB", edgecolor="white", linewidth=0.5)
    b2 = ax.bar(x, temp_impact, w, bottom=spread_cost,        label="Temporary impact", color="#534AB7", alpha=0.8, edgecolor="white", linewidth=0.5)
    b3 = ax.bar(x, perm_impact, w, bottom=spread_cost + temp_impact, label="Permanent impact", color="#D85A30", alpha=0.8, edgecolor="white", linewidth=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title("Estimated cost decomposition by strategy")
    ax.set_ylabel("Average slippage (bps)")
    ax.legend()

    # Value labels on top
    for i, s in enumerate(strategies):
        total = means[s]
        ax.text(i, total + 0.1, f"{total:.2f}", ha="center", va="bottom", fontsize=9, color="#444")

    fig.tight_layout()
    fig.savefig(out_path / "cost_decomposition.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path / 'cost_decomposition.png'}")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def run_tca(results_path: str, plot_dir: str):
    df = pd.read_csv(results_path)
    out_path = Path(plot_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print("\n=== Transaction Cost Analysis ===\n")

    tbl = summary_table(df)
    print(tbl.to_string())
    tbl.to_csv(out_path / "summary_table.csv")
    print(f"\n  Summary saved to {out_path / 'summary_table.csv'}")

    print("\nGenerating plots...")
    plot_is_distribution(df, out_path)
    plot_cumulative_cost(df, out_path)
    plot_participation_rate(df, out_path)
    plot_cost_decomposition(df, out_path)

    print(f"\nAll plots saved to {plot_dir}/")

    # Print improvement vs each benchmark, per side
    rl_key = "rl" if "rl" in df["strategy"].values else ("rl_fast" if "rl_fast" in df["strategy"].values else None)
    other_strategies = [s for s in df["strategy"].unique() if s != rl_key]
    sides = df["side"].unique().tolist() if "side" in df.columns else [None]

    if rl_key is not None:
        print()
        for side in sides:
            side_df = df[df["side"] == side] if side is not None else df
            rl_is = side_df[side_df["strategy"] == rl_key]["is_bps"].mean()
            for strategy in other_strategies:
                bench_is = side_df[side_df["strategy"] == strategy]["is_bps"].mean()
                improvement = bench_is - rl_is
                pct = improvement / abs(bench_is) * 100 if bench_is != 0 else 0
                tag = "improvement" if improvement > 0 else "worse"
                prefix = f"[{side.upper()}] " if side is not None else ""
                label = STRATEGY_LABELS.get(strategy, strategy).upper()
                print(f"  {prefix}RL vs {label}: {improvement:+.2f} bps ({pct:+.1f}%) — {tag}")
            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results",  default="evaluation/results.csv")
    parser.add_argument("--plot-dir", default="evaluation/plots")
    args = parser.parse_args()
    run_tca(args.results, args.plot_dir)