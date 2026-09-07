"""
agent/env.py — with urgency as a state feature

State (11 features):
    [0]  inventory_fraction
    [1]  time_fraction
    [2]  price_drift
    [3]  spread_norm
    [4]  volume_ratio
    [5]  book_imbalance
    [6]  side indicator (+1 buy / -1 sell)
    [7]  regime (0=calm, 1=volatile)
    [8]  hawkes_intensity_norm
    [9]  is_news_window
    [10] urgency (0=patient, 1=very urgent)

Urgency levels:
    0.0  — patient   (full day, minimize impact)
    0.5  — normal    (balance impact vs timing risk)
    1.0  — urgent    (exit fast, accept higher impact)

The agent sees urgency in its state and learns different
execution strategies for each level automatically.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces
from typing import Optional

try:
    from simulator.market import MarketSimulator, MarketConfig, FillResult
    from simulator.synthetic_data import (
        generate_intraday_data,
        SyntheticMarketConfig,
        get_day,
        load_csv_data,
    )
except ModuleNotFoundError:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from simulator.market import MarketSimulator, MarketConfig, FillResult
    from simulator.synthetic_data import (
        generate_intraday_data,
        SyntheticMarketConfig,
        get_day,
        load_csv_data,
    )

# Urgency presets — (risk_aversion, hold_penalty_coeff, hold_penalty_exp)
# Urgency presets — (risk_aversion, hold_penalty_coeff, hold_penalty_exp, trade_reward_coeff)
#
# trade_reward_coeff added to address a confirmed action-saturation bug:
# trace_raw_actions.py showed the trained policy outputting action=1.0 on
# EVERY step regardless of urgency or side -- fully saturated, ignoring
# two of its 13 input features entirely. Root cause: the previous flat
# trade_reward coefficient (2.0 for every urgency level) gave a large,
# immediate, urgency-independent reward for trading any amount, while the
# cost-based penalty terms are comparatively weak per unit traded and
# hold_penalty is especially weak early in an episode (time_frac^exp is
# tiny near step 0). Net effect: trading immediately and maximally was
# close to always locally optimal, regardless of urgency or anything else
# in the state. Scaling the trade bonus itself by urgency directly ties
# the "how much do I want to trade right now" incentive to the urgency
# input, rather than leaving it as an always-dominant flat constant.
#
# This is a narrower, more conservative fix than schedule-pacing-penalty
# attempts tried earlier (which added an explicit target-schedule term and
# caused real instability on an earlier, less-calibrated version of this
# environment) -- validate this alone first before considering that.
URGENCY_PRESETS = {
    0.0: (1e-6,  2.0, 3.0, 0.4),   # patient:  low risk aversion, gentle hold penalty, low trade bonus
    0.3: (1e-5,  5.0, 2.0, 0.9),   # moderate: default behavior
    0.5: (1e-4,  8.0, 1.5, 1.4),   # normal:   balanced
    0.7: (1e-3, 12.0, 1.2, 1.9),   # urgent:   trade faster
    1.0: (1e-2, 20.0, 1.0, 2.5),   # critical: exit NOW, high trade bonus
}

def get_urgency_params(urgency: float) -> tuple:
    """Interpolate urgency parameters between presets."""
    keys = sorted(URGENCY_PRESETS.keys())
    if urgency <= keys[0]:
        return URGENCY_PRESETS[keys[0]]
    if urgency >= keys[-1]:
        return URGENCY_PRESETS[keys[-1]]
    # Find surrounding keys and interpolate
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i+1]
        if lo <= urgency <= hi:
            t = (urgency - lo) / (hi - lo)
            p_lo = URGENCY_PRESETS[lo]
            p_hi = URGENCY_PRESETS[hi]
            return tuple(p_lo[j] + t * (p_hi[j] - p_lo[j]) for j in range(len(p_lo)))


class ExecutionEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        cfg: dict,
        data: Optional[pd.DataFrame] = None,
        side: str = "random",
        urgency: float = None,   # None = randomize each episode
    ):
        super().__init__()
        self.cfg = cfg
        exec_cfg = cfg["execution"]
        market_cfg_dict = cfg["market"]

        self.total_shares = exec_cfg["total_shares"]
        # Optional per-ticker order sizing: when set, the order size for each
        # episode becomes order_size_pct_adv * that ticker's real ADV, instead
        # of one fixed share count for every name.
        #
        # Motivation: a fixed 100k-share order is a very different problem for
        # SPY than for a thin name. Diagnosed consequence (see
        # trace_raw_actions.py): at a fixed size the agent is liquidity-
        # constrained across most of its action range -- any action above
        # ~1-3% of remaining yields an identical fill because the
        # participation cap binds first. That makes the action space largely
        # inert and is the leading explanation for why urgency conditioning
        # never developed: urgency can only ask the agent to trade LESS, and
        # trading less is never rewarded when you are already capped.
        #
        # Sizing by ADV keeps the execution difficulty roughly comparable
        # across tickers, which should leave the action space actually live.
        self.order_size_pct_adv = exec_cfg.get("order_size_pct_adv", None)

        # Action space parameterisation.
        #
        #   "fraction_of_remaining" (default, original):
        #       qty = action * remaining
        #   "participation_rate" (POV-style):
        #       qty = action * max_participation_rate * this_step_volume
        #
        # Why the second exists: with fraction_of_remaining, the participation
        # cap binds whenever action * remaining > max_participation_rate *
        # step_volume. Measured on real data with a 96k-share order against
        # ~6k-share minutes, that means everything above action = 0.016
        # produces an IDENTICAL fill -- 98.4% of the action range is dead, and
        # sitting at the top of it is the natural policy. That is the direct
        # cause of the observed action saturation (raw action pinned at 1.0
        # regardless of urgency, side, or ticker) and of the failure of six
        # separate reward-shaping attempts to produce urgency-conditioned
        # behaviour. Resizing the order does NOT fix it: 5% of ADV came to
        # 96,091 shares, essentially the same as the fixed 100,000, because
        # institutional order sizes are inherently many multiples of a single
        # minute's volume.
        #
        # Under participation_rate, every value in [0, 1] maps to a genuinely
        # different quantity at any order size and in any liquidity
        # condition, so the agent is choosing "trade at 5% of volume vs 25%",
        # which is both a live decision and what real POV algos actually do.
        self.action_mode = exec_cfg.get("action_mode", "fraction_of_remaining")
        if self.action_mode not in ("fraction_of_remaining", "participation_rate"):
            raise ValueError(f"Unknown action_mode: {self.action_mode}")

        # Passive execution. Off by default: enabling it changes the action
        # space dimension, so existing checkpoints cannot be loaded and a
        # retrain from scratch is required.
        self.enable_passive = exec_cfg.get("enable_passive", False)

        # Reward-term weights, for ablation studies. Each is a MULTIPLIER on
        # the corresponding term, defaulting to 1.0 so behaviour is unchanged
        # unless explicitly configured. Set a weight to 0.0 to ablate that
        # term entirely.
        #
        # disable_alpha_signal additionally zeros signal_value and
        # signal_strength in the OBSERVATION. A true alpha ablation needs
        # both: zeroing only alpha_reward_weight leaves the signal visible in
        # state, so the policy can still condition on it and the ablation
        # measures nothing. Zeroing in-place (rather than dropping the
        # features) keeps the observation dimension at 13, so the network
        # architecture is identical across ablation runs and results stay
        # comparable.
        rw = cfg.get("reward_weights", {}) or {}
        self.w_trade = rw.get("trade", 1.0)
        self.w_impact = rw.get("impact", 1.0)
        self.w_adv = rw.get("adverse_selection", 1.0)
        self.w_hold = rw.get("hold", 1.0)
        self.w_regime = rw.get("regime", 1.0)
        self.w_news = rw.get("news", 1.0)
        self.w_pacing = rw.get("pacing", 1.0)
        self.w_alpha = rw.get("alpha", 1.0)
        self.disable_alpha_signal = rw.get("disable_alpha_signal", False)

        # Transaction fees. All default to ZERO so every result produced
        # before fees were modelled reproduces exactly; set them in config to
        # enable. Representative institutional US equity values:
        #   commission_per_share      0.0005   ($0.05 per 100 shares)
        #   taker_fee_per_share       0.0030   (typical exchange take fee)
        #   sec_fee_bps_sell          0.278    (SEC Section 31, sells only)
        #   finra_taf_per_share_sell  0.000166 (FINRA TAF, sells only)
        fees = cfg.get("fees", {}) or {}
        self.commission_per_share = fees.get("commission_per_share", 0.0)
        self.taker_fee_per_share = fees.get("taker_fee_per_share", 0.0)
        self.sec_fee_bps_sell = fees.get("sec_fee_bps_sell", 0.0)
        self.finra_taf_per_share_sell = fees.get("finra_taf_per_share_sell", 0.0)
        # Rebate earned per share on PASSIVE fills (liquidity provision).
        # Typical US equity maker rebate is ~$0.0020-0.0030/share.
        self.maker_rebate_per_share = fees.get("maker_rebate_per_share", 0.0)
        self.total_steps = exec_cfg["total_steps"]
        self.default_side = side
        self.default_urgency = urgency   # None = randomize
        # Per-step position cap, as a fraction of the ORIGINAL total order
        # size. Configurable (defaults to the original hardcoded 0.15) so
        # this can be tested/tuned without silently changing behavior for
        # existing configs that don't set it explicitly.
        self.max_per_step_fraction = exec_cfg.get("max_per_step_fraction", 0.15)
        # Hard urgency-based action cap: a genuine CONSTRAINT (not a reward
        # preference) on the maximum action_frac allowed per step, scaling
        # linearly from urgency_action_cap_min (at urgency=0, patient) to
        # urgency_action_cap_max (at urgency=1, critical). Added after
        # confirming via trace_raw_actions.py that soft reward shaping
        # (urgency-scaled trade_reward + schedule-pacing penalty) was
        # trained away over a long run -- the "best" checkpoint by eval
        # reward was STILL fully saturated (raw action=1.0 regardless of
        # urgency) on every ticker tested. A hard cap can't be optimized
        # away the same way, since it's enforced structurally, not learned.
        # Bypassed entirely on the mandatory final step and drawdown-stop
        # (both already bypass the other position caps below, for the same
        # reason: a genuinely forced full liquidation must not be blocked).
        self.urgency_action_cap_min = exec_cfg.get("urgency_action_cap_min", 0.05)
        self.urgency_action_cap_max = exec_cfg.get("urgency_action_cap_max", 1.0)
        self.vol_per_step = (
            market_cfg_dict["volatility_per_min"]
            * np.sqrt(exec_cfg["step_duration_min"])
        )

        self.market_cfg = MarketConfig(
            avg_daily_volume=market_cfg_dict["avg_daily_volume"],
            steps_per_day=exec_cfg["total_steps"],
            step_duration_min=exec_cfg["step_duration_min"],
            avg_spread_bps=market_cfg_dict["avg_spread_bps"],
            volatility_per_min=market_cfg_dict["volatility_per_min"],
            eta_temporary=market_cfg_dict["eta_temporary"],
            gamma_permanent=market_cfg_dict["gamma_permanent"],
            permanent_impact_exponent=market_cfg_dict.get("permanent_impact_exponent", 1.0),
            impact_exponent=market_cfg_dict.get("impact_exponent", 0.6),
            spread_widening_factor=market_cfg_dict.get("spread_widening_factor", 1.5),
            book_depth_levels=market_cfg_dict["book_depth_levels"],
            book_replenish_halflife=market_cfg_dict["book_replenish_halflife"],
            max_participation_rate=exec_cfg["max_participation_rate"],
            adverse_selection_factor=market_cfg_dict.get("adverse_selection_factor", 0.3),
            passive_fill_prob=market_cfg_dict.get("passive_fill_prob", 0.4),
            calm_vol=market_cfg_dict.get("calm_vol", 0.0002),
            volatile_vol=market_cfg_dict.get("volatile_vol", 0.0012),
            prob_calm_to_volatile=market_cfg_dict.get("prob_calm_to_volatile", 0.005),
            prob_volatile_to_calm=market_cfg_dict.get("prob_volatile_to_calm", 0.10),
            hawkes_baseline=market_cfg_dict.get("hawkes_baseline", 10.0),
            hawkes_alpha=market_cfg_dict.get("hawkes_alpha", 0.6),
            hawkes_decay=market_cfg_dict.get("hawkes_decay", 0.3),
            news_spread_multiplier=market_cfg_dict.get("news_spread_multiplier", 2.0),
            news_probability=market_cfg_dict.get("news_probability", 0.005),
        )

        self.rng = np.random.default_rng()
        self.sim = MarketSimulator(self.market_cfg, rng=self.rng)

        if data is not None:
            self.data = data
        else:
            data_cfg = cfg["data"]
            if data_cfg["source"] == "csv":
                self.data = load_csv_data(data_cfg["path"], exec_cfg["step_duration_min"])
            else:
                syn_cfg = SyntheticMarketConfig(
                    avg_daily_volume=market_cfg_dict["avg_daily_volume"],
                    steps_per_day=exec_cfg["total_steps"],
                    volatility_per_min=market_cfg_dict["volatility_per_min"],
                    avg_spread_bps=market_cfg_dict["avg_spread_bps"],
                    step_duration_min=exec_cfg["step_duration_min"],
                )
                self.data = generate_intraday_data(syn_cfg)

        self.n_days = self.data["day"].nunique()

        # 13-dimensional state (added urgency + alpha signal)
        self.observation_space = spaces.Box(
            low=np.array( [0,  0, -0.5, 0,  0,  -1, -1, 0, 0, 0, 0, -1, 0], dtype=np.float32),
            high=np.array([1,  1,  0.5, 5,  10,  1,  1, 1, 3, 1, 1,  1, 1], dtype=np.float32),
        )
        # Action space. With passive execution enabled the agent chooses BOTH
        # how much to trade and how to split it between aggressive (crossing
        # the spread, certain fill, pays the taker fee) and passive (resting
        # at the touch, uncertain fill, earns the spread and a maker rebate
        # but suffers adverse selection).
        #
        #   action[0] = participation rate, as before
        #   action[1] = passive fraction, 0 = all aggressive, 1 = all passive
        #
        # Defaults to the original one-dimensional space so previously
        # trained models still load. Enabling this changes the action
        # dimension, so it REQUIRES retraining from scratch -- an existing
        # checkpoint cannot be loaded into a two-dimensional space.
        if self.enable_passive:
            self.action_space = spaces.Box(
                low=np.array([0.0, 0.0], dtype=np.float32),
                high=np.array([1.0, 1.0], dtype=np.float32),
            )
        else:
            self.action_space = spaces.Box(
                low=np.array([0.0], dtype=np.float32),
                high=np.array([1.0], dtype=np.float32),
            )

        self.side = "buy"
        self.urgency = 0.5
        self.remaining = 0.0
        self.step_count = 0
        self.arrival_price = 0.0
        self.total_cost = 0.0
        self.fills = []

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self.rng = np.random.default_rng(seed)
            self.sim = MarketSimulator(self.market_cfg, rng=self.rng)

        # Randomize side
        if self.default_side == "random":
            self.side = "buy" if self.rng.random() > 0.5 else "sell"
        else:
            self.side = self.default_side

        # Randomize urgency — sample from full range each episode
        if self.default_urgency is None:
            self.urgency = float(self.rng.uniform(0.0, 1.0))
        else:
            self.urgency = float(self.default_urgency)

        day_idx = self.rng.integers(0, self.n_days)
        day_data = get_day(self.data, int(day_idx))

        if len(day_data) > self.total_steps:
            day_data = day_data.iloc[:self.total_steps].reset_index(drop=True)
        elif len(day_data) < self.total_steps:
            pad = pd.concat(
                [day_data.iloc[[-1]]] * (self.total_steps - len(day_data)),
                ignore_index=True,
            )
            day_data = pd.concat([day_data, pad], ignore_index=True)

        # Use this episode's ticker's real average daily volume, if the data
        # has it (see synthetic_data.py's load_csv_data), instead of the one
        # global config value applied uniformly to every ticker. The config
        # value remains the fallback for synthetic/no-ticker-info data.
        if "ticker_adv" in day_data.columns and len(day_data) > 0:
            self.sim.cfg.avg_daily_volume = float(day_data["ticker_adv"].iloc[0])

        if "ticker" in day_data.columns and len(day_data) > 0:
            self.ticker = day_data["ticker"].iloc[0]
        else:
            self.ticker = None

        # Per-ticker order sizing (see __init__). Set BEFORE self.remaining is
        # initialised below. Everything downstream that uses total_shares does
        # so as a ratio (remaining/total_shares, filled/total_shares, and
        # is_bps normalised by total_shares * arrival_price), so varying it per
        # episode keeps observations in [0,1] and keeps is_bps comparable
        # across episodes with different order sizes.
        if self.order_size_pct_adv is not None and "ticker_adv" in day_data.columns \
                and len(day_data) > 0:
            adv = float(day_data["ticker_adv"].iloc[0])
            self.total_shares = max(1.0, adv * self.order_size_pct_adv)

        self.arrival_price = self.sim.reset(day_data)
        self.remaining = float(self.total_shares)
        self.step_count = 0
        self.total_cost = 0.0
        self.fills = []

        return self._get_obs(), {}

    def step(self, action: np.ndarray):
        action_frac = float(np.clip(action[0], 0.0, 1.0))

        # Force complete execution on final step
        is_final_step = self.step_count == self.total_steps - 1
        if is_final_step:
            action_frac = 1.0
            qty = self.remaining
        elif self.action_mode == "participation_rate":
            # POV-style: the action IS the participation rate, as a fraction
            # of the configured maximum. Every value in [0, 1] maps to a
            # distinct quantity, so the action space stays live at any order
            # size (see __init__ for why fraction_of_remaining does not).
            #
            # The hard urgency_action_cap is deliberately NOT applied here.
            # It was introduced as a structural workaround for saturation
            # caused by the fraction_of_remaining parameterisation; under
            # participation_rate the underlying cause is removed, and keeping
            # the cap would just impose urgency behaviour rather than let the
            # agent learn it -- which is the thing we actually want to test.
            step_volume = float(self.sim.day_data.loc[self.sim.step_idx, "volume"])
            target_participation = action_frac * self.market_cfg.max_participation_rate
            qty = min(target_participation * step_volume, self.remaining)
        else:
            # Hard urgency-based action cap -- a genuine constraint, not a
            # reward preference. Scales linearly from
            # urgency_action_cap_min (patient) to urgency_action_cap_max
            # (critical). Physically prevents the saturated "always dump
            # max" behavior at low urgency regardless of what the policy
            # network outputs, since soft reward shaping alone was
            # confirmed (via trace_raw_actions.py) to be trained away over
            # a long run.
            urgency_max_action = (
                self.urgency_action_cap_min
                + (self.urgency_action_cap_max - self.urgency_action_cap_min) * self.urgency
            )
            action_frac = min(action_frac, urgency_max_action)
            qty = action_frac * self.remaining

        # Backlog-aware cap multiplier: as execution falls further behind
        # an idealized linear pace, proportionally raise BOTH the per-step
        # position limit below AND the simulator's own participation cap
        # (passed through further down) -- computed ONCE here so the two
        # caps move together consistently. Without scaling env.py's own
        # flat cap too, it would become the new unintended bottleneck: qty
        # gets capped here BEFORE it ever reaches the simulator, so simply
        # raising the simulator's cap alone would have no effect once
        # env.py's own limit is the binding one.
        time_frac_before = self.step_count / self.total_steps
        ideal_remaining_frac = 1.0 - time_frac_before
        actual_remaining_frac = self.remaining / self.total_shares
        backlog_severity = max(0.0, actual_remaining_frac - ideal_remaining_frac)
        # Up to 4x the normal cap at maximum severity (fully behind, i.e.
        # 100% of the order still remaining with ~0% time left).
        backlog_multiplier = 1.0 + 3.0 * min(backlog_severity, 1.0)

        # --- Position limits ---
        # Max 15% of order per step (scaled up by backlog_multiplier when
        # falling behind schedule) — but NOT on the forced final-liquidation
        # step, otherwise the agent can strand inventory unfilled forever
        # (unfilled shares are invisible to the cost metric, which made an
        # under-trading policy look artificially cheap).
        if not is_final_step:
            max_per_step = self.total_shares * self.max_per_step_fraction * backlog_multiplier
            qty = min(qty, max_per_step)

        # --- Drawdown stop ---
        # If cost already exceeds 150 bps of order value, emergency exit
        max_loss = self.arrival_price * self.total_shares * 0.015
        drawdown_triggered = self.total_cost > max_loss
        if drawdown_triggered:
            qty = self.remaining  # force full liquidation

        # Both the scheduled final step and an emergency drawdown stop are
        # "must fully liquidate right now" situations -- force_fill=True
        # bypasses the SIMULATOR's own internal participation cap (a
        # SEPARATE cap from env.py's own 15%-per-step limit above) so a
        # mandatory full liquidation can't silently get stranded as
        # unfilled inventory against a thin bar's volume. Without this,
        # unfilled shares are invisible to the cost metric -- the same
        # failure mode as the original position-cap bug, resurfacing
        # here through a different cap at finer (1-minute) bar granularity.
        force_fill = is_final_step or drawdown_triggered

        # Same backlog_multiplier applied to the simulator's own cap, so
        # a strategy that's fallen behind schedule -- e.g. during a real
        # thin-liquidity stretch -- has a proactive, gradual way to catch
        # up at correspondingly higher (but bounded) cost, rather than
        # being blocked until force_fill kicks in only on the mandatory
        # final step. Applies uniformly to every strategy that steps
        # through this env (TWAP/VWAP/AC benchmarks and the RL agent
        # alike), since it lives here rather than in any one strategy's
        # own action formula.
        participation_cap_override = None
        if not force_fill:
            base_cap = self.market_cfg.max_participation_rate
            participation_cap_override = min(base_cap * backlog_multiplier, 1.0)

        # Split between passive and aggressive execution.
        #
        # Passive is deliberately disabled on force_fill steps (final step
        # and drawdown stop): those require guaranteed completion, and a
        # resting order might simply not fill. A real desk facing a hard
        # deadline crosses the spread for the same reason.
        passive_qty = 0.0
        if self.enable_passive and not force_fill and qty > 0:
            passive_frac = float(np.clip(action[1], 0.0, 1.0)) if len(action) > 1 else 0.0
            passive_qty = passive_frac * qty
            qty = qty - passive_qty

        fill = self.sim.execute(qty, side=self.side, force_fill=force_fill,
                                 participation_cap_override=participation_cap_override)

        if passive_qty > 0:
            pfill = self.sim.execute_passive_order(passive_qty, side=self.side)
            if pfill.filled_qty > 0:
                # Combine into one quantity-weighted FillResult so every
                # downstream consumer (cost accounting, info dict, logging)
                # sees a single fill per step regardless of the split.
                tot = fill.filled_qty + pfill.filled_qty
                w_a = fill.filled_qty / tot
                w_p = pfill.filled_qty / tot
                fill = FillResult(
                    filled_qty=tot,
                    avg_price=(fill.avg_price * w_a + pfill.avg_price * w_p)
                              if fill.filled_qty > 0 else pfill.avg_price,
                    arrival_price=fill.arrival_price,
                    slippage_bps=fill.slippage_bps * w_a + pfill.slippage_bps * w_p,
                    temporary_impact_bps=fill.temporary_impact_bps * w_a,
                    permanent_impact_bps=fill.permanent_impact_bps * w_a,
                    spread_cost_bps=fill.spread_cost_bps * w_a + pfill.spread_cost_bps * w_p,
                    adverse_selection_bps=(fill.adverse_selection_bps * w_a
                                            + pfill.adverse_selection_bps * w_p),
                    participation_rate=fill.participation_rate + pfill.participation_rate,
                    regime=fill.regime,
                )
                self.passive_filled_this_step = pfill.filled_qty
            else:
                self.passive_filled_this_step = 0.0
        else:
            self.passive_filled_this_step = 0.0

        self.fills.append(fill)

        if self.side == "buy":
            step_cost = fill.filled_qty * max(0, fill.avg_price - self.arrival_price)
        else:
            step_cost = fill.filled_qty * max(0, self.arrival_price - fill.avg_price)

        adv_sel_cost = fill.filled_qty * self.arrival_price * fill.adverse_selection_bps / 10_000
        step_cost += adv_sel_cost

        # --- Transaction fees ---
        # Real US equity execution costs, previously not modelled at all.
        # Per-share components apply to both sides; SEC Section 31 and FINRA
        # TAF are regulatory sell-side-only charges.
        #
        # Note the agent only sends aggressive (marketable) orders, so it
        # always pays the TAKER fee and never earns a maker rebate. A
        # passive-order capability would change that, and is listed as
        # future work.
        #
        # Because every strategy executes the same total share count, fees
        # add a near-identical constant to every strategy's cost. They make
        # absolute bps figures more realistic but barely affect relative
        # comparisons -- expect percentage improvements to dilute slightly.
        # --- Transaction fees ---
        # Aggressive fills cross the spread and pay the taker fee; passive
        # fills provide liquidity and earn the maker rebate instead. Charging
        # the taker fee on every share (as before passive execution existed)
        # would understate the benefit of trading passively.
        passive_filled = getattr(self, "passive_filled_this_step", 0.0)
        aggressive_filled = max(fill.filled_qty - passive_filled, 0.0)

        fee_cost = aggressive_filled * (self.commission_per_share + self.taker_fee_per_share)
        fee_cost += passive_filled * (self.commission_per_share - self.maker_rebate_per_share)
        if self.side == "sell":
            notional = fill.filled_qty * fill.avg_price
            fee_cost += notional * self.sec_fee_bps_sell / 10_000
            fee_cost += fill.filled_qty * self.finra_taf_per_share_sell
        step_cost += fee_cost

        self.remaining -= fill.filled_qty
        self.total_cost += step_cost
        self.sim.step()
        self.step_count += 1

        done = self.step_count >= self.total_steps

        # Get urgency-dependent reward parameters
        risk_aversion, hold_coeff, hold_exp, trade_coeff = get_urgency_params(self.urgency)

        shares_traded_frac = fill.filled_qty / self.total_shares
        inv_frac = self.remaining / self.total_shares
        time_frac = self.step_count / self.total_steps

        trade_reward    =  self.w_trade * trade_coeff * shares_traded_frac
        impact_penalty  = -self.w_impact * shares_traded_frac * abs(fill.slippage_bps) / 10.0
        adv_penalty     = -self.w_adv * 0.5 * shares_traded_frac * fill.adverse_selection_bps / 10.0

        # Hold penalty scales with urgency
        hold_penalty = -self.w_hold * hold_coeff * inv_frac * (time_frac ** hold_exp)

        state = self.sim.current_state
        regime_penalty = -self.w_regime * 0.3 * shares_traded_frac * (state["regime"] == "volatile")
        news_penalty   = -self.w_news * 0.5 * shares_traded_frac * state["is_news_window"]

        # Schedule-pacing penalty (Option B): directly rewards matching an
        # urgency-dependent target execution schedule -- Option A (urgency-
        # scaled trade_reward) alone was confirmed insufficient via
        # trace_raw_actions.py at both 5M and 10M timesteps (raw_action
        # stayed pinned at exactly 1.0 regardless of urgency). Root cause:
        # Option A only changes HOW MUCH reward trading gets, not WHEN it's
        # rewarded -- if front-loading into the real, measured liquid
        # morning window is genuinely the lowest-cost strategy under the
        # impact model, that stays optimal at every urgency level, since
        # urgency never made a specific time WORSE to trade at, only scaled
        # a penalty magnitude. This term directly ties reward to matching a
        # target inventory curve that depends on urgency: patient (low
        # urgency) targets near-linear depletion across the day; urgent
        # targets front-loaded depletion.
        #
        # Damping: earlier attempts (before this session's real-data
        # calibration and force_fill/backlog-cap fixes) caused the policy
        # to trade through clearly bad conditions just to stay on schedule.
        # Damping by volatility regime alone helped but wasn't complete --
        # thin REAL liquidity (not just volatility spikes) was also part of
        # why forcing schedule adherence backfired, so this version damps
        # by BOTH regime and real-time liquidity (state["volume_ratio"],
        # the same real per-minute liquidity signal already used
        # elsewhere), so the agent isn't punished for waiting out a
        # genuinely thin-volume stretch even while patient-but-behind.
        schedule_exponent = 1.0 + 5.0 * self.urgency
        target_inv_frac = (1.0 - time_frac) ** schedule_exponent
        regime_factor = 1.0 if state["regime"] == "calm" else 0.15
        liquidity_factor = float(np.clip(state["volume_ratio"], 0.1, 1.0))
        pacing_weight = 1.0 * regime_factor * liquidity_factor
        pacing_penalty = -self.w_pacing * pacing_weight * abs(inv_frac - target_inv_frac)

        # Alpha term: reward holding inventory into a favorable forward move,
        # penalize holding into an unfavorable one. Uses the ground-truth
        # forward return (fine for reward; only the noisy signal_value in
        # state goes into obs).
        side_mult = 1.0 if self.side == "buy" else -1.0
        forward_ret = self.sim.get_forward_return()
        alpha_captured_bps = side_mult * forward_ret * 10_000
        alpha_reward = self.w_alpha * 0.3 * inv_frac * alpha_captured_bps / 10.0

        reward = float(
            trade_reward + impact_penalty + adv_penalty
            + hold_penalty + regime_penalty + news_penalty + alpha_reward
            + pacing_penalty
        )

        obs = self._get_obs()
        info = {
            "side": self.side,
            "urgency": self.urgency,
            "remaining": self.remaining,
            "step_cost": step_cost,
            "total_cost": self.total_cost,
            "is_bps": self.total_cost / (self.arrival_price * self.total_shares + 1e-9) * 10_000,
            "slippage_bps": fill.slippage_bps,
            "adverse_selection_bps": fill.adverse_selection_bps,
            "participation_rate": fill.participation_rate,
            "regime": fill.regime,
            "drawdown_stop": self.total_cost > max_loss,   # add this
            "hit_position_limit": qty < action_frac * self.remaining,  # add this
        }
        return obs, reward, done, False, info

    def _get_obs(self) -> np.ndarray:
        state = self.sim.current_state
        side_ind   = 1.0 if self.side == "buy" else -1.0
        regime_ind = 1.0 if state["regime"] == "volatile" else 0.0
        hawkes_norm = np.clip(
            state["hawkes_intensity"] / (self.market_cfg.hawkes_baseline + 1e-9), 0, 3
        )
        news_ind = 1.0 if state["is_news_window"] else 0.0

        return np.array([
            self.remaining / self.total_shares,
            (self.total_steps - self.step_count) / self.total_steps,
            (state["mid_price"] - self.arrival_price) / (self.arrival_price + 1e-9),
            state["spread_bps"] / 10.0,
            np.clip(state["volume_ratio"], 0, 10),
            np.clip(state["book_imbalance"], -1, 1),
            side_ind,
            regime_ind,
            hawkes_norm,
            news_ind,
            self.urgency,           # urgency exposed to agent
            state["signal_value"] if not self.disable_alpha_signal else 0.0,
            state["signal_strength"] if not self.disable_alpha_signal else 0.0,
        ], dtype=np.float32)

    def render(self, mode="human"):
        state = self.sim.current_state
        print(
            f"[{self.side.upper()}|{state['regime']}|urgency={self.urgency:.1f}] "
            f"Step {self.step_count:3d} | "
            f"Remaining: {self.remaining:10,.0f} | "
            f"Mid: {state['mid_price']:.4f} | "
            f"Cost: ${self.total_cost:,.2f}"
        )

    def _pad_action(self, value: float) -> np.ndarray:
        """
        Shape a benchmark's scalar action to match the active action space.

        With passive execution enabled the space is two-dimensional, so
        benchmarks must supply a second element. It is set to 0.0 -- all
        aggressive -- which keeps TWAP/VWAP/AC/POV behaving exactly as they
        do without passive execution, so the comparison isolates the
        agent's use of passive orders rather than changing the baselines.
        """
        if self.enable_passive:
            return np.array([value, 0.0], dtype=np.float32)
        return np.array([value], dtype=np.float32)

    def _to_action(self, frac_of_remaining: float) -> np.ndarray:
        """
        Convert a benchmark's intended fraction-of-remaining into whatever
        the ACTIVE action space expects, so TWAP/VWAP/AC execute the same
        intended quantity under either parameterisation.

        Without this, under action_mode="participation_rate" a TWAP output of
        1/steps_left would be silently reinterpreted as a participation rate,
        and every benchmark would trade a completely different (tiny)
        quantity -- invalidating every comparison without raising any error.
        """
        frac_of_remaining = float(np.clip(frac_of_remaining, 0.0, 1.0))
        if self.action_mode != "participation_rate":
            return self._pad_action(frac_of_remaining)

        intended_qty = frac_of_remaining * self.remaining
        step_volume = float(self.sim.day_data.loc[self.sim.step_idx, "volume"])
        max_qty = self.market_cfg.max_participation_rate * max(step_volume, 1.0)
        action = intended_qty / (max_qty + 1e-9)
        return self._pad_action(float(np.clip(action, 0.0, 1.0)))

    def twap_action(self) -> np.ndarray:
        steps_left = max(1, self.total_steps - self.step_count)
        return self._to_action(1.0 / steps_left)

    def vwap_action(self, volume_profile: np.ndarray) -> np.ndarray:
        if self.step_count >= len(volume_profile):
            frac = 1.0
        else:
            remaining_profile = volume_profile[self.step_count:]
            frac = volume_profile[self.step_count] / (remaining_profile.sum() + 1e-9)
        return self._to_action(frac)

    def pov_action(self, participation_rate: float) -> np.ndarray:
        """
        Constant percentage-of-volume benchmark: trade a fixed fraction of
        each step's actual volume, regardless of schedule or conditions.

        This is the natural head-to-head for the RL policy, which under
        action_mode="participation_rate" is itself a POV algo -- the
        difference being that the agent varies its rate with market state
        and urgency while this benchmark holds it constant. Beating TWAP,
        VWAP and AC shows the policy beats schedule-based algos; beating a
        tuned POV shows it beats a volume-based one on the same terms.

        Note the order must be completable: with an order of X% of ADV, a
        constant rate below X% cannot finish within the session and will be
        force-liquidated at the close. With orders at 5% of ADV, rates at or
        above ~5% complete; 10% completes in roughly half a day.
        """
        step_volume = float(self.sim.day_data.loc[self.sim.step_idx, "volume"])
        qty = participation_rate * step_volume
        frac = min(qty / (self.remaining + 1e-9), 1.0)
        return self._to_action(frac)

    def ac_action(self) -> np.ndarray:
        steps_left = self.total_steps - self.step_count
        if steps_left <= 1:
            return self._to_action(1.0)
        sigma = self.vol_per_step
        eta = self.market_cfg.eta_temporary
        risk_aversion, _, _, _ = get_urgency_params(self.urgency)
        kappa = np.sqrt(risk_aversion * sigma**2 / (eta + 1e-12))
        kappa = max(kappa, 1e-6)
        denom = np.sinh(kappa * steps_left) + 1e-9
        qty_t = self.remaining * (1 - np.sinh(kappa * (steps_left - 1)) / denom)
        frac = np.clip(qty_t / (self.remaining + 1e-9), 0, 1)
        return self._to_action(frac)