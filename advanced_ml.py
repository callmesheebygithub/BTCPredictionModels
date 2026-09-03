# advanced_ml.py

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from prophet import Prophet
import torch
import torch.nn as nn
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class AdvancedMLModels:
    """Collection of advanced ML models for price prediction"""
    
    def __init__(self):
        self.models = {}
        self.scaler = MinMaxScaler()
        self.feature_importance = {}
        
    def prepare_features(self, df):
        """Prepare features for ML models"""
        df = df.copy()
        
        # Price features
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Moving averages
        for window in [7, 14, 21, 30, 50]:
            df[f'ma_{window}'] = df['close'].rolling(window).mean()
            df[f'ma_ratio_{window}'] = df['close'] / df[f'ma_{window}']
        
        # Volatility
        df['volatility_7'] = df['returns'].rolling(7).std()
        df['volatility_14'] = df['returns'].rolling(14).std()
        df['volatility_30'] = df['returns'].rolling(30).std()
        
        # Price position
        df['high_low_ratio'] = (df['high'] - df['low']) / df['close']
        df['close_open_ratio'] = df['close'] / df['open']
        
        # Volume features
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # Momentum
        for window in [5, 10, 20]:
            df[f'momentum_{window}'] = df['close'] - df['close'].shift(window)
            df[f'momentum_pct_{window}'] = (df['close'] - df['close'].shift(window)) / df['close'].shift(window) * 100
        
        # RSI (Relative Strength Index)
        df['rsi'] = self.calculate_rsi(df['close'], 14)
        
        # MACD
        df['macd'], df['macd_signal'] = self.calculate_macd(df['close'])
        
        # Bollinger Bands
        df['bb_upper'], df['bb_lower'] = self.calculate_bollinger_bands(df['close'])
        
        # Price extremes
        df['high_52w'] = df['high'].rolling(365).max()
        df['low_52w'] = df['low'].rolling(365).min()
        df['price_position'] = (df['close'] - df['low_52w']) / (df['high_52w'] - df['low_52w'])
        
        return df.dropna()
    
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculate MACD"""
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line
    
    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        rolling_mean = prices.rolling(window=period).mean()
        rolling_std = prices.rolling(window=period).std()
        upper_band = rolling_mean + (rolling_std * std_dev)
        lower_band = rolling_mean - (rolling_std * std_dev)
        return upper_band, lower_band
    
    def train_ensemble(self, df, target_col='close'):
        """Train ensemble of multiple models"""
        print("🔄 Training Ensemble Models...")
        
        # Prepare features
        df_features = self.prepare_features(df)
        
        # Define features and target
        feature_cols = [col for col in df_features.columns if col not in ['date', target_col]]
        X = df_features[feature_cols].values
        y = df_features[target_col].values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Split data
        split = int(0.8 * len(X_scaled))
        X_train, X_test = X_scaled[:split], X_scaled[split:]
        y_train, y_test = y[:split], y[split:]
        
        # Define models
        models = {
            'random_forest': RandomForestRegressor(n_estimators=200, random_state=42),
            'gradient_boosting': GradientBoostingRegressor(n_estimators=200, random_state=42),
            'xgboost': XGBRegressor(n_estimators=200, learning_rate=0.01, random_state=42),
            'lightgbm': LGBMRegressor(n_estimators=200, learning_rate=0.01, random_state=42),
            'svr': SVR(kernel='rbf', C=1.0, epsilon=0.1),
            'mlp': MLPRegressor(hidden_layer_sizes=(100, 50), max_iter=1000, random_state=42)
        }
        
        # Train each model
        predictions = {}
        importances = {}
        
        for name, model in models.items():
            try:
                print(f"  Training {name}...")
                model.fit(X_train, y_train)
                pred = model.predict(X_test)
                predictions[name] = pred
                
                # Store feature importance if available
                if hasattr(model, 'feature_importances_'):
                    importances[name] = model.feature_importances_
                elif hasattr(model, 'coef_'):
                    importances[name] = np.abs(model.coef_)
                else:
                    importances[name] = None
                
                self.models[name] = model
                
            except Exception as e:
                print(f"  ❌ {name} failed: {e}")
                continue
        
        # Calculate ensemble predictions (weighted average)
        if predictions:
            # Weight based on accuracy
            weights = self.calculate_weights(predictions, y_test)
            ensemble_pred = np.zeros_like(y_test)
            for name, pred in predictions.items():
                ensemble_pred += pred * weights.get(name, 1/len(predictions))
            
            self.models['ensemble'] = {
                'weights': weights,
                'predictions': predictions
            }
            
            # Calculate ensemble accuracy
            ensemble_mape = np.mean(np.abs((ensemble_pred - y_test) / y_test)) * 100
            
            print(f"\n✅ Ensemble Model Trained!")
            print(f"  MAPE: {ensemble_mape:.2f}%")
            print(f"  Models used: {len(predictions)}")
            
            return ensemble_pred, ensemble_mape
        
        return None, None
    
    def calculate_weights(self, predictions, y_true):
        """Calculate weights based on model performance"""
        weights = {}
        total_error = 0
        
        for name, pred in predictions.items():
            mape = np.mean(np.abs((pred - y_true) / y_true))
            error = 1 / (mape + 0.01)  # Avoid division by zero
            weights[name] = error
            total_error += error
        
        # Normalize weights
        for name in weights:
            weights[name] /= total_error
        
        return weights
    
    def predict_with_ensemble(self, df):
        """Make prediction using ensemble"""
        # Prepare features
        df_features = self.prepare_features(df)
        feature_cols = [col for col in df_features.columns if col not in ['date', 'close']]
        
        # Get last row
        X_last = df_features[feature_cols].iloc[-1:].values
        X_last_scaled = self.scaler.transform(X_last)
        
        predictions = {}
        for name, model in self.models.items():
            if name != 'ensemble':
                try:
                    pred = model.predict(X_last_scaled)
                    predictions[name] = pred[0]
                except:
                    continue
        
        # Weighted ensemble prediction
        if predictions and 'ensemble' in self.models:
            weights = self.models['ensemble']['weights']
            final_pred = 0
            for name, pred in predictions.items():
                if name in weights:
                    final_pred += pred * weights[name]
            return final_pred
        
        return None
    
    def get_feature_importance(self):
        """Get feature importance from all models"""
        importance_dict = {}
        for name, model in self.models.items():
            if name != 'ensemble' and hasattr(model, 'feature_importances_'):
                importance_dict[name] = model.feature_importances_
        
        if importance_dict:
            # Average importance across models
            avg_importance = np.zeros(len(next(iter(importance_dict.values()))))
            for imp in importance_dict.values():
                avg_importance += imp
            avg_importance /= len(importance_dict)
            return avg_importance
        
        return None

# ============================================
# Prophet Model for Time Series
# ============================================

class ProphetPredictor:
    """Facebook Prophet for time series forecasting"""
    
    def __init__(self):
        self.model = None
        self.df = None
    
    def prepare_prophet_data(self, df):
        """Prepare data for Prophet"""
        prophet_df = pd.DataFrame({
            'ds': pd.to_datetime(df['date']),
            'y': df['close']
        })
        return prophet_df
    
    def train(self, df, periods=30):
        """Train Prophet model"""
        print("🔄 Training Prophet Model...")
        
        prophet_df = self.prepare_prophet_data(df)
        
        # Add seasonality
        self.model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            seasonality_mode='multiplicative'
        )
        
        # Add custom seasonalities
        self.model.add_seasonality(name='monthly', period=30.5, fourier_order=5)
        
        # Add changepoint prior
        self.model.changepoint_prior_scale = 0.5
        
        # Fit model
        self.model.fit(prophet_df)
        
        # Make future dataframe
        future = self.model.make_future_dataframe(periods=periods)
        forecast = self.model.predict(future)
        
        print(f"✅ Prophet model trained for {periods} days")
        
        return forecast
    
    def predict(self, df):
        """Make prediction using Prophet"""
        prophet_df = self.prepare_prophet_data(df)
        
        if self.model is None:
            self.train(df)
        
        future = self.model.make_future_dataframe(periods=1)
        forecast = self.model.predict(future)
        
        return forecast.iloc[-1]['yhat']

# ============================================
# Advanced LSTM with Attention
# ============================================

class AttentionLSTM(nn.Module):
    """LSTM with Attention Mechanism"""
    
    def __init__(self, input_size, hidden_size, num_layers, dropout=0.2):
        super(AttentionLSTM, self).__init__()
        
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, 
                           batch_first=True, dropout=dropout)
        
        self.attention = nn.MultiheadAttention(hidden_size, num_heads=4, 
                                              batch_first=True)
        
        self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
        self.fc2 = nn.Linear(hidden_size // 2, 1)
        self.dropout = nn.Dropout(dropout)
        self.relu = nn.ReLU()
    
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        
        # Self-attention
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        
        # Pooling (take last output)
        pooled = attn_out[:, -1, :]
        
        # Fully connected
        out = self.dropout(self.relu(self.fc1(pooled)))
        out = self.fc2(out)
        
        return out

class AdvancedLSTMTrainer:
    """Trainer for Attention LSTM"""
    
    def __init__(self, seq_length=60, hidden_size=128, num_layers=3):
        self.seq_length = seq_length
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.scaler = MinMaxScaler()
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    def prepare_data(self, df):
        """Prepare data with advanced features"""
        # Use advanced ML features
        ml = AdvancedMLModels()
        df_features = ml.prepare_features(df)
        
        # Select features
        features = ['close', 'volume', 'rsi', 'returns', 'volatility_14', 
                   'ma_ratio_30', 'momentum_pct_10', 'bb_upper', 'bb_lower']
        
        # Ensure all features exist
        available_features = [f for f in features if f in df_features.columns]
        data = df_features[available_features].values
        
        # Scale
        scaled_data = self.scaler.fit_transform(data)
        
        # Create sequences
        X, y = [], []
        for i in range(self.seq_length, len(scaled_data)):
            X.append(scaled_data[i-self.seq_length:i])
            y.append(scaled_data[i, 0])  # Close price
        
        return np.array(X), np.array(y)
    
    def train(self, df, epochs=100, batch_size=32):
        """Train Attention LSTM"""
        print("🔄 Training Attention LSTM...")
        
        X, y = self.prepare_data(df)
        
        if len(X) == 0:
            print("❌ Not enough data for training")
            return None
        
        # Split
        split = int(0.8 * len(X))
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        
        # To tensors
        X_train = torch.FloatTensor(X_train).to(self.device)
        y_train = torch.FloatTensor(y_train).reshape(-1, 1).to(self.device)
        X_test = torch.FloatTensor(X_test).to(self.device)
        y_test = torch.FloatTensor(y_test).reshape(-1, 1).to(self.device)
        
        # Initialize model
        self.model = AttentionLSTM(
            input_size=X.shape[2],
            hidden_size=self.hidden_size,
            num_layers=self.num_layers
        ).to(self.device)
        
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=20)
        
        # Train
        for epoch in range(epochs):
            self.model.train()
            
            # Mini-batch training
            for i in range(0, len(X_train), batch_size):
                batch_X = X_train[i:i+batch_size]
                batch_y = y_train[i:i+batch_size]
                
                optimizer.zero_grad()
                output = self.model(batch_X)
                loss = criterion(output, batch_y)
                loss.backward()
                optimizer.step()
            
            # Validation
            if (epoch + 1) % 10 == 0:
                self.model.eval()
                with torch.no_grad():
                    train_loss = criterion(self.model(X_train), y_train).item()
                    test_loss = criterion(self.model(X_test), y_test).item()
                    scheduler.step(test_loss)
                    
                    print(f"Epoch {epoch+1}/{epochs}, Train Loss: {train_loss:.6f}, Test Loss: {test_loss:.6f}")
        
        print("✅ Attention LSTM trained successfully")
        return self.model
    
    def predict(self, df):
        """Make prediction"""
        if self.model is None:
            print("⚠️ Model not trained")
            return None
        
        # Prepare data
        ml = AdvancedMLModels()
        df_features = ml.prepare_features(df)
        
        features = ['close', 'volume', 'rsi', 'returns', 'volatility_14', 
                   'ma_ratio_30', 'momentum_pct_10', 'bb_upper', 'bb_lower']
        available_features = [f for f in features if f in df_features.columns]
        
        last_sequence = df_features[available_features].values[-self.seq_length:]
        scaled_sequence = self.scaler.transform(last_sequence)
        
        X_pred = torch.FloatTensor(scaled_sequence).reshape(1, self.seq_length, -1).to(self.device)
        
        self.model.eval()
        with torch.no_grad():
            prediction_scaled = self.model(X_pred).item()
        
        # Inverse transform
        dummy = np.zeros((1, len(available_features)))
        dummy[0, 0] = prediction_scaled
        prediction = self.scaler.inverse_transform(dummy)[0, 0]
        
        return prediction

# ============================================
# Model Comparison and Selection
# ============================================

class ModelSelector:
    """Compare and select best model"""
    
    def __init__(self):
        self.models = {}
        self.best_model = None
        self.metrics = {}
    
    def evaluate_models(self, df):
        """Evaluate all models and select best"""
        print("\n🔄 Evaluating Models...")
        
        # Prepare data
        ml = AdvancedMLModels()
        df_features = ml.prepare_features(df)
        
        X = df_features[['close']].values
        y = df_features['close'].values
        
        # Split
        split = int(0.8 * len(X))
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        
        # Define models to test
        models_to_test = {
            'Random Forest': RandomForestRegressor(n_estimators=100),
            'XGBoost': XGBRegressor(n_estimators=100),
            'LightGBM': LGBMRegressor(n_estimators=100),
            'Gradient Boosting': GradientBoostingRegressor(n_estimators=100)
        }
        
        results = {}
        for name, model in models_to_test.items():
            try:
                model.fit(X_train, y_train)
                pred = model.predict(X_test)
                
                mae = np.mean(np.abs(pred - y_test))
                rmse = np.sqrt(np.mean((pred - y_test) ** 2))
                mape = np.mean(np.abs((pred - y_test) / y_test)) * 100
                
                results[name] = {
                    'model': model,
                    'mae': mae,
                    'rmse': rmse,
                    'mape': mape
                }
                
                print(f"  {name}: MAPE={mape:.2f}%, MAE=${mae:.2f}")
                
            except Exception as e:
                print(f"  ❌ {name} failed: {e}")
        
        # Select best model
        if results:
            best_name = min(results, key=lambda x: results[x]['mape'])
            self.best_model = results[best_name]['model']
            self.metrics = results[best_name]
            self.models = results
            
            print(f"\n✅ Best Model: {best_name}")
            print(f"  MAPE: {self.metrics['mape']:.2f}%")
            print(f"  MAE: ${self.metrics['mae']:.2f}")
            
            return self.best_model
        
        return None