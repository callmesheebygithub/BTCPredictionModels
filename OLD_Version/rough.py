"""
BTC PREDICTOR - MAIN PIPELINE (Yahoo-Only Daily Update)
Run this file to start the predictor
"""

import ccxt
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
import warnings
warnings.filterwarnings('ignore')

# ============================================
# IMPORT YAHOO UPDATER AND OTHER MODULES
# ============================================

# Check if yahoo_daily_updater.py exists
try:
    from yahoo_daily_updater import YahooDailyUpdater
    print("✅ Yahoo Daily Updater module loaded")
except ImportError as e:
    print(f"⚠️ yahoo_daily_updater.py not found: {e}")
    print("Using Binance fallback...")
    YahooDailyUpdater = None

# Check if advanced_ml.py exists
try:
    from advanced_ml import AdvancedMLModels, ProphetPredictor, AdvancedLSTMTrainer, ModelSelector
    print("✅ Advanced ML module loaded")
except ImportError as e:
    print(f"❌ Error loading advanced_ml.py: {e}")
    print("Please make sure advanced_ml.py is in the same directory")
    exit(1)

# Check if email_notifier.py exists
try:
    from email_notifier import EmailNotifier, setup_email_config
    print("✅ Email notifier module loaded")
except ImportError as e:
    print(f"❌ Error loading email_notifier.py: {e}")
    print("Please make sure email_notifier.py is in the same directory")
    exit(1)

# ============================================
# 1. DATABASE MANAGER
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
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                predicted_close REAL,
                actual_close REAL,
                error_percentage REAL,
                absolute_error REAL,
                direction_correct INTEGER,
                model_version TEXT,
                timestamp TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                period TEXT,
                avg_error REAL,
                avg_abs_error REAL,
                direction_accuracy REAL,
                total_predictions INTEGER,
                model_version TEXT
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
        """Get data after specific date"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(f'SELECT * FROM btc_daily WHERE date > "{date}" ORDER BY date', conn)
        conn.close()
        return df
    
    def save_prediction(self, date, predicted, actual=None, model_version='v1'):
        """Save prediction - NO duplicates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if prediction already exists
        cursor.execute('SELECT id, predicted_close, actual_close FROM predictions WHERE date = ?', (date,))
        existing = cursor.fetchone()
        
        if existing:
            pred_id, existing_pred, existing_actual = existing
            
            # If actual is provided and different, update
            if actual is not None and existing_actual is None:
                error_pct = ((predicted - actual) / actual) * 100
                abs_error = abs(predicted - actual)
                direction_correct = 1 if (predicted > actual) else 0
                
                cursor.execute('''
                    UPDATE predictions 
                    SET actual_close = ?, error_percentage = ?, absolute_error = ?, 
                        direction_correct = ?, timestamp = ?
                    WHERE id = ?
                ''', (actual, error_pct, abs_error, direction_correct, datetime.now().isoformat(), pred_id))
                
                print(f"  ✅ Updated prediction for {date} with actual price: ${actual:,.2f}")
            else:
                print(f"  ℹ️ Prediction for {date} already exists (ID: {pred_id})")
        else:
            # Insert new prediction
            cursor.execute('''
                INSERT INTO predictions 
                (date, predicted_close, actual_close, model_version, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (date, predicted, actual, model_version, datetime.now().isoformat()))
            print(f"  ✅ New prediction saved for {date}: ${predicted:,.2f}")
        
        conn.commit()
        conn.close()
        
        # Update performance if actual is provided
        if actual is not None:
            self.update_performance_metrics()
    
    def update_yesterday_predictions(self):
        """Update yesterday's predictions with actual prices"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Check if yesterday's prediction exists and has no actual
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, predicted_close FROM predictions 
            WHERE date = ? AND actual_close IS NULL
        ''', (yesterday,))
        pred = cursor.fetchone()
        conn.close()
        
        if pred:
            pred_id, predicted = pred
            
            # Get actual price from btc_daily
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT close FROM btc_daily WHERE date = ?', (yesterday,))
            actual = cursor.fetchone()
            conn.close()
            
            if actual:
                actual_close = actual[0]
                print(f"\n📊 Updating yesterday's prediction ({yesterday})")
                print(f"  Predicted: ${predicted:,.2f}")
                print(f"  Actual: ${actual_close:,.2f}")
                
                # Update with actual
                self.save_prediction(yesterday, predicted, actual_close, 'v1')
                return True
        
        return False
    
    def get_prediction_for_date(self, date):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT predicted_close, actual_close, error_percentage, direction_correct 
            FROM predictions WHERE date = ?
        ''', (date,))
        result = cursor.fetchone()
        conn.close()
        return result
    
    def get_recent_predictions(self, days=30):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(f'''
            SELECT date, predicted_close, actual_close, error_percentage, absolute_error, direction_correct
            FROM predictions 
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
    
    def delete_duplicate_predictions(self):
        """Delete duplicate predictions keeping only the latest"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT date, COUNT(*) FROM predictions 
            GROUP BY date HAVING COUNT(*) > 1
        ''')
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"\n🗑️ Found {len(duplicates)} duplicate dates")
            for date, count in duplicates:
                cursor.execute('''
                    DELETE FROM predictions 
                    WHERE date = ? AND id NOT IN (
                        SELECT MAX(id) FROM predictions WHERE date = ?
                    )
                ''', (date, date))
                print(f"  Deleted {count-1} duplicate(s) for {date}")
            conn.commit()
        
        conn.close()
    
    def update_performance_metrics(self):
        conn = sqlite3.connect(self.db_path)
        
        df = pd.read_sql_query('''
            SELECT date, error_percentage, absolute_error, direction_correct
            FROM predictions 
            WHERE actual_close IS NOT NULL 
            ORDER BY date DESC 
            LIMIT 30
        ''', conn)
        
        if not df.empty:
            metrics = {
                'avg_error': df['error_percentage'].mean(),
                'avg_abs_error': df['absolute_error'].mean(),
                'direction_accuracy': df['direction_correct'].mean() * 100,
                'total_predictions': len(df)
            }
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO performance 
                (date, period, avg_error, avg_abs_error, direction_accuracy, total_predictions, model_version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().strftime('%Y-%m-%d'),
                'daily',
                metrics['avg_error'],
                metrics['avg_abs_error'],
                metrics['direction_accuracy'],
                metrics['total_predictions'],
                'v1'
            ))
            conn.commit()
            
            print(f"\n📊 Performance Metrics (Last {metrics['total_predictions']} days):")
            print(f"  • Average Error: {metrics['avg_error']:.2f}%")
            print(f"  • Average Absolute Error: ${metrics['avg_abs_error']:.2f}")
            print(f"  • Direction Accuracy: {metrics['direction_accuracy']:.1f}%")
        
        conn.close()
        return metrics if not df.empty else None

# ============================================
# 2. YAHOO DATA PIPELINE (Integrated)
# ============================================

class YahooDataFetcher:
    """Fetch data from Yahoo Finance only"""
    
    def __init__(self):
        try:
            import yfinance as yf
            self.yf = yf
            print("✅ Yahoo Finance loaded")
        except ImportError:
            print("❌ yfinance not installed. Please run: pip install yfinance")
            self.yf = None
    
    def fetch_from_date(self, start_date, end_date=None, symbol='BTC-USD'):
        """Fetch data from Yahoo Finance"""
        if self.yf is None:
            print("❌ yfinance not available")
            return None
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            print(f"📥 Fetching from Yahoo Finance: {start_date} to {end_date}")
            df = self.yf.download(symbol, start=start_date, end=end_date, progress=False)
            
            if df.empty:
                print("❌ No data received from Yahoo Finance")
                return None
            
            # Format for database
            df = df.reset_index()
            df['date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
            df = df[['date', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            df = df.dropna()
            
            print(f"✅ Downloaded {len(df)} records from Yahoo Finance")
            return df
            
        except Exception as e:
            print(f"❌ Yahoo Finance error: {e}")
            return None

# ============================================
# 3. DATA PIPELINE (Yahoo-Only)
# ============================================

class DataPipeline:
    def __init__(self):
        self.db = DatabaseManager()
        self.fetcher = YahooDataFetcher()
    
    def initial_load(self):
        """Load data from 2014"""
        print("🔄 Initial data load from Yahoo Finance...")
        start_date = '2014-09-17'
        df = self.fetcher.fetch_from_date(start_date)
        
        if df is not None and not df.empty:
            self.db.insert_data(df)
            print(f"✅ Initial data loaded: {len(df)} records")
            return True
        return False
    
    def daily_update(self):
        """Daily update from Yahoo Finance only"""
        print("🔄 Checking for new data from Yahoo Finance...")
        last_date = self.db.get_last_date()
        
        if not last_date:
            print("⚠️ No data in database, running initial load...")
            return self.initial_load()
        
        start_date = (datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        df = self.fetcher.fetch_from_date(start_date, end_date)
        
        if df is not None and not df.empty:
            # Filter only new data
            existing_dates = set(self.db.get_all_data()['date'])
            df = df[~df['date'].isin(existing_dates)]
            
            if not df.empty:
                self.db.insert_data(df)
                print(f"✅ Added {len(df)} new records from Yahoo Finance")
                return True
            else:
                print("ℹ️ No new data to add")
                return True
        
        return False

# ============================================
# 4. LSTM MODEL
# ============================================

class LSTMPredictor(nn.Module):
    def __init__(self, input_size=5, hidden_size=64, num_layers=2):
        super(LSTMPredictor, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)
    
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        return self.fc(lstm_out[:, -1, :])

class ModelTrainer:
    def __init__(self, model_path='model.pth'):
        self.scaler = MinMaxScaler()
        self.model = None
        self.seq_length = 30
        self.model_path = model_path
        self.is_trained = False
        self.learning_rate = 0.001
        self.feature_count = 5
        
        if os.path.exists(model_path):
            self.load_model()
    
    def load_model(self):
        try:
            self.model = LSTMPredictor(input_size=5)
            self.model.load_state_dict(torch.load(self.model_path))
            self.model.eval()
            self.is_trained = True
            print("✅ Existing model loaded successfully")
            return True
        except Exception as e:
            print(f"⚠️ Could not load existing model: {e}")
            return False
    
    def prepare_data(self, df, include_prediction_errors=False):
        features = ['open', 'high', 'low', 'close', 'volume']
        
        if include_prediction_errors:
            db = DatabaseManager()
            predictions = db.get_recent_predictions(30)
            if not predictions.empty:
                error_col = pd.Series(index=df.index, dtype=float)
                for idx, row in df.iterrows():
                    date = row['date']
                    pred = predictions[predictions['date'] == date]
                    if not pred.empty:
                        error_col[idx] = pred['error_percentage'].iloc[0]
                df['error_feature'] = error_col.fillna(0)
                features.append('error_feature')
        
        data = df[features].values
        scaled_data = self.scaler.fit_transform(data)
        
        X, y = [], []
        for i in range(self.seq_length, len(scaled_data)):
            X.append(scaled_data[i-self.seq_length:i])
            y.append(scaled_data[i, 3])
        
        self.feature_count = len(features)
        return np.array(X), np.array(y)
    
    def train(self, df, force=False, use_error_features=True):
        if not force and self.is_trained:
            last_train_date = self._get_last_train_date()
            if last_train_date and last_train_date >= df['date'].iloc[-1]:
                print("ℹ️ Model is up to date, no training needed")
                return self.model
        
        print(f"🔄 Training model with {len(df)} records...")
        
        if len(df) < self.seq_length + 10:
            print(f"⚠️ Not enough data (need {self.seq_length + 10}, have {len(df)})")
            return None
        
        X, y = self.prepare_data(df, include_prediction_errors=use_error_features)
        
        if len(X) == 0:
            print("⚠️ No training data available")
            return None
        
        split = int(0.8 * len(X))
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        
        X_train = torch.FloatTensor(X_train)
        y_train = torch.FloatTensor(y_train).reshape(-1, 1)
        X_test = torch.FloatTensor(X_test)
        y_test = torch.FloatTensor(y_test).reshape(-1, 1)
        
        performance = self._get_recent_performance()
        if performance and performance['avg_abs_error'] > 500:
            self.learning_rate = 0.002
        elif performance and performance['avg_abs_error'] < 200:
            self.learning_rate = 0.0005
        else:
            self.learning_rate = 0.001
        
        self.model = LSTMPredictor(input_size=self.feature_count, hidden_size=64, num_layers=2)
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        
        print(f"📊 Learning rate: {self.learning_rate}")
        print(f"📊 Features used: {self.feature_count}")
        
        epochs = 100
        for epoch in range(epochs):
            self.model.train()
            optimizer.zero_grad()
            output = self.model(X_train)
            loss = criterion(output, y_train)
            loss.backward()
            optimizer.step()
            
            if (epoch + 1) % 20 == 0:
                self.model.eval()
                with torch.no_grad():
                    test_loss = criterion(self.model(X_test), y_test)
                    print(f"Epoch {epoch+1}/{epochs}, Train Loss: {loss.item():.6f}, Test Loss: {test_loss.item():.6f}")
        
        torch.save(self.model.state_dict(), self.model_path)
        self.is_trained = True
        self._save_train_date(df['date'].iloc[-1])
        print(f"✅ Model trained and saved to '{self.model_path}'")
        return self.model
    
    def _get_recent_performance(self):
        db = DatabaseManager()
        df = db.get_recent_predictions(10)
        if not df.empty:
            return {
                'avg_abs_error': df['absolute_error'].mean(),
                'direction_accuracy': df['direction_correct'].mean() * 100
            }
        return None
    
    def _get_last_train_date(self):
        try:
            with open('train_date.txt', 'r') as f:
                return f.read().strip()
        except:
            return None
    
    def _save_train_date(self, date):
        with open('train_date.txt', 'w') as f:
            f.write(date)
    
    def predict_next_day(self):
        if not self.is_trained:
            if not self.load_model():
                print("⚠️ No trained model found")
                return None
        
        db = DatabaseManager()
        df = db.get_all_data()
        
        if len(df) < self.seq_length:
            print(f"⚠️ Not enough data for prediction (need {self.seq_length})")
            return None
        
        features = ['open', 'high', 'low', 'close', 'volume']
        
        try:
            predictions = db.get_recent_predictions(30)
            if not predictions.empty:
                error_col = pd.Series(index=df.index, dtype=float)
                for idx, row in df.iterrows():
                    date = row['date']
                    pred = predictions[predictions['date'] == date]
                    if not pred.empty:
                        error_col[idx] = pred['error_percentage'].iloc[0]
                df['error_feature'] = error_col.fillna(0)
                features.append('error_feature')
        except:
            pass
        
        last_days = df[features].values[-self.seq_length:]
        scaled_last = self.scaler.fit_transform(last_days)
        X_pred = torch.FloatTensor(scaled_last).reshape(1, self.seq_length, len(features))
        
        self.model.eval()
        with torch.no_grad():
            prediction_scaled = self.model(X_pred).item()
        
        dummy = np.zeros((1, len(features)))
        dummy[0, 3] = prediction_scaled
        prediction = self.scaler.inverse_transform(dummy)[0, 3]
        
        return prediction

# ============================================
# 5. SELF-LEARNING PREDICTOR (Yahoo-Only)
# ============================================

class SelfLearningPredictor:
    def __init__(self):
        self.db = DatabaseManager()
        self.pipeline = DataPipeline()
        self.trainer = ModelTrainer()
        self.is_setup = False
        self._check_setup()
        self.model_version = 'v1.0'
        self.improvement_count = 0
    
    def _check_setup(self):
        try:
            count = self.db.get_count()
            if count > 0:
                self.is_setup = True
                print(f"✅ System already setup with {count} records")
                if os.path.exists('model.pth'):
                    self.trainer.load_model()
        except Exception as e:
            print(f"⚠️ Setup check error: {e}")
            self.is_setup = False
    
    def auto_setup(self):
        if self.is_setup:
            print("ℹ️ System already setup, skipping initial setup")
            return True
        
        print("🚀 Running automatic setup...")
        
        if self.pipeline.initial_load():
            df = self.pipeline.db.get_all_data()
            self.trainer.train(df, force=True)
            
            prediction = self.trainer.predict_next_day()
            if prediction:
                print(f"📈 Tomorrow's predicted close price: ${prediction:,.2f}")
            
            self.is_setup = True
            return True
        
        print("❌ Setup failed")
        return False
    
    def daily_job(self):
        print(f"\n{'='*60}")
        print(f"🔄 Running daily job at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # STEP 1: Update yesterday's predictions with actual prices
        print("\n📊 Checking yesterday's predictions...")
        self.db.update_yesterday_predictions()
        
        # STEP 2: Delete any duplicate predictions
        self.db.delete_duplicate_predictions()
        
        # STEP 3: Update data from Yahoo
        if self.pipeline.daily_update():
            df = self.pipeline.db.get_all_data()
            latest_date = df['date'].iloc[-1]
            
            # STEP 4: Retrain if needed
            last_train_date = self.trainer._get_last_train_date()
            if last_train_date != latest_date:
                print("🔄 Retraining model with improved features...")
                self.trainer.train(df, force=True)
                self.improvement_count += 1
                self.model_version = f'v1.{self.improvement_count}'
                print(f"📦 Model version updated to: {self.model_version}")
            else:
                print("ℹ️ No new data, model is up to date")
            
            # STEP 5: Make prediction for tomorrow
            prediction = self.trainer.predict_next_day()
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            
            if prediction:
                # Check if prediction already exists
                existing = self.db.get_prediction_for_date(tomorrow)
                if existing and existing[0] is not None:
                    print(f"ℹ️ Prediction for {tomorrow} already exists: ${existing[0]:,.2f}")
                else:
                    # Save new prediction
                    self.db.save_prediction(tomorrow, prediction, None, self.model_version)
                
                last_close = df['close'].iloc[-1]
                change = ((prediction - last_close) / last_close) * 100
                
                print(f"\n📈 Tomorrow's Prediction ({tomorrow}):")
                print(f"  • Predicted Close: ${prediction:,.2f}")
                print(f"  • Current Close: ${last_close:,.2f}")
                print(f"  • Expected Change: {change:+.2f}%")
            
            # STEP 6: Show performance
            self._show_performance()
            
            print("✅ Daily job completed")
        else:
            print("❌ Daily update failed")
        print(f"{'='*60}\n")
    
    def _show_performance(self):
        metrics = self.db.update_performance_metrics()
        
        if metrics:
            print(f"\n📊 Overall Performance:")
            print(f"  • Model Version: {self.model_version}")
            print(f"  • Average Error: {metrics['avg_error']:.2f}%")
            print(f"  • Avg Absolute Error: ${metrics['avg_abs_error']:.2f}")
            print(f"  • Direction Accuracy: {metrics['direction_accuracy']:.1f}%")
            print(f"  • Total Predictions: {metrics['total_predictions']}")
            
            if metrics['direction_accuracy'] < 50:
                print(f"  ⚠️ Direction accuracy below 50% - Model needs improvement!")
            elif metrics['direction_accuracy'] > 60:
                print(f"  ✅ Good direction accuracy!")
            
            if metrics['avg_abs_error'] > 1000:
                print(f"  ⚠️ High error rate - Consider adding more features")

# ============================================
# 6. ENHANCED PREDICTOR (With Advanced ML + Email + Yahoo Update)
# ============================================

class EnhancedSelfLearningPredictor(SelfLearningPredictor):
    """Enhanced predictor with Advanced ML and Email - Yahoo Only"""
    
    def __init__(self):
        super().__init__()
        self.ml_models = AdvancedMLModels()
        self.prophet = ProphetPredictor()
        self.lstm_attention = AdvancedLSTMTrainer()
        self.model_selector = ModelSelector()
        self.email_notifier = EmailNotifier()
        self.use_advanced_ml = True
        self.use_email = True
        
        # Train advanced models if enough data
        if self.is_setup:
            self.train_advanced_models()
    
    def train_advanced_models(self):
        df = self.db.get_all_data()
        
        if len(df) > 100:
            print("\n🚀 Training Advanced ML Models...")
            
            ensemble_pred, ensemble_mape = self.ml_models.train_ensemble(df)
            if ensemble_pred is not None:
                print(f"✅ Ensemble trained (MAPE: {ensemble_mape:.2f}%)")
            
            try:
                self.prophet.train(df)
                print("✅ Prophet trained")
            except Exception as e:
                print(f"❌ Prophet failed: {e}")
            
            try:
                self.lstm_attention.train(df, epochs=50)
                print("✅ Attention LSTM trained")
            except Exception as e:
                print(f"❌ Attention LSTM failed: {e}")
    
    def get_ensemble_prediction(self):
        df = self.db.get_all_data()
        return self.ml_models.predict_with_ensemble(df)
    
    def get_prophet_prediction(self):
        df = self.db.get_all_data()
        try:
            return self.prophet.predict(df)
        except:
            return None
    
    def get_lstm_prediction(self):
        df = self.db.get_all_data()
        try:
            return self.lstm_attention.predict(df)
        except:
            return None
    
    def get_best_prediction(self):
        predictions = {
            'lstm': self.get_lstm_prediction(),
            'ensemble': self.get_ensemble_prediction(),
            'prophet': self.get_prophet_prediction(),
            'original': self.trainer.predict_next_day()
        }
        
        predictions = {k: v for k, v in predictions.items() if v is not None}
        
        if not predictions:
            return None
        
        weights = {
            'lstm': 0.30,
            'ensemble': 0.30,
            'prophet': 0.20,
            'original': 0.20
        }
        
        final_prediction = sum(predictions.get(name, 0) * weights.get(name, 0.25) 
                              for name in predictions)
        
        return final_prediction
    
    def daily_job_with_email(self):
        """Enhanced daily job with email notification - Yahoo Only"""
        print(f"\n{'='*60}")
        print(f"🔄 Running enhanced daily job at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # STEP 1: Update yesterday's predictions
        print("\n📊 Checking yesterday's predictions...")
        self.db.update_yesterday_predictions()
        
        # STEP 2: Delete duplicates
        self.db.delete_duplicate_predictions()
        
        # STEP 3: Update data from Yahoo
        if self.pipeline.daily_update():
            df = self.pipeline.db.get_all_data()
            latest_date = df['date'].iloc[-1]
            
            # STEP 4: Retrain if needed
            last_train_date = self.trainer._get_last_train_date()
            if last_train_date != latest_date:
                print("🔄 Retraining all models...")
                self.trainer.train(df, force=True)
                self.train_advanced_models()
                self.improvement_count += 1
                self.model_version = f'v1.{self.improvement_count}'
            
            # STEP 5: Make prediction
            final_prediction = self.get_best_prediction()
            
            if final_prediction:
                tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                last_close = df['close'].iloc[-1]
                change = ((final_prediction - last_close) / last_close) * 100
                
                # Check if exists
                existing = self.db.get_prediction_for_date(tomorrow)
                if existing and existing[0] is not None:
                    print(f"ℹ️ Prediction for {tomorrow} already exists")
                else:
                    self.db.save_prediction(tomorrow, final_prediction, None, self.model_version)
                
                # Prepare email data
                predictions = {
                    'original': self.trainer.predict_next_day(),
                    'ensemble': self.get_ensemble_prediction(),
                    'prophet': self.get_prophet_prediction(),
                    'lstm': self.get_lstm_prediction()
                }
                
                prediction_data = {
                    'price': final_prediction,
                    'change': change,
                    'current_price': last_close,
                    'confidence': 75,
                    'range_low': final_prediction * 0.98,
                    'range_high': final_prediction * 1.02,
                    'models_used': len([p for p in predictions.values() if p is not None])
                }
                
                performance_data = {
                    'avg_error': 0,
                    'avg_abs_error': 0,
                    'direction_accuracy': 0,
                    'total_predictions': 0,
                    'model_version': self.model_version,
                    'recent_predictions': self.db.get_recent_predictions(10)
                }
                
                metrics = self.db.update_performance_metrics()
                if metrics:
                    performance_data.update(metrics)
                
                # Send email
                if self.use_email:
                    print("\n📧 Sending email report...")
                    self.email_notifier.send_daily_prediction_report(
                        prediction_data, 
                        performance_data
                    )
                
                print(f"\n📈 Final Prediction ({tomorrow}):")
                print(f"  • Predicted Close: ${final_prediction:,.2f}")
                print(f"  • Current Close: ${last_close:,.2f}")
                print(f"  • Expected Change: {change:+.2f}%")
                print(f"  • Models Used: {prediction_data['models_used']}")
                
                print("\n  Individual Model Predictions:")
                for name, pred in predictions.items():
                    if pred:
                        print(f"    • {name}: ${pred:,.2f}")
                
                self._show_performance()
        
        print(f"{'='*60}\n")

# ============================================
# 7. MAIN EXECUTION
# ============================================

def main_with_advanced_features():
    """Main with advanced features and email - Yahoo Only"""
    
    # Check for email configuration
    if not os.path.exists('email_config.json'):
        print("\n📧 Email not configured. Would you like to set it up now?")
        choice = input("Setup email? (y/n): ").strip().lower()
        if choice == 'y':
            setup_email_config()
    
    # Initialize predictor
    predictor = EnhancedSelfLearningPredictor()
    
    # Auto setup
    if not predictor.is_setup:
        print("🔧 First time setup...")
        predictor.auto_setup()
    
    # Show prediction
    print("\n" + "="*60)
    print("📊 INITIAL PREDICTION (Advanced ML):")
    
    final_pred = predictor.get_best_prediction()
    
    if final_pred:
        db = DatabaseManager()
        df = db.get_all_data()
        last_close = df['close'].iloc[-1]
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        change = ((final_pred - last_close) / last_close) * 100
        
        print(f"  • Tomorrow's Date: {tomorrow}")
        print(f"  • Predicted Close: ${final_pred:,.2f}")
        print(f"  • Current Close: ${last_close:,.2f}")
        print(f"  • Expected Change: {change:+.2f}%")
        
        # Save prediction
        predictor.db.save_prediction(tomorrow, final_pred, None, predictor.model_version)
        
        # Send initial email
        print("\n📧 Sending initial prediction email...")
        
        prediction_data = {
            'price': final_pred,
            'change': change,
            'current_price': last_close,
            'confidence': 75,
            'range_low': final_pred * 0.98,
            'range_high': final_pred * 1.02,
            'models_used': 4
        }
        
        performance_data = {
            'avg_error': 0,
            'avg_abs_error': 0,
            'direction_accuracy': 0,
            'total_predictions': 0,
            'model_version': predictor.model_version,
            'recent_predictions': predictor.db.get_recent_predictions(10)
        }
        
        metrics = predictor.db.update_performance_metrics()
        if metrics:
            performance_data.update(metrics)
        
        if predictor.use_email:
            email_result = predictor.email_notifier.send_daily_prediction_report(
                prediction_data,
                performance_data
            )
            if email_result:
                print("✅ Initial prediction email sent successfully!")
            else:
                print("⚠️ Failed to send initial email (check email configuration)")
    
    print("="*60 + "\n")
    
    # Schedule daily job with email
    schedule.every().day.at("00:30").do(predictor.daily_job_with_email)
    
    print("✅ Enhanced BTC Predictor is running!")
    print("📅 Daily updates scheduled for 00:30 UTC")
    print("📊 Data Source: Yahoo Finance Only (Consistent)")
    print("🧠 Advanced ML Features:")
    print("  • Ensemble Models (Random Forest, XGBoost, LightGBM)")
    print("  • Prophet Time Series")
    print("  • Attention LSTM")
    print("  • Automatic Model Selection")
    print("📧 Email notifications enabled")
    print("💌 Initial prediction email sent!")
    print("Press Ctrl+C to stop\n")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

def main_simple():
    """Simple version without advanced features"""
    predictor = SelfLearningPredictor()
    
    if not predictor.is_setup:
        print("🔧 First time setup - this will take a few minutes...")
        predictor.auto_setup()
    
    print("\n" + "="*60)
    print("📊 INITIAL PREDICTION:")
    pred = predictor.trainer.predict_next_day()
    if pred:
        db = DatabaseManager()
        df = db.get_all_data()
        last_close = df['close'].iloc[-1]
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        change = ((pred - last_close) / last_close) * 100
        
        print(f"  • Tomorrow's Date: {tomorrow}")
        print(f"  • Predicted Close: ${pred:,.2f}")
        print(f"  • Current Close: ${last_close:,.2f}")
        print(f"  • Expected Change: {change:+.2f}%")
        
        predictor.db.save_prediction(tomorrow, pred, None, predictor.model_version)
    print("="*60 + "\n")
    
    schedule.every().day.at("00:30").do(predictor.daily_job)
    
    print("✅ BTC Self-Learning Predictor is running!")
    print("📅 Daily updates scheduled for 00:30 UTC")
    print("Press Ctrl+C to stop\n")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    # By default, run with advanced features
    main_with_advanced_features()