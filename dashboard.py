# dashboard.py

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class Dashboard:
    def __init__(self):
        self.db = DatabaseManager()
    
    def run(self):
        st.set_page_config(layout="wide", page_title="BTC Predictor Dashboard")
        
        st.title("🚀 Bitcoin Prediction Dashboard")
        
        # Get data
        df = self.db.get_all_data()
        
        # Sidebar
        st.sidebar.header("Controls")
        days = st.sidebar.slider("Days to show", 30, 730, 90)
        
        # Main chart
        fig = make_subplots(rows=2, cols=1, 
                           shared_xaxes=True,
                           vertical_spacing=0.03,
                           row_heights=[0.7, 0.3])
        
        # Price chart
        fig.add_trace(go.Candlestick(
            x=df['date'].tail(days),
            open=df['open'].tail(days),
            high=df['high'].tail(days),
            low=df['low'].tail(days),
            close=df['close'].tail(days),
            name='BTC Price'
        ), row=1, col=1)
        
        # Volume chart
        fig.add_trace(go.Bar(
            x=df['date'].tail(days),
            y=df['volume'].tail(days),
            name='Volume',
            marker_color='blue'
        ), row=2, col=1)
        
        fig.update_layout(height=600, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Current Price", f"${df['close'].iloc[-1]:,.2f}")
        with col2:
            st.metric("24h Change", f"{df['close'].pct_change().iloc[-1]*100:.2f}%")
        with col3:
            st.metric("Volume", f"{df['volume'].iloc[-1]:,.0f}")
        with col4:
            # Show latest prediction
            pred = self.get_latest_prediction()
            if pred:
                st.metric("Next Day Prediction", f"${pred:,.2f}")
    
    def get_latest_prediction(self):
        conn = sqlite3.connect('btc_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT predicted_close FROM predictions 
            ORDER BY date DESC LIMIT 1
        ''')
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

# Run: streamlit run dashboard.py