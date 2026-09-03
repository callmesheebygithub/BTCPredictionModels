"""
ROUGH.PY - Database Viewer & Exporter
Use this file to view, analyze, and export BTC data from your database
"""
import numpy as np
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import sys

# ============================================
# DATABASE CONNECTION
# ============================================

DB_PATH = 'btc_data.db'

def get_connection():
    """Get database connection"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database '{DB_PATH}' not found!")
        print("Please run btc_pipeline.py first to create the database.")
        return None
    return sqlite3.connect(DB_PATH)

def get_table_columns(table_name):
    """Get all column names from a table"""
    conn = get_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    conn.close()
    return columns

# ============================================
# 1. VIEW DATA FUNCTIONS
# ============================================

def view_all_data(limit=50):
    """View all BTC daily data"""
    conn = get_connection()
    if not conn:
        return
    
    print("\n" + "="*80)
    print("📊 BTC DAILY DATA (Latest Records)")
    print("="*80)
    
    query = f"""
        SELECT date, open, high, low, close, volume 
        FROM btc_daily 
        ORDER BY date DESC 
        LIMIT {limit}
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("❌ No data found in database!")
        return
    
    print(f"\n📈 Total Records in Database: {len(df)} (showing last {limit})")
    print("\n" + df.to_string(index=False))
    print("\n" + "="*80)
    
    # Basic statistics
    print("\n📊 Basic Statistics:")
    print(f"  • Date Range: {df['date'].min()} to {df['date'].max()}")
    print(f"  • Avg Close: ${df['close'].mean():,.2f}")
    print(f"  • Min Close: ${df['close'].min():,.2f}")
    print(f"  • Max Close: ${df['close'].max():,.2f}")
    print(f"  • Avg Volume: {df['volume'].mean():,.0f}")
    print("="*80 + "\n")
    
    return df

def view_predictions(limit=30):
    """View all predictions with accuracy"""
    conn = get_connection()
    if not conn:
        return
    
    print("\n" + "="*80)
    print("🎯 PREDICTIONS HISTORY")
    print("="*80)
    
    # Get ALL columns from predictions table
    columns = get_table_columns('predictions')
    if not columns:
        print("❌ Predictions table not found!")
        return
    
    query = f"""
        SELECT {', '.join(columns)}
        FROM predictions 
        ORDER BY date DESC 
        LIMIT {limit}
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("❌ No predictions found in database!")
        return
    
    # Format direction if column exists
    if 'direction_correct' in df.columns:
        df['direction'] = df['direction_correct'].apply(
            lambda x: '✅ CORRECT' if x == 1 else '❌ WRONG' if x == 0 else '⏳ PENDING'
        )
    
    print(f"\n📈 Total Predictions: {len(df)} (showing last {limit})")
    print("\n" + df.to_string(index=False))
    print("\n" + "="*80)
    
    # Statistics
    if 'actual_close' in df.columns and not df['actual_close'].isna().all():
        valid = df[df['actual_close'].notna()]
        if not valid.empty and 'error_percentage' in valid.columns:
            print("\n📊 Prediction Statistics:")
            print(f"  • Avg Error: {valid['error_percentage'].mean():.2f}%")
            print(f"  • Avg Absolute Error: ${valid['absolute_error'].mean():.2f}")
            print(f"  • Direction Accuracy: {valid['direction_correct'].mean()*100:.1f}%")
            print(f"  • Total Validated: {len(valid)}")
            
            # Best and worst predictions
            best = valid.loc[valid['error_percentage'].abs().idxmin()]
            worst = valid.loc[valid['error_percentage'].abs().idxmax()]
            print(f"\n🏆 Best Prediction: {best['date']} (Error: {best['error_percentage']:.2f}%)")
            print(f"💩 Worst Prediction: {worst['date']} (Error: {worst['error_percentage']:.2f}%)")
    
    print("="*80 + "\n")
    
    return df

def view_performance():
    """View performance metrics"""
    conn = get_connection()
    if not conn:
        return
    
    print("\n" + "="*80)
    print("📈 PERFORMANCE METRICS")
    print("="*80)
    
    # Get ALL columns from performance table
    columns = get_table_columns('performance')
    if not columns:
        print("❌ Performance table not found!")
        return
    
    query = f"""
        SELECT {', '.join(columns)}
        FROM performance 
        ORDER BY date DESC 
        LIMIT 20
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("❌ No performance data found!")
        return
    
    print(f"\n📊 Latest Performance Records:")
    print("\n" + df.to_string(index=False))
    print("\n" + "="*80 + "\n")
    
    # Show trend
    if len(df) > 1 and 'direction_accuracy' in df.columns:
        latest = df.iloc[0]
        previous = df.iloc[1]
        direction_change = latest['direction_accuracy'] - previous['direction_accuracy']
        print(f"📉 Direction Accuracy Trend: {direction_change:+.1f}% (from {previous['direction_accuracy']:.1f}% to {latest['direction_accuracy']:.1f}%)")
        print("="*80 + "\n")
    
    return df

# ============================================
# 2. EXPORT FUNCTIONS - ALL COLUMNS
# ============================================

def export_to_excel(filename=None):
    """Export ALL data to Excel file with ALL columns"""
    if filename is None:
        filename = f'btc_data_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    conn = get_connection()
    if not conn:
        return False
    
    print(f"\n📤 Exporting data to Excel...")
    
    try:
        # Get ALL columns from each table
        btc_columns = get_table_columns('btc_daily')
        pred_columns = get_table_columns('predictions')
        perf_columns = get_table_columns('performance')
        
        # Read ALL data with ALL columns
        btc_data = pd.read_sql_query(f"""
            SELECT {', '.join(btc_columns) if btc_columns else '*'} 
            FROM btc_daily 
            ORDER BY date
        """, conn)
        
        predictions = pd.read_sql_query(f"""
            SELECT {', '.join(pred_columns) if pred_columns else '*'} 
            FROM predictions 
            ORDER BY date
        """, conn) if pred_columns else pd.DataFrame()
        
        performance = pd.read_sql_query(f"""
            SELECT {', '.join(perf_columns) if perf_columns else '*'} 
            FROM performance 
            ORDER BY date
        """, conn) if perf_columns else pd.DataFrame()
        
        conn.close()
        
        # Check if data exists
        if btc_data.empty:
            print("❌ No BTC data to export!")
            return False
        
        # Create Excel writer
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Sheet 1: BTC Daily Data (ALL columns)
            btc_data.to_excel(writer, sheet_name='BTC_Daily', index=False)
            
            # Sheet 2: Predictions (ALL columns)
            if not predictions.empty:
                predictions.to_excel(writer, sheet_name='Predictions', index=False)
            
            # Sheet 3: Performance (ALL columns)
            if not performance.empty:
                performance.to_excel(writer, sheet_name='Performance', index=False)
            
            # Sheet 4: Column Info (NEW - shows all columns)
            column_info = create_column_info(btc_data, predictions, performance)
            column_info.to_excel(writer, sheet_name='Column_Info', index=False)
            
            # Sheet 5: Summary Statistics
            summary = create_summary(btc_data, predictions)
            summary.to_excel(writer, sheet_name='Summary', index=False)
            
            # Sheet 6: Technical Analysis
            if len(btc_data) > 30:
                tech_analysis = create_technical_analysis(btc_data)
                tech_analysis.to_excel(writer, sheet_name='Technical_Analysis', index=False)
        
        print(f"✅ Data exported successfully to: {filename}")
        print(f"\n📊 Export Summary:")
        print(f"  • BTC Daily Records: {len(btc_data)} ({len(btc_data.columns)} columns)")
        print(f"  • Predictions: {len(predictions)} ({len(predictions.columns)} columns)")
        print(f"  • Performance Records: {len(performance)} ({len(performance.columns)} columns)")
        
        # Show all column names
        print(f"\n📋 BTC Daily Columns: {', '.join(btc_data.columns)}")
        if not predictions.empty:
            print(f"📋 Predictions Columns: {', '.join(predictions.columns)}")
        if not performance.empty:
            print(f"📋 Performance Columns: {', '.join(performance.columns)}")
        
        # Open file automatically (Windows only)
        if sys.platform == 'win32':
            try:
                os.startfile(filename)
                print(f"\n📂 File opened automatically")
            except:
                pass
        
        return True
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_column_info(btc_data, predictions, performance):
    """Create column information sheet"""
    info_data = []
    
    # BTC Daily columns
    info_data.append(['TABLE', 'COLUMN NAME', 'DATA TYPE', 'SAMPLE VALUE'])
    for col in btc_data.columns:
        dtype = btc_data[col].dtype
        sample = btc_data[col].iloc[0] if not btc_data.empty else 'N/A'
        info_data.append(['btc_daily', col, str(dtype), str(sample)])
    
    # Predictions columns
    if not predictions.empty:
        for col in predictions.columns:
            dtype = predictions[col].dtype
            sample = predictions[col].iloc[0] if not predictions.empty else 'N/A'
            info_data.append(['predictions', col, str(dtype), str(sample)])
    
    # Performance columns
    if not performance.empty:
        for col in performance.columns:
            dtype = performance[col].dtype
            sample = performance[col].iloc[0] if not performance.empty else 'N/A'
            info_data.append(['performance', col, str(dtype), str(sample)])
    
    df = pd.DataFrame(info_data)
    return df

def create_summary(btc_data, predictions):
    """Create summary statistics"""
    summary_data = []
    
    # BTC Data Summary
    summary_data.append(['BTC DATA SUMMARY', ''])
    summary_data.append(['Total Records', len(btc_data)])
    summary_data.append(['Total Columns', len(btc_data.columns)])
    summary_data.append(['Date Range', f"{btc_data['date'].min()} to {btc_data['date'].max()}"])
    summary_data.append(['Current Price', f"${btc_data['close'].iloc[-1]:,.2f}"])
    summary_data.append(['Avg Close', f"${btc_data['close'].mean():,.2f}"])
    summary_data.append(['Min Close', f"${btc_data['close'].min():,.2f}"])
    summary_data.append(['Max Close', f"${btc_data['close'].max():,.2f}"])
    summary_data.append(['Avg Volume', f"{btc_data['volume'].mean():,.0f}"])
    summary_data.append([])
    
    # Price Changes
    if len(btc_data) > 7:
        summary_data.append(['PRICE CHANGES', ''])
        summary_data.append(['1-Day Change', f"{((btc_data['close'].iloc[-1] - btc_data['close'].iloc[-2]) / btc_data['close'].iloc[-2] * 100):+.2f}%"])
        summary_data.append(['7-Day Change', f"{((btc_data['close'].iloc[-1] - btc_data['close'].iloc[-7]) / btc_data['close'].iloc[-7] * 100):+.2f}%"])
        if len(btc_data) > 30:
            summary_data.append(['30-Day Change', f"{((btc_data['close'].iloc[-1] - btc_data['close'].iloc[-30]) / btc_data['close'].iloc[-30] * 100):+.2f}%"])
        summary_data.append([])
    
    # Predictions Summary
    if not predictions.empty:
        summary_data.append(['PREDICTIONS SUMMARY', ''])
        summary_data.append(['Total Predictions', len(predictions)])
        summary_data.append(['Total Columns', len(predictions.columns)])
        
        if 'actual_close' in predictions.columns:
            valid = predictions[predictions['actual_close'].notna()]
            if not valid.empty:
                summary_data.append(['Validated Predictions', len(valid)])
                if 'error_percentage' in valid.columns:
                    summary_data.append(['Avg Error %', f"{valid['error_percentage'].mean():.2f}%"])
                if 'absolute_error' in valid.columns:
                    summary_data.append(['Avg Absolute Error', f"${valid['absolute_error'].mean():.2f}"])
                if 'direction_correct' in valid.columns:
                    summary_data.append(['Direction Accuracy', f"{valid['direction_correct'].mean()*100:.1f}%"])
    
    df = pd.DataFrame(summary_data)
    df.columns = ['Metric', 'Value']
    return df

def create_technical_analysis(btc_data):
    """Create technical analysis sheet"""
    df = btc_data.copy()
    
    # Moving Averages
    df['MA_7'] = df['close'].rolling(7).mean()
    df['MA_25'] = df['close'].rolling(25).mean()
    df['MA_50'] = df['close'].rolling(50).mean()
    df['MA_200'] = df['close'].rolling(200).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands
    df['BB_upper'] = df['close'].rolling(20).mean() + (df['close'].rolling(20).std() * 2)
    df['BB_middle'] = df['close'].rolling(20).mean()
    df['BB_lower'] = df['close'].rolling(20).mean() - (df['close'].rolling(20).std() * 2)
    
    # MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_histogram'] = df['MACD'] - df['MACD_signal']
    
    # ATR (Average True Range)
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    # Current signals (last row only)
    last_row = df.iloc[-1:].copy()
    
    # Add signal indicators
    signals = []
    if last_row['close'].iloc[0] > last_row['MA_50'].iloc[0]:
        signals.append("Bullish (Above MA50)")
    else:
        signals.append("Bearish (Below MA50)")
    
    if last_row['RSI'].iloc[0] > 70:
        signals.append("Overbought")
    elif last_row['RSI'].iloc[0] < 30:
        signals.append("Oversold")
    else:
        signals.append("Neutral")
    
    if last_row['MACD'].iloc[0] > last_row['MACD_signal'].iloc[0]:
        signals.append("MACD Bullish")
    else:
        signals.append("MACD Bearish")
    
    last_row['Signals'] = ', '.join(signals)
    
    return last_row

# ============================================
# 3. ANALYSIS FUNCTIONS
# ============================================

def analyze_data():
    """Perform basic analysis on the data"""
    conn = get_connection()
    if not conn:
        return
    
    print("\n" + "="*80)
    print("🔍 DATA ANALYSIS")
    print("="*80)
    
    # Get data
    btc_data = pd.read_sql_query("SELECT * FROM btc_daily ORDER BY date", conn)
    predictions = pd.read_sql_query("SELECT * FROM predictions ORDER BY date", conn)
    conn.close()
    
    if btc_data.empty:
        print("❌ No data to analyze!")
        return
    
    print(f"\n📊 BTC Data Analysis:")
    print(f"  • Total Days: {len(btc_data)}")
    print(f"  • Total Columns: {len(btc_data.columns)}")
    print(f"  • Date Range: {btc_data['date'].min()} to {btc_data['date'].max()}")
    print(f"  • Current Price: ${btc_data['close'].iloc[-1]:,.2f}")
    
    if len(btc_data) > 7:
        print(f"  • 7-Day Change: {((btc_data['close'].iloc[-1] - btc_data['close'].iloc[-7]) / btc_data['close'].iloc[-7] * 100):+.2f}%")
    if len(btc_data) > 30:
        print(f"  • 30-Day Change: {((btc_data['close'].iloc[-1] - btc_data['close'].iloc[-30]) / btc_data['close'].iloc[-30] * 100):+.2f}%")
    if len(btc_data) > 90:
        print(f"  • 90-Day Change: {((btc_data['close'].iloc[-1] - btc_data['close'].iloc[-90]) / btc_data['close'].iloc[-90] * 100):+.2f}%")
    
    # Price ranges
    print(f"\n📈 Price Statistics:")
    print(f"  • All-Time High: ${btc_data['high'].max():,.2f}")
    print(f"  • All-Time Low: ${btc_data['low'].min():,.2f}")
    print(f"  • Average Close: ${btc_data['close'].mean():,.2f}")
    print(f"  • Median Close: ${btc_data['close'].median():,.2f}")
    
    # Volatility
    daily_returns = btc_data['close'].pct_change() * 100
    print(f"\n📉 Volatility:")
    print(f"  • Avg Daily Return: {daily_returns.mean():+.2f}%")
    print(f"  • Max Daily Gain: {daily_returns.max():+.2f}%")
    print(f"  • Max Daily Loss: {daily_returns.min():+.2f}%")
    print(f"  • Volatility (Std Dev): {daily_returns.std():.2f}%")
    
    # Winning days
    winning_days = (daily_returns > 0).sum()
    print(f"  • Winning Days: {winning_days} ({winning_days/len(daily_returns)*100:.1f}%)")
    
    # Predictions Analysis
    if not predictions.empty:
        print(f"\n🎯 Prediction Analysis:")
        print(f"  • Total Predictions: {len(predictions)}")
        print(f"  • Columns: {', '.join(predictions.columns)}")
        
        if 'actual_close' in predictions.columns:
            valid = predictions[predictions['actual_close'].notna()]
            if not valid.empty:
                print(f"  • Validated Predictions: {len(valid)}")
                if 'error_percentage' in valid.columns:
                    print(f"  • Avg Error: {valid['error_percentage'].mean():.2f}%")
                if 'direction_correct' in valid.columns:
                    print(f"  • Direction Accuracy: {valid['direction_correct'].mean()*100:.1f}%")
    
    print("="*80 + "\n")

# ============================================
# 4. CLEANUP FUNCTIONS
# ============================================

def delete_old_data(days=365):
    """Delete data older than specified days"""
    conn = get_connection()
    if not conn:
        return
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    print(f"\n🗑️ Deleting data older than {days} days (before {cutoff_date})...")
    
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM btc_daily WHERE date < '{cutoff_date}'")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"✅ Deleted {deleted} records older than {days} days")
    return deleted

def clear_predictions():
    """Clear all prediction data"""
    conn = get_connection()
    if not conn:
        return
    
    confirm = input("\n⚠️ Are you sure you want to delete all predictions? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Operation cancelled")
        return
    
    cursor = conn.cursor()
    cursor.execute("DELETE FROM predictions")
    cursor.execute("DELETE FROM performance")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"✅ Deleted all predictions and performance data")
    return deleted

def clear_all_data():
    """Clear ALL data (including BTC prices)"""
    conn = get_connection()
    if not conn:
        return
    
    confirm = input("\n⚠️ WARNING: This will delete ALL data including BTC prices! Are you sure? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Operation cancelled")
        return
    
    cursor = conn.cursor()
    cursor.execute("DELETE FROM btc_daily")
    cursor.execute("DELETE FROM predictions")
    cursor.execute("DELETE FROM performance")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"✅ Deleted ALL data from database")
    print("Please run btc_pipeline.py again to rebuild the database.")
    return deleted

# ============================================
# 5. UTILITY FUNCTIONS
# ============================================

def show_database_info():
    """Show database info and size"""
    conn = get_connection()
    if not conn:
        return
    
    print("\n" + "="*80)
    print("📋 DATABASE INFORMATION")
    print("="*80)
    
    # Get file size
    if os.path.exists(DB_PATH):
        size = os.path.getsize(DB_PATH)
        if size < 1024 * 1024:
            size_str = f"{size / 1024:.2f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.2f} MB"
        print(f"  • Database Size: {size_str}")
    
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"\n  • Tables:")
    total_records = 0
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        total_records += count
        
        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        col_names = [col[1] for col in columns]
        
        print(f"    - {table_name}: {count} records, {len(columns)} columns")
        print(f"      Columns: {', '.join(col_names)}")
    
    print(f"\n  • Total Records: {total_records}")
    
    conn.close()
    print("="*80 + "\n")

def quick_view():
    """Quick view of latest data"""
    print("\n" + "="*80)
    print("⚡ QUICK VIEW (Last 5 records)")
    print("="*80)
    
    conn = get_connection()
    if not conn:
        return
    
    # Latest 5 price records with ALL columns
    btc_columns = get_table_columns('btc_daily')
    if btc_columns:
        df = pd.read_sql_query(f"""
            SELECT {', '.join(btc_columns)}
            FROM btc_daily 
            ORDER BY date DESC 
            LIMIT 5
        """, conn)
        if not df.empty:
            print("\n📊 Latest Prices:")
            print(df.to_string(index=False))
    
    # Latest prediction with ALL columns
    pred_columns = get_table_columns('predictions')
    if pred_columns:
        pred = pd.read_sql_query(f"""
            SELECT {', '.join(pred_columns)}
            FROM predictions 
            ORDER BY date DESC 
            LIMIT 1
        """, conn)
        if not pred.empty:
            print("\n🎯 Latest Prediction:")
            print(pred.to_string(index=False))
    
    # Performance
    perf_columns = get_table_columns('performance')
    if perf_columns:
        perf = pd.read_sql_query(f"""
            SELECT {', '.join(perf_columns)}
            FROM performance 
            ORDER BY date DESC 
            LIMIT 1
        """, conn)
        if not perf.empty and 'direction_accuracy' in perf.columns:
            print(f"\n📈 Current Accuracy: {perf['direction_accuracy'].iloc[0]:.1f}% ({perf['total_predictions'].iloc[0]} predictions)")
    
    conn.close()
    print("="*80 + "\n")

# ============================================
# 6. MAIN MENU
# ============================================

def show_menu():
    """Display main menu"""
    print("\n" + "="*80)
    print("📊 BTC DATABASE MANAGER (rough.py)")
    print("="*80)
    print("\nSelect an option:")
    print("  1. 📊 View BTC Daily Data")
    print("  2. 🎯 View Predictions History")
    print("  3. 📈 View Performance Metrics")
    print("  4. 📤 Export to Excel (ALL Columns)")
    print("  5. 🔍 Analyze Data")
    print("  6. ⚡ Quick View")
    print("  7. 📋 Database Info")
    print("  8. 🗑️ Delete Old Data (older than 365 days)")
    print("  9. 🗑️ Clear All Predictions")
    print(" 10. 🗑️ Clear ALL Data (WARNING!)")
    print(" 11. ❌ Exit")
    print("="*80)

def view_all_tables():
    """View all tables in database"""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("\n" + "="*80)
    print("📋 DATABASE TABLES")
    print("="*80)
    
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  • {table_name}: {count} records")
    
    conn.close()
    print("="*80 + "\n")

def main():
    """Main function"""
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database '{DB_PATH}' not found!")
        print("Please run btc_pipeline.py first to create the database.")
        return
    
    while True:
        show_menu()
        choice = input("\nEnter your choice (1-11): ").strip()
        
        if choice == '1':
            view_all_data()
        elif choice == '2':
            view_predictions()
        elif choice == '3':
            view_performance()
        elif choice == '4':
            export_to_excel()
        elif choice == '5':
            analyze_data()
        elif choice == '6':
            quick_view()
        elif choice == '7':
            show_database_info()
        elif choice == '8':
            delete_old_data(365)
        elif choice == '9':
            clear_predictions()
        elif choice == '10':
            clear_all_data()
        elif choice == '11':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice! Please try again.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()