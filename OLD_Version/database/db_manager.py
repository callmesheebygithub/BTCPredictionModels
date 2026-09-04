# database/db_manager.py
"""
Database Manager - Handles all database operations
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta  # FIXED: Added timedelta
from typing import Optional, List, Dict
import os

class DatabaseManager:
    def __init__(self, db_path='btc_data.db'):
        self.db_path = db_path
        self.create_tables()
    
    def create_tables(self):
        """Create all required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # BTC daily data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS btc_daily (
                date TEXT PRIMARY KEY,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL
            )
        ''')
        
        # Model predictions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                model_name TEXT,
                predicted_price REAL,
                actual_price REAL,
                predicted_return REAL,
                actual_return REAL,
                absolute_error REAL,
                squared_error REAL,
                direction_correct INTEGER,
                prev_close REAL,
                timestamp TEXT,
                UNIQUE(date, model_name)
            )
        ''')
        
        # Ensemble predictions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                predicted_close REAL,
                actual_close REAL,
                error_percentage REAL,
                absolute_error REAL,
                direction_correct INTEGER,
                direction_type TEXT,
                actual_direction_type TEXT,
                predicted_return REAL,
                actual_return REAL,
                confidence_score REAL,
                range_low REAL,
                range_high REAL,
                regime TEXT,
                signal TEXT,
                model_version TEXT,
                timestamp TEXT
            )
        ''')
        
        # Performance metrics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                period TEXT,
                mae REAL,
                rmse REAL,
                mape REAL,
                smape REAL,
                mean_error REAL,
                median_abs_error REAL,
                direction_accuracy REAL,
                up_accuracy REAL,
                down_accuracy REAL,
                total_predictions INTEGER,
                model_version TEXT,
                UNIQUE(date, period)
            )
        ''')
        
        # Model versions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT UNIQUE,
                model_type TEXT,
                train_start TEXT,
                train_end TEXT,
                test_start TEXT,
                test_end TEXT,
                features TEXT,
                hyperparameters TEXT,
                metrics TEXT,
                is_champion INTEGER DEFAULT 0,
                created_at TEXT
            )
        ''')
        
        # Walk-forward results
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS walk_forward_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fold INTEGER,
                train_start TEXT,
                train_end TEXT,
                test_start TEXT,
                test_end TEXT,
                mae REAL,
                rmse REAL,
                mape REAL,
                direction_accuracy REAL,
                model_version TEXT,
                created_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_last_date(self):
        """Get last date in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(date) FROM btc_daily')
        result = cursor.fetchone()[0]
        conn.close()
        return result
    
    def get_count(self):
        """Get total records count"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM btc_daily')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def insert_data(self, df):
        """Insert data into btc_daily"""
        conn = sqlite3.connect(self.db_path)
        df.to_sql('btc_daily', conn, if_exists='append', index=False)
        conn.close()
    
    def get_all_data(self):
        """Get all BTC data"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query('SELECT * FROM btc_daily ORDER BY date', conn)
        conn.close()
        return df
    
    def get_data_after_date(self, date):
        """Get data after specific date"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(f'SELECT * FROM btc_daily WHERE date > "{date}" ORDER BY date', conn)
        conn.close()
        return df
    
    def get_previous_close(self, date):
        """Get previous day's close price"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT close FROM btc_daily 
            WHERE date < ? 
            ORDER BY date DESC 
            LIMIT 1
        ''', (date,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def save_model_prediction(self, date: str, model_name: str, predicted: float, 
                             actual: Optional[float] = None, 
                             prev_close: Optional[float] = None):
        """Save individual model prediction"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if actual is not None and prev_close is not None:
            abs_error = abs(predicted - actual)
            sq_error = (predicted - actual) ** 2
            pred_return = (predicted - prev_close) / prev_close
            actual_return = (actual - prev_close) / prev_close
            direction_correct = 1 if (predicted > prev_close) == (actual > prev_close) else 0
        else:
            abs_error = None
            sq_error = None
            pred_return = None
            actual_return = None
            direction_correct = None
        
        cursor.execute('''
            INSERT OR REPLACE INTO model_predictions 
            (date, model_name, predicted_price, actual_price, predicted_return,
             actual_return, absolute_error, squared_error, direction_correct, 
             prev_close, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date, model_name, predicted, actual, pred_return,
              actual_return, abs_error, sq_error, direction_correct,
              prev_close, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_model_performance(self, model_name: str, days: int = 30) -> pd.DataFrame:
        """Get performance metrics for a specific model"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(f'''
            SELECT 
                date,
                absolute_error as mae,
                squared_error as mse,
                direction_correct,
                predicted_return,
                actual_return,
                prev_close
            FROM model_predictions 
            WHERE model_name = ? AND actual_price IS NOT NULL
            ORDER BY date DESC 
            LIMIT {days}
        ''', conn, params=(model_name,))
        conn.close()
        
        if not df.empty:
            df['rmse'] = np.sqrt(df['mse'])
            df['mape'] = (df['mae'] / df['actual_price']) * 100 if 'actual_price' in df.columns else None
            df['direction_accuracy'] = df['direction_correct'].mean() * 100
            df['total_predictions'] = len(df)
        
        return df
    
    def save_ensemble_prediction(self, date: str, predicted: float, actual: Optional[float] = None,
                                confidence_score: Optional[float] = None,
                                range_low: Optional[float] = None, range_high: Optional[float] = None,
                                regime: Optional[str] = None, signal: Optional[str] = None,
                                model_version: str = 'v1.0'):
        """Save ensemble prediction"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        prev_close = self.get_previous_close(date)
        
        if actual is not None:
            error_pct = ((predicted - actual) / actual) * 100
            abs_error = abs(predicted - actual)
            
            if prev_close is not None:
                pred_direction = predicted > prev_close
                actual_direction = actual > prev_close
                direction_correct = 1 if pred_direction == actual_direction else 0
                direction_type = 'UP' if pred_direction else 'DOWN'
                actual_direction_type = 'UP' if actual_direction else 'DOWN'
                pred_return = (predicted - prev_close) / prev_close
                actual_return = (actual - prev_close) / prev_close
            else:
                direction_correct = None
                direction_type = 'UNKNOWN'
                actual_direction_type = 'UNKNOWN'
                pred_return = None
                actual_return = None
        else:
            error_pct = None
            abs_error = None
            direction_correct = None
            actual_direction_type = None
            actual_return = None
            
            if prev_close is not None:
                pred_direction = predicted > prev_close
                direction_type = 'UP' if pred_direction else 'DOWN'
                pred_return = (predicted - prev_close) / prev_close
            else:
                direction_type = 'UNKNOWN'
                pred_return = None
        
        cursor.execute('''
            INSERT OR REPLACE INTO predictions 
            (date, predicted_close, actual_close, error_percentage, absolute_error,
             direction_correct, direction_type, actual_direction_type,
             predicted_return, actual_return, confidence_score, range_low, range_high,
             regime, signal, model_version, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date, predicted, actual, error_pct, abs_error,
              direction_correct, direction_type, actual_direction_type,
              pred_return, actual_return, confidence_score, range_low, range_high,
              regime, signal, model_version, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def update_yesterday_predictions(self):
        """Update yesterday's predictions with actual prices - FIXED"""
        # Use UTC timezone
        utc = pytz.UTC
        yesterday = (datetime.now(utc) - timedelta(days=1)).strftime('%Y-%m-%d')
        
        print(f"[INFO] Checking yesterday's prediction for: {yesterday}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if yesterday's data exists in btc_daily
        cursor.execute('SELECT close FROM btc_daily WHERE date = ?', (yesterday,))
        actual = cursor.fetchone()
        
        if not actual:
            print(f"[WARN] No actual price found for {yesterday} in btc_daily")
            conn.close()
            return False
        
        actual_close = actual[0]
        prev_close = self.get_previous_close(yesterday)
        
        # Check if prediction exists for yesterday
        cursor.execute('''
            SELECT id, predicted_close FROM predictions 
            WHERE date = ? AND actual_close IS NULL
        ''', (yesterday,))
        pred = cursor.fetchone()
        
        if pred:
            pred_id, predicted = pred
            print(f"[INFO] Updating yesterday's prediction ({yesterday})")
            print(f"[INFO]   Predicted: ${predicted:,.2f}")
            print(f"[INFO]   Actual: ${actual_close:,.2f}")
            
            # Calculate error
            error_pct = ((predicted - actual_close) / actual_close) * 100
            abs_error = abs(predicted - actual_close)
            
            # Update prediction with actual
            cursor.execute('''
                UPDATE predictions 
                SET actual_close = ?, error_percentage = ?, absolute_error = ?, timestamp = ?
                WHERE id = ?
            ''', (actual_close, error_pct, abs_error, datetime.now(utc).isoformat(), pred_id))
            conn.commit()
            print(f"[OK] ✅ Prediction updated with actual close")
            
            # Update individual model predictions
            cursor.execute('''
                SELECT model_name, predicted_price FROM model_predictions 
                WHERE date = ? AND actual_price IS NULL
            ''', (yesterday,))
            model_preds = cursor.fetchall()
            
            for model_name, predicted in model_preds:
                # Calculate metrics for model
                abs_error = abs(predicted - actual_close)
                sq_error = (predicted - actual_close) ** 2
                
                if prev_close is not None:
                    pred_return = (predicted - prev_close) / prev_close
                    actual_return = (actual_close - prev_close) / prev_close
                    direction_correct = 1 if (predicted > prev_close) == (actual_close > prev_close) else 0
                else:
                    pred_return = None
                    actual_return = None
                    direction_correct = None
                
                cursor.execute('''
                    UPDATE model_predictions 
                    SET actual_price = ?, absolute_error = ?, squared_error = ?,
                        predicted_return = ?, actual_return = ?, direction_correct = ?,
                        timestamp = ?
                    WHERE date = ? AND model_name = ?
                ''', (actual_close, abs_error, sq_error, pred_return, actual_return,
                      direction_correct, datetime.now(utc).isoformat(), yesterday, model_name))
            
            conn.commit()
            print(f"[OK] ✅ Updated {len(model_preds)} individual model predictions")
            conn.close()
            
            # Update performance metrics
            self.update_performance_metrics()
            return True
        else:
            # Check if prediction exists but already has actual
            cursor.execute('''
                SELECT predicted_close, actual_close FROM predictions 
                WHERE date = ?
            ''', (yesterday,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"[INFO] Prediction for {yesterday} already has actual: ${existing[1]:,.2f}")
            else:
                print(f"[WARN] No prediction found for {yesterday}")
            
            conn.close()
            return False
    
    def get_recent_predictions(self, days=30):
        """Get recent predictions"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(f'''
            SELECT * FROM predictions 
            WHERE actual_close IS NOT NULL
            ORDER BY date DESC 
            LIMIT {days}
        ''', conn)
        conn.close()
        return df
    
    def get_all_predictions(self):
        """Get all predictions"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query('SELECT * FROM predictions ORDER BY date DESC', conn)
        conn.close()
        return df
    
    def update_performance_metrics(self):
        """Update performance metrics"""
        conn = sqlite3.connect(self.db_path)
        
        df = pd.read_sql_query('''
            SELECT date, predicted_close, actual_close, error_percentage,
                   absolute_error, direction_correct, direction_type,
                   predicted_return, actual_return
            FROM predictions 
            WHERE actual_close IS NOT NULL 
            ORDER BY date DESC 
            LIMIT 30
        ''', conn)
        
        if df.empty:
            conn.close()
            return None
        
        valid = df.dropna(subset=['error_percentage', 'absolute_error'])
        
        squared_errors = (valid['predicted_close'] - valid['actual_close']) ** 2
        rmse = np.sqrt(squared_errors.mean())
        
        metrics = {
            'mae': valid['absolute_error'].mean(),
            'rmse': rmse,
            'mape': valid['error_percentage'].abs().mean(),
            'smape': (2 * np.abs(valid['predicted_close'] - valid['actual_close']) / 
                     (np.abs(valid['predicted_close']) + np.abs(valid['actual_close']))).mean() * 100,
            'mean_error': valid['error_percentage'].mean(),
            'median_abs_error': valid['absolute_error'].median(),
            'direction_accuracy': valid['direction_correct'].mean() * 100,
            'total_predictions': len(valid)
        }
        
        if 'direction_type' in valid.columns:
            up_preds = valid[valid['direction_type'] == 'UP']
            down_preds = valid[valid['direction_type'] == 'DOWN']
            metrics['up_accuracy'] = up_preds['direction_correct'].mean() * 100 if not up_preds.empty else 0
            metrics['down_accuracy'] = down_preds['direction_correct'].mean() * 100 if not down_preds.empty else 0
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO performance 
            (date, period, mae, rmse, mape, smape, mean_error,
             median_abs_error, direction_accuracy, up_accuracy, down_accuracy,
             total_predictions, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (today, 'rolling_30d', metrics['mae'], metrics['rmse'], metrics['mape'],
              metrics['smape'], metrics['mean_error'], metrics['median_abs_error'],
              metrics['direction_accuracy'], metrics['up_accuracy'],
              metrics['down_accuracy'], metrics['total_predictions'], 'v1'))
        
        conn.commit()
        conn.close()
        
        print(f"[INFO] Performance Metrics (Last {metrics['total_predictions']} days):")
        print(f"[INFO]   MAE: ${metrics['mae']:,.2f}")
        print(f"[INFO]   RMSE: ${metrics['rmse']:,.2f}")
        print(f"[INFO]   MAPE: {metrics['mape']:.2f}%")
        print(f"[INFO]   Direction Accuracy: {metrics['direction_accuracy']:.1f}%")
        
        return metrics

    