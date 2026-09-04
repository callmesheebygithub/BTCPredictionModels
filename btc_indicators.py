"""
btc_indicators_improved.py - BTC Technical Indicators Calculator (IMPROVED)
Fixed all issues mentioned in the review
"""

import mysql.connector
from mysql.connector import Error
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
import os
import json
import time

import os
import logging
from dotenv import load_dotenv

# Load .env from the same directory as this Python file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_FILE)

# Read credentials
DB_USER = os.getenv("db_user")
DB_PASSWORD = os.getenv("db_password")
DB_HOST = os.getenv("db_host")
DB_NAME = os.getenv("db_name")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
    missing = []

    if not DB_USER:
        missing.append("db_user")

    if not DB_PASSWORD:
        missing.append("db_password")

    if not DB_HOST:
        missing.append("db_host")

    if not DB_NAME:
        missing.append("db_name")

    raise ValueError(
        f".env file mein values missing hain: {', '.join(missing)}"
    )

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(BASE_DIR, "btc_indicators.log"),
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

logger.info(
    f"Database configuration loaded: "
    f"user={DB_USER}, host={DB_HOST}, database={DB_NAME}"
)

class BTCIndicators:
    def __init__(self):
        """Initialize database connection with retry"""
        self.conn = None
        self.cursor = None
        self.max_retries = 3
        self.connect_with_retry()
    
    def connect_with_retry(self):
        """Connect to MySQL database with retry mechanism"""
        for attempt in range(self.max_retries):
            try:
                self.conn = mysql.connector.connect(
                    host=DB_HOST,
                    database=DB_NAME,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    pool_size=5,
                    pool_name='btc_pool'
                )
                self.cursor = self.conn.cursor()
                logger.info("✅ Connected to database")
                return True
            except Error as e:
                logger.warning(f"⚠️ Connection attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                else:
                    logger.error(f"❌ All connection attempts failed: {e}")
                    return False
        return False
    
    def ensure_connection(self):
        """Ensure connection is alive, reconnect if needed"""
        try:
            self.conn.ping(reconnect=True)
            return True
        except:
            return self.connect_with_retry()
    
    def fetch_data(self, days=365):
        """Fetch BTC data from database with validation"""
        try:
            self.ensure_connection()
            
            # Check minimum required rows
            check_query = "SELECT COUNT(*) FROM btc_price_history"
            self.cursor.execute(check_query)
            total_rows = self.cursor.fetchone()[0]
            
            if total_rows < 50:
                logger.warning(f"⚠️ Only {total_rows} rows available. Need at least 50 for reliable indicators.")
                days = min(days, total_rows)
            
            query = f"""
                SELECT date, open, high, low, close, volume 
                FROM btc_price_history 
                ORDER BY date DESC 
                LIMIT {days}
            """
            df = pd.read_sql_query(query, self.conn)
            df = df.sort_values('date')
            df = df.reset_index(drop=True)
            
            if len(df) < 50:
                logger.error(f"❌ Insufficient data: {len(df)} rows. Need at least 50.")
                return None
                
            logger.info(f"✅ Fetched {len(df)} records")
            return df
            
        except Error as e:
            logger.error(f"❌ Error fetching data: {e}")
            return None
    
    def find_swing_points(self, df, lookback=100):
        """Find swing highs and lows for support/resistance"""
        recent_df = df.tail(lookback)
        highs = []
        lows = []
        
        for i in range(2, len(recent_df) - 2):
            # Swing High
            if (recent_df['high'].iloc[i] > recent_df['high'].iloc[i-1] and 
                recent_df['high'].iloc[i] > recent_df['high'].iloc[i-2] and
                recent_df['high'].iloc[i] > recent_df['high'].iloc[i+1] and
                recent_df['high'].iloc[i] > recent_df['high'].iloc[i+2]):
                highs.append({
                    'date': recent_df['date'].iloc[i],
                    'price': recent_df['high'].iloc[i]
                })
            
            # Swing Low
            if (recent_df['low'].iloc[i] < recent_df['low'].iloc[i-1] and 
                recent_df['low'].iloc[i] < recent_df['low'].iloc[i-2] and
                recent_df['low'].iloc[i] < recent_df['low'].iloc[i+1] and
                recent_df['low'].iloc[i] < recent_df['low'].iloc[i+2]):
                lows.append({
                    'date': recent_df['date'].iloc[i],
                    'price': recent_df['low'].iloc[i]
                })
        
        return highs, lows
    
    def group_levels(self, levels, threshold_pct=2.0):
        """Group similar levels with 2% threshold (fixed)"""
        if not levels:
            return []
        
        levels = sorted(levels, key=lambda x: x['price'])
        grouped = []
        current_group = [levels[0]]
        
        for level in levels[1:]:
            # Using 2.0% threshold (fixed from 0.02%)
            if (level['price'] - current_group[-1]['price']) / current_group[-1]['price'] * 100 < threshold_pct:
                current_group.append(level)
            else:
                avg_price = sum([x['price'] for x in current_group]) / len(current_group)
                grouped.append({
                    'price': avg_price,
                    'strength': len(current_group),
                    'dates': [x['date'] for x in current_group]
                })
                current_group = [level]
        
        if current_group:
            avg_price = sum([x['price'] for x in current_group]) / len(current_group)
            grouped.append({
                'price': avg_price,
                'strength': len(current_group),
                'dates': [x['date'] for x in current_group]
            })
        
        return grouped
    
    def calculate_support_resistance(self, df, lookback=100):
        """Calculate Support and Resistance levels (FIXED)"""
        try:
            highs, lows = self.find_swing_points(df, lookback)
            
            # Group levels with 2.0% threshold (fixed)
            support_levels = self.group_levels(lows, threshold_pct=2.0)
            resistance_levels = self.group_levels(highs, threshold_pct=2.0)
            
            # Sort by strength
            support_levels = sorted(support_levels, key=lambda x: x['strength'], reverse=True)
            resistance_levels = sorted(resistance_levels, key=lambda x: x['strength'], reverse=True)
            
            current_price = df['close'].iloc[-1]
            
            # Find nearest support and resistance by price distance (FIXED)
            nearest_support = None
            nearest_resistance = None
            min_support_dist = float('inf')
            min_resistance_dist = float('inf')
            
            for support in support_levels:
                if support['price'] < current_price:
                    dist = current_price - support['price']
                    if dist < min_support_dist:
                        min_support_dist = dist
                        nearest_support = support
            
            for resistance in resistance_levels:
                if resistance['price'] > current_price:
                    dist = resistance['price'] - current_price
                    if dist < min_resistance_dist:
                        min_resistance_dist = dist
                        nearest_resistance = resistance
            
            return {
                'current_price': current_price,
                'support_levels': support_levels[:5],
                'resistance_levels': resistance_levels[:5],
                'nearest_support': nearest_support,
                'nearest_resistance': nearest_resistance
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating support/resistance: {e}")
            return None
    
    def calculate_volume_profile(self, df):
        """Calculate Volume Profile with POC, VAH, VAL (FIXED)"""
        try:
            # Use 20 bins instead of 10 for better resolution
            bins = 20
            price_bins = pd.cut(df['close'], bins=bins)
            volume_profile = df.groupby(price_bins)['volume'].sum()
            
            # Find POC (Point of Control) - highest volume node
            poc_idx = volume_profile.idxmax()
            poc_price = (poc_idx.left + poc_idx.right) / 2
            
            # Calculate VAH and VAL (Value Area High/Low)
            total_volume = volume_profile.sum()
            cum_volume = 0
            value_area_volume = total_volume * 0.7  # 70% value area
            
            # Sort by volume for value area
            sorted_profile = volume_profile.sort_values(ascending=False)
            cum_sum = 0
            value_area_levels = []
            
            for idx, vol in sorted_profile.items():
                cum_sum += vol
                value_area_levels.append(idx)
                if cum_sum >= value_area_volume:
                    break
            
            # Get VAH and VAL
            all_prices = []
            for interval in value_area_levels:
                all_prices.append(interval.left)
                all_prices.append(interval.right)
            
            val = min(all_prices) if all_prices else df['close'].min()
            vah = max(all_prices) if all_prices else df['close'].max()
            
            # Find high volume nodes (HVN) and low volume nodes (LVN)
            avg_volume = volume_profile.mean()
            hvn = []
            lvn = []
            
            for interval, vol in volume_profile.items():
                if vol > avg_volume * 1.5:
                    hvn.append({
                        'price_range': f"${interval.left:,.0f} - ${interval.right:,.0f}",
                        'volume': vol,
                        'avg_price': (interval.left + interval.right) / 2
                    })
                elif vol < avg_volume * 0.5:
                    lvn.append({
                        'price_range': f"${interval.left:,.0f} - ${interval.right:,.0f}",
                        'volume': vol,
                        'avg_price': (interval.left + interval.right) / 2
                    })
            
            return {
                'poc': poc_price,
                'vah': vah,
                'val': val,
                'hvn': sorted(hvn, key=lambda x: x['volume'], reverse=True)[:5],
                'lvn': sorted(lvn, key=lambda x: x['volume'])[:5]
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating volume profile: {e}")
            return None
    
    def calculate_liquidity(self, df):
        """Calculate Volume-based Liquidity Proxy (FIXED - renamed)"""
        try:
            avg_volume = df['volume'].mean()
            recent_volume = df['volume'].iloc[-30:].mean()
            
            # Use improved volume profile
            volume_profile = self.calculate_volume_profile(df)
            
            # Calculate volume-weighted average price (VWAP)
            df['vwap'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
            current_vwap = df['vwap'].iloc[-1]
            
            return {
                'avg_volume_30d': recent_volume,
                'avg_volume_overall': avg_volume,
                'volume_ratio': recent_volume / avg_volume if avg_volume > 0 else 0,
                'vwap': current_vwap,
                'volume_profile': volume_profile
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating liquidity: {e}")
            return None
    
    def calculate_moving_averages(self, df):
        """Calculate moving averages with improved trend logic (FIXED)"""
        try:
            periods = [7, 20, 50, 100, 200]
            ma_data = {}
            current_price = df['close'].iloc[-1]
            
            for period in periods:
                ma = df['close'].rolling(window=period).mean()
                ema = df['close'].ewm(span=period, adjust=False).mean()
                
                # Improved trend logic: price vs MA + slope
                price_vs_ma = current_price - ma.iloc[-1]
                price_vs_ema = current_price - ema.iloc[-1]
                
                # Calculate slope (rate of change)
                slope = (ma.iloc[-1] - ma.iloc[-5]) / ma.iloc[-5] * 100 if len(ma) > 5 else 0
                
                # Determine trend based on multiple factors
                if price_vs_ma > 0 and price_vs_ema > 0 and slope > 0:
                    trend = 'Strong Bullish'
                elif price_vs_ma > 0 and price_vs_ema > 0:
                    trend = 'Bullish'
                elif price_vs_ma < 0 and price_vs_ema < 0 and slope < 0:
                    trend = 'Strong Bearish'
                elif price_vs_ma < 0 and price_vs_ema < 0:
                    trend = 'Bearish'
                else:
                    trend = 'Neutral'
                
                ma_data[f'MA_{period}'] = {
                    'value': ma.iloc[-1],
                    'ema': ema.iloc[-1],
                    'trend': trend,
                    'slope': slope,
                    'period': period
                }
            
            return ma_data
            
        except Exception as e:
            logger.error(f"❌ Error calculating moving averages: {e}")
            return None
    
    def calculate_rsi(self, df, period=14):
        """Calculate RSI using Wilder's smoothing (FIXED)"""
        try:
            delta = df['close'].diff()
            
            # Wilder's smoothing (EMA-like)
            gain = delta.clip(lower=0)
            loss = (-delta).clip(lower=0)
            
            # Use EMA for Wilder's smoothing
            avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            current_rsi = rsi.iloc[-1]
            
            return {
                'value': current_rsi,
                'status': 'Overbought' if current_rsi > 70 else 'Oversold' if current_rsi < 30 else 'Neutral',
                'period': period
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating RSI: {e}")
            return None
    
    def calculate_macd(self, df):
        """Calculate MACD indicator"""
        try:
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            histogram = macd - signal
            
            current_macd = macd.iloc[-1]
            current_signal = signal.iloc[-1]
            current_histogram = histogram.iloc[-1]
            
            return {
                'macd': current_macd,
                'signal': current_signal,
                'histogram': current_histogram,
                'signal_status': 'Bullish' if current_macd > current_signal else 'Bearish',
                'histogram_status': 'Increasing' if histogram.iloc[-1] > histogram.iloc[-2] else 'Decreasing'
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating MACD: {e}")
            return None
    
    def calculate_bollinger_bands(self, df, period=20, std_dev=2):
        """Calculate Bollinger Bands with historical percentile (FIXED)"""
        try:
            sma = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()
            
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)
            
            current_price = df['close'].iloc[-1]
            current_upper = upper_band.iloc[-1]
            current_middle = sma.iloc[-1]
            current_lower = lower_band.iloc[-1]
            
            # Calculate historical bandwidth percentile
            bandwidth = (upper_band - lower_band) / sma
            current_bandwidth = bandwidth.iloc[-1]
            
            # Historical percentile
            bandwidth_history = bandwidth.dropna()
            percentile = (bandwidth_history < current_bandwidth).sum() / len(bandwidth_history) * 100 if len(bandwidth_history) > 0 else 50
            
            # Squeeze based on historical percentile (FIXED)
            squeeze = 'Yes' if percentile < 20 else 'No'  # Bottom 20% = squeeze
            
            # Position
            if current_price > current_upper:
                position = 'Above Upper Band'
            elif current_price < current_lower:
                position = 'Below Lower Band'
            else:
                position = 'Inside Bands'
            
            return {
                'upper_band': current_upper,
                'middle_band': current_middle,
                'lower_band': current_lower,
                'position': position,
                'band_width': current_upper - current_lower,
                'bandwidth_percentile': percentile,
                'squeeze': squeeze
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating Bollinger Bands: {e}")
            return None
    
    def calculate_atr(self, df, period=14):
        """Calculate ATR with historical percentile (FIXED)"""
        try:
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            atr = true_range.rolling(period).mean()
            
            current_atr = atr.iloc[-1]
            current_price = df['close'].iloc[-1]
            
            # Historical percentile for ATR
            atr_history = atr.dropna()
            percentile = (atr_history < current_atr).sum() / len(atr_history) * 100 if len(atr_history) > 0 else 50
            
            # Regime-based classification (FIXED)
            if percentile > 80:
                volatility_status = 'Extremely High'
            elif percentile > 60:
                volatility_status = 'High'
            elif percentile > 40:
                volatility_status = 'Normal'
            elif percentile > 20:
                volatility_status = 'Low'
            else:
                volatility_status = 'Extremely Low'
            
            return {
                'atr': current_atr,
                'atr_percent': (current_atr / current_price) * 100,
                'period': period,
                'volatility_status': volatility_status,
                'percentile': percentile
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating ATR: {e}")
            return None
    
    def calculate_fibonacci(self, df):
        """Calculate Fibonacci using swing highs/lows (FIXED)"""
        try:
            # Find recent swing high and low (last 30 days)
            recent_df = df.tail(30)
            
            # Find actual swing high and low
            swing_high = recent_df['high'].max()
            swing_low = recent_df['low'].min()
            
            # Get dates of swing high and low
            high_date = recent_df[recent_df['high'] == swing_high]['date'].iloc[-1]
            low_date = recent_df[recent_df['low'] == swing_low]['date'].iloc[-1]
            
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
            
            current_price = df['close'].iloc[-1]
            
            # Use ATR-based proximity instead of fixed 5% (FIXED)
            atr = self.calculate_atr(df) if hasattr(self, 'calculate_atr') else None
            atr_value = atr['atr'] if atr else diff * 0.05
            
            current_fib = None
            for level, price in fib_levels.items():
                if abs(current_price - price) < atr_value * 0.5:  # Within 0.5 ATR
                    current_fib = level
                    break
            
            return {
                'high': swing_high,
                'low': swing_low,
                'high_date': high_date.strftime('%Y-%m-%d') if hasattr(high_date, 'strftime') else str(high_date),
                'low_date': low_date.strftime('%Y-%m-%d') if hasattr(low_date, 'strftime') else str(low_date),
                'range': diff,
                'fib_levels': fib_levels,
                'current_fib_level': current_fib
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating Fibonacci: {e}")
            return None
    
    def calculate_pivot_points(self, df):
        """Calculate Pivot Points"""
        try:
            prev_day = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
            
            H = prev_day['high']
            L = prev_day['low']
            C = prev_day['close']
            
            pp = (H + L + C) / 3
            r1 = (2 * pp) - L
            r2 = pp + (H - L)
            r3 = r1 + (H - L)
            s1 = (2 * pp) - H
            s2 = pp - (H - L)
            s3 = s1 - (H - L)
            
            current_price = df['close'].iloc[-1]
            
            return {
                'pivot': pp,
                'resistance_1': r1,
                'resistance_2': r2,
                'resistance_3': r3,
                'support_1': s1,
                'support_2': s2,
                'support_3': s3,
                'current_position': 'Above Pivot' if current_price > pp else 'Below Pivot'
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating pivot points: {e}")
            return None
    
    def calculate_market_structure(self, df):
        """Calculate market structure: BOS, CHOCH, HH, HL, LH, LL (NEW)"""
        try:
            # Find swing points
            highs, lows = self.find_swing_points(df, lookback=50)
            
            # Get recent swing points
            recent_highs = sorted(highs, key=lambda x: x['date'])[-10:]
            recent_lows = sorted(lows, key=lambda x: x['date'])[-10:]
            
            # Determine trend
            if len(recent_highs) > 0 and len(recent_lows) > 0:
                # Higher highs and higher lows = uptrend
                hh = len([i for i in range(1, len(recent_highs)) if recent_highs[i]['price'] > recent_highs[i-1]['price']])
                hl = len([i for i in range(1, len(recent_lows)) if recent_lows[i]['price'] > recent_lows[i-1]['price']])
                lh = len([i for i in range(1, len(recent_highs)) if recent_highs[i]['price'] < recent_highs[i-1]['price']])
                ll = len([i for i in range(1, len(recent_lows)) if recent_lows[i]['price'] < recent_lows[i-1]['price']])
                
                if hh > lh and hl > ll:
                    trend_regime = 'Uptrend'
                elif lh > hh and ll > hl:
                    trend_regime = 'Downtrend'
                else:
                    trend_regime = 'Range'
            else:
                trend_regime = 'Unknown'
            
            return {
                'trend_regime': trend_regime,
                'recent_highs': recent_highs[-5:],
                'recent_lows': recent_lows[-5:]
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating market structure: {e}")
            return None
    
    def generate_signal(self, results):
        """Generate improved signal with weighted confluence (FIXED)"""
        try:
            signal = {
                'direction': 'NEUTRAL',
                'strength': 0,
                'confidence': 0,
                'factors': [],
                'weights': {}
            }
            
            scores = {}
            weights = {}
            
            # 1. RSI Signal (Weight: 15%)
            if 'rsi' in results:
                rsi_value = results['rsi']['value']
                if rsi_value > 70:
                    scores['rsi'] = -2
                    signal['factors'].append('RSI Overbought')
                elif rsi_value < 30:
                    scores['rsi'] = 2
                    signal['factors'].append('RSI Oversold')
                else:
                    scores['rsi'] = 0
                    signal['factors'].append('RSI Neutral')
                weights['rsi'] = 0.15
            
            # 2. MACD Signal (Weight: 20%)
            if 'macd' in results:
                if results['macd']['signal_status'] == 'Bullish':
                    scores['macd'] = 3
                    signal['factors'].append('MACD Bullish')
                else:
                    scores['macd'] = -3
                    signal['factors'].append('MACD Bearish')
                weights['macd'] = 0.20
            
            # 3. Moving Averages Signal (Weight: 25%)
            if 'moving_averages' in results:
                bullish_count = 0
                strong_bullish = 0
                for ma in results['moving_averages'].values():
                    if 'Strong Bullish' in ma['trend']:
                        strong_bullish += 1
                        bullish_count += 1
                    elif 'Bullish' in ma['trend']:
                        bullish_count += 1
                
                if strong_bullish >= 3:
                    scores['ma'] = 4
                    signal['factors'].append(f'MA Strong Bullish ({strong_bullish}/5)')
                elif bullish_count >= 4:
                    scores['ma'] = 2
                    signal['factors'].append(f'MA Bullish ({bullish_count}/5)')
                elif bullish_count >= 3:
                    scores['ma'] = 1
                    signal['factors'].append(f'MA Mild Bullish ({bullish_count}/5)')
                elif bullish_count <= 1:
                    scores['ma'] = -2
                    signal['factors'].append(f'MA Bearish ({5-bullish_count}/5)')
                else:
                    scores['ma'] = 0
                    signal['factors'].append('MA Neutral')
                weights['ma'] = 0.25
            
            # 4. Bollinger Bands Signal (Weight: 10%)
            if 'bollinger_bands' in results:
                position = results['bollinger_bands']['position']
                if position == 'Below Lower Band':
                    scores['bb'] = 1.5
                    signal['factors'].append('BB Oversold')
                elif position == 'Above Upper Band':
                    scores['bb'] = -1.5
                    signal['factors'].append('BB Overbought')
                else:
                    scores['bb'] = 0
                    signal['factors'].append('BB Neutral')
                weights['bb'] = 0.10
            
            # 5. Support & Resistance (Weight: 15%)
            if 'support_resistance' in results:
                sr = results['support_resistance']
                current_price = results['current_price']
                
                nearest_support = sr.get('nearest_support')
                nearest_resistance = sr.get('nearest_resistance')
                
                if nearest_support and nearest_resistance:
                    support_dist = (current_price - nearest_support['price']) / current_price * 100
                    resistance_dist = (nearest_resistance['price'] - current_price) / current_price * 100
                    
                    # Closer to support = bullish, closer to resistance = bearish
                    if support_dist < resistance_dist:
                        scores['sr'] = 1.5
                        signal['factors'].append(f'Near Support (${nearest_support["price"]:,.0f})')
                    elif resistance_dist < support_dist:
                        scores['sr'] = -1.5
                        signal['factors'].append(f'Near Resistance (${nearest_resistance["price"]:,.0f})')
                    else:
                        scores['sr'] = 0
                        signal['factors'].append('S/R Neutral')
                else:
                    scores['sr'] = 0
                weights['sr'] = 0.15
            
            # 6. Fibonacci (Weight: 5%)
            if 'fibonacci' in results:
                fib = results['fibonacci']
                if fib.get('current_fib_level'):
                    level = float(fib['current_fib_level'])
                    if level < 0.5:
                        scores['fib'] = 1
                        signal['factors'].append(f'Fib Level {fib["current_fib_level"]} (Support)')
                    elif level > 0.5:
                        scores['fib'] = -1
                        signal['factors'].append(f'Fib Level {fib["current_fib_level"]} (Resistance)')
                    else:
                        scores['fib'] = 0
                else:
                    scores['fib'] = 0
                weights['fib'] = 0.05
            
            # 7. ATR (Volatility) (Weight: 5%)
            if 'atr' in results:
                atr_status = results['atr']['volatility_status']
                if 'Low' in atr_status:
                    scores['atr'] = 0.5  # Low volatility = good for entries
                    signal['factors'].append(f'Low Volatility ({atr_status})')
                elif 'High' in atr_status:
                    scores['atr'] = -0.5  # High volatility = risk
                    signal['factors'].append(f'High Volatility ({atr_status})')
                else:
                    scores['atr'] = 0
                weights['atr'] = 0.05
            
            # 8. Liquidity (Weight: 5%)
            if 'liquidity' in results:
                liq = results['liquidity']
                if liq['volume_ratio'] > 1.2:
                    scores['liquidity'] = 0.5
                    signal['factors'].append('High Volume')
                elif liq['volume_ratio'] < 0.8:
                    scores['liquidity'] = -0.5
                    signal['factors'].append('Low Volume')
                else:
                    scores['liquidity'] = 0
                weights['liquidity'] = 0.05
            
            # Calculate weighted score
            total_score = 0
            total_weight = 0
            
            for key in scores:
                if key in weights:
                    total_score += scores[key] * weights[key]
                    total_weight += weights[key]
            
            # Normalize
            normalized_score = total_score / total_weight if total_weight > 0 else 0
            
            # Determine direction with confidence
            signal['score'] = normalized_score
            
            if normalized_score > 2.5:
                signal['direction'] = 'STRONG BUY'
                signal['confidence'] = 'High'
                signal['strength'] = 5
            elif normalized_score > 1.5:
                signal['direction'] = 'BUY'
                signal['confidence'] = 'Medium'
                signal['strength'] = 4
            elif normalized_score > 0.5:
                signal['direction'] = 'MILD BUY'
                signal['confidence'] = 'Low'
                signal['strength'] = 2
            elif normalized_score < -2.5:
                signal['direction'] = 'STRONG SELL'
                signal['confidence'] = 'High'
                signal['strength'] = 5
            elif normalized_score < -1.5:
                signal['direction'] = 'SELL'
                signal['confidence'] = 'Medium'
                signal['strength'] = 4
            elif normalized_score < -0.5:
                signal['direction'] = 'MILD SELL'
                signal['confidence'] = 'Low'
                signal['strength'] = 2
            else:
                signal['direction'] = 'NEUTRAL'
                signal['confidence'] = 'Low'
                signal['strength'] = 1
            
            signal['weights'] = weights
            signal['normalized_score'] = normalized_score
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Error generating signal: {e}")
            return None
    
    def calculate_all_indicators(self):
        """Calculate all indicators and return combined results"""
        logger.info("\n" + "="*60)
        logger.info("📊 CALCULATING BTC INDICATORS (IMPROVED)")
        logger.info("="*60)
        
        # Fetch data with validation
        df = self.fetch_data(days=365)
        if df is None or df.empty:
            logger.error("❌ No data available")
            return None
        
        current_price = df['close'].iloc[-1]
        current_date = df['date'].iloc[-1]
        
        results = {
            'date': current_date.strftime('%Y-%m-%d'),
            'current_price': current_price,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 1. Support & Resistance (FIXED)
        logger.info("🔍 Calculating Support & Resistance...")
        sr = self.calculate_support_resistance(df)
        if sr:
            results['support_resistance'] = sr
        
        # 2. Liquidity (FIXED - renamed to Volume-based Liquidity Proxy)
        logger.info("💧 Calculating Volume-based Liquidity Proxy...")
        liquidity = self.calculate_liquidity(df)
        if liquidity:
            results['liquidity'] = liquidity
        
        # 3. Moving Averages (FIXED)
        logger.info("📈 Calculating Moving Averages...")
        ma = self.calculate_moving_averages(df)
        if ma:
            results['moving_averages'] = ma
        
        # 4. RSI (FIXED - Wilder's smoothing)
        logger.info("📊 Calculating RSI...")
        rsi = self.calculate_rsi(df)
        if rsi:
            results['rsi'] = rsi
        
        # 5. MACD
        logger.info("📊 Calculating MACD...")
        macd = self.calculate_macd(df)
        if macd:
            results['macd'] = macd
        
        # 6. Bollinger Bands (FIXED - historical percentile)
        logger.info("📊 Calculating Bollinger Bands...")
        bb = self.calculate_bollinger_bands(df)
        if bb:
            results['bollinger_bands'] = bb
        
        # 7. ATR (FIXED - historical percentile)
        logger.info("📊 Calculating ATR...")
        atr = self.calculate_atr(df)
        if atr:
            results['atr'] = atr
        
        # 8. Fibonacci (FIXED - swing based + ATR proximity)
        logger.info("📊 Calculating Fibonacci...")
        fib = self.calculate_fibonacci(df)
        if fib:
            results['fibonacci'] = fib
        
        # 9. Pivot Points
        logger.info("📊 Calculating Pivot Points...")
        pivot = self.calculate_pivot_points(df)
        if pivot:
            results['pivot_points'] = pivot
        
        # 10. Market Structure (NEW)
        logger.info("📊 Calculating Market Structure...")
        structure = self.calculate_market_structure(df)
        if structure:
            results['market_structure'] = structure
        
        # 11. Overall Signal (FIXED - weighted confluence)
        logger.info("🎯 Generating Overall Signal...")
        signal = self.generate_signal(results)
        results['overall_signal'] = signal
        
        logger.info("✅ All indicators calculated successfully!")
        return results
    
    def print_results(self, results):
        """Print formatted results"""
        if not results:
            return
        
        print("\n" + "="*80)
        print(f"📊 BTC INDICATORS REPORT (IMPROVED)")
        print("="*80)
        print(f"📅 Date: {results['date']}")
        print(f"💰 Current Price: ${results['current_price']:,.2f}")
        print(f"⏰ Generated: {results['timestamp']}")
        print("="*80)
        
        # Market Structure
        if 'market_structure' in results:
            structure = results['market_structure']
            print(f"\n📊 MARKET STRUCTURE: {structure.get('trend_regime', 'Unknown')}")
        
        # Support & Resistance
        if 'support_resistance' in results:
            sr = results['support_resistance']
            print("\n🎯 SUPPORT & RESISTANCE")
            print("-"*80)
            
            if sr['nearest_support']:
                print(f"  Nearest Support: ${sr['nearest_support']['price']:,.2f} (Strength: {sr['nearest_support']['strength']})")
            if sr['nearest_resistance']:
                print(f"  Nearest Resistance: ${sr['nearest_resistance']['price']:,.2f} (Strength: {sr['nearest_resistance']['strength']})")
        
        # Moving Averages
        if 'moving_averages' in results:
            print("\n📈 MOVING AVERAGES")
            print("-"*80)
            for period, data in results['moving_averages'].items():
                print(f"  {period}: ${data['value']:,.2f} (Trend: {data['trend']}, Slope: {data['slope']:.2f}%)")
        
        # Overall Signal
        if 'overall_signal' in results:
            signal = results['overall_signal']
            print("\n" + "="*80)
            print(f"🎯 OVERALL SIGNAL: {signal['direction']}")
            print(f"   Score: {signal.get('normalized_score', signal['score']):.2f}")
            print(f"   Confidence: {signal.get('confidence', 'N/A')}")
            print("="*80)
            print("\nFactors:")
            for factor in signal['factors']:
                print(f"  • {factor}")
            print("="*80 + "\n")
    
    def save_to_db(self, results):
        """Save indicators to database for backtesting"""
        try:
            self.ensure_connection()
            
            # Create table if not exists
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS indicators_history (
                    date DATE PRIMARY KEY,
                    signal_direction VARCHAR(20),
                    signal_score DECIMAL(10, 4),
                    signal_confidence VARCHAR(10),
                    rsi DECIMAL(10, 4),
                    macd DECIMAL(10, 4),
                    atr DECIMAL(10, 4),
                    trend_regime VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert data
            date = results['date']
            signal = results['overall_signal']
            
            self.cursor.execute("""
                INSERT INTO indicators_history 
                (date, signal_direction, signal_score, signal_confidence, rsi, macd, atr, trend_regime)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                signal_direction = VALUES(signal_direction),
                signal_score = VALUES(signal_score),
                signal_confidence = VALUES(signal_confidence),
                rsi = VALUES(rsi),
                macd = VALUES(macd),
                atr = VALUES(atr),
                trend_regime = VALUES(trend_regime)
            """, (
                date,
                signal['direction'],
                signal.get('normalized_score', signal['score']),
                signal.get('confidence', 'Low'),
                results['rsi']['value'] if 'rsi' in results else None,
                results['macd']['macd'] if 'macd' in results else None,
                results['atr']['atr'] if 'atr' in results else None,
                results.get('market_structure', {}).get('trend_regime', None)
            ))
            
            self.conn.commit()
            logger.info("✅ Indicators saved to database for backtesting")
            
        except Exception as e:
            logger.error(f"❌ Error saving indicators to DB: {e}")
    
    def close(self):
        """Close connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("🔒 Connection closed")

def main():
    """Main function"""
    indicator = BTCIndicators()
    
    try:
        # Calculate all indicators
        results = indicator.calculate_all_indicators()
        
        if results:
            # Print results
            indicator.print_results(results)
            
            # Save to JSON
            indicator.save_to_json(results)
            
            # Save to database for backtesting
            indicator.save_to_db(results)
            
            print("✅ Indicators calculation completed!")
        else:
            print("❌ Failed to calculate indicators")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        indicator.close()

if __name__ == "__main__":
    main()