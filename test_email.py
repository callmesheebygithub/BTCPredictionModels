# test_email.py
from email_notifier import EmailNotifier
from datetime import datetime

def test_email_only():
    """Test email separately"""
    notifier = EmailNotifier()
    
    test_data = {
        'price': 75000.00,
        'change': 2.5,
        'current_price': 73200.00,
        'confidence': 78,
        'range_low': 73500.00,
        'range_high': 76500.00,
        'models_used': 4
    }
    
    perf_data = {
        'avg_error': 1.2,
        'avg_abs_error': 850.00,
        'direction_accuracy': 58.5,
        'total_predictions': 45,
        'model_version': 'v1.5'
    }
    
    result = notifier.send_daily_prediction_report(test_data, perf_data)
    
    if result:
        print("✅ Test email sent successfully!")
    else:
        print("❌ Test email failed. Please check email_config.json")

if __name__ == "__main__":
    test_email_only()