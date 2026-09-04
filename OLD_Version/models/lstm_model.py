# models/lstm_model.py
"""
LSTM Model with Feature Engineering - Complete
"""

import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import os
import pickle
import json
from datetime import datetime

from models.features import FeatureEngineer


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
    def __init__(self, model_dir='models/', seq_length=30, use_features=True):
        self.model_dir = model_dir
        self.seq_length = seq_length
        self.use_features = use_features
        self.feature_engineer = FeatureEngineer() if use_features else None
        
        self.scaler = None
        self.model = None
        self.is_trained = False
        self.features = None
        self.feature_count = 0
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
            'use_features': self.use_features,
            'created_at': datetime.now().isoformat()
        }
        with open(paths['metadata'], 'w') as f:
            json.dump(metadata, f, indent=4)
        self.model_version = version
        print(f"[OK] Model saved: {version}")
    
    def load_model(self, version='latest'):
        if version == 'latest':
            versions = [d for d in os.listdir(self.model_dir) 
                       if os.path.isdir(os.path.join(self.model_dir, d))]
            if not versions:
                print("[ERROR] No model versions found")
                return False
            version = sorted(versions)[-1]
        
        paths = self._get_model_paths(version)
        if not os.path.exists(paths['model']):
            print(f"[ERROR] Model not found: {paths['model']}")
            return False
        
        try:
            # Load metadata first
            if os.path.exists(paths['metadata']):
                with open(paths['metadata'], 'r') as f:
                    metadata = json.load(f)
                    self.feature_count = metadata.get('feature_count', 5)
                    self.features = metadata.get('features', ['open', 'high', 'low', 'close', 'volume'])
                    self.seq_length = metadata.get('seq_length', 30)
                    self.use_features = metadata.get('use_features', False)
            else:
                self.feature_count = 5
                self.features = ['open', 'high', 'low', 'close', 'volume']
                self.seq_length = 30
                self.use_features = False
            
            if self.feature_count <= 0:
                print(f"[WARN] Invalid feature_count: {self.feature_count}, setting to 5")
                self.feature_count = 5
                self.features = ['open', 'high', 'low', 'close', 'volume']
            
            self.model = LSTMPredictor(input_size=self.feature_count)
            self.model.load_state_dict(torch.load(paths['model']))
            self.model.eval()
            
            with open(paths['scaler'], 'rb') as f:
                self.scaler = pickle.load(f)
            
            self.is_trained = True
            self.model_version = version
            print(f"[OK] Model loaded: {version} (features: {self.feature_count})")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to load model: {e}")
            return False
    
    def prepare_data(self, df, fit_scaler=False):
        if self.use_features and self.feature_engineer:
            df = self.feature_engineer.add_all_features(df)
        
        if 'target_return' not in df.columns:
            print("[ERROR] 'target_return' column not found!")
            return np.array([]), np.array([])
        
        exclude_cols = ['date', 'target_return', 'target_direction', 'target_return_3d', 'target_return_5d']
        self.features = [c for c in df.columns if c not in exclude_cols]
        self.feature_count = len(self.features)
        
        data = df[self.features].values
        targets = df['target_return'].values
        
        if len(data) <= self.seq_length:
            print(f"[WARN] Not enough data: {len(data)} rows, need at least {self.seq_length + 1}")
            return np.array([]), np.array([])
        
        if fit_scaler:
            self.scaler = MinMaxScaler()
            scaled_data = self.scaler.fit_transform(data)
        else:
            if self.scaler is None:
                print("[ERROR] Scaler not fitted!")
                return np.array([]), np.array([])
            scaled_data = self.scaler.transform(data)
        
        X, y = [], []
        for i in range(self.seq_length, len(scaled_data)):
            X.append(scaled_data[i-self.seq_length:i])
            y.append(targets[i])
        
        print(f"[INFO] Features: {self.feature_count}")
        print(f"[INFO] Samples: {len(X)}")
        return np.array(X), np.array(y)
    
    def train(self, df, force=False, version=None):
        if not force and self.is_trained:
            return self.model
        
        print(f"[INFO] Training model with {len(df)} records...")
        
        if len(df) < self.seq_length + 30:
            print("[ERROR] Not enough data")
            return None
        
        total = len(df)
        train_end = int(0.85 * total)
        val_end = int(0.95 * total)
        
        train_df = df.iloc[:train_end]
        val_df = df.iloc[train_end:val_end]
        test_df = df.iloc[val_end:]
        
        print(f"[INFO]   Train: {train_df['date'].min()} to {train_df['date'].max()} ({len(train_df)} records)")
        print(f"[INFO]   Val:   {val_df['date'].min()} to {val_df['date'].max()} ({len(val_df)} records)")
        print(f"[INFO]   Test:  {test_df['date'].min()} to {test_df['date'].max()} ({len(test_df)} records)")
        
        X_train, y_train = self.prepare_data(train_df, fit_scaler=True)
        
        if len(X_train) == 0:
            print("[ERROR] No training data available!")
            return None
        
        X_val, y_val = self.prepare_data(val_df)
        if len(X_val) == 0:
            print("[WARN] No validation data, using training data")
            X_val, y_val = X_train, y_train
        
        if len(test_df) >= self.seq_length + 5:
            test_with_context = pd.concat([train_df.tail(self.seq_length), test_df])
            X_test, y_test = self.prepare_data(test_with_context)
            if len(X_test) == 0:
                print("[WARN] No test data, using validation data")
                X_test, y_test = X_val, y_val
        else:
            print(f"[WARN] Test data too small ({len(test_df)} rows), using validation data")
            X_test, y_test = X_val, y_val
        
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
                    print(f"[INFO] Early stopping at epoch {epoch+1}")
                    break
            
            if (epoch + 1) % 20 == 0:
                test_loss = criterion(self.model(X_test_t), y_test_t).item()
                print(f"[INFO] Epoch {epoch+1}/{epochs}, Train: {loss.item():.6f}, Val: {val_loss:.6f}, Test: {test_loss:.6f}")
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
        
        print(f"[OK] Model trained and saved: {version}")
        return self.model
    
    def predict_next_day(self, df=None):
        if df is None:
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            df = db.get_all_data()
        
        if not self.is_trained:
            if not self.load_model():
                print("[ERROR] No trained model found")
                return None
        
        if self.use_features and self.feature_engineer:
            df = self.feature_engineer.add_all_features(df)
        
        df = df.dropna()
        
        if len(df) < self.seq_length:
            print("[ERROR] Not enough data")
            return None
        
        last_days = df[self.features].values[-self.seq_length:]
        scaled_last = self.scaler.transform(last_days)
        X_pred = torch.FloatTensor(scaled_last).reshape(1, self.seq_length, len(self.features))
        
        self.model.eval()
        with torch.no_grad():
            pred_return = self.model(X_pred).item()
        
        current_price = df['close'].iloc[-1]
        pred_price = current_price * (1 + pred_return)
        
        return pred_price