"""
agent/train.py — PPO trainer with buy/sell support and real data
"""

import argparse
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv

from agent.env import ExecutionEnv
from simulator.data_split import train_test_split_days
from simulator.synthetic_data import load_csv_data, generate_intraday_data, SyntheticMarketConfig


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_and_split_data(cfg: dict):
    """Load the full dataset once and split chronologically per-ticker."""
    data_cfg = cfg["data"]
    exec_cfg = cfg["execution"]
    market_cfg = cfg["market"]
    if data_cfg["source"] == "csv":
        full_df = load_csv_data(data_cfg["path"], exec_cfg["step_duration_min"])
    else:
        syn_cfg = SyntheticMarketConfig(
            avg_daily_volume=market_cfg["avg_daily_volume"],
            steps_per_day=exec_cfg["total_steps"],
            volatility_per_min=market_cfg["volatility_per_min"],
            avg_spread_bps=market_cfg["avg_spread_bps"],
            step_duration_min=exec_cfg["step_duration_min"],
        )
        full_df = generate_intraday_data(syn_cfg)

    test_frac = data_cfg.get("test_frac", 0.2)
    train_df, test_df = train_test_split_days(full_df, test_frac=test_frac)
    return train_df, test_df


def make_env_fn(cfg: dict, data, seed: int = 0, side: str = "random"):
    def _init():
        env = ExecutionEnv(cfg, data=data, side=side)
        env = Monitor(env)
        env.reset(seed=seed)
        return env
    return _init


def train(cfg: dict, total_timesteps: int = None):
    train_cfg = cfg["training"]
    n_timesteps = total_timesteps or train_cfg["total_timesteps"]
    n_envs = train_cfg["n_envs"]
    seed = train_cfg["seed"]

    log_dir = Path(train_cfg["log_dir"])
    model_dir = Path(train_cfg["model_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    print(f"Training PPO agent (buy + sell, {n_envs} parallel envs)")
    print(f"  Timesteps : {n_timesteps:,}")
    print()

    train_df, test_df = load_and_split_data(cfg)

        # Pick the best checkpoint on the end of the TRAINING window, never on test.
    val_frac = cfg["data"].get("val_frac")
    if val_frac:
        train_df, val_df = train_test_split_days(train_df, test_frac=val_frac)
    else:
        val_df = test_df

    env = make_vec_env(
        make_env_fn(cfg, train_df, seed=seed, side="random"),
        n_envs=n_envs,
        seed=seed,
        vec_env_cls=SubprocVecEnv,
    )
    eval_env = make_vec_env(
        make_env_fn(cfg, test_df, seed=seed + 9999, side="random"),
        n_envs=1,
        seed=seed + 9999,
    )

    model = PPO(
        policy="MlpPolicy",
        env=env,
        learning_rate=train_cfg.get("learning_rate", 3e-4),
        n_steps=train_cfg.get("n_steps", 2048),
        batch_size=train_cfg.get("batch_size", 256),
        n_epochs=train_cfg.get("n_epochs", 10),
        gamma=train_cfg.get("gamma", 0.99),
        ent_coef=train_cfg.get("ent_coef", 0.01),
        clip_range=train_cfg.get("clip_range", 0.2),
        verbose=1,
        tensorboard_log=str(log_dir),
        seed=seed,
        policy_kwargs=dict(net_arch=dict(pi=[256, 256], vf=[256, 256])),
        device="cpu",
    )

    callbacks = [
        EvalCallback(
            eval_env,
            best_model_save_path=str(model_dir),
            log_path=str(log_dir),
            eval_freq=max(train_cfg.get("eval_freq", 10_000) // n_envs, 1),
            n_eval_episodes=train_cfg.get("n_eval_episodes", 20),
            deterministic=True,
            verbose=1,
        ),
        CheckpointCallback(
            save_freq=max(50_000 // n_envs, 1),
            save_path=str(model_dir / "checkpoints"),
            name_prefix="ppo_exec",
        ),
    ]

    model.learn(
        total_timesteps=n_timesteps,
        callback=callbacks,
        progress_bar=True,
    )

    final_path = str(model_dir / "final_model")
    model.save(final_path)
    print(f"\nDone. Model saved to {final_path}.zip")
    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--total-timesteps", type=int, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    train(cfg, total_timesteps=args.total_timesteps)