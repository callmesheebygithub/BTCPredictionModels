"""
daily_btc_updater.py - Daily BTC Data Updater
Runs at 5:15 AM Pakistani time and updates previous day's BTC data
"""

import mysql.connector
from mysql.connector import Error
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
import schedule
from dotenv import load_dotenv
import os
import pytz

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
        logging.FileHandler('daily_btc_updater.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DailyBTCUpdater:
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
    
    def get_last_date(self):
        """Get last date in database"""
        try:
            self.cursor.execute("SELECT MAX(date) FROM btc_price_history")
            result = self.cursor.fetchone()
            return result[0] if result and result[0] else None
        except Error as e:
            logger.error(f"❌ Error getting last date: {e}")
            return None
    
    def fetch_btc_data(self, start_date, end_date):
        """Fetch Bitcoin data from Yahoo Finance"""
        try:
            logger.info(f"📥 Fetching BTC data from {start_date} to {end_date}")
            
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
                # Check if record exists (using date as primary key)
                self.cursor.execute(
                    "SELECT date FROM btc_price_history WHERE date = %s",
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
    
    def get_missing_dates(self):
        """Get missing dates between last record and yesterday"""
        try:
            last_date = self.get_last_date()
            
            if not last_date:
                # If no data, start from 2014-09-17
                start_date = datetime(2014, 9, 17).date()
            else:
                start_date = last_date + timedelta(days=1)
            
            # Yesterday's date
            yesterday = datetime.now().date() - timedelta(days=1)
            
            if start_date > yesterday:
                logger.info("ℹ️ Data is already up to date")
                return None
            
            logger.info(f"📅 Fetching data from {start_date} to {yesterday}")
            return start_date, yesterday
            
        except Exception as e:
            logger.error(f"❌ Error getting missing dates: {e}")
            return None
    
    def update_daily_data(self):
        """Main function to update daily data"""
        logger.info("\n" + "="*60)
        logger.info("🔄 STARTING DAILY UPDATE")
        logger.info("="*60)
        logger.info(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check connection
        if not self.conn:
            if not self.connect():
                logger.error("❌ Cannot connect to database")
                return False
        
        try:
            # Get missing dates
            date_range = self.get_missing_dates()
            
            if date_range is None:
                logger.info("ℹ️ No update needed")
                return True
            
            start_date, end_date = date_range
            
            # If only one day, fetch that day
            if start_date == end_date:
                fetch_start = start_date
                fetch_end = start_date + timedelta(days=1)
            else:
                fetch_start = start_date
                fetch_end = end_date + timedelta(days=1)
            
            # Fetch data
            df = self.fetch_btc_data(
                fetch_start.strftime('%Y-%m-%d'),
                fetch_end.strftime('%Y-%m-%d')
            )
            
            if df is not None and not df.empty:
                # Clean data
                cleaned_df = self.clean_data(df)
                
                if cleaned_df is not None and not cleaned_df.empty:
                    # Store data
                    self.store_data(cleaned_df)
                    
                    # Log success
                    logger.info(f"✅ Daily update completed successfully")
                    
                    # Show latest record
                    self.cursor.execute("""
                        SELECT date, open, close, volume 
                        FROM btc_price_history 
                        ORDER BY date DESC 
                        LIMIT 1
                    """)
                    latest = self.cursor.fetchone()
                    if latest:
                        logger.info(f"📊 Latest record: {latest[0]} | Close: ${latest[2]:,.2f} | Volume: {latest[3]:,}")
                    
                    return True
            else:
                logger.warning("⚠️ No data available for the specified date range")
                return False
                
        except Exception as e:
            logger.error(f"❌ Update failed: {e}")
            return False
        
        finally:
            logger.info("="*60 + "\n")
    
    def close(self):
        """Close connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("🔒 Connection closed")

def run_update():
    """Wrapper function for scheduler"""
    updater = DailyBTCUpdater()
    try:
        updater.update_daily_data()
    finally:
        updater.close()

def schedule_daily_update():
    """Schedule daily update at 5:15 AM Pakistani time"""
    # Set Pakistani timezone
    pakistan_tz = pytz.timezone('Asia/Karachi')
    
    logger.info("="*60)
    logger.info("⏰ DAILY BTC UPDATER SCHEDULER")
    logger.info("="*60)
    logger.info(f"📍 Timezone: Asia/Karachi (Pakistani Time)")
    logger.info(f"🕐 Scheduled Time: 5:15 AM daily")
    logger.info(f"📅 Current Time: {datetime.now(pakistan_tz).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60 + "\n")
    
    # Schedule for 5:15 AM Pakistani time
    schedule.every().day.at("05:15").do(run_update)
    
    # Run once immediately if needed (optional)
    # Uncomment below to run once on start
    # run_update()
    
    logger.info("✅ Scheduler started. Waiting for 5:15 AM...")
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

def run_once():
    """Run update once immediately"""
    logger.info("🔄 Running update once...")
    run_update()

if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--once":
            # Run once and exit
            run_once()
            sys.exit(0)
        elif sys.argv[1] == "--help":
            print("""
Usage:
  python daily_btc_updater.py          # Start scheduler (runs at 5:15 AM daily)
  python daily_btc_updater.py --once   # Run update once and exit
  python daily_btc_updater.py --help   # Show this help
            """)
            sys.exit(0)
    
    # Start scheduler
    schedule_daily_update()