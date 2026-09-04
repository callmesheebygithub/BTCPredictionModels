# models/ensemble.py
"""
Dynamic Ensemble - Weighted model combination
"""

from database.db_manager import DatabaseManager
from typing import Dict, List

class DynamicEnsemble:
    def __init__(self):
        self.db = DatabaseManager()
        self.weights = {}
    
    def calculate_weights(self, model_names: List[str], lookback_days: int = 30) -> Dict[str, float]:
        weights = {}
        performance_scores = {}
        
        for name in model_names:
            perf_df = self.db.get_model_performance(name, lookback_days)
            
            if not perf_df.empty:
                mape = perf_df['mape'].mean() if 'mape' in perf_df.columns else 100
                dir_acc = perf_df['direction_accuracy'].mean() if 'direction_accuracy' in perf_df.columns else 50
                
                mape_score = max(0, 100 - mape)
                dir_score = dir_acc
                score = (mape_score * 0.6) + (dir_score * 0.4)
                performance_scores[name] = max(1, score)
            else:
                performance_scores[name] = 50.0
        
        total = sum(performance_scores.values())
        if total > 0:
            for name in performance_scores:
                weights[name] = performance_scores[name] / total
        else:
            for name in model_names:
                weights[name] = 1.0 / len(model_names)
        
        self.weights = weights
        return weights