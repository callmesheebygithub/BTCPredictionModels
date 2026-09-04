# dashboard.py
"""
BTC Predictor - Complete Streamlit Dashboard
Shows: Price charts, Predictions, Performance, Features, Support/Resistance
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
from datetime import datetime, timedelta
import os

# ============================================
# PAGE CONFIG
# ============================================

st.set_page_config(
    page_title="BTC Predictor Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# CSS STYLING
# ============================================

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #f7931a;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #1a1a2e;
    }
    .metric-label {
        font-size: 12px;
        color: #666;
    }
    .prediction-box {
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        border: 2px solid #f7931a;
    }
    .prediction-price {
        font-size: 36px;
        font-weight: bold;
        color: #1a1a2e;
    }
    .prediction-change {
        font-size: 18px;
        font-weight: bold;
    }
    .positive { color: #28a745; }
    .negative { color: #dc3545; }
    .neutral { color: #ffc107; }
    .sr-level {
        background: white;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        margin: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .sr-resistance { border-left: 4px solid #dc3545; }
    .sr-support { border-left: 4px solid #28a745; }
    .sr-current { border-left: 4px solid #f7931a; background: #f7931a10; }
</style>
""", unsafe_allow_html=True)

# ============================================
# DATABASE FUNCTIONS
# ============================================

def get_db_connection():
    """Get database connection"""
    db_path = 'btc_data.db'
    if not os.path.exists(db_path):
        return None
    return sqlite3.connect(db_path)

def load_data():
    """Load all data from database"""
    conn = get_db_connection()
    if conn is None:
        return None, None, None, None
    
    # BTC daily data
    btc_data = pd.read_sql_query("SELECT * FROM btc_daily ORDER BY date", conn)
    
    # Predictions
    predictions = pd.read_sql_query("SELECT * FROM predictions ORDER BY date DESC", conn)
    
    # Performance
    performance = pd.read_sql_query("SELECT * FROM performance ORDER BY date DESC LIMIT 30", conn)
    
    # Model versions
    models = pd.read_sql_query("SELECT * FROM model_versions ORDER BY created_at DESC", conn)
    
    conn.close()
    
    return btc_data, predictions, performance, models

def calculate_support_resistance(df):
    """Calculate Support & Resistance levels"""
    if df is None or len(df) < 20:
        return {}
    
    recent = df.tail(20)
    high = recent['high'].max()
    low = recent['low'].min()
    close = recent['close'].iloc[-1]
    
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)
    
    return {
        'r3': r3, 'r2': r2, 'r1': r1,
        'pivot': pivot,
        's1': s1, 's2': s2, 's3': s3
    }

# ============================================
# MAIN DASHBOARD
# ============================================

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🚀 BTC Predictor Dashboard</h1>
        <p style="opacity:0.8;">Real-time Bitcoin Price Prediction & Analysis</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Load data
    btc_data, predictions, performance, models = load_data()
    
    if btc_data is None or btc_data.empty:
        st.error("❌ No data found! Please run `python main.py` first.")
        return
    
    # ============================================
    # SIDEBAR
    # ============================================
    
    with st.sidebar:
        st.header("📊 Controls")
        
        # Date range selector
        min_date = btc_data['date'].min()
        max_date = btc_data['date'].max()
        days = st.slider("Days to show", 30, 730, 90)
        
        st.divider()
        
        # Model info
        st.subheader("🤖 Model Info")
        if models is not None and not models.empty:
            champion = models[models['is_champion'] == 1]
            if not champion.empty:
                st.success(f"🏆 Champion: {champion.iloc[0]['version']}")
            st.write(f"Total Models: {len(models)}")
        
        st.divider()
        
        # Refresh button
        if st.button("🔄 Refresh Data"):
            st.rerun()
    
    # ============================================
    # TOP METRICS
    # ============================================
    
    col1, col2, col3, col4 = st.columns(4)
    
    current_price = btc_data['close'].iloc[-1]
    price_change = ((btc_data['close'].iloc[-1] - btc_data['close'].iloc[-2]) / btc_data['close'].iloc[-2]) * 100
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Current Price</div>
            <div class="metric-value">${current_price:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        color = "positive" if price_change >= 0 else "negative"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">24h Change</div>
            <div class="metric-value {color}">{price_change:+.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Latest prediction
        if predictions is not None and not predictions.empty:
            latest_pred = predictions.iloc[0]
            pred_price = latest_pred['predicted_close']
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Next Day Prediction</div>
                <div class="metric-value">${pred_price:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="metric-card">
                <div class="metric-label">Next Day Prediction</div>
                <div class="metric-value">-</div>
            </div>
            """, unsafe_allow_html=True)
    
    with col4:
        if predictions is not None and not predictions.empty:
            latest_pred = predictions.iloc[0]
            confidence = latest_pred.get('confidence_score', 0) or 0
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Confidence</div>
                <div class="metric-value">{confidence:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="metric-card">
                <div class="metric-label">Confidence</div>
                <div class="metric-value">-</div>
            </div>
            """, unsafe_allow_html=True)
    
    # ============================================
    # PRICE CHART
    # ============================================
    
    st.subheader("📈 BTC Price Chart")
    
    # Filter data
    filtered_data = btc_data.tail(days)
    
    # Create subplot
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
        subplot_titles=("BTC Price", "Volume")
    )
    
    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=filtered_data['date'],
            open=filtered_data['open'],
            high=filtered_data['high'],
            low=filtered_data['low'],
            close=filtered_data['close'],
            name='BTC',
            increasing_line_color='#28a745',
            decreasing_line_color='#dc3545'
        ),
        row=1, col=1
    )
    
    # Add predictions as markers
    if predictions is not None and not predictions.empty:
        pred_dates = predictions['date'].tolist()
        pred_prices = predictions['predicted_close'].tolist()
        
        # Filter predictions within date range
        pred_data = []
        for i, date in enumerate(pred_dates):
            if date >= filtered_data['date'].min():
                pred_data.append((date, pred_prices[i]))
        
        if pred_data:
            pred_dates_filtered = [p[0] for p in pred_data]
            pred_prices_filtered = [p[1] for p in pred_data]
            
            fig.add_trace(
                go.Scatter(
                    x=pred_dates_filtered,
                    y=pred_prices_filtered,
                    mode='markers+lines',
                    name='Predictions',
                    line=dict(color='#f7931a', dash='dash'),
                    marker=dict(color='#f7931a', size=8)
                ),
                row=1, col=1
            )
    
    # Volume chart
    fig.add_trace(
        go.Bar(
            x=filtered_data['date'],
            y=filtered_data['volume'],
            name='Volume',
            marker_color='#1a1a2e'
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        height=600,
        template='plotly_white',
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # ============================================
    # SUPPORT & RESISTANCE
    # ============================================
    
    st.subheader("📊 Support & Resistance Levels")
    
    sr_levels = calculate_support_resistance(btc_data)
    
    if sr_levels:
        cols = st.columns(7)
        
        sr_items = [
            ("🚀 R3", sr_levels.get('r3', 0), "resistance"),
            ("📈 R2", sr_levels.get('r2', 0), "resistance"),
            ("📊 R1", sr_levels.get('r1', 0), "resistance"),
            ("📍 Current", current_price, "current"),
            ("📉 S1", sr_levels.get('s1', 0), "support"),
            ("📉 S2", sr_levels.get('s2', 0), "support"),
            ("🛡️ S3", sr_levels.get('s3', 0), "support")
        ]
        
        for col, (label, value, level_type) in zip(cols, sr_items):
            color = "#dc3545" if "R" in label else "#28a745" if "S" in label else "#f7931a"
            border = f"border-left: 4px solid {color};"
            if level_type == "current":
                border += " background: #f7931a10; border: 2px solid #f7931a;"
            
            st.markdown(f"""
            <div class="sr-level" style="{border}">
                <div style="font-size:11px; color:#666;">{label}</div>
                <div style="font-size:16px; font-weight:bold; color:{color};">${value:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # ============================================
    # PREDICTION TABLE
    # ============================================
    
    st.subheader("📋 Recent Predictions")
    
    if predictions is not None and not predictions.empty:
        # Format for display
        display_preds = predictions.head(10).copy()
        display_preds = display_preds[['date', 'predicted_close', 'actual_close', 'confidence_score', 'signal']]
        display_preds.columns = ['Date', 'Predicted', 'Actual', 'Confidence', 'Signal']
        
        # Add error column
        display_preds['Error'] = display_preds.apply(
            lambda row: f"{(row['Actual'] / row['Predicted'] - 1) * 100:.2f}%" 
            if pd.notna(row['Actual']) else "⏳ Pending",
            axis=1
        )
        
        # FIXED: Use map instead of applymap (pandas 2.1+)
        def color_signal(val):
            if val == 'BUY':
                return 'color: #28a745; font-weight: bold;'
            elif val == 'SELL':
                return 'color: #dc3545; font-weight: bold;'
            elif val == 'HOLD':
                return 'color: #ffc107; font-weight: bold;'
            else:
                return 'color: #6c757d;'
        
        # Apply styling
        styled_df = display_preds.style.map(color_signal, subset=['Signal'])
        
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=400
        )
    else:
        st.info("No predictions yet. Run the system to generate predictions.")
    
    # ============================================
    # PERFORMANCE METRICS
    # ============================================
    
    st.subheader("📈 Model Performance")
    
    if performance is not None and not performance.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        latest_perf = performance.iloc[0]
        
        with col1:
            st.metric(
                "Direction Accuracy",
                f"{latest_perf.get('direction_accuracy', 0):.1f}%",
                delta=f"{latest_perf.get('direction_accuracy', 0) - performance.iloc[1].get('direction_accuracy', 0):.1f}%" if len(performance) > 1 else None
            )
        
        with col2:
            st.metric(
                "MAE",
                f"${latest_perf.get('mae', 0):,.2f}",
                delta=f"-${(latest_perf.get('mae', 0) - performance.iloc[1].get('mae', 0)):.2f}" if len(performance) > 1 else None
            )
        
        with col3:
            st.metric(
                "RMSE",
                f"${latest_perf.get('rmse', 0):,.2f}",
                delta=f"-${(latest_perf.get('rmse', 0) - performance.iloc[1].get('rmse', 0)):.2f}" if len(performance) > 1 else None
            )
        
        with col4:
            st.metric(
                "Total Predictions",
                f"{latest_perf.get('total_predictions', 0):.0f}"
            )
        
        # Performance chart
        if len(performance) > 1:
            st.subheader("📉 Performance Trend")
            
            perf_trend = performance.sort_values('date')
            
            fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True)
            
            fig2.add_trace(
                go.Scatter(
                    x=perf_trend['date'],
                    y=perf_trend['direction_accuracy'],
                    mode='lines+markers',
                    name='Direction Accuracy',
                    line=dict(color='#28a745')
                ),
                row=1, col=1
            )
            
            fig2.add_trace(
                go.Scatter(
                    x=perf_trend['date'],
                    y=perf_trend['mae'],
                    mode='lines+markers',
                    name='MAE',
                    line=dict(color='#dc3545')
                ),
                row=2, col=1
            )
            
            fig2.update_layout(height=400, template='plotly_white')
            fig2.update_yaxes(title_text="Accuracy (%)", row=1, col=1)
            fig2.update_yaxes(title_text="MAE ($)", row=2, col=1)
            
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No performance data yet.")
    
    # ============================================
    # TECHNICAL INDICATORS (Latest)
    # ============================================
    
    st.subheader("📊 Latest Technical Indicators")
    
    if len(btc_data) > 0:
        latest = btc_data.iloc[-1]
        
        # Calculate some basic indicators
        indicators = {}
        
        # Returns
        if 'return_1d' in latest.index:
            indicators['1D Return'] = f"{latest.get('return_1d', 0) * 100:.2f}%"
        
        # RSI
        if 'rsi_14' in latest.index:
            rsi = latest.get('rsi_14', 50)
            indicators['RSI (14)'] = f"{rsi:.1f}"
        
        # MACD
        if 'macd' in latest.index:
            indicators['MACD'] = f"{latest.get('macd', 0):.4f}"
        
        # Volatility
        if 'volatility_14' in latest.index:
            indicators['Volatility (14)'] = f"{latest.get('volatility_14', 0):.1f}%"
        
        # ATR
        if 'atr_14' in latest.index:
            indicators['ATR (14)'] = f"${latest.get('atr_14', 0):.2f}"
        
        # Display in columns
        if indicators:
            cols = st.columns(len(indicators))
            for col, (label, value) in zip(cols, indicators.items()):
                with col:
                    st.metric(label, value)
    
    # ============================================
    # FOOTER
    # ============================================
    
    st.divider()
    st.caption(f"🔄 Data updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Model: v{models.iloc[0]['version'] if models is not None and not models.empty else 'N/A'}")
    st.caption("⚠️ This is for educational purposes only. Do your own research before trading.")

# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    main()