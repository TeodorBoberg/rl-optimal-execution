"""
simulator/market.py — upgraded simulator with:
  1. Empirically-calibrated impact model (multi-factor, not just sqrt)
  2. Hawkes process order flow (realistic clustering)
  3. Adverse selection penalty for passive fills
  4. Regime-switching price model (calm / volatile)
  5. Dynamic spread (vol, depth, time-of-day, news windows)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------

@dataclass
class MarketConfig:
    avg_daily_volume: int = 5_000_000
    steps_per_day: int = 78
    step_duration_min: int = 5
    avg_spread_bps: float = 5.0
    volatility_per_min: float = 0.0003
    # Impact model coefficients (calibrate from your own fill data)
    eta_temporary: float = 0.0005
    gamma_permanent: float = 0.00005
    # Exponent on participation in the permanent impact term.
    #
    # 1.0 = linear (Kyle 1985), which is what this simulator assumed and
    # what every result before this change was measured under.
    #
    # Measured from 312M classified trade observations, permanent impact is
    # strongly CONCAVE: fitted exponent 0.157 / 0.191 / 0.188 at 5 / 15 / 60
    # minute horizons, with 11/11 participation buckets significant at every
    # horizon and impact flat across horizons (confirming it is genuinely
    # permanent, not decaying temporary impact).
    #
    # The measured LEVEL is deliberately NOT imported. Those observations sit
    # at ~0.002% participation while this simulator operates at 5-25%, two to
    # three orders of magnitude higher, and extrapolating a power law across
    # that gap is the same error that produced an implausible 868x value when
    # attempted for eta_temporary. Instead gamma_permanent should be
    # re-anchored so that permanent impact at a representative participation
    # matches the previous linear model there -- this changes the SHAPE
    # (how impact scales with size) without importing an unsupported level.
    permanent_impact_exponent: float = 1.0
    impact_exponent: float = 0.6          # empirical: ~0.5-0.7 in practice
    spread_impact_exp: float = 0.3        # spread contribution to impact
    vol_impact_exp: float = 0.4           # vol contribution to impact
    # Reactive layer
    spread_widening_factor: float = 2.0
    book_depth_levels: int = 10
    book_replenish_halflife: int = 5
    max_participation_rate: float = 0.25
    # Adverse selection
    adverse_selection_factor: float = 0.3  # fraction of spread paid as adv. sel.
    # Baseline probability that a resting passive order fills within a step,
    # before size and volatility adjustments. NOT CALIBRATED: estimating it
    # needs data on resting orders that never filled, which the public tape
    # does not contain (it records executions only). This is the dominant
    # assumption in the passive execution model.
    passive_fill_prob: float = 0.4
    # Regime switching
    calm_vol: float = 0.0002
    volatile_vol: float = 0.0012
    prob_calm_to_volatile: float = 0.02
    prob_volatile_to_calm: float = 0.05
    # Hawkes process
    hawkes_baseline: float = 10.0         # background order arrival rate
    hawkes_alpha: float = 0.6             # self-excitation strength
    hawkes_decay: float = 0.3             # excitation decay rate
    # News windows (steps where spread spikes)
    news_spread_multiplier: float = 5.0
    news_probability: float = 0.02        # prob of news event per step
    # Alpha signal (noisy proxy for a real forecasting model's output)
    alpha_horizon_steps: int = 6          # look-ahead window, in steps, the signal predicts
    alpha_noise_std: float = 2.0          # higher = noisier/less informative signal (~62% directional accuracy)
    alpha_decay: float = 0.9              # how much true forward return bleeds into the signal


# ------------------------------------------------------------------
# Fill result
# ------------------------------------------------------------------

@dataclass
class FillResult:
    filled_qty: float
    avg_price: float
    arrival_price: float
    slippage_bps: float
    temporary_impact_bps: float
    permanent_impact_bps: float
    spread_cost_bps: float
    adverse_selection_bps: float
    participation_rate: float
    regime: str


# ------------------------------------------------------------------
# 1. Regime-switching price model
# ------------------------------------------------------------------

class RegimeSwitchingModel:
    """
    Two regimes: calm and volatile.
    Markov switching with calibrated transition probabilities.
    """

    def __init__(self, cfg: MarketConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self.regime = "calm"
        # Transition matrix [calm->calm, calm->vol], [vol->calm, vol->vol]
        self.transition = np.array([
            [1 - cfg.prob_calm_to_volatile, cfg.prob_calm_to_volatile],
            [cfg.prob_volatile_to_calm,     1 - cfg.prob_volatile_to_calm],
        ])

    def step_vol(self) -> tuple[float, str]:
        """Returns (volatility_this_step, current_regime)."""
        probs = self.transition[0 if self.regime == "calm" else 1]
        self.regime = self.rng.choice(["calm", "volatile"], p=probs)
        vol = self.cfg.calm_vol if self.regime == "calm" else self.cfg.volatile_vol
        return vol, self.regime

    def reset(self):
        self.regime = "calm"


# ------------------------------------------------------------------
# 2. Hawkes process order flow
# ------------------------------------------------------------------

class HawkesOrderFlow:
    """
    Self-exciting point process for order arrivals.
    Lambda(t) = baseline + sum(alpha * exp(-decay * (t - t_i)))
    where t_i are past order arrival times.

    In discrete time: intensity decays each step and gets excited by fills.
    """

    def __init__(self, cfg: MarketConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self.intensity = cfg.hawkes_baseline

    def reset(self):
        self.intensity = self.cfg.hawkes_baseline

    def step(self, orders_this_step: float) -> float:
        """
        Advance one time step.
        orders_this_step: volume traded this step (normalized by avg_vol).
        Returns current intensity (proxy for available liquidity multiplier).
        """
        # Decay existing intensity toward baseline
        self.intensity = (
            self.cfg.hawkes_baseline
            + (self.intensity - self.cfg.hawkes_baseline)
            * np.exp(-self.cfg.hawkes_decay)
        )
        # Self-excitation from this step's order flow
        self.intensity += self.cfg.hawkes_alpha * orders_this_step
        return self.intensity

    @property
    def liquidity_multiplier(self) -> float:
        """
        High intensity = more orders = more liquidity available.
        Returns a multiplier for available book depth.
        """
        return np.clip(self.intensity / self.cfg.hawkes_baseline, 0.3, 3.0)


# ------------------------------------------------------------------
# 3. Limit Order Book with adverse selection
# ------------------------------------------------------------------

class LimitOrderBook:
    """
    LOB with Hawkes-driven depth and adverse selection on passive fills.
    """

    def __init__(
        self,
        mid_price: float,
        spread_bps: float,
        step_volume: int,
        n_levels: int,
        replenish_halflife: int,
        liquidity_multiplier: float,
        rng: np.random.Generator,
    ):
        self.rng = rng
        self.n_levels = n_levels
        self.replenish_rate = 1 - 0.5 ** (1 / max(1, replenish_halflife))
        self.mid_price = mid_price

        tick = max(0.01, mid_price * 0.0001)
        half_spread = mid_price * spread_bps / 20_000
        self.best_ask = mid_price + half_spread
        self.best_bid = mid_price - half_spread
        self.levels = np.array([self.best_ask + i * tick for i in range(n_levels)])

        # Power-law depth, scaled by Hawkes liquidity multiplier
        weights = np.array([1 / (i + 1) ** 0.7 for i in range(n_levels)])
        weights /= weights.sum()
        total_depth = step_volume * 2 * liquidity_multiplier
        self.quantities = (
            weights * total_depth * self.rng.lognormal(0, 0.2, n_levels)
        ).astype(float)
        self.max_quantities = self.quantities.copy()

    def execute_aggressive(self, qty: float, force_fill: bool = False) -> tuple[float, float]:
        """Market order — walks through ask levels. Returns (avg_price, filled).

        force_fill=True is for genuinely mandatory end-of-episode
        liquidation: if the visible n_levels can't fully absorb qty, keep
        extending the SAME tick-price progression (same step size as the
        real levels) for as many additional synthetic levels as needed,
        rather than silently returning a partial fill. This guarantees a
        full fill with a well-defined, correspondingly worse price for the
        excess -- consistent with what a real desk facing a forced
        liquidation would eventually get, rather than the order just
        vanishing as invisible-to-cost "unfilled" inventory.
        """
        remaining = qty
        total_cost = 0.0
        total_filled = 0.0
        for i in range(self.n_levels):
            avail = self.quantities[i]
            if avail <= 0:
                continue
            fill = min(remaining, avail)
            total_cost += fill * self.levels[i]
            total_filled += fill
            self.quantities[i] -= fill
            remaining -= fill
            if remaining <= 0:
                break

        if remaining > 0 and force_fill:
            # Fill the excess at a small, BOUNDED continuation beyond the
            # last real level -- NOT scaling further with the size of the
            # excess. compute_impact() (called in execute() on the FULL
            # requested qty, before this method even runs) already applies
            # the real-data-validated power-law impact markup for the
            # complete order size, regardless of physical book depth. An
            # earlier version of this fix ALSO scaled this synthetic
            # extension's price linearly with excess size -- double-
            # counting "large order = large cost" through two separate
            # mechanisms simultaneously, which produced unrealistically
            # extreme tail costs on forced liquidations. The size-dependent
            # cost signal belongs in compute_impact()'s power law only;
            # this extension just needs to guarantee completion at a
            # modestly worse (not runaway) price.
            tick = self.levels[1] - self.levels[0] if self.n_levels > 1 else self.levels[0] * 0.0001
            fixed_extra_ticks = 3  # small, bounded -- not size-dependent
            excess_price = self.levels[-1] + fixed_extra_ticks * tick
            total_cost += remaining * excess_price
            total_filled += remaining
            remaining = 0.0

        avg_price = total_cost / total_filled if total_filled > 0 else self.levels[0]
        return avg_price, total_filled

    def execute_passive(self, qty: float, adverse_sel_factor: float,
                         side: str = "buy", base_fill_prob: float = 0.4,
                         vol_ratio: float = 1.0) -> tuple[float, float, float]:
        """
        Limit order resting at the near touch. Returns
        (avg_price, filled_qty, adverse_selection_cost_bps).

        A passive buy rests at the best BID and a passive sell rests at the
        best ASK, so in both cases the order earns the half-spread instead
        of paying it -- that is the entire point of trading passively. The
        previous implementation hardcoded `best_bid` for both sides, which
        made passive sells earn the spread twice over.

        Fill probability is uncertain and depends on whether enough
        opposing flow arrives while the order rests. Two effects are
        modelled rather than using a flat constant:

          - SIZE: an order large relative to displayed depth at the touch
            sits behind a longer queue and is less likely to be fully
            filled within the step.
          - VOLATILITY: when prices move more, the touch is more likely to
            be reached, so fills become more likely -- but see adverse
            selection below, which is the offsetting cost.

        Adverse selection is the reason passive execution is not free
        money: conditional on being filled, the fill happened because
        someone wanted to trade against you, and price tends to continue
        moving against the fill afterwards.

        NOTE: base_fill_prob is NOT calibrated. It is the dominant
        assumption in this model and would need real passive-order fill
        data to estimate, which the public tape does not contain (it shows
        executions, not resting orders that never filled).
        """
        if qty <= 0:
            return self.mid_price, 0.0, 0.0

        depth = self.quantities[0] if len(self.quantities) else 0.0
        size_ratio = qty / max(depth, 1e-9)
        # Queue effect: fill probability falls as the order grows relative
        # to displayed depth. 1/(1+x) is bounded in (0, 1] and decays
        # smoothly rather than cutting off.
        size_factor = 1.0 / (1.0 + max(size_ratio, 0.0))
        vol_factor = float(np.clip(vol_ratio, 0.5, 2.0))

        fill_prob = float(np.clip(base_fill_prob * size_factor * vol_factor, 0.0, 1.0))
        filled = qty * fill_prob * self.rng.uniform(0.5, 1.0)

        # Rest at the near touch: bid for a buy, ask for a sell.
        avg_price = self.best_bid if side == "buy" else self.best_ask

        spread_bps = (self.best_ask - self.best_bid) / self.mid_price * 10_000
        # Adverse selection scales with how easily the fill was obtained:
        # fills that arrive in fast markets are the more informed ones.
        adv_sel_bps = adverse_sel_factor * spread_bps * vol_factor

        return avg_price, filled, adv_sel_bps

    def replenish(self):
        deficit = self.max_quantities - self.quantities
        self.quantities += (
            deficit * self.replenish_rate * self.rng.uniform(0.5, 1.5, self.n_levels)
        )
        self.quantities = np.minimum(self.quantities, self.max_quantities)


# ------------------------------------------------------------------
# 4. Dynamic spread model
# ------------------------------------------------------------------

class DynamicSpreadModel:
    """
    Spread = base * time_multiplier * vol_multiplier * depth_multiplier * news_multiplier

    All multipliers are calibrated from historical bid/ask data ideally;
    here we use reasonable defaults with the right functional form.
    """

    def __init__(self, cfg: MarketConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self.is_news_window = False
        # Pre-compute U-shaped time-of-day profile
        t = np.linspace(0, 1, cfg.steps_per_day)
        self.time_profile = 0.5 + 2.0 * (t - 0.5) ** 2
        self.time_profile /= self.time_profile.mean()  # normalize to mean=1

    def reset(self):
        self.is_news_window = False

    def compute(
        self,
        step_idx: int,
        realised_vol: float,       # vol relative to long-run avg (ratio)
        book_depth_ratio: float,   # current depth / avg depth
    ) -> float:
        """Returns spread in bps for this step."""
        base = self.cfg.avg_spread_bps

        # Time of day
        t_mult = self.time_profile[min(step_idx, len(self.time_profile) - 1)]

        # Volatility regime
        vol_mult = max(0.5, realised_vol) ** 0.5

        # Book depth (thin book = wide spread)
        depth_mult = 1.0 / np.clip(book_depth_ratio, 0.2, 2.0) ** 0.3

        # News event (random shock)
        self.is_news_window = self.rng.random() < self.cfg.news_probability
        news_mult = self.cfg.news_spread_multiplier if self.is_news_window else 1.0

        spread = base * t_mult * vol_mult * depth_mult * news_mult
        return float(np.clip(spread, 1.0, 100.0))


# ------------------------------------------------------------------
# 5. Multi-factor impact model
# ------------------------------------------------------------------

def compute_impact(
    qty: float,
    avg_vol_per_step: float,
    spread_bps: float,
    realised_vol: float,
    cfg: MarketConfig,
) -> tuple[float, float]:
    """
    Multi-factor impact model:
        impact = eta * (qty/adv)^exponent * spread^s_exp * vol^v_exp

    Returns (temporary_impact_fraction, permanent_impact_fraction).
    """
    participation = qty / (avg_vol_per_step + 1e-9)

    # Defensive floor: participation, spread_bps, and realised_vol all get
    # raised to FRACTIONAL powers below (impact_exponent, spread_impact_exp,
    # vol_impact_exp are all non-integer). Python's ** on a negative base
    # with a non-integer exponent returns a COMPLEX number rather than
    # raising an error -- this caused a real crash mid-training when a rare
    # data artifact produced a negative spread_bps (traced to tick bar
    # aggregation; fixed at the source in tick_to_bars.py, but clipping
    # here too means this whole class of bug can never crash a run again,
    # regardless of what future data issues might surface upstream.
    participation = max(participation, 0.0)
    spread_ratio = max(spread_bps / cfg.avg_spread_bps, 1e-6)
    realised_vol = max(realised_vol, 1e-6)

    temp = (
        cfg.eta_temporary
        * (participation ** cfg.impact_exponent)
        * (spread_ratio ** cfg.spread_impact_exp)
        * (realised_vol ** cfg.vol_impact_exp)
    )
    perm = cfg.gamma_permanent * (participation ** cfg.permanent_impact_exponent)

    return float(temp), float(perm)


# ------------------------------------------------------------------
# 6. Main simulator
# ------------------------------------------------------------------

class MarketSimulator:
    """
    Full upgraded simulator combining all components.
    """

    def __init__(self, cfg: MarketConfig, rng: Optional[np.random.Generator] = None):
        self.cfg = cfg
        self.rng = rng or np.random.default_rng()
        self.regime_model = RegimeSwitchingModel(cfg, self.rng)
        self.hawkes = HawkesOrderFlow(cfg, self.rng)
        self.spread_model = DynamicSpreadModel(cfg, self.rng)

        self.day_data = None
        self.step_idx = 0
        self.mid_price = 100.0
        self.permanent_impact_acc = 0.0
        self.current_vol = cfg.volatility_per_min
        self.current_regime = "calm"
        self.lob: Optional[LimitOrderBook] = None
        self.signal_values: Optional[np.ndarray] = None
        self.signal_strengths: Optional[np.ndarray] = None
        self._forward_returns: Optional[np.ndarray] = None  # ground truth, reward-only — never expose via current_state

    def reset(self, day_data) -> float:
        self.day_data = day_data.reset_index(drop=True)
        self.step_idx = 0
        self.permanent_impact_acc = 0.0
        self.mid_price = float(self.day_data.loc[0, "close"])
        self.regime_model.reset()
        self.hawkes.reset()
        self.spread_model.reset()
        self.current_vol = self.cfg.volatility_per_min
        self._compute_alpha_signals()
        self._rebuild_lob()
        return self.mid_price

    def _compute_alpha_signals(self):
        """
        Precompute a noisy alpha signal for every step in the episode.

        This is a stand-in for a real forecasting model's output. It's built
        from *actual* forward returns within this day's data (which is fine —
        it's only ever used at reset/train time, never leaked into the
        observation beyond the noisy signal_value/signal_strength pair).
        Calibrated so the signal is directionally correct only ~55-65% of the
        time, similar to a real weak alpha source — if it's too clean the
        agent will learn to blindly trust it and won't generalize.
        """
        closes = self.day_data["close"].values.astype(float)
        n = len(closes)
        horizon = self.cfg.alpha_horizon_steps

        forward_returns = np.zeros(n)
        for i in range(n):
            j = min(i + horizon, n - 1)
            forward_returns[i] = (closes[j] / closes[i] - 1) if closes[i] > 0 else 0.0

        ret_std = np.std(forward_returns) + 1e-8
        noise = self.rng.normal(0, self.cfg.alpha_noise_std, size=n) * ret_std
        raw_signal = forward_returns * self.cfg.alpha_decay + noise

        # Normalize by the *combined* signal's own std (not just ret_std), then
        # soft-saturate with tanh instead of hard-clipping — hard clipping at
        # +-1 wastes most of the signal's dynamic range at the boundary and
        # destroys the graded confidence information signal_strength needs.
        signal_std = np.std(raw_signal) + 1e-8
        self.signal_values = np.tanh(raw_signal / signal_std)
        self.signal_strengths = (
            np.abs(self.signal_values) * self.rng.uniform(0.5, 1.0, size=n)
        )
        self._forward_returns = forward_returns  # ground truth, for reward computation only

    def get_forward_return(self, step_idx: Optional[int] = None) -> float:
        """
        Ground-truth forward return over alpha_horizon_steps, for use in
        reward = alpha_captured - execution_cost. Do NOT put this in obs —
        only signal_value/signal_strength (the noisy proxy) belong there.
        """
        if self._forward_returns is None:
            return 0.0
        idx = self.step_idx if step_idx is None else step_idx
        idx = min(idx, len(self._forward_returns) - 1)
        return float(self._forward_returns[idx])

    def _rebuild_lob(self):
        row = self.day_data.loc[self.step_idx]
        step_vol = int(row["volume"])
        avg_vol = self.cfg.avg_daily_volume / self.cfg.steps_per_day

        # Vol ratio for spread model
        realised_vol_ratio = self.current_vol / (self.cfg.volatility_per_min + 1e-12)

        # Book depth ratio from Hawkes
        depth_ratio = self.hawkes.liquidity_multiplier

        spread = self.spread_model.compute(
            self.step_idx,
            realised_vol_ratio,
            depth_ratio,
        )

        self.lob = LimitOrderBook(
            mid_price=self.mid_price,
            spread_bps=spread,
            step_volume=step_vol,
            n_levels=self.cfg.book_depth_levels,
            replenish_halflife=self.cfg.book_replenish_halflife,
            liquidity_multiplier=self.hawkes.liquidity_multiplier,
            rng=self.rng,
        )

    def execute_passive_order(self, qty: float, side: str = "buy") -> FillResult:
        """
        Execute a passive (resting limit) order for this step and return a
        FillResult, matching execute()'s interface so callers can combine
        passive and aggressive fills uniformly.

        Unlike execute(), a passive order is NOT capped by participation:
        it rests in the book rather than consuming displayed liquidity, so
        it does not take a share of the step's traded volume in the same
        way. Its constraint is the fill probability instead.

        Passive fills earn the half-spread rather than paying it, so
        slippage_bps is NEGATIVE (a gain) before adverse selection is
        applied. Whether passive execution is actually cheaper depends on
        whether that gain exceeds the adverse selection cost -- which is
        precisely the trade-off the policy has to learn.
        """
        if qty <= 0:
            return FillResult(0, self.mid_price, self.mid_price, 0, 0, 0, 0, 0, 0,
                               self.current_regime)

        arrival_price = self.mid_price
        realised_vol = self.current_vol / max(self.cfg.volatility_per_min, 1e-12)

        avg_price, filled, adv_sel_bps = self.lob.execute_passive(
            qty,
            self.cfg.adverse_selection_factor,
            side=side,
            base_fill_prob=getattr(self.cfg, "passive_fill_prob", 0.4),
            vol_ratio=realised_vol,
        )
        if filled <= 0:
            return FillResult(0, arrival_price, arrival_price, 0, 0, 0, 0, 0, 0,
                               self.current_regime)

        # Signed slippage relative to arrival: negative means we did better
        # than the midpoint, which is the normal case for a passive fill.
        if side == "buy":
            slippage_bps = (avg_price - arrival_price) / arrival_price * 10_000
        else:
            slippage_bps = (arrival_price - avg_price) / arrival_price * 10_000

        row = self.day_data.loc[self.step_idx]
        step_volume = max(1, int(row["volume"]))

        return FillResult(
            filled_qty=filled,
            avg_price=avg_price,
            arrival_price=arrival_price,
            slippage_bps=slippage_bps,
            temporary_impact_bps=0.0,      # resting orders do not cross the spread
            permanent_impact_bps=0.0,
            spread_cost_bps=slippage_bps,
            adverse_selection_bps=adv_sel_bps,
            participation_rate=filled / step_volume,
            regime=self.current_regime,
        )

    def execute(self, qty: float, side: str = "buy", force_fill: bool = False,
                participation_cap_override: float = None) -> FillResult:
        if qty <= 0:
            return FillResult(0, self.mid_price, self.mid_price, 0, 0, 0, 0, 0, 0, self.current_regime)

        row = self.day_data.loc[self.step_idx]
        step_volume = max(1, int(row["volume"]))
        arrival_price = self.mid_price
        avg_vol = self.cfg.avg_daily_volume / self.cfg.steps_per_day

        # Cap participation -- UNLESS force_fill is set, for genuinely
        # mandatory end-of-episode liquidation. Without this bypass, a
        # forced final-step liquidation could still get silently capped
        # below the requested quantity by this participation limit (using
        # THIS bar's real, possibly-thin volume) -- leaving genuine
        # unfilled inventory, invisible to the cost metric. This is the
        # same failure mode as the original position-cap bug, resurfacing
        # through this cap at finer (1-minute) bar granularity where a
        # single bar's volume is much smaller than at 5-minute bars.
        #
        # participation_cap_override, when provided, replaces the normal
        # cfg.max_participation_rate -- used by env.py to proactively
        # raise the allowed participation rate as accumulated backlog
        # grows, rather than only being able to catch up via the extreme
        # force_fill mechanism at the very last step.
        if not force_fill:
            effective_cap = (participation_cap_override
                              if participation_cap_override is not None
                              else self.cfg.max_participation_rate)
            max_qty = step_volume * effective_cap
            qty = min(qty, max_qty)
        participation_rate = qty / step_volume

        # Current spread
        current_spread_bps = float(row.get("spread_bps", self.cfg.avg_spread_bps))
        realised_vol = self.current_vol / (self.cfg.volatility_per_min + 1e-12)

        # Multi-factor impact
        temp_impact, perm_impact = compute_impact(
            qty, avg_vol, current_spread_bps, realised_vol, self.cfg
        )

        # LOB execution (aggressive market order)
        if side == "buy":
            lob_price, filled_qty = self.lob.execute_aggressive(qty, force_fill=force_fill)
            exec_price = lob_price * (1 + temp_impact)
            self.mid_price += perm_impact * arrival_price
        else:
            lob_price, filled_qty = self.lob.execute_aggressive(qty, force_fill=force_fill)
            exec_price = (2 * arrival_price - lob_price) * (1 - temp_impact)
            self.mid_price -= perm_impact * arrival_price

        self.permanent_impact_acc += abs(perm_impact * arrival_price)

        # Adverse selection cost (always present, even on aggressive fills
        # because informed flow trades against you)
        adv_sel_bps = (
            self.cfg.adverse_selection_factor
            * current_spread_bps
            * participation_rate  # higher participation = more adverse selection
        )

        # Cost decomposition
        spread_cost_bps = current_spread_bps / 2
        temp_impact_bps = temp_impact * 10_000
        perm_impact_bps = perm_impact * 10_000
        slippage_bps = (exec_price - arrival_price) / arrival_price * 10_000
        if side == "sell":
            slippage_bps = -slippage_bps

        # Update Hawkes with this step's order flow
        self.hawkes.step(qty / avg_vol)

        return FillResult(
            filled_qty=filled_qty,
            avg_price=exec_price,
            arrival_price=arrival_price,
            slippage_bps=slippage_bps,
            temporary_impact_bps=temp_impact_bps,
            permanent_impact_bps=perm_impact_bps,
            spread_cost_bps=spread_cost_bps,
            adverse_selection_bps=adv_sel_bps,
            participation_rate=participation_rate,
            regime=self.current_regime,
        )

    def step(self):
        """Advance one time step."""
        if self.lob:
            self.lob.replenish()

        self.step_idx = min(self.step_idx + 1, len(self.day_data) - 1)
        row = self.day_data.loc[self.step_idx]

        # Update regime and volatility
        self.current_vol, self.current_regime = self.regime_model.step_vol()

        # Price evolution: market move + permanent impact already baked in
        prev_close = float(self.day_data.loc[max(0, self.step_idx - 1), "close"])
        curr_close = float(row["close"])
        market_ret = (curr_close / prev_close - 1) if prev_close > 0 else 0
        noise = self.rng.normal(0, self.current_vol * np.sqrt(self.cfg.step_duration_min))
        self.mid_price = self.mid_price * np.exp(market_ret + noise * 0.1)

        self._rebuild_lob()

    @property
    def current_state(self) -> dict:
        row = self.day_data.loc[self.step_idx]
        step_volume = int(row["volume"])
        avg_vol = self.cfg.avg_daily_volume / self.cfg.steps_per_day
        spread_bps = float(row.get("spread_bps", self.cfg.avg_spread_bps))

        if self.lob is not None:
            ask_depth = self.lob.quantities[:3].sum()
            bid_depth = ask_depth * self.rng.uniform(0.7, 1.3)
            imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth + 1e-9)
        else:
            imbalance = 0.0

        return {
            "mid_price": self.mid_price,
            "spread_bps": spread_bps,
            "step_volume": step_volume,
            "volume_ratio": step_volume / avg_vol,
            "book_imbalance": imbalance,
            "permanent_impact_bps": self.permanent_impact_acc / (self.mid_price + 1e-9) * 10_000,
            "regime": self.current_regime,
            "hawkes_intensity": self.hawkes.intensity,
            "is_news_window": self.spread_model.is_news_window,
            "signal_value": float(self.signal_values[self.step_idx])
            if self.signal_values is not None else 0.0,
            "signal_strength": float(self.signal_strengths[self.step_idx])
            if self.signal_strengths is not None else 0.0,
        }