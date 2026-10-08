"""
disable_drawdown_stop.py

Sets execution.drawdown_stop_frac to null in configs/default.yaml and every
walk-forward fold config.

Why: a threshold sweep showed the 150bps emergency stop was causing the
worst blowups rather than preventing them. On the fold-3/seed-43 policy it
moved the buy-side max episode cost from 19,013bps to 401bps and the
result from -6.8% to +25.8% vs TWAP, with the median unchanged at 19.70bps.
Thresholds of 0.05, 0.15 and disabled were byte-identical, so the stop only
ever fired in the 1.5-5% range and never helped.

Edits the files as TEXT rather than via yaml load/dump, so comments and
key order in default.yaml are preserved.

Usage:
    python disable_drawdown_stop.py            # apply
    python disable_drawdown_stop.py --check    # report only, change nothing
"""

import argparse
import glob
import re

LINE = "  drawdown_stop_frac: null"


def patch(path, check_only):
    txt = open(path, encoding="utf-8").read()
    lines = txt.split("\n")

    # Already set? Replace whatever value it has.
    for i, l in enumerate(lines):
        if re.match(r"^\s+drawdown_stop_frac\s*:", l):
            if l.strip() == LINE.strip():
                return "already null"
            if not check_only:
                lines[i] = LINE
                open(path, "w", encoding="utf-8").write("\n".join(lines))
            return f"changed ({l.strip()} -> {LINE.strip()})"

    # Otherwise insert directly under the execution: block header.
    for i, l in enumerate(lines):
        if re.match(r"^execution\s*:\s*$", l):
            if not check_only:
                lines.insert(i + 1, LINE)
                open(path, "w", encoding="utf-8").write("\n".join(lines))
            return "added"

    # Inline-mapping form, e.g. "execution: {a: 1, b: 2}"
    for i, l in enumerate(lines):
        m = re.match(r"^(execution\s*:\s*\{)(.*)\}\s*$", l)
        if m:
            if not check_only:
                body = m.group(2).rstrip().rstrip(",")
                lines[i] = f"{m.group(1)}{body}, drawdown_stop_frac: null}}"
                open(path, "w", encoding="utf-8").write("\n".join(lines))
            return "added (inline)"

    return "FAILED: no 'execution:' block found"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    files = ["configs/default.yaml"] + sorted(glob.glob("configs/walkforward/fold*.yaml"))
    print(("CHECK ONLY -- " if args.check else "") + f"{len(files)} config(s):\n")
    bad = 0
    for f in files:
        try:
            res = patch(f, args.check)
        except FileNotFoundError:
            res = "FAILED: not found"
        bad += res.startswith("FAILED")
        print(f"  {f:<40} {res}")

    if bad:
        print(f"\n{bad} file(s) could not be patched -- add this line by hand under 'execution:':")
        print(f"  {LINE}")
    else:
        print("\nDone. Verify with:")
        print('  findstr /n "drawdown_stop_frac" configs\\default.yaml configs\\walkforward\\fold*.yaml')


if __name__ == "__main__":
    main()