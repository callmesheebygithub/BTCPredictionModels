# validation/walk_forward.py
"""
Walk-Forward Validation
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from models.lstm_model import ModelTrainer
from database.db_manager import DatabaseManager

class WalkForwardValidator:
    def __init__(self):
        self.db = DatabaseManager()
        self.model_dir = 'validation/'
        self.results = []
    
    def run(self, df: pd.DataFrame, train_years: int = 5, test_years: int = 1):
        """Run walk-forward validation"""
        print("\n[INFO] WALK-FORWARD VALIDATION")
        print("[INFO] " + "="*60)
        
        years = sorted(df['date'].str[:4].unique())
        
        if len(years) < train_years + test_years:
            print(f"[ERROR] Not enough years. Need {train_years + test_years}, have {len(years)}")
            return
        
        results = []
        
        for i in range(len(years) - train_years - test_years + 1):
            fold = i + 1
            train_end_year = years[i + train_years - 1]
            test_end_year = years[i + train_years + test_years - 1]
            
            train_end = f"{train_end_year}-12-31"
            train_start = f"{years[i]}-01-01"
            test_end = f"{test_end_year}-12-31"
            test_start = f"{years[i + train_years]}-01-01"
            
            print(f"\n[INFO] Fold {fold}:")
            print(f"[INFO]   Train: {train_start} to {train_end}")
            print(f"[INFO]   Test:  {test_start} to {test_end}")
            
            # Create isolated trainer
            fold_dir = os.path.join(self.model_dir, f'fold_{fold}')
            trainer = ModelTrainer(model_dir=fold_dir)
            
            # Train on historical data
            train_df = df[(df['date'] >= train_start) & (df['date'] <= train_end)]
            version = f'fold_{fold}_v1'
            trainer.train(train_df, force=True, version=version)
            
            # Test on future data
            test_df = df[(df['date'] >= test_start) & (df['date'] <= test_end)]
            
            predictions = []
            actuals = []
            directions = []
            
            prev_close = train_df.iloc[-1]['close']
            
            for j in range(len(test_df)):
                available_data = pd.concat([train_df, test_df.iloc[:j]])
                pred = trainer.predict_next_day(available_data)
                
                if pred is not None:
                    predictions.append(pred)
                    actuals.append(test_df.iloc[j]['close'])
                    
                    pred_dir = pred > prev_close
                    actual_dir = test_df.iloc[j]['close'] > prev_close
                    directions.append(1 if pred_dir == actual_dir else 0)
                    
                    prev_close = test_df.iloc[j]['close']
            
            if predictions:
                predictions = np.array(predictions)
                actuals = np.array(actuals)
                
                mae = np.mean(np.abs(predictions - actuals))
                rmse = np.sqrt(np.mean((predictions - actuals) ** 2))
                mape = np.mean(np.abs((predictions - actuals) / actuals)) * 100
                dir_acc = np.mean(directions) * 100 if directions else 0
                
                print(f"[INFO]   MAE: ${mae:,.2f}")
                print(f"[INFO]   RMSE: ${rmse:,.2f}")
                print(f"[INFO]   MAPE: {mape:.2f}%")
                print(f"[INFO]   Direction Accuracy: {dir_acc:.1f}%")
                
                result = {
                    'fold': fold,
                    'train_start': train_start,
                    'train_end': train_end,
                    'test_start': test_start,
                    'test_end': test_end,
                    'mae': mae,
                    'rmse': rmse,
                    'mape': mape,
                    'direction_accuracy': dir_acc
                }
                
                self._save_result(result)
                results.append(result)
            else:
                print(f"[WARN] No predictions generated for fold {fold}")
        
        return results
    
    def _save_result(self, result):
        """Save walk-forward result to database"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO walk_forward_results 
            (fold, train_start, train_end, test_start, test_end,
             mae, rmse, mape, direction_accuracy, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (result['fold'], result['train_start'], result['train_end'],
              result['test_start'], result['test_end'], result['mae'],
              result['rmse'], result['mape'], result['direction_accuracy'],
              datetime.now().isoformat()))
        conn.commit()
        conn.close()