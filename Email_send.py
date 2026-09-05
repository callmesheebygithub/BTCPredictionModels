"""
btc_email_sender.py - Send Complete BTC Dashboard Report via Email with PDF Attachment
Sends the FULL dashboard including ML predictions, charts, and all technical indicators
BOTH in email body AND as PDF attachment
"""

import json
import smtplib
import logging
import os
import sys
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fpdf import FPDF
import mysql.connector
from mysql.connector import Error
import plotly.graph_objects as go
from io import BytesIO
import base64
import tempfile
import warnings
warnings.filterwarnings('ignore')

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


class PDFReport(FPDF):
    """Custom PDF class for BTC Dashboard Report"""
    
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.core_fonts_encoding = 'utf-8'
        
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(247, 147, 26)
        self.cell(0, 10, 'BTC AI Trading Dashboard - Complete Report', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C')
        self.ln(5)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()} | BTC Dashboard', 0, 0, 'C')
    
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 13)
        self.set_text_color(0, 0, 0)
        self.cell(0, 8, title, 0, 1, 'L')
        self.line(self.get_x(), self.get_y(), self.get_x() + 190, self.get_y())
        self.ln(4)
    
    def add_metric(self, label, value, subtext=''):
        self.set_font('Arial', 'B', 10)
        self.set_text_color(0, 0, 0)
        clean_label = str(label).encode('latin-1', errors='ignore').decode('latin-1')
        self.cell(55, 7, clean_label, 0, 0)
        self.set_font('Arial', '', 10)
        self.set_text_color(247, 147, 26)
        clean_value = str(value).encode('latin-1', errors='ignore').decode('latin-1')
        self.cell(55, 7, clean_value, 0, 0)
        if subtext:
            self.set_font('Arial', 'I', 8)
            self.set_text_color(100, 100, 100)
            clean_subtext = str(subtext).encode('latin-1', errors='ignore').decode('latin-1')
            self.cell(0, 7, clean_subtext, 0, 1)
        else:
            self.ln(7)
    
    def add_section_break(self):
        self.ln(3)
        self.set_draw_color(200, 200, 200)
        self.line(self.get_x(), self.get_y(), self.get_x() + 190, self.get_y())
        self.ln(3)


class BTCEmailSender:
    def __init__(self):
        """Initialize email sender"""
        self.indicators = None
        self.results = None
        self.ml_predictions = None
        self.ml_performance = None
        self.pdf_path = None
        
    def get_db_config(self):
        """Reads MySQL configuration from .env"""
        return {
            "host": os.getenv("db_host", os.getenv("DB_HOST", "localhost")),
            "user": os.getenv("db_user", os.getenv("DB_USER", "root")),
            "password": os.getenv("db_password", os.getenv("DB_PASSWORD", "")),
            "database": os.getenv("db_name", os.getenv("DB_NAME", "btc_prediction"))
        }
    
    def get_db_connection(self):
        """Create MySQL connection."""
        config = self.get_db_config()
        try:
            connection = mysql.connector.connect(
                host=config["host"],
                user=config["user"],
                password=config["password"],
                database=config["database"]
            )
            return connection
        except Error as e:
            logger.error(f"❌ MySQL connection error: {e}")
            return None
    
    def get_indicators(self):
        """Call btc_indicators.py and get results"""
        try:
            logger.info("🔄 Calling btc_indicators.py...")
            self.indicators = BTCIndicators()
            self.results = self.indicators.calculate_all_indicators()
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
    
    def load_ml_predictions(self, days=7):
        """Load ML predictions from database"""
        connection = self.get_db_connection()
        if connection is None:
            return pd.DataFrame()
        
        query = """
            SELECT
                prediction_date,
                model_name,
                current_close,
                predicted_return,
                predicted_price,
                predicted_direction,
                actual_return,
                actual_price,
                actual_direction,
                evaluated,
                created_at
            FROM btc_predictions
            WHERE prediction_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY prediction_date ASC, model_name ASC
        """
        
        try:
            df = pd.read_sql(query, connection, params=(days,))
            connection.close()
            if not df.empty:
                df["prediction_date"] = pd.to_datetime(df["prediction_date"])
            return df
        except Exception as e:
            connection.close()
            logger.warning(f"⚠️ Could not load ML predictions: {e}")
            return pd.DataFrame()
    
    def load_ml_performance(self):
        """Load model performance from database"""
        connection = self.get_db_connection()
        if connection is None:
            return pd.DataFrame()
        
        query = """
            SELECT
                evaluation_date,
                period_start,
                period_end,
                model_name,
                total_predictions,
                mae,
                rmse,
                directional_accuracy,
                avg_predicted_return,
                avg_actual_return,
                total_strategy_return,
                win_rate,
                model_rank,
                created_at
            FROM btc_model_performance
            ORDER BY evaluation_date DESC, model_rank ASC
        """
        
        try:
            df = pd.read_sql(query, connection)
            connection.close()
            if not df.empty:
                df["evaluation_date"] = pd.to_datetime(df["evaluation_date"])
            return df
        except Exception:
            connection.close()
            return pd.DataFrame()
    
    def clean_text(self, text):
        """Clean text for PDF to avoid encoding issues"""
        if text is None:
            return ""
        replacements = {
            '₿': 'BTC',
            '📈': '[UP]',
            '📉': '[DOWN]',
            '➡️': '[RANGE]',
            '🟢': '[BUY]',
            '🔴': '[SELL]',
            '🟡': '[NEUTRAL]',
            '📊': '[CHART]',
            '🎯': '[TARGET]',
            '💰': '[PRICE]',
            '💧': '[LIQUIDITY]',
            '📍': '[LOCATION]',
            '📧': '[EMAIL]',
            '🚀': '[ROCKET]',
            '✅': '[OK]',
            '❌': '[ERROR]',
            '⚠️': '[WARNING]',
            '🏆': '[TROPHY]',
            '🥇': '[GOLD]',
            '🤖': '[ROBOT]',
            '📅': '[CALENDAR]',
            '📋': '[LIST]',
            '📁': '[FOLDER]',
            '🔄': '[REFRESH]',
            '📎': '[ATTACHMENT]',
            '📄': '[DOCUMENT]',
            '💾': '[SAVE]',
            '📥': '[DOWNLOAD]',
            '📤': '[UPLOAD]',
            '🔮': '[CRYSTAL]',
        }
        
        result = str(text)
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result.encode('latin-1', errors='ignore').decode('latin-1')
    
    def create_pdf_report(self):
        """Create PDF report with FULL dashboard data including ML"""
        if not self.results:
            return None
        
        try:
            pdf = PDFReport()
            
            # ============================================================
            # PAGE 1: MAIN DASHBOARD
            # ============================================================
            pdf.add_page()
            
            # Current Price
            current_price = self.results.get('current_price', 0)
            pdf.set_font('Arial', 'B', 22)
            pdf.set_text_color(247, 147, 26)
            pdf.cell(0, 12, f'BTC ${current_price:,.2f}', 0, 1, 'C')
            pdf.ln(3)
            
            # Overall Signal
            if 'overall_signal' in self.results:
                signal = self.results['overall_signal']
                direction = signal.get('direction', 'NEUTRAL')
                confidence = signal.get('confidence', 'Unknown')
                score = signal.get('normalized_score', signal.get('score', 0))
                
                pdf.set_font('Arial', 'B', 14)
                if 'BUY' in direction:
                    pdf.set_text_color(0, 200, 0)
                elif 'SELL' in direction:
                    pdf.set_text_color(200, 0, 0)
                else:
                    pdf.set_text_color(200, 200, 0)
                pdf.cell(0, 10, f'SIGNAL: {direction} (Score: {score:.2f})', 0, 1, 'C')
                pdf.set_font('Arial', '', 11)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 8, f'Confidence: {confidence}', 0, 1, 'C')
                pdf.ln(3)
            
            pdf.add_section_break()
            
            # Technical Indicators
            pdf.chapter_title('TECHNICAL INDICATORS')
            
            # Market Structure
            if 'market_structure' in self.results:
                structure = self.results['market_structure']
                pdf.add_metric('Trend Regime', structure.get('trend_regime', 'Unknown'))
                bos = structure.get('bos', [])
                choch = structure.get('choch', [])
                pdf.add_metric('BOS/CHOCH', f'{len(bos)} BOS, {len(choch)} CHOCH')
                
                if 'hh_hl_lh_ll' in structure:
                    hh_hl = structure['hh_hl_lh_ll']
                    pdf.add_metric('HH/HL/LH/LL', 
                        f"HH:{hh_hl.get('HH',0)} HL:{hh_hl.get('HL',0)} LH:{hh_hl.get('LH',0)} LL:{hh_hl.get('LL',0)}")
            
            # Support & Resistance
            if 'support_resistance' in self.results:
                sr = self.results['support_resistance']
                support = sr.get('nearest_support', {})
                resistance = sr.get('nearest_resistance', {})
                pdf.add_metric('Nearest Support', f'${support.get("price", 0):,.2f}', f'Strength: {support.get("strength", 0)} touches')
                pdf.add_metric('Nearest Resistance', f'${resistance.get("price", 0):,.2f}', f'Strength: {resistance.get("strength", 0)} touches')
            
            # RSI
            if 'rsi' in self.results:
                rsi = self.results['rsi']
                pdf.add_metric('RSI', f'{rsi.get("value", 0):.1f}', f'Status: {rsi.get("status", "Neutral")}')
            
            # MACD
            if 'macd' in self.results:
                macd = self.results['macd']
                pdf.add_metric('MACD', f'{macd.get("macd", 0):.2f}', f'Signal: {macd.get("signal_status", "Neutral")}')
            
            # ATR
            if 'atr' in self.results:
                atr = self.results['atr']
                pdf.add_metric('ATR', f'${atr.get("atr", 0):.2f}', f'{atr.get("percentile", 0):.0f}th percentile')
            
            # Bollinger Bands
            if 'bollinger_bands' in self.results:
                bb = self.results['bollinger_bands']
                pdf.add_metric('Bollinger Bands', f'Upper: ${bb.get("upper_band", 0):,.2f}')
                pdf.add_metric('', f'Mid: ${bb.get("middle_band", 0):,.2f}')
                pdf.add_metric('', f'Lower: ${bb.get("lower_band", 0):,.2f}')
                pdf.add_metric('Position', bb.get('position', 'Inside Bands'))
                pdf.add_metric('Squeeze', bb.get('squeeze', 'No'))
            
            pdf.add_section_break()
            
            # Moving Averages
            pdf.chapter_title('MOVING AVERAGES')
            if 'moving_averages' in self.results:
                ma = self.results['moving_averages']
                for period, data in ma.items():
                    trend = data.get('trend', 'Neutral')
                    pdf.add_metric(f'{period}', f'${data["value"]:,.2f}', f'Trend: {trend} | Slope: {data.get("slope", 0):.2f}%')
            
            pdf.add_section_break()
            
            # Fibonacci & Pivot
            pdf.chapter_title('FIBONACCI & PIVOT POINTS')
            
            if 'fibonacci' in self.results:
                fib = self.results['fibonacci']
                if fib:
                    pdf.add_metric('Swing High', f'${fib.get("swing_high", 0):,.2f}', fib.get('high_date', 'N/A'))
                    pdf.add_metric('Swing Low', f'${fib.get("swing_low", 0):,.2f}', fib.get('low_date', 'N/A'))
                    pdf.add_metric('Current Level', fib.get('current_fib_level', 'N/A'))
            
            if 'pivot_points' in self.results:
                pivot = self.results['pivot_points']
                pdf.add_metric('Pivot', f'${pivot.get("pivot", 0):,.2f}')
                pdf.add_metric('Position', pivot.get('current_position', 'Below Pivot'))
                pdf.add_metric('R1/R2/R3', 
                    f'${pivot.get("resistance_1",0):,.2f} / ${pivot.get("resistance_2",0):,.2f} / ${pivot.get("resistance_3",0):,.2f}')
                pdf.add_metric('S1/S2/S3', 
                    f'${pivot.get("support_1",0):,.2f} / ${pivot.get("support_2",0):,.2f} / ${pivot.get("support_3",0):,.2f}')
            
            pdf.add_section_break()
            
            # Liquidity
            pdf.chapter_title('LIQUIDITY ANALYSIS')
            if 'liquidity' in self.results:
                liq = self.results['liquidity']
                pdf.add_metric('30-Day Avg Volume', f'{liq.get("avg_volume_30d", 0):,.0f}')
                pdf.add_metric('Volume Ratio', f'{liq.get("volume_ratio", 0):.2f}x')
                
                if 'volume_profile' in liq:
                    vp = liq['volume_profile']
                    if vp:
                        pdf.add_metric('POC', f'${vp.get("poc", 0):,.2f}')
                        pdf.add_metric('VAH', f'${vp.get("vah", 0):,.2f}')
                        pdf.add_metric('VAL', f'${vp.get("val", 0):,.2f}')
            
            # ============================================================
            # PAGE 2: ML PREDICTIONS
            # ============================================================
            pdf.add_page()
            pdf.chapter_title('MACHINE LEARNING PREDICTIONS')
            
            # Load ML data
            self.ml_predictions = self.load_ml_predictions(days=7)
            self.ml_performance = self.load_ml_performance()
            
            if not self.ml_predictions.empty:
                latest_date = self.ml_predictions['prediction_date'].max()
                pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 8, f'Latest Prediction Date: {latest_date.strftime("%d %b %Y")}', 0, 1)
                pdf.ln(3)
                
                # Model predictions table
                latest_preds = self.ml_predictions[self.ml_predictions['prediction_date'] == latest_date]
                
                model_names = {
                    'linear_regression': 'Linear Regression',
                    'random_forest': 'Random Forest', 
                    'xgboost': 'XGBoost',
                    'lightgbm': 'LightGBM',
                    'lstm': 'LSTM',
                    'gru': 'GRU'
                }
                
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(40, 7, 'Model', 1, 0, 'C')
                pdf.cell(35, 7, 'Predicted Price', 1, 0, 'C')
                pdf.cell(35, 7, 'Predicted Return', 1, 0, 'C')
                pdf.cell(35, 7, 'Direction', 1, 0, 'C')
                pdf.cell(45, 7, 'Result', 1, 1, 'C')
                
                pdf.set_font('Arial', '', 8)
                for _, row in latest_preds.iterrows():
                    model_name = model_names.get(row['model_name'], row['model_name'])
                    clean_model = self.clean_text(model_name)
                    
                    predicted_price = f"${row['predicted_price']:,.2f}" if pd.notna(row['predicted_price']) else 'N/A'
                    predicted_return = f"{row['predicted_return']*100:+.2f}%" if pd.notna(row['predicted_return']) else 'N/A'
                    
                    direction = 'UP' if int(row['predicted_direction']) == 1 else 'DOWN'
                    
                    result = 'Pending'
                    if pd.notna(row['actual_direction']):
                        if int(row['predicted_direction']) == int(row['actual_direction']):
                            result = '✅ Correct'
                        else:
                            result = '❌ Wrong'
                    
                    pdf.cell(40, 6, clean_model, 1, 0)
                    pdf.cell(35, 6, predicted_price, 1, 0)
                    pdf.cell(35, 6, predicted_return, 1, 0)
                    pdf.cell(35, 6, direction, 1, 0)
                    pdf.cell(45, 6, result, 1, 1)
                
                pdf.ln(5)
                
                # All predictions table
                pdf.chapter_title('7-DAY PREDICTION HISTORY')
                pdf.set_font('Arial', 'B', 8)
                pdf.cell(25, 6, 'Date', 1, 0, 'C')
                pdf.cell(40, 6, 'Model', 1, 0, 'C')
                pdf.cell(30, 6, 'Predicted Price', 1, 0, 'C')
                pdf.cell(30, 6, 'Predicted Return', 1, 0, 'C')
                pdf.cell(25, 6, 'Direction', 1, 0, 'C')
                pdf.cell(30, 6, 'Result', 1, 1, 'C')
                
                pdf.set_font('Arial', '', 7)
                for _, row in self.ml_predictions.head(20).iterrows():
                    model_name = model_names.get(row['model_name'], row['model_name'])
                    clean_model = self.clean_text(model_name)
                    date_str = row['prediction_date'].strftime('%d %b')
                    
                    predicted_price = f"${row['predicted_price']:,.2f}" if pd.notna(row['predicted_price']) else 'N/A'
                    predicted_return = f"{row['predicted_return']*100:+.2f}%" if pd.notna(row['predicted_return']) else 'N/A'
                    
                    direction = 'UP' if int(row['predicted_direction']) == 1 else 'DOWN'
                    
                    result = 'Pending'
                    if pd.notna(row['actual_direction']):
                        if int(row['predicted_direction']) == int(row['actual_direction']):
                            result = 'Correct'
                        else:
                            result = 'Wrong'
                    
                    pdf.cell(25, 5, date_str, 1, 0)
                    pdf.cell(40, 5, clean_model, 1, 0)
                    pdf.cell(30, 5, predicted_price, 1, 0)
                    pdf.cell(30, 5, predicted_return, 1, 0)
                    pdf.cell(25, 5, direction, 1, 0)
                    pdf.cell(30, 5, result, 1, 1)
            
            # ============================================================
            # PAGE 3: MODEL PERFORMANCE
            # ============================================================
            if not self.ml_performance.empty:
                pdf.add_page()
                pdf.chapter_title('MODEL PERFORMANCE RANKING')
                
                latest_eval = self.ml_performance['evaluation_date'].max()
                latest_perf = self.ml_performance[self.ml_performance['evaluation_date'] == latest_eval]
                latest_perf = latest_perf.sort_values('model_rank')
                
                model_names = {
                    'linear_regression': 'Linear Regression',
                    'random_forest': 'Random Forest', 
                    'xgboost': 'XGBoost',
                    'lightgbm': 'LightGBM',
                    'lstm': 'LSTM',
                    'gru': 'GRU'
                }
                
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(15, 7, 'Rank', 1, 0, 'C')
                pdf.cell(35, 7, 'Model', 1, 0, 'C')
                pdf.cell(25, 7, 'Predictions', 1, 0, 'C')
                pdf.cell(25, 7, 'Accuracy', 1, 0, 'C')
                pdf.cell(25, 7, 'Win Rate', 1, 0, 'C')
                pdf.cell(30, 7, 'MAE', 1, 0, 'C')
                pdf.cell(35, 7, 'Strategy Return', 1, 1, 'C')
                
                pdf.set_font('Arial', '', 8)
                for _, row in latest_perf.iterrows():
                    model_name = model_names.get(row['model_name'], row['model_name'])
                    clean_model = self.clean_text(model_name)
                    
                    pdf.cell(15, 6, f"#{int(row['model_rank'])}", 1, 0, 'C')
                    pdf.cell(35, 6, clean_model, 1, 0)
                    pdf.cell(25, 6, str(int(row['total_predictions'])), 1, 0, 'C')
                    pdf.cell(25, 6, f"{float(row['directional_accuracy']):.1f}%", 1, 0, 'C')
                    pdf.cell(25, 6, f"{float(row['win_rate']):.1f}%", 1, 0, 'C')
                    pdf.cell(30, 6, f"{float(row['mae']):.5f}", 1, 0, 'C')
                    pdf.cell(35, 6, f"{float(row['total_strategy_return']):+.2f}%", 1, 1, 'C')
                
                winner = latest_perf.iloc[0]
                pdf.ln(5)
                pdf.set_font('Arial', 'B', 12)
                pdf.set_text_color(247, 147, 26)
                winner_name = model_names.get(winner['model_name'], winner['model_name'])
                pdf.cell(0, 10, f'🏆 WEEKLY WINNER: {self.clean_text(winner_name)}', 0, 1, 'C')
                pdf.set_font('Arial', '', 10)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 7, f'Directional Accuracy: {float(winner["directional_accuracy"]):.2f}%  |  Strategy Return: {float(winner["total_strategy_return"]):+.2f}%', 0, 1, 'C')
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            pdf_path = f'btc_dashboard_full_report_{timestamp}.pdf'
            pdf.output(pdf_path)
            
            logger.info(f"✅ PDF report created: {pdf_path}")
            self.pdf_path = pdf_path
            return pdf_path
            
        except Exception as e:
            logger.error(f"❌ Error creating PDF: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_html_email(self):
        """Create HTML email content with ALL dashboard data (same as PDF)"""
        if not self.results:
            return None
        
        # Load ML data
        self.ml_predictions = self.load_ml_predictions(days=7)
        self.ml_performance = self.load_ml_performance()
        
        model_names = {
            'linear_regression': 'Linear Regression',
            'random_forest': 'Random Forest', 
            'xgboost': 'XGBoost',
            'lightgbm': 'LightGBM',
            'lstm': 'LSTM',
            'gru': 'GRU'
        }
        
        # ============================================================
        # Build ML Predictions HTML
        # ============================================================
        ml_html = ""
        if not self.ml_predictions.empty:
            latest_date = self.ml_predictions['prediction_date'].max()
            latest_preds = self.ml_predictions[self.ml_predictions['prediction_date'] == latest_date]
            
            ml_html += f"""
                <div class="section">
                    <div class="section-title">🤖 Machine Learning Predictions</div>
                    <div style="font-size:14px; color:#666; margin-bottom:10px;">📅 Latest Prediction: {latest_date.strftime('%d %b %Y')}</div>
                    <table>
                        <tr><th>Model</th><th>Predicted Price</th><th>Predicted Return</th><th>Direction</th><th>Result</th></tr>
            """
            
            for _, row in latest_preds.iterrows():
                model_name = model_names.get(row['model_name'], row['model_name'])
                predicted_price = f"${row['predicted_price']:,.2f}" if pd.notna(row['predicted_price']) else 'N/A'
                predicted_return = f"{row['predicted_return']*100:+.2f}%" if pd.notna(row['predicted_return']) else 'N/A'
                direction = '🟢 UP' if int(row['predicted_direction']) == 1 else '🔴 DOWN'
                
                result = '⏳ Pending'
                if pd.notna(row['actual_direction']):
                    if int(row['predicted_direction']) == int(row['actual_direction']):
                        result = '✅ Correct'
                    else:
                        result = '❌ Wrong'
                
                ml_html += f"""
                    <tr>
                        <td><strong>{model_name}</strong></td>
                        <td>{predicted_price}</td>
                        <td>{predicted_return}</td>
                        <td>{direction}</td>
                        <td>{result}</td>
                    </tr>
                """
            
            ml_html += "</table></div>"
            
            # 7-Day Prediction History
            ml_html += f"""
                <div class="section">
                    <div class="section-title">📅 7-Day Prediction History</div>
                    <table>
                        <tr><th>Date</th><th>Model</th><th>Predicted Price</th><th>Predicted Return</th><th>Direction</th><th>Result</th></tr>
            """
            
            for _, row in self.ml_predictions.head(20).iterrows():
                model_name = model_names.get(row['model_name'], row['model_name'])
                date_str = row['prediction_date'].strftime('%d %b')
                predicted_price = f"${row['predicted_price']:,.2f}" if pd.notna(row['predicted_price']) else 'N/A'
                predicted_return = f"{row['predicted_return']*100:+.2f}%" if pd.notna(row['predicted_return']) else 'N/A'
                direction = '🟢 UP' if int(row['predicted_direction']) == 1 else '🔴 DOWN'
                
                result = '⏳ Pending'
                if pd.notna(row['actual_direction']):
                    if int(row['predicted_direction']) == int(row['actual_direction']):
                        result = '✅ Correct'
                    else:
                        result = '❌ Wrong'
                
                ml_html += f"""
                    <tr>
                        <td>{date_str}</td>
                        <td>{model_name}</td>
                        <td>{predicted_price}</td>
                        <td>{predicted_return}</td>
                        <td>{direction}</td>
                        <td>{result}</td>
                    </tr>
                """
            
            ml_html += "</table></div>"
        
        # ============================================================
        # Build ML Performance HTML
        # ============================================================
        perf_html = ""
        if not self.ml_performance.empty:
            latest_eval = self.ml_performance['evaluation_date'].max()
            latest_perf = self.ml_performance[self.ml_performance['evaluation_date'] == latest_eval]
            latest_perf = latest_perf.sort_values('model_rank')
            
            winner = latest_perf.iloc[0] if not latest_perf.empty else None
            
            perf_html += f"""
                <div class="section">
                    <div class="section-title">🏆 Weekly Model Performance</div>
                    <div style="font-size:14px; color:#666; margin-bottom:10px;">📅 Evaluation Date: {latest_eval.strftime('%d %b %Y')}</div>
            """
            
            if winner is not None:
                winner_name = model_names.get(winner['model_name'], winner['model_name'])
                perf_html += f"""
                    <div style="text-align:center; padding:15px; background: linear-gradient(135deg, #fff3e0, #ffe0b2); border-radius:8px; margin:10px 0; border: 2px solid #f7931a;">
                        <strong style="font-size:18px; color:#f7931a;">🥇 Weekly Winner: {winner_name}</strong><br>
                        <span style="font-size:14px;">
                            Directional Accuracy: <strong>{float(winner['directional_accuracy']):.2f}%</strong> | 
                            Win Rate: <strong>{float(winner['win_rate']):.2f}%</strong> | 
                            Strategy Return: <strong>{float(winner['total_strategy_return']):+.2f}%</strong>
                        </span>
                    </div>
                """
            
            perf_html += """
                    <table>
                        <tr><th>Rank</th><th>Model</th><th>Predictions</th><th>Accuracy</th><th>Win Rate</th><th>MAE</th><th>Strategy Return</th></tr>
            """
            
            for _, row in latest_perf.iterrows():
                model_name = model_names.get(row['model_name'], row['model_name'])
                rank_color = '#f7931a' if int(row['model_rank']) == 1 else '#333'
                perf_html += f"""
                    <tr>
                        <td style="color:{rank_color}; font-weight:bold;">#{int(row['model_rank'])}</td>
                        <td><strong>{model_name}</strong></td>
                        <td>{int(row['total_predictions'])}</td>
                        <td>{float(row['directional_accuracy']):.2f}%</td>
                        <td>{float(row['win_rate']):.2f}%</td>
                        <td>{float(row['mae']):.5f}</td>
                        <td style="color:{'green' if float(row['total_strategy_return']) > 0 else 'red'}; font-weight:bold;">{float(row['total_strategy_return']):+.2f}%</td>
                    </tr>
                """
            
            perf_html += "</table></div>"
        
        # ============================================================
        # Build Signal Factors HTML
        # ============================================================
        factors_html = ""
        if 'overall_signal' in self.results:
            signal = self.results['overall_signal']
            
            if 'factors' in signal and signal['factors']:
                factors_html += """
                    <div class="section">
                        <div class="section-title">📋 Signal Factors</div>
                        <ul style="columns: 2; -webkit-columns: 2; -moz-columns: 2;">
                """
                for factor in signal['factors']:
                    factors_html += f"<li style='padding: 3px 0;'>{factor}</li>"
                factors_html += """
                        </ul>
                    </div>
                """
            
            if 'weights' in signal:
                factors_html += """
                    <div class="section">
                        <div class="section-title">⚖️ Indicator Weights</div>
                        <ul style="columns: 2; -webkit-columns: 2; -moz-columns: 2;">
                """
                for key, weight in signal['weights'].items():
                    factors_html += f"<li style='padding: 3px 0;'>{key}: {weight:.0%}</li>"
                factors_html += """
                        </ul>
                    </div>
                """
        
        # ============================================================
        # Build Fibonacci Levels HTML
        # ============================================================
        fib_html = ""
        if 'fibonacci' in self.results:
            fib = self.results['fibonacci']
            if fib and fib.get('fib_levels'):
                fib_html += f"""
                    <div class="section">
                        <div class="section-title">📊 Fibonacci Levels</div>
                        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:8px;">
                """
                for level, price in fib.get('fib_levels', {}).items():
                    if level in ['0.0%', '100.0%']:
                        fib_html += f"""
                            <div style="background:#e8f5e9; padding:6px 10px; border-radius:4px; text-align:center;">
                                <strong style="font-size:12px;">{level}</strong><br>
                                <span style="font-size:12px; color:#2e7d32;">${price:,.2f}</span>
                            </div>
                        """
                    elif level in ['23.6%', '38.2%', '50.0%', '61.8%', '78.6%']:
                        fib_html += f"""
                            <div style="background:#fff3e0; padding:6px 10px; border-radius:4px; text-align:center;">
                                <strong style="font-size:12px;">{level}</strong><br>
                                <span style="font-size:12px; color:#e65100;">${price:,.2f}</span>
                            </div>
                        """
                    else:
                        fib_html += f"""
                            <div style="background:#f5f5f5; padding:6px 10px; border-radius:4px; text-align:center;">
                                <strong style="font-size:12px;">{level}</strong><br>
                                <span style="font-size:12px; color:#333;">${price:,.2f}</span>
                            </div>
                        """
                fib_html += """
                        </div>
                    </div>
                """
        
        # ============================================================
        # Build Support & Resistance Levels HTML
        # ============================================================
        sr_html = ""
        if 'support_resistance' in self.results:
            sr = self.results['support_resistance']
            
            if 'support_levels' in sr and sr['support_levels']:
                sr_html += """
                    <div class="section">
                        <div class="section-title">📊 All Support Levels</div>
                        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr; gap:8px;">
                """
                for s in sr['support_levels'][:5]:
                    sr_html += f"""
                        <div style="background:#e8f5e9; padding:8px; border-radius:4px; text-align:center;">
                            <div style="font-size:12px; color:#2e7d32;">${s['price']:,.2f}</div>
                            <div style="font-size:10px; color:#666;">{s['strength']} touches</div>
                        </div>
                    """
                sr_html += """
                        </div>
                    </div>
                """
            
            if 'resistance_levels' in sr and sr['resistance_levels']:
                sr_html += """
                    <div class="section">
                        <div class="section-title">📊 All Resistance Levels</div>
                        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr; gap:8px;">
                """
                for r in sr['resistance_levels'][:5]:
                    sr_html += f"""
                        <div style="background:#ffebee; padding:8px; border-radius:4px; text-align:center;">
                            <div style="font-size:12px; color:#c62828;">${r['price']:,.2f}</div>
                            <div style="font-size:10px; color:#666;">{r['strength']} touches</div>
                        </div>
                    """
                sr_html += """
                        </div>
                    </div>
                """
        
        # ============================================================
        # Build Liquidity HVN/LVN HTML
        # ============================================================
        liq_html = ""
        if 'liquidity' in self.results:
            liq = self.results['liquidity']
            
            if 'high_volume_nodes' in liq and liq['high_volume_nodes']:
                liq_html += """
                    <div class="section">
                        <div class="section-title">📊 High Volume Nodes (HVN)</div>
                        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr; gap:8px;">
                """
                for node in liq['high_volume_nodes'][:5]:
                    liq_html += f"""
                        <div style="background:#e3f2fd; padding:8px; border-radius:4px; text-align:center;">
                            <div style="font-size:11px; color:#1565c0;">{node.get('price_range', 'N/A')}</div>
                            <div style="font-size:10px; color:#666;">{node.get('volume', 0):,.0f}</div>
                        </div>
                    """
                liq_html += """
                        </div>
                    </div>
                """
            
            if 'low_volume_nodes' in liq and liq['low_volume_nodes']:
                liq_html += """
                    <div class="section">
                        <div class="section-title">📊 Low Volume Nodes (LVN)</div>
                        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr; gap:8px;">
                """
                for node in liq['low_volume_nodes'][:5]:
                    liq_html += f"""
                        <div style="background:#fff3e0; padding:8px; border-radius:4px; text-align:center;">
                            <div style="font-size:11px; color:#e65100;">{node.get('price_range', 'N/A')}</div>
                            <div style="font-size:10px; color:#666;">{node.get('volume', 0):,.0f}</div>
                        </div>
                    """
                liq_html += """
                        </div>
                    </div>
                """
        
        # ============================================================
        # Main HTML Email
        # ============================================================
        current_price = self.results.get('current_price', 0)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px; }}
                .container {{ max-width: 1200px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #f7931a, #f9a825); color: white; padding: 25px; border-radius: 10px 10px 0 0; text-align: center; margin: -30px -30px 20px -30px; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header p {{ margin: 5px 0 0 0; opacity: 0.9; }}
                .section {{ margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px; border-left: 4px solid #f7931a; }}
                .section-title {{ font-size: 17px; font-weight: bold; color: #f7931a; margin-bottom: 10px; }}
                .price {{ font-size: 34px; font-weight: bold; color: #f7931a; text-align: center; padding: 15px; background: #fff3e0; border-radius: 8px; margin: 10px 0; }}
                .signal {{ font-size: 22px; font-weight: bold; text-align: center; padding: 15px; border-radius: 8px; margin: 10px 0; }}
                .signal-buy {{ background-color: #d4edda; color: #155724; border: 2px solid #28a745; }}
                .signal-sell {{ background-color: #f8d7da; color: #721c24; border: 2px solid #dc3545; }}
                .signal-neutral {{ background-color: #fff3cd; color: #856404; border: 2px solid #ffc107; }}
                .confidence-high {{ color: #28a745; font-weight: bold; }}
                .confidence-medium {{ color: #ffc107; font-weight: bold; }}
                .confidence-low {{ color: #dc3545; font-weight: bold; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px; }}
                th {{ background-color: #f7931a; color: white; padding: 10px; text-align: left; }}
                td {{ padding: 8px 10px; border-bottom: 1px solid #ddd; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .footer {{ text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
                .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
                .grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; }}
                .grid-4 {{ display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 15px; }}
                .stat-box {{ background: white; padding: 12px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }}
                .stat-label {{ font-size: 11px; color: #666; }}
                .stat-value {{ font-size: 16px; font-weight: bold; color: #333; }}
                .stat-value-large {{ font-size: 22px; font-weight: bold; color: #f7931a; }}
                .pdf-notice {{ background-color: #e8f4fd; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; border: 2px dashed #007bff; }}
                .pdf-notice strong {{ color: #007bff; }}
                .trend-up {{ color: #28a745; font-weight: bold; }}
                .trend-down {{ color: #dc3545; font-weight: bold; }}
                .trend-neutral {{ color: #ffc107; font-weight: bold; }}
                ul {{ list-style-type: none; padding: 0; margin: 5px 0; }}
                li {{ padding: 3px 0; }}
                @media only screen and (max-width: 600px) {{
                    .grid-2, .grid-3, .grid-4 {{ grid-template-columns: 1fr; }}
                    table {{ font-size: 11px; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 BTC AI Trading Dashboard - Complete Report</h1>
                    <p>{datetime.now().strftime('%A, %B %d, %Y - %H:%M:%S')}</p>
                </div>
                
                <div class="pdf-notice">
                    <strong>📄 Complete PDF Report Attached</strong><br>
                    Full dashboard report with all indicators and ML predictions is attached as PDF.
                </div>
                
                <div class="price">BTC ${current_price:,.2f}</div>
        """
        
        # ============================================================
        # Overall Signal
        # ============================================================
        if 'overall_signal' in self.results:
            signal = self.results['overall_signal']
            direction = signal.get('direction', 'NEUTRAL')
            score = signal.get('normalized_score', signal.get('score', 0))
            confidence = signal.get('confidence', 'Unknown')
            
            signal_class = 'signal-buy' if 'BUY' in direction else 'signal-sell' if 'SELL' in direction else 'signal-neutral'
            emoji = '🟢' if 'BUY' in direction else '🔴' if 'SELL' in direction else '🟡'
            conf_class = 'confidence-high' if confidence == 'High' else 'confidence-medium' if confidence == 'Medium' else 'confidence-low'
            
            html += f"""
                <div class="signal {signal_class}">
                    {emoji} {direction} (Score: {score:.2f})
                    <br>
                    <span style="font-size: 16px;">Confidence: <span class="{conf_class}">{confidence}</span></span>
                </div>
            """
        
        # ============================================================
        # Technical Indicators Grid
        # ============================================================
        html += """
            <div class="section">
                <div class="section-title">📊 Technical Indicators</div>
                <div class="grid-4">
        """
        
        # Market Structure
        if 'market_structure' in self.results:
            structure = self.results['market_structure']
            trend = structure.get('trend_regime', 'Unknown')
            trend_class = 'trend-up' if trend == 'Uptrend' else 'trend-down' if trend == 'Downtrend' else 'trend-neutral'
            bos = structure.get('bos', [])
            choch = structure.get('choch', [])
            html += f"""
                <div class="stat-box">
                    <div class="stat-label">Market Structure</div>
                    <div class="stat-value {trend_class}">{trend}</div>
                    <div style="font-size:11px; color:#666;">BOS: {len(bos)} | CHOCH: {len(choch)}</div>
                </div>
            """
        
        # Support & Resistance
        if 'support_resistance' in self.results:
            sr = self.results['support_resistance']
            support = sr.get('nearest_support', {})
            resistance = sr.get('nearest_resistance', {})
            html += f"""
                <div class="stat-box">
                    <div class="stat-label">Support / Resistance</div>
                    <div class="stat-value">${support.get('price', 0):,.2f}</div>
                    <div style="font-size:11px; color:#666;">Support</div>
                    <div class="stat-value">${resistance.get('price', 0):,.2f}</div>
                    <div style="font-size:11px; color:#666;">Resistance</div>
                </div>
            """
        
        # RSI
        if 'rsi' in self.results:
            rsi = self.results['rsi']
            rsi_value = rsi.get('value', 0)
            rsi_color = '#28a745' if rsi_value < 30 else '#dc3545' if rsi_value > 70 else '#ffc107'
            html += f"""
                <div class="stat-box">
                    <div class="stat-label">RSI</div>
                    <div class="stat-value" style="color:{rsi_color};">{rsi_value:.1f}</div>
                    <div style="font-size:11px; color:#666;">{rsi.get('status', 'Neutral')}</div>
                    <div style="font-size:10px; color:#999;">Period: {rsi.get('period', 14)}</div>
                </div>
            """
        
        # ATR
        if 'atr' in self.results:
            atr = self.results['atr']
            html += f"""
                <div class="stat-box">
                    <div class="stat-label">ATR</div>
                    <div class="stat-value">${atr.get('atr', 0):.2f}</div>
                    <div style="font-size:11px; color:#666;">{atr.get('percentile', 0):.0f}th percentile</div>
                </div>
            """
        
        html += '</div></div>'
        
        # ============================================================
        # MACD
        # ============================================================
        if 'macd' in self.results:
            macd = self.results['macd']
            html += f"""
                <div class="section">
                    <div class="section-title">📊 MACD</div>
                    <div class="grid-4">
                        <div class="stat-box">
                            <div class="stat-label">MACD Line</div>
                            <div class="stat-value">{macd.get('macd', 0):.3f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Signal Line</div>
                            <div class="stat-value">{macd.get('signal', 0):.3f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Histogram</div>
                            <div class="stat-value">{macd.get('histogram', 0):.3f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Signal Status</div>
                            <div class="stat-value">{macd.get('signal_status', 'Neutral')}</div>
                        </div>
                    </div>
                </div>
            """
        
        # ============================================================
        # Signal Factors
        # ============================================================
        html += factors_html
        
        # ============================================================
        # Moving Averages
        # ============================================================
        if 'moving_averages' in self.results:
            html += """
                <div class="section">
                    <div class="section-title">📈 Moving Averages</div>
                    <table>
                        <tr><th>Period</th><th>Value</th><th>EMA</th><th>Trend</th><th>Slope</th></tr>
            """
            for period, data in self.results['moving_averages'].items():
                trend = data.get('trend', 'Neutral')
                trend_class = 'trend-up' if 'Bullish' in trend else 'trend-down' if 'Bearish' in trend else 'trend-neutral'
                html += f"""
                    <tr>
                        <td><strong>{period}</strong></td>
                        <td>${data['value']:,.2f}</td>
                        <td>${data.get('ema', data['value']):,.2f}</td>
                        <td class="{trend_class}">{trend}</td>
                        <td>{data.get('slope', 0):.2f}%</td>
                    </tr>
                """
            html += "</table></div>"
        
        # ============================================================
        # Bollinger Bands
        # ============================================================
        if 'bollinger_bands' in self.results:
            bb = self.results['bollinger_bands']
            html += f"""
                <div class="section">
                    <div class="section-title">📊 Bollinger Bands</div>
                    <div class="grid-4">
                        <div class="stat-box">
                            <div class="stat-label">Upper Band</div>
                            <div class="stat-value" style="color:#28a745;">${bb.get('upper_band', 0):,.2f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Middle Band</div>
                            <div class="stat-value" style="color:#f7931a;">${bb.get('middle_band', 0):,.2f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Lower Band</div>
                            <div class="stat-value" style="color:#dc3545;">${bb.get('lower_band', 0):,.2f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Position</div>
                            <div class="stat-value">{bb.get('position', 'Inside Bands')}</div>
                            <div style="font-size:11px; color:#666;">Squeeze: {bb.get('squeeze', 'No')}</div>
                        </div>
                    </div>
                </div>
            """
        
        # ============================================================
        # Fibonacci
        # ============================================================
        html += fib_html
        
        # ============================================================
        # Pivot Points
        # ============================================================
        if 'pivot_points' in self.results:
            pivot = self.results['pivot_points']
            html += f"""
                <div class="section">
                    <div class="section-title">📊 Pivot Points</div>
                    <div class="grid-3">
                        <div class="stat-box">
                            <div class="stat-label">Pivot</div>
                            <div class="stat-value" style="color:#f7931a;">${pivot.get('pivot', 0):,.2f}</div>
                            <div style="font-size:11px; color:#666;">Position: {pivot.get('current_position', 'Below Pivot')}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Resistance Levels</div>
                            <div class="stat-value" style="font-size:14px; color:#dc3545;">
                                R1: ${pivot.get('resistance_1', 0):,.2f}<br>
                                R2: ${pivot.get('resistance_2', 0):,.2f}<br>
                                R3: ${pivot.get('resistance_3', 0):,.2f}
                            </div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Support Levels</div>
                            <div class="stat-value" style="font-size:14px; color:#28a745;">
                                S1: ${pivot.get('support_1', 0):,.2f}<br>
                                S2: ${pivot.get('support_2', 0):,.2f}<br>
                                S3: ${pivot.get('support_3', 0):,.2f}
                            </div>
                        </div>
                    </div>
                    <div style="text-align:center; margin-top:10px; font-size:14px;">
                        Nearest: {pivot.get('nearest_level', 'N/A')} (${pivot.get('distance_to_nearest', 0):.2f} away)
                    </div>
                </div>
            """
        
        # ============================================================
        # Support & Resistance Levels
        # ============================================================
        html += sr_html
        
        # ============================================================
        # Liquidity
        # ============================================================
        if 'liquidity' in self.results:
            liq = self.results['liquidity']
            html += f"""
                <div class="section">
                    <div class="section-title">💧 Liquidity Analysis</div>
                    <div class="grid-3">
                        <div class="stat-box">
                            <div class="stat-label">30-Day Avg Volume</div>
                            <div class="stat-value">{liq.get('avg_volume_30d', 0):,.0f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Overall Avg Volume</div>
                            <div class="stat-value">{liq.get('avg_volume_overall', 0):,.0f}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Volume Ratio</div>
                            <div class="stat-value">{liq.get('volume_ratio', 0):.2f}x</div>
                        </div>
                    </div>
            """
            
            if 'volume_profile' in liq:
                vp = liq['volume_profile']
                if vp:
                    html += f"""
                        <div class="grid-3" style="margin-top:10px;">
                            <div class="stat-box">
                                <div class="stat-label">POC</div>
                                <div class="stat-value">${vp.get('poc', 0):,.2f}</div>
                            </div>
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
            
            html += "</div>"
        
        # ============================================================
        # Liquidity HVN/LVN
        # ============================================================
        html += liq_html
        
        # ============================================================
        # ML Predictions
        # ============================================================
        html += ml_html
        
        # ============================================================
        # ML Performance
        # ============================================================
        html += perf_html
        
        # ============================================================
        # Footer
        # ============================================================
        html += """
                <div class="footer">
                    <p>📄 Complete PDF Dashboard attached separately with all charts and data.</p>
                    <p>Generated by BTC AI Trading Dashboard</p>
                    <p>Indicators: S/R, Market Structure, MA, RSI, MACD, BB, Fibonacci, Pivot, Liquidity, ATR</p>
                    <p>Models: Linear Regression, Random Forest, XGBoost, LightGBM, LSTM, GRU</p>
                    <p>© 2026 All Rights Reserved</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_email(self, subject, html_content, pdf_path=None):
        """Send email with HTML content and PDF attachment"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = EMAIL_SENDER
            msg['To'] = EMAIL_RECEIVER
            
            text_content = f"""
BTC AI Trading Dashboard - Complete Report
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Current Price: ${self.results.get('current_price', 0):,.2f}

Signal: {self.results.get('overall_signal', {}).get('direction', 'NEUTRAL')}
Confidence: {self.results.get('overall_signal', {}).get('confidence', 'Unknown')}

Market Structure: {self.results.get('market_structure', {}).get('trend_regime', 'Unknown')}

📄 Complete PDF Dashboard report is attached with all indicators and ML predictions.

Please view this email in HTML format for the complete report.
            """
            text_part = MIMEText(text_content, 'plain')
            msg.attach(text_part)
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    pdf_data = f.read()
                pdf_attachment = MIMEApplication(pdf_data, _subtype='pdf')
                pdf_attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(pdf_path))
                msg.attach(pdf_attachment)
                logger.info(f"📎 Attached PDF: {os.path.basename(pdf_path)}")
            
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
        """Main function to get indicators, create PDF, and send report"""
        logger.info("\n" + "="*60)
        logger.info("📧 SENDING COMPLETE BTC DASHBOARD REPORT WITH PDF")
        logger.info("="*60)
        
        if not self.get_indicators():
            logger.error("❌ Failed to get indicators")
            return False
        
        pdf_path = self.create_pdf_report()
        if not pdf_path:
            logger.warning("⚠️ Could not create PDF report. Sending email without attachment.")
        
        html_content = self.create_html_email()
        if not html_content:
            logger.error("❌ Failed to create email content")
            return False
        
        subject = f"BTC AI Dashboard Complete Report - {datetime.now().strftime('%Y-%m-%d')}"
        success = self.send_email(subject, html_content, pdf_path)
        
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                logger.info(f"🗑️ Cleaned up PDF: {pdf_path}")
            except Exception as e:
                logger.warning(f"⚠️ Could not delete PDF: {e}")
        
        if success:
            logger.info("✅ Report sent successfully!")
        else:
            logger.error("❌ Failed to send report")
        
        return success


def main():
    sender = BTCEmailSender()
    try:
        sender.send_report()
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()