# prediction/predictor.py
"""
Main Predictor - Orchestrates all components
"""

import sys
import os

# Add parent directory to path if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from data.pipeline import DataPipeline
from models.lstm_model import ModelTrainer
from prediction.confidence import ConfidenceCalculator
from models.ensemble import DynamicEnsemble
from validation.champion import ChampionChallenger
from models.advanced_ml import AdvancedMLWrapper
from prediction.signal import SignalGenerator
from prediction.intervals import IntervalCalculator
from config import MAX_DAILY_CHANGE
import numpy as np
from datetime import datetime, timedelta


class EnhancedSelfLearningPredictor:
    def __init__(self):
        self.db = DatabaseManager()
        self.pipeline = DataPipeline()
        self.trainer = ModelTrainer()
        self.confidence_calc = ConfidenceCalculator()
        self.ensemble = DynamicEnsemble()
        self.champion_challenger = ChampionChallenger()
        self.advanced_ml = AdvancedMLWrapper()
        self.signal_gen = SignalGenerator()
        self.interval_calc = IntervalCalculator()
        
        self.is_setup = False
        self.model_version = None
        self.use_advanced_ml = True
        self.use_email = True
        
        try:
            from email_notifier import EmailNotifier
            self.email_notifier = EmailNotifier()
        except:
            self.email_notifier = None
            self.use_email = False
        
        self._check_setup()
        
        if not self.is_setup or self.champion_challenger.get_champion() is None:
            print("[WARN] No model found. Training required!")
            self.auto_setup()
        else:
            champion = self.champion_challenger.get_champion()
            if champion:
                self.trainer.load_model(champion)
                self.model_version = champion
                print(f"[OK] Champion loaded: {champion}")
            
            if self.use_advanced_ml and not self.advanced_ml.is_trained:
                try:
                    self.advanced_ml.train(self.db.get_all_data())
                except Exception as e:
                    print(f"[WARN] Advanced ML training failed: {e}")
    
    def _check_setup(self):
        try:
            count = self.db.get_count()
            if count > 0:
                self.is_setup = True
                print(f"[OK] System ready with {count} records")
            else:
                self.is_setup = False
                print("[WARN] No data found in database")
        except Exception as e:
            print(f"[ERROR] Setup check error: {e}")
            self.is_setup = False
    
    def auto_setup(self):
        print("[INFO] Running automatic setup...")
        
        if not self.pipeline.initial_load():
            print("[ERROR] Failed to load data")
            return False
        
        df = self.pipeline.db.get_all_data()
        
        if df.empty:
            print("[ERROR] No data available for training")
            return False
        
        version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"[INFO] Training base model: {version}")
        
        try:
            self.trainer.train(df, force=True, version=version)
        except Exception as e:
            print(f"[ERROR] Model training failed: {e}")
            return False
        
        self.champion_challenger.set_champion(version)
        self.model_version = version
        self.is_setup = True
        
        if self.use_advanced_ml:
            try:
                self.advanced_ml.train(df)
            except Exception as e:
                print(f"[WARN] Advanced ML training failed: {e}")
        
        print(f"[OK] Setup complete! Model: {self.model_version}")
        return True
    
    def get_model_predictions(self, df, date=None):
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        prev_close = self.db.get_previous_close(date)
        predictions = {}
        
        try:
            original_pred = self.trainer.predict_next_day(df)
            if original_pred is not None and original_pred > 0:
                predictions['original'] = original_pred
                self.db.save_model_prediction(date, 'original', original_pred, None, prev_close)
        except Exception as e:
            print(f"[WARN] Original LSTM prediction failed: {e}")
        
        if self.use_advanced_ml and self.advanced_ml.is_trained:
            try:
                lstm_pred = self.advanced_ml.predict_lstm(df)
                if lstm_pred is not None and lstm_pred > 0:
                    predictions['lstm'] = lstm_pred
                    self.db.save_model_prediction(date, 'lstm', lstm_pred, None, prev_close)
            except:
                pass
            
            try:
                ensemble_pred = self.advanced_ml.predict_ensemble(df)
                if ensemble_pred is not None and ensemble_pred > 0:
                    predictions['ensemble'] = ensemble_pred
                    self.db.save_model_prediction(date, 'ensemble', ensemble_pred, None, prev_close)
            except:
                pass
            
            try:
                prophet_pred = self.advanced_ml.predict_prophet(df)
                if prophet_pred is not None and prophet_pred > 0:
                    predictions['prophet'] = prophet_pred
                    self.db.save_model_prediction(date, 'prophet', prophet_pred, None, prev_close)
            except:
                pass
        
        return predictions
    
    def get_ensemble_prediction(self, predictions):
        predictions = {k: v for k, v in predictions.items() if v is not None and v > 0}
        
        if not predictions:
            return None, {}
        
        model_names = list(predictions.keys())
        weights = self.ensemble.calculate_weights(model_names)
        
        final_prediction = sum(predictions[name] * weights.get(name, 1.0/len(model_names)) 
                              for name in predictions)
        
        df = self.db.get_all_data()
        if not df.empty:
            current_price = df['close'].iloc[-1]
            min_pred = current_price * (1 - MAX_DAILY_CHANGE)
            max_pred = current_price * (1 + MAX_DAILY_CHANGE)
            
            if final_prediction < min_pred or final_prediction > max_pred:
                print(f"[WARN] Prediction ${final_prediction:,.2f} outside reasonable range")
                final_prediction = np.clip(final_prediction, min_pred, max_pred)
        
        return final_prediction, weights
    
    def daily_job(self):
        print(f"\n[INFO] {'='*60}")
        print(f"[INFO] Running daily job at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.db.update_yesterday_predictions()
        
        if not self.pipeline.daily_update():
            print("[WARN] Daily update failed")
            return
        
        df = self.pipeline.db.get_all_data()
        
        all_predictions = self.get_model_predictions(df)
        final_prediction, weights = self.get_ensemble_prediction(all_predictions)
        
        if final_prediction is None:
            print("[WARN] No prediction generated")
            return
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        last_close = df['close'].iloc[-1]
        change = ((final_prediction - last_close) / last_close) * 100
        
        confidence_data = self.confidence_calc.calculate(all_predictions, last_close, df)
        intervals = self.interval_calc.calculate(final_prediction, df)
        signal = self.signal_gen.generate(final_prediction, last_close, confidence_data)
        
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
        
        print(f"\n[INFO] FINAL FORECAST ({tomorrow}):")
        print(f"[INFO]   Predicted Close: ${final_prediction:,.2f}")
        print(f"[INFO]   Current Close: ${last_close:,.2f}")
        print(f"[INFO]   Expected Change: {change:+.2f}%")
        print(f"[INFO]   Direction: {confidence_data['direction']}")
        print(f"[INFO]   Confidence Score: {confidence_data['confidence_score']:.1f}%")
        print(f"[INFO]   Range: ${intervals['low']:,.2f} - ${intervals['high']:,.2f}")
        print(f"[INFO]   Signal: {signal}")
        
        if self.use_email and self.email_notifier:
            try:
                prediction_data = {
                    'price': final_prediction,
                    'change': change,
                    'current_price': last_close,
                    'confidence': confidence_data['confidence_score'],
                    'range_low': intervals['low'],
                    'range_high': intervals['high'],
                    'direction': confidence_data['direction'],
                    'regime': confidence_data.get('regime', 'UNKNOWN'),
                    'signal': signal
                }
                
                performance_data = {
                    'model_version': self.model_version or 'v1.0',
                    'recent_predictions': self.db.get_recent_predictions(10)
                }
                
                metrics = self.db.update_performance_metrics()
                if metrics:
                    performance_data.update(metrics)
                
                self.email_notifier.send_daily_prediction_report(prediction_data, performance_data)
            except Exception as e:
                print(f"[ERROR] Email sending failed: {e}")
        
        self.db.update_performance_metrics()