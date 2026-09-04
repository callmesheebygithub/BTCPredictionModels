# data/pipeline.py
"""
Data Pipeline - Manages data loading and updates - FIXED
"""

from database.db_manager import DatabaseManager
from data.yahoo_fetcher import YahooFetcher  # FIXED: Changed from YahooDataFetcher
from datetime import datetime, timedelta

class DataPipeline:
    def __init__(self):
        self.db = DatabaseManager()
        self.fetcher = YahooFetcher()  # FIXED: Changed from YahooDataFetcher
    
    def initial_load(self):
        """Initial data load from Yahoo"""
        print("[INFO] Initial data load from Yahoo...")
        
        if self.db.get_count() > 0:
            print("[INFO] Database already has data, checking for updates...")
            return self.daily_update()
        
        start_date = '2014-09-17'
        end_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        
        df = self.fetcher.fetch(start_date, end_date)
        
        if df is not None and not df.empty:
            self.db.insert_data(df)
            print(f"[OK] Initial data loaded: {len(df)} records")
            return True
        return False
    
    def daily_update(self):
        """Daily update from Yahoo - FIXED: includes current date"""
        print("[INFO] Checking for new data from Yahoo...")
        last_date = self.db.get_last_date()
        
        if not last_date:
            print("[WARN] No data in database, running initial load...")
            return self.initial_load()
        
        # FIXED: Fetch from 2 days before last date to ensure no gaps
        start_date = (datetime.strptime(last_date, '%Y-%m-%d') - timedelta(days=2)).strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        
        print(f"[INFO] Checking data from {start_date} to {end_date}")
        
        df = self.fetcher.fetch(start_date, end_date)
        
        if df is not None and not df.empty:
            existing_dates = set(self.db.get_all_data()['date'])
            df = df[~df['date'].isin(existing_dates)]
            
            if not df.empty:
                self.db.insert_data(df)
                print(f"[OK] Added {len(df)} new records")
                print(f"[OK] New date range: {df['date'].min()} to {df['date'].max()}")
                
                # Check if today's data is included
                today = datetime.now().strftime('%Y-%m-%d')
                if today in df['date'].values:
                    print(f"[OK] ✅ Today's data ({today}) fetched successfully!")
                else:
                    print(f"[WARN] Today's data ({today}) not yet available (market may be open)")
                
                return True
            else:
                print("[INFO] No new data to add (already up to date)")
                return True
        
        print("[WARN] No data fetched")
        return False
    
    def force_update(self):
        """Force update - fetch last 10 days"""
        print("[INFO] Force updating last 10 days...")
        start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        
        df = self.fetcher.fetch(start_date, end_date)
        
        if df is not None and not df.empty:
            # Get existing dates
            existing_df = self.db.get_all_data()
            if not existing_df.empty:
                existing_dates = set(existing_df['date'])
                new_data = df[~df['date'].isin(existing_dates)]
            else:
                new_data = df
            
            if not new_data.empty:
                self.db.insert_data(new_data)
                print(f"[OK] Added {len(new_data)} new records")
                print(f"[OK] Date range: {new_data['date'].min()} to {new_data['date'].max()}")
                return True
            else:
                print("[INFO] No new data to add")
                return True
        
        return False