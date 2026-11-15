"""
evaluation/guard_sensitivity.py   (STAGE 3c)

Collects urgency_frontier runs made with different guardrail settings and
puts them side by side: is the agent's edge specific to the 5% / 10-minute
guardrail, or does it hold across settings?

Each directory must contain urgency_frontier_runs.csv (and urgency_frontier.md
for the bootstrap interval, which is copied over when present).

Usage:
    python evaluation/guard_sensitivity.py "none=evaluation/stage3" "5%,10=evaluation/stage3_guard" "2.5%,10=evaluation/stage3_g025" ...
"""
import os
import re
import sys

import pandas as pd


def boot_rows(md_path):
    """urgency -> (gap, lo, hi) for 'best classical incl. spread-aware' from urgency_frontier.md."""
    out = {}
    if not os.path.exists(md_path):
        return out
    pat = re.compile(r"^\|\s*([\d.]+)\s*\|\s*best classical incl\. spread-aware\s*\|\s*([+-][\d.]+)\s*\|"
                     r"\s*\[([+-][\d.]+),\s*([+-][\d.]+)\]")
    for line in open(md_path, encoding="utf-8"):
        m = pat.match(line.strip())
        if m:
            out[float(m.group(1))] = tuple(float(m.group(i)) for i in (2, 3, 4))
    return out


def main():
    specs = [a.split("=", 1) for a in sys.argv[1:] if "=" in a]
    if not specs:
        raise SystemExit(__doc__)
    R = ["# Guardrail sensitivity", "",
         "Gap to the best classical strategy at equal risk (bps, negative = agent cheaper), "
         "mean over the runs (fold x seed), with the day-bootstrap 95% interval. `runs < 0` = how many of "
         "the runs beat the best classical strategy. Same models and episodes in every column; "
         "only the guardrail differs. The classical strategies are the unguarded ones in every column.", ""]
    tabs, worst = {}, {}
    for label, d in specs:
        r = pd.read_csv(os.path.join(d, "urgency_frontier_runs.csv"))
        b = boot_rows(os.path.join(d, "urgency_frontier.md"))
        g = r.groupby("urgency").gap_best
        tabs[label] = {u: (g.mean()[u], (r[r.urgency == u].gap_best < 0).sum(), len(r[r.urgency == u]),
                           b.get(round(u, 2))) for u in g.mean().index}
        worst[label] = r.groupby(["fold", "seed"]).gap_best.max().max()
    urgs = sorted({u for t in tabs.values() for u in t})
    R.append("| urgency | " + " | ".join(lbl for lbl, _ in specs) + " |")
    R.append("|---|" + "---|" * len(specs))
    for u in urgs:
        cells = []
        for lbl, _ in specs:
            if u not in tabs[lbl]:
                cells.append("")
                continue
            m, neg, n, bt = tabs[lbl][u]
            ci = f" [{bt[1]:+.2f}, {bt[2]:+.2f}]" if bt else ""
            cells.append(f"{m:+.2f}{ci}, runs<0: {neg}/{n}")
        R.append(f"| {u:g} | " + " | ".join(cells) + " |")
    R += ["", "Worst single run (largest gap at any urgency): " +
          ", ".join(f"{lbl}: {worst[lbl]:+.2f}" for lbl, _ in specs)]
    out = "evaluation/guard_sensitivity.md"
    with open(out, "w") as f:
        f.write("\n".join(R) + "\n")
    print("\n".join(R))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()