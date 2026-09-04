"""
btc_indicators_table_production.py - Production-Ready BTC Daily Indicators Table
FIXED: Price columns NULL issue - COMPLETE FIX
"""

import mysql.connector
from mysql.connector import Error
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Read credentials from .env
DB_USER = os.getenv('db_user')
DB_PASSWORD = os.getenv('db_password')
DB_HOST = os.getenv('db_host')
DB_NAME = os.getenv('db_name')

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
    raise ValueError("❌ .env file mein kuch values missing hain!")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('btc_indicators_table.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BTCIndicatorsTable:
    def __init__(self):
        """Initialize database connection"""
        self.conn = None
        self.cursor = None
        self.connect()
    
    def connect(self):
        """Connect to MySQL database with explicit failure"""
        try:
            self.conn = mysql.connector.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            self.cursor = self.conn.cursor()
            logger.info("✅ Connected to database")
            return True
        except Error as e:
            logger.error(f"❌ Connection failed: {e}")
            raise Exception(f"Database connection failed: {e}")
    
    def create_table(self):
        """Create btc_daily_indicators table with optimized structure"""
        try:
            logger.info("📊 Creating btc_daily_indicators table...")
            
            # Drop table if exists for fresh start
            self.cursor.execute("DROP TABLE IF EXISTS btc_daily_indicators")
            
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS btc_daily_indicators (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    date DATE UNIQUE,
                    
                    -- BTC Price Data
                    open_price DECIMAL(18, 8),
                    high_price DECIMAL(18, 8),
                    low_price DECIMAL(18, 8),
                    close_price DECIMAL(18, 8),
                    volume DECIMAL(30, 0),
                    
                    -- Moving Averages (Rolling)
                    ma_7 DECIMAL(18, 8),
                    ma_20 DECIMAL(18, 8),
                    ma_50 DECIMAL(18, 8),
                    ma_100 DECIMAL(18, 8),
                    ma_200 DECIMAL(18, 8),
                    
                    ma_7_trend VARCHAR(20),
                    ma_20_trend VARCHAR(20),
                    ma_50_trend VARCHAR(20),
                    ma_100_trend VARCHAR(20),
                    ma_200_trend VARCHAR(20),
                    
                    -- RSI (Wilder's Smoothing)
                    rsi_14 DECIMAL(10, 4),
                    rsi_status VARCHAR(20),
                    
                    -- MACD
                    macd DECIMAL(18, 8),
                    macd_signal DECIMAL(18, 8),
                    macd_histogram DECIMAL(18, 8),
                    macd_signal_status VARCHAR(20),
                    
                    -- Bollinger Bands (Rolling window)
                    bb_upper DECIMAL(18, 8),
                    bb_middle DECIMAL(18, 8),
                    bb_lower DECIMAL(18, 8),
                    bb_position VARCHAR(30),
                    bb_squeeze VARCHAR(5),
                    bb_bandwidth_percentile DECIMAL(10, 4),
                    
                    -- ATR (Rolling percentile)
                    atr_14 DECIMAL(18, 8),
                    atr_percent DECIMAL(10, 4),
                    atr_percentile DECIMAL(10, 4),
                    
                    -- Support & Resistance (Zone-based)
                    nearest_support DECIMAL(18, 8),
                    nearest_resistance DECIMAL(18, 8),
                    support_strength INT,
                    resistance_strength INT,
                    
                    -- Fibonacci (Swing-based with ATR tolerance)
                    fib_0_0 DECIMAL(18, 8),
                    fib_0_236 DECIMAL(18, 8),
                    fib_0_382 DECIMAL(18, 8),
                    fib_0_5 DECIMAL(18, 8),
                    fib_0_618 DECIMAL(18, 8),
                    fib_0_786 DECIMAL(18, 8),
                    fib_1_0 DECIMAL(18, 8),
                    fib_current_level VARCHAR(10),
                    fib_direction VARCHAR(10),
                    
                    -- Pivot Points
                    pivot_point DECIMAL(18, 8),
                    pivot_r1 DECIMAL(18, 8),
                    pivot_r2 DECIMAL(18, 8),
                    pivot_r3 DECIMAL(18, 8),
                    pivot_s1 DECIMAL(18, 8),
                    pivot_s2 DECIMAL(18, 8),
                    pivot_s3 DECIMAL(18, 8),
                    pivot_position VARCHAR(30),
                    
                    -- Market Structure (Alternating swings)
                    trend_regime VARCHAR(20),
                    bos_type VARCHAR(20),
                    choch_type VARCHAR(20),
                    hh_count INT,
                    hl_count INT,
                    lh_count INT,
                    ll_count INT,
                    
                    -- Liquidity (30-day rolling)
                    avg_volume_30d BIGINT,
                    volume_ratio DECIMAL(10, 4),
                    poc_price DECIMAL(18, 8),
                    vah_price DECIMAL(18, 8),
                    val_price DECIMAL(18, 8),
                    
                    -- Signal (Calibrated)
                    signal_direction VARCHAR(20),
                    signal_score DECIMAL(10, 4),
                    signal_confidence VARCHAR(10),
                    
                    -- Metadata
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    
                    INDEX idx_date (date),
                    INDEX idx_signal (signal_direction),
                    INDEX idx_trend (trend_regime)
                )
            """)
            
            self.conn.commit()
            logger.info("✅ Table created successfully!")
            return True
            
        except Error as e:
            logger.error(f"❌ Error creating table: {e}")
            return False
    
    def fetch_btc_data(self, min_days=250):
        """Fetch BTC data with validation using direct mysql connector"""
        try:
            query = """
                SELECT date, open, high, low, close, volume 
                FROM btc_price_history 
                ORDER BY date
            """
            df = pd.read_sql_query(query, self.conn)
            
            if len(df) < min_days:
                logger.warning(f"⚠️ Only {len(df)} days available. Need at least {min_days}.")
                return None
            
            # Data validation
            df = self.validate_data(df)
            
            logger.info(f"✅ Fetched {len(df)} validated records")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error fetching BTC data: {e}")
            return None
    
    def validate_data(self, df):
        """Validate and clean data"""
        df = df.drop_duplicates(subset=['date'])
        
        date_range = pd.date_range(df['date'].min(), df['date'].max())
        missing_dates = set(date_range) - set(df['date'])
        if missing_dates:
            logger.warning(f"⚠️ Missing {len(missing_dates)} dates")
        
        invalid = df[df['high'] < df['low']]
        if not invalid.empty:
            logger.warning(f"⚠️ Found {len(invalid)} invalid OHLC rows")
            df = df[df['high'] >= df['low']]
        
        df['volume'] = df['volume'].fillna(0).astype('int64')
        
        return df.sort_values('date').reset_index(drop=True)
    
    def calculate_indicators_vectorized(self, df):
        """Calculate all indicators using vectorized operations"""
        logger.info("📊 Calculating indicators vectorized...")
        
        # Create a copy for calculations
        data = df.copy()
        
        # Minimum warm-up period
        warmup = 200
        
        # 1. Moving Averages (Vectorized)
        for period in [7, 20, 50, 100, 200]:
            col = f'ma_{period}'
            data[col] = data['close'].rolling(window=period).mean()
            
            data[f'{col}_trend'] = 'Neutral'
            mask_bull = data['close'] > data[col]
            mask_bear = data['close'] < data[col]
            data.loc[mask_bull, f'{col}_trend'] = 'Bullish'
            data.loc[mask_bear, f'{col}_trend'] = 'Bearish'
            data.loc[data[col].isna(), f'{col}_trend'] = None
        
        # 2. RSI (Wilder's Smoothing)
        delta = data['close'].diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        data['rsi_14'] = 100 - (100 / (1 + rs))
        
        data['rsi_status'] = 'Neutral'
        data.loc[data['rsi_14'] > 70, 'rsi_status'] = 'Overbought'
        data.loc[data['rsi_14'] < 30, 'rsi_status'] = 'Oversold'
        data.loc[data['rsi_14'].isna(), 'rsi_status'] = None
        
        # 3. MACD
        exp1 = data['close'].ewm(span=12, adjust=False).mean()
        exp2 = data['close'].ewm(span=26, adjust=False).mean()
        data['macd'] = exp1 - exp2
        data['macd_signal'] = data['macd'].ewm(span=9, adjust=False).mean()
        data['macd_histogram'] = data['macd'] - data['macd_signal']
        data['macd_signal_status'] = 'Bearish'
        data.loc[data['macd'] > data['macd_signal'], 'macd_signal_status'] = 'Bullish'
        data.loc[data['macd'].isna(), 'macd_signal_status'] = None
        
        # 4. Bollinger Bands
        period = 20
        sma = data['close'].rolling(window=period).mean()
        std = data['close'].rolling(window=period).std()
        data['bb_upper'] = sma + (std * 2)
        data['bb_middle'] = sma
        data['bb_lower'] = sma - (std * 2)
        
        data['bb_position'] = 'Inside Bands'
        data.loc[data['close'] > data['bb_upper'], 'bb_position'] = 'Above Upper Band'
        data.loc[data['close'] < data['bb_lower'], 'bb_position'] = 'Below Lower Band'
        data.loc[data['bb_upper'].isna(), 'bb_position'] = None
        
        # Rolling percentile for bandwidth (252-day window)
        bandwidth = (data['bb_upper'] - data['bb_lower']) / data['bb_middle']
        
        def rolling_percentile(series, window):
            result = []
            for i in range(len(series)):
                if i < window:
                    result.append(np.nan)
                else:
                    window_data = series[i-window:i+1].dropna()
                    if len(window_data) > 0:
                        current_val = series.iloc[i]
                        percentile = (window_data < current_val).sum() / len(window_data) * 100
                        result.append(percentile)
                    else:
                        result.append(np.nan)
            return pd.Series(result, index=series.index)
        
        data['bb_bandwidth_percentile'] = rolling_percentile(bandwidth, 252)
        
        data['bb_squeeze'] = 'No'
        data.loc[data['bb_bandwidth_percentile'] < 20, 'bb_squeeze'] = 'Yes'
        data.loc[data['bb_bandwidth_percentile'].isna(), 'bb_squeeze'] = None
        
        # 5. ATR with Rolling Percentile
        high_low = data['high'] - data['low']
        high_close = (data['high'] - data['close'].shift()).abs()
        low_close = (data['low'] - data['close'].shift()).abs()
        
        true_range = pd.DataFrame({
            'hl': high_low,
            'hc': high_close,
            'lc': low_close
        }).max(axis=1)
        
        data['atr_14'] = true_range.rolling(14).mean()
        data['atr_percent'] = (data['atr_14'] / data['close']) * 100
        data['atr_percentile'] = rolling_percentile(data['atr_14'], 252)
        
        # 6. Support & Resistance
        highs = []
        lows = []
        for i in range(2, len(data)):
            if (data['high'].iloc[i] > data['high'].iloc[i-1] and 
                data['high'].iloc[i] > data['high'].iloc[i-2]):
                highs.append({
                    'idx': i,
                    'price': data['high'].iloc[i],
                    'date': data['date'].iloc[i]
                })
            
            if (data['low'].iloc[i] < data['low'].iloc[i-1] and 
                data['low'].iloc[i] < data['low'].iloc[i-2]):
                lows.append({
                    'idx': i,
                    'price': data['low'].iloc[i],
                    'date': data['date'].iloc[i]
                })
        
        def group_swings(swings, tolerance=0.02):
            if not swings:
                return []
            grouped = []
            swings = sorted(swings, key=lambda x: x['price'])
            current_group = [swings[0]]
            
            for s in swings[1:]:
                if abs(s['price'] - current_group[-1]['price']) / current_group[-1]['price'] < tolerance:
                    current_group.append(s)
                else:
                    avg_price = sum([x['price'] for x in current_group]) / len(current_group)
                    grouped.append({
                        'price': avg_price,
                        'strength': len(current_group),
                        'dates': [x['date'] for x in current_group]
                    })
                    current_group = [s]
            
            if current_group:
                avg_price = sum([x['price'] for x in current_group]) / len(current_group)
                grouped.append({
                    'price': avg_price,
                    'strength': len(current_group),
                    'dates': [x['date'] for x in current_group]
                })
            
            return grouped
        
        support_levels = group_swings(lows)
        resistance_levels = group_swings(highs)
        
        data['nearest_support'] = None
        data['nearest_resistance'] = None
        data['support_strength'] = 0
        data['resistance_strength'] = 0
        
        for i in range(warmup, len(data)):
            current_price = data['close'].iloc[i]
            
            supports_below = [s for s in support_levels if s['price'] < current_price]
            if supports_below:
                nearest_s = max(supports_below, key=lambda x: x['price'])
                data.loc[data.index[i], 'nearest_support'] = nearest_s['price']
                data.loc[data.index[i], 'support_strength'] = nearest_s['strength']
            
            resistances_above = [r for r in resistance_levels if r['price'] > current_price]
            if resistances_above:
                nearest_r = min(resistances_above, key=lambda x: x['price'])
                data.loc[data.index[i], 'nearest_resistance'] = nearest_r['price']
                data.loc[data.index[i], 'resistance_strength'] = nearest_r['strength']
        
        # 7. Fibonacci
        data['fib_0_0'] = None
        data['fib_0_236'] = None
        data['fib_0_382'] = None
        data['fib_0_5'] = None
        data['fib_0_618'] = None
        data['fib_0_786'] = None
        data['fib_1_0'] = None
        data['fib_current_level'] = None
        data['fib_direction'] = None
        
        for i in range(warmup, len(data)):
            recent = data.iloc[max(0, i-30):i+1]
            
            if len(recent) >= 30:
                recent_highs = [h for h in highs if h['idx'] <= i]
                recent_lows = [l for l in lows if l['idx'] <= i]
                
                if recent_highs and recent_lows:
                    latest_high = max(recent_highs, key=lambda x: x['idx'])
                    latest_low = max(recent_lows, key=lambda x: x['idx'])
                    
                    if latest_high['idx'] > latest_low['idx']:
                        swing_high = latest_high['price']
                        swing_low = latest_low['price']
                        data.loc[data.index[i], 'fib_direction'] = 'Bearish'
                    else:
                        swing_low = latest_low['price']
                        swing_high = latest_high['price']
                        data.loc[data.index[i], 'fib_direction'] = 'Bullish'
                    
                    diff = swing_high - swing_low
                    
                    fib_levels = {
                        '0.0': swing_high,
                        '0.236': swing_high - diff * 0.236,
                        '0.382': swing_high - diff * 0.382,
                        '0.5': swing_high - diff * 0.5,
                        '0.618': swing_high - diff * 0.618,
                        '0.786': swing_high - diff * 0.786,
                        '1.0': swing_low
                    }
                    
                    for key, value in fib_levels.items():
                        col = f'fib_{key.replace(".", "_")}'
                        data.loc[data.index[i], col] = value
                    
                    current_price = data['close'].iloc[i]
                    atr_val = data['atr_14'].iloc[i] if not pd.isna(data['atr_14'].iloc[i]) else diff * 0.02
                    tolerance = atr_val * 0.5
                    
                    current_fib = None
                    for level, price in fib_levels.items():
                        if abs(current_price - price) < tolerance:
                            current_fib = level
                            break
                    data.loc[data.index[i], 'fib_current_level'] = current_fib
        
        # 8. Pivot Points
        data['pivot_point'] = None
        data['pivot_r1'] = None
        data['pivot_r2'] = None
        data['pivot_r3'] = None
        data['pivot_s1'] = None
        data['pivot_s2'] = None
        data['pivot_s3'] = None
        data['pivot_position'] = None
        
        for i in range(1, len(data)):
            prev = data.iloc[i-1]
            H = prev['high']
            L = prev['low']
            C = prev['close']
            
            pp = (H + L + C) / 3
            data.loc[data.index[i], 'pivot_point'] = pp
            data.loc[data.index[i], 'pivot_r1'] = (2 * pp) - L
            data.loc[data.index[i], 'pivot_r2'] = pp + (H - L)
            data.loc[data.index[i], 'pivot_r3'] = (2 * pp) + (H - L)
            data.loc[data.index[i], 'pivot_s1'] = (2 * pp) - H
            data.loc[data.index[i], 'pivot_s2'] = pp - (H - L)
            data.loc[data.index[i], 'pivot_s3'] = (2 * pp) - (H - L)
            
            current_price = data['close'].iloc[i]
            data.loc[data.index[i], 'pivot_position'] = 'Above Pivot' if current_price > pp else 'Below Pivot'
        
        # 9. Market Structure
        data['trend_regime'] = None
        data['bos_type'] = None
        data['choch_type'] = None
        data['hh_count'] = 0
        data['hl_count'] = 0
        data['lh_count'] = 0
        data['ll_count'] = 0
        
        for i in range(warmup, len(data)):
            recent_highs = [h for h in highs if h['idx'] <= i][-10:]
            recent_lows = [l for l in lows if l['idx'] <= i][-10:]
            
            if len(recent_highs) >= 2 and len(recent_lows) >= 2:
                hh = sum(1 for j in range(1, len(recent_highs)) if recent_highs[j]['price'] > recent_highs[j-1]['price'])
                hl = sum(1 for j in range(1, len(recent_lows)) if recent_lows[j]['price'] > recent_lows[j-1]['price'])
                lh = len(recent_highs) - 1 - hh
                ll = len(recent_lows) - 1 - hl
                
                data.loc[data.index[i], 'hh_count'] = hh
                data.loc[data.index[i], 'hl_count'] = hl
                data.loc[data.index[i], 'lh_count'] = lh
                data.loc[data.index[i], 'll_count'] = ll
                
                if hh > lh and hl > ll:
                    data.loc[data.index[i], 'trend_regime'] = 'Uptrend'
                elif lh > hh and ll > hl:
                    data.loc[data.index[i], 'trend_regime'] = 'Downtrend'
                else:
                    data.loc[data.index[i], 'trend_regime'] = 'Range'
                
                if len(recent_highs) >= 3 and len(recent_lows) >= 3:
                    last_high = recent_highs[-1]
                    prev_high = recent_highs[-2]
                    last_low = recent_lows[-1]
                    prev_low = recent_lows[-2]
                    
                    current_price = data['close'].iloc[i]
                    
                    if current_price > prev_high['price'] and current_price > last_high['price']:
                        data.loc[data.index[i], 'bos_type'] = 'Bullish BOS'
                    elif current_price < prev_low['price'] and current_price < last_low['price']:
                        data.loc[data.index[i], 'bos_type'] = 'Bearish BOS'
                    
                    if len(recent_lows) >= 4:
                        if (recent_lows[-1]['price'] > recent_lows[-2]['price'] > recent_lows[-3]['price']):
                            data.loc[data.index[i], 'choch_type'] = 'Bullish CHOCH'
                        elif (recent_highs[-1]['price'] < recent_highs[-2]['price'] < recent_highs[-3]['price']):
                            data.loc[data.index[i], 'choch_type'] = 'Bearish CHOCH'
        
        # 10. Liquidity
        data['avg_volume_30d'] = data['volume'].rolling(30).mean()
        data['volume_ratio'] = data['volume'] / data['avg_volume_30d']
        
        data['poc_price'] = None
        data['vah_price'] = None
        data['val_price'] = None
        
        for i in range(warmup, len(data)):
            recent = data.iloc[max(0, i-30):i+1]
            if len(recent) >= 20:
                bins = pd.cut(recent['close'], bins=10)
                profile = recent.groupby(bins)['volume'].sum()
                
                if not profile.empty:
                    poc_idx = profile.idxmax()
                    data.loc[data.index[i], 'poc_price'] = (poc_idx.left + poc_idx.right) / 2
                    
                    total_vol = profile.sum()
                    cum_vol = 0
                    value_area = []
                    for idx, vol in profile.sort_values(ascending=False).items():
                        cum_vol += vol
                        value_area.append(idx)
                        if cum_vol >= total_vol * 0.7:
                            break
                    
                    all_prices = []
                    for interval in value_area:
                        all_prices.append(interval.left)
                        all_prices.append(interval.right)
                    
                    if all_prices:
                        data.loc[data.index[i], 'vah_price'] = max(all_prices)
                        data.loc[data.index[i], 'val_price'] = min(all_prices)
        
        # 11. Signal
        data['signal_direction'] = 'NEUTRAL'
        data['signal_score'] = 0.0
        data['signal_confidence'] = 'Low'
        
        for i in range(warmup, len(data)):
            score = 0.0
            
            rsi_val = data['rsi_14'].iloc[i]
            if pd.notna(rsi_val):
                if rsi_val < 30:
                    score += 1.5
                elif rsi_val > 70:
                    score -= 1.5
            
            macd_status = data['macd_signal_status'].iloc[i]
            if pd.notna(macd_status):
                if macd_status == 'Bullish':
                    score += 2.0
                else:
                    score -= 2.0
            
            ma_bullish = 0
            ma_bearish = 0
            for period in [7, 20, 50]:
                trend = data[f'ma_{period}_trend'].iloc[i]
                if trend == 'Bullish':
                    ma_bullish += 1
                elif trend == 'Bearish':
                    ma_bearish += 1
            
            if ma_bullish >= 2:
                score += 1.0
            elif ma_bearish >= 2:
                score -= 1.0
            
            bb_pos = data['bb_position'].iloc[i]
            if bb_pos == 'Below Lower Band':
                score += 0.5
            elif bb_pos == 'Above Upper Band':
                score -= 0.5
            
            trend = data['trend_regime'].iloc[i]
            if trend == 'Uptrend':
                score += 0.5
            elif trend == 'Downtrend':
                score -= 0.5
            
            if score >= 3.0:
                data.loc[data.index[i], 'signal_direction'] = 'STRONG BUY'
                data.loc[data.index[i], 'signal_confidence'] = 'High'
            elif score >= 1.5:
                data.loc[data.index[i], 'signal_direction'] = 'BUY'
                data.loc[data.index[i], 'signal_confidence'] = 'Medium'
            elif score <= -3.0:
                data.loc[data.index[i], 'signal_direction'] = 'STRONG SELL'
                data.loc[data.index[i], 'signal_confidence'] = 'High'
            elif score <= -1.5:
                data.loc[data.index[i], 'signal_direction'] = 'SELL'
                data.loc[data.index[i], 'signal_confidence'] = 'Medium'
            else:
                data.loc[data.index[i], 'signal_direction'] = 'NEUTRAL'
                data.loc[data.index[i], 'signal_confidence'] = 'Low'
            
            data.loc[data.index[i], 'signal_score'] = score
        
        # ============================================================
        # IMPORTANT FIX: Rename columns BEFORE removing warm-up rows
        # ============================================================
        data = data.rename(columns={
            'open': 'open_price',
            'high': 'high_price',
            'low': 'low_price',
            'close': 'close_price'
        })
        
        # Remove warm-up rows
        data = data.iloc[warmup:].reset_index(drop=True)
        
        logger.info(f"✅ Calculated indicators for {len(data)} days")
        return data
    
    def store_indicators_batch(self, df):
        """Store indicators using batch insert"""
        try:
            # Replace NaN with None for MySQL
            df = df.where(pd.notna(df), None)
            
            columns = [
                'date', 'open_price', 'high_price', 'low_price', 'close_price', 'volume',
                'ma_7', 'ma_20', 'ma_50', 'ma_100', 'ma_200',
                'ma_7_trend', 'ma_20_trend', 'ma_50_trend', 'ma_100_trend', 'ma_200_trend',
                'rsi_14', 'rsi_status',
                'macd', 'macd_signal', 'macd_histogram', 'macd_signal_status',
                'bb_upper', 'bb_middle', 'bb_lower', 'bb_position', 'bb_squeeze', 'bb_bandwidth_percentile',
                'atr_14', 'atr_percent', 'atr_percentile',
                'nearest_support', 'nearest_resistance', 'support_strength', 'resistance_strength',
                'fib_0_0', 'fib_0_236', 'fib_0_382', 'fib_0_5', 'fib_0_618', 'fib_0_786', 'fib_1_0',
                'fib_current_level', 'fib_direction',
                'pivot_point', 'pivot_r1', 'pivot_r2', 'pivot_r3', 'pivot_s1', 'pivot_s2', 'pivot_s3',
                'pivot_position',
                'trend_regime', 'bos_type', 'choch_type',
                'hh_count', 'hl_count', 'lh_count', 'll_count',
                'avg_volume_30d', 'volume_ratio', 'poc_price', 'vah_price', 'val_price',
                'signal_direction', 'signal_score', 'signal_confidence'
            ]
            
            values = []
            for _, row in df.iterrows():
                row_values = []
                for col in columns:
                    val = row.get(col)
                    if pd.isna(val):
                        row_values.append(None)
                    elif isinstance(val, (np.integer, np.int64)):
                        row_values.append(int(val))
                    elif isinstance(val, (np.floating, np.float64)):
                        row_values.append(float(val))
                    else:
                        row_values.append(val)
                values.append(tuple(row_values))
            
            placeholders = ', '.join(['%s'] * len(columns))
            columns_str = ', '.join(columns)
            update_clause = ', '.join([f"{col} = VALUES({col})" for col in columns if col != 'date'])
            
            query = f"""
                INSERT INTO btc_daily_indicators ({columns_str})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE {update_clause}
            """
            
            batch_size = 500
            total_inserted = 0
            
            for i in range(0, len(values), batch_size):
                batch = values[i:i+batch_size]
                self.cursor.executemany(query, batch)
                self.conn.commit()
                total_inserted += len(batch)
                logger.info(f"📊 Inserted {total_inserted}/{len(values)} rows")
            
            logger.info(f"✅ Stored {total_inserted} rows successfully")
            return True
            
        except Error as e:
            logger.error(f"❌ Error storing indicators: {e}")
            self.conn.rollback()
            return False
    
    def build_full_table(self):
        """Build complete indicators table"""
        logger.info("\n" + "="*60)
        logger.info("📊 BUILDING BTC DAILY INDICATORS TABLE (PRODUCTION)")
        logger.info("="*60)
        
        if not self.create_table():
            return False
        
        df = self.fetch_btc_data()
        if df is None or df.empty:
            logger.error("❌ No BTC data available")
            return False
        
        indicators_df = self.calculate_indicators_vectorized(df)
        
        if indicators_df is None or indicators_df.empty:
            logger.error("❌ Failed to calculate indicators")
            return False
        
        if not self.store_indicators_batch(indicators_df):
            logger.error("❌ Failed to store indicators")
            return False
        
        self.show_summary()
        return True
    
    def show_summary(self):
        """Show table summary"""
        try:
            self.cursor.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    MIN(date) as earliest_date,
                    MAX(date) as latest_date,
                    COUNT(CASE WHEN signal_direction IN ('BUY', 'STRONG BUY') THEN 1 END) as buy_signals,
                    COUNT(CASE WHEN signal_direction IN ('SELL', 'STRONG SELL') THEN 1 END) as sell_signals,
                    COUNT(CASE WHEN signal_direction = 'NEUTRAL' THEN 1 END) as neutral_signals,
                    AVG(signal_score) as avg_score
                FROM btc_daily_indicators
            """)
            
            result = self.cursor.fetchone()
            
            logger.info("\n" + "="*60)
            logger.info("📊 TABLE SUMMARY")
            logger.info("="*60)
            logger.info(f"Total Records: {result[0]}")
            logger.info(f"Date Range: {result[1]} to {result[2]}")
            logger.info(f"Buy Signals: {result[3]}")
            logger.info(f"Sell Signals: {result[4]}")
            logger.info(f"Neutral Signals: {result[5]}")
            logger.info(f"Avg Signal Score: {result[6]:.2f}")
            logger.info("="*60)
            
        except Error as e:
            logger.error(f"❌ Error getting summary: {e}")
    
    def close(self):
        """Close connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("🔒 Connection closed")

def main():
    """Main function"""
    builder = None
    try:
        builder = BTCIndicatorsTable()
        builder.build_full_table()
        
        # Verify data
        builder.cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(close_price) as non_null_close,
                MIN(close_price) as min_close,
                MAX(close_price) as max_close,
                AVG(close_price) as avg_close
            FROM btc_daily_indicators
        """)
        stats = builder.cursor.fetchone()
        
        print("\n" + "="*60)
        print("📊 DATA VERIFICATION")
        print("="*60)
        print(f"  Total Records: {stats[0]}")
        print(f"  Non-Null Close Prices: {stats[1]}")
        print(f"  Min Close: ${stats[2]:,.2f}")
        print(f"  Max Close: ${stats[3]:,.2f}")
        print(f"  Avg Close: ${stats[4]:,.2f}")
        print("="*60)
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if builder:
            builder.close()

if __name__ == "__main__":
    main()