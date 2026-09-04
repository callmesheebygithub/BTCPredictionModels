# validation/champion.py
"""
Champion/Challenger System - Model selection
FIXED: Proper model loading, error handling, and champion management
"""

import sqlite3
from datetime import datetime
from typing import Optional, Dict
from models.lstm_model import ModelTrainer
from database.db_manager import DatabaseManager
import pandas as pd
import numpy as np
import os


class ChampionChallenger:
    def __init__(self):
        self.db = DatabaseManager()
        self.model_dir = 'models/'
        self._ensure_model_dir()
    
    def _ensure_model_dir(self):
        """Ensure model directory exists"""
        os.makedirs(self.model_dir, exist_ok=True)
    
    def evaluate_challenger(self, new_version: str, test_days: int = 30) -> Dict:
        """
        Evaluate challenger against champion
        
        Args:
            new_version: Version string of challenger model
            test_days: Number of days to test on
        
        Returns:
            Dict with evaluation results
        """
        champion = self.get_champion()
        
        # If no champion exists, promote immediately
        if champion is None:
            self.set_champion(new_version)
            return {
                'promoted': True, 
                'reason': 'No existing champion',
                'champion': None,
                'challenger': new_version,
                'improvement': 100.0
            }
        
        try:
            # Load both models
            champion_trainer = ModelTrainer()
            if not champion_trainer.load_model(champion):
                # If champion can't load, promote challenger
                self.set_champion(new_version)
                return {
                    'promoted': True,
                    'reason': 'Champion failed to load',
                    'champion': champion,
                    'challenger': new_version,
                    'improvement': 100.0
                }
            
            challenger_trainer = ModelTrainer()
            if not challenger_trainer.load_model(new_version):
                return {
                    'promoted': False,
                    'reason': 'Challenger failed to load',
                    'champion': champion,
                    'challenger': new_version,
                    'improvement': 0.0
                }
            
            df = self.db.get_all_data()
            if df.empty or len(df) < test_days + 30:
                return {
                    'promoted': False,
                    'reason': 'Not enough test data',
                    'champion': champion,
                    'challenger': new_version,
                    'improvement': 0.0
                }
            
            # Split data
            test_df = df.tail(test_days)
            train_df = df.head(len(df) - test_days)
            
            # Test both models
            champion_results = []
            challenger_results = []
            
            for i in range(len(test_df)):
                available_data = pd.concat([train_df, test_df.iloc[:i]])
                actual = test_df.iloc[i]['close']
                
                champion_pred = champion_trainer.predict_next_day(available_data)
                challenger_pred = challenger_trainer.predict_next_day(available_data)
                
                if champion_pred is not None:
                    champion_results.append({
                        'date': test_df.iloc[i]['date'],
                        'prediction': champion_pred,
                        'actual': actual,
                        'error': abs(champion_pred - actual)
                    })
                
                if challenger_pred is not None:
                    challenger_results.append({
                        'date': test_df.iloc[i]['date'],
                        'prediction': challenger_pred,
                        'actual': actual,
                        'error': abs(challenger_pred - actual)
                    })
            
            if not champion_results:
                self.set_champion(new_version)
                return {
                    'promoted': True,
                    'reason': 'Champion failed to predict',
                    'champion': champion,
                    'challenger': new_version,
                    'improvement': 100.0
                }
            
            if not challenger_results:
                return {
                    'promoted': False,
                    'reason': 'Challenger failed to predict',
                    'champion': champion,
                    'challenger': new_version,
                    'improvement': 0.0
                }
            
            # Calculate metrics
            champion_mae = np.mean([r['error'] for r in champion_results])
            challenger_mae = np.mean([r['error'] for r in challenger_results])
            
            # Direction accuracy
            champion_directions = []
            challenger_directions = []
            
            for i in range(1, min(len(champion_results), len(challenger_results))):
                # Champion direction
                if champion_results[i]['prediction'] > champion_results[i-1]['actual']:
                    champion_dir = 1
                else:
                    champion_dir = 0
                
                if champion_results[i]['actual'] > champion_results[i-1]['actual']:
                    actual_dir = 1
                else:
                    actual_dir = 0
                
                champion_directions.append(1 if champion_dir == actual_dir else 0)
                
                # Challenger direction
                if challenger_results[i]['prediction'] > challenger_results[i-1]['actual']:
                    challenger_dir = 1
                else:
                    challenger_dir = 0
                
                if challenger_results[i]['actual'] > challenger_results[i-1]['actual']:
                    actual_dir = 1
                else:
                    actual_dir = 0
                
                challenger_directions.append(1 if challenger_dir == actual_dir else 0)
            
            champion_dir_acc = np.mean(champion_directions) * 100 if champion_directions else 0
            challenger_dir_acc = np.mean(challenger_directions) * 100 if challenger_directions else 0
            
            # Improvement calculation
            improvement = ((champion_mae - challenger_mae) / champion_mae) * 100 if champion_mae > 0 else 0
            
            result = {
                'promoted': improvement > 5,  # At least 5% improvement
                'champion_mae': champion_mae,
                'challenger_mae': challenger_mae,
                'champion_dir_acc': champion_dir_acc,
                'challenger_dir_acc': challenger_dir_acc,
                'improvement': improvement,
                'champion': champion,
                'challenger': new_version,
                'reason': 'Improvement threshold met' if improvement > 5 else 'Insufficient improvement'
            }
            
            if result['promoted']:
                self.set_champion(new_version)
                print(f"[INFO] 🏆 New champion: {new_version}")
                print(f"[INFO]   MAE Improvement: {improvement:.1f}%")
                print(f"[INFO]   Direction Accuracy: {challenger_dir_acc:.1f}% vs {champion_dir_acc:.1f}%")
            else:
                print(f"[INFO] ❌ Challenger {new_version} not promoted")
                print(f"[INFO]   MAE Improvement: {improvement:.1f}% (need >5%)")
                print(f"[INFO]   Direction Accuracy: {challenger_dir_acc:.1f}% vs {champion_dir_acc:.1f}%")
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Champion evaluation failed: {e}")
            return {
                'promoted': False,
                'reason': f'Evaluation error: {str(e)}',
                'champion': champion,
                'challenger': new_version,
                'improvement': 0.0
            }
    
    def get_champion(self) -> Optional[str]:
        """Get current champion version"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            
            # First check if any champion exists
            cursor.execute('SELECT COUNT(*) FROM model_versions WHERE is_champion = 1')
            count = cursor.fetchone()[0]
            
            if count == 0:
                conn.close()
                return None
            
            # Get the champion
            cursor.execute('''
                SELECT version FROM model_versions 
                WHERE is_champion = 1 
                ORDER BY created_at DESC 
                LIMIT 1
            ''')
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                # Verify model files exist
                version_dir = os.path.join(self.model_dir, result[0])
                model_path = os.path.join(version_dir, 'model.pth')
                if not os.path.exists(model_path):
                    print(f"[WARN] Champion {result[0]} files missing, clearing champion")
                    self._clear_champion()
                    return None
                return result[0]
            
            return None
            
        except Exception as e:
            print(f"[ERROR] Failed to get champion: {e}")
            return None
    
    def _clear_champion(self):
        """Clear champion flag"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE model_versions SET is_champion = 0 WHERE is_champion = 1')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[ERROR] Failed to clear champion: {e}")
    
    def set_champion(self, version: str):
        """
        Set a model as champion
        
        Args:
            version: Version string to set as champion
        """
        try:
            # Verify model exists
            version_dir = os.path.join(self.model_dir, version)
            model_path = os.path.join(version_dir, 'model.pth')
            if not os.path.exists(model_path):
                print(f"[ERROR] Cannot set champion: Model {version} not found")
                return
            
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            
            # Clear existing champions
            cursor.execute('UPDATE model_versions SET is_champion = 0 WHERE is_champion = 1')
            
            # Check if version already exists
            cursor.execute('SELECT version FROM model_versions WHERE version = ?', (version,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record
                cursor.execute('''
                    UPDATE model_versions 
                    SET is_champion = 1, created_at = ? 
                    WHERE version = ?
                ''', (datetime.now().isoformat(), version))
            else:
                # Insert new record
                cursor.execute('''
                    INSERT INTO model_versions (version, is_champion, created_at) 
                    VALUES (?, 1, ?)
                ''', (version, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            print(f"[OK] ✅ Champion set to: {version}")
            
        except Exception as e:
            print(f"[ERROR] Failed to set champion: {e}")
    
    def list_models(self):
        """List all available models"""
        try:
            if not os.path.exists(self.model_dir):
                print("[INFO] No models directory found")
                return
            
            versions = [d for d in os.listdir(self.model_dir) 
                       if os.path.isdir(os.path.join(self.model_dir, d))]
            
            if not versions:
                print("[INFO] No models found")
                return
            
            champion = self.get_champion()
            
            print(f"\n[INFO] Available Models:")
            print("-" * 50)
            for version in sorted(versions, reverse=True):
                is_champion = "🏆 CHAMPION" if version == champion else ""
                version_dir = os.path.join(self.model_dir, version)
                model_path = os.path.join(version_dir, 'model.pth')
                if os.path.exists(model_path):
                    size = os.path.getsize(model_path) / 1024 / 1024
                    print(f"  {version} - {size:.2f} MB {is_champion}")
                else:
                    print(f"  {version} - ❌ INCOMPLETE")
            print("-" * 50)
            
        except Exception as e:
            print(f"[ERROR] Failed to list models: {e}")