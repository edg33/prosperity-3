import numpy as np
import pandas as pd
import itertools
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# ------------------------------
# Editable inputs
# ------------------------------
BASE = 10_000                # Base treasure in each suitcase
COSTS = [0, 50_000, 100_000] # Fees for 1st, 2nd, 3rd openings

# Per-suitcase specs: (name, multiplier, inhabitants)
raw = [
    ("A1", 80, 6),
    ("A2", 50, 4),
    ("A3", 83, 7),
    ("A4", 31, 2),
    ("A5", 60, 4),
    ("B1", 89, 8),
    ("B2", 10, 1),
    ("B3", 37, 3),
    ("B4", 70, 4),
    ("B5", 90, 10),
    ("C1", 17, 1),
    ("C2", 40, 3),
    ("C3", 73, 4),
    ("C4", 100, 15),
    ("C5", 20, 2),
    ("D1", 41, 3),
    ("D2", 79, 5),
    ("D3", 23, 2),
    ("D4", 47, 3),
    ("D5", 30, 2),
]

df = pd.DataFrame(raw, columns=["name", "multiplier", "inhabitants"])
n = len(df)

# Initialize with a distribution that considers both multiplier and inhabitants
def initialize_shares():
    # Consider both multiplier and inhabitants in initial weighting
    weights = df["multiplier"].values / (df["inhabitants"].values ** 0.5)
    shares = weights / weights.sum()
    return shares

# EV function with behavioral noise
def expected_value(shares, noise_level=0.1):
    base_ev = BASE * df["multiplier"].values / (df["inhabitants"].values + 100 * shares)
    # Add multiplicative noise to represent behavioral uncertainty
    noise = 1 + noise_level * np.random.randn(len(shares))
    return base_ev * noise

# Improved replicator dynamics with behavioral factors
def replicator(initial_shares, noise_level=0.1, noise_decay=0.95, max_iter=10000, tol=1e-9):
    shares = initial_shares.copy()
    current_noise = noise_level
    
    for iter in range(max_iter):
        ev = expected_value(shares, current_noise)
        avg = (shares * ev).sum() + 1e-10
        new = shares * ev / avg
        new = 0.8 * new + 0.2 * shares
        
        min_share = 0.00001
        new = np.maximum(new, min_share)
        new = new / new.sum()
        
        if np.max(np.abs(new - shares)) < tol:
            return new
            
        shares = new
        current_noise *= noise_decay
        
    return shares

# Analysis parameters
noise_levels = [0.05, 0.1, 0.15, 0.2, 0.25, 0.5, 0.75, 1.0]
rationality_levels = [0.0, 0.25, 0.5, 0.75, 1.0]
num_simulations = 50

# Storage for results
all_results = []
best_combinations = []
profit_distribution = {}

# Run simulations across noise levels
for noise in noise_levels:
    print(f"\nAnalyzing noise level: {noise:.2f}")
    
    for sim in range(num_simulations):
        initial_shares = initialize_shares()
        full_rational = replicator(initial_shares, noise_level=noise)
        
        for lam in rationality_levels:
            # Blend rational and initial with some randomness
            shares = (1-lam) * initial_shares + lam * full_rational
            shares = shares + np.random.normal(0, 0.01, size=len(shares))
            shares = np.maximum(shares, 0)
            shares = shares / shares.sum()
            
            ev_lam = expected_value(shares, noise_level=noise)
            
            # Find best combinations
            for k in (1,2,3):
                for combo in itertools.combinations(range(n), k):
                    profit = ev_lam[list(combo)].sum() - sum(COSTS[:k])
                    combo_names = ", ".join(sorted([df.loc[i,"name"] for i in combo]))
                    
                    all_results.append({
                        "noise": noise,
                        "lambda": lam,
                        "simulation": sim,
                        "combination": combo_names,
                        "num_suitcases": k,
                        "profit": profit
                    })

# Convert to DataFrame for analysis
results_df = pd.DataFrame(all_results)

# Aggregate results
def analyze_results(df):
    # Best combinations overall
    best_overall = df.groupby('combination')['profit'].agg([
        'mean', 'std', 'count',
        lambda x: np.percentile(x, 25),
        lambda x: np.percentile(x, 75)
    ]).reset_index()
    
    best_overall = best_overall.rename(columns={
        'mean': 'avg_profit',
        'std': 'profit_std',
        '<lambda_0>': 'profit_25th',
        '<lambda_1>': 'profit_75th'
    })
    
    # Sort by average profit
    best_overall = best_overall.sort_values('avg_profit', ascending=False)
    
    # Calculate risk-adjusted returns (Sharpe-like ratio)
    best_overall['risk_adjusted_return'] = best_overall['avg_profit'] / best_overall['profit_std']
    
    return best_overall

# Overall analysis
print("\n=== Overall Best Combinations ===")
best_overall = analyze_results(results_df)
print(best_overall.head(10))

# Analysis by noise level
print("\n=== Best Combinations by Noise Level ===")
for noise in noise_levels:
    noise_results = results_df[results_df['noise'] == noise]
    print(f"\nNoise Level: {noise:.2f}")
    print(analyze_results(noise_results).head(3))

# Create visualizations
plt.figure(figsize=(15, 10))

# Plot 1: Distribution of profits for top combinations
top_5_combos = best_overall.head(5)['combination'].tolist()
plot_data = results_df[results_df['combination'].isin(top_5_combos)]

plt.subplot(2, 1, 1)
sns.boxplot(data=plot_data, x='combination', y='profit')
plt.xticks(rotation=45)
plt.title('Profit Distribution for Top 5 Combinations')

# Plot 2: Profit vs Noise Level for top combinations
plt.subplot(2, 1, 2)
for combo in top_5_combos:
    combo_data = results_df[results_df['combination'] == combo]
    sns.lineplot(data=combo_data, x='noise', y='profit', label=combo)
plt.title('Profit vs Noise Level for Top Combinations')

plt.tight_layout()
plt.savefig('suitcase_analysis.png')

# Statistical significance testing
print("\n=== Statistical Analysis ===")
top_2_combos = best_overall.head(2)['combination'].tolist()
combo1_profits = results_df[results_df['combination'] == top_2_combos[0]]['profit']
combo2_profits = results_df[results_df['combination'] == top_2_combos[1]]['profit']

t_stat, p_value = stats.ttest_ind(combo1_profits, combo2_profits)
print(f"T-test between top 2 combinations:")
print(f"t-statistic: {t_stat:.4f}")
print(f"p-value: {p_value:.4f}")

# Recommendation
print("\n=== Final Recommendation ===")
best_combo = best_overall.iloc[0]
print(f"Most reliable combination: {best_combo['combination']}")
print(f"Average profit: {best_combo['avg_profit']:.2f}")
print(f"Profit range: {best_combo['profit_25th']:.2f} to {best_combo['profit_75th']:.2f}")
print(f"Risk-adjusted return: {best_combo['risk_adjusted_return']:.2f}")

# Save detailed results to CSV for further analysis
results_df.to_csv('suitcase_analysis_results.csv', index=False)
best_overall.to_csv('best_combinations.csv', index=False)
