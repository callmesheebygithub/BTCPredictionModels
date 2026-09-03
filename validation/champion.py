# validation/champion.py
"""
Champion/Challenger System - Model selection
"""

import sqlite3
from datetime import datetime
from typing import Optional, Dict
from models.lstm_model import ModelTrainer
from database.db_manager import DatabaseManager
import pandas as pd
import numpy as np

class ChampionChallenger:
    def __init__(self):
        self.db = DatabaseManager()
        self.model_dir = 'models/'
    
    def evaluate_challenger(self, new_version: str, test_days: int = 30) -> Dict:
        champion = self.get_champion()
        
        if champion is None:
            self.set_champion(new_version)
            return {'promoted': True, 'reason': 'No existing champion'}
        
        champion_trainer = ModelTrainer()
        champion_trainer.load_model(champion)
        
        challenger_trainer = ModelTrainer()
        challenger_trainer.load_model(new_version)
        
        df = self.db.get_all_data()
        if len(df) < test_days:
            return {'promoted': False, 'reason': 'Not enough test data'}
        
        test_df = df.tail(test_days)
        train_df = df.head(len(df) - test_days)
        
        champion_results = []
        challenger_results = []
        
        for i in range(len(test_df)):
            available_data = pd.concat([train_df, test_df.iloc[:i]])
            actual = test_df.iloc[i]['close']
            
            champion_pred = champion_trainer.predict_next_day(available_data)
            challenger_pred = challenger_trainer.predict_next_day(available_data)
            
            if champion_pred is not None:
                champion_results.append(champion_pred)
            
            if challenger_pred is not None:
                challenger_results.append(challenger_pred)
        
        if not champion_results:
            return {'promoted': True, 'reason': 'Champion failed to predict'}
        
        champion_mae = np.mean([abs(x - actual) for x in champion_results[:len(test_df)]])
        challenger_mae = np.mean([abs(x - actual) for x in challenger_results[:len(test_df)]]) if challenger_results else float('inf')
        
        improvement = ((champion_mae - challenger_mae) / champion_mae) * 100 if challenger_mae != float('inf') else -100
        
        result = {
            'promoted': improvement > 5 and challenger_results,
            'champion_mae': champion_mae,
            'challenger_mae': challenger_mae,
            'improvement': improvement,
            'champion': champion,
            'challenger': new_version
        }
        
        if result['promoted']:
            self.set_champion(new_version)
            print(f"[INFO] New champion: {new_version} (Improvement: {improvement:.1f}%)")
        else:
            print(f"[INFO] Challenger {new_version} not promoted (Improvement: {improvement:.1f}%)")
        
        return result
    
    def get_champion(self) -> Optional[str]:
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT version FROM model_versions 
            WHERE is_champion = 1 
            ORDER BY created_at DESC 
            LIMIT 1
        ''')
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def set_champion(self, version: str):
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE model_versions SET is_champion = 0 WHERE is_champion = 1')
        cursor.execute('''
            UPDATE model_versions SET is_champion = 1, created_at = ? WHERE version = ?
        ''', (datetime.now().isoformat(), version))
        
        if cursor.rowcount == 0:
            cursor.execute('''
                INSERT INTO model_versions (version, is_champion, created_at) VALUES (?, 1, ?)
            ''', (version, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        print(f"[OK] Champion set to: {version}")