# prediction/confidence.py
"""
Confidence Calculator
"""

import numpy as np
from database.db_manager import DatabaseManager

class ConfidenceCalculator:
    def __init__(self):
        self.db = DatabaseManager()
    
    def calculate(self, predictions: dict, current_price: float, df: pd.DataFrame) -> dict:
        """Calculate confidence score"""
        factors = {}
        
        values = [p for p in predictions.values() if p is not None]
        if len(values) > 1:
            std = np.std(values)
            mean = np.mean(values)
            cv = std / mean if mean != 0 else 1
            agreement = max(0, 100 - (cv * 100))
            factors['model_agreement'] = min(100, agreement)
        else:
            factors['model_agreement'] = 50
        
        recent = self.db.get_recent_predictions(30)
        if not recent.empty:
            valid = recent[recent['direction_correct'].notna()]
            if not valid.empty:
                factors['historical_accuracy'] = valid['direction_correct'].mean() * 100
            else:
                factors['historical_accuracy'] = 50
        else:
            factors['historical_accuracy'] = 50
        
        if df is not None and len(df) > 30:
            returns = df['close'].pct_change()
            volatility = returns.std() * 100
            
            if volatility < 1:
                factors['volatility'] = 90
            elif volatility < 2:
                factors['volatility'] = 70
            elif volatility < 3:
                factors['volatility'] = 50
            else:
                factors['volatility'] = 30
        else:
            factors['volatility'] = 50
        
        regime = self.detect_regime(df)
        factors['regime_confidence'] = regime['confidence']
        factors['regime'] = regime['regime']
        
        if len(values) > 1:
            range_pct = (max(values) - min(values)) / np.mean(values) * 100
            if range_pct < 1:
                factors['dispersion'] = 90
            elif range_pct < 3:
                factors['dispersion'] = 70
            elif range_pct < 5:
                factors['dispersion'] = 50
            else:
                factors['dispersion'] = 30
        else:
            factors['dispersion'] = 50
        
        if not recent.empty:
            valid = recent[recent['direction_correct'].notna()]
            if len(valid) >= 10:
                factors['recent_trend'] = valid.head(10)['direction_correct'].mean() * 100
            else:
                factors['recent_trend'] = 50
        else:
            factors['recent_trend'] = 50
        
        weights = {
            'model_agreement': 0.25,
            'historical_accuracy': 0.20,
            'volatility': 0.15,
            'regime_confidence': 0.15,
            'dispersion': 0.15,
            'recent_trend': 0.10
        }
        
        confidence_score = sum(factors.get(k, 50) * weights[k] for k in weights)
        confidence_score = min(100, max(0, confidence_score))
        
        if len(values) > 1:
            mean_pred = np.mean(values)
            if mean_pred > current_price * 1.002:
                direction = 'BULLISH'
            elif mean_pred < current_price * 0.998:
                direction = 'BEARISH'
            else:
                direction = 'NEUTRAL'
        else:
            direction = 'NEUTRAL'
        
        return {
            'confidence_score': confidence_score,
            'direction': direction,
            'factors': factors,
            'regime': factors.get('regime', 'UNKNOWN')
        }
    
    def detect_regime(self, df):
        if df is None or len(df) < 50:
            return {'regime': 'UNKNOWN', 'confidence': 50}
        
        prices = df['close'].values
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:]) if len(prices) > 200 else ma50
        
        returns = df['close'].pct_change()
        vol = returns.std() * 100
        
        if prices[-1] > ma50 and ma50 > ma200:
            regime = 'BULL'
            confidence = 70
        elif prices[-1] < ma50 and ma50 < ma200:
            regime = 'BEAR'
            confidence = 70
        else:
            regime = 'SIDEWAYS'
            confidence = 50
        
        if vol > 3:
            regime += '_HIGH_VOL'
            confidence -= 10
        elif vol < 1:
            regime += '_LOW_VOL'
            confidence += 10
        
        return {'regime': regime, 'confidence': min(90, confidence)}