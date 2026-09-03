# data/yahoo_fetcher.py
"""
Yahoo Finance Data Fetcher
"""

import pandas as pd
from datetime import datetime
import time

class YahooDataFetcher:
    def __init__(self):
        try:
            import yfinance as yf
            self.yf = yf
            print("[OK] Yahoo Finance loaded")
        except ImportError:
            print("[ERROR] yfinance not installed")
            self.yf = None
    
    def fetch_from_date(self, start_date, end_date=None, symbol='BTC-USD'):
        """Fetch data from Yahoo Finance"""
        if self.yf is None:
            return None
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            print(f"[INFO] Fetching from Yahoo: {start_date} to {end_date}")
            df = self.yf.download(symbol, start=start_date, end=end_date, progress=False)
            
            if df.empty:
                print("[ERROR] No data received")
                return None
            
            df = df.reset_index()
            df['date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
            df = df[['date', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            df = df.dropna()
            
            print(f"[OK] Downloaded {len(df)} records")
            return df
            
        except Exception as e:
            print(f"[ERROR] Yahoo error: {e}")
            return None