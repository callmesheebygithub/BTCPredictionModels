
"""
BTC_MYSQL_EXPORTER.py
MySQL Data Download & Export Tool

Features:
- Automatically detects ALL tables in the selected MySQL database
- Export ALL tables to Excel
- Export ALL tables to separate CSV files
- Export ALL tables to separate JSON files
- Create ZIP containing all exports
- Optional BTC-specific analysis sheets
- Database/table information viewer
- Custom SQL query support
"""

import mysql.connector
from mysql.connector import Error

import pandas as pd
import numpy as np

from datetime import datetime
import os
import sys
import json
import zipfile
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# 1. LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

DB_USER = os.getenv("db_user")
DB_PASSWORD = os.getenv("db_password")
DB_HOST = os.getenv("db_host")
DB_NAME = os.getenv("db_name")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
    raise ValueError(
        "❌ .env file mein kuch values missing hain!\n"
        "Please check:\n"
        "db_user\n"
        "db_password\n"
        "db_host\n"
        "db_name"
    )


# ============================================================
# 2. CONFIGURATION
# ============================================================

DB_CONFIG = {
    "host": DB_HOST,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME,
}

EXPORT_DIR = "btc_exports"

Path(EXPORT_DIR).mkdir(parents=True, exist_ok=True)


# ============================================================
# IMPORTANT:
# We DO NOT hardcode table names anymore.
#
# The program automatically detects ALL tables from MySQL.
# ============================================================


# ============================================================
# 3. DATABASE CONNECTION
# ============================================================

def get_connection():
    """Create and return MySQL database connection."""

    try:
        conn = mysql.connector.connect(**DB_CONFIG)

        if conn.is_connected():
            return conn

        return None

    except Error as e:
        print(f"❌ Database connection failed: {e}")
        print(
            f"📋 Host={DB_CONFIG['host']}, "
            f"User={DB_CONFIG['user']}, "
            f"Database={DB_CONFIG['database']}"
        )
        return None


# ============================================================
# 4. TEST CONNECTION
# ============================================================

def test_connection():
    """Test MySQL database connection."""

    print("\n" + "=" * 80)
    print("🔌 TESTING DATABASE CONNECTION")
    print("=" * 80)

    conn = get_connection()

    if not conn:
        return False

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()

        print(f"✅ Connected to MySQL")
        print(f"🛢️ MySQL Version: {version[0]}")
        print(f"📁 Database: {DB_CONFIG['database']}")

        cursor.close()
        conn.close()

        return True

    except Error as e:
        print(f"❌ Connection test failed: {e}")

        try:
            conn.close()
        except:
            pass

        return False


# ============================================================
# 5. GET ALL DATABASE TABLES
# ============================================================

def get_all_tables():
    """
    Automatically detect ALL tables in the selected database.
    """

    conn = get_connection()

    if not conn:
        return []

    try:
        cursor = conn.cursor()

        cursor.execute("SHOW TABLES")

        rows = cursor.fetchall()

        tables = [row[0] for row in rows]

        cursor.close()
        conn.close()

        return tables

    except Error as e:

        print(f"❌ Error getting tables: {e}")

        try:
            conn.close()
        except:
            pass

        return []


# ============================================================
# 6. SAFE MYSQL IDENTIFIER
# ============================================================

def quote_identifier(identifier):
    """
    Safely quote a MySQL table/column identifier.
    """

    identifier = str(identifier).replace("`", "``")

    return f"`{identifier}`"


# ============================================================
# 7. GET TABLE COLUMNS
# ============================================================

def get_table_columns(conn, table_name):
    """Return list of columns for a table."""

    try:

        cursor = conn.cursor()

        query = f"SHOW COLUMNS FROM {quote_identifier(table_name)}"

        cursor.execute(query)

        rows = cursor.fetchall()

        cursor.close()

        return [row[0] for row in rows]

    except Error as e:

        print(
            f"❌ Error getting columns for "
            f"{table_name}: {e}"
        )

        return []


# ============================================================
# 8. CHECK IF TABLE HAS DATE COLUMN
# ============================================================

def get_order_column(conn, table_name):
    """
    Find a sensible column for ordering.

    Priority:
    1. date
    2. datetime
    3. timestamp
    4. created_at
    5. id
    6. no ordering
    """

    columns = get_table_columns(conn, table_name)

    if not columns:
        return None

    priority_columns = [
        "date",
        "datetime",
        "timestamp",
        "created_at",
        "updated_at",
        "id",
    ]

    column_lower_map = {
        col.lower(): col
        for col in columns
    }

    for candidate in priority_columns:

        if candidate in column_lower_map:
            return column_lower_map[candidate]

    return None


# ============================================================
# 9. GET ALL DATA FROM TABLE
# ============================================================

def get_all_data(table_name, conn=None):
    """
    Get ALL rows and ALL columns from a table.

    Automatically handles tables that don't have a date column.
    """

    close_connection = False

    if conn is None:

        conn = get_connection()

        if not conn:
            return None

        close_connection = True

    try:

        order_column = get_order_column(
            conn,
            table_name
        )

        table_sql = quote_identifier(table_name)

        if order_column:

            order_sql = quote_identifier(
                order_column
            )

            query = (
                f"SELECT * FROM {table_sql} "
                f"ORDER BY {order_sql}"
            )

        else:

            query = f"SELECT * FROM {table_sql}"

        df = pd.read_sql_query(
            query,
            conn
        )

        return df

    except Exception as e:

        print(
            f"❌ Error getting data "
            f"from {table_name}: {e}"
        )

        return None

    finally:

        if close_connection:

            try:
                conn.close()
            except:
                pass


# ============================================================
# 10. GET TABLE INFORMATION
# ============================================================

def get_table_info():
    """
    Get information about EVERY table
    in the selected database.
    """

    conn = get_connection()

    if not conn:
        return {}

    try:

        tables = get_all_tables()

        table_info = {}

        for table_name in tables:

            columns = get_table_columns(
                conn,
                table_name
            )

            try:

                cursor = conn.cursor()

                count_query = (
                    f"SELECT COUNT(*) "
                    f"FROM {quote_identifier(table_name)}"
                )

                cursor.execute(count_query)

                count = cursor.fetchone()[0]

                cursor.close()

            except:

                count = 0

            table_info[table_name] = {
                "columns": columns,
                "count": count,
            }

        conn.close()

        return table_info

    except Error as e:

        print(f"❌ Error getting table info: {e}")

        try:
            conn.close()
        except:
            pass

        return {}


# ============================================================
# 11. GET DATA BY DATE RANGE
# ============================================================

def get_data_by_date_range(
    table_name,
    start_date,
    end_date
):
    """
    Get data between two dates.

    Only works if the table has a date column.
    """

    conn = get_connection()

    if not conn:
        return None

    try:

        columns = get_table_columns(
            conn,
            table_name
        )

        if "date" not in [
            c.lower() for c in columns
        ]:

            print(
                f"⚠️ Table '{table_name}' "
                f"does not have a date column."
            )

            return None

        date_column = next(
            c for c in columns
            if c.lower() == "date"
        )

        query = f"""
            SELECT *
            FROM {quote_identifier(table_name)}
            WHERE {quote_identifier(date_column)}
            BETWEEN %s AND %s
            ORDER BY {quote_identifier(date_column)}
        """

        df = pd.read_sql_query(
            query,
            conn,
            params=[start_date, end_date]
        )

        return df

    except Exception as e:

        print(
            f"❌ Error getting data "
            f"from {table_name}: {e}"
        )

        return None

    finally:

        try:
            conn.close()
        except:
            pass


# ============================================================
# 12. EXPORT ALL TABLES TO EXCEL
# ============================================================

def export_to_excel(filename=None):
    """
    Export EVERY database table to Excel.

    Each MySQL table gets its own Excel sheet.
    """

    if filename is None:

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = os.path.join(
            EXPORT_DIR,
            f"btc_complete_database_{timestamp}.xlsx"
        )

    print("\n" + "=" * 80)
    print("📤 EXPORTING ALL DATABASE TABLES TO EXCEL")
    print("=" * 80)

    conn = get_connection()

    if not conn:
        return False

    try:

        tables = get_all_tables()

        if not tables:

            print("❌ No tables found!")

            conn.close()

            return False

        print(
            f"📊 Found {len(tables)} tables "
            f"in database."
        )

        exported_tables = 0

        with pd.ExcelWriter(
            filename,
            engine="openpyxl"
        ) as writer:

            # ------------------------------------------------
            # EXPORT EVERY TABLE
            # ------------------------------------------------

            for table_name in tables:

                print(
                    f"\n📋 Exporting table: "
                    f"{table_name}"
                )

                df = get_all_data(
                    table_name,
                    conn
                )

                if df is None:

                    print(
                        "   ❌ Failed to read table"
                    )

                    continue

                # Excel sheet names max = 31 chars
                sheet_name = table_name[:31]

                # Make sure sheet name is valid
                invalid_chars = [
                    "\\",
                    "/",
                    "*",
                    "?",
                    ":",
                    "[",
                    "]",
                ]

                for char in invalid_chars:
                    sheet_name = sheet_name.replace(
                        char,
                        "_"
                    )

                # Excel cannot have duplicate sheet names
                existing_sheets = writer.book.sheetnames

                original_sheet_name = sheet_name
                counter = 1

                while sheet_name in existing_sheets:

                    suffix = f"_{counter}"

                    sheet_name = (
                        original_sheet_name[:31 - len(suffix)]
                        + suffix
                    )

                    counter += 1

                df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False
                )

                print(
                    f"   ✅ {len(df):,} records "
                    f"exported"
                )

                exported_tables += 1

            # ------------------------------------------------
            # DATABASE SUMMARY
            # ------------------------------------------------

            print(
                "\n📊 Creating Database_Summary..."
            )

            summary_rows = []

            for table_name in tables:

                df = get_all_data(
                    table_name,
                    conn
                )

                if df is not None:

                    summary_rows.append([
                        table_name,
                        len(df),
                        len(df.columns),
                        ", ".join(df.columns)
                    ])

            summary_df = pd.DataFrame(
                summary_rows,
                columns=[
                    "Table",
                    "Records",
                    "Columns_Count",
                    "Columns"
                ]
            )

            summary_df.to_excel(
                writer,
                sheet_name="Database_Summary",
                index=False
            )

            # ------------------------------------------------
            # COLUMN INFORMATION
            # ------------------------------------------------

            print(
                "📋 Creating Column_Info..."
            )

            column_rows = []

            for table_name in tables:

                try:

                    cursor = conn.cursor()

                    cursor.execute(
                        f"DESCRIBE "
                        f"{quote_identifier(table_name)}"
                    )

                    columns = cursor.fetchall()

                    cursor.close()

                    for col in columns:

                        column_rows.append([
                            table_name,
                            col[0],
                            col[1],
                            col[2],
                            col[3],
                            col[4],
                            col[5],
                        ])

                except Exception as e:

                    print(
                        f"⚠️ Could not describe "
                        f"{table_name}: {e}"
                    )

            column_df = pd.DataFrame(
                column_rows,
                columns=[
                    "Table",
                    "Column",
                    "Data Type",
                    "Nullable",
                    "Key",
                    "Default",
                    "Extra",
                ]
            )

            column_df.to_excel(
                writer,
                sheet_name="Column_Info",
                index=False
            )

            # ------------------------------------------------
            # BTC ANALYSIS
            # ------------------------------------------------

            if "btc_price_history" in tables:

                print(
                    "\n📈 Creating BTC analysis sheets..."
                )

                btc_data = get_all_data(
                    "btc_price_history",
                    conn
                )

                if (
                    btc_data is not None
                    and not btc_data.empty
                ):

                    if "date" in btc_data.columns:

                        summary = create_summary_sheet(
                            btc_data
                        )

                        summary.to_excel(
                            writer,
                            sheet_name="BTC_Summary",
                            index=False
                        )

                        all_time = create_all_time_stats(
                            btc_data
                        )

                        all_time.to_excel(
                            writer,
                            sheet_name="All_Time_Stats",
                            index=False
                        )

                        monthly = create_monthly_stats(
                            btc_data
                        )

                        monthly.to_excel(
                            writer,
                            sheet_name="Monthly_Stats",
                            index=False
                        )

                        yearly = create_yearly_stats(
                            btc_data
                        )

                        yearly.to_excel(
                            writer,
                            sheet_name="Yearly_Stats",
                            index=False
                        )

                        distribution = create_price_distribution(
                            btc_data
                        )

                        distribution.to_excel(
                            writer,
                            sheet_name="Price_Distribution",
                            index=False
                        )

                        technical = create_technical_indicators(
                            btc_data
                        )

                        if technical is not None:

                            technical.to_excel(
                                writer,
                                sheet_name="Technical_Indicators",
                                index=False
                            )

            # ------------------------------------------------
            # BTC DAILY INDICATORS ANALYSIS
            # ------------------------------------------------

            if "btc_daily_indicators" in tables:

                print(
                    "📊 Creating indicator analysis..."
                )

                indicator_data = get_all_data(
                    "btc_daily_indicators",
                    conn
                )

                if (
                    indicator_data is not None
                    and not indicator_data.empty
                ):

                    indicators_summary = (
                        create_indicators_summary(
                            indicator_data
                        )
                    )

                    indicators_summary.to_excel(
                        writer,
                        sheet_name="Indicators_Summary",
                        index=False
                    )

        conn.close()

        # ----------------------------------------------------
        # FINAL RESULT
        # ----------------------------------------------------

        print("\n" + "=" * 80)
        print("✅ EXCEL EXPORT COMPLETED")
        print("=" * 80)

        print(
            f"📁 File: {filename}"
        )

        if os.path.exists(filename):

            size_mb = (
                os.path.getsize(filename)
                / (1024 * 1024)
            )

            print(
                f"📦 Size: {size_mb:.2f} MB"
            )

        print(
            f"📊 Tables exported: "
            f"{exported_tables}/{len(tables)}"
        )

        print("=" * 80)

        # Windows: automatically open
        if sys.platform == "win32":

            try:
                os.startfile(filename)
                print("📂 Excel file opened automatically.")

            except:
                pass

        return True

    except Exception as e:

        print(
            f"❌ Excel export failed: {e}"
        )

        import traceback
        traceback.print_exc()

        try:
            conn.close()
        except:
            pass

        return False


# ============================================================
# 13. EXPORT ALL TABLES TO CSV
# ============================================================

def export_to_csv():
    """
    Export EVERY MySQL table to a separate CSV file.
    """

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    export_folder = os.path.join(
        EXPORT_DIR,
        f"csv_export_{timestamp}"
    )

    Path(export_folder).mkdir(
        parents=True,
        exist_ok=True
    )

    print("\n" + "=" * 80)
    print("📤 EXPORTING ALL DATABASE TABLES TO CSV")
    print("=" * 80)

    conn = get_connection()

    if not conn:
        return False

    try:

        tables = get_all_tables()

        exported_count = 0

        for table_name in tables:

            print(
                f"📊 Exporting {table_name}..."
            )

            df = get_all_data(
                table_name,
                conn
            )

            if df is None:
                continue

            filename = os.path.join(
                export_folder,
                f"{table_name}.csv"
            )

            df.to_csv(
                filename,
                index=False,
                encoding="utf-8-sig"
            )

            print(
                f"   ✅ {len(df):,} records "
                f"saved"
            )

            exported_count += 1

        conn.close()

        print("\n" + "=" * 80)
        print("✅ CSV EXPORT COMPLETED")
        print("=" * 80)

        print(
            f"📁 Folder: {export_folder}"
        )

        print(
            f"📊 Files: "
            f"{exported_count}/{len(tables)}"
        )

        print("=" * 80)

        return True

    except Exception as e:

        print(
            f"❌ CSV export failed: {e}"
        )

        try:
            conn.close()
        except:
            pass

        return False


# ============================================================
# 14. EXPORT ALL TABLES TO JSON
# ============================================================

def export_to_json():
    """
    Export EVERY MySQL table to a separate JSON file.
    """

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    export_folder = os.path.join(
        EXPORT_DIR,
        f"json_export_{timestamp}"
    )

    Path(export_folder).mkdir(
        parents=True,
        exist_ok=True
    )

    print("\n" + "=" * 80)
    print("📤 EXPORTING ALL DATABASE TABLES TO JSON")
    print("=" * 80)

    conn = get_connection()

    if not conn:
        return False

    try:

        tables = get_all_tables()

        exported_count = 0

        for table_name in tables:

            print(
                f"📊 Exporting {table_name}..."
            )

            df = get_all_data(
                table_name,
                conn
            )

            if df is None:
                continue

            # Convert datetime/date columns
            for col in df.columns:

                if (
                    pd.api.types.is_datetime64_any_dtype(
                        df[col]
                    )
                    or "date" in col.lower()
                    or "time" in col.lower()
                ):

                    df[col] = df[col].astype(str)

            filename = os.path.join(
                export_folder,
                f"{table_name}.json"
            )

            df.to_json(
                filename,
                orient="records",
                indent=2,
                force_ascii=False
            )

            print(
                f"   ✅ {len(df):,} records "
                f"saved"
            )

            exported_count += 1

        conn.close()

        print("\n" + "=" * 80)
        print("✅ JSON EXPORT COMPLETED")
        print("=" * 80)

        print(
            f"📁 Folder: {export_folder}"
        )

        print(
            f"📊 Files: "
            f"{exported_count}/{len(tables)}"
        )

        print("=" * 80)

        return True

    except Exception as e:

        print(
            f"❌ JSON export failed: {e}"
        )

        try:
            conn.close()
        except:
            pass

        return False


# ============================================================
# 15. EXPORT ALL FORMATS
# ============================================================

def export_all_formats():
    """
    Export the complete database in:
    Excel + CSV + JSON
    """

    print("\n" + "=" * 80)
    print("📤 EXPORTING COMPLETE DATABASE")
    print("=" * 80)

    success = True

    if not export_to_excel():
        success = False

    if not export_to_csv():
        success = False

    if not export_to_json():
        success = False

    print("\n" + "=" * 80)

    if success:

        print(
            "✅ ALL FORMATS EXPORTED SUCCESSFULLY!"
        )

    else:

        print(
            "⚠️ Some exports failed."
        )

    print("=" * 80)

    return success


# ============================================================
# 16. CREATE ZIP EXPORT
# ============================================================

def create_zip_export():
    """
    Create ZIP containing:
    - Complete Excel file
    - CSV folder
    - JSON folder
    """

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    zip_filename = os.path.join(
        EXPORT_DIR,
        f"btc_complete_export_{timestamp}.zip"
    )

    print("\n" + "=" * 80)
    print("📦 CREATING COMPLETE ZIP EXPORT")
    print("=" * 80)

    print(
        "📤 Exporting Excel, CSV and JSON..."
    )

    excel_success = export_to_excel()
    csv_success = export_to_csv()
    json_success = export_to_json()

    if not (
        excel_success
        or csv_success
        or json_success
    ):

        print(
            "❌ No exports were created."
        )

        return False

    # --------------------------------------------------------
    # Find latest exports
    # --------------------------------------------------------

    export_items = []

    files = list(
        Path(EXPORT_DIR).iterdir()
    )

    # Excel files
    excel_files = [
        p for p in files
        if p.is_file()
        and p.suffix.lower() == ".xlsx"
    ]

    if excel_files:

        latest_excel = max(
            excel_files,
            key=lambda p: p.stat().st_mtime
        )

        export_items.append(
            latest_excel
        )

    # CSV folders
    csv_folders = [
        p for p in files
        if p.is_dir()
        and p.name.startswith("csv_export_")
    ]

    if csv_folders:

        latest_csv = max(
            csv_folders,
            key=lambda p: p.stat().st_mtime
        )

        export_items.append(
            latest_csv
        )

    # JSON folders
    json_folders = [
        p for p in files
        if p.is_dir()
        and p.name.startswith("json_export_")
    ]

    if json_folders:

        latest_json = max(
            json_folders,
            key=lambda p: p.stat().st_mtime
        )

        export_items.append(
            latest_json
        )

    if not export_items:

        print(
            "❌ Nothing found to put in ZIP."
        )

        return False

    # --------------------------------------------------------
    # Create ZIP
    # --------------------------------------------------------

    print(
        f"\n📦 Creating ZIP: "
        f"{zip_filename}"
    )

    with zipfile.ZipFile(
        zip_filename,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zipf:

        for item in export_items:

            item = Path(item)

            if item.is_file():

                zipf.write(
                    item,
                    item.name
                )

            else:

                for file_path in item.rglob("*"):

                    if file_path.is_file():

                        arcname = os.path.join(
                            item.name,
                            file_path.relative_to(item)
                        )

                        zipf.write(
                            file_path,
                            arcname
                        )

    print("\n" + "=" * 80)
    print("✅ ZIP EXPORT COMPLETED")
    print("=" * 80)

    print(
        f"📁 File: {zip_filename}"
    )

    if os.path.exists(zip_filename):

        size_mb = (
            os.path.getsize(zip_filename)
            / (1024 * 1024)
        )

        print(
            f"📦 Size: {size_mb:.2f} MB"
        )

    print("=" * 80)

    return True


# ============================================================
# 17. BTC SUMMARY
# ============================================================

def create_summary_sheet(btc_data):
    """Create BTC summary statistics."""

    summary_data = []

    summary_data.append(
        ["METRIC", "VALUE"]
    )

    summary_data.append(
        ["Total Records", len(btc_data)]
    )

    if btc_data.empty:
        return pd.DataFrame(
            summary_data,
            columns=["Metric", "Value"]
        )

    if "date" in btc_data.columns:

        summary_data.append([
            "Date Range Start",
            btc_data["date"].min()
        ])

        summary_data.append([
            "Date Range End",
            btc_data["date"].max()
        ])

    if "close" in btc_data.columns:

        close = pd.to_numeric(
            btc_data["close"],
            errors="coerce"
        )

        summary_data.append(
            ["", ""]
        )

        summary_data.append(
            ["PRICE STATISTICS", ""]
        )

        summary_data.append([
            "Current Price",
            f"${close.iloc[-1]:,.2f}"
        ])

        summary_data.append([
            "Average Price",
            f"${close.mean():,.2f}"
        ])

        summary_data.append([
            "Median Price",
            f"${close.median():,.2f}"
        ])

        summary_data.append([
            "Min Price",
            f"${close.min():,.2f}"
        ])

        summary_data.append([
            "Max Price",
            f"${close.max():,.2f}"
        ])

        returns = close.pct_change() * 100

        summary_data.append(
            ["", ""]
        )

        summary_data.append(
            ["RETURNS", ""]
        )

        if close.iloc[0] != 0:

            total_return = (
                (
                    close.iloc[-1]
                    - close.iloc[0]
                )
                / close.iloc[0]
                * 100
            )

            summary_data.append([
                "Total Return %",
                f"{total_return:.2f}%"
            ])

        summary_data.append([
            "Average Daily Return %",
            f"{returns.mean():.2f}%"
        ])

        summary_data.append([
            "Max Daily Gain %",
            f"{returns.max():.2f}%"
        ])

        summary_data.append([
            "Max Daily Loss %",
            f"{returns.min():.2f}%"
        ])

        summary_data.append([
            "Standard Deviation %",
            f"{returns.std():.2f}%"
        ])

    if "volume" in btc_data.columns:

        volume = pd.to_numeric(
            btc_data["volume"],
            errors="coerce"
        )

        summary_data.append(
            ["", ""]
        )

        summary_data.append(
            ["VOLUME", ""]
        )

        summary_data.append([
            "Average Volume",
            f"{volume.mean():,.0f}"
        ])

        summary_data.append([
            "Max Volume",
            f"{volume.max():,.0f}"
        ])

        summary_data.append([
            "Min Volume",
            f"{volume.min():,.0f}"
        ])

    return pd.DataFrame(
        summary_data,
        columns=["Metric", "Value"]
    )


# ============================================================
# 18. BTC TECHNICAL INDICATORS
# ============================================================

def create_technical_indicators(btc_data):
    """Create technical indicators."""

    if (
        btc_data.empty
        or len(btc_data) < 50
        or "close" not in btc_data.columns
    ):
        return None

    df = btc_data.copy()

    close = pd.to_numeric(
        df["close"],
        errors="coerce"
    )

    # Moving averages
    df["MA_7"] = close.rolling(7).mean()
    df["MA_25"] = close.rolling(25).mean()
    df["MA_50"] = close.rolling(50).mean()
    df["MA_200"] = close.rolling(200).mean()

    # RSI
    delta = close.diff()

    gain = (
        delta.where(delta > 0, 0)
        .rolling(14)
        .mean()
    )

    loss = (
        -delta.where(delta < 0, 0)
        .rolling(14)
        .mean()
    )

    rs = gain / loss

    df["RSI_14"] = (
        100
        - (100 / (1 + rs))
    )

    # Bollinger Bands
    middle = close.rolling(20).mean()
    std = close.rolling(20).std()

    df["BB_Upper"] = (
        middle + (std * 2)
    )

    df["BB_Middle"] = middle

    df["BB_Lower"] = (
        middle - (std * 2)
    )

    # MACD
    exp1 = close.ewm(
        span=12,
        adjust=False
    ).mean()

    exp2 = close.ewm(
        span=26,
        adjust=False
    ).mean()

    df["MACD"] = exp1 - exp2

    df["MACD_Signal"] = (
        df["MACD"]
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    df["MACD_Histogram"] = (
        df["MACD"]
        - df["MACD_Signal"]
    )

    # ATR
    if all(
        col in df.columns
        for col in ["high", "low"]
    ):

        high = pd.to_numeric(
            df["high"],
            errors="coerce"
        )

        low = pd.to_numeric(
            df["low"],
            errors="coerce"
        )

        high_low = high - low

        high_close = (
            high
            - close.shift()
        ).abs()

        low_close = (
            low
            - close.shift()
        ).abs()

        true_range = pd.concat(
            [
                high_low,
                high_close,
                low_close,
            ],
            axis=1
        ).max(axis=1)

        df["ATR_14"] = (
            true_range
            .rolling(14)
            .mean()
        )

    # Return last 30 rows for analysis
    return df.tail(30)


# ============================================================
# 19. ALL-TIME STATISTICS
# ============================================================

def create_all_time_stats(btc_data):

    if (
        btc_data.empty
        or "close" not in btc_data.columns
    ):
        return pd.DataFrame()

    close = pd.to_numeric(
        btc_data["close"],
        errors="coerce"
    )

    stats = []

    stats.append([
        "STATISTIC",
        "DATE",
        "VALUE"
    ])

    ath_idx = close.idxmax()
    atl_idx = close.idxmin()

    ath_date = (
        btc_data.loc[ath_idx, "date"]
        if "date" in btc_data.columns
        else ""
    )

    atl_date = (
        btc_data.loc[atl_idx, "date"]
        if "date" in btc_data.columns
        else ""
    )

    stats.append([
        "All-Time High",
        ath_date,
        f"${close.loc[ath_idx]:,.2f}"
    ])

    stats.append([
        "All-Time Low",
        atl_date,
        f"${close.loc[atl_idx]:,.2f}"
    ])

    current = close.iloc[-1]
    ath = close.max()
    atl = close.min()

    stats.append(["", "", ""])
    stats.append([
        "CURRENT POSITION",
        "",
        ""
    ])

    stats.append([
        "Price from ATH",
        "",
        f"{current / ath * 100:.1f}%"
    ])

    stats.append([
        "Price from ATL",
        "",
        f"{current / atl * 100:.1f}%"
    ])

    if ath != atl:

        percentile = (
            (current - atl)
            / (ath - atl)
            * 100
        )

        stats.append([
            "Current Percentile",
            "",
            f"{percentile:.1f}%"
        ])

    return pd.DataFrame(
        stats[1:],
        columns=stats[0]
    )


# ============================================================
# 20. MONTHLY STATISTICS
# ============================================================

def create_monthly_stats(btc_data):

    if (
        btc_data.empty
        or "date" not in btc_data.columns
        or "close" not in btc_data.columns
    ):
        return pd.DataFrame()

    df = btc_data.copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    agg_dict = {
        "close": [
            "mean",
            "min",
            "max",
            "std",
        ]
    }

    if "volume" in df.columns:
        agg_dict["volume"] = "mean"

    monthly = (
        df.groupby(
            ["year", "month"]
        )
        .agg(agg_dict)
        .round(2)
    )

    columns = [
        "Avg_Close",
        "Min_Close",
        "Max_Close",
        "Std_Dev",
    ]

    if "volume" in df.columns:
        columns.append("Avg_Volume")

    monthly.columns = columns

    monthly = monthly.reset_index()

    return monthly


# ============================================================
# 21. YEARLY STATISTICS
# ============================================================

def create_yearly_stats(btc_data):

    if (
        btc_data.empty
        or "date" not in btc_data.columns
        or "close" not in btc_data.columns
    ):
        return pd.DataFrame()

    df = btc_data.copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df["year"] = df["date"].dt.year

    yearly = (
        df.groupby("year")
        .agg(
            Avg_Close=("close", "mean"),
            Min_Close=("close", "min"),
            Max_Close=("close", "max"),
            Std_Dev=("close", "std")
        )
        .round(2)
        .reset_index()
    )

    year_start = (
        df.groupby("year")["close"]
        .first()
        .reset_index(name="Year_Start")
    )

    year_end = (
        df.groupby("year")["close"]
        .last()
        .reset_index(name="Year_End")
    )

    yearly = yearly.merge(
        year_start,
        on="year"
    )

    yearly = yearly.merge(
        year_end,
        on="year"
    )

    yearly["Year_Return_%"] = (
        (
            yearly["Year_End"]
            - yearly["Year_Start"]
        )
        / yearly["Year_Start"]
        * 100
    ).round(2)

    return yearly


# ============================================================
# 22. PRICE DISTRIBUTION
# ============================================================

def create_price_distribution(btc_data):

    if (
        btc_data.empty
        or "close" not in btc_data.columns
    ):
        return pd.DataFrame()

    df = btc_data.copy()

    df["close"] = pd.to_numeric(
        df["close"],
        errors="coerce"
    )

    bins = [
        0,
        1000,
        5000,
        10000,
        20000,
        30000,
        40000,
        50000,
        60000,
        70000,
        80000,
        float("inf"),
    ]

    labels = [
        "$0-1K",
        "$1K-5K",
        "$5K-10K",
        "$10K-20K",
        "$20K-30K",
        "$30K-40K",
        "$40K-50K",
        "$50K-60K",
        "$60K-70K",
        "$70K-80K",
        "$80K+",
    ]

    df["price_range"] = pd.cut(
        df["close"],
        bins=bins,
        labels=labels,
        right=False
    )

    distribution = (
        df.groupby(
            "price_range",
            observed=False
        )
        .size()
        .reset_index(
            name="count"
        )
    )

    distribution["percentage"] = (
        distribution["count"]
        / len(df)
        * 100
    ).round(1)

    return distribution


# ============================================================
# 23. INDICATORS SUMMARY
# ============================================================

def create_indicators_summary(
    indicators_data
):

    if indicators_data.empty:
        return pd.DataFrame()

    summary_data = []

    summary_data.append([
        "METRIC",
        "VALUE"
    ])

    summary_data.append([
        "Total Records",
        len(indicators_data)
    ])

    if "date" in indicators_data.columns:

        summary_data.append([
            "Date Range Start",
            indicators_data["date"].min()
        ])

        summary_data.append([
            "Date Range End",
            indicators_data["date"].max()
        ])

    # Signal distribution
    if "signal_direction" in indicators_data.columns:

        summary_data.append([
            "",
            ""
        ])

        summary_data.append([
            "SIGNAL DISTRIBUTION",
            ""
        ])

        signal_counts = (
            indicators_data[
                "signal_direction"
            ]
            .value_counts()
        )

        for signal, count in signal_counts.items():

            pct = (
                count
                / len(indicators_data)
                * 100
            )

            summary_data.append([
                str(signal),
                f"{count} ({pct:.1f}%)"
            ])

    # RSI
    if "rsi_14" in indicators_data.columns:

        rsi = pd.to_numeric(
            indicators_data["rsi_14"],
            errors="coerce"
        )

        summary_data.append([
            "",
            ""
        ])

        summary_data.append([
            "RSI STATISTICS",
            ""
        ])

        summary_data.append([
            "Average",
            f"{rsi.mean():.2f}"
        ])

        summary_data.append([
            "Minimum",
            f"{rsi.min():.2f}"
        ])

        summary_data.append([
            "Maximum",
            f"{rsi.max():.2f}"
        ])

        summary_data.append([
            "Current",
            f"{rsi.iloc[-1]:.2f}"
        ])

    # Trend regime
    if "trend_regime" in indicators_data.columns:

        summary_data.append([
            "",
            ""
        ])

        summary_data.append([
            "TREND REGIME",
            ""
        ])

        regime_counts = (
            indicators_data[
                "trend_regime"
            ]
            .value_counts()
        )

        for regime, count in regime_counts.items():

            pct = (
                count
                / len(indicators_data)
                * 100
            )

            summary_data.append([
                str(regime),
                f"{count} ({pct:.1f}%)"
            ])

    # Signal score
    if "signal_score" in indicators_data.columns:

        score = pd.to_numeric(
            indicators_data["signal_score"],
            errors="coerce"
        )

        summary_data.append([
            "",
            ""
        ])

        summary_data.append([
            "SIGNAL SCORE",
            ""
        ])

        summary_data.append([
            "Average",
            f"{score.mean():.2f}"
        ])

        summary_data.append([
            "Minimum",
            f"{score.min():.2f}"
        ])

        summary_data.append([
            "Maximum",
            f"{score.max():.2f}"
        ])

        summary_data.append([
            "Current",
            f"{score.iloc[-1]:.2f}"
        ])

    return pd.DataFrame(
        summary_data,
        columns=["Metric", "Value"]
    )


# ============================================================
# 24. CUSTOM SQL QUERY
# ============================================================

def query_data():

    print("\n" + "=" * 80)
    print("🔍 CUSTOM SQL QUERY")
    print("=" * 80)

    conn = get_connection()

    if not conn:
        return

    print("\nAvailable Tables:")

    tables = get_all_tables()

    table_info = get_table_info()

    for table_name in tables:

        count = table_info.get(
            table_name,
            {}
        ).get(
            "count",
            0
        )

        print(
            f"  - {table_name} "
            f"({count:,} records)"
        )

    print(
        "\nEnter your SQL query "
        "(or 'exit' to go back):"
    )

    print(
        "Example: "
        "SELECT * FROM btc_price_history LIMIT 10"
    )

    while True:

        query = input(
            "\nSQL> "
        ).strip()

        if query.lower() == "exit":
            break

        if not query:
            continue

        try:

            df = pd.read_sql_query(
                query,
                conn
            )

            if df.empty:

                print(
                    "✅ Query executed successfully. "
                    "No results returned."
                )

            else:

                print(
                    f"\n✅ {len(df):,} "
                    "records returned:"
                )

                print(
                    df.to_string(
                        index=False
                    )
                )

                save = input(
                    "\nSave this data? (y/n): "
                ).strip().lower()

                if save == "y":

                    timestamp = (
                        datetime.now()
                        .strftime(
                            "%Y%m%d_%H%M%S"
                        )
                    )

                    filename = os.path.join(
                        EXPORT_DIR,
                        f"query_result_{timestamp}.csv"
                    )

                    df.to_csv(
                        filename,
                        index=False,
                        encoding="utf-8-sig"
                    )

                    print(
                        f"✅ Data saved to: "
                        f"{filename}"
                    )

        except Exception as e:

            print(
                f"❌ Query error: {e}"
            )

    conn.close()


# ============================================================
# 25. VIEW DATABASE TABLES
# ============================================================

def view_database_tables():

    print("\n" + "=" * 80)
    print("📊 ALL DATABASE TABLES")
    print("=" * 80)

    table_info = get_table_info()

    if not table_info:

        print(
            "❌ No tables found."
        )

        return

    conn = get_connection()

    if not conn:
        return

    total_records = 0

    for table_name, info in table_info.items():

        print(
            f"\n📋 Table: {table_name}"
        )

        print(
            f"   Records: "
            f"{info['count']:,}"
        )

        print(
            f"   Columns: "
            f"{len(info['columns'])}"
        )

        print(
            f"   Fields: "
            f"{', '.join(info['columns'])}"
        )

        total_records += info["count"]

        # Sample data
        try:

            query = (
                f"SELECT * FROM "
                f"{quote_identifier(table_name)} "
                f"LIMIT 3"
            )

            df = pd.read_sql_query(
                query,
                conn
            )

            if not df.empty:

                print(
                    "   Sample Data:"
                )

                print(
                    df.to_string(
                        index=False
                    )
                )

        except Exception as e:

            print(
                f"   ⚠️ Sample unavailable: {e}"
            )

    conn.close()

    print("\n" + "=" * 80)

    print(
        f"📊 Total Tables: "
        f"{len(table_info)}"
    )

    print(
        f"📊 Total Records: "
        f"{total_records:,}"
    )

    print("=" * 80)


# ============================================================
# 26. DATABASE INFORMATION
# ============================================================

def show_database_info():

    print("\n" + "=" * 80)
    print("📋 DATABASE INFORMATION")
    print("=" * 80)

    print(
        f"  • Host: "
        f"{DB_CONFIG['host']}"
    )

    print(
        f"  • Database: "
        f"{DB_CONFIG['database']}"
    )

    print(
        f"  • User: "
        f"{DB_CONFIG['user']}"
    )

    conn = get_connection()

    if not conn:
        return

    try:

        cursor = conn.cursor()

        cursor.execute(
            "SELECT VERSION()"
        )

        version = cursor.fetchone()

        print(
            f"  • MySQL Version: "
            f"{version[0]}"
        )

        cursor.close()

        conn.close()

    except:

        try:
            conn.close()
        except:
            pass

    table_info = get_table_info()

    if table_info:

        print(
            "\n  • ALL TABLES:"
        )

        total_records = 0

        for table_name, info in table_info.items():

            print(
                f"    - {table_name}: "
                f"{info['count']:,} records, "
                f"{len(info['columns'])} columns"
            )

            total_records += info["count"]

        print(
            f"\n  • Total Tables: "
            f"{len(table_info)}"
        )

        print(
            f"  • Total Records: "
            f"{total_records:,}"
        )

    print("=" * 80 + "\n")


# ============================================================
# 27. MAIN MENU
# ============================================================

def show_menu():

    print("\n" + "=" * 80)
    print("📊 BTC / MYSQL COMPLETE DATABASE EXPORTER")
    print("=" * 80)

    print("\nSelect an option:")

    print(
        "  1. 📤 Export ALL Tables to Excel"
    )

    print(
        "  2. 📤 Export ALL Tables to CSV"
    )

    print(
        "  3. 📤 Export ALL Tables to JSON"
    )

    print(
        "  4. 📤 Export ALL Formats"
    )

    print(
        "  5. 📦 Create ZIP Archive"
    )

    print(
        "  6. 📊 View ALL Database Tables"
    )

    print(
        "  7. 🔍 Run Custom SQL Query"
    )

    print(
        "  8. 📋 Database Information"
    )

    print(
        "  9. 🔌 Test Database Connection"
    )

    print(
        " 10. ❌ Exit"
    )

    print("=" * 80)


# ============================================================
# 28. MAIN FUNCTION
# ============================================================

def main():

    print("\n" + "=" * 80)
    print("🚀 MYSQL COMPLETE DATABASE EXPORTER")
    print("=" * 80)

    print(
        f"📁 Database: "
        f"{DB_CONFIG['database']}"
    )

    print(
        f"🖥️ Host: "
        f"{DB_CONFIG['host']}"
    )

    print(
        f"📁 Export Directory: "
        f"{EXPORT_DIR}"
    )

    print("=" * 80)

    # Test connection
    if not test_connection():

        print(
            "\n❌ Cannot connect to database."
        )

        print(
            "Please check your .env file."
        )

        print(
            "Make sure MySQL is running "
            "and credentials are correct."
        )

        return

    # Show detected tables
    tables = get_all_tables()

    print(
        f"\n📊 Detected "
        f"{len(tables)} table(s):"
    )

    for table in tables:

        print(
            f"   • {table}"
        )

    while True:

        show_menu()

        choice = input(
            "\nEnter your choice (1-10): "
        ).strip()

        if choice == "1":

            export_to_excel()

        elif choice == "2":

            export_to_csv()

        elif choice == "3":

            export_to_json()

        elif choice == "4":

            export_all_formats()

        elif choice == "5":

            create_zip_export()

        elif choice == "6":

            view_database_tables()

        elif choice == "7":

            query_data()

        elif choice == "8":

            show_database_info()

        elif choice == "9":

            test_connection()

        elif choice == "10":

            print(
                "\n👋 Goodbye!"
            )

            break

        else:

            print(
                "❌ Invalid choice! "
                "Please enter 1-10."
            )

        input(
            "\nPress Enter to continue..."
        )


# ============================================================
# 29. RUN PROGRAM
# ============================================================

if __name__ == "__main__":
    main()