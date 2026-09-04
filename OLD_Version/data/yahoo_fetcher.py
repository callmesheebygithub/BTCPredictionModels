# data/yahoo_fetcher.py
"""
Yahoo Finance Data Fetcher - FIXED for current date
NO CIRCULAR IMPORT
"""

import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf

class YahooFetcher:
    """Fetch data from Yahoo Finance - includes current date"""
    
    def __init__(self):
        self.source = 'yahoo'
    
    def fetch(self, start_date: str, end_date: str = None, symbol: str = 'BTC-USD') -> pd.DataFrame:
        """
        Fetch OHLCV data from Yahoo Finance
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD) - if None, fetches today + 2 days
            symbol: Trading pair (default: BTC-USD)
        
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        if end_date is None:
            # Fetch 2 days extra to ensure we get today's data
            end_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        
        try:
            print(f"[INFO] Fetching from Yahoo: {start_date} to {end_date}")
            df = yf.download(symbol, start=start_date, end=end_date, progress=False)
            
            if df.empty:
                print("[WARN] No data received from Yahoo")
                return None
            
            # Format for database
            df = df.reset_index()
            df['date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
            df = df[['date', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            df = df.dropna()
            
            print(f"[OK] Downloaded {len(df)} records from Yahoo")
            print(f"[OK] Date range: {df['date'].min()} to {df['date'].max()}")
            return df
            
        except Exception as e:
            print(f"[ERROR] Yahoo fetch failed: {e}")
            return None
    
    def fetch_latest(self, days: int = 7, symbol: str = 'BTC-USD') -> pd.DataFrame:
        """Fetch latest N days data"""
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        return self.fetch(start_date, end_date, symbol)
    
    def fetch_today(self, symbol: str = 'BTC-USD') -> pd.DataFrame:
        """Fetch today's data only (if available)"""
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        return self.fetch(start_date, end_date, symbol)