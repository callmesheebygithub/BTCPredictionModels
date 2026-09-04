# prediction/intervals.py
"""
Prediction Intervals Calculator
"""

import numpy as np
from database.db_manager import DatabaseManager

class IntervalCalculator:
    def __init__(self):
        self.db = DatabaseManager()
    
    def calculate(self, prediction: float, df: pd.DataFrame) -> Dict:
        """Calculate prediction intervals"""
        recent = self.db.get_recent_predictions(30)
        
        if not recent.empty:
            valid = recent[recent['absolute_error'].notna()]
            if not valid.empty:
                errors = valid['absolute_error'].values
                lower_error = np.percentile(errors, 2.5)
                upper_error = np.percentile(errors, 97.5)
                
                return {
                    'low': prediction - lower_error,
                    'high': prediction + upper_error,
                    'lower_error': lower_error,
                    'upper_error': upper_error,
                    'width': (upper_error + lower_error) / prediction * 100
                }
        
        atr = self.calculate_atr(df)
        return {
            'low': prediction - atr * 0.5,
            'high': prediction + atr * 0.5,
            'lower_error': atr * 0.5,
            'upper_error': atr * 0.5,
            'width': atr / prediction * 100
        }
    
    def calculate_atr(self, df, period=14):
        """Calculate Average True Range"""
        if len(df) < period:
            return df['close'].std() * 0.02
        
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = np.mean(tr[-period:])
        
        return atr