import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import itertools
from concurrent.futures import ProcessPoolExecutor
import time

# Constants
BASE = 10_000
COSTS = [0, 50_000, 100_000]
NUM_PLAYERS = 300
NUM_SIMULATIONS = 30

# Progress tracking
def print_progress(current, total, prefix='', suffix='', length=50):
    percent = int(100 * current / total)
    filled = int(length * current / total)
    bar = '=' * filled + '-' * (length - filled)
    print(f'\r{prefix} [{bar}] {percent}% {suffix}', end='', flush=True)
    if current == total:
        print()

# Suitcase configurations
SUITCASES = [
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

class Player:
    def __init__(self, id, rationality, risk_tolerance):
        self.id = id
        self.rationality = rationality
        self.risk_tolerance = risk_tolerance
        
    def calculate_ev(self, suitcase_idx, current_choices, noise_level):
        name, multiplier, inhabitants = SUITCASES[suitcase_idx]
        choice_count = current_choices.count(suitcase_idx)
        perception_noise = np.random.normal(0, (1 - self.rationality) * noise_level)
        ev = BASE * multiplier / (inhabitants + choice_count + 1)
        ev *= (1 + perception_noise)
        risk_factor = 1 - (choice_count / NUM_PLAYERS) * (1 - self.risk_tolerance)
        ev *= risk_factor
        return ev
        
    def evaluate_combination(self, combo, all_evs, current_choices):
        # Calculate total number of suitcase choices for percentage calculation
        total_choices = len(current_choices) if current_choices else 1  # Avoid division by zero
        
        # Calculate total EV for the combination
        total_ev = 0
        for idx in combo:
            # Get base EV
            name, multiplier, inhabitants = SUITCASES[idx]
            
            # Calculate percentage of times this suitcase was chosen
            times_chosen = current_choices.count(idx)
            percentage_chosen = (times_chosen / total_choices) if total_choices > 0 else 0
            
            # Calculate EV according to the rules
            ev = BASE * multiplier / (inhabitants + percentage_chosen * 100)
            
            # Add some noise based on rationality
            if np.random.random() > self.rationality:
                perception_noise = np.random.normal(0, (1 - self.rationality) * 0.1)
                ev *= (1 + perception_noise)
            
            total_ev += ev
        
        # Subtract costs based on number of suitcases
        costs = sum(COSTS[:len(combo)])
        
        # Calculate final profit
        profit = total_ev - costs
        
        return profit
        
    def choose_suitcases(self, current_choices, noise_level):
        all_evs = []
        
        # Calculate EV for each suitcase
        for idx in range(len(SUITCASES)):
            ev = self.calculate_ev(idx, current_choices, noise_level)
            all_evs.append((idx, ev))
        
        # Sort by EV
        all_evs.sort(key=lambda x: x[1], reverse=True)
        
        # Consider top 8 suitcases for combinations
        top_candidates = [x[0] for x in all_evs[:8]]
        
        # Evaluate all possible combinations of 1-3 suitcases
        best_profit = float('-inf')
        best_choice = []
        
        # Try different sizes of combinations
        for k in range(1, 4):  # 1 to 3 suitcases
            for combo in itertools.combinations(top_candidates, k):
                profit = self.evaluate_combination(combo, all_evs, current_choices)
                
                if profit > best_profit:
                    best_profit = profit
                    best_choice = list(combo)
        
        return best_choice

def run_simulation(sim_id):
    np.random.seed(sim_id)
    results = []
    noise_levels = [0.05, 0.1, 0.15, 0.2, 0.25]
    
    # Initialize players with varying characteristics
    players = []
    for i in range(NUM_PLAYERS):
        rationality = np.random.beta(5, 2)  # Most players are somewhat rational
        risk_tolerance = np.random.beta(2, 2)  # Varied risk tolerance
        players.append(Player(i, rationality, risk_tolerance))
    
    # Run multiple rounds with different noise levels
    for noise in noise_levels:
        # Initial random assignment
        current_choices = []
        
        # Sequential choice process
        np.random.shuffle(players)
        for player in players:
            choices = player.choose_suitcases(current_choices, noise)
            current_choices.extend(choices)
        
        # Calculate final distributions and profits
        total_choices = len(current_choices)
        choice_counts = Counter(current_choices)
        
        # Record choices and calculate actual profits
        for player in players:
            player_choices = [i for i in player.choose_suitcases(current_choices, noise)]
            if player_choices:
                # Calculate actual profit
                total_ev = 0
                for choice in player_choices:
                    name, multiplier, inhabitants = SUITCASES[choice]
                    times_chosen = choice_counts[choice]
                    percentage_chosen = times_chosen / total_choices
                    ev = BASE * multiplier / (inhabitants + percentage_chosen * 100)
                    total_ev += ev
                
                profit = total_ev - sum(COSTS[:len(player_choices)])
                choice_names = tuple(sorted([SUITCASES[idx][0] for idx in player_choices]))
                results.append({
                    'simulation': sim_id,
                    'noise': noise,
                    'player_id': player.id,
                    'rationality': player.rationality,
                    'risk_tolerance': player.risk_tolerance,
                    'combination': ', '.join(choice_names),
                    'num_suitcases': len(player_choices),
                    'profit': profit
                })
    
    return results, sim_id

def analyze_results(all_results):
    df = pd.DataFrame(all_results)
    
    # Overall best combinations
    best_combos = df.groupby('combination').agg({
        'profit': ['mean', 'std', 'count'],
        'player_id': 'nunique',
        'num_suitcases': 'first'  # Add number of suitcases to results
    }).reset_index()
    
    best_combos.columns = ['combination', 'avg_profit', 'profit_std', 'count', 'unique_players', 'num_suitcases']
    best_combos['risk_adjusted_return'] = best_combos['avg_profit'] / best_combos['profit_std']
    
    # Group by number of suitcases
    best_by_num = {}
    for n in [1, 2, 3]:
        n_suitcases = best_combos[best_combos['num_suitcases'] == n].sort_values('avg_profit', ascending=False)
        best_by_num[n] = n_suitcases
    
    # Overall best still sorted by profit
    best_combos = best_combos.sort_values('avg_profit', ascending=False)
    
    # Analysis by player characteristics
    rationality_impact = df.groupby(pd.qcut(df['rationality'], 5))['profit'].mean()
    risk_impact = df.groupby(pd.qcut(df['risk_tolerance'], 5))['profit'].mean()
    
    return best_combos, best_by_num, rationality_impact, risk_impact

def main():
    start_time = time.time()
    print(f"Starting massive simulation with {NUM_PLAYERS:,} players across {NUM_SIMULATIONS} simulations")
    print(f"Total calculations: {NUM_PLAYERS * NUM_SIMULATIONS * 5:,} player decisions")
    print("-" * 70)
    
    # Run simulations in parallel
    all_results = []
    completed = 0
    
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_simulation, i) for i in range(NUM_SIMULATIONS)]
        
        while completed < NUM_SIMULATIONS:
            newly_completed = [f for f in futures if f.done()]
            for future in newly_completed:
                results, sim_id = future.result()
                all_results.extend(results)
                futures.remove(future)
                completed += 1
                
                print_progress(completed, NUM_SIMULATIONS,
                             prefix='Overall Progress:',
                             suffix=f'({completed}/{NUM_SIMULATIONS} simulations)')
            
            time.sleep(0.1)
    
    print("\nAnalyzing results...")
    best_combos, best_by_num, rationality_impact, risk_impact = analyze_results(all_results)
    
    print("\n=== Best Combinations by Number of Suitcases ===")
    for n in [1, 2, 3]:
        print(f"\nTop 5 combinations with {n} suitcase{'s' if n > 1 else ''}:")
        print(best_by_num[n][['combination', 'avg_profit', 'profit_std', 'count', 'risk_adjusted_return']].head())
    
    print("\n=== Overall Top 10 Most Profitable Combinations ===")
    print(best_combos[['combination', 'num_suitcases', 'avg_profit', 'profit_std', 'count', 'risk_adjusted_return']].head(10))
    
    print("\n=== Impact of Player Rationality on Profit ===")
    print(rationality_impact)
    
    print("\n=== Impact of Risk Tolerance on Profit ===")
    print(risk_impact)
    
    print("\nGenerating visualizations...")
    plt.figure(figsize=(15, 15))
    
    # Plot 1: Top combinations profit distribution by number of suitcases
    plt.subplot(3, 1, 1)
    top_n_each = []
    for n in [1, 2, 3]:
        top_n_each.extend(best_by_num[n].head(3)['combination'].tolist())
    
    plot_data = pd.DataFrame(all_results)
    plot_data = plot_data[plot_data['combination'].isin(top_n_each)]
    sns.boxplot(data=plot_data, x='combination', y='profit', hue='num_suitcases')
    plt.xticks(rotation=45)
    plt.title('Profit Distribution for Top 3 Combinations of Each Size')
    
    # Plot 2: Profit vs Number of Suitcases
    plt.subplot(3, 1, 2)
    sns.boxplot(data=plot_data, x='num_suitcases', y='profit')
    plt.title('Profit Distribution by Number of Suitcases')
    
    # Plot 3: Profit vs Rationality
    plt.subplot(3, 1, 3)
    sns.scatterplot(data=plot_data, x='rationality', y='profit', hue='num_suitcases', alpha=0.1)
    plt.title('Profit vs Player Rationality by Number of Suitcases')
    
    plt.tight_layout()
    plt.savefig('massive_simulation_results.png')
    
    print("\nSaving results to CSV files...")
    pd.DataFrame(all_results).to_csv('massive_simulation_results.csv', index=False)
    best_combos.to_csv('massive_simulation_best_combos.csv', index=False)
    
    # Save results by number of suitcases
    for n in [1, 2, 3]:
        best_by_num[n].to_csv(f'best_combinations_{n}_suitcases.csv', index=False)
    
    elapsed = time.time() - start_time
    print(f"\nSimulation completed in {elapsed:.1f} seconds")
    print(f"Average time per simulation: {elapsed/NUM_SIMULATIONS:.1f} seconds")
    print(f"Average time per player decision: {elapsed/(NUM_PLAYERS * NUM_SIMULATIONS * 5)*1000:.2f} ms")

if __name__ == "__main__":
    main()
