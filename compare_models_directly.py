import numpy as np
from stable_baselines3 import PPO

model_old = PPO.load("models/best_model_1MIN_BACKLOG_FIXED_5M_SIGNFLIP.zip")
model_new = PPO.load("models/best_model_1MIN_25M_BACKUP.zip")

print("=== Basic model info ===")
print(f"Old model policy net architecture: {model_old.policy}")
print()
print(f"New model policy net architecture: {model_new.policy}")
print()

# Compare actual weight values directly -- if these are identical, the
# models are functionally the same regardless of what the file hash says
old_params = list(model_old.policy.parameters())
new_params = list(model_new.policy.parameters())
print(f"Number of parameter tensors: old={len(old_params)}, new={len(new_params)}")

total_diff = 0.0
total_elements = 0
for i, (p_old, p_new) in enumerate(zip(old_params, new_params)):
    diff = (p_old - p_new).abs().sum().item()
    total_diff += diff
    total_elements += p_old.numel()

print(f"\nTotal absolute difference across ALL weights: {total_diff:.6f}")
print(f"Average absolute difference per weight: {total_diff/total_elements:.8f}")
print("(If this is exactly 0.0, the weights are IDENTICAL despite the different file hash "
      "-- would point to a training/saving bug. If it's a small but nonzero number, the "
      "weights genuinely differ but by a small amount. If large, they're substantially different.)")

# Now test on a handful of FIXED, identical observations -- does deterministic
# prediction actually differ between the two models?
print("\n=== Raw prediction comparison on fixed test observations ===")
rng = np.random.default_rng(42)
n_tests = 10
any_differ = False
for i in range(n_tests):
    obs = rng.uniform(-1, 1, size=(13,)).astype(np.float32)
    action_old, _ = model_old.predict(obs, deterministic=True)
    action_new, _ = model_new.predict(obs, deterministic=True)
    differs = not np.allclose(action_old, action_new, atol=1e-6)
    any_differ = any_differ or differs
    print(f"  Test obs {i}: old_action={action_old}, new_action={action_new}, "
          f"differ={'YES' if differs else 'no'}")

print(f"\nAny predictions differ across {n_tests} random test observations: {any_differ}")
if not any_differ:
    print("WARNING: predictions are identical despite different file hashes. "
          "This points to a real bug -- possibly in how the model was saved after "
          "training, or the 25M run somehow not actually updating this specific "
          "checkpoint file's weights meaningfully.")