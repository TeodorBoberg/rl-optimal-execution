"""
agent/train_fast.py

Fast training using SB3 PPO + vectorized environment wrapper.
Keeps the reliable SB3 training loop but feeds it data from
the fast VecMarketSimulator via a Gymnasium wrapper.
"""

import argparse
import sys
import yaml
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv
import gymnasium as gym
from gymnasium import spaces

from simulator.vec_market import VecMarketSimulator, VecMarketConfig
from simulator.synthetic_data import generate_intraday_data, SyntheticMarketConfig, load_csv_data
from simulator.data_split import train_test_split_days


# ------------------------------------------------------------------
# Thin Gymnasium wrapper around VecMarketSimulator (single env)
# ------------------------------------------------------------------

from stable_baselines3.common.vec_env import VecEnv
from stable_baselines3.common.vec_env.base_vec_env import VecEnvObs, VecEnvStepReturn

class BulkVecEnv(VecEnv):
    """
    Wraps VecMarketSimulator as an SB3-compatible VecEnv.
    All N environments step simultaneously in one NumPy call.
    No Python loop over environments at all.
    """

    def __init__(self, cfg: dict, n_envs: int = 64, data: "pd.DataFrame | None" = None):
        self.cfg = cfg
        self.total_shares = cfg["execution"]["total_shares"]
        m = cfg["market"]
        e = cfg["execution"]

        sim_cfg = VecMarketConfig(
            n_envs=n_envs,
            avg_daily_volume=m["avg_daily_volume"],
            steps_per_day=e["total_steps"],
            step_duration_min=e["step_duration_min"],
            avg_spread_bps=m["avg_spread_bps"],
            volatility_per_min=m["volatility_per_min"],
            eta_temporary=m["eta_temporary"],
            gamma_permanent=m["gamma_permanent"],
            impact_exponent=m.get("impact_exponent", 0.6),
            spread_widening_factor=m.get("spread_widening_factor", 1.5),
            max_participation_rate=e["max_participation_rate"],
            adverse_selection_factor=m.get("adverse_selection_factor", 0.3),
            calm_vol=m.get("calm_vol", 0.0002),
            volatile_vol=m.get("volatile_vol", 0.0012),
            prob_calm_to_volatile=m.get("prob_calm_to_volatile", 0.005),
            prob_volatile_to_calm=m.get("prob_volatile_to_calm", 0.10),
            hawkes_baseline=m.get("hawkes_baseline", 10.0),
            hawkes_alpha=m.get("hawkes_alpha", 0.6),
            hawkes_decay=m.get("hawkes_decay", 0.3),
            news_spread_multiplier=m.get("news_spread_multiplier", 2.0),
            news_probability=m.get("news_probability", 0.005),
            alpha_horizon_steps=m.get("alpha_horizon_steps", 6),
            alpha_noise_std=m.get("alpha_noise_std", 2.0),
            alpha_decay=m.get("alpha_decay", 0.9),
            alpha_reward_weight=m.get("alpha_reward_weight", 0.3),
        )

        price_data, volume_data, day_adv = self._load_data(cfg, data=data)
        self.sim = VecMarketSimulator(sim_cfg, price_data, volume_data, day_adv=day_adv)

        observation_space = spaces.Box(
            low=np.array( [0, 0, -0.5, 0,  0, -1, -1, 0, 0, 0, 0, -1, 0], dtype=np.float32),
            high=np.array([1, 1,  0.5, 5, 10,  1,  1, 1, 3, 1, 1,  1, 1], dtype=np.float32),
        )
        action_space = spaces.Box(
            low=np.array([0.0], dtype=np.float32),
            high=np.array([1.0], dtype=np.float32),
        )
        super().__init__(n_envs, observation_space, action_space)
        self.reset()

    def _load_data(self, cfg, data=None):
        steps = cfg["execution"]["total_steps"]
        if data is not None:
            # Pre-split (train or test) DataFrame supplied by the caller —
            # do NOT re-read from cfg["data"]["path"], that would silently
            # pull in the full unsplit dataset and undo the split.
            df = data
        else:
            data_cfg = cfg["data"]
            if data_cfg["source"] == "csv":
                df = load_csv_data(data_cfg["path"], cfg["execution"]["step_duration_min"])
            else:
                df = generate_intraday_data(SyntheticMarketConfig(
                    n_days=500, steps_per_day=steps,
                    avg_daily_volume=cfg["market"]["avg_daily_volume"],
                    volatility_per_min=cfg["market"]["volatility_per_min"],
                ))
        return self._build_grids(df, steps)

    def _build_grids(self, df, steps):
        n_days = df["day"].nunique()
        price  = np.zeros((n_days, steps))
        volume = np.zeros((n_days, steps))
        # Per-day real average daily volume (see synthetic_data.py's
        # load_csv_data), used to correctly scale Hawkes intensity per
        # ticker instead of one shared config constant for every name.
        day_adv = np.full(n_days, self.cfg["market"].get("avg_daily_volume", 5_000_000), dtype=float)
        has_adv = "ticker_adv" in df.columns
        for day in range(n_days):
            d = df[df["day"] == day].reset_index(drop=True)
            n = min(len(d), steps)
            price[day, :n]  = d["close"].values[:n]
            volume[day, :n] = d["volume"].values[:n]
            if n < steps:
                price[day, n:]  = price[day, n-1]
                volume[day, n:] = volume[day, n-1]
            if has_adv and len(d) > 0:
                day_adv[day] = float(d["ticker_adv"].iloc[0])
        print(f"Loaded {n_days} days of data")
        return price, volume, day_adv

    def reset(self):
        obs = self.sim.reset_all(self.total_shares)
        return obs

    def step_async(self, actions):
        self._actions = actions

    def step_wait(self):
        obs, rewards, dones, info = self.sim.step(
            self._actions.flatten(), self.total_shares
        )
        # Auto-reset done environments
        done_mask = dones.astype(bool)
        if done_mask.any():
            self.sim.reset_envs(done_mask, self.total_shares)
            obs = self.sim._get_obs()

        infos = [{"done": dones[i]} for i in range(self.num_envs)]
        return obs, rewards, dones, infos

    def close(self): pass
    def get_attr(self, attr, indices=None): return [None] * self.num_envs
    def set_attr(self, attr, val, indices=None): pass
    def env_method(self, method, *args, indices=None, **kwargs): return [None] * self.num_envs
    def env_is_wrapped(self, wrapper, indices=None): return [False] * self.num_envs
    def get_images(self): return []


# ------------------------------------------------------------------
# Training
# ------------------------------------------------------------------

def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def load_and_split_data(cfg: dict):
    """Load the full dataset once and split chronologically per-ticker."""
    data_cfg = cfg["data"]
    steps = cfg["execution"]["total_steps"]
    if data_cfg["source"] == "csv":
        full_df = load_csv_data(data_cfg["path"], cfg["execution"]["step_duration_min"])
    else:
        full_df = generate_intraday_data(SyntheticMarketConfig(
            n_days=500, steps_per_day=steps,
            avg_daily_volume=cfg["market"]["avg_daily_volume"],
            volatility_per_min=cfg["market"]["volatility_per_min"],
        ))
    test_frac = data_cfg.get("test_frac", 0.2)
    train_df, test_df = train_test_split_days(full_df, test_frac=test_frac)
    return train_df, test_df


class ActorCritic(nn.Module):
    """Kept for backtest compatibility — SB3 uses its own internal network."""
    def __init__(self, obs_dim=13, hidden=512):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.LayerNorm(hidden), nn.Tanh(),
            nn.Linear(hidden, hidden),  nn.LayerNorm(hidden), nn.Tanh(),
            nn.Linear(hidden, 256),     nn.Tanh(),
        )
        self.actor_mean    = nn.Sequential(nn.Linear(256, 1), nn.Sigmoid())
        self.actor_log_std = nn.Parameter(torch.zeros(1))
        self.critic        = nn.Linear(256, 1)

    def forward(self, obs):
        feat = self.shared(obs)
        return self.actor_mean(feat), self.critic(feat)

    def get_action(self, obs, deterministic=False):
        mean, value = self.forward(obs)
        std  = self.actor_log_std.exp().expand_as(mean)
        dist = torch.distributions.Normal(mean, std)
        action = mean if deterministic else dist.sample()
        action = action.clamp(0.0, 1.0)
        return action, dist.log_prob(action).squeeze(-1), value, dist.entropy().mean()


def train(cfg: dict, total_timesteps: int = None, save_path: str = "models/fast_model"):
    train_cfg = cfg["training"]
    n_timesteps = total_timesteps or train_cfg["total_timesteps"]
    seed = train_cfg.get("seed", 42)

    Path(save_path).parent.mkdir(parents=True, exist_ok=True)

    print(f"Training PPO (SB3) with fast vec simulator")
    print(f"  Timesteps: {n_timesteps:,}")

    n_envs = train_cfg.get("n_envs_fast", 64)
    print(f"  Parallel envs: {n_envs} (fully vectorized)")

    train_df, test_df = load_and_split_data(cfg)

    env      = BulkVecEnv(cfg, n_envs=n_envs, data=train_df)
    eval_env = BulkVecEnv(cfg, n_envs=4, data=test_df)

    model = PPO(
        policy="MlpPolicy",
        env=env,
        learning_rate=train_cfg.get("learning_rate", 1e-4),
        n_steps=train_cfg.get("n_steps", 512),
        batch_size=train_cfg.get("batch_size", 512),
        n_epochs=train_cfg.get("n_epochs", 10),
        gamma=train_cfg.get("gamma", 0.99),
        ent_coef=train_cfg.get("ent_coef", 0.01),
        clip_range=train_cfg.get("clip_range", 0.2),
        verbose=1,
        seed=seed,
        policy_kwargs=dict(net_arch=dict(pi=[512, 512, 256], vf=[512, 512, 256])),
    )

    callbacks = [
        EvalCallback(
            eval_env,
            best_model_save_path=str(Path(save_path).parent),
            log_path="logs/",
            eval_freq=train_cfg.get("eval_freq", 5000),
            n_eval_episodes=train_cfg.get("n_eval_episodes", 20),
            deterministic=True,
            verbose=1,
        ),
        CheckpointCallback(
            save_freq=50_000,
            save_path="models/checkpoints/",
            name_prefix="ppo_fast",
        ),
    ]

    model.learn(total_timesteps=n_timesteps, callback=callbacks, progress_bar=True)

    # Save in both SB3 format and as .pt for backtest_fast.py
    model.save(save_path)
    torch.save({"model_state": None, "cfg": cfg, "sb3": True}, save_path + "_best.pt")
    print(f"\nDone. Model saved to {save_path}.zip")
    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",    default="configs/default.yaml")
    parser.add_argument("--timesteps", type=int, default=None)
    parser.add_argument("--save-path", default="models/fast_model")
    args = parser.parse_args()
    cfg = load_config(args.config)
    train(cfg, total_timesteps=args.timesteps, save_path=args.save_path)