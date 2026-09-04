# email_notifier.py
"""
Enhanced Email Notifier - Complete BTC Report with Features
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import pandas as pd
import numpy as np
from datetime import datetime
import os
import json
import base64

class EmailNotifier:
    def __init__(self, config_file='email_config.json'):
        self.config = self.load_config(config_file)
        self.last_report_date = None
    
    def load_config(self, config_file):
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            default_config = {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "email": "your_email@gmail.com",
                "password": "your_app_password",
                "to_emails": ["receiver@gmail.com"]
            }
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config
    
    def send_email(self, subject, body, attachments=None, html=True):
        if self.config['email'] == "your_email@gmail.com":
            print("⚠️ Email not configured")
            return False
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config['email']
            msg['To'] = ', '.join(self.config['to_emails'])
            msg['Subject'] = subject
            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
                            msg.attach(part)
            server = smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port'])
            server.starttls()
            server.login(self.config['email'], self.config['password'])
            server.send_message(msg)
            server.quit()
            print(f"✅ Email sent to {', '.join(self.config['to_emails'])}")
            return True
        except Exception as e:
            print(f"❌ Email failed: {e}")
            return False
    
    def send_daily_prediction_report(self, prediction_data, performance_data, features_data=None):
        """Send complete daily report with features"""
        subject = f"📊 BTC Daily Report - {datetime.now().strftime('%Y-%m-%d')}"
        body = self.create_complete_report(prediction_data, performance_data, features_data)
        return self.send_email(subject, body)
    
    def create_complete_report(self, prediction, performance, features=None):
        """Create complete HTML report with all features"""
        
        # Get current price and features
        current_price = prediction.get('current_price', 0)
        predicted_price = prediction.get('price', 0)
        change = prediction.get('change', 0)
        confidence = prediction.get('confidence', 0)
        
        # Calculate Support/Resistance
        sr_levels = self.calculate_support_resistance(current_price)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; padding: 20px; }}
                .container {{ max-width: 750px; margin: 0 auto; background: white; border-radius: 16px; padding: 30px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460); color: white; padding: 25px; border-radius: 12px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header .sub {{ font-size: 14px; opacity: 0.8; margin-top: 5px; }}
                
                .price-box {{ background: #f8f9fa; padding: 20px; border-radius: 12px; margin: 20px 0; text-align: center; border-left: 5px solid #f7931a; }}
                .price-box .big {{ font-size: 36px; font-weight: bold; color: #1a1a2e; }}
                .price-box .change {{ font-size: 20px; font-weight: bold; }}
                .price-box .change.positive {{ color: #28a745; }}
                .price-box .change.negative {{ color: #dc3545; }}
                
                .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 15px 0; }}
                .card {{ background: #f8f9fa; padding: 15px; border-radius: 10px; }}
                .card .label {{ font-size: 12px; color: #666; }}
                .card .value {{ font-size: 18px; font-weight: bold; color: #1a1a2e; }}
                
                .sr-section {{ background: #e8f4f8; padding: 15px; border-radius: 12px; margin: 15px 0; }}
                .sr-levels {{ display: flex; justify-content: space-around; flex-wrap: wrap; }}
                .sr-item {{ text-align: center; padding: 8px 15px; background: white; border-radius: 8px; margin: 5px; }}
                .sr-item .level {{ font-size: 18px; font-weight: bold; }}
                .sr-item .label {{ font-size: 11px; color: #666; }}
                .resistance {{ color: #dc3545; }}
                .support {{ color: #28a745; }}
                
                .features-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin: 10px 0; }}
                .feature-item {{ background: white; padding: 8px 12px; border-radius: 6px; border-left: 3px solid #f7931a; }}
                .feature-item .fname {{ font-size: 11px; color: #666; }}
                .feature-item .fvalue {{ font-size: 14px; font-weight: 600; }}
                .feature-item .fsignal {{ font-size: 12px; }}
                .bullish {{ color: #28a745; }}
                .bearish {{ color: #dc3545; }}
                .neutral {{ color: #ffc107; }}
                
                .table-wrap {{ overflow-x: auto; margin: 15px 0; }}
                table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
                th {{ background: #1a1a2e; color: white; padding: 10px; text-align: left; }}
                td {{ padding: 8px 10px; border-bottom: 1px solid #eee; }}
                tr:hover {{ background: #f8f9fa; }}
                .status-badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; }}
                .status-badge.bullish {{ background: #d4edda; color: #155724; }}
                .status-badge.bearish {{ background: #f8d7da; color: #721c24; }}
                .status-badge.neutral {{ background: #fff3cd; color: #856404; }}
                
                .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }}
            </style>
        </head>
        <body>
            <div class="container">
                <!-- HEADER -->
                <div class="header">
                    <h1>🚀 BTC Daily Report</h1>
                    <div class="sub">{datetime.now().strftime('%A, %B %d, %Y at %H:%M UTC')}</div>
                </div>
                
                <!-- PRICE SUMMARY -->
                <div class="price-box">
                    <div style="font-size:14px; color:#666;">Current Price</div>
                    <div class="big">${current_price:,.2f}</div>
                    <div class="change {('positive' if change >= 0 else 'negative')}">
                        {change:+.2f}% predicted change
                    </div>
                    <div style="margin-top:10px; font-size:14px;">
                        Predicted: <strong>${predicted_price:,.2f}</strong>
                        <span style="margin:0 10px; color:#ddd;">|</span>
                        Confidence: <strong>{confidence:.1f}%</strong>
                        <span style="margin:0 10px; color:#ddd;">|</span>
                        Signal: <strong>{prediction.get('signal', 'NO TRADE')}</strong>
                    </div>
                </div>
                
                <!-- DIRECTION & CONFIDENCE -->
                <div class="grid-2">
                    <div class="card">
                        <div class="label">Direction</div>
                        <div class="value">{prediction.get('direction', 'NEUTRAL')}</div>
                        <div style="font-size:12px; color:#666;">Based on ensemble agreement</div>
                    </div>
                    <div class="card">
                        <div class="label">Regime</div>
                        <div class="value">{prediction.get('regime', 'UNKNOWN')}</div>
                        <div style="font-size:12px; color:#666;">Market condition</div>
                    </div>
                </div>
                
                <!-- SUPPORT / RESISTANCE -->
                <div class="sr-section">
                    <h3 style="margin:0 0 10px 0;">📊 Support & Resistance</h3>
                    <div class="sr-levels">
                        <div class="sr-item">
                            <div class="label">🚀 Resistance 3</div>
                            <div class="level resistance">${sr_levels.get('r3', 0):,.2f}</div>
                        </div>
                        <div class="sr-item">
                            <div class="label">📈 Resistance 2</div>
                            <div class="level resistance">${sr_levels.get('r2', 0):,.2f}</div>
                        </div>
                        <div class="sr-item">
                            <div class="label">📊 Resistance 1</div>
                            <div class="level resistance">${sr_levels.get('r1', 0):,.2f}</div>
                        </div>
                        <div class="sr-item" style="background:#f7931a20; border:2px solid #f7931a;">
                            <div class="label">📍 Current</div>
                            <div class="level" style="color:#f7931a;">${current_price:,.2f}</div>
                        </div>
                        <div class="sr-item">
                            <div class="label">📉 Support 1</div>
                            <div class="level support">${sr_levels.get('s1', 0):,.2f}</div>
                        </div>
                        <div class="sr-item">
                            <div class="label">📉 Support 2</div>
                            <div class="level support">${sr_levels.get('s2', 0):,.2f}</div>
                        </div>
                        <div class="sr-item">
                            <div class="label">🛡️ Support 3</div>
                            <div class="level support">${sr_levels.get('s3', 0):,.2f}</div>
                        </div>
                    </div>
                    <div style="text-align:center; font-size:12px; color:#666; margin-top:10px;">
                        Based on pivot points + ATR calculation
                    </div>
                </div>
                
                <!-- PREDICTION RANGE -->
                <div class="grid-2">
                    <div class="card" style="background:#d4edda; border-left:4px solid #28a745;">
                        <div class="label">Expected Range</div>
                        <div class="value" style="color:#28a745;">${prediction.get('range_low', 0):,.2f}</div>
                        <div style="font-size:12px; color:#666;">Lower bound (95% confidence)</div>
                    </div>
                    <div class="card" style="background:#f8d7da; border-left:4px solid #dc3545;">
                        <div class="label">Expected Range</div>
                        <div class="value" style="color:#dc3545;">${prediction.get('range_high', 0):,.2f}</div>
                        <div style="font-size:12px; color:#666;">Upper bound (95% confidence)</div>
                    </div>
                </div>
                """
        
        # ============================================
        # ADD FEATURES SECTION (40+ indicators)
        # ============================================
        
        if features and isinstance(features, dict):
            html += """
                <h3 style="margin:20px 0 10px 0;">📈 Technical Indicators</h3>
                <div class="table-wrap">
                    <table>
                        <tr>
                            <th>Indicator</th>
                            <th>Value</th>
                            <th>Signal</th>
                        </tr>
            """
            
            # RSI
            if 'rsi_14' in features:
                rsi_val = features['rsi_14']
                rsi_signal = 'Overbought 🔴' if rsi_val > 70 else 'Oversold 🟢' if rsi_val < 30 else 'Neutral ⚪'
                rsi_class = 'bearish' if rsi_val > 70 else 'bullish' if rsi_val < 30 else 'neutral'
                html += f"""
                    <tr>
                        <td><strong>RSI (14)</strong></td>
                        <td>{rsi_val:.1f}</td>
                        <td><span class="status-badge {rsi_class}">{rsi_signal}</span></td>
                    </tr>
                """
            
            # MACD
            if 'macd' in features and 'macd_signal' in features:
                macd_signal = 'Bullish 🟢' if features['macd'] > features['macd_signal'] else 'Bearish 🔴'
                macd_class = 'bullish' if features['macd'] > features['macd_signal'] else 'bearish'
                html += f"""
                    <tr>
                        <td><strong>MACD</strong></td>
                        <td>{features['macd']:.4f}</td>
                        <td><span class="status-badge {macd_class}">{macd_signal}</span></td>
                    </tr>
                """
            
            # Moving Averages
            for ma in ['ma_7', 'ma_21', 'ma_50', 'ma_200']:
                if ma in features and 'close' in features:
                    price = features.get('close', 0)
                    ma_val = features[ma]
                    signal = 'Above ✅' if price > ma_val else 'Below ❌'
                    ma_class = 'bullish' if price > ma_val else 'bearish'
                    html += f"""
                        <tr>
                            <td><strong>{ma.upper().replace('_', ' ')}</strong></td>
                            <td>${ma_val:,.2f}</td>
                            <td><span class="status-badge {ma_class}">{signal}</span></td>
                        </tr>
                    """
            
            # ADX
            if 'adx' in features:
                adx_val = features['adx']
                adx_signal = 'Strong Trend 💪' if adx_val > 25 else 'Weak Trend 🌊'
                adx_class = 'bullish' if adx_val > 25 else 'neutral'
                html += f"""
                    <tr>
                        <td><strong>ADX</strong></td>
                        <td>{adx_val:.1f}</td>
                        <td><span class="status-badge {adx_class}">{adx_signal}</span></td>
                    </tr>
                """
            
            # ATR
            if 'atr_14' in features:
                html += f"""
                    <tr>
                        <td><strong>ATR (14)</strong></td>
                        <td>${features['atr_14']:,.2f}</td>
                        <td><span class="status-badge neutral">Volatility: {features.get('volatility_14', 0):.1f}%</span></td>
                    </tr>
                """
            
            # Volume
            if 'volume_ratio_14' in features:
                vol_ratio = features['volume_ratio_14']
                vol_signal = 'High Volume 🔥' if vol_ratio > 1.5 else 'Normal Volume 📊' if vol_ratio > 0.8 else 'Low Volume 📉'
                vol_class = 'bullish' if vol_ratio > 1.5 else 'neutral'
                html += f"""
                    <tr>
                        <td><strong>Volume Ratio</strong></td>
                        <td>{vol_ratio:.2f}x</td>
                        <td><span class="status-badge {vol_class}">{vol_signal}</span></td>
                    </tr>
                """
            
            # Bollinger Bands
            if 'bb_position' in features:
                bb_pos = features['bb_position']
                bb_signal = 'Overbought 🔴' if bb_pos > 0.8 else 'Oversold 🟢' if bb_pos < 0.2 else 'Neutral ⚪'
                bb_class = 'bearish' if bb_pos > 0.8 else 'bullish' if bb_pos < 0.2 else 'neutral'
                html += f"""
                    <tr>
                        <td><strong>Bollinger Position</strong></td>
                        <td>{bb_pos:.0%}</td>
                        <td><span class="status-badge {bb_class}">{bb_signal}</span></td>
                    </tr>
                """
            
            # Trend
            if 'trend_direction' in features:
                trend = 'Bullish 🟢' if features['trend_direction'] == 1 else 'Bearish 🔴'
                trend_class = 'bullish' if features['trend_direction'] == 1 else 'bearish'
                html += f"""
                    <tr>
                        <td><strong>Trend Direction</strong></td>
                        <td>{'UP' if features['trend_direction'] == 1 else 'DOWN'}</td>
                        <td><span class="status-badge {trend_class}">{trend}</span></td>
                    </tr>
                """
                html += f"""
                    <tr>
                        <td><strong>Trend Strength</strong></td>
                        <td>{features.get('trend_strength', 0):.1f}%</td>
                        <td><span class="status-badge neutral">{'Strong' if features.get('trend_strength', 0) > 20 else 'Weak'}</span></td>
                    </tr>
                """
            
            html += """
                    </table>
                </div>
            """
        
        # ============================================
        # PERFORMANCE SECTION
        # ============================================
        
        if performance:
            html += """
                <h3 style="margin:20px 0 10px 0;">📊 Model Performance</h3>
                <div class="grid-2">
                    <div class="card">
                        <div class="label">Direction Accuracy</div>
                        <div class="value">{:.1f}%</div>
                    </div>
                    <div class="card">
                        <div class="label">Total Predictions</div>
                        <div class="value">{}</div>
                    </div>
                    <div class="card">
                        <div class="label">MAE (Avg Error)</div>
                        <div class="value">${:,.2f}</div>
                    </div>
                    <div class="card">
                        <div class="label">Model Version</div>
                        <div class="value" style="font-size:14px;">{}</div>
                    </div>
                </div>
            """.format(
                performance.get('direction_accuracy', 0),
                performance.get('total_predictions', 0),
                performance.get('mae', 0),
                performance.get('model_version', 'v1.0')
            )
        
        # ============================================
        # RECENT PREDICTIONS TABLE
        # ============================================
        
        if performance and performance.get('recent_predictions') is not None:
            recent = performance['recent_predictions']
            if not recent.empty:
                html += """
                    <h3 style="margin:20px 0 10px 0;">📋 Recent Predictions</h3>
                    <div class="table-wrap">
                        <table>
                            <tr>
                                <th>Date</th>
                                <th>Predicted</th>
                                <th>Actual</th>
                                <th>Error</th>
                                <th>Direction</th>
                            </tr>
                """
                for _, row in recent.head(7).iterrows():
                    error = row.get('error_percentage', 0)
                    direction = "✅" if row.get('direction_correct', 0) == 1 else "❌"
                    color = 'positive' if error < 0 else 'negative' if error > 0 else 'neutral'
                    html += f"""
                        <tr>
                            <td>{row['date']}</td>
                            <td>${row['predicted_close']:,.2f}</td>
                            <td>${row['actual_close']:,.2f}</td>
                            <td class="{color}">{error:+.2f}%</td>
                            <td>{direction}</td>
                        </tr>
                    """
                html += "</table></div>"
        
        # ============================================
        # FOOTER
        # ============================================
        
        html += """
                <div class="footer">
                    <p>🤖 Generated by BTC Self-Learning Predictor</p>
                    <p style="font-size:11px; color:#aaa;">
                        This is an automated prediction. Please do your own research before trading.<br>
                        Support/Resistance based on pivot points + ATR calculation.
                    </p>
                    <p style="font-size:11px; color:#aaa;">
                        Report generated at {}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'))
        
        return html
    
    # ============================================
    # SUPPORT / RESISTANCE CALCULATION
    # ============================================
    
    def calculate_support_resistance(self, current_price, df=None):
        """
        Calculate Support & Resistance levels using pivot points + ATR
        """
        if df is None:
            try:
                from database.db_manager import DatabaseManager
                db = DatabaseManager()
                df = db.get_all_data()
            except:
                df = None
        
        if df is not None and len(df) > 0:
            # Get recent data
            recent = df.tail(20)
            high = recent['high'].max()
            low = recent['low'].min()
            close = recent['close'].iloc[-1]
            
            # Pivot points
            pivot = (high + low + close) / 3
            r1 = 2 * pivot - low
            r2 = pivot + (high - low)
            r3 = high + 2 * (pivot - low)
            s1 = 2 * pivot - high
            s2 = pivot - (high - low)
            s3 = low - 2 * (high - pivot)
            
            # Adjust with ATR
            try:
                from models.features import FeatureEngineer
                atr = FeatureEngineer._atr(df.tail(50))
                if not atr.empty:
                    atr_val = atr.iloc[-1]
                    r1 = current_price + atr_val * 0.5
                    r2 = current_price + atr_val * 1.0
                    r3 = current_price + atr_val * 1.5
                    s1 = current_price - atr_val * 0.5
                    s2 = current_price - atr_val * 1.0
                    s3 = current_price - atr_val * 1.5
            except:
                pass
            
            return {
                'r3': r3,
                'r2': r2,
                'r1': r1,
                's1': s1,
                's2': s2,
                's3': s3,
                'pivot': pivot
            }
        
        # Fallback: ATR-based levels
        atr_val = current_price * 0.02  # 2% ATR approximation
        return {
            'r3': current_price + atr_val * 1.5,
            'r2': current_price + atr_val * 1.0,
            'r1': current_price + atr_val * 0.5,
            's1': current_price - atr_val * 0.5,
            's2': current_price - atr_val * 1.0,
            's3': current_price - atr_val * 1.5,
            'pivot': current_price
        }
    
    def send_alert(self, alert_type, message, data=None):
        subject = f"⚠️ BTC Alert: {alert_type}"
        body = f"<h2>⚠️ {alert_type}</h2><p>{message}</p>"
        if data:
            body += "<pre>" + json.dumps(data, indent=2) + "</pre>"
        return self.send_email(subject, body)