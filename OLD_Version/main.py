# main.py
"""
BTC Predictor - Main Entry Point
Complete with Features + Support/Resistance in Email
"""

import os
import sys
import schedule
import time
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prediction.predictor import EnhancedSelfLearningPredictor
from config import SCHEDULE_TIME
from utils.helpers import print_success, print_info, print_error


def main():
    """Main entry point"""
    
    # Check email config
    if not os.path.exists('email_config.json'):
        print_info("Email not configured. Setup now?")
        choice = input("Setup email? (y/n): ").strip().lower()
        if choice == 'y':
            try:
                from email_notifier import setup_email_config
                setup_email_config()
            except:
                print_error("Email setup failed")
    
    # Initialize predictor
    predictor = EnhancedSelfLearningPredictor()
    
    if predictor.model_version is None:
        print_error("Model training failed!")
        return
    
    print_success(f"Model ready: {predictor.model_version}")
    
    # Show initial prediction
    print_info("\n" + "="*60)
    print_info("INITIAL PREDICTION")
    
    df = predictor.db.get_all_data()
    all_preds = predictor.get_model_predictions(df)
    final_pred, weights = predictor.get_ensemble_prediction(all_preds)
    
    if final_pred is not None:
        last_close = df['close'].iloc[-1]
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        change = ((final_pred - last_close) / last_close) * 100
        
        confidence_data = predictor.confidence_calc.calculate(all_preds, last_close, df)
        intervals = predictor.interval_calc.calculate(final_pred, df)
        signal = predictor.signal_gen.generate(final_pred, last_close, confidence_data)
        
        print_info(f"  Tomorrow's Date: {tomorrow}")
        print_info(f"  Predicted Close: ${final_pred:,.2f}")
        print_info(f"  Current Close: ${last_close:,.2f}")
        print_info(f"  Expected Change: {change:+.2f}%")
        print_info(f"  Direction: {confidence_data['direction']}")
        print_info(f"  Confidence Score: {confidence_data['confidence_score']:.1f}%")
        print_info(f"  Range: ${intervals['low']:,.2f} - ${intervals['high']:,.2f}")
        print_info(f"  Signal: {signal}")
        
        predictor.db.save_ensemble_prediction(
            date=tomorrow,
            predicted=final_pred,
            actual=None,
            confidence_score=confidence_data['confidence_score'],
            range_low=intervals['low'],
            range_high=intervals['high'],
            regime=confidence_data.get('regime', 'UNKNOWN'),
            signal=signal,
            model_version=predictor.model_version or 'v1.0'
        )
        
        # ============================================
        # SEND EMAIL WITH FEATURES + SUPPORT/RESISTANCE
        # ============================================
        if predictor.use_email and predictor.email_notifier:
            print_info("Sending initial email with features...")
            
            # Get features data
            features = predictor._get_features_dict(df)
            
            prediction_data = {
                'price': final_pred,
                'change': change,
                'current_price': last_close,
                'confidence': confidence_data['confidence_score'],
                'range_low': intervals['low'],
                'range_high': intervals['high'],
                'direction': confidence_data['direction'],
                'regime': confidence_data.get('regime', 'UNKNOWN'),
                'signal': signal
            }
            
            performance_data = {
                'model_version': predictor.model_version or 'v1.0',
                'recent_predictions': predictor.db.get_recent_predictions(10)
            }
            
            metrics = predictor.db.update_performance_metrics()
            if metrics:
                performance_data.update(metrics)
            
            try:
                predictor.email_notifier.send_daily_prediction_report(
                    prediction_data, 
                    performance_data,
                    features_data=features  # ✅ Features + Support/Resistance
                )
                print_success("Initial email sent successfully!")
            except Exception as e:
                print_error(f"Email sending failed: {e}")
    
    print_info("="*60 + "\n")
    
    # Schedule daily job
    schedule.every().day.at(SCHEDULE_TIME).do(predictor.daily_job)
    
    print_success("BTC Predictor is running!")
    print_info(f"Daily updates scheduled for {SCHEDULE_TIME} UTC")
    print_info(f"Current model: {predictor.model_version}")
    print_info("📧 Email reports include: 40+ indicators + Support/Resistance")
    print_info("Press Ctrl+C to stop\n")
    
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()