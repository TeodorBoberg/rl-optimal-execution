import pandas as pd

UNRELIABLE_TICKERS = {"unh", "jnj", "cat", "roku", "etsy"}

df = pd.read_csv("data/combined_1m.csv")
print(f"Before filtering: {len(df)} rows, {df['ticker'].nunique()} tickers")

df_clean = df[~df["ticker"].isin(UNRELIABLE_TICKERS)].copy()
print(f"After filtering: {len(df_clean)} rows, {df_clean['ticker'].nunique()} tickers")
print(f"Remaining tickers: {sorted(df_clean['ticker'].unique())}")

# No day-renumbering needed -- train_test_split_days() groups by ticker and
# renumbers within each split already, so gaps in the global day numbering
# (left behind by the removed tickers' day blocks) don't affect anything
# downstream.

df_clean.to_csv("data/combined_1m_clean.csv", index=False)
print("\nSaved to data/combined_1m_clean.csv")
print("Update configs/default.yaml -> data.path to point at this file.")