# models/features.py
"""
Feature Engineering - 40+ Technical Indicators
"""

import pandas as pd
import numpy as np

class FeatureEngineer:
    @staticmethod
    def add_all_features(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Returns
        for period in [1, 3, 5, 10, 20]:
            df[f'return_{period}d'] = df['close'].pct_change(period)
        df['log_return'] = np.log(df['close'] / df['close'].shift(1))
        
        # Price ratios
        df['high_low_ratio'] = (df['high'] - df['low']) / df['close']
        df['close_open_ratio'] = df['close'] / df['open']
        
        # RSI
        df['rsi_7'] = FeatureEngineer._rsi(df['close'], 7)
        df['rsi_14'] = FeatureEngineer._rsi(df['close'], 14)
        df['rsi_21'] = FeatureEngineer._rsi(df['close'], 21)
        
        # MACD
        df['macd'], df['macd_signal'], df['macd_hist'] = FeatureEngineer._macd(df['close'])
        
        # Moving Averages
        for window in [7, 14, 21, 30, 50, 100, 200]:
            df[f'ma_{window}'] = df['close'].rolling(window).mean()
            df[f'ma_ratio_{window}'] = df['close'] / df[f'ma_{window}']
        
        # EMA
        for span in [9, 12, 26, 50]:
            df[f'ema_{span}'] = df['close'].ewm(span=span, adjust=False).mean()
        
        # Bollinger Bands
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = FeatureEngineer._bollinger_bands(df['close'])
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # ATR
        df['atr_14'] = FeatureEngineer._atr(df)
        
        # Volume
        for window in [7, 14, 30]:
            df[f'volume_ma_{window}'] = df['volume'].rolling(window).mean()
            df[f'volume_ratio_{window}'] = df['volume'] / df[f'volume_ma_{window}']
        
        # Volatility
        for period in [7, 14, 30]:
            df[f'volatility_{period}'] = df['return_1d'].rolling(period).std() * np.sqrt(365)
        
        # Trend
        df['ma_50'] = df['close'].rolling(50).mean()
        df['ma_200'] = df['close'].rolling(200).mean()
        df['trend_direction'] = np.where(df['ma_50'] > df['ma_200'], 1, -1)
        df['trend_strength'] = abs(df['ma_50'] - df['ma_200']) / df['ma_200'] * 100
        
        # ADX
        df['adx'] = FeatureEngineer._adx(df)
        
        # Targets
        df['target_return'] = df['close'].shift(-1) / df['close'] - 1
        df['target_direction'] = np.where(df['target_return'] > 0, 1, 0)
        df['target_return_3d'] = df['close'].shift(-3) / df['close'] - 1
        df['target_return_5d'] = df['close'].shift(-5) / df['close'] - 1
        
        df = df.dropna()
        print(f"[INFO] Total features: {len(df.columns) - 1}")
        return df
    
    @staticmethod
    def _rsi(prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def _macd(prices, fast=12, slow=26, signal=9):
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return macd, signal_line, histogram
    
    @staticmethod
    def _bollinger_bands(prices, period=20, std_dev=2):
        rolling_mean = prices.rolling(window=period).mean()
        rolling_std = prices.rolling(window=period).std()
        upper = rolling_mean + (rolling_std * std_dev)
        lower = rolling_mean - (rolling_std * std_dev)
        return upper, rolling_mean, lower
    
    @staticmethod
    def _atr(df, period=14):
        high, low, close = df['high'], df['low'], df['close']
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    @staticmethod
    def _adx(df, period=14):
        high, low, close = df['high'], df['low'], df['close']
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        up_move = high - high.shift()
        down_move = low.shift() - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        atr = tr.rolling(period).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(period).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(period).mean() / atr)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx.rolling(period).mean()