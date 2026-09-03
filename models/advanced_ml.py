# models/advanced_ml.py
"""
Advanced ML Wrapper - Handles ensemble, prophet, attention LSTM
"""

import numpy as np
import pandas as pd
from typing import Optional

class AdvancedMLWrapper:
    def __init__(self):
        self.models = None
        self.prophet = None
        self.lstm_attention = None
        self.is_trained = False
        self.available = False
        
        try:
            from advanced_ml import AdvancedMLModels, ProphetPredictor, AdvancedLSTMTrainer
            self.AdvancedMLModels = AdvancedMLModels
            self.ProphetPredictor = ProphetPredictor
            self.AdvancedLSTMTrainer = AdvancedLSTMTrainer
            self.available = True
            print("[OK] Advanced ML initialized")
        except ImportError as e:
            print(f"[WARN] Advanced ML not available: {e}")
    
    def train(self, df):
        if not self.available:
            print("[WARN] Advanced ML not available")
            return
        
        print("[INFO] Training Advanced ML Models...")
        
        try:
            if self.AdvancedMLModels:
                self.models = self.AdvancedMLModels()
                ensemble_pred, ensemble_mape = self.models.train_ensemble(df)
                if ensemble_pred is not None:
                    print(f"[OK] Ensemble trained (MAPE: {ensemble_mape:.2f}%)")
        except Exception as e:
            print(f"[ERROR] Ensemble training failed: {e}")
        
        try:
            if self.ProphetPredictor:
                self.prophet = self.ProphetPredictor()
                self.prophet.train(df)
                print("[OK] Prophet trained")
        except Exception as e:
            print(f"[ERROR] Prophet failed: {e}")
        
        try:
            if self.AdvancedLSTMTrainer:
                self.lstm_attention = self.AdvancedLSTMTrainer()
                self.lstm_attention.train(df, epochs=50)
                print("[OK] Attention LSTM trained")
        except Exception as e:
            print(f"[ERROR] Attention LSTM failed: {e}")
        
        self.is_trained = True
    
    def predict_ensemble(self, df):
        if not self.available or not self.models:
            return None
        try:
            return self.models.predict_with_ensemble(df)
        except Exception as e:
            print(f"[WARN] Ensemble prediction failed: {e}")
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