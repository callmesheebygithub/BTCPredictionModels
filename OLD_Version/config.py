# config.py
"""
Configuration file for BTC Predictor - Complete
"""

# ============================================
# SCHEDULE
# ============================================
SCHEDULE_TIME = "00:30"  # UTC

# ============================================
# MODEL SETTINGS
# ============================================
MAX_DAILY_CHANGE = 0.12  # 12% max daily change (sanity check)

# Feature Engineering - NEW
USE_FEATURE_ENGINEERING = True  # Set to True to use 40+ technical indicators
USE_FEATURES = True  # Alias for USE_FEATURE_ENGINEERING

# LSTM parameters - UPDATED for better performance
LSTM_SEQ_LENGTH = 30  # Increased from 30 for better context
TRAIN_SPLIT = 0.85    # More training data
LSTM_HIDDEN_SIZE = 128  # Increased from 64
LSTM_NUM_LAYERS = 3  # Increased from 2
LSTM_EPOCHS = 100
LSTM_LEARNING_RATE = 0.001
LSTM_EARLY_STOPPING_PATIENCE = 15

# Feature columns for LSTM (base features - will be expanded with indicators)
LSTM_BASE_FEATURES = ['open', 'high', 'low', 'close', 'volume']

# Legacy compatibility
LSTM_FEATURES = LSTM_BASE_FEATURES

# ============================================
# DATABASE
# ============================================
DB_PATH = 'btc_data.db'
MODEL_DIR = 'models/'

# ============================================
# LOGGING
# ============================================
LOG_FILE = 'btc_predictor.log'
LOG_LEVEL = 'INFO'

# ============================================
# EMAIL
# ============================================
EMAIL_CONFIG = 'email_config.json'

# ============================================
# ENSEMBLE WEIGHTS (default, will be dynamically adjusted)
# ============================================
ENSEMBLE_WEIGHTS = {
    'lstm': 0.30,
    'ensemble': 0.30,
    'prophet': 0.20,
    'original': 0.20
}

# ============================================
# CONFIDENCE WEIGHTS
# ============================================
CONFIDENCE_WEIGHTS = {
    'model_agreement': 0.25,
    'historical_accuracy': 0.20,
    'volatility': 0.15,
    'regime_confidence': 0.15,
    'dispersion': 0.15,
    'recent_trend': 0.10
}