# prediction/signal.py
"""
Signal Generator - Trading signals
"""

class SignalGenerator:
    def generate(self, prediction: float, current_price: float, confidence_data: dict) -> str:
        """Generate trading signal"""
        change = (prediction - current_price) / current_price
        confidence_score = confidence_data['confidence_score']
        direction = confidence_data['direction']
        
        if confidence_score < 45:
            return 'NO TRADE'
        
        if abs(change) < 0.01:
            return 'HOLD'
        
        if change > 0.03 and confidence_score > 55:
            return 'BUY'
        elif change < -0.03 and confidence_score > 55:
            return 'SELL'
        elif change > 0.01:
            return 'HOLD'
        else:
            return 'NO TRADE'