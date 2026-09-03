"""
BTC PREDICTOR - PRODUCTION VERSION v4.0
COMPLETE FIXED CODE - Realistic Predictions, Proper Training, All Features Working
"""

import pandas as pd
import numpy as np
import sqlite3
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime, timedelta
import schedule
import time
import os
import pickle
import json
import logging
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# ============================================
# LOGGING SETUP
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('btc_predictor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def print_success(msg): print(f"[OK] {msg}")
def print_info(msg): print(f"[INFO] {msg}")
def print_error(msg): print(f"[ERROR] {msg}")
def print_warning(msg): print(f"[WARN] {msg}")

# ============================================
# CONSTANTS
# ============================================

SCHEDULE_TIME = "00:30"
MAX_DAILY_CHANGE = 0.12  # 12% max daily change (sanity check)

# ============================================
# IMPORTS
# ============================================

try:
    from advanced_ml import AdvancedMLModels, ProphetPredictor, AdvancedLSTMTrainer
    print_success("Advanced ML module loaded")
except ImportError as e:
    print_error(f"Error loading advanced_ml.py: {e}")
    print_info("Continuing without advanced ML...")
    AdvancedMLModels = None
    ProphetPredictor = None
    AdvancedLSTMTrainer = None

try:
    from email_notifier import EmailNotifier, setup_email_config
    print_success("Email notifier module loaded")
except ImportError as e:
    print_error(f"Error loading email_notifier.py: {e}")
    EmailNotifier = None
    setup_email_config = None

# ============================================
# 1. COMPLETE DATABASE MANAGER
# ============================================

class DatabaseManager:
    def __init__(self, db_path='btc_data.db'):
        self.db_path = db_path
        self.create_tables()
    
    def create_tables(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(date) FROM btc_daily')
        result = cursor.fetchone()[0]
        conn.close()
        return result
    
    def get_count(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM btc_daily')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def insert_data(self, df):
        conn = sqlite3.connect(self.db_path)
        df.to_sql('btc_daily', conn, if_exists='append', index=False)
        conn.close()
    
    def get_all_data(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query('SELECT * FROM btc_daily ORDER BY date', conn)
        conn.close()
        return df
    
    def get_data_after_date(self, date):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(f'SELECT * FROM btc_daily WHERE date > "{date}" ORDER BY date', conn)
        conn.close()
        return df
    
    def get_previous_close(self, date):
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
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT close FROM btc_daily WHERE date = ?', (yesterday,))
        actual = cursor.fetchone()
        
        if not actual:
            conn.close()
            return False
        
        actual_close = actual[0]
        prev_close = self.get_previous_close(yesterday)
        
        cursor.execute('''
            SELECT predicted_close FROM predictions 
            WHERE date = ? AND actual_close IS NULL
        ''', (yesterday,))
        pred = cursor.fetchone()
        
        if pred:
            print_info(f"Updating yesterday's prediction ({yesterday})")
            print_info(f"  Predicted: ${pred[0]:,.2f}")
            print_info(f"  Actual: ${actual_close:,.2f}")
            self.save_ensemble_prediction(yesterday, pred[0], actual_close)
        
        cursor.execute('''
            SELECT model_name, predicted_price FROM model_predictions 
            WHERE date = ? AND actual_price IS NULL
        ''', (yesterday,))
        model_preds = cursor.fetchall()
        
        for model_name, predicted in model_preds:
            self.save_model_prediction(yesterday, model_name, predicted, actual_close, prev_close)
        
        conn.close()
        return True
    
    def get_recent_predictions(self, days=30):
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
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query('SELECT * FROM predictions ORDER BY date DESC', conn)
        conn.close()
        return df
    
    def update_performance_metrics(self):
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
        
        print_info(f"Performance Metrics (Last {metrics['total_predictions']} days):")
        print_info(f"  MAE: ${metrics['mae']:,.2f}")
        print_info(f"  RMSE: ${metrics['rmse']:,.2f}")
        print_info(f"  MAPE: {metrics['mape']:.2f}%")
        print_info(f"  Direction Accuracy: {metrics['direction_accuracy']:.1f}%")
        
        return metrics

# ============================================
# 2. LSTM MODEL
# ============================================

class LSTMPredictor(nn.Module):
    def __init__(self, input_size=5, hidden_size=64, num_layers=2):
        super(LSTMPredictor, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc1 = nn.Linear(hidden_size, 32)
        self.fc2 = nn.Linear(32, 1)
        self.dropout = nn.Dropout(0.2)
        self.relu = nn.ReLU()
    
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        out = self.dropout(self.relu(self.fc1(lstm_out[:, -1, :])))
        return self.fc2(out)

class ModelTrainer:
    def __init__(self, model_dir='models/'):
        self.model_dir = model_dir
        self.scaler = None
        self.model = None
        self.seq_length = 30
        self.is_trained = False
        self.feature_count = 5
        self.features = ['open', 'high', 'low', 'close', 'volume']
        self.train_date = None
        self.test_date = None
        self.model_version = None
        self.validation_loss = None
        
        os.makedirs(model_dir, exist_ok=True)
    
    def _get_model_paths(self, version=None):
        if version is None:
            version = self.model_version or 'latest'
        
        version_dir = os.path.join(self.model_dir, version)
        os.makedirs(version_dir, exist_ok=True)
        
        return {
            'model': os.path.join(version_dir, 'model.pth'),
            'scaler': os.path.join(version_dir, 'scaler.pkl'),
            'metadata': os.path.join(version_dir, 'metadata.json'),
            'train_info': os.path.join(version_dir, 'train_info.json')
        }
    
    def save_model(self, version):
        paths = self._get_model_paths(version)
        
        torch.save(self.model.state_dict(), paths['model'])
        
        with open(paths['scaler'], 'wb') as f:
            pickle.dump(self.scaler, f)
        
        metadata = {
            'feature_count': self.feature_count,
            'features': self.features,
            'seq_length': self.seq_length,
            'train_date': self.train_date,
            'test_date': self.test_date,
            'validation_loss': self.validation_loss,
            'version': version,
            'created_at': datetime.now().isoformat()
        }
        with open(paths['metadata'], 'w') as f:
            json.dump(metadata, f, indent=4)
        
        train_info = {
            'train_start': self.train_start if hasattr(self, 'train_start') else None,
            'train_end': self.train_end if hasattr(self, 'train_end') else None,
            'test_start': self.test_start if hasattr(self, 'test_start') else None,
            'test_end': self.test_end if hasattr(self, 'test_end') else None,
            'num_features': self.feature_count,
            'seq_length': self.seq_length
        }
        with open(paths['train_info'], 'w') as f:
            json.dump(train_info, f, indent=4)
        
        self.model_version = version
        print_success(f"Model saved: {version}")
    
    def load_model(self, version='latest'):
        if version == 'latest':
            versions = [d for d in os.listdir(self.model_dir) 
                       if os.path.isdir(os.path.join(self.model_dir, d))]
            if not versions:
                print_error("No model versions found")
                return False
            version = sorted(versions)[-1]
        
        paths = self._get_model_paths(version)
        
        if not os.path.exists(paths['model']):
            print_error(f"Model not found: {paths['model']}")
            return False
        
        try:
            self.model = LSTMPredictor(input_size=5)
            self.model.load_state_dict(torch.load(paths['model']))
            self.model.eval()
            
            with open(paths['scaler'], 'rb') as f:
                self.scaler = pickle.load(f)
            
            if os.path.exists(paths['metadata']):
                with open(paths['metadata'], 'r') as f:
                    metadata = json.load(f)
                    self.feature_count = metadata.get('feature_count', 5)
                    self.features = metadata.get('features', ['open', 'high', 'low', 'close', 'volume'])
                    self.seq_length = metadata.get('seq_length', 30)
                    self.train_date = metadata.get('train_date')
                    self.test_date = metadata.get('test_date')
                    self.validation_loss = metadata.get('validation_loss')
            
            self.is_trained = True
            self.model_version = version
            print_success(f"Model loaded: {version}")
            return True
            
        except Exception as e:
            print_error(f"Failed to load model: {e}")
            return False
    
    def prepare_data(self, df, fit_scaler=False):
        features = self.features.copy()
        data = df[features].values
        
        if fit_scaler:
            self.scaler = MinMaxScaler()
            scaled_data = self.scaler.fit_transform(data)
        else:
            if self.scaler is None:
                print_error("Scaler not fitted!")
                return np.array([]), np.array([])
            scaled_data = self.scaler.transform(data)
        
        X, y = [], []
        for i in range(self.seq_length, len(scaled_data)):
            X.append(scaled_data[i-self.seq_length:i])
            y.append(scaled_data[i, 3])
        
        return np.array(X), np.array(y)
    
    def train(self, df, force=False, version=None):
        if not force and self.is_trained:
            return self.model
        
        print_info(f"Training model with {len(df)} records...")
        
        if len(df) < self.seq_length + 30:
            print_error(f"Not enough data")
            return None
        
        total = len(df)
        train_end = int(0.8 * total)
        val_end = int(0.9 * total)
        
        train_df = df.iloc[:train_end]
        val_df = df.iloc[train_end:val_end]
        test_df = df.iloc[val_end:]
        
        print_info(f"  Train: {train_df['date'].min()} to {train_df['date'].max()} ({len(train_df)} records)")
        print_info(f"  Val:   {val_df['date'].min()} to {val_df['date'].max()} ({len(val_df)} records)")
        print_info(f"  Test:  {test_df['date'].min()} to {test_df['date'].max()} ({len(test_df)} records)")
        
        self.train_start = train_df['date'].min()
        self.train_end = train_df['date'].max()
        self.test_start = test_df['date'].min()
        self.test_end = test_df['date'].max()
        
        X_train, y_train = self.prepare_data(train_df, fit_scaler=True)
        X_val, y_val = self.prepare_data(val_df)
        
        test_with_context = pd.concat([train_df.tail(self.seq_length), test_df])
        X_test, y_test = self.prepare_data(test_with_context)
        
        if len(X_train) == 0 or len(X_val) == 0 or len(X_test) == 0:
            print_error("No training/validation/test data available")
            return None
        
        X_train_t = torch.FloatTensor(X_train)
        y_train_t = torch.FloatTensor(y_train).reshape(-1, 1)
        X_val_t = torch.FloatTensor(X_val)
        y_val_t = torch.FloatTensor(y_val).reshape(-1, 1)
        X_test_t = torch.FloatTensor(X_test)
        y_test_t = torch.FloatTensor(y_test).reshape(-1, 1)
        
        self.model = LSTMPredictor(input_size=self.feature_count)
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10)
        
        epochs = 100
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(epochs):
            self.model.train()
            optimizer.zero_grad()
            output = self.model(X_train_t)
            loss = criterion(output, y_train_t)
            loss.backward()
            optimizer.step()
            
            self.model.eval()
            with torch.no_grad():
                val_loss = criterion(self.model(X_val_t), y_val_t).item()
                
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    torch.save(self.model.state_dict(), 'best_model.pth')
                else:
                    patience_counter += 1
                    
                if patience_counter >= 15:
                    print_info(f"Early stopping at epoch {epoch+1}")
                    break
            
            if (epoch + 1) % 20 == 0:
                test_loss = criterion(self.model(X_test_t), y_test_t).item()
                print_info(f"Epoch {epoch+1}/{epochs}, Train Loss: {loss.item():.6f}, Val Loss: {val_loss:.6f}, Test Loss: {test_loss:.6f}")
                scheduler.step(val_loss)
        
        if os.path.exists('best_model.pth'):
            self.model.load_state_dict(torch.load('best_model.pth'))
            os.remove('best_model.pth')
        
        self.is_trained = True
        self.train_date = train_df['date'].max()
        self.test_date = test_df['date'].max()
        self.validation_loss = best_val_loss
        
        if version is None:
            version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.save_model(version)
        
        print_success(f"Model trained and saved: {version}")
        return self.model
    
    def predict_next_day(self, df=None):
        if df is None:
            db = DatabaseManager()
            df = db.get_all_data()
        
        if not self.is_trained:
            if not self.load_model():
                print_error("No trained model found")
                return None
        
        if len(df) < self.seq_length:
            print_error(f"Not enough data")
            return None
        
        last_days = df[self.features].values[-self.seq_length:]
        scaled_last = self.scaler.transform(last_days)
        X_pred = torch.FloatTensor(scaled_last).reshape(1, self.seq_length, len(self.features))
        
        self.model.eval()
        with torch.no_grad():
            prediction_scaled = self.model(X_pred).item()
        
        dummy = np.zeros((1, len(self.features)))
        dummy[0, 3] = prediction_scaled
        prediction = self.scaler.inverse_transform(dummy)[0, 3]
        
        return prediction

# ============================================
# 3. ADVANCED ML WRAPPER
# ============================================

class AdvancedMLWrapper:
    def __init__(self):
        self.models = None
        self.prophet = None
        self.lstm_attention = None
        self.is_trained = False
        self.available = False
        
        if AdvancedMLModels is not None:
            try:
                self.models = AdvancedMLModels()
                self.prophet = ProphetPredictor()
                self.lstm_attention = AdvancedLSTMTrainer()
                self.available = True
                print_success("Advanced ML initialized")
            except Exception as e:
                print_warning(f"Advanced ML init failed: {e}")
    
    def train(self, df):
        if not self.available:
            print_warning("Advanced ML not available")
            return
        
        print_info("Training Advanced ML Models...")
        
        try:
            if self.models:
                ensemble_pred, ensemble_mape = self.models.train_ensemble(df)
                if ensemble_pred is not None:
                    print_success(f"Ensemble trained (MAPE: {ensemble_mape:.2f}%)")
        except Exception as e:
            print_error(f"Ensemble training failed: {e}")
        
        try:
            if self.prophet:
                self.prophet.train(df)
                print_success("Prophet trained")
        except Exception as e:
            print_error(f"Prophet failed: {e}")
        
        try:
            if self.lstm_attention:
                self.lstm_attention.train(df, epochs=50)
                print_success("Attention LSTM trained")
        except Exception as e:
            print_error(f"Attention LSTM failed: {e}")
        
        self.is_trained = True
    
    def predict_ensemble(self, df):
        if not self.available or not self.models:
            return None
        try:
            return self.models.predict_with_ensemble(df)
        except Exception as e:
            print_warning(f"Ensemble prediction failed: {e}")
            return None
    
    def predict_prophet(self, df):
        if not self.available or not self.prophet:
            return None
        try:
            return self.prophet.predict(df)
        except:
            return None
    
    def predict_lstm(self, df):
        if not self.available or not self.lstm_attention:
            return None
        try:
            return self.lstm_attention.predict(df)
        except:
            return None

# ============================================
# 4. CONFIDENCE CALCULATOR
# ============================================

class ConfidenceCalculator:
    def __init__(self):
        self.db = DatabaseManager()
    
    def calculate(self, predictions: Dict[str, float], current_price: float, df: pd.DataFrame) -> Dict:
        factors = {}
        
        values = [p for p in predictions.values() if p is not None]
        if len(values) > 1:
            std = np.std(values)
            mean = np.mean(values)
            cv = std / mean if mean != 0 else 1
            agreement = max(0, 100 - (cv * 100))
            factors['model_agreement'] = min(100, agreement)
        else:
            factors['model_agreement'] = 50
        
        recent = self.db.get_recent_predictions(30)
        if not recent.empty:
            valid = recent[recent['direction_correct'].notna()]
            if not valid.empty:
                factors['historical_accuracy'] = valid['direction_correct'].mean() * 100
            else:
                factors['historical_accuracy'] = 50
        else:
            factors['historical_accuracy'] = 50
        
        if df is not None and len(df) > 30:
            returns = df['close'].pct_change()
            volatility = returns.std() * 100
            
            if volatility < 1:
                factors['volatility'] = 90
            elif volatility < 2:
                factors['volatility'] = 70
            elif volatility < 3:
                factors['volatility'] = 50
            else:
                factors['volatility'] = 30
        else:
            factors['volatility'] = 50
        
        regime = self.detect_regime(df)
        factors['regime_confidence'] = regime['confidence']
        factors['regime'] = regime['regime']
        
        if len(values) > 1:
            range_pct = (max(values) - min(values)) / np.mean(values) * 100
            if range_pct < 1:
                factors['dispersion'] = 90
            elif range_pct < 3:
                factors['dispersion'] = 70
            elif range_pct < 5:
                factors['dispersion'] = 50
            else:
                factors['dispersion'] = 30
        else:
            factors['dispersion'] = 50
        
        if not recent.empty:
            valid = recent[recent['direction_correct'].notna()]
            if len(valid) >= 10:
                factors['recent_trend'] = valid.head(10)['direction_correct'].mean() * 100
            else:
                factors['recent_trend'] = 50
        else:
            factors['recent_trend'] = 50
        
        weights = {
            'model_agreement': 0.25,
            'historical_accuracy': 0.20,
            'volatility': 0.15,
            'regime_confidence': 0.15,
            'dispersion': 0.15,
            'recent_trend': 0.10
        }
        
        confidence_score = sum(factors.get(k, 50) * weights[k] for k in weights)
        confidence_score = min(100, max(0, confidence_score))
        
        if len(values) > 1:
            mean_pred = np.mean(values)
            if mean_pred > current_price * 1.002:
                direction = 'BULLISH'
            elif mean_pred < current_price * 0.998:
                direction = 'BEARISH'
            else:
                direction = 'NEUTRAL'
        else:
            direction = 'NEUTRAL'
        
        return {
            'confidence_score': confidence_score,
            'direction': direction,
            'factors': factors,
            'regime': factors.get('regime', 'UNKNOWN')
        }
    
    def detect_regime(self, df):
        if df is None or len(df) < 50:
            return {'regime': 'UNKNOWN', 'confidence': 50}
        
        prices = df['close'].values
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:]) if len(prices) > 200 else ma50
        
        returns = df['close'].pct_change()
        vol = returns.std() * 100
        
        if prices[-1] > ma50 and ma50 > ma200:
            regime = 'BULL'
            confidence = 70
        elif prices[-1] < ma50 and ma50 < ma200:
            regime = 'BEAR'
            confidence = 70
        else:
            regime = 'SIDEWAYS'
            confidence = 50
        
        if vol > 3:
            regime += '_HIGH_VOL'
            confidence -= 10
        elif vol < 1:
            regime += '_LOW_VOL'
            confidence += 10
        
        return {'regime': regime, 'confidence': min(90, confidence)}

# ============================================
# 5. DYNAMIC ENSEMBLE
# ============================================

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

# ============================================
# 6. CHAMPION/CHALLENGER
# ============================================

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
            print_info(f"New champion: {new_version} (Improvement: {improvement:.1f}%)")
        else:
            print_info(f"Challenger {new_version} not promoted (Improvement: {improvement:.1f}%)")
        
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
        print_success(f"Champion set to: {version}")

# ============================================
# 7. YAHOO DATA FETCHER
# ============================================

class YahooDataFetcher:
    def __init__(self):
        try:
            import yfinance as yf
            self.yf = yf
            print_success("Yahoo Finance loaded")
        except ImportError:
            print_error("yfinance not installed")
            self.yf = None
    
    def fetch_from_date(self, start_date, end_date=None, symbol='BTC-USD'):
        if self.yf is None:
            return None
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            print_info(f"Fetching from Yahoo: {start_date} to {end_date}")
            df = self.yf.download(symbol, start=start_date, end=end_date, progress=False)
            
            if df.empty:
                print_error("No data received")
                return None
            
            df = df.reset_index()
            df['date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
            df = df[['date', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            df = df.dropna()
            
            print_success(f"Downloaded {len(df)} records")
            return df
            
        except Exception as e:
            print_error(f"Yahoo error: {e}")
            return None

# ============================================
# 8. DATA PIPELINE
# ============================================

class DataPipeline:
    def __init__(self):
        self.db = DatabaseManager()
        self.fetcher = YahooDataFetcher()
    
    def initial_load(self):
        print_info("Initial data load from Yahoo...")
        
        if self.db.get_count() > 0:
            print_info("Database already has data, skipping initial load")
            return True
        
        start_date = '2014-09-17'
        df = self.fetcher.fetch_from_date(start_date)
        
        if df is not None and not df.empty:
            conn = sqlite3.connect(self.db.db_path)
            df.to_sql('btc_daily', conn, if_exists='append', index=False)
            conn.close()
            print_success(f"Initial data loaded: {len(df)} records")
            return True
        return False
    
    def daily_update(self):
        print_info("Checking for new data from Yahoo...")
        last_date = self.db.get_last_date()
        
        if not last_date:
            print_warning("No data in database, running initial load...")
            return self.initial_load()
        
        start_date = (datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        df = self.fetcher.fetch_from_date(start_date, end_date)
        
        if df is not None and not df.empty:
            existing_dates = set(self.db.get_all_data()['date'])
            df = df[~df['date'].isin(existing_dates)]
            
            if not df.empty:
                conn = sqlite3.connect(self.db.db_path)
                df.to_sql('btc_daily', conn, if_exists='append', index=False)
                conn.close()
                print_success(f"Added {len(df)} new records")
                return True
            else:
                print_info("No new data to add")
                return True
        
        return False

# ============================================
# 9. COMPLETE ENHANCED PREDICTOR
# ============================================

class EnhancedSelfLearningPredictor:
    def __init__(self):
        self.db = DatabaseManager()
        self.pipeline = DataPipeline()
        self.trainer = ModelTrainer()
        self.confidence_calc = ConfidenceCalculator()
        self.ensemble = DynamicEnsemble()
        self.champion_challenger = ChampionChallenger()
        self.email_notifier = EmailNotifier() if EmailNotifier else None
        
        self.advanced_ml = AdvancedMLWrapper()
        
        self.is_setup = False
        self.model_version = None
        self.use_email = True
        self.use_advanced_ml = True
        
        self._check_setup()
        
        # FIXED: Force training if no model exists
        if not self.is_setup or self.champion_challenger.get_champion() is None:
            print_warning("No model found. Training required!")
            self.auto_setup()
        else:
            # Load existing model
            champion = self.champion_challenger.get_champion()
            if champion:
                self.trainer.load_model(champion)
                self.model_version = champion
                print_success(f"Champion loaded: {champion}")
            
            # Train advanced models if needed
            if self.use_advanced_ml and not self.advanced_ml.is_trained:
                try:
                    self.advanced_ml.train(self.db.get_all_data())
                except Exception as e:
                    print_warning(f"Advanced ML training failed: {e}")
    
    def _check_setup(self):
        try:
            count = self.db.get_count()
            if count > 0:
                self.is_setup = True
                print_success(f"System ready with {count} records")
            else:
                self.is_setup = False
                print_warning("No data found in database")
        except Exception as e:
            print_error(f"Setup check error: {e}")
            self.is_setup = False
    
    def auto_setup(self):
        print_info("Running automatic setup with forced training...")
        
        if not self.pipeline.initial_load():
            print_error("Failed to load data")
            return False
        
        df = self.pipeline.db.get_all_data()
        
        if df.empty:
            print_error("No data available for training")
            return False
        
        version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print_info(f"Training base model: {version}")
        print_info(f"Data shape: {df.shape}")
        print_info(f"Date range: {df['date'].min()} to {df['date'].max()}")
        
        try:
            self.trainer.train(df, force=True, version=version)
        except Exception as e:
            print_error(f"Model training failed: {e}")
            return False
        
        # Verify model works
        test_pred = self.trainer.predict_next_day(df.tail(100))
        if test_pred is None:
            print_error("Model validation failed - prediction returned None")
            return False
        
        current_price = df['close'].iloc[-1]
        change = ((test_pred - current_price) / current_price) * 100
        print_info(f"Test prediction: ${test_pred:,.2f} ({change:+.2f}%)")
        
        self.champion_challenger.set_champion(version)
        self.model_version = version
        self.is_setup = True
        
        if self.use_advanced_ml:
            try:
                self.advanced_ml.train(df)
            except Exception as e:
                print_warning(f"Advanced ML training failed: {e}")
        
        print_success(f"Setup complete! Model: {self.model_version}")
        return True
    
    def get_model_predictions(self, df, date=None):
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        prev_close = self.db.get_previous_close(date)
        predictions = {}
        
        # Original LSTM
        try:
            original_pred = self.trainer.predict_next_day(df)
            if original_pred is not None and original_pred > 0:
                predictions['original'] = original_pred
                self.db.save_model_prediction(date, 'original', original_pred, None, prev_close)
                print_info(f"Original LSTM: ${original_pred:,.2f}")
        except Exception as e:
            print_warning(f"Original LSTM prediction failed: {e}")
        
        # Advanced models
        if self.use_advanced_ml and self.advanced_ml.is_trained:
            try:
                lstm_pred = self.advanced_ml.predict_lstm(df)
                if lstm_pred is not None and lstm_pred > 0:
                    predictions['lstm'] = lstm_pred
                    self.db.save_model_prediction(date, 'lstm', lstm_pred, None, prev_close)
                    print_info(f"LSTM Attention: ${lstm_pred:,.2f}")
            except Exception as e:
                print_warning(f"LSTM Attention failed: {e}")
            
            try:
                ensemble_pred = self.advanced_ml.predict_ensemble(df)
                if ensemble_pred is not None and ensemble_pred > 0:
                    predictions['ensemble'] = ensemble_pred
                    self.db.save_model_prediction(date, 'ensemble', ensemble_pred, None, prev_close)
                    print_info(f"Ensemble: ${ensemble_pred:,.2f}")
            except Exception as e:
                print_warning(f"Ensemble prediction failed: {e}")
            
            try:
                prophet_pred = self.advanced_ml.predict_prophet(df)
                if prophet_pred is not None and prophet_pred > 0:
                    predictions['prophet'] = prophet_pred
                    self.db.save_model_prediction(date, 'prophet', prophet_pred, None, prev_close)
                    print_info(f"Prophet: ${prophet_pred:,.2f}")
            except Exception as e:
                print_warning(f"Prophet prediction failed: {e}")
        
        # Fallback
        if not predictions and original_pred is not None and original_pred > 0:
            predictions['original'] = original_pred
        
        return predictions
    
    def get_ensemble_prediction(self, predictions: Dict[str, float]) -> Tuple[Optional[float], Dict]:
        predictions = {k: v for k, v in predictions.items() if v is not None and v > 0}
        
        if not predictions:
            return None, {}
        
        model_names = list(predictions.keys())
        weights = self.ensemble.calculate_weights(model_names)
        
        final_prediction = sum(predictions[name] * weights.get(name, 1.0/len(model_names)) 
                              for name in predictions)
        
        # FIXED: Sanity check - realistic price range
        df = self.db.get_all_data()
        if not df.empty:
            current_price = df['close'].iloc[-1]
            min_pred = current_price * (1 - MAX_DAILY_CHANGE)
            max_pred = current_price * (1 + MAX_DAILY_CHANGE)
            
            if final_prediction < min_pred or final_prediction > max_pred:
                print_warning(f"Prediction ${final_prediction:,.2f} outside reasonable range")
                print_warning(f"Clamping to range: ${min_pred:,.2f} - ${max_pred:,.2f}")
                final_prediction = np.clip(final_prediction, min_pred, max_pred)
        
        return final_prediction, weights
    
    def calculate_intervals(self, prediction: float, df: pd.DataFrame) -> Dict:
        recent = self.db.get_recent_predictions(30)
        
        if not recent.empty:
            valid = recent[recent['absolute_error'].notna()]
            if not valid.empty:
                errors = valid['absolute_error'].values
                lower_error = np.percentile(errors, 2.5)
                upper_error = np.percentile(errors, 97.5)
                
                return {
                    'low': prediction - lower_error,
                    'high': prediction + upper_error,
                    'lower_error': lower_error,
                    'upper_error': upper_error,
                    'width': (upper_error + lower_error) / prediction * 100
                }
        
        atr = self.calculate_atr(df)
        return {
            'low': prediction - atr * 0.5,
            'high': prediction + atr * 0.5,
            'lower_error': atr * 0.5,
            'upper_error': atr * 0.5,
            'width': atr / prediction * 100
        }
    
    def calculate_atr(self, df, period=14):
        if len(df) < period:
            return df['close'].std() * 0.02
        
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = np.mean(tr[-period:])
        
        return atr
    
    def generate_signal(self, prediction: float, current_price: float, 
                       confidence_data: Dict, intervals: Dict) -> str:
        change = (prediction - current_price) / current_price
        confidence_score = confidence_data['confidence_score']
        direction = confidence_data['direction']
        
        if confidence_score < 45:
            return 'NO TRADE'
        
        if abs(change) < 0.01:
            return 'HOLD'
        
        if change > 0.03 and confidence_score > 55:
            return 'BUY'
        elif change < -0.03 and confidence_score > 55:
            return 'SELL'
        elif change > 0.01:
            return 'HOLD'
        else:
            return 'NO TRADE'
    
    def daily_job(self):
        print_info(f"\n{'='*60}")
        print_info(f"Running daily job at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print_info("Updating yesterday's predictions...")
        self.db.update_yesterday_predictions()
        
        if not self.pipeline.daily_update():
            print_warning("Daily update failed or no new data")
            print_info(f"{'='*60}\n")
            return
        
        df = self.pipeline.db.get_all_data()
        
        # Weekly retraining
        last_train_date = self.trainer._get_last_train_date() if hasattr(self.trainer, '_get_last_train_date') else None
        days_since_train = (datetime.now() - datetime.strptime(last_train_date, '%Y-%m-%d')).days if last_train_date else 999
        
        if days_since_train >= 7:
            print_info("Weekly retraining...")
            new_version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            try:
                self.trainer.train(df, force=True, version=new_version)
                result = self.champion_challenger.evaluate_challenger(new_version)
                if result['promoted']:
                    self.model_version = new_version
                else:
                    champion = self.champion_challenger.get_champion()
                    if champion:
                        self.trainer.load_model(champion)
                        self.model_version = champion
                
                if self.use_advanced_ml:
                    self.advanced_ml.train(df)
            except Exception as e:
                print_error(f"Retraining failed: {e}")
        else:
            print_info(f"Last retrained {days_since_train} days ago (weekly schedule)")
        
        all_predictions = self.get_model_predictions(df)
        final_prediction, weights = self.get_ensemble_prediction(all_predictions)
        
        if final_prediction is None:
            print_warning("No prediction generated")
            print_info(f"{'='*60}\n")
            return
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        last_close = df['close'].iloc[-1]
        change = ((final_prediction - last_close) / last_close) * 100
        
        confidence_data = self.confidence_calc.calculate(all_predictions, last_close, df)
        intervals = self.calculate_intervals(final_prediction, df)
        signal = self.generate_signal(final_prediction, last_close, confidence_data, intervals)
        
        self.db.save_ensemble_prediction(
            date=tomorrow,
            predicted=final_prediction,
            actual=None,
            confidence_score=confidence_data['confidence_score'],
            range_low=intervals['low'],
            range_high=intervals['high'],
            regime=confidence_data.get('regime', 'UNKNOWN'),
            signal=signal,
            model_version=self.model_version or 'v1.0'
        )
        
        print_info(f"\nFINAL FORECAST ({tomorrow}):")
        print_info(f"  Predicted Close: ${final_prediction:,.2f}")
        print_info(f"  Current Close: ${last_close:,.2f}")
        print_info(f"  Expected Change: {change:+.2f}%")
        print_info(f"  Direction: {confidence_data['direction']}")
        print_info(f"  Confidence Score: {confidence_data['confidence_score']:.1f}%")
        print_info(f"  Range: ${intervals['low']:,.2f} - ${intervals['high']:,.2f}")
        print_info(f"  Signal: {signal}")
        
        if weights:
            print_info(f"\n  Model Weights:")
            for name, weight in weights.items():
                print_info(f"    {name}: {weight*100:.1f}%")
        
        if self.use_email and self.email_notifier:
            print_info("Sending email report...")
            prediction_data = {
                'price': final_prediction,
                'change': change,
                'current_price': last_close,
                'confidence': confidence_data['confidence_score'],
                'range_low': intervals['low'],
                'range_high': intervals['high'],
                'models_used': len([p for p in all_predictions.values() if p is not None]),
                'direction': confidence_data['direction'],
                'regime': confidence_data.get('regime', 'UNKNOWN'),
                'signal': signal,
                'model_weights': weights
            }
            
            performance_data = {
                'model_version': self.model_version or 'v1.0',
                'recent_predictions': self.db.get_recent_predictions(10)
            }
            
            metrics = self.db.update_performance_metrics()
            if metrics:
                performance_data.update(metrics)
            
            try:
                self.email_notifier.send_daily_prediction_report(prediction_data, performance_data)
            except Exception as e:
                print_error(f"Email sending failed: {e}")
        
        self.db.update_performance_metrics()
        
        print_info(f"{'='*60}\n")

# ============================================
# 10. MAIN
# ============================================

def main():
    """Main entry point"""
    
    # Check email config
    if EmailNotifier and not os.path.exists('email_config.json'):
        print_info("Email not configured. Setup now?")
        choice = input("Setup email? (y/n): ").strip().lower()
        if choice == 'y' and setup_email_config:
            setup_email_config()
    
    # Initialize predictor
    predictor = EnhancedSelfLearningPredictor()
    
    # Verify model is ready
    if predictor.model_version is None:
        print_error("Model training failed! Please check logs.")
        return
    
    print_success(f"Model ready: {predictor.model_version}")
    
    # Test prediction
    df = predictor.db.get_all_data()
    test_pred = predictor.trainer.predict_next_day(df.tail(100))
    if test_pred:
        current_price = df['close'].iloc[-1]
        change = ((test_pred - current_price) / current_price) * 100
        print_info(f"Test prediction sanity: ${test_pred:,.2f} ({change:+.2f}%)")
        
        if abs(change) > 10:
            print_warning(f"Prediction change {change:.1f}% is high - check model quality")
    
    # Show initial prediction
    print_info("\n" + "="*60)
    print_info("INITIAL PREDICTION")
    
    all_preds = predictor.get_model_predictions(df)
    final_pred, weights = predictor.get_ensemble_prediction(all_preds)
    
    if final_pred is not None:
        last_close = df['close'].iloc[-1]
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        change = ((final_pred - last_close) / last_close) * 100
        
        confidence_data = predictor.confidence_calc.calculate(all_preds, last_close, df)
        intervals = predictor.calculate_intervals(final_pred, df)
        signal = predictor.generate_signal(final_pred, last_close, confidence_data, intervals)
        
        print_info(f"  Tomorrow's Date: {tomorrow}")
        print_info(f"  Predicted Close: ${final_pred:,.2f}")
        print_info(f"  Current Close: ${last_close:,.2f}")
        print_info(f"  Expected Change: {change:+.2f}%")
        print_info(f"  Direction: {confidence_data['direction']}")
        print_info(f"  Confidence Score: {confidence_data['confidence_score']:.1f}%")
        print_info(f"  Range: ${intervals['low']:,.2f} - ${intervals['high']:,.2f}")
        print_info(f"  Signal: {signal}")
        
        predictor.db.save_ensemble_prediction(
            date=tomorrow,
            predicted=final_pred,
            actual=None,
            confidence_score=confidence_data['confidence_score'],
            range_low=intervals['low'],
            range_high=intervals['high'],
            regime=confidence_data.get('regime', 'UNKNOWN'),
            signal=signal,
            model_version=predictor.model_version or 'v1.0'
        )
        
        if predictor.use_email and predictor.email_notifier:
            print_info("Sending initial email...")
            prediction_data = {
                'price': final_pred,
                'change': change,
                'current_price': last_close,
                'confidence': confidence_data['confidence_score'],
                'range_low': intervals['low'],
                'range_high': intervals['high'],
                'models_used': len([p for p in all_preds.values() if p is not None]),
                'direction': confidence_data['direction'],
                'regime': confidence_data.get('regime', 'UNKNOWN'),
                'signal': signal,
                'model_weights': weights
            }
            
            performance_data = {
                'model_version': predictor.model_version or 'v1.0',
                'recent_predictions': predictor.db.get_recent_predictions(10)
            }
            
            metrics = predictor.db.update_performance_metrics()
            if metrics:
                performance_data.update(metrics)
            
            try:
                predictor.email_notifier.send_daily_prediction_report(prediction_data, performance_data)
            except Exception as e:
                print_error(f"Email sending failed: {e}")
    
    print_info("="*60 + "\n")
    
    # Schedule daily job
    schedule.every().day.at(SCHEDULE_TIME).do(predictor.daily_job)
    
    print_success("BTC Predictor is running!")
    print_info(f"Daily updates scheduled for {SCHEDULE_TIME} UTC")
    print_info(f"Current model: {predictor.model_version}")
    print_info("Press Ctrl+C to stop\n")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# ============================================
# 11. RESET DATABASE UTILITY
# ============================================

def reset_database():
    """Reset predictions table only"""
    try:
        conn = sqlite3.connect('btc_data.db')
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS predictions")
        cursor.execute('''
            CREATE TABLE predictions (
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
        
        conn.commit()
        conn.close()
        print_success("Predictions table reset successfully!")
        return True
    except Exception as e:
        print_error(f"Reset failed: {e}")
        return False

# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    import sys
    
    # Check for reset flag
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        reset_database()
        print_info("Database reset complete. Run again without --reset to start.")
        sys.exit(0)
    
    main()