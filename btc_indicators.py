"""
btc_indicators.py - BTC Technical Indicators Calculator
Calculates Support, Resistance, Liquidity, and other important indicators
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
        logging.FileHandler('btc_indicators.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BTCIndicators:
    def __init__(self):
        """Initialize database connection"""
        self.conn = None
        self.cursor = None
        self.connect()
    
    def connect(self):
        """Connect to MySQL database"""
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
            return False
    
    def fetch_data(self, days=365):
        """Fetch BTC data from database"""
        try:
            query = f"""
                SELECT date, open, high, low, close, volume 
                FROM btc_price_history 
                ORDER BY date DESC 
                LIMIT {days}
            """
            df = pd.read_sql_query(query, self.conn)
            df = df.sort_values('date')
            df = df.reset_index(drop=True)
            logger.info(f"✅ Fetched {len(df)} records")
            return df
            
        except Error as e:
            logger.error(f"❌ Error fetching data: {e}")
            return None
    
    def calculate_support_resistance(self, df, lookback=100):
        """Calculate Support and Resistance levels"""
        try:
            # Get recent data
            recent_df = df.tail(lookback)
            
            # Find swing highs and lows
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
            
            # Group similar levels
            def group_levels(levels, threshold_pct=0.02):
                if not levels:
                    return []
                
                levels = sorted(levels, key=lambda x: x['price'])
                grouped = []
                current_group = [levels[0]]
                
                for level in levels[1:]:
                    if (level['price'] - current_group[-1]['price']) / current_group[-1]['price'] * 100 < threshold_pct:
                        current_group.append(level)
                    else:
                        # Average the group
                        avg_price = sum([x['price'] for x in current_group]) / len(current_group)
                        grouped.append({
                            'price': avg_price,
                            'strength': len(current_group),
                            'dates': [x['date'] for x in current_group]
                        })
                        current_group = [level]
                
                # Add last group
                if current_group:
                    avg_price = sum([x['price'] for x in current_group]) / len(current_group)
                    grouped.append({
                        'price': avg_price,
                        'strength': len(current_group),
                        'dates': [x['date'] for x in current_group]
                    })
                
                return grouped
            
            support_levels = group_levels(lows, 0.02)
            resistance_levels = group_levels(highs, 0.02)
            
            # Sort by strength (number of touches)
            support_levels = sorted(support_levels, key=lambda x: x['strength'], reverse=True)
            resistance_levels = sorted(resistance_levels, key=lambda x: x['strength'], reverse=True)
            
            # Get current price
            current_price = df['close'].iloc[-1]
            
            # Find nearest support and resistance
            nearest_support = None
            nearest_resistance = None
            
            for support in support_levels:
                if support['price'] < current_price:
                    nearest_support = support
                    break
            
            for resistance in resistance_levels:
                if resistance['price'] > current_price:
                    nearest_resistance = resistance
                    break
            
            return {
                'current_price': current_price,
                'support_levels': support_levels[:5],  # Top 5 supports
                'resistance_levels': resistance_levels[:5],  # Top 5 resistances
                'nearest_support': nearest_support,
                'nearest_resistance': nearest_resistance
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating support/resistance: {e}")
            return None
    
    def calculate_liquidity(self, df):
        """Calculate Liquidity indicators"""
        try:
            # Volume indicators
            avg_volume = df['volume'].mean()
            recent_volume = df['volume'].iloc[-30:].mean()
            
            # Volume profile (where most volume traded)
            volume_profile = df.groupby(pd.cut(df['close'], bins=10))['volume'].sum()
            
            # High volume nodes
            volume_nodes = []
            for interval in volume_profile.index:
                price_range = interval
                volume = volume_profile[interval]
                if volume > avg_volume * 1.5:  # High volume nodes
                    volume_nodes.append({
                        'price_range': f"${price_range.left:,.0f} - ${price_range.right:,.0f}",
                        'volume': volume,
                        'avg_price': (price_range.left + price_range.right) / 2
                    })
            
            # Order book liquidity (estimated)
            # Based on volume and price levels
            liquidity_levels = []
            for i in range(5, len(df), 10):
                price = df['close'].iloc[i]
                volume = df['volume'].iloc[i]
                liquidity_score = volume / avg_volume
                if liquidity_score > 1.5:
                    liquidity_levels.append({
                        'price': price,
                        'volume': volume,
                        'liquidity_score': liquidity_score
                    })
            
            return {
                'avg_volume_30d': recent_volume,
                'avg_volume_overall': avg_volume,
                'volume_ratio': recent_volume / avg_volume if avg_volume > 0 else 0,
                'high_volume_nodes': sorted(volume_nodes, key=lambda x: x['volume'], reverse=True)[:5],
                'liquidity_levels': sorted(liquidity_levels, key=lambda x: x['liquidity_score'], reverse=True)[:10]
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating liquidity: {e}")
            return None
    
    def calculate_moving_averages(self, df):
        """Calculate all important moving averages"""
        try:
            periods = [7, 20, 50, 100, 200]
            ma_data = {}
            
            for period in periods:
                ma = df['close'].rolling(window=period).mean()
                ma_data[f'MA_{period}'] = {
                    'value': ma.iloc[-1],
                    'trend': 'Bullish' if ma.iloc[-1] > ma.iloc[-5] else 'Bearish',
                    'period': period
                }
            
            return ma_data
            
        except Exception as e:
            logger.error(f"❌ Error calculating moving averages: {e}")
            return None
    
    def calculate_rsi(self, df, period=14):
        """Calculate RSI indicator"""
        try:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
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
        """Calculate Bollinger Bands"""
        try:
            sma = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()
            
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)
            
            current_price = df['close'].iloc[-1]
            current_upper = upper_band.iloc[-1]
            current_middle = sma.iloc[-1]
            current_lower = lower_band.iloc[-1]
            
            # Determine position
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
                'squeeze': 'Yes' if (current_upper - current_lower) / current_middle < 0.1 else 'No'
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating Bollinger Bands: {e}")
            return None
    
    def calculate_atr(self, df, period=14):
        """Calculate Average True Range (Volatility)"""
        try:
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            atr = true_range.rolling(period).mean()
            
            current_atr = atr.iloc[-1]
            current_price = df['close'].iloc[-1]
            
            return {
                'atr': current_atr,
                'atr_percent': (current_atr / current_price) * 100,
                'period': period,
                'volatility_status': 'High' if (current_atr / current_price) * 100 > 2 else 'Normal' if (current_atr / current_price) * 100 > 1 else 'Low'
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating ATR: {e}")
            return None
    
    def calculate_fibonacci(self, df, lookback=30):
        """Calculate Fibonacci retracement levels"""
        try:
            recent_df = df.tail(lookback)
            high = recent_df['high'].max()
            low = recent_df['low'].min()
            diff = high - low
            
            fib_levels = {
                '0.0': high,
                '0.236': high - diff * 0.236,
                '0.382': high - diff * 0.382,
                '0.5': high - diff * 0.5,
                '0.618': high - diff * 0.618,
                '0.786': high - diff * 0.786,
                '1.0': low
            }
            
            current_price = df['close'].iloc[-1]
            
            # Find current fib level
            current_fib = None
            for level, price in fib_levels.items():
                if abs(current_price - price) / diff < 0.05:  # Within 5% of fib level
                    current_fib = level
                    break
            
            return {
                'high': high,
                'low': low,
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
            # Get previous day's data
            prev_day = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
            
            H = prev_day['high']
            L = prev_day['low']
            C = prev_day['close']
            
            # Classic Pivot Points
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
    
    def calculate_all_indicators(self):
        """Calculate all indicators and return combined results"""
        logger.info("\n" + "="*60)
        logger.info("📊 CALCULATING BTC INDICATORS")
        logger.info("="*60)
        
        # Fetch data
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
        
        # 1. Support & Resistance
        logger.info("🔍 Calculating Support & Resistance...")
        sr = self.calculate_support_resistance(df)
        if sr:
            results['support_resistance'] = sr
        
        # 2. Liquidity
        logger.info("💧 Calculating Liquidity...")
        liquidity = self.calculate_liquidity(df)
        if liquidity:
            results['liquidity'] = liquidity
        
        # 3. Moving Averages
        logger.info("📈 Calculating Moving Averages...")
        ma = self.calculate_moving_averages(df)
        if ma:
            results['moving_averages'] = ma
        
        # 4. RSI
        logger.info("📊 Calculating RSI...")
        rsi = self.calculate_rsi(df)
        if rsi:
            results['rsi'] = rsi
        
        # 5. MACD
        logger.info("📊 Calculating MACD...")
        macd = self.calculate_macd(df)
        if macd:
            results['macd'] = macd
        
        # 6. Bollinger Bands
        logger.info("📊 Calculating Bollinger Bands...")
        bb = self.calculate_bollinger_bands(df)
        if bb:
            results['bollinger_bands'] = bb
        
        # 7. ATR (Volatility)
        logger.info("📊 Calculating ATR...")
        atr = self.calculate_atr(df)
        if atr:
            results['atr'] = atr
        
        # 8. Fibonacci
        logger.info("📊 Calculating Fibonacci...")
        fib = self.calculate_fibonacci(df)
        if fib:
            results['fibonacci'] = fib
        
        # 9. Pivot Points
        logger.info("📊 Calculating Pivot Points...")
        pivot = self.calculate_pivot_points(df)
        if pivot:
            results['pivot_points'] = pivot
        
        # 10. Overall Signal
        logger.info("🎯 Generating Overall Signal...")
        signal = self.generate_signal(results)
        results['overall_signal'] = signal
        
        logger.info("✅ All indicators calculated successfully!")
        return results
    
    def generate_signal(self, results):
        """Generate overall buy/sell signal based on all indicators"""
        try:
            signal = {
                'direction': 'NEUTRAL',
                'strength': 0,
                'factors': []
            }
            
            score = 0
            
            # RSI Signal
            if 'rsi' in results:
                rsi_value = results['rsi']['value']
                if rsi_value > 70:
                    signal['factors'].append('RSI Overbought')
                    score -= 2
                elif rsi_value < 30:
                    signal['factors'].append('RSI Oversold')
                    score += 2
                else:
                    signal['factors'].append('RSI Neutral')
            
            # MACD Signal
            if 'macd' in results:
                if results['macd']['signal_status'] == 'Bullish':
                    signal['factors'].append('MACD Bullish')
                    score += 2
                else:
                    signal['factors'].append('MACD Bearish')
                    score -= 2
            
            # Moving Averages Signal
            if 'moving_averages' in results:
                bullish_count = 0
                for ma in results['moving_averages'].values():
                    if ma['trend'] == 'Bullish':
                        bullish_count += 1
                
                if bullish_count >= 3:
                    signal['factors'].append(f'MA Bullish ({bullish_count}/5)')
                    score += 1
                else:
                    signal['factors'].append(f'MA Bearish ({5-bullish_count}/5)')
                    score -= 1
            
            # Bollinger Bands Signal
            if 'bollinger_bands' in results:
                position = results['bollinger_bands']['position']
                if position == 'Below Lower Band':
                    signal['factors'].append('BB Oversold')
                    score += 1
                elif position == 'Above Upper Band':
                    signal['factors'].append('BB Overbought')
                    score -= 1
                else:
                    signal['factors'].append('BB Neutral')
            
            # Determine final signal
            if score >= 4:
                signal['direction'] = 'STRONG BUY'
                signal['strength'] = 5
            elif score >= 2:
                signal['direction'] = 'BUY'
                signal['strength'] = 3
            elif score <= -4:
                signal['direction'] = 'STRONG SELL'
                signal['strength'] = 5
            elif score <= -2:
                signal['direction'] = 'SELL'
                signal['strength'] = 3
            else:
                signal['direction'] = 'NEUTRAL'
                signal['strength'] = 1
            
            signal['score'] = score
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Error generating signal: {e}")
            return None
    
    def print_results(self, results):
        """Print formatted results"""
        if not results:
            return
        
        print("\n" + "="*80)
        print(f"📊 BTC INDICATORS REPORT")
        print("="*80)
        print(f"📅 Date: {results['date']}")
        print(f"💰 Current Price: ${results['current_price']:,.2f}")
        print(f"⏰ Generated: {results['timestamp']}")
        print("="*80)
        
        # Support & Resistance
        if 'support_resistance' in results:
            sr = results['support_resistance']
            print("\n🎯 SUPPORT & RESISTANCE")
            print("-"*80)
            
            print(f"  Nearest Support: ${sr['nearest_support']['price']:,.2f} (Strength: {sr['nearest_support']['strength']})" if sr['nearest_support'] else "  Nearest Support: None")
            print(f"  Nearest Resistance: ${sr['nearest_resistance']['price']:,.2f} (Strength: {sr['nearest_resistance']['strength']})" if sr['nearest_resistance'] else "  Nearest Resistance: None")
            
            print("\n  Top Support Levels:")
            for i, support in enumerate(sr['support_levels'][:3], 1):
                print(f"    {i}. ${support['price']:,.2f} (Touches: {support['strength']})")
            
            print("\n  Top Resistance Levels:")
            for i, resistance in enumerate(sr['resistance_levels'][:3], 1):
                print(f"    {i}. ${resistance['price']:,.2f} (Touches: {resistance['strength']})")
        
        # Moving Averages
        if 'moving_averages' in results:
            print("\n📈 MOVING AVERAGES")
            print("-"*80)
            for period, data in results['moving_averages'].items():
                print(f"  {period}: ${data['value']:,.2f} ({data['trend']})")
        
        # RSI
        if 'rsi' in results:
            rsi = results['rsi']
            print(f"\n📊 RSI ({rsi['period']} days): {rsi['value']:.2f} ({rsi['status']})")
        
        # MACD
        if 'macd' in results:
            macd = results['macd']
            print(f"\n📊 MACD: {macd['signal_status']} (Signal: {macd['signal']:.2f})")
        
        # Bollinger Bands
        if 'bollinger_bands' in results:
            bb = results['bollinger_bands']
            print("\n📊 BOLLINGER BANDS")
            print("-"*80)
            print(f"  Upper: ${bb['upper_band']:,.2f}")
            print(f"  Middle: ${bb['middle_band']:,.2f}")
            print(f"  Lower: ${bb['lower_band']:,.2f}")
            print(f"  Position: {bb['position']}")
            print(f"  Squeeze: {bb['squeeze']}")
        
        # ATR (Volatility)
        if 'atr' in results:
            atr = results['atr']
            print(f"\n📊 ATR ({atr['period']} days): ${atr['atr']:,.2f} ({atr['volatility_status']} Volatility)")
        
        # Fibonacci
        if 'fibonacci' in results:
            fib = results['fibonacci']
            print("\n📊 FIBONACCI LEVELS")
            print("-"*80)
            for level, price in fib['fib_levels'].items():
                print(f"  {level}: ${price:,.2f}")
            if fib['current_fib_level']:
                print(f"  Current Level: {fib['current_fib_level']}")
        
        # Pivot Points
        if 'pivot_points' in results:
            pivot = results['pivot_points']
            print("\n📊 PIVOT POINTS")
            print("-"*80)
            print(f"  Pivot: ${pivot['pivot']:,.2f}")
            print(f"  R1: ${pivot['resistance_1']:,.2f} | S1: ${pivot['support_1']:,.2f}")
            print(f"  R2: ${pivot['resistance_2']:,.2f} | S2: ${pivot['support_2']:,.2f}")
            print(f"  R3: ${pivot['resistance_3']:,.2f} | S3: ${pivot['support_3']:,.2f}")
            print(f"  Position: {pivot['current_position']}")
        
        # Liquidity
        if 'liquidity' in results:
            liq = results['liquidity']
            print("\n💧 LIQUIDITY")
            print("-"*80)
            print(f"  30-Day Avg Volume: {liq['avg_volume_30d']:,.0f}")
            print(f"  Volume Ratio: {liq['volume_ratio']:.2f}x")
            
            print("\n  High Volume Nodes:")
            for i, node in enumerate(liq['high_volume_nodes'][:3], 1):
                print(f"    {i}. {node['price_range']} - Volume: {node['volume']:,.0f}")
        
        # Overall Signal
        if 'overall_signal' in results:
            signal = results['overall_signal']
            print("\n" + "="*80)
            print(f"🎯 OVERALL SIGNAL: {signal['direction']} (Score: {signal['score']})")
            print("="*80)
            print("\nFactors:")
            for factor in signal['factors']:
                print(f"  • {factor}")
            print("="*80 + "\n")
    
    def save_to_json(self, results, filename=None):
        """Save results to JSON file"""
        if not results:
            return
        
        if filename is None:
            filename = f"btc_indicators_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Convert numpy types to Python types
        def convert_to_serializable(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, pd.Timestamp):
                return obj.strftime('%Y-%m-%d')
            else:
                return obj
        
        # Serialize and save
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, default=convert_to_serializable, indent=2)
            logger.info(f"✅ Results saved to {filename}")
        except Exception as e:
            logger.error(f"❌ Error saving to JSON: {e}")
    
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