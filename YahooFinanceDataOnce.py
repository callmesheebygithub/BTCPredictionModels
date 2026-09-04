"""
fetch_and_store.py - Fetch BTC data from Yahoo Finance and store in MySQL
"""

import mysql.connector
from mysql.connector import Error
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
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
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BitcoinDataFetcher:
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
    
    def fetch_btc_data(self, start_date='2014-09-17', end_date=None):
        """Fetch Bitcoin data from Yahoo Finance"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"📥 Fetching BTC data from {start_date} to {end_date}")
        
        try:
            btc = yf.Ticker("BTC-USD")
            df = btc.history(start=start_date, end=end_date)
            
            if df.empty:
                logger.warning("⚠️ No data fetched")
                return None
            
            logger.info(f"✅ Fetched {len(df)} records")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error fetching data: {e}")
            return None
    
    def clean_data(self, df):
        """Clean data for database insertion"""
        try:
            df = df.reset_index()
            df.columns = df.columns.str.lower()
            df['date'] = pd.to_datetime(df['date']).dt.date
            
            # Keep only required columns
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
            
            # Remove duplicates
            df = df.drop_duplicates(subset=['date'])
            
            # Remove null values
            df = df.dropna()
            
            # Convert volume to integer
            df['volume'] = df['volume'].astype('int64')
            
            logger.info(f"✅ Cleaned {len(df)} records")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error cleaning data: {e}")
            return None
    
    def store_data(self, df):
        """Store data in database"""
        if df is None or df.empty:
            logger.warning("⚠️ No data to store")
            return False
        
        try:
            inserted = 0
            updated = 0
            
            for _, row in df.iterrows():
                # Check if record exists
                self.cursor.execute(
                    "SELECT id FROM btc_price_history WHERE date = %s",
                    (row['date'].isoformat(),)
                )
                existing = self.cursor.fetchone()
                
                if existing:
                    # Update
                    self.cursor.execute('''
                        UPDATE btc_price_history 
                        SET open = %s, high = %s, low = %s, close = %s, volume = %s
                        WHERE date = %s
                    ''', (
                        float(row['open']), float(row['high']), 
                        float(row['low']), float(row['close']), 
                        int(row['volume']), row['date'].isoformat()
                    ))
                    updated += 1
                else:
                    # Insert
                    self.cursor.execute('''
                        INSERT INTO btc_price_history 
                        (date, open, high, low, close, volume)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (
                        row['date'].isoformat(), 
                        float(row['open']), float(row['high']), 
                        float(row['low']), float(row['close']), 
                        int(row['volume'])
                    ))
                    inserted += 1
            
            self.conn.commit()
            logger.info(f"✅ Stored: {inserted} inserted, {updated} updated")
            return True
            
        except Error as e:
            logger.error(f"❌ Error storing data: {e}")
            self.conn.rollback()
            return False
    
    def get_last_date(self):
        """Get last date in database"""
        try:
            self.cursor.execute("SELECT MAX(date) FROM btc_price_history")
            result = self.cursor.fetchone()
            return result[0] if result and result[0] else None
        except:
            return None
    
    def close(self):
        """Close connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("🔒 Connection closed")

def main():
    """Main function"""
    fetcher = BitcoinDataFetcher()
    
    if not fetcher.conn:
        return
    
    # Check last date
    last_date = fetcher.get_last_date()
    
    if last_date:
        start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
        logger.info(f"📅 Found data till {last_date}. Fetching from {start_date}")
    else:
        start_date = '2014-09-17'
        logger.info(f"📅 No data found. Starting from {start_date}")
    
    # Fetch data
    df = fetcher.fetch_btc_data(start_date=start_date)
    
    if df is not None and not df.empty:
        # Clean data
        cleaned_df = fetcher.clean_data(df)
        
        if cleaned_df is not None and not cleaned_df.empty:
            # Store data
            fetcher.store_data(cleaned_df)
    
    fetcher.close()

if __name__ == "__main__":
    main()