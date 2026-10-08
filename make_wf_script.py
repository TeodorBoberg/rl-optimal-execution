"""
make_wf_script.py

Turns configs/walkforward/run_wf_seeds.txt into a PowerShell script that
copies each trained model only if the run actually succeeded.

Written as a file rather than a `python -c` one-liner because PowerShell
expands $LASTEXITCODE inside a double-quoted -c argument before Python ever
sees it, so the guard silently became "if (1 -eq 0)".

Usage:
    python make_wf_script.py
    .\\configs\\walkforward\\run_wf_seeds.ps1
"""

import os

SRC = "configs/walkforward/run_wf_seeds.txt"
DST = "configs/walkforward/run_wf_seeds.ps1"

if not os.path.exists(SRC):
    raise SystemExit(
        f"{SRC} not found. Generate it first:\n"
        "  python evaluation/walkforward_seed_study.py --emit-commands --seeds 42,43,44")

lines = [l.strip() for l in open(SRC)
         if l.strip() and not l.strip().startswith("REM")]

pairs = []
i = 0
while i < len(lines) - 1:
    train, copy = lines[i], lines[i + 1]
    if not train.startswith("python") or not copy.lower().startswith("copy"):
        raise SystemExit(f"Unexpected command pair at line {i}:\n  {train}\n  {copy}")
    pairs.append((train, copy))
    i += 2

out = [
    "# Walk-forward x training-seed batch.",
    "# A model is copied ONLY if its training run exited successfully, so a",
    "# crashed run cannot silently save a stale best_model.zip under a new",
    "# name -- which would be very hard to spot many hours later.",
    "$ErrorActionPreference = 'Continue'",
    "$failed = @()",
    "",
]
for n, (train, copy) in enumerate(pairs, 1):
    target = copy.split()[-1]
    out += [
        f"Write-Host '=== [{n}/{len(pairs)}] {target} ===' -ForegroundColor Cyan",
        train,
        "if ($LASTEXITCODE -eq 0) {",
        f"    {copy}",
        f"    Write-Host 'saved {target}' -ForegroundColor Green",
        "} else {",
        f'    Write-Host "FAILED (exit $LASTEXITCODE): {target}" -ForegroundColor Red',
        f"    $failed += '{target}'",
        "}",
        "",
    ]

out += [
    "Write-Host ''",
    "if ($failed.Count -gt 0) {",
    "    Write-Host \"$($failed.Count) run(s) failed:\" -ForegroundColor Red",
    "    $failed | ForEach-Object { Write-Host \"  $_\" }",
    "} else {",
    "    Write-Host 'All runs completed.' -ForegroundColor Green",
    "}",
    "Get-ChildItem models\\wf_f*_s*.zip | Measure-Object | "
    "ForEach-Object { Write-Host \"models present: $($_.Count) of "
    f"{len(pairs)}\" }}",
]

os.makedirs(os.path.dirname(DST), exist_ok=True)
with open(DST, "w") as f:
    f.write("\n".join(out) + "\n")

print(f"Wrote {DST}  ({len(pairs)} training runs)")
print("\nRun it with:")
print(f"  .\\{DST.replace('/', chr(92))}")
print("\nTo capture all output to a file as well:")
print(f"  .\\{DST.replace('/', chr(92))} *> logs\\walkforward_run.txt")
print("\nIf PowerShell blocks the script, allow local scripts for this session:")
print("  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass")