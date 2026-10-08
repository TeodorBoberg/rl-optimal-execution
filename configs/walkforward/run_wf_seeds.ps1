# Walk-forward x training-seed batch.
# A model is copied ONLY if its training run exited successfully, so a
# crashed run cannot silently save a stale best_model.zip under a new
# name -- which would be very hard to spot many hours later.
$ErrorActionPreference = 'Continue'
$failed = @()

Write-Host '=== [1/12] models\wf_f0_s42.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold0.yaml --timesteps 10000000 --train-seed 42
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f0_s42.zip
    Write-Host 'saved models\wf_f0_s42.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f0_s42.zip" -ForegroundColor Red
    $failed += 'models\wf_f0_s42.zip'
}

Write-Host '=== [2/12] models\wf_f0_s43.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold0.yaml --timesteps 10000000 --train-seed 43
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f0_s43.zip
    Write-Host 'saved models\wf_f0_s43.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f0_s43.zip" -ForegroundColor Red
    $failed += 'models\wf_f0_s43.zip'
}

Write-Host '=== [3/12] models\wf_f0_s44.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold0.yaml --timesteps 10000000 --train-seed 44
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f0_s44.zip
    Write-Host 'saved models\wf_f0_s44.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f0_s44.zip" -ForegroundColor Red
    $failed += 'models\wf_f0_s44.zip'
}

Write-Host '=== [4/12] models\wf_f1_s42.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold1.yaml --timesteps 10000000 --train-seed 42
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f1_s42.zip
    Write-Host 'saved models\wf_f1_s42.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f1_s42.zip" -ForegroundColor Red
    $failed += 'models\wf_f1_s42.zip'
}

Write-Host '=== [5/12] models\wf_f1_s43.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold1.yaml --timesteps 10000000 --train-seed 43
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f1_s43.zip
    Write-Host 'saved models\wf_f1_s43.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f1_s43.zip" -ForegroundColor Red
    $failed += 'models\wf_f1_s43.zip'
}

Write-Host '=== [6/12] models\wf_f1_s44.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold1.yaml --timesteps 10000000 --train-seed 44
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f1_s44.zip
    Write-Host 'saved models\wf_f1_s44.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f1_s44.zip" -ForegroundColor Red
    $failed += 'models\wf_f1_s44.zip'
}

Write-Host '=== [7/12] models\wf_f2_s42.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold2.yaml --timesteps 10000000 --train-seed 42
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f2_s42.zip
    Write-Host 'saved models\wf_f2_s42.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f2_s42.zip" -ForegroundColor Red
    $failed += 'models\wf_f2_s42.zip'
}

Write-Host '=== [8/12] models\wf_f2_s43.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold2.yaml --timesteps 10000000 --train-seed 43
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f2_s43.zip
    Write-Host 'saved models\wf_f2_s43.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f2_s43.zip" -ForegroundColor Red
    $failed += 'models\wf_f2_s43.zip'
}

Write-Host '=== [9/12] models\wf_f2_s44.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold2.yaml --timesteps 10000000 --train-seed 44
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f2_s44.zip
    Write-Host 'saved models\wf_f2_s44.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f2_s44.zip" -ForegroundColor Red
    $failed += 'models\wf_f2_s44.zip'
}

Write-Host '=== [10/12] models\wf_f3_s42.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold3.yaml --timesteps 10000000 --train-seed 42
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f3_s42.zip
    Write-Host 'saved models\wf_f3_s42.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f3_s42.zip" -ForegroundColor Red
    $failed += 'models\wf_f3_s42.zip'
}

Write-Host '=== [11/12] models\wf_f3_s43.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold3.yaml --timesteps 10000000 --train-seed 43
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f3_s43.zip
    Write-Host 'saved models\wf_f3_s43.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f3_s43.zip" -ForegroundColor Red
    $failed += 'models\wf_f3_s43.zip'
}

Write-Host '=== [12/12] models\wf_f3_s44.zip ===' -ForegroundColor Cyan
python run.py --config configs/walkforward/fold3.yaml --timesteps 10000000 --train-seed 44
if ($LASTEXITCODE -eq 0) {
    copy models\best_model.zip models\wf_f3_s44.zip
    Write-Host 'saved models\wf_f3_s44.zip' -ForegroundColor Green
} else {
    Write-Host "FAILED (exit $LASTEXITCODE): models\wf_f3_s44.zip" -ForegroundColor Red
    $failed += 'models\wf_f3_s44.zip'
}

Write-Host ''
if ($failed.Count -gt 0) {
    Write-Host "$($failed.Count) run(s) failed:" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host 'All runs completed.' -ForegroundColor Green
}
Get-ChildItem models\wf_f*_s*.zip | Measure-Object | ForEach-Object { Write-Host "models present: $($_.Count) of 12" }
