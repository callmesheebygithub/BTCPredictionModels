"""
btc_email_sender.py - Send BTC Indicators Report via Email (UPDATED)
Calls btc_indicators.py as a module and emails the results
"""

import json
import smtplib
import logging
import os
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import btc_indicators as module
try:
    from btc_indicators import BTCIndicators
except ImportError:
    print("❌ btc_indicators.py not found!")
    print("Please make sure btc_indicators.py is in the same directory.")
    sys.exit(1)

# Email credentials from .env
EMAIL_SENDER = os.getenv('email_sender')
EMAIL_PASSWORD = os.getenv('email_password')
EMAIL_RECEIVER = os.getenv('email_receiver')
EMAIL_SMTP_SERVER = os.getenv('email_smtp_server', 'smtp.gmail.com')
EMAIL_SMTP_PORT = int(os.getenv('email_smtp_port', 587))

# Check email credentials
if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
    raise ValueError("❌ .env file mein email values missing hain!")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('btc_email_sender.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BTCEmailSender:
    def __init__(self):
        """Initialize email sender"""
        self.indicators = None
        self.results = None
    
    def get_indicators(self):
        """Call btc_indicators.py and get results"""
        try:
            logger.info("🔄 Calling btc_indicators.py...")
            
            # Create instance of BTCIndicators from imported module
            self.indicators = BTCIndicators()
            
            # Calculate all indicators
            self.results = self.indicators.calculate_all_indicators()
            
            # Close connection
            self.indicators.close()
            
            if self.results:
                logger.info("✅ Indicators calculated successfully")
                return True
            else:
                logger.error("❌ Failed to calculate indicators")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error calling indicators: {e}")
            return False
    
    def create_html_email(self):
        """Create HTML email content from results (UPDATED)"""
        if not self.results:
            return None
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    padding: 20px;
                }}
                .container {{
                    max-width: 900px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #f7931a, #f9a825);
                    color: white;
                    padding: 20px;
                    border-radius: 10px 10px 0 0;
                    text-align: center;
                    margin: -30px -30px 20px -30px;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                }}
                .header p {{
                    margin: 5px 0 0 0;
                    opacity: 0.9;
                }}
                .section {{
                    margin: 25px 0;
                    padding: 15px;
                    background-color: #f8f9fa;
                    border-radius: 8px;
                    border-left: 4px solid #f7931a;
                }}
                .section-title {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #f7931a;
                    margin-bottom: 10px;
                }}
                .price {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #f7931a;
                    text-align: center;
                    padding: 15px;
                    background: #fff3e0;
                    border-radius: 8px;
                    margin: 10px 0;
                }}
                .signal {{
                    font-size: 24px;
                    font-weight: bold;
                    text-align: center;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 10px 0;
                }}
                .signal-buy {{
                    background-color: #d4edda;
                    color: #155724;
                    border: 2px solid #28a745;
                }}
                .signal-sell {{
                    background-color: #f8d7da;
                    color: #721c24;
                    border: 2px solid #dc3545;
                }}
                .signal-neutral {{
                    background-color: #fff3cd;
                    color: #856404;
                    border: 2px solid #ffc107;
                }}
                .confidence-high {{
                    color: #28a745;
                    font-weight: bold;
                }}
                .confidence-medium {{
                    color: #ffc107;
                    font-weight: bold;
                }}
                .confidence-low {{
                    color: #dc3545;
                    font-weight: bold;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 10px 0;
                }}
                th {{
                    background-color: #f7931a;
                    color: white;
                    padding: 10px;
                    text-align: left;
                }}
                td {{
                    padding: 8px 10px;
                    border-bottom: 1px solid #ddd;
                }}
                tr:hover {{
                    background-color: #f5f5f5;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    color: #666;
                    font-size: 12px;
                }}
                .badge {{
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: bold;
                }}
                .badge-bullish {{
                    background-color: #28a745;
                    color: white;
                }}
                .badge-bearish {{
                    background-color: #dc3545;
                    color: white;
                }}
                .badge-neutral {{
                    background-color: #ffc107;
                    color: #333;
                }}
                .badge-bos {{
                    background-color: #17a2b8;
                    color: white;
                }}
                .badge-choch {{
                    background-color: #6f42c1;
                    color: white;
                }}
                .grid-2 {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 15px;
                }}
                .grid-3 {{
                    display: grid;
                    grid-template-columns: 1fr 1fr 1fr;
                    gap: 15px;
                }}
                .stat-box {{
                    background: white;
                    padding: 12px;
                    border-radius: 6px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .stat-label {{
                    font-size: 12px;
                    color: #666;
                }}
                .stat-value {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #333;
                }}
                .trend-uptrend {{
                    color: #28a745;
                    font-weight: bold;
                }}
                .trend-downtrend {{
                    color: #dc3545;
                    font-weight: bold;
                }}
                .trend-range {{
                    color: #ffc107;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 BTC Daily Report</h1>
                    <p>{datetime.now().strftime('%A, %B %d, %Y - %H:%M:%S')}</p>
                </div>
        """
        
        # Current Price
        current_price = self.results.get('current_price', 0)
        html += f"""
            <div class="price">
                ${current_price:,.2f}
            </div>
        """
        
        # Overall Signal with Confidence
        if 'overall_signal' in self.results:
            signal = self.results['overall_signal']
            direction = signal.get('direction', 'NEUTRAL')
            score = signal.get('normalized_score', signal.get('score', 0))
            confidence = signal.get('confidence', 'Unknown')
            
            signal_class = 'signal-buy' if 'BUY' in direction else 'signal-sell' if 'SELL' in direction else 'signal-neutral'
            emoji = '🟢' if 'BUY' in direction else '🔴' if 'SELL' in direction else '🟡'
            
            # Confidence class
            conf_class = 'confidence-high' if confidence == 'High' else 'confidence-medium' if confidence == 'Medium' else 'confidence-low'
            
            html += f"""
                <div class="signal {signal_class}">
                    {emoji} {direction} (Score: {score:.2f})
                    <br>
                    <span style="font-size: 16px;">Confidence: <span class="{conf_class}">{confidence}</span></span>
                </div>
            """
            
            # Factors
            if 'factors' in signal:
                html += """
                    <div class="section">
                        <div class="section-title">📋 Signal Factors</div>
                        <ul>
                """
                for factor in signal['factors']:
                    html += f"<li>{factor}</li>"
                html += """
                        </ul>
                    </div>
                """
            
            # Weights
            if 'weights' in signal:
                html += """
                    <div class="section">
                        <div class="section-title">⚖️ Indicator Weights</div>
                        <ul>
                """
                for key, weight in signal['weights'].items():
                    html += f"<li>{key}: {weight:.0%}</li>"
                html += """
                        </ul>
                    </div>
                """
        
        # Market Structure (NEW)
        if 'market_structure' in self.results:
            structure = self.results['market_structure']
            html += f"""
                <div class="section">
                    <div class="section-title">📊 Market Structure</div>
                    <div class="grid-2">
                        <div class="stat-box">
                            <div class="stat-label">Trend Regime</div>
                            <div class="stat-value">
            """
            
            trend = structure.get('trend_regime', 'Unknown')
            if trend == 'Uptrend':
                html += f'<span class="trend-uptrend">📈 {trend}</span>'
            elif trend == 'Downtrend':
                html += f'<span class="trend-downtrend">📉 {trend}</span>'
            elif trend == 'Range':
                html += f'<span class="trend-range">➡️ {trend}</span>'
            else:
                html += f'❓ {trend}'
            
            html += """
                            </div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">BOS / CHOCH</div>
                            <div class="stat-value">
            """
            
            bos = structure.get('bos', [])
            choch = structure.get('choch', [])
            html += f"{len(bos)} BOS, {len(choch)} CHOCH"
            
            html += """
                            </div>
                        </div>
                    </div>
            """
            
            # BOS details
            if bos:
                html += """
                    <table>
                        <tr><th>Break of Structure (BOS)</th><th>Price</th></tr>
                """
                for b in bos:
                    html += f"""
                        <tr>
                            <td><span class="badge badge-bos">{b['type']}</span></td>
                            <td>${b['price']:,.2f}</td>
                        </tr>
                    """
                html += "</table>"
            
            # CHOCH details
            if choch:
                html += """
                    <table>
                        <tr><th>Change of Character (CHOCH)</th></tr>
                """
                for c in choch:
                    html += f"""
                        <tr>
                            <td><span class="badge badge-choch">{c['type']}</span></td>
                        </tr>
                    """
                html += "</table>"
            
            # HH/HL/LH/LL
            if 'hh_hl_lh_ll' in structure:
                hh_hl = structure['hh_hl_lh_ll']
                html += f"""
                    <div style="margin-top: 10px; text-align: center;">
                        <span style="margin: 0 10px;">HH: {hh_hl.get('HH', 0)}</span>
                        <span style="margin: 0 10px;">HL: {hh_hl.get('HL', 0)}</span>
                        <span style="margin: 0 10px;">LH: {hh_hl.get('LH', 0)}</span>
                        <span style="margin: 0 10px;">LL: {hh_hl.get('LL', 0)}</span>
                    </div>
                """
            
            html += "</div>"
        
        # Support & Resistance
        if 'support_resistance' in self.results:
            sr = self.results['support_resistance']
            html += f"""
                <div class="section">
                    <div class="section-title">🎯 Support & Resistance</div>
                    <div class="grid-2">
                        <div class="stat-box">
                            <div class="stat-label">Nearest Support</div>
                            <div class="stat-value">${sr.get('nearest_support', {}).get('price', 0):,.2f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Nearest Resistance</div>
                            <div class="stat-value">${sr.get('nearest_resistance', {}).get('price', 0):,.2f}</div>
                        </div>
                    </div>
            """
            
            if 'support_levels' in sr and sr['support_levels']:
                html += """
                    <table>
                        <tr><th>Support Levels</th><th>Strength</th></tr>
                """
                for support in sr['support_levels'][:3]:
                    html += f"""
                        <tr>
                            <td>${support['price']:,.2f}</td>
                            <td>{support['strength']} touches</td>
                        </tr>
                    """
                html += "</table>"
            
            if 'resistance_levels' in sr and sr['resistance_levels']:
                html += """
                    <table>
                        <tr><th>Resistance Levels</th><th>Strength</th></tr>
                """
                for resistance in sr['resistance_levels'][:3]:
                    html += f"""
                        <tr>
                            <td>${resistance['price']:,.2f}</td>
                            <td>{resistance['strength']} touches</td>
                        </tr>
                    """
                html += "</table>"
            
            html += "</div>"
        
        # Moving Averages
        if 'moving_averages' in self.results:
            ma = self.results['moving_averages']
            html += f"""
                <div class="section">
                    <div class="section-title">📈 Moving Averages</div>
                    <table>
                        <tr><th>Period</th><th>Value</th><th>EMA</th><th>Trend</th><th>Slope</th></tr>
            """
            for period, data in ma.items():
                badge_class = 'badge-bullish' if 'Bullish' in data.get('trend', '') else 'badge-bearish' if 'Bearish' in data.get('trend', '') else 'badge-neutral'
                html += f"""
                    <tr>
                        <td>{period}</td>
                        <td>${data['value']:,.2f}</td>
                        <td>${data.get('ema', data['value']):,.2f}</td>
                        <td><span class="badge {badge_class}">{data['trend']}</span></td>
                        <td>{data.get('slope', 0):.2f}%</td>
                    </tr>
                """
            html += "</table></div>"
        
        # RSI, MACD, ATR Grid
        html += '<div class="grid-3">'
        
        if 'rsi' in self.results:
            rsi = self.results['rsi']
            badge_class = 'badge-bullish' if rsi.get('status') == 'Oversold' else 'badge-bearish' if rsi.get('status') == 'Overbought' else 'badge-neutral'
            html += f"""
                <div class="section">
                    <div class="section-title">📊 RSI</div>
                    <div style="text-align:center; font-size:24px; font-weight:bold;">{rsi.get('value', 0):.1f}</div>
                    <div style="text-align:center;"><span class="badge {badge_class}">{rsi.get('status', 'Neutral')}</span></div>
                    <div style="font-size:12px; color:#666; text-align:center;">{rsi.get('period', 14)} days</div>
                </div>
            """
        
        if 'macd' in self.results:
            macd = self.results['macd']
            badge_class = 'badge-bullish' if macd.get('signal_status') == 'Bullish' else 'badge-bearish'
            html += f"""
                <div class="section">
                    <div class="section-title">📊 MACD</div>
                    <div style="text-align:center; font-size:20px; font-weight:bold;">{macd.get('signal_status', 'Neutral')}</div>
                    <div style="font-size:12px; color:#666; text-align:center;">Signal: {macd.get('signal', 0):.2f}</div>
                    <div style="font-size:12px; color:#666; text-align:center;">Histogram: {macd.get('histogram', 0):.2f}</div>
                </div>
            """
        
        if 'atr' in self.results:
            atr = self.results['atr']
            html += f"""
                <div class="section">
                    <div class="section-title">📊 ATR</div>
                    <div style="text-align:center; font-size:20px; font-weight:bold;">${atr.get('atr', 0):.2f}</div>
                    <div style="font-size:12px; color:#666; text-align:center;">{atr.get('percentile', 0):.0f}th percentile</div>
            """
            if 'overall_signal' in self.results and 'atr_info' in self.results['overall_signal']:
                atr_info = self.results['overall_signal']['atr_info']
                html += f"""
                    <div style="font-size:11px; color:#666; text-align:center; margin-top:5px;">
                        Stop Loss: ${atr_info.get('suggested_stop_loss', 0):.2f}
                    </div>
                """
            html += "</div>"
        
        html += '</div>'
        
        # Bollinger Bands
        if 'bollinger_bands' in self.results:
            bb = self.results['bollinger_bands']
            html += f"""
                <div class="section">
                    <div class="section-title">📊 Bollinger Bands</div>
                    <div class="grid-3">
                        <div class="stat-box">
                            <div class="stat-label">Upper Band</div>
                            <div class="stat-value">${bb.get('upper_band', 0):,.2f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Middle Band</div>
                            <div class="stat-value">${bb.get('middle_band', 0):,.2f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Lower Band</div>
                            <div class="stat-value">${bb.get('lower_band', 0):,.2f}</div>
                        </div>
                    </div>
                    <div style="text-align:center; margin-top:10px; font-size:14px;">
                        Position: {bb.get('position', 'Inside Bands')} | 
                        Squeeze: {bb.get('squeeze', 'No')} | 
                        Percentile: {bb.get('bandwidth_percentile', 0):.0f}%
                    </div>
                </div>
            """
        
        # Fibonacci (Swing-based)
        if 'fibonacci' in self.results:
            fib = self.results['fibonacci']
            html += f"""
                <div class="section">
                    <div class="section-title">📊 Fibonacci (Swing-based)</div>
                    <div style="font-size:14px; text-align:center; margin-bottom:10px;">
                        Swing High: ${fib.get('swing_high', 0):,.2f} ({fib.get('high_date', 'N/A')}) | 
                        Swing Low: ${fib.get('swing_low', 0):,.2f} ({fib.get('low_date', 'N/A')})
                    </div>
                    <table>
                        <tr><th>Level</th><th>Price</th></tr>
            """
            for level, price in fib.get('fib_levels', {}).items():
                html += f"""
                    <tr>
                        <td>{level}</td>
                        <td>${price:,.2f}</td>
                    </tr>
                """
            html += "</table>"
            if fib.get('current_fib_level'):
                html += f"<div style='margin-top:10px;'>📍 Current Level: <strong>{fib['current_fib_level']}</strong></div>"
            html += "</div>"
        
        # Pivot Points
        if 'pivot_points' in self.results:
            pivot = self.results['pivot_points']
            html += f"""
                <div class="section">
                    <div class="section-title">📊 Pivot Points</div>
                    <div class="grid-2">
                        <div class="stat-box">
                            <div class="stat-label">Pivot</div>
                            <div class="stat-value">${pivot.get('pivot', 0):,.2f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Position</div>
                            <div class="stat-value">{pivot.get('current_position', 'Below Pivot')}</div>
                        </div>
                    </div>
                    <div class="grid-2">
                        <div>
                            <div class="stat-box">
                                <div class="stat-label">R1 / R2 / R3</div>
                                <div class="stat-value">
                                    ${pivot.get('resistance_1', 0):,.2f} / ${pivot.get('resistance_2', 0):,.2f} / ${pivot.get('resistance_3', 0):,.2f}
                                </div>
                            </div>
                        </div>
                        <div>
                            <div class="stat-box">
                                <div class="stat-label">S1 / S2 / S3</div>
                                <div class="stat-value">
                                    ${pivot.get('support_1', 0):,.2f} / ${pivot.get('support_2', 0):,.2f} / ${pivot.get('support_3', 0):,.2f}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div style="text-align:center; margin-top:10px; font-size:14px;">
                        Nearest: {pivot.get('nearest_level', 'N/A')} (${pivot.get('distance_to_nearest', 0):.2f} away)
                    </div>
                </div>
            """
        
        # Liquidity with Volume Profile
        if 'liquidity' in self.results:
            liq = self.results['liquidity']
            html += f"""
                <div class="section">
                    <div class="section-title">💧 Liquidity Analysis</div>
                    <div class="grid-2">
                        <div class="stat-box">
                            <div class="stat-label">30-Day Avg Volume</div>
                            <div class="stat-value">{liq.get('avg_volume_30d', 0):,.0f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Volume Ratio</div>
                            <div class="stat-value">{liq.get('volume_ratio', 0):.2f}x</div>
                        </div>
                    </div>
            """
            
            # Volume Profile
            if 'volume_profile' in liq:
                vp = liq['volume_profile']
                if vp:
                    html += """
                        <div class="grid-3">
                            <div class="stat-box">
                                <div class="stat-label">POC</div>
                                <div class="stat-value">$""" + f"{vp.get('poc', 0):,.2f}</div></div>"
                    html += f"""
                            <div class="stat-box">
                                <div class="stat-label">VAH</div>
                                <div class="stat-value">${vp.get('vah', 0):,.2f}</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-label">VAL</div>
                                <div class="stat-value">${vp.get('val', 0):,.2f}</div>
                            </div>
                        </div>
                    """
            
            # High Volume Nodes
            if 'high_volume_nodes' in liq and liq['high_volume_nodes']:
                html += """
                    <table>
                        <tr><th>High Volume Nodes (HVN)</th><th>Volume</th></tr>
                """
                for node in liq['high_volume_nodes'][:3]:
                    html += f"""
                        <tr>
                            <td>{node.get('price_range', 'N/A')}</td>
                            <td>{node.get('volume', 0):,.0f}</td>
                        </tr>
                    """
                html += "</table>"
            
            html += "</div>"
        
        # Footer
        html += """
                <div class="footer">
                    <p>Generated by BTC Indicators System (Improved)</p>
                    <p>Indicators: S/R, Market Structure, MA, RSI, MACD, BB, Fibonacci, Pivot, Liquidity, ATR</p>
                    <p>© 2026 All Rights Reserved</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_email(self, subject, html_content):
        """Send email with HTML content"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = EMAIL_SENDER
            msg['To'] = EMAIL_RECEIVER
            
            # Add plain text version
            text_content = f"""
BTC Daily Report (Improved)
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Current Price: ${self.results.get('current_price', 0):,.2f}

Signal: {self.results.get('overall_signal', {}).get('direction', 'NEUTRAL')}
Confidence: {self.results.get('overall_signal', {}).get('confidence', 'Unknown')}

Market Structure: {self.results.get('market_structure', {}).get('trend_regime', 'Unknown')}

Please view this email in HTML format for the complete report with all indicators.
            """
            text_part = MIMEText(text_content, 'plain')
            msg.attach(text_part)
            
            # Add HTML part
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            logger.info(f"📧 Sending email to {EMAIL_RECEIVER}...")
            
            server = smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT)
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            logger.info("✅ Email sent successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            return False
    
    def send_report(self):
        """Main function to get indicators and send report"""
        logger.info("\n" + "="*60)
        logger.info("📧 SENDING BTC INDICATORS REPORT (IMPROVED)")
        logger.info("="*60)
        
        # Get indicators from btc_indicators.py
        if not self.get_indicators():
            logger.error("❌ Failed to get indicators")
            return False
        
        # Create email content
        html_content = self.create_html_email()
        if not html_content:
            logger.error("❌ Failed to create email content")
            return False
        
        # Send email
        subject = f"🚀 BTC Daily Report - {datetime.now().strftime('%Y-%m-%d')}"
        success = self.send_email(subject, html_content)
        
        if success:
            logger.info("✅ Report sent successfully!")
        else:
            logger.error("❌ Failed to send report")
        
        return success

def main():
    """Main function"""
    sender = BTCEmailSender()
    
    try:
        # Send report
        sender.send_report()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()