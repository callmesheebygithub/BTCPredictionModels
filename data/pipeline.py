# data/pipeline.py
"""
Data Pipeline - Manages data loading and updates
"""

from database.db_manager import DatabaseManager
from data.yahoo_fetcher import YahooDataFetcher
from datetime import datetime, timedelta

class DataPipeline:
    def __init__(self):
        self.db = DatabaseManager()
        self.fetcher = YahooDataFetcher()
    
    def initial_load(self):
        """Initial data load from Yahoo"""
        print("[INFO] Initial data load from Yahoo...")
        
        if self.db.get_count() > 0:
            print("[INFO] Database already has data, skipping initial load")
            return True
        
        start_date = '2014-09-17'
        df = self.fetcher.fetch_from_date(start_date)
        
        if df is not None and not df.empty:
            self.db.insert_data(df)
            print(f"[OK] Initial data loaded: {len(df)} records")
            return True
        return False
    
    def daily_update(self):
        """Daily update from Yahoo"""
        print("[INFO] Checking for new data from Yahoo...")
        last_date = self.db.get_last_date()
        
        if not last_date:
            print("[WARN] No data in database, running initial load...")
            return self.initial_load()
        
        start_date = (datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        df = self.fetcher.fetch_from_date(start_date, end_date)
        
        if df is not None and not df.empty:
            existing_dates = set(self.db.get_all_data()['date'])
            df = df[~df['date'].isin(existing_dates)]
            
            if not df.empty:
                self.db.insert_data(df)
                print(f"[OK] Added {len(df)} new records")
                return True
            else:
                print("[INFO] No new data to add")
                return True
        
        return False