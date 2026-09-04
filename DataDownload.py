"""
BTC_MYSQL_EXPORTER.py - MySQL Data Download & Export Tool
Download Bitcoin data from MySQL database in multiple formats
"""

import mysql.connector
from mysql.connector import Error
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import json
import zipfile
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DB_USER = os.getenv('db_user')
DB_PASSWORD = os.getenv('db_password')
DB_HOST = os.getenv('db_host')
DB_NAME = os.getenv('db_name')
# Agar koi value missing hai to error show karein
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
    raise ValueError("❌ .env file mein kuch values missing hain! Please check .env file.")
# ============================================
# CONFIGURATION
# ============================================

# Database credentials from .env
DB_CONFIG = {
    'host': os.getenv('db_host', DB_HOST),
    'user': os.getenv('db_user', DB_USER),
    'password': os.getenv('db_password', DB_PASSWORD),
    'database': os.getenv('db_name', DB_NAME)
}

EXPORT_DIR = 'btc_exports'  # Directory for exports

# Create export directory if it doesn't exist
Path(EXPORT_DIR).mkdir(exist_ok=True)

# ============================================
# DATABASE CONNECTION
# ============================================

def get_connection():
    """Get MySQL database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"❌ Database connection failed: {e}")
        print(f"📋 Config: Host={DB_CONFIG['host']}, User={DB_CONFIG['user']}, Database={DB_CONFIG['database']}")
        return None

def test_connection():
    """Test database connection"""
    print("\n" + "="*80)
    print("🔌 TESTING DATABASE CONNECTION")
    print("="*80)
    
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"✅ Connected to MySQL: {version[0]}")
        conn.close()
        return True
    except Error as e:
        print(f"❌ Connection test failed: {e}")
        return False

def get_table_info():
    """Get information about all tables in database"""
    conn = get_connection()
    if not conn:
        return {}
    
    try:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        table_info = {}
        for table in tables:
            table_name = table[0]
            
            # Get columns
            cursor.execute(f"SHOW COLUMNS FROM {table_name}")
            columns = [col[0] for col in cursor.fetchall()]
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            
            table_info[table_name] = {
                'columns': columns,
                'count': count
            }
        
        conn.close()
        return table_info
        
    except Error as e:
        print(f"❌ Error getting table info: {e}")
        conn.close()
        return {}

def get_all_data(table_name, columns=None):
    """Get all data from a table with optional columns"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        if columns:
            col_str = ', '.join(columns)
        else:
            col_str = '*'
        
        query = f"SELECT {col_str} FROM {table_name} ORDER BY date"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
        
    except Error as e:
        print(f"❌ Error getting data from {table_name}: {e}")
        conn.close()
        return None

def get_data_by_date_range(table_name, start_date, end_date):
    """Get data for a specific date range"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        query = f"""
            SELECT * FROM {table_name} 
            WHERE date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY date
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
        
    except Error as e:
        print(f"❌ Error getting data: {e}")
        conn.close()
        return None

# ============================================
# 1. EXPORT FUNCTIONS
# ============================================

def export_to_excel(filename=None, table_name='btc_price_history'):
    """Export data to Excel with multiple sheets and formatting"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(EXPORT_DIR, f'btc_data_{timestamp}.xlsx')
    
    print("\n" + "="*80)
    print("📤 EXPORTING DATA TO EXCEL (MySQL)")
    print("="*80)
    
    conn = get_connection()
    if not conn:
        return False
    
    try:
        # Get table info
        table_info = get_table_info()
        
        # Check if btc_price_history table exists
        if table_name not in table_info:
            print(f"❌ Table '{table_name}' not found!")
            print(f"Available tables: {', '.join(table_info.keys())}")
            conn.close()
            return False
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            
            # Sheet 1: BTC Price History (complete)
            print("📊 Exporting BTC price history...")
            btc_data = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY date", conn)
            if not btc_data.empty:
                btc_data.to_excel(writer, sheet_name='BTC_Price_History', index=False)
                print(f"   ✅ {len(btc_data)} records exported")
            
            # Sheet 2: Raw Data with all columns
            print("📊 Exporting raw data...")
            raw_data = btc_data.copy()
            raw_data.to_excel(writer, sheet_name='Raw_Data', index=False)
            
            # Sheet 3: Summary Statistics
            print("📊 Creating summary statistics...")
            summary = create_summary_sheet(btc_data)
            summary.to_excel(writer, sheet_name='Summary', index=False)
            
            # Sheet 4: Technical Indicators
            print("🔧 Creating technical indicators...")
            tech_data = create_technical_indicators(btc_data)
            if tech_data is not None:
                tech_data.to_excel(writer, sheet_name='Technical_Indicators', index=False)
            
            # Sheet 5: All-time Statistics
            print("📈 Creating all-time statistics...")
            all_time_stats = create_all_time_stats(btc_data)
            all_time_stats.to_excel(writer, sheet_name='All_Time_Stats', index=False)
            
            # Sheet 6: Column Information
            print("📋 Creating column information...")
            col_info = create_column_info_sheet(conn, table_info)
            col_info.to_excel(writer, sheet_name='Column_Info', index=False)
            
            # Sheet 7: Monthly Averages
            print("📊 Creating monthly averages...")
            monthly_stats = create_monthly_stats(btc_data)
            monthly_stats.to_excel(writer, sheet_name='Monthly_Stats', index=False)
            
            # Sheet 8: Yearly Statistics
            print("📅 Creating yearly statistics...")
            yearly_stats = create_yearly_stats(btc_data)
            yearly_stats.to_excel(writer, sheet_name='Yearly_Stats', index=False)
            
            # Sheet 9: Price Distribution
            print("📊 Creating price distribution...")
            dist_data = create_price_distribution(btc_data)
            dist_data.to_excel(writer, sheet_name='Price_Distribution', index=False)
            
            # Sheet 10: Recent Data (Last 30 days)
            print("📊 Creating recent data...")
            recent_data = btc_data.tail(30) if len(btc_data) > 30 else btc_data
            recent_data.to_excel(writer, sheet_name='Recent_Data', index=False)
        
        conn.close()
        
        print("\n" + "="*80)
        print(f"✅ DATA EXPORTED SUCCESSFULLY!")
        print(f"📁 File: {filename}")
        if os.path.exists(filename):
            print(f"📊 Size: {os.path.getsize(filename) / (1024*1024):.2f} MB")
        print(f"📋 Sheets: 10")
        print("="*80 + "\n")
        
        # Open file automatically (Windows only)
        if sys.platform == 'win32':
            try:
                os.startfile(filename)
                print("📂 File opened automatically")
            except:
                pass
        
        return True
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def export_to_csv(table_name='btc_price_history'):
    """Export data to CSV files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_folder = os.path.join(EXPORT_DIR, f'csv_export_{timestamp}')
    Path(export_folder).mkdir(exist_ok=True)
    
    print("\n" + "="*80)
    print("📤 EXPORTING DATA TO CSV (MySQL)")
    print("="*80)
    
    conn = get_connection()
    if not conn:
        return False
    
    try:
        table_info = get_table_info()
        
        for table_name in table_info:
            print(f"📊 Exporting {table_name}...")
            df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY date", conn)
            if not df.empty:
                filename = os.path.join(export_folder, f'{table_name}.csv')
                df.to_csv(filename, index=False)
                print(f"   ✅ {len(df)} records saved to {filename}")
        
        conn.close()
        
        print("\n" + "="*80)
        print(f"✅ CSV EXPORT COMPLETED!")
        print(f"📁 Folder: {export_folder}")
        print(f"📊 Files: {len(table_info)}")
        print("="*80 + "\n")
        
        return True
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False

def export_to_json(table_name='btc_price_history'):
    """Export data to JSON files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_folder = os.path.join(EXPORT_DIR, f'json_export_{timestamp}')
    Path(export_folder).mkdir(exist_ok=True)
    
    print("\n" + "="*80)
    print("📤 EXPORTING DATA TO JSON (MySQL)")
    print("="*80)
    
    conn = get_connection()
    if not conn:
        return False
    
    try:
        table_info = get_table_info()
        
        for table_name in table_info:
            print(f"📊 Exporting {table_name}...")
            df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY date", conn)
            if not df.empty:
                # Convert date columns to string for JSON serialization
                for col in df.columns:
                    if 'date' in col.lower():
                        df[col] = df[col].astype(str)
                
                filename = os.path.join(export_folder, f'{table_name}.json')
                df.to_json(filename, orient='records', indent=2)
                print(f"   ✅ {len(df)} records saved to {filename}")
        
        conn.close()
        
        print("\n" + "="*80)
        print(f"✅ JSON EXPORT COMPLETED!")
        print(f"📁 Folder: {export_folder}")
        print("="*80 + "\n")
        
        return True
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False

def export_all_formats():
    """Export data in all formats (Excel, CSV, JSON)"""
    print("\n" + "="*80)
    print("📤 EXPORTING DATA IN ALL FORMATS (MySQL)")
    print("="*80)
    
    success = True
    
    # Export Excel
    if not export_to_excel():
        success = False
    
    # Export CSV
    if not export_to_csv():
        success = False
    
    # Export JSON
    if not export_to_json():
        success = False
    
    if success:
        print("\n✅ All exports completed successfully!")
    else:
        print("\n⚠️ Some exports failed. Please check the errors above.")
    
    return success

# ============================================
# 2. SHEET CREATION FUNCTIONS
# ============================================

def create_summary_sheet(btc_data):
    """Create summary statistics sheet"""
    summary_data = []
    
    # Basic Info
    summary_data.append(['METRIC', 'VALUE'])
    summary_data.append(['Total Records', len(btc_data)])
    if not btc_data.empty:
        summary_data.append(['Date Range Start', btc_data['date'].min()])
        summary_data.append(['Date Range End', btc_data['date'].max()])
    summary_data.append(['', ''])
    
    # Price Statistics
    if not btc_data.empty:
        summary_data.append(['PRICE STATISTICS', ''])
        summary_data.append(['Current Price', f"${btc_data['close'].iloc[-1]:,.2f}"])
        summary_data.append(['Average Price', f"${btc_data['close'].mean():,.2f}"])
        summary_data.append(['Median Price', f"${btc_data['close'].median():,.2f}"])
        summary_data.append(['Min Price', f"${btc_data['close'].min():,.2f}"])
        summary_data.append(['Max Price', f"${btc_data['close'].max():,.2f}"])
        summary_data.append(['Price Range', f"${btc_data['close'].max() - btc_data['close'].min():,.2f}"])
        summary_data.append(['', ''])
        
        # Returns
        returns = btc_data['close'].pct_change() * 100
        summary_data.append(['RETURNS', ''])
        total_return = ((btc_data['close'].iloc[-1] - btc_data['close'].iloc[0]) / btc_data['close'].iloc[0] * 100)
        summary_data.append(['Total Return %', f"{total_return:.2f}%"])
        summary_data.append(['Average Daily Return %', f"{returns.mean():.2f}%"])
        summary_data.append(['Max Daily Gain %', f"{returns.max():.2f}%"])
        summary_data.append(['Max Daily Loss %', f"{returns.min():.2f}%"])
        summary_data.append(['Standard Deviation %', f"{returns.std():.2f}%"])
        summary_data.append(['', ''])
        
        # Volume
        summary_data.append(['VOLUME', ''])
        summary_data.append(['Average Volume', f"{btc_data['volume'].mean():,.0f}"])
        summary_data.append(['Max Volume', f"{btc_data['volume'].max():,.0f}"])
        summary_data.append(['Min Volume', f"{btc_data['volume'].min():,.0f}"])
        summary_data.append(['', ''])
        
        # Winning/Losing Days
        winning_days = (returns > 0).sum()
        losing_days = (returns < 0).sum()
        summary_data.append(['DAYS SUMMARY', ''])
        summary_data.append(['Winning Days', winning_days])
        summary_data.append(['Losing Days', losing_days])
        summary_data.append(['Win Rate', f"{winning_days / len(btc_data) * 100:.1f}%"])
    
    df = pd.DataFrame(summary_data)
    df.columns = ['Metric', 'Value']
    return df

def create_technical_indicators(btc_data):
    """Create technical indicators sheet"""
    if btc_data.empty or len(btc_data) < 50:
        return None
    
    df = btc_data.copy()
    
    # Moving Averages
    df['MA_7'] = df['close'].rolling(7).mean()
    df['MA_25'] = df['close'].rolling(25).mean()
    df['MA_50'] = df['close'].rolling(50).mean()
    df['MA_200'] = df['close'].rolling(200).mean()
    
    # RSI (14-day)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI_14'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands (20-day, 2 std dev)
    df['BB_Upper'] = df['close'].rolling(20).mean() + (df['close'].rolling(20).std() * 2)
    df['BB_Middle'] = df['close'].rolling(20).mean()
    df['BB_Lower'] = df['close'].rolling(20).mean() - (df['close'].rolling(20).std() * 2)
    
    # MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    
    # ATR (14-day)
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR_14'] = true_range.rolling(14).mean()
    
    # Keep only last 30 days for summary
    return df.tail(30)

def create_all_time_stats(btc_data):
    """Create all-time statistics sheet"""
    if btc_data.empty:
        return pd.DataFrame()
    
    stats = []
    
    # All-time high/low
    ath_idx = btc_data['close'].idxmax()
    atl_idx = btc_data['close'].idxmin()
    
    stats.append(['STATISTIC', 'DATE', 'VALUE'])
    stats.append(['All-Time High', btc_data.loc[ath_idx, 'date'], f"${btc_data.loc[ath_idx, 'close']:,.2f}"])
    stats.append(['All-Time Low', btc_data.loc[atl_idx, 'date'], f"${btc_data.loc[atl_idx, 'close']:,.2f}"])
    
    # Current price position
    current = btc_data['close'].iloc[-1]
    ath = btc_data['close'].max()
    atl = btc_data['close'].min()
    
    stats.append(['', '', ''])
    stats.append(['CURRENT POSITION', '', ''])
    stats.append(['Price from ATH', '', f"{(current / ath * 100):.1f}%"])
    stats.append(['Price from ATL', '', f"{(current / atl * 100):.1f}%"])
    stats.append(['Current Percentile', '', f"{((current - atl) / (ath - atl) * 100):.1f}%"])
    
    df = pd.DataFrame(stats)
    df.columns = df.iloc[0]
    df = df[1:]
    return df

def create_column_info_sheet(conn, table_info):
    """Create column information sheet"""
    info_data = []
    
    for table_name, info in table_info.items():
        for col in info['columns']:
            # Get data type
            try:
                cursor = conn.cursor()
                cursor.execute(f"DESCRIBE {table_name} {col}")
                col_info = cursor.fetchone()
                data_type = col_info[1] if col_info else 'N/A'
            except:
                data_type = 'N/A'
            
            info_data.append([table_name, col, data_type])
    
    df = pd.DataFrame(info_data)
    df.columns = ['Table', 'Column', 'Data Type']
    return df

def create_monthly_stats(btc_data):
    """Create monthly statistics sheet"""
    if btc_data.empty:
        return pd.DataFrame()
    
    df = btc_data.copy()
    df['year'] = pd.to_datetime(df['date']).dt.year
    df['month'] = pd.to_datetime(df['date']).dt.month
    
    monthly = df.groupby(['year', 'month']).agg({
        'close': ['mean', 'min', 'max', 'std'],
        'volume': 'mean'
    }).round(2)
    
    monthly.columns = ['Avg_Close', 'Min_Close', 'Max_Close', 'Std_Dev', 'Avg_Volume']
    monthly = monthly.reset_index()
    
    # Format columns
    monthly['Avg_Close'] = monthly['Avg_Close'].apply(lambda x: f"${x:,.2f}")
    monthly['Min_Close'] = monthly['Min_Close'].apply(lambda x: f"${x:,.2f}")
    monthly['Max_Close'] = monthly['Max_Close'].apply(lambda x: f"${x:,.2f}")
    monthly['Avg_Volume'] = monthly['Avg_Volume'].apply(lambda x: f"{x:,.0f}")
    
    return monthly

def create_yearly_stats(btc_data):
    """Create yearly statistics sheet"""
    if btc_data.empty:
        return pd.DataFrame()
    
    df = btc_data.copy()
    df['year'] = pd.to_datetime(df['date']).dt.year
    
    yearly = df.groupby('year').agg({
        'close': ['mean', 'min', 'max', 'std'],
        'volume': 'mean'
    }).round(2)
    
    yearly.columns = ['Avg_Close', 'Min_Close', 'Max_Close', 'Std_Dev', 'Avg_Volume']
    yearly = yearly.reset_index()
    
    # Calculate yearly return
    yearly['Year_Start'] = df.groupby('year')['close'].first().values
    yearly['Year_End'] = df.groupby('year')['close'].last().values
    yearly['Year_Return_%'] = ((yearly['Year_End'] - yearly['Year_Start']) / yearly['Year_Start'] * 100).round(2)
    
    # Format columns
    yearly['Avg_Close'] = yearly['Avg_Close'].apply(lambda x: f"${x:,.2f}")
    yearly['Min_Close'] = yearly['Min_Close'].apply(lambda x: f"${x:,.2f}")
    yearly['Max_Close'] = yearly['Max_Close'].apply(lambda x: f"${x:,.2f}")
    yearly['Year_Return_%'] = yearly['Year_Return_%'].apply(lambda x: f"{x:+.2f}%")
    
    return yearly

def create_price_distribution(btc_data):
    """Create price distribution sheet"""
    if btc_data.empty:
        return pd.DataFrame()
    
    # Create price bins
    bins = [0, 1000, 5000, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, float('inf')]
    labels = ['$0-1K', '$1K-5K', '$5K-10K', '$10K-20K', '$20K-30K', '$30K-40K', 
              '$40K-50K', '$50K-60K', '$60K-70K', '$70K-80K', '$80K+']
    
    btc_data['price_range'] = pd.cut(btc_data['close'], bins=bins, labels=labels, right=False)
    
    distribution = btc_data.groupby('price_range').size().reset_index(name='count')
    distribution['percentage'] = (distribution['count'] / len(btc_data) * 100).round(1)
    distribution = distribution.sort_values('price_range')
    
    return distribution

# ============================================
# 3. DATA QUERY FUNCTIONS
# ============================================

def query_data():
    """Run custom SQL queries"""
    print("\n" + "="*80)
    print("🔍 CUSTOM SQL QUERY")
    print("="*80)
    
    conn = get_connection()
    if not conn:
        return
    
    print("\nAvailable Tables:")
    table_info = get_table_info()
    for table_name in table_info:
        print(f"  - {table_name} ({table_info[table_name]['count']} records)")
    
    print("\nEnter your SQL query (or 'exit' to go back):")
    print("Example: SELECT * FROM btc_price_history LIMIT 10")
    
    while True:
        query = input("\nSQL> ").strip()
        
        if query.lower() == 'exit':
            break
        
        if not query:
            continue
        
        try:
            df = pd.read_sql_query(query, conn)
            if df.empty:
                print("✅ Query executed successfully. No results returned.")
            else:
                print(f"\n✅ {len(df)} records returned:")
                print(df.to_string(index=False))
                
                # Option to save
                save = input("\nSave this data? (y/n): ").strip().lower()
                if save == 'y':
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = os.path.join(EXPORT_DIR, f'query_result_{timestamp}.csv')
                    df.to_csv(filename, index=False)
                    print(f"✅ Data saved to: {filename}")
                
        except Exception as e:
            print(f"❌ Query error: {e}")
    
    conn.close()

# ============================================
# 4. ZIP AND COMPRESS
# ============================================

def create_zip_export():
    """Create a ZIP file with all exports"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = os.path.join(EXPORT_DIR, f'btc_export_{timestamp}.zip')
    
    print("\n" + "="*80)
    print("📦 CREATING ZIP EXPORT (MySQL)")
    print("="*80)
    
    # First, export all formats
    print("📤 Exporting data...")
    export_to_excel()
    export_to_csv()
    export_to_json()
    
    # Find all export folders and files
    export_items = []
    for item in os.listdir(EXPORT_DIR):
        item_path = os.path.join(EXPORT_DIR, item)
        if os.path.isfile(item_path) and item.endswith('.xlsx'):
            export_items.append(item_path)
        elif os.path.isdir(item_path) and (item.startswith('csv_export_') or item.startswith('json_export_')):
            export_items.append(item_path)
    
    if not export_items:
        print("❌ No exports found to zip")
        return False
    
    print(f"\n📦 Creating ZIP file: {zip_filename}")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for item in export_items:
            if os.path.isfile(item):
                zipf.write(item, os.path.basename(item))
            else:
                for root, dirs, files in os.walk(item):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join(os.path.basename(item), file)
                        zipf.write(file_path, arcname)
    
    print(f"\n✅ ZIP export created: {zip_filename}")
    print(f"📊 Size: {os.path.getsize(zip_filename) / (1024*1024):.2f} MB")
    
    return True

# ============================================
# 5. MAIN MENU
# ============================================

def show_menu():
    """Display main menu"""
    print("\n" + "="*80)
    print("📊 BTC DATA EXPORTER (MySQL)")
    print("="*80)
    print("\nSelect an option:")
    print("  1. 📤 Export to Excel (10 Sheets with Analysis)")
    print("  2. 📤 Export to CSV (Separate files per table)")
    print("  3. 📤 Export to JSON (Separate files per table)")
    print("  4. 📤 Export ALL Formats (Excel + CSV + JSON)")
    print("  5. 📦 Create ZIP Archive with All Exports")
    print("  6. 📊 View Database Tables")
    print("  7. 🔍 Run Custom SQL Query")
    print("  8. 📋 Database Information")
    print("  9. 🔌 Test Database Connection")
    print(" 10. ❌ Exit")
    print("="*80)

def view_database_tables():
    """View all tables in database"""
    print("\n" + "="*80)
    print("📊 DATABASE TABLES")
    print("="*80)
    
    table_info = get_table_info()
    if not table_info:
        print("❌ No tables found or connection failed")
        return
    
    conn = get_connection()
    if not conn:
        return
    
    for table_name, info in table_info.items():
        print(f"\n📋 Table: {table_name}")
        print(f"   Records: {info['count']}")
        print(f"   Columns: {', '.join(info['columns'])}")
        
        # Show sample data
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 3", conn)
            if not df.empty:
                print(f"   Sample Data:")
                print(df.to_string(index=False))
        except:
            pass
    
    conn.close()
    print("\n" + "="*80)

def show_database_info():
    """Show database information"""
    print("\n" + "="*80)
    print("📋 DATABASE INFORMATION (MySQL)")
    print("="*80)
    
    print(f"  • Host: {DB_CONFIG['host']}")
    print(f"  • Database: {DB_CONFIG['database']}")
    print(f"  • User: {DB_CONFIG['user']}")
    
    conn = get_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"  • MySQL Version: {version[0]}")
        conn.close()
    except:
        pass
    
    table_info = get_table_info()
    if table_info:
        print(f"\n  • Tables:")
        total_records = 0
        for table_name, info in table_info.items():
            print(f"    - {table_name}: {info['count']} records, {len(info['columns'])} columns")
            total_records += info['count']
        print(f"\n  • Total Records: {total_records}")
    
    print("="*80 + "\n")

# ============================================
# 6. MAIN FUNCTION
# ============================================

def main():
    """Main function"""
    print("\n" + "="*80)
    print("🚀 BTC DATA EXPORTER (MySQL)")
    print(f"📁 Database: {DB_CONFIG['database']} @ {DB_CONFIG['host']}")
    print(f"📁 Export Directory: {EXPORT_DIR}")
    print("="*80)
    
    # Test connection first
    if not test_connection():
        print("\n❌ Cannot connect to database. Please check your .env file.")
        print("Make sure MySQL is running and credentials are correct.")
        return
    
    while True:
        show_menu()
        choice = input("\nEnter your choice (1-10): ").strip()
        
        if choice == '1':
            export_to_excel()
        elif choice == '2':
            export_to_csv()
        elif choice == '3':
            export_to_json()
        elif choice == '4':
            export_all_formats()
        elif choice == '5':
            create_zip_export()
        elif choice == '6':
            view_database_tables()
        elif choice == '7':
            query_data()
        elif choice == '8':
            show_database_info()
        elif choice == '9':
            test_connection()
        elif choice == '10':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice! Please try again.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()