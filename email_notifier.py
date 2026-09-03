# email_notifier.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import pandas as pd
from datetime import datetime
import os
import json
from pathlib import Path

class EmailNotifier:
    def __init__(self, config_file='email_config.json'):
        """
        Initialize Email Notifier
        Config file example:
        {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "email": "mdshoaibhabib1@gmail.com",
            "password": "kcwr gley rmwq jrms",
            "to_emails": ["mdshoaibhabibai@gmail.com", "mdshoaibhabibai@outlook.com"]
        }
        """
        self.config = self.load_config(config_file)
        self.last_report_date = None
    
    def load_config(self, config_file):
        """Load email configuration"""
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            # Create default config
            default_config = {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "email": "mdshoaibhabib1@gmail.com",
                "password": "mpkd tcfh mdgi fadp",
                "to_emails": ["mdsshoaibhabibai@outlook.com"]
            }
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            print(f"⚠️ Please configure {config_file} with your email settings")
            return default_config
    
    def send_email(self, subject, body, attachments=None, html=True):
        """
        Send email with optional attachments
        """
        if self.config['email'] == "your_email@gmail.com":
            print("⚠️ Email not configured. Please update email_config.json")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config['email']
            msg['To'] = ', '.join(self.config['to_emails'])
            msg['Subject'] = subject
            
            # Attach body
            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Attach files
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename={os.path.basename(file_path)}'
                            )
                            msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port'])
            server.starttls()
            server.login(self.config['email'], self.config['password'])
            server.send_message(msg)
            server.quit()
            
            print(f"✅ Email sent successfully to {', '.join(self.config['to_emails'])}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            return False
    
    def send_daily_prediction_report(self, prediction_data, performance_data, charts=None):
        """
        Send daily prediction report
        """
        subject = f"📊 BTC Prediction Report - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Create HTML body
        body = self.create_report_html(prediction_data, performance_data)
        
        attachments = []
        if charts:
            attachments.extend(charts)
        
        return self.send_email(subject, body, attachments)
    
    def create_report_html(self, prediction, performance):
        """Create beautiful HTML email report"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; }}
                .prediction-box {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #667eea; }}
                .metric {{ display: inline-block; width: 45%; margin: 5px; padding: 10px; background: white; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #333; }}
                .metric-label {{ font-size: 12px; color: #666; }}
                .performance {{ background: #e8f5e9; padding: 15px; border-radius: 10px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
                .positive {{ color: #4caf50; }}
                .negative {{ color: #f44336; }}
                .neutral {{ color: #ff9800; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th {{ background: #667eea; color: white; padding: 10px; text-align: left; }}
                td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                .badge {{ display: inline-block; padding: 3px 10px; border-radius: 15px; font-size: 12px; font-weight: bold; }}
                .badge-success {{ background: #4caf50; color: white; }}
                .badge-warning {{ background: #ff9800; color: white; }}
                .badge-danger {{ background: #f44336; color: white; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 BTC Prediction Report</h1>
                    <p>{datetime.now().strftime('%A, %B %d, %Y %H:%M')}</p>
                </div>
        """
        
        # Prediction Section
        if prediction:
            change = prediction.get('change', 0)
            change_class = 'positive' if change > 0 else 'negative' if change < 0 else 'neutral'
            confidence = prediction.get('confidence', 0)
            confidence_class = 'badge-success' if confidence > 70 else 'badge-warning' if confidence > 40 else 'badge-danger'
            
            html += f"""
                <div class="prediction-box">
                    <h2>📈 Today's Prediction</h2>
                    <div style="text-align: center;">
                        <div class="metric">
                            <div class="metric-label">Predicted Price</div>
                            <div class="metric-value">${prediction.get('price', 0):,.2f}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Expected Change</div>
                            <div class="metric-value {change_class}">{change:+.2f}%</div>
                        </div>
                    </div>
                    <div style="text-align: center; margin-top: 15px;">
                        <span class="badge {confidence_class}">Confidence: {confidence:.1f}%</span>
                    </div>
                    <div style="margin-top: 15px; text-align: center;">
                        <div class="metric" style="width: 30%;">
                            <div class="metric-label">Range Low</div>
                            <div class="metric-value">${prediction.get('range_low', 0):,.2f}</div>
                        </div>
                        <div class="metric" style="width: 30%;">
                            <div class="metric-label">Current Price</div>
                            <div class="metric-value">${prediction.get('current_price', 0):,.2f}</div>
                        </div>
                        <div class="metric" style="width: 30%;">
                            <div class="metric-label">Range High</div>
                            <div class="metric-value">${prediction.get('range_high', 0):,.2f}</div>
                        </div>
                    </div>
                </div>
            """
        
        # Performance Section
        if performance:
            html += f"""
                <div class="performance">
                    <h3>📊 Performance Metrics</h3>
                    <table>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                        </tr>
                        <tr>
                            <td>Average Error</td>
                            <td>{performance.get('avg_error', 0):.2f}%</td>
                        </tr>
                        <tr>
                            <td>Average Absolute Error</td>
                            <td>${performance.get('avg_abs_error', 0):.2f}</td>
                        </tr>
                        <tr>
                            <td>Direction Accuracy</td>
                            <td>{performance.get('direction_accuracy', 0):.1f}%</td>
                        </tr>
                        <tr>
                            <td>Total Predictions</td>
                            <td>{performance.get('total_predictions', 0)}</td>
                        </tr>
                    </table>
                </div>
            """
        
        # Recent Predictions Table
        if performance and performance.get('recent_predictions') is not None:
            recent = performance['recent_predictions']
            html += f"""
                <h3>📋 Recent Predictions</h3>
                <table>
                    <tr>
                        <th>Date</th>
                        <th>Predicted</th>
                        <th>Actual</th>
                        <th>Error</th>
                        <th>Direction</th>
                    </tr>
            """
            for _, row in recent.head(5).iterrows():
                direction = "✅" if row.get('direction_correct', 0) == 1 else "❌"
                color = 'positive' if row.get('error_percentage', 0) < 0 else 'negative'
                html += f"""
                    <tr>
                        <td>{row['date']}</td>
                        <td>${row['predicted_close']:,.2f}</td>
                        <td>${row['actual_close']:,.2f}</td>
                        <td class="{color}">{row.get('error_percentage', 0):+.2f}%</td>
                        <td>{direction}</td>
                    </tr>
                """
            html += "</table>"
        
        # Footer
        html += f"""
                <div class="footer">
                    <p>🤖 Generated by BTC Self-Learning Predictor v{performance.get('model_version', '1.0')}</p>
                    <p>This is an automated prediction. Please do your own research before trading.</p>
                    <p>Report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_alert(self, alert_type, message, data=None):
        """Send alert email for specific events"""
        subject = f"⚠️ BTC Alert: {alert_type}"
        
        body = f"""
        <h2>⚠️ {alert_type}</h2>
        <p>{message}</p>
        """
        
        if data:
            body += "<h3>Additional Data:</h3><pre>" + json.dumps(data, indent=2) + "</pre>"
        
        return self.send_email(subject, body)
    
    def send_performance_report(self, performance_df):
        """Send detailed performance report with attachment"""
        subject = f"📊 BTC Performance Report - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Create summary
        summary = f"""
        <h2>📊 Performance Summary</h2>
        <p>Total Predictions: {len(performance_df)}</p>
        <p>Average Error: {performance_df['error_percentage'].mean():.2f}%</p>
        <p>Direction Accuracy: {(performance_df['direction_correct'].mean() * 100):.1f}%</p>
        """
        
        # Save to Excel and attach
        excel_file = f"performance_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
        performance_df.to_excel(excel_file, index=False)
        
        return self.send_email(subject, summary, attachments=[excel_file])

# ============================================
# Email Configuration Setup
# ============================================

def setup_email_config():
    """Interactive email configuration setup"""
    print("\n📧 Email Configuration Setup")
    print("="*50)
    
    config = {}
    
    print("\nChoose email provider:")
    print("1. Gmail")
    print("2. Outlook")
    print("3. Custom SMTP")
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == '1':
        config['smtp_server'] = 'smtp.gmail.com'
        config['smtp_port'] = 587
    elif choice == '2':
        config['smtp_server'] = 'smtp.office365.com'
        config['smtp_port'] = 587
    else:
        config['smtp_server'] = input("SMTP Server: ")
        config['smtp_port'] = int(input("SMTP Port: "))
    
    config['email'] = input("\nYour Email: ")
    config['password'] = input("App Password (not regular password): ")
    
    print("\nRecipient emails (comma separated):")
    to_emails = input("Emails: ").split(',')
    config['to_emails'] = [email.strip() for email in to_emails]
    
    # Save config
    with open('email_config.json', 'w') as f:
        json.dump(config, f, indent=4)
    
    print("\n✅ Email configuration saved to email_config.json")
    print("⚠️ Note: For Gmail, use App Password (not regular password)")
    print("   Create at: https://myaccount.google.com/apppasswords")

if __name__ == "__main__":
    setup_email_config()