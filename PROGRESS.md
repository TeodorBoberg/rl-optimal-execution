# Project Progress

## What this is
RL optimal execution algorithm. Learns to buy/sell large stock orders with
minimal market impact, beating TWAP/VWAP/Almgren-Chriss benchmarks. Goal:
present this to a quant hedge fund (contact: Anders, at Lynx).

## Current status (as of this session)
- Core pipeline is now methodologically sound: proper train/test split,
  train/eval simulator consistency, alpha signal integration, per-ticker
  liquidity calibration. Several serious bugs that were inflating results
  have been found and fixed (see "Bugs found and fixed" below).
- Ticker universe expanded from 6 to 19 names, downloaded and combined
  successfully (`data/combined.csv` confirmed present with all 19).
- **Not yet done: a real full training run with the new 19-ticker data +
  the per-ticker ADV fix.** All prior "final" numbers (the ~30-53%
  improvement figures) were on the old 6-ticker universe. This is the
  immediate next step.
- Got real practitioner feedback from Anders (Lynx) on this project —
  see "Anders' feedback" section below. Not yet acted on.

---

## Session history — what was done, in order

### 1. Alpha signal integration
Added a noisy forward-looking signal (`signal_value`, `signal_strength`)
to the observation space (11 → 13 features), calibrated to ~60-65%
directional accuracy (deliberately weak/noisy, like a real alpha source —
first pass was accidentally too clean at ~80% accuracy and got retuned).
Reward now includes an `alpha_captured` term. Implemented in both
simulators (`market.py`, `vec_market.py`) and wired through `env.py` and
`train_fast.py`'s obs space bounds.

### 2. Bugs found and fixed
- **`agent/env.py` position-cap bug (serious):** the forced full-liquidation
  on the last step (`action_frac = 1.0`) was being silently overridden by
  a `max_per_step = total_shares * 0.15` cap applied unconditionally,
  stranding up to 85% of sell orders unfilled. Unfilled inventory was
  invisible to the cost metric, making the RL agent's "near-zero cost"
  results look like skill when it was actually just not trading. Fixed by
  exempting the forced final step from the cap.
- **`evaluation/backtest_fast.py` `NameError`:** `strategies` was a
  variable local to `run_backtest()`, referenced in the `__main__` block
  where it wasn't defined. Fixed.
- **`evaluation/backtest_fast.py` and `evaluation/tca.py` only ever
  compared RL vs TWAP**, and blended buy/sell into one averaged number.
  Both now loop over every benchmark (TWAP/VWAP/AC) and report buy/sell
  separately.

### 3. Discovered: train/eval simulator mismatch
Training (`train_fast.py` → `vec_market.py`, formula-based impact, no
real order book) and evaluation (`backtest_fast.py` → `agent/env.py` →
`market.py`, LOB-based with real depth levels) were two different market
models. This was masked by the position-cap bug above; once that was
fixed, buy-side performance collapsed from "+40-55% improvement" to
"-200% worse", revealing the policy had learned to hoard-then-dump in a
way that was cheap in the vectorized sim but catastrophic against a real
order book.

### 4. Discovered: no train/test split (data leakage)
Training and evaluation were drawing from the exact same `combined.csv`,
including the `EvalCallback` used for model selection during training —
so even "best checkpoint" selection was happening on in-sample data. This
was confirmed by testing on GOOGL (a ticker documented as originally
held out): results dropped from ~40-99% "improvement" to a mixed,
modest, sometimes-losing picture — the honest baseline.

### 5. Fix: proper chronological train/test split
New file `simulator/data_split.py` — splits **chronologically, per
ticker** (each ticker's earliest ~80% of days → train, latest ~20% →
test), not randomly (avoids lookahead bias) and not by holding out whole
tickers (every ticker contributes to both sets). Re-indexes `day` to stay
contiguous per split (required by `get_day()` / grid-building code
elsewhere). Wired into `agent/train.py`, `agent/train_fast.py` (both the
main training env AND the `EvalCallback`'s eval env), and
`evaluation/backtest_fast.py`. Config: `data.test_frac` in
`configs/default.yaml` (default 0.2).

### 6. Decision: unify simulators by training on the LOB-based one
Given the goal is a credible hedge-fund pitch, decided to train AND
evaluate on `market.py` (real order book, Hawkes-driven depth) rather
than the faster formula-based `vec_market.py`, accepting a training
slowdown (SB3 `SubprocVecEnv` is ~2,000 steps/sec vs. ~50,000-200,000 for
the vectorized sim). New file **`run.py`** — clone of `run_fast.py` but
Phase 1 calls `agent.train.train()` instead of `agent.train_fast.train()`.
Phases 2/3 (backtest, TCA) were already on the LOB simulator, so no
changes needed there. `run.py` was smoke-tested end-to-end (tiny
timesteps) and works; **has not yet been run for a real full training
pass.**

### 7. Statistical significance check
Ran a paired t-test (RL vs each benchmark, per side) on the last
6-ticker/train-test-split result. 5/6 comparisons significant at raw
p<0.05; after Bonferroni correction for multiple comparisons (6 tests →
threshold p<0.0083), only **BUY vs Almgren-Chriss** and **SELL vs TWAP**
held up clearly. **SELL vs VWAP was not significant at all** (p=0.11) —
a genuine, honestly-reported weak spot, not just noise.
`check_significance.py` (root-level diagnostic script) has the code.

### 8. Ticker universe expansion (6 → 19)
Original 6: AAPL, MSFT, NVDA, TSLA, GOOGL, SPY — almost all mega-cap
tech + one index. Added 13 for sector/cap/vol diversity: JPM, BAC
(financials), JNJ, UNH (healthcare), XOM, CVX (energy), WMT, PG (staples),
CAT (industrials), DUK (utilities/low-vol anchor), ETSY, ROKU (mid-cap —
genuine liquidity stress test, much lower ADV than the mega-caps), QQQ
(second index/ETF). All 19 downloaded and combined successfully into
`data/combined.csv` (confirmed: 19 `*_5m.csv` files, `combine.py` ran
clean).

### 9. Fix: per-ticker average daily volume calibration
Found that `market.avg_daily_volume` in `default.yaml` (a single fixed
5,000,000 constant) was being applied uniformly to every ticker regardless
of real liquidity — e.g. NVDA's real ADV is ~130M (26x the config value),
while a mid-cap like ETSY would be far below it. This constant only
feeds the Hawkes intensity normalization (`qty / avg_vol`), but the
miscalibration is large and systematic. Fixed:
- `simulator/synthetic_data.py`'s `load_csv_data()` now computes each
  ticker's real average daily volume from the actual data and attaches it
  as a `ticker_adv` column.
- `agent/env.py`'s `ExecutionEnv.reset()` reads it per-episode and
  overrides `self.sim.cfg.avg_daily_volume` before stepping.
- `simulator/vec_market.py` / `agent/train_fast.py` got the harder
  version of the same fix — a per-environment array (`self.avg_daily_volume`,
  shape `(n_envs,)`) rather than one shared scalar, since a batch of
  parallel environments can span multiple tickers at once. Verified with
  a test showing 5 distinct ADV values correctly assigned across a batch
  spanning multiple tickers.
- All of this tested and confirmed working against the real (6-ticker,
  pre-expansion) `combined.csv` before being handed off. **Needs
  re-verification against the new 19-ticker file**, though the mechanism
  is generic and should work unchanged.

### 10. Environment/tooling fixes
- PowerShell execution policy blocking venv activation — resolved
  (`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`,
  then `.\venv\Scripts\Activate.ps1`).
- Clarified: diagnostic Python snippets must always be saved as `.py`
  files and run with `python file.py` — pasting raw Python into a
  PowerShell (or any shell) prompt breaks because of `&`/operator
  conflicts. All diagnostic scripts provided follow this pattern already.
- `combine.py` troubleshooting — was a false alarm, resolved once working
  directory was confirmed correct.

### 11. Anders' feedback (Lynx) — see next section, not yet acted on

---

## Anders' feedback (practitioner input, Lynx)

Translated/summarized from Swedish text messages:

1. Execution research is hard because it typically requires **tick-level
   data with quote/depth information** — not 5-minute OHLCV bars, which
   is all `combined.csv` currently has.
2. The core difficulty is **market impact estimation**. Without your own
   large orders to directly observe impact from, you have to infer it by
   identifying which trades are "aggressor" (buyer-/seller-initiated) —
   i.e. **trade classification** (tick rule, Lee-Ready algorithm) — then
   studying how aggressive trades move price.
3. Pointed to **Jean-Philippe Bouchaud** (at CFM, a Lynx competitor) as a
   starting point — known for the **square-root law of market impact**
   (impact ∝ √(order size / ADV), i.e. exponent ≈ 0.5). Worth noting:
   the project's current `impact_exponent: 0.6` config value is already
   close to this, which is a good sign, but it was hand-picked, not
   calibrated or cited — worth fixing that gap before presenting.

This directly targets the weakest, least-defensible part of the current
simulator: the impact model's parameters (`eta_temporary`,
`gamma_permanent`, `impact_exponent`, LOB `book_depth_levels`,
`book_replenish_halflife`) are all hand-set config constants, never
validated against real market data.

---

## Code structure

```
rl_execution/
├── run.py                       [NEW this session] Full pipeline, LOB simulator
│                                 throughout (train -> backtest -> TCA). Preferred
│                                 entrypoint for anything presentation-bound.
├── run_fast.py                  [legacy/superseded] Vectorized training + LOB
│                                 eval -- has the train/eval mismatch. Keep for
│                                 quick experiments only, not for real numbers.
├── combine.py                   [unmodified, lives in data/] Combines *_5m.csv
│                                 into combined.csv. Assigns global contiguous
│                                 `day` index per ticker block.
├── download_data.py             [unmodified, not seen this session] Downloads
│                                 one ticker's 5-min OHLCV via yfinance.
│
├── configs/
│   └── default.yaml             [MODIFIED] +alpha_horizon_steps, alpha_noise_std,
│                                 alpha_decay, alpha_reward_weight (under `market:`),
│                                 +data.test_frac (0.2 default)
│
├── data/
│   ├── combined.csv             19 tickers as of this session (was 5-6)
│   └── *_5m.csv                 19 raw per-ticker files
│
├── simulator/
│   ├── market.py                [MODIFIED] LOB-based sim. +alpha signal
│   │                             (_compute_alpha_signals, get_forward_return).
│   │                             Used by agent/env.py.
│   ├── vec_market.py            [MODIFIED] Vectorized formula-based sim.
│   │                             +alpha signal, +per-env avg_daily_volume
│   │                             (day_adv array). Used by agent/train_fast.py.
│   ├── synthetic_data.py        [MODIFIED] load_csv_data() now computes and
│   │                             attaches `ticker_adv` column (real per-ticker
│   │                             average daily volume).
│   ├── data_split.py            [NEW] train_test_split_days() -- chronological,
│   │                             per-ticker, contiguous day re-indexing.
│   └── __init__.py
│
├── agent/
│   ├── env.py                   [MODIFIED] ExecutionEnv. 13-dim obs (was 11).
│   │                             Fixed position-cap-overrides-forced-liquidation
│   │                             bug. Per-episode avg_daily_volume override
│   │                             from ticker_adv.
│   ├── train.py                 [MODIFIED] SB3 PPO + SubprocVecEnv + ExecutionEnv
│   │                             (LOB sim). Now loads+splits data once, trains on
│   │                             train_df, EvalCallback uses test_df.
│   ├── train_fast.py            [MODIFIED] SB3 PPO + BulkVecEnv + VecMarketSimulator
│   │                             (vectorized sim). Same data-split wiring as
│   │                             train.py. BulkVecEnv now accepts optional
│   │                             `data=` override DataFrame.
│   └── __init__.py
│
├── evaluation/
│   ├── backtest_fast.py         [MODIFIED] Fixed NameError. Compares RL vs all
│   │                             benchmarks (not just TWAP), per side (not
│   │                             blended). Now loads+splits data independently
│   │                             and evaluates ONLY on the held-out test split.
│   ├── tca.py                   [MODIFIED] summary_table() now groups by
│   │                             (strategy, side) not just strategy. Final
│   │                             comparison block loops over all benchmarks
│   │                             and both sides (was TWAP-only, blended).
│   └── (backtest.py -- slow-path equivalent -- never seen this session, may
│        not exist / may be superseded by backtest_fast.py)
│
└── (root-level diagnostic scripts, not part of core pipeline, written
     ad hoc this session -- safe to delete or keep for reference)
    ├── check_sell.py             unfilled_fraction / participation_rate check
    ├── check_sell_correlation.py unfilled_fraction vs cost correlation check
    └── check_significance.py     paired t-test, RL vs each benchmark per side
```

### Important compatibility note
Observation space is now **13-dim** (was 11). Any old saved model
checkpoint will fail to load (shape mismatch) -- always retrain from
scratch after these changes, never resume/fine-tune from an old
checkpoint.

---

## What to fix / do next (priority order)

1. **Run a real full training pass with `run.py` on the new 19-ticker
   data.** This is the immediate next step -- everything above has been
   smoke-tested but not run for real at scale on the expanded universe.
   ```
   python run.py --timesteps 5000000
   ```
   Expect this to take considerably longer than `run_fast.py` did
   (LOB sim + SubprocVecEnv is slow -- budget well over an hour, possibly
   several). Expect performance numbers to look more modest than prior
   runs -- mid-caps like ETSY/ROKU are genuinely liquidity-constrained
   relative to the fixed `execution.total_shares: 100_000` order size,
   which is a harder, more realistic problem than mega-cap-only training.

2. **Address Anders' feedback -- market impact model credibility.** This
   is the single biggest thing standing between "a working prototype"
   and "something a quant desk would take seriously." Concrete options,
   roughly in order of effort:
   - Read up on Bouchaud's square-root law papers, compare to current
     `impact_exponent: 0.6` -- cheapest, do this first.
   - Implement a trade-classification-based (tick rule / Lee-Ready)
     empirical impact estimate from the existing 5-min data -- limited by
     bar granularity but directionally useful, and would give a real
     number to calibrate `eta_temporary`/`gamma_permanent` against
     instead of hand-picked constants.
   - Longer-term: get real tick-level data (Anders' stated ideal) -- bigger
     lift, worth scoping once the above two are done.

3. **Investigate the SELL vs VWAP weakness** (p=0.11, not significant) --
   paused earlier in favor of the simulator-unification work. Worth
   returning to once the 19-ticker retrain is done, since the underlying
   data just changed substantially.

4. **Re-verify the significance test and per-side/per-benchmark breakdown
   on the new 19-ticker, LOB-trained results** -- the last significance
   check was on the old 6-ticker, still-not-fully-unified setup. Rerun
   `check_significance.py` against the new `results.csv` once available.

5. **Minor/nice-to-have:** `evaluation/backtest.py` (a non-fast backtest
   script, if it exists / is separate from `backtest_fast.py`) was never
   reviewed this session -- worth checking it isn't a third, diverging
   implementation of the same comparison logic now that `backtest_fast.py`
   and `tca.py` have been patched.

---

## How to run (current, as of this session)

```
cd rl_execution
venv\Scripts\activate                    (or .\venv\Scripts\Activate.ps1 in PowerShell)

# Full realistic pipeline (train + backtest + TCA), LOB simulator throughout:
python run.py --timesteps 5000000

# Backtest only, using an existing checkpoint:
python run.py --skip-train --model-path models/best_model.zip

# Re-download / re-combine data (from inside data/ folder):
python download_data.py --ticker <TICKER> --days 50
python combine.py

# Diagnostics (run from rl_execution root):
python check_significance.py
```