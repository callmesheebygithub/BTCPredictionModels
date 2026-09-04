"""
YAHOO-ONLY DAILY UPDATE SYSTEM
Consistent data from Yahoo Finance only
"""

import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import schedule
import time
import os

class YahooDailyUpdater:
    """Daily update using Yahoo Finance only"""
    
    def __init__(self, db_path='btc_data.db'):
        self.db_path = db_path
        self.symbol = 'BTC-USD'
        self.create_tables()
    
    def create_tables(self):
        """Create tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS btc_daily (
                date TEXT PRIMARY KEY,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                predicted_close REAL,
                actual_close REAL,
                error_percentage REAL,
                absolute_error REAL,
                direction_correct INTEGER,
                model_version TEXT,
                timestamp TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                period TEXT,
                avg_error REAL,
                avg_abs_error REAL,
                direction_accuracy REAL,
                total_predictions INTEGER,
                model_version TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_last_date(self):
        """Get last date in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(date) FROM btc_daily')
        result = cursor.fetchone()[0]
        conn.close()
        return result
    
    def get_all_data(self):
        """Get all data from database"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query('SELECT * FROM btc_daily ORDER BY date', conn)
        conn.close()
        return df
    
    def get_count(self):
        """Get total records count"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM btc_daily')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def fetch_yahoo_data(self, start_date, end_date):
        """
        Fetch data from Yahoo Finance
        """
        try:
            print(f"📥 Fetching data from Yahoo Finance...")
            print(f"   From: {start_date} to {end_date}")
            
            # Download data
            df = yf.download(self.symbol, start=start_date, end=end_date, progress=False)
            
            if df.empty:
                print("❌ No data received from Yahoo Finance")
                return None
            
            # Format for database
            df = df.reset_index()
            df['date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
            df = df[['date', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            
            # Remove rows with NaN values
            df = df.dropna()
            
            print(f"✅ Downloaded {len(df)} records from Yahoo Finance")
            return df
            
        except Exception as e:
            print(f"❌ Yahoo Finance error: {e}")
            return None
    
    def daily_update(self):
        """
        Daily update - fetch only new data from Yahoo
        """
        print("\n" + "="*60)
        print(f"🔄 DAILY UPDATE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Check last date in database
        last_date = self.get_last_date()
        
        if not last_date:
            print("⚠️ No data in database! Please run full load first.")
            return False
        
        print(f"📅 Last date in database: {last_date}")
        
        # Calculate start date (day after last date)
        start_date = (datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')  # Include today
        
        print(f"📥 Fetching new data from {start_date} to {end_date}...")
        
        # Fetch new data from Yahoo
        df = self.fetch_yahoo_data(start_date, end_date)
        
        if df is None:
            print("❌ Failed to fetch new data")
            return False
        
        # Filter only new data (after last_date)
        new_data = df[df['date'] > last_date]
        
        if new_data.empty:
            print("ℹ️ No new data available")
            return True
        
        # Save to database
        print(f"\n💾 Adding {len(new_data)} new records to database...")
        
        conn = sqlite3.connect(self.db_path)
        new_data.to_sql('btc_daily', conn, if_exists='append', index=False)
        conn.close()
        
        print(f"✅ Added {len(new_data)} new records")
        print(f"   Date range: {new_data['date'].min()} to {new_data['date'].max()}")
        
        # Show latest data
        print(f"\n📋 Latest data added:")
        print(new_data.tail().to_string(index=False))
        
        # Verify update
        new_count = self.get_count()
        print(f"\n📊 Total records now: {new_count}")
        
        return True
    
    def full_load(self, start_date='2014-09-17'):
        """
        Full load from 2014
        """
        print("\n" + "="*60)
        print("🔄 FULL LOAD (Yahoo Only)")
        print("="*60)
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"📥 Fetching data from {start_date} to {end_date}...")
        print("   This may take a few minutes...")
        
        df = self.fetch_yahoo_data(start_date, end_date)
        
        if df is None:
            print("❌ Failed to fetch data")
            return False
        
        # Save to database
        print(f"\n💾 Saving {len(df)} records to database...")
        
        conn = sqlite3.connect(self.db_path)
        df.to_sql('btc_daily', conn, if_exists='replace', index=False)
        conn.close()
        
        print(f"✅ Data saved to database!")
        print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"   Total records: {len(df)}")
        
        return True
    
    def check_data_status(self):
        """Check current data status"""
        print("\n" + "="*60)
        print("📊 DATA STATUS CHECK")
        print("="*60)
        
        count = self.get_count()
        
        if count == 0:
            print("❌ Database is empty!")
            return
        
        df = self.get_all_data()
        last_date = df['date'].max()
        today = datetime.now().strftime('%Y-%m-%d')
        
        print(f"  • Total Records: {count}")
        print(f"  • Date Range: {df['date'].min()} to {last_date}")
        print(f"  • Latest Price: ${df['close'].iloc[-1]:,.2f}")
        
        # Check if data is up to date
        if last_date == today:
            print(f"  • Status: ✅ Up to date (today: {today})")
        elif datetime.strptime(last_date, '%Y-%m-%d') < datetime.now() - timedelta(days=1):
            days_behind = (datetime.now() - datetime.strptime(last_date, '%Y-%m-%d')).days
            print(f"  • Status: ⚠️ {days_behind} days behind")
        else:
            print(f"  • Status: ℹ️ Yesterday's data available")
        
        # Show last 5 days
        print(f"\n📋 Last 5 days:")
        print(df.tail(5).to_string(index=False))
        
        print("="*60 + "\n")

# ============================================
# AUTO-UPDATE SCHEDULER
# ============================================

class AutoUpdater:
    """Automatic daily updater"""
    
    def __init__(self):
        self.updater = YahooDailyUpdater()
    
    def run_daily_update(self):
        """Run daily update"""
        self.updater.daily_update()
    
    def schedule_updates(self, update_time="00:30"):
        """
        Schedule daily updates at specific time
        Default: 00:30 UTC (after market close)
        """
        print(f"📅 Scheduling daily updates at {update_time} UTC")
        
        # Schedule daily update
        schedule.every().day.at(update_time).do(self.run_daily_update)
        
        print("✅ Auto-updater is running!")
        print(f"   Next update: {schedule.next_run()}")
        print("   Press Ctrl+C to stop\n")
        
        # Run once immediately if needed
        choice = input("Run update now? (y/n): ").strip().lower()
        if choice == 'y':
            self.run_daily_update()
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

# ============================================
# MAIN
# ============================================

def main():
    """Main function"""
    
    print("\n🚀 YAHOO DAILY UPDATER")
    print("="*60)
    
    updater = YahooDailyUpdater()
    count = updater.get_count()
    
    if count == 0:
        print("📭 Database is empty!")
        print("\nOptions:")
        print("  1. Full load from 2014")
        print("  2. Exit")
        choice = input("Enter choice (1/2): ").strip()
        
        if choice == '1':
            updater.full_load()
        else:
            return
    
    # Show menu
    while True:
        print("\n" + "="*60)
        print("📊 YAHOO DAILY UPDATER MENU")
        print("="*60)
        print("  1. 🔄 Daily Update (fetch new data)")
        print("  2. 📊 Check Data Status")
        print("  3. 🔄 Full Reload (from 2014)")
        print("  4. ⏰ Start Auto-Updater (scheduled daily)")
        print("  5. ❌ Exit")
        print("="*60)
        
        choice = input("Enter choice (1-5): ").strip()
        
        if choice == '1':
            updater.daily_update()
        elif choice == '2':
            updater.check_data_status()
        elif choice == '3':
            confirm = input("⚠️ This will replace ALL data. Continue? (yes/no): ")
            if confirm.lower() == 'yes':
                updater.full_load()
        elif choice == '4':
            auto = AutoUpdater()
            auto.schedule_updates("00:30")
        elif choice == '5':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice!")
        
        input("\nPress Enter to continue...")

# ============================================
# STANDALONE DAILY UPDATE
# ============================================

def daily_update_only():
    """Run daily update only (for cron jobs)"""
    updater = YahooDailyUpdater()
    updater.daily_update()

if __name__ == "__main__":
    # Install yfinance if not present
    try:
        import yfinance
    except ImportError:
        print("📦 Installing yfinance...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'yfinance'])
        print("✅ yfinance installed!")
    
    main()