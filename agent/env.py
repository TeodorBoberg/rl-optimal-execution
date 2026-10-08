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
# risk_aversion RESCALED. The previous values (1e-6 to 1e-2) made the
# Almgren-Chriss benchmark mathematically identical to TWAP, so the project
# reported three schedule-based benchmarks while having only two.
#
# AC's trading rate comes from kappa = sqrt(risk_aversion * sigma^2 / eta).
# With sigma = 3e-4 (per-minute return) and the calibrated eta = 5e-4, the
# old values gave kappa ~1e-5 to 1e-3, so sinh(kappa*n)/sinh(kappa*(n-1))
# came to 1.00257 -- exactly 1/389, i.e. a linear schedule, i.e. TWAP. The
# duplication was visible in per-ticker results as TWAP and AC matching to
# one decimal on every row.
#
# The presets below were chosen from the resulting completion curves
# (fraction of the order done by 25% / 50% / 75% through the session,
# against 25/50/75 for linear TWAP):
#     0.05 -> 31% / 57% / 79%   barely front-loaded
#     0.20 -> 45% / 72% / 88%
#     0.60 -> 63% / 87% / 96%
#     1.50 -> 78% / 95% / 99%
#     5.00 -> 93% / 99% / 100%  nearly immediate
# Above ~10 the schedule degenerates into "dump everything at the open".
#
# risk_aversion is unpacked in step() but unused in the reward, so this
# changes ONLY the AC benchmark -- no retraining required.
URGENCY_PRESETS = {
    0.0: (0.05,  2.0, 3.0, 0.4),   # patient:  close to linear
    0.3: (0.20,  5.0, 2.0, 0.9),   # moderate
    0.5: (0.60,  8.0, 1.5, 1.4),   # normal:   clearly front-loaded
    0.7: (1.50, 12.0, 1.2, 1.9),   # urgent
    1.0: (5.00, 20.0, 1.0, 2.5),   # critical: mostly done by the quarter mark
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
        #   "clock_rate":
        #       qty = m(action) * total_shares / total_steps, where
        #       m = 10 ** (clock_rate_decades * (action - 0.5)): a multiple of
        #       the TWAP pace on a log scale (0.5 = TWAP, default range 0.01x
        #       to 100x), and action ~0 = trade nothing.
        #   Why: participation_rate makes the agent a volume-follower -- its
        #   natural "constant" action trades in proportion to each bar's
        #   volume. The simulator prices temporary impact against AVERAGE
        #   volume per minute, not the bar's own volume, so following volume
        #   makes per-bar size uneven and, with convex impact, costs more
        #   than a smooth clock-time schedule (VWAP vs TWAP: +0.5bps). Under
        #   clock_rate a constant action IS a smooth schedule, so the agent
        #   can express what Almgren-Chriss does directly, and can still
        #   condition on volume if that pays. Every action value maps to a
        #   distinct quantity, as with participation_rate.
        self.clock_rate_decades = float(exec_cfg.get("clock_rate_decades", 4.0))

        # Action squashing. Stable-Baselines3 samples actions from an
        # unbounded Gaussian and CLIPS them to the Box. With a [0, 1] box,
        # every sample below 0 becomes "trade nothing" and the policy gets no
        # signal about how far below 0 it is -- so it can drift into that
        # region and use it as an on/off switch. Measured in Stage 1: the
        # agent traded nothing in 28-40% of minutes with the order still
        # open, and its trade size swung ~2.1-2.3x minute to minute (TWAP
        # 1.0x, POV 20% 1.6x). With impact growing as size**1.65, pausing and
        # catching up costs ~1.6x the temporary impact of trading evenly.
        #
        # action_squash = "sigmoid": the action space becomes [-B, B] and the
        # environment maps each element through a sigmoid to [0, 1] before
        # anything else. Clipping only happens at +-B (B = 10, i.e. below
        # 5e-5 of the range), far from where the policy operates, and the
        # untrained policy starts at 0.5 instead of 0. The trade-size
        # semantics of action_mode are unchanged, so benchmarks trade exactly
        # the same quantities (they are converted with the inverse, logit).
        self.action_squash = exec_cfg.get("action_squash", None)
        if self.action_squash not in (None, "sigmoid"):
            raise ValueError(f"Unknown action_squash: {self.action_squash}")
        self.squash_bound = float(exec_cfg.get("action_squash_bound", 10.0))

        # book_imbalance in the observation is generated noise
        # (rng.uniform(0.7, 1.3) on every call, see MarketSimulator.current_state).
        # drop_noise_obs zeroes it; the observation keeps 13 dimensions.
        self.drop_noise_obs = bool(exec_cfg.get("drop_noise_obs", False))
        # The observation includes the simulator's HIDDEN state: the volatility
        # regime indicator and the news-window flag. A real algorithm cannot
        # see either; it would have to estimate them. hide_state_obs zeroes
        # both (evaluation diagnostic: how much of the agent's edge needs them).
        self.hide_state_obs = bool(exec_cfg.get("hide_state_obs", False))
        # honest_obs: hide the hidden state AND put in its place what a real
        # trader can observe before deciding:
        #   slot 7 (was regime flag)  realised volatility of the mid over the
        #                              last honest_vol_window minutes, relative
        #                              to the calibrated per-minute vol, /3,
        #                              clipped to [0, 1]
        #   slot 9 (was news flag)     the CURRENT quoted spread from the book
        #                              (public before trading), relative to the
        #                              average spread, /5, clipped to [0, 1]
        # The observation keeps 13 dimensions. The Hawkes input (slot 8) stays:
        # in this simulator it is a deterministic function of the order's own
        # past trades, which the trader knows.
        self.honest_obs = bool(exec_cfg.get("honest_obs", False))
        self.honest_vol_window = int(exec_cfg.get("honest_vol_window", 15))
        if self.honest_obs:
            self.hide_state_obs = True

        # Optional smoothness penalty (mean_variance reward only), off by
        # default: c * ((q_t - q_{t-1}) / TWAP_pace)**2 per step. A shaping
        # term -- use only if squashing alone does not remove the jitter.
        self.action_change_penalty = float(exec_cfg.get("action_change_penalty", 0.0))
        #   "adv_rate":
        #       qty = action * adv_rate_max * (ADV / total_steps): a LINEAR
        #       rate against AVERAGE minute volume. A constant action is a
        #       smooth clock-time schedule (like clock_rate) but without the
        #       log scale that amplified jitter. Default max = 2x the average
        #       minute's volume, so benchmark quantities are representable
        #       (the simulator's own participation cap binds well before).
        self.adv_rate_max = float(exec_cfg.get("adv_rate_max", 2.0))
        if self.action_mode not in ("fraction_of_remaining", "participation_rate",
                                    "clock_rate", "adv_rate"):
            raise ValueError(f"Unknown action_mode: {self.action_mode}")

        # Passive execution. Off by default: enabling it changes the action
        # space dimension, so existing checkpoints cannot be loaded and a
        # retrain from scratch is required.
        self.enable_passive = exec_cfg.get("enable_passive", False)

        # Bars of lag between the data the policy observes and the bar it
        # trades in. 1 = causal (observe the completed previous bar, act in
        # the current one). 0 reproduces the earlier non-causal behaviour and
        # exists only for comparison.
        self.observation_lag = exec_cfg.get("observation_lag", 1)

        # Emergency drawdown stop: if accumulated cost exceeds this fraction
        # of the order's arrival value, liquidate everything immediately.
        #
        # 0.015 (150bps) was hand-chosen and never justified. It is
        # implicated in the worst observed blowups: on a CVX day where the
        # order was 9.1% of the day's ENTIRE volume, TWAP tripped the stop at
        # step 298 and force-filled the remainder for 14,436bps -- almost
        # certainly worse than simply continuing to trade would have been.
        # The "protection" caused the loss it was meant to prevent.
        #
        # Set to null/None in config to disable the stop entirely.
        self.drawdown_stop_frac = exec_cfg.get("drawdown_stop_frac", 0.015)

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

        # Reward definition.
        #
        # "shaped" (original): eight hand-tuned terms (trade incentive,
        #   slippage, adverse selection, holding, regime, news, pacing,
        #   alpha). It never charges permanent impact and is not the
        #   quantity the agent is evaluated on.
        #
        # "mean_variance": the Almgren-Chriss objective, per step,
        #       r_t = -[ dCost_t  +  lambda(u) * f_t^2 * sigma_step^2 ] * reward_scale
        #   dCost_t   this step's execution + own permanent impact + fees,
        #             in bps of the order (the signed-IS components that
        #             have non-zero expectation)
        #   f_t       fraction of the order still held after this step
        #   sigma     per-step volatility in bps (same sigma the AC benchmark uses)
        #   lambda(u) = lambda_min * (lambda_max / lambda_min) ** urgency
        #   Summed over the episode this is E[cost] + lambda * Var[cost] under
        #   the AC price model. Market drift is left OUT of the reward: its
        #   expectation is zero and its variance is what the lambda term
        #   prices, so including the realised drift would only add ~100bps
        #   of noise per episode to a ~10bps signal. The default lambda range
        #   spans the empirical AC frontier (implied lambda between adjacent
        #   AC settings runs from ~7e-5 to ~1.2e-2 per bps).
        self.reward_mode = exec_cfg.get("reward_mode", "shaped")
        if self.reward_mode not in ("shaped", "mean_variance"):
            raise ValueError(f"Unknown reward_mode: {self.reward_mode}")
        self.mv_lambda_min = float(exec_cfg.get("mv_lambda_min", 5e-5))
        self.mv_lambda_max = float(exec_cfg.get("mv_lambda_max", 2e-2))
        self.reward_scale = float(exec_cfg.get("reward_scale", 0.1))

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
            permanent_impact_mode=market_cfg_dict.get("permanent_impact_mode", "per_fill"),
            permanent_cum_bps_at_ref=market_cfg_dict.get("permanent_cum_bps_at_ref", 7.5),
            permanent_cum_ref_frac=market_cfg_dict.get("permanent_cum_ref_frac", 0.05),
            permanent_cum_exponent=market_cfg_dict.get("permanent_cum_exponent", 0.5),
            impact_volume_ref=market_cfg_dict.get("impact_volume_ref", "average"),
            impact_exponent=market_cfg_dict.get("impact_exponent", 0.6),
            # These two were never passed through: the config's values were
            # silently ignored and the dataclass defaults (0.3 / 0.4) used.
            # The defaults equal the config values, so no earlier result
            # changes -- but overriding them did nothing.
            spread_impact_exp=market_cfg_dict.get("spread_impact_exp", 0.3),
            vol_impact_exp=market_cfg_dict.get("vol_impact_exp", 0.4),
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
        n_act = 2 if self.enable_passive else 1
        lo, hi = ((-self.squash_bound, self.squash_bound) if self.action_squash
                  else (0.0, 1.0))
        self.action_space = spaces.Box(
            low=np.full(n_act, lo, dtype=np.float32),
            high=np.full(n_act, hi, dtype=np.float32),
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
        self.day_idx = int(day_idx)   # recorded so evaluation can cluster by trading day
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
        # SIGNED implementation shortfall and its decomposition (see step()).
        # self.total_cost is kept exactly as before -- clipped at zero per
        # fill -- so every existing result and the drawdown stop reproduce.
        self.total_cost_signed = 0.0
        self.cost_drift = 0.0        # market moved between arrival and this fill
        self.cost_permanent = 0.0    # the order's own accumulated permanent impact
        self.cost_execution = 0.0    # fill vs the mid at the time: spread, temp impact, adverse selection
        self.cost_fees = 0.0
        self._mv_prev_cost = 0.0
        self._prev_fill_qty = None
        self._mid_hist = []
        self.fills = []

        return self._get_obs(), {}

    def _unsquash(self, action) -> np.ndarray:
        a = np.asarray(action, dtype=np.float64).ravel()
        out = 1.0 / (1.0 + np.exp(-np.clip(a, -50, 50)))
        eps = 1e-6
        out[a <= -self.squash_bound + eps] = 0.0   # the box edge means exactly 0 / 1
        out[a >= self.squash_bound - eps] = 1.0
        return out

    def step(self, action: np.ndarray):
        if self.action_squash:
            action = self._unsquash(action)
        action_frac = float(np.clip(action[0], 0.0, 1.0))

        # Force complete execution on final step
        is_final_step = self.step_count == self.total_steps - 1
        if is_final_step:
            action_frac = 1.0
            qty = self.remaining
        elif self.action_mode == "adv_rate":
            avg_min_vol = self.sim.cfg.avg_daily_volume / self.total_steps
            qty = min(action_frac * self.adv_rate_max * avg_min_vol, self.remaining)
        elif self.action_mode == "clock_rate":
            base = self.total_shares / self.total_steps
            mult = 0.0 if action_frac <= 1e-3 else 10.0 ** (self.clock_rate_decades * (action_frac - 0.5))
            qty = min(mult * base, self.remaining)
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

        # Schedule guardrail (evaluation wrapper for the RL agent only; set
        # by the evaluation scripts, never during training, never for
        # benchmarks). If the order has fallen more than rl_guard_band of its
        # size behind a straight-line (TWAP) pace, trade at least enough to
        # close that excess over the next rl_guard_steps minutes. It only ever
        # ADDS to what the policy chose. This is the standard risk control a
        # desk puts around any model: it removes the failure where a too-slow
        # policy is left with a large block to dump at the close.
        band = getattr(self, "rl_guard_band", None)
        if band is not None and not is_final_step:
            target_rem = self.total_shares * (1.0 - self.step_count / self.total_steps)
            excess = self.remaining - target_rem - band * self.total_shares
            if excess > 0:
                steps = max(1, int(getattr(self, "rl_guard_steps", 10)))
                qty = max(qty, min(excess / steps, self.remaining))

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
        if self.drawdown_stop_frac is None:
            max_loss = float("inf")
            drawdown_triggered = False
        else:
            max_loss = self.arrival_price * self.total_shares * self.drawdown_stop_frac
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

        # Own permanent impact accumulated BEFORE this step's fill, in price
        # units. The step's execution price is built off a mid that already
        # contains it, so it is the part of (mid - arrival) the order caused.
        perm_before = float(self.sim.permanent_impact_acc)
        bar_volume = float(self.sim.day_data.loc[self.sim.step_idx, "volume"])
        cum_mode = self.sim.cumulative_mode
        if cum_mode:
            x_before = float(self.sim.cum_executed)
            base_mid_t = float(self.sim.base_mid)

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

        # --- Signed implementation shortfall ---
        # step_cost above clips each fill's price component at zero:
        # max(0, fill - arrival). That is NOT implementation shortfall. A fill
        # below arrival (for a buy) earns nothing, so random price drift is
        # charged when it goes against the order and never credited when it
        # goes for it. The expected charge grows with exposure time -- about
        # sigma * sqrt(t) / sqrt(2*pi) -- so the clipped metric builds a large
        # penalty for trading late into every strategy's cost, independent of
        # execution quality. A zero-impact toy with 4bps/min volatility
        # charges TWAP ~21bps and a schedule that finishes in 100 minutes
        # ~10bps, from drift alone.
        #
        # The signed version is the standard definition, and decomposes
        # exactly into three parts:
        #   drift      mid at fill time vs arrival, excluding own impact
        #   permanent  the order's own accumulated permanent impact
        #   execution  fill vs mid at fill time + adverse selection
        # plus fees.
        if fill.filled_qty > 0 and cum_mode:
            # Exact attribution under cumulative permanent impact:
            #   drift      = where the price path WITHOUT own impact was
            #   permanent  = integral of G over this step's slice of the order
            #   execution  = everything else in the fill price
            sgn = 1.0 if self.side == "buy" else -1.0
            q = fill.filled_qty
            price_total = q * sgn * (fill.avg_price - self.arrival_price)
            drift = q * sgn * (base_mid_t - self.arrival_price)
            perm = (self.sim.cum_H(self.sim.cum_executed) - self.sim.cum_H(x_before)) * self.sim.p0
            self.cost_drift += drift
            self.cost_permanent += perm
            self.cost_execution += price_total - drift - perm + adv_sel_cost
        elif fill.filled_qty > 0:
            sgn = 1.0 if self.side == "buy" else -1.0
            q = fill.filled_qty
            mid_t = fill.arrival_price
            drift_px = sgn * (mid_t - self.arrival_price) - perm_before
            self.cost_drift += q * drift_px
            self.cost_permanent += q * perm_before
            self.cost_execution += q * sgn * (fill.avg_price - mid_t) + adv_sel_cost
        self.cost_fees += fee_cost
        self.total_cost_signed = (self.cost_drift + self.cost_permanent
                                  + self.cost_execution + self.cost_fees)

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

        if self.reward_mode == "mean_variance":
            scale = self.arrival_price * self.total_shares / 1e4 + 1e-12
            cost_now = self.cost_execution + self.cost_permanent + self.cost_fees
            d_cost_bps = (cost_now - self._mv_prev_cost) / scale
            self._mv_prev_cost = cost_now
            lam = self.mv_lambda_min * (self.mv_lambda_max / self.mv_lambda_min) ** self.urgency
            sigma_bps = self.vol_per_step * 1e4
            risk_bps = lam * (inv_frac ** 2) * sigma_bps ** 2
            smooth_pen = 0.0
            if self.action_change_penalty > 0:
                pace = self.total_shares / self.total_steps
                if self._prev_fill_qty is not None:
                    smooth_pen = self.action_change_penalty * (
                        (fill.filled_qty - self._prev_fill_qty) / (pace + 1e-9)) ** 2
                self._prev_fill_qty = fill.filled_qty
            reward = float(-(d_cost_bps + risk_bps + smooth_pen) * self.reward_scale)

        obs = self._get_obs()
        info = {
            "side": self.side,
            "urgency": self.urgency,
            "remaining": self.remaining,
            "step_cost": step_cost,
            "total_cost": self.total_cost,
            "is_bps": self.total_cost / (self.arrival_price * self.total_shares + 1e-9) * 10_000,
            "is_bps_signed": self.total_cost_signed / (self.arrival_price * self.total_shares + 1e-9) * 10_000,
            "filled_qty": fill.filled_qty,
            "bar_volume": bar_volume,
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

        # CAUSALITY: bar-aggregate features must come from a COMPLETED bar.
        #
        # state["volume_ratio"] and state["spread_bps"] are derived from
        # day_data at the current step -- but a bar's total volume and median
        # spread are only known once that minute has closed. Feeding them to
        # the policy before it acts is lookahead, and it is the single most
        # valuable thing a participation-rate policy could cheat with: the
        # action IS a fraction of the minute's volume, so knowing that volume
        # in advance is close to the ideal leak.
        #
        # Execution deliberately still uses the CURRENT bar's volume. That is
        # legitimate: a POV algorithm genuinely participates in volume as it
        # arrives through the minute. Only the DECISION has to be causal.
        #
        # observation_lag = 0 reproduces the earlier (non-causal) behaviour.
        lag = self.observation_lag
        if lag > 0:
            obs_idx = max(0, self.sim.step_idx - lag)
            row = self.sim.day_data.loc[obs_idx]
            avg_vol = self.market_cfg.avg_daily_volume / self.market_cfg.steps_per_day
            lagged_volume_ratio = float(row["volume"]) / (avg_vol + 1e-9)
            lagged_spread_bps = float(row.get("spread_bps", self.market_cfg.avg_spread_bps))
        else:
            lagged_volume_ratio = state["volume_ratio"]
            lagged_spread_bps = state["spread_bps"]
        side_ind   = 1.0 if self.side == "buy" else -1.0
        regime_ind = 1.0 if state["regime"] == "volatile" else 0.0
        if self.hide_state_obs:
            regime_ind = 0.0
        hawkes_norm = np.clip(
            state["hawkes_intensity"] / (self.market_cfg.hawkes_baseline + 1e-9), 0, 3
        )
        news_ind = 1.0 if state["is_news_window"] else 0.0
        if self.hide_state_obs:
            news_ind = 0.0
        if self.honest_obs:
            hist = getattr(self, "_mid_hist", None)
            if hist is None:
                hist = self._mid_hist = []
            hist.append(float(state["mid_price"]))
            w = self.honest_vol_window
            if len(hist) >= 3:
                p = np.array(hist[-(w + 1):])
                rv = float(np.std(np.diff(np.log(p))))
            else:
                rv = self.market_cfg.volatility_per_min
            regime_ind = float(np.clip(rv / (self.market_cfg.volatility_per_min + 1e-12) / 3.0, 0, 1))
            lob = self.sim.lob
            if lob is not None:
                q_spread = (lob.best_ask - lob.best_bid) / (lob.mid_price + 1e-12) * 1e4
            else:
                q_spread = self.market_cfg.avg_spread_bps
            news_ind = float(np.clip(q_spread / (self.market_cfg.avg_spread_bps + 1e-9) / 5.0, 0, 1))

        return np.array([
            self.remaining / self.total_shares,
            (self.total_steps - self.step_count) / self.total_steps,
            (state["mid_price"] - self.arrival_price) / (self.arrival_price + 1e-9),
            lagged_spread_bps / 10.0,
            np.clip(lagged_volume_ratio, 0, 10),
            0.0 if self.drop_noise_obs else np.clip(state["book_imbalance"], -1, 1),
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
        vals = [value, 0.0] if self.enable_passive else [value]
        if self.action_squash:
            vals = [self._logit(v) for v in vals]
        return np.array(vals, dtype=np.float32)

    def _logit(self, v: float) -> float:
        """Inverse of _unsquash, for benchmarks: exact 0 and 1 map to the
        box edges, which _unsquash maps back to exactly 0 and 1."""
        v = float(v)
        if v <= 0.0:
            return -self.squash_bound
        if v >= 1.0:
            return self.squash_bound
        b = self.squash_bound - 1e-5
        return float(np.clip(np.log(v / (1.0 - v)), -b, b))

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
        if self.action_mode == "fraction_of_remaining":
            return self._pad_action(frac_of_remaining)

        if self.action_mode == "adv_rate":
            intended_qty = frac_of_remaining * self.remaining
            avg_min_vol = self.sim.cfg.avg_daily_volume / self.total_steps
            a = intended_qty / (self.adv_rate_max * avg_min_vol + 1e-9)
            return self._pad_action(float(np.clip(a, 0.0, 1.0)))

        if self.action_mode == "clock_rate":
            # Inverse of the log mapping in step(). Quantities below 1% of the
            # TWAP pace map to "trade nothing"; above 100x it clips (the
            # simulator's participation cap binds long before that).
            intended_qty = frac_of_remaining * self.remaining
            base = self.total_shares / self.total_steps
            if intended_qty <= 0:
                return self._pad_action(0.0)
            mult = intended_qty / base
            a = 0.5 + np.log10(max(mult, 1e-12)) / self.clock_rate_decades
            if a <= 1e-3:
                return self._pad_action(0.0)
            return self._pad_action(float(np.clip(a, 0.0, 1.0)))

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

    def quoted_spread_bps(self) -> float:
        """Current quoted spread from the book -- public before trading."""
        lob = self.sim.lob
        if lob is None:
            return float(self.market_cfg.avg_spread_bps)
        return float((lob.best_ask - lob.best_bid) / (lob.mid_price + 1e-12) * 1e4)

    def ac_volume_clock_action(self, risk_aversion: float, volume_profile: np.ndarray,
                               live: bool = False, spread_k: float = 0.0) -> np.ndarray:
        """Almgren-Chriss run on a VOLUME clock instead of a time clock.

        When temporary impact is priced against each minute's actual volume
        (market.impact_volume_ref = bar), the classical optimum is the AC
        schedule in volume time: trade more in minutes that carry more volume.
        One unit of volume time = one average minute (ADV / total_steps).

          remaining volume time  N = total_steps * expected share of the day's
                                     volume still to come (from volume_profile)
          this minute's length   d = expected share of this minute    (live=False)
                                   = actual volume / average minute   (live=True)
          trade fraction of remaining = 1 - sinh(k (N - d)) / sinh(k N)

        live=False is a fixed schedule (with risk aversion -> 0 it is VWAP).
        live=True scales each minute by the volume actually trading in it --
        the same information POV benchmarks use -- and rescales the remaining
        volume by the day's realised-vs-expected volume so far, so it is the
        adaptive classical strategy and the fairest benchmark for an RL agent
        that sees volume. k is computed exactly as in ac_action.
        """
        t = self.step_count
        steps_left = self.total_steps - t
        if steps_left <= 1 or t >= len(volume_profile):
            return self._to_action(1.0)
        prof = np.asarray(volume_profile, dtype=float)
        prof = prof / (prof.sum() + 1e-12)
        n_rem = self.total_steps * float(prof[t:].sum())
        if live:
            bar_vol = float(self.sim.day_data.loc[self.sim.step_idx, "volume"])
            avg_min = self.sim.cfg.avg_daily_volume / self.total_steps
            d = bar_vol / (avg_min + 1e-9)
            # Rescale the remaining-volume estimate by how busy the day has been
            # so far (completed minutes only). Without this, on a day trading
            # at 0.3x ADV the clock runs slow and ~24% of the order is left for
            # the forced final minute; with it the strategy re-paces itself.
            if t > 0:
                done_vol = float(self.sim.day_data["volume"].iloc[:self.sim.step_idx].sum())
                exp_vol = self.sim.cfg.avg_daily_volume * float(prof[:t].sum())
                n_rem *= float(np.clip(done_vol / (exp_vol + 1e-9), 0.2, 5.0))
        else:
            d = self.total_steps * float(prof[t])
        if n_rem <= 1e-9 or d >= n_rem:
            return self._to_action(1.0)
        sigma = self.vol_per_step
        eta = self.market_cfg.eta_temporary
        kappa = max(np.sqrt(risk_aversion * sigma ** 2 / (eta + 1e-12)), 1e-6)
        frac = 1.0 - np.sinh(kappa * (n_rem - d)) / (np.sinh(kappa * n_rem) + 1e-12)
        if spread_k > 0:
            # Spread-aware variant -- the one-line practitioner rule "trade
            # less when the spread is wide". Each minute's quantity is scaled
            # by (typical spread / current quoted spread) ** k, where typical
            # is the running mean of the quotes seen so far in this order
            # (causal). Shares not traded now stay in inventory and the AC
            # recursion above re-paces them over the remaining volume.
            q = self.quoted_spread_bps()
            hist = getattr(self, "_qs_hist", None)
            if hist is None or self.step_count == 0:
                hist = self._qs_hist = []
            hist.append(q)
            typical = float(np.mean(hist))
            frac = frac * (typical / max(q, 1e-9)) ** spread_k
        return self._to_action(float(np.clip(frac, 0.0, 1.0)))

    def ac_action(self, risk_aversion: float = None) -> np.ndarray:
        """Almgren-Chriss schedule. `risk_aversion` overrides the urgency
        preset, so the benchmark can be swept to find its best setting."""
        steps_left = self.total_steps - self.step_count
        if steps_left <= 1:
            return self._to_action(1.0)
        sigma = self.vol_per_step
        eta = self.market_cfg.eta_temporary
        if risk_aversion is None:
            risk_aversion, _, _, _ = get_urgency_params(self.urgency)
        kappa = np.sqrt(risk_aversion * sigma**2 / (eta + 1e-12))
        kappa = max(kappa, 1e-6)
        denom = np.sinh(kappa * steps_left) + 1e-9
        qty_t = self.remaining * (1 - np.sinh(kappa * (steps_left - 1)) / denom)
        frac = np.clip(qty_t / (self.remaining + 1e-9), 0, 1)
        return self._to_action(frac)