# fix_all_files.py
"""
Fix all Python files - Remove null bytes and recreate
"""

import os
import shutil

# Backup corrupted files
if not os.path.exists('backup_corrupted'):
    os.makedirs('backup_corrupted')

def recreate_file(filepath, content):
    """Recreate file with clean UTF-8 encoding"""
    # Backup old file if exists
    if os.path.exists(filepath):
        backup_path = os.path.join('backup_corrupted', os.path.basename(filepath) + '.bak')
        try:
            shutil.copy2(filepath, backup_path)
            print(f"📦 Backed up: {filepath} -> {backup_path}")
        except:
            pass
    
    # Write clean file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Recreated: {filepath}")

# ============================================
# 1. FIX main.py
# ============================================

main_py = '''# main.py
"""
BTC Predictor - Main Entry Point
"""

import os
import sys
import schedule
import time
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prediction.predictor import EnhancedSelfLearningPredictor
from config import SCHEDULE_TIME
from utils.helpers import print_success, print_info, print_error

def main():
    """Main entry point"""
    
    # Check email config
    if not os.path.exists('email_config.json'):
        print_info("Email not configured. Setup now?")
        choice = input("Setup email? (y/n): ").strip().lower()
        if choice == 'y':
            try:
                from email_notifier import setup_email_config
                setup_email_config()
            except:
                print_error("Email setup failed")
    
    # Initialize predictor
    predictor = EnhancedSelfLearningPredictor()
    
    if predictor.model_version is None:
        print_error("Model training failed!")
        return
    
    print_success(f"Model ready: {predictor.model_version}")
    
    # Show initial prediction
    print_info("\\n" + "="*60)
    print_info("INITIAL PREDICTION")
    
    df = predictor.db.get_all_data()
    all_preds = predictor.get_model_predictions(df)
    final_pred, weights = predictor.get_ensemble_prediction(all_preds)
    
    if final_pred is not None:
        last_close = df['close'].iloc[-1]
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        change = ((final_pred - last_close) / last_close) * 100
        
        confidence_data = predictor.confidence_calc.calculate(all_preds, last_close, df)
        intervals = predictor.interval_calc.calculate(final_pred, df)
        signal = predictor.signal_gen.generate(final_pred, last_close, confidence_data)
        
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
                'direction': confidence_data['direction'],
                'regime': confidence_data.get('regime', 'UNKNOWN'),
                'signal': signal
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
    
    print_info("="*60 + "\\n")
    
    # Schedule daily job
    schedule.every().day.at(SCHEDULE_TIME).do(predictor.daily_job)
    
    print_success("BTC Predictor is running!")
    print_info(f"Daily updates scheduled for {SCHEDULE_TIME} UTC")
    print_info(f"Current model: {predictor.model_version}")
    print_info("Press Ctrl+C to stop\\n")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
'''

# ============================================
# 2. FIX config.py
# ============================================

config_py = '''# config.py
"""
Configuration file for BTC Predictor
"""

# Schedule time (UTC)
SCHEDULE_TIME = "00:30"

# Maximum daily change for sanity check (12%)
MAX_DAILY_CHANGE = 0.12

# Database path
DB_PATH = 'btc_data.db'

# Model directory
MODEL_DIR = 'models/'

# Logging configuration
LOG_FILE = 'btc_predictor.log'
LOG_LEVEL = 'INFO'

# Feature columns for LSTM
LSTM_FEATURES = ['open', 'high', 'low', 'close', 'volume']

# LSTM parameters
LSTM_SEQ_LENGTH = 30
LSTM_HIDDEN_SIZE = 64
LSTM_NUM_LAYERS = 2
LSTM_EPOCHS = 100
LSTM_LEARNING_RATE = 0.001
LSTM_EARLY_STOPPING_PATIENCE = 15

# Ensemble weights (default, will be dynamically adjusted)
ENSEMBLE_WEIGHTS = {
    'lstm': 0.30,
    'ensemble': 0.30,
    'prophet': 0.20,
    'original': 0.20
}

# Confidence weights
CONFIDENCE_WEIGHTS = {
    'model_agreement': 0.25,
    'historical_accuracy': 0.20,
    'volatility': 0.15,
    'regime_confidence': 0.15,
    'dispersion': 0.15,
    'recent_trend': 0.10
}
'''

# ============================================
# 3. FIX utils/helpers.py
# ============================================

helpers_py = '''# utils/helpers.py
"""
Utility functions
"""

def print_success(msg): print(f"[OK] {msg}")
def print_info(msg): print(f"[INFO] {msg}")
def print_error(msg): print(f"[ERROR] {msg}")
def print_warning(msg): print(f"[WARN] {msg}")
'''

# ============================================
# Recreate all files
# ============================================

print("🔄 Recreating all Python files with clean encoding...\\n")

# main.py
recreate_file('main.py', main_py)

# config.py
recreate_file('config.py', config_py)

# utils/helpers.py
recreate_file('utils/helpers.py', helpers_py)

# prediction/predictor.py (already recreated)
# prediction/__init__.py
recreate_file('prediction/__init__.py', '''# prediction/__init__.py
from .predictor import EnhancedSelfLearningPredictor
from .confidence import ConfidenceCalculator
from .intervals import IntervalCalculator
from .signal import SignalGenerator

__all__ = [
    'EnhancedSelfLearningPredictor',
    'ConfidenceCalculator',
    'IntervalCalculator',
    'SignalGenerator'
]
''')

# models/__init__.py
recreate_file('models/__init__.py', '''# models/__init__.py
from .lstm_model import LSTMPredictor, ModelTrainer
from .ensemble import DynamicEnsemble
from .advanced_ml import AdvancedMLWrapper

__all__ = [
    'LSTMPredictor',
    'ModelTrainer',
    'DynamicEnsemble',
    'AdvancedMLWrapper'
]
''')

# database/__init__.py
recreate_file('database/__init__.py', '''# database/__init__.py
from .db_manager import DatabaseManager
__all__ = ['DatabaseManager']
''')

# data/__init__.py
recreate_file('data/__init__.py', '''# data/__init__.py
from .yahoo_fetcher import YahooDataFetcher
from .pipeline import DataPipeline
__all__ = ['YahooDataFetcher', 'DataPipeline']
''')

# validation/__init__.py
recreate_file('validation/__init__.py', '''# validation/__init__.py
from .champion import ChampionChallenger
from .walk_forward import WalkForwardValidator
__all__ = ['ChampionChallenger', 'WalkForwardValidator']
''')

print("\\n✅ All files recreated successfully!")
print("📦 Old files backed up in: backup_corrupted/")
print("\\n🚀 Now run: python main.py")