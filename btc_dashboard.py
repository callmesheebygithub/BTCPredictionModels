"""
btc_dashboard_streamlit.py - BTC Indicators Dashboard (UPDATED for improved indicators)
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import os
import sys

# Import btc_indicators (improved version)
try:
    from btc_indicators import BTCIndicators
except ImportError:
    st.error("❌ btc_indicators.py not found!")
    st.stop()

# Import email sender
try:
    from btc_email_sender import BTCEmailSender
except ImportError:
    st.error("❌ btc_email_sender.py not found!")
    st.stop()

# Page config
st.set_page_config(
    page_title="BTC Indicators Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #f7931a, #f9a825);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 30px;
    }
    .metric-card {
        background: #1e1e2f;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #f7931a;
        margin: 10px 0;
    }
    .signal-buy {
        background: #00ff88;
        color: #000;
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 24px;
    }
    .signal-sell {
        background: #ff4757;
        color: #fff;
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 24px;
    }
    .signal-neutral {
        background: #ffd93d;
        color: #000;
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 24px;
    }
    .confidence-high {
        color: #00ff88;
        font-weight: bold;
    }
    .confidence-medium {
        color: #ffd93d;
        font-weight: bold;
    }
    .confidence-low {
        color: #ff6b6b;
        font-weight: bold;
    }
    .stButton button {
        width: 100%;
        background: #f7931a;
        color: white;
        font-weight: bold;
        font-size: 18px;
        padding: 10px;
    }
    .stButton button:hover {
        background: #f9a825;
    }
    .info-box {
        background: #1e1e2f;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #f7931a;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Session state initialization
if 'results' not in st.session_state:
    st.session_state.results = None
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'loading' not in st.session_state:
    st.session_state.loading = False

# ============================================
# FUNCTIONS
# ============================================

def load_indicators():
    """Load indicators from btc_indicators.py"""
    with st.spinner("🔄 Loading indicators from database..."):
        try:
            indicator = BTCIndicators()
            results = indicator.calculate_all_indicators()
            indicator.close()
            
            if results:
                st.session_state.results = results
                st.session_state.last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                st.session_state.loading = False
                st.success("✅ Data loaded successfully!")
                return True
            else:
                st.error("❌ Failed to load indicators!")
                st.session_state.loading = False
                return False
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.session_state.loading = False
            return False

def send_email_report():
    """Send email report"""
    with st.spinner("📧 Sending email..."):
        try:
            email_sender = BTCEmailSender()
            email_sender.results = st.session_state.results
            
            html_content = email_sender.create_html_email()
            
            if html_content:
                subject = f"🚀 BTC Daily Report - {datetime.now().strftime('%Y-%m-%d')}"
                success = email_sender.send_email(subject, html_content)
                
                if success:
                    st.success("✅ Email sent successfully!")
                else:
                    st.error("❌ Failed to send email!")
            else:
                st.error("❌ Failed to create email content!")
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

def export_json():
    """Export results to JSON"""
    try:
        filename = f"btc_indicators_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        def convert(obj):
            if hasattr(obj, 'item'):
                return obj.item()
            return obj
        
        with open(filename, 'w') as f:
            json.dump(st.session_state.results, f, default=convert, indent=2)
        
        st.success(f"✅ Data exported to {filename}")
        
        # Download button
        with open(filename, 'r') as f:
            json_data = f.read()
            st.download_button(
                label="📥 Download JSON",
                data=json_data,
                file_name=filename,
                mime="application/json",
                use_container_width=True
            )
            
    except Exception as e:
        st.error(f"❌ Failed to export: {str(e)}")

# ============================================
# SIDEBAR
# ============================================

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Bitcoin.svg/800px-Bitcoin.svg.png", width=100)
    st.markdown("## 📊 Controls")
    
    # Refresh button
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.session_state.loading = True
        st.rerun()
    
    # Email button
    if st.button("📧 Send Email Report", use_container_width=True):
        if st.session_state.results:
            send_email_report()
        else:
            st.error("❌ No data available! Please refresh first.")
    
    # Export button
    if st.button("💾 Export JSON", use_container_width=True):
        if st.session_state.results:
            export_json()
        else:
            st.error("❌ No data available! Please refresh first.")
    
    st.markdown("---")
    st.markdown("### 📈 Info")
    if st.session_state.last_update:
        st.write(f"🕐 Last Update: {st.session_state.last_update}")
    
    st.markdown("---")
    st.markdown("### 📊 Indicators Included")
    st.write("• Support & Resistance (with price reaction)")
    st.write("• Market Structure (BOS/CHOCH)")
    st.write("• Moving Averages (7,20,50,100,200)")
    st.write("• RSI (Wilder's Smoothing)")
    st.write("• MACD")
    st.write("• Bollinger Bands (Historical Percentile)")
    st.write("• Fibonacci (Swing-based)")
    st.write("• Pivot Points")
    st.write("• Volume-based Liquidity")
    st.write("• ATR (Risk Management)")

# ============================================
# MAIN CONTENT
# ============================================

# Title
st.markdown('<div class="main-header"><h1>🚀 BTC Indicators Dashboard</h1><p>Real-time Bitcoin Technical Analysis (Improved)</p></div>', unsafe_allow_html=True)

# Load data if not loaded or refresh requested
if st.session_state.loading or st.session_state.results is None:
    load_indicators()

# Display results
if st.session_state.results:
    results = st.session_state.results
    
    # ============================================
    # TOP ROW: Current Price, Signal, RSI, ATR
    # ============================================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        current_price = results.get('current_price', 0)
        st.metric(
            label="💰 Current Price",
            value=f"${current_price:,.2f}",
            delta=None
        )
    
    with col2:
        if 'overall_signal' in results:
            signal = results['overall_signal']
            direction = signal.get('direction', 'NEUTRAL')
            confidence = signal.get('confidence', 'Unknown')
            
            # Signal color
            if 'BUY' in direction:
                st.markdown('<div class="signal-buy">🟢 BUY</div>', unsafe_allow_html=True)
            elif 'SELL' in direction:
                st.markdown('<div class="signal-sell">🔴 SELL</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="signal-neutral">🟡 NEUTRAL</div>', unsafe_allow_html=True)
            
            # Confidence
            if confidence == 'High':
                st.markdown(f'<p style="text-align:center;"><span class="confidence-high">Confidence: {confidence}</span></p>', unsafe_allow_html=True)
            elif confidence == 'Medium':
                st.markdown(f'<p style="text-align:center;"><span class="confidence-medium">Confidence: {confidence}</span></p>', unsafe_allow_html=True)
            else:
                st.markdown(f'<p style="text-align:center;"><span class="confidence-low">Confidence: {confidence}</span></p>', unsafe_allow_html=True)
    
    with col3:
        if 'rsi' in results:
            rsi = results['rsi']
            st.metric(
                label="📊 RSI",
                value=f"{rsi.get('value', 0):.1f}",
                delta=rsi.get('status', 'Neutral')
            )
    
    with col4:
        if 'atr' in results:
            atr = results['atr']
            # Show ATR with percentile
            st.metric(
                label="📊 ATR",
                value=f"${atr.get('atr', 0):.2f}",
                delta=f"{atr.get('percentile', 0):.0f}th percentile"
            )
            
            # Show suggested stop loss if available
            if 'overall_signal' in results and 'atr_info' in results['overall_signal']:
                atr_info = results['overall_signal']['atr_info']
                st.caption(f"Stop Loss: ${atr_info['suggested_stop_loss']:.2f}")
    
    # ============================================
    # ROW 2: Market Structure & Support/Resistance
    # ============================================
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container():
            st.subheader("📊 Market Structure")
            if 'market_structure' in results:
                structure = results['market_structure']
                
                # Trend
                trend = structure.get('trend_regime', 'Unknown')
                if trend == 'Uptrend':
                    st.success(f"📈 {trend}")
                elif trend == 'Downtrend':
                    st.error(f"📉 {trend}")
                elif trend == 'Range':
                    st.warning(f"➡️ {trend}")
                else:
                    st.info(f"❓ {trend}")
                
                # BOS (Break of Structure)
                bos = structure.get('bos', [])
                if bos:
                    st.write("**Break of Structure (BOS):**")
                    for b in bos:
                        st.write(f"• {b['type']} at ${b['price']:,.2f}")
                else:
                    st.write("**BOS:** None")
                
                # CHOCH (Change of Character)
                choch = structure.get('choch', [])
                if choch:
                    st.write("**Change of Character (CHOCH):**")
                    for c in choch:
                        st.write(f"• {c['type']}")
                else:
                    st.write("**CHOCH:** None")
                
                # HH/HL/LH/LL
                if 'hh_hl_lh_ll' in structure:
                    hh_hl = structure['hh_hl_lh_ll']
                    st.write(f"**HH:** {hh_hl.get('HH', 0)} | **HL:** {hh_hl.get('HL', 0)} | **LH:** {hh_hl.get('LH', 0)} | **LL:** {hh_hl.get('LL', 0)}")
    
    with col2:
        with st.container():
            st.subheader("🎯 Support & Resistance")
            if 'support_resistance' in results:
                sr = results['support_resistance']
                
                # Nearest levels
                support = sr.get('nearest_support', {})
                resistance = sr.get('nearest_resistance', {})
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if support:
                        st.metric(
                            "Support",
                            f"${support.get('price', 0):,.2f}",
                            f"Strength: {support.get('strength', 0)}"
                        )
                    else:
                        st.metric("Support", "N/A")
                
                with col_b:
                    if resistance:
                        st.metric(
                            "Resistance",
                            f"${resistance.get('price', 0):,.2f}",
                            f"Strength: {resistance.get('strength', 0)}"
                        )
                    else:
                        st.metric("Resistance", "N/A")
                
                # Top support levels
                if 'support_levels' in sr and sr['support_levels']:
                    with st.expander("📊 All Support Levels"):
                        supports = pd.DataFrame([
                            {"Level": i+1, "Price": f"${s['price']:,.2f}", "Strength": f"{s['strength']} touches"}
                            for i, s in enumerate(sr['support_levels'][:5])
                        ])
                        st.dataframe(supports, use_container_width=True, hide_index=True)
                
                # Top resistance levels
                if 'resistance_levels' in sr and sr['resistance_levels']:
                    with st.expander("📊 All Resistance Levels"):
                        resistances = pd.DataFrame([
                            {"Level": i+1, "Price": f"${r['price']:,.2f}", "Strength": f"{r['strength']} touches"}
                            for i, r in enumerate(sr['resistance_levels'][:5])
                        ])
                        st.dataframe(resistances, use_container_width=True, hide_index=True)
    
    # ============================================
    # ROW 3: Moving Averages
    # ============================================
    with st.container():
        st.subheader("📈 Moving Averages")
        if 'moving_averages' in results:
            ma = results['moving_averages']
            
            ma_data = []
            for period, data in ma.items():
                ma_data.append({
                    "Period": period,
                    "Value": f"${data['value']:,.2f}",
                    "EMA": f"${data.get('ema', data['value']):,.2f}",
                    "Trend": data.get('trend', 'Neutral'),
                    "Slope": f"{data.get('slope', 0):.2f}%"
                })
            
            ma_df = pd.DataFrame(ma_data)
            
            # Color code trends
            def color_trend(val):
                if 'Strong Bullish' in val or val == 'Bullish':
                    return 'background-color: #00ff88; color: black'
                elif 'Strong Bearish' in val or val == 'Bearish':
                    return 'background-color: #ff4757; color: white'
                else:
                    return 'background-color: #ffd93d; color: black'
            
            styled_df = ma_df.style.map(color_trend, subset=['Trend'])
            st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True
            )
    
    # ============================================
    # ROW 4: RSI & MACD
    # ============================================
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container():
            st.subheader("📊 RSI")
            if 'rsi' in results:
                rsi = results['rsi']
                
                # RSI Gauge
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number+delta",
                    value = rsi.get('value', 0),
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "RSI (Wilder's Smoothing)"},
                    delta = {'reference': 50},
                    gauge = {
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 30], 'color': "red"},
                            {'range': [30, 70], 'color': "yellow"},
                            {'range': [70, 100], 'color': "green"}
                        ],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': rsi.get('value', 0)
                        }
                    }
                ))
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
                
                st.info(f"Status: {rsi.get('status', 'Neutral')} | Period: {rsi.get('period', 14)} days")
    
    with col2:
        with st.container():
            st.subheader("📊 MACD")
            if 'macd' in results:
                macd = results['macd']
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("MACD", f"{macd.get('macd', 0):.2f}")
                with col_b:
                    st.metric("Signal", f"{macd.get('signal', 0):.2f}")
                with col_c:
                    st.metric("Histogram", f"{macd.get('histogram', 0):.2f}")
                
                st.info(f"Signal Status: {macd.get('signal_status', 'Neutral')} | Histogram: {macd.get('histogram_status', 'Stable')}")
    
    # ============================================
    # ROW 5: Bollinger Bands
    # ============================================
    st.subheader("📊 Bollinger Bands")
    if 'bollinger_bands' in results:
        bb = results['bollinger_bands']
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Upper Band", f"${bb.get('upper_band', 0):,.2f}")
        with col2:
            st.metric("Middle Band", f"${bb.get('middle_band', 0):,.2f}")
        with col3:
            st.metric("Lower Band", f"${bb.get('lower_band', 0):,.2f}")
        with col4:
            st.metric("Position", bb.get('position', 'Inside Bands'))
        
        st.info(f"Band Width: ${bb.get('band_width', 0):,.2f} | Squeeze: {bb.get('squeeze', 'No')} | Percentile: {bb.get('bandwidth_percentile', 0):.0f}%")
    
    # ============================================
    # ROW 6: Fibonacci & Pivot Points
    # ============================================
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container():
            st.subheader("📊 Fibonacci (Swing-based)")
            if 'fibonacci' in results:
                fib = results['fibonacci']
                
                if fib:
                    st.write(f"**Swing High:** ${fib.get('swing_high', 0):,.2f} ({fib.get('high_date', 'N/A')})")
                    st.write(f"**Swing Low:** ${fib.get('swing_low', 0):,.2f} ({fib.get('low_date', 'N/A')})")
                    st.write(f"**Range:** ${fib.get('range', 0):,.2f}")
                    
                    fib_data = []
                    for level, price in fib.get('fib_levels', {}).items():
                        fib_data.append({
                            "Level": level,
                            "Price": f"${price:,.2f}"
                        })
                    
                    fib_df = pd.DataFrame(fib_data)
                    st.dataframe(fib_df, use_container_width=True, hide_index=True)
                    
                    if fib.get('current_fib_level'):
                        st.success(f"📍 Current Level: {fib['current_fib_level']}")
                else:
                    st.warning("No swing points found for Fibonacci")
    
    with col2:
        with st.container():
            st.subheader("📊 Pivot Points")
            if 'pivot_points' in results:
                pivot = results['pivot_points']
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Pivot", f"${pivot.get('pivot', 0):,.2f}")
                    st.metric("R1", f"${pivot.get('resistance_1', 0):,.2f}")
                    st.metric("R2", f"${pivot.get('resistance_2', 0):,.2f}")
                    st.metric("R3", f"${pivot.get('resistance_3', 0):,.2f}")
                with col_b:
                    st.metric("Position", pivot.get('current_position', 'N/A'))
                    st.metric("S1", f"${pivot.get('support_1', 0):,.2f}")
                    st.metric("S2", f"${pivot.get('support_2', 0):,.2f}")
                    st.metric("S3", f"${pivot.get('support_3', 0):,.2f}")
                
                st.caption(f"Nearest: {pivot.get('nearest_level', 'N/A')} (${pivot.get('distance_to_nearest', 0):.2f} away)")
    
    # ============================================
    # ROW 7: Liquidity Analysis
    # ============================================
    st.subheader("💧 Liquidity Analysis (Volume-based)")
    if 'liquidity' in results:
        liq = results['liquidity']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("30-Day Avg Volume", f"{liq.get('avg_volume_30d', 0):,.0f}")
        with col2:
            st.metric("Overall Avg Volume", f"{liq.get('avg_volume_overall', 0):,.0f}")
        with col3:
            st.metric("Volume Ratio", f"{liq.get('volume_ratio', 0):.2f}x")
        
        # Volume Profile
        if 'volume_profile' in liq:
            vp = liq['volume_profile']
            if vp:
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("POC", f"${vp.get('poc', 0):,.2f}")
                with col_b:
                    st.metric("VAH", f"${vp.get('vah', 0):,.2f}")
                with col_c:
                    st.metric("VAL", f"${vp.get('val', 0):,.2f}")
        
        # High Volume Nodes
        if 'high_volume_nodes' in liq and liq['high_volume_nodes']:
            with st.expander("📊 High Volume Nodes (HVN)"):
                hvn_data = pd.DataFrame([
                    {
                        "Price Range": node.get('price_range', 'N/A'),
                        "Volume": f"{node.get('volume', 0):,.0f}"
                    }
                    for node in liq['high_volume_nodes'][:5]
                ])
                st.dataframe(hvn_data, use_container_width=True, hide_index=True)
        
        # Low Volume Nodes
        if 'low_volume_nodes' in liq and liq['low_volume_nodes']:
            with st.expander("📊 Low Volume Nodes (LVN)"):
                lvn_data = pd.DataFrame([
                    {
                        "Price Range": node.get('price_range', 'N/A'),
                        "Volume": f"{node.get('volume', 0):,.0f}"
                    }
                    for node in liq['low_volume_nodes'][:5]
                ])
                st.dataframe(lvn_data, use_container_width=True, hide_index=True)
    
    # ============================================
    # ROW 8: Signal Factors
    # ============================================
    if 'overall_signal' in results:
        signal = results['overall_signal']
        
        st.subheader("📋 Signal Factors")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Factors:**")
            if 'factors' in signal and signal['factors']:
                for factor in signal['factors']:
                    st.write(f"• {factor}")
        
        with col2:
            st.write("**Weights:**")
            if 'weights' in signal:
                for key, weight in signal['weights'].items():
                    st.write(f"• {key}: {weight:.0%}")
            
            if 'normalized_score' in signal:
                st.metric("Normalized Score", f"{signal['normalized_score']:.2f}")

else:
    st.info("👈 Click 'Refresh Data' to load indicators")

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>🚀 BTC Indicators Dashboard | Powered by Streamlit</p>
    <p>Indicators: S/R, Market Structure, MA, RSI, MACD, BB, Fibonacci, Pivot, Liquidity, ATR</p>
    <p>© 2026 All Rights Reserved</p>
</div>
""", unsafe_allow_html=True)

# Auto refresh
if st.session_state.results:
    st.caption(f"🕐 Last updated: {st.session_state.last_update}")