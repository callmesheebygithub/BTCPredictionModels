"""
prepare_btc_ml_data.py

Purpose:
    Read BTC daily OHLCV data from:
        btc_price_history

    Create ML-ready features in:
        btc_ml_features

Important:
    btc_price_history is NEVER modified.

Target:
    target_return = next day's percentage return

Example:
    Sep 3 close = 100,000
    Sep 4 close = 102,000

    Sep 3 target_return = 0.02

Latest candle:
    If Sep 4 is the latest available candle and Sep 5
    does not exist yet:

        Sep 4 target_return = NULL
        Sep 4 target_direction = NULL

    Sep 4 is STILL kept because its features are required
    to predict Sep 5.
"""

import mysql.connector
from mysql.connector import Error

import pandas as pd
import numpy as np

from dotenv import load_dotenv
import os
import logging


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

DB_USER = os.getenv("db_user")
DB_PASSWORD = os.getenv("db_password")
DB_HOST = os.getenv("db_host")
DB_NAME = os.getenv("db_name")


if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
    raise ValueError(
        "❌ .env file mein db_user, db_password, db_host ya db_name missing hain!"
    )


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    try:

        conn = mysql.connector.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

        logger.info("✅ Connected to MySQL")

        return conn

    except Error as e:

        logger.error(
            f"❌ Database connection failed: {e}"
        )

        raise


# ============================================================
# LOAD RAW DATA
# ============================================================

def load_raw_data(conn):

    query = """
        SELECT
            date,
            open,
            high,
            low,
            close,
            volume
        FROM btc_price_history
        ORDER BY date ASC
    """

    logger.info(
        "📥 Loading BTC OHLCV data..."
    )

    df = pd.read_sql(
        query,
        conn
    )

    if df.empty:

        raise ValueError(
            "❌ btc_price_history table mein koi data nahi hai!"
        )

    logger.info(
        f"✅ Loaded {len(df):,} OHLCV records"
    )

    logger.info(
        f"📅 Raw data range: "
        f"{df['date'].min()} → {df['date'].max()}"
    )

    return df


# ============================================================
# FEATURE ENGINEERING
# ============================================================

def create_features(df):

    logger.info(
        "⚙️ Creating ML features..."
    )

    df = df.copy()

    # --------------------------------------------------------
    # BASIC CLEANING
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"]
    )

    df = df.sort_values(
        "date"
    )

    df = df.drop_duplicates(
        subset=["date"],
        keep="last"
    )

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for col in numeric_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # Remove rows where raw OHLCV is incomplete
    df = df.dropna(
        subset=numeric_columns
    ).copy()

    # --------------------------------------------------------
    # 1. RETURNS
    # --------------------------------------------------------

    df["return_1d"] = (
        df["close"].pct_change(1)
    )

    df["return_3d"] = (
        df["close"].pct_change(3)
    )

    df["return_7d"] = (
        df["close"].pct_change(7)
    )

    df["return_14d"] = (
        df["close"].pct_change(14)
    )

    df["return_30d"] = (
        df["close"].pct_change(30)
    )

    # --------------------------------------------------------
    # 2. PRICE CHANGE
    # --------------------------------------------------------

    df["price_change"] = (
        df["close"] - df["open"]
    )

    df["price_change_pct"] = (
        (df["close"] - df["open"])
        / df["open"]
    )

    # --------------------------------------------------------
    # 3. CANDLE FEATURES
    # --------------------------------------------------------

    df["candle_body"] = (
        df["close"] - df["open"]
    )

    df["candle_body_pct"] = (
        (df["close"] - df["open"])
        / df["open"]
    )

    df["upper_wick"] = (
        df["high"]
        - df[["open", "close"]].max(axis=1)
    )

    df["lower_wick"] = (
        df[["open", "close"]].min(axis=1)
        - df["low"]
    )

    df["upper_wick_pct"] = (
        df["upper_wick"]
        / df["close"]
    )

    df["lower_wick_pct"] = (
        df["lower_wick"]
        / df["close"]
    )

    # --------------------------------------------------------
    # 4. DAILY RANGE
    # --------------------------------------------------------

    df["daily_range"] = (
        df["high"] - df["low"]
    )

    df["daily_range_pct"] = (
        (df["high"] - df["low"])
        / df["close"]
    )

    # --------------------------------------------------------
    # 5. SIMPLE MOVING AVERAGES
    # --------------------------------------------------------

    df["sma_7"] = (
        df["close"].rolling(7).mean()
    )

    df["sma_14"] = (
        df["close"].rolling(14).mean()
    )

    df["sma_30"] = (
        df["close"].rolling(30).mean()
    )

    df["sma_50"] = (
        df["close"].rolling(50).mean()
    )

    df["sma_100"] = (
        df["close"].rolling(100).mean()
    )

    df["sma_200"] = (
        df["close"].rolling(200).mean()
    )

    # --------------------------------------------------------
    # 6. EXPONENTIAL MOVING AVERAGES
    # --------------------------------------------------------

    df["ema_12"] = (
        df["close"]
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    df["ema_26"] = (
        df["close"]
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

    df["ema_50"] = (
        df["close"]
        .ewm(
            span=50,
            adjust=False
        )
        .mean()
    )

    # --------------------------------------------------------
    # 7. RSI
    # --------------------------------------------------------

    delta = df["close"].diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = (
        gain.rolling(14).mean()
    )

    avg_loss = (
        loss.rolling(14).mean()
    )

    rs = (
        avg_gain / avg_loss
    )

    df["rsi_14"] = (
        100 - (100 / (1 + rs))
    )

    # --------------------------------------------------------
    # 8. ROC
    # --------------------------------------------------------

    df["roc_7"] = (
        df["close"].pct_change(7)
        * 100
    )

    df["roc_14"] = (
        df["close"].pct_change(14)
        * 100
    )

    # --------------------------------------------------------
    # 9. VOLATILITY
    # --------------------------------------------------------

    df["volatility_7"] = (
        df["return_1d"]
        .rolling(7)
        .std()
    )

    df["volatility_14"] = (
        df["return_1d"]
        .rolling(14)
        .std()
    )

    df["volatility_30"] = (
        df["return_1d"]
        .rolling(30)
        .std()
    )

    # --------------------------------------------------------
    # 10. VOLUME FEATURES
    # --------------------------------------------------------

    df["volume_change"] = (
        df["volume"].pct_change()
    )

    df["volume_sma_7"] = (
        df["volume"]
        .rolling(7)
        .mean()
    )

    df["volume_sma_30"] = (
        df["volume"]
        .rolling(30)
        .mean()
    )

    df["volume_ratio"] = (
        df["volume"]
        / df["volume_sma_7"]
    )

    # --------------------------------------------------------
    # 11. TREND RATIOS
    # --------------------------------------------------------

    df["sma_7_30_ratio"] = (
        df["sma_7"]
        / df["sma_30"]
    )

    df["sma_30_200_ratio"] = (
        df["sma_30"]
        / df["sma_200"]
    )

    # --------------------------------------------------------
    # 12. BOLLINGER BANDS
    # --------------------------------------------------------

    bb_middle = (
        df["close"]
        .rolling(20)
        .mean()
    )

    bb_std = (
        df["close"]
        .rolling(20)
        .std()
    )

    df["bb_middle"] = bb_middle

    df["bb_upper"] = (
        bb_middle
        + (2 * bb_std)
    )

    df["bb_lower"] = (
        bb_middle
        - (2 * bb_std)
    )

    df["bb_width"] = (
        (df["bb_upper"] - df["bb_lower"])
        / df["bb_middle"]
    )

    df["bb_position"] = (
        (df["close"] - df["bb_lower"])
        / (
            df["bb_upper"]
            - df["bb_lower"]
        )
    )

    # --------------------------------------------------------
    # 13. ATR
    # --------------------------------------------------------

    previous_close = (
        df["close"].shift(1)
    )

    tr1 = (
        df["high"] - df["low"]
    )

    tr2 = (
        df["high"] - previous_close
    ).abs()

    tr3 = (
        df["low"] - previous_close
    ).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    df["atr_14"] = (
        true_range
        .rolling(14)
        .mean()
    )

    # --------------------------------------------------------
    # 14. MACD
    # --------------------------------------------------------

    ema_12 = (
        df["close"]
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema_26 = (
        df["close"]
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

    df["macd"] = (
        ema_12 - ema_26
    )

    df["macd_signal"] = (
        df["macd"]
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    df["macd_hist"] = (
        df["macd"]
        - df["macd_signal"]
    )

    # ========================================================
    # 15. TARGET
    # ========================================================

    df["target_return"] = (
        df["close"].shift(-1)
        / df["close"]
        - 1
    )

    # ========================================================
    # 16. TARGET DIRECTION
    # ========================================================

    # IMPORTANT:
    # Do NOT convert unknown latest target to 0.
    #
    # If target_return is NaN:
    # target_direction must remain NaN.

    df["target_direction"] = np.where(
        df["target_return"].notna(),
        np.where(
            df["target_return"] > 0,
            1,
            0
        ),
        np.nan
    )

    # ========================================================
    # CLEAN INF
    # ========================================================

    df = df.replace(
        [np.inf, -np.inf],
        np.nan
    )

    # ========================================================
    # FEATURE COLUMNS
    # ========================================================

    feature_columns = [

        "return_1d",
        "return_3d",
        "return_7d",
        "return_14d",
        "return_30d",

        "price_change",
        "price_change_pct",

        "candle_body",
        "candle_body_pct",

        "upper_wick",
        "lower_wick",

        "upper_wick_pct",
        "lower_wick_pct",

        "daily_range",
        "daily_range_pct",

        "sma_7",
        "sma_14",
        "sma_30",
        "sma_50",
        "sma_100",
        "sma_200",

        "ema_12",
        "ema_26",
        "ema_50",

        "rsi_14",

        "roc_7",
        "roc_14",

        "volatility_7",
        "volatility_14",
        "volatility_30",

        "volume_change",
        "volume_sma_7",
        "volume_sma_30",
        "volume_ratio",

        "sma_7_30_ratio",
        "sma_30_200_ratio",

        "bb_middle",
        "bb_upper",
        "bb_lower",
        "bb_width",
        "bb_position",

        "atr_14",

        "macd",
        "macd_signal",
        "macd_hist"
    ]

    # ========================================================
    # DROP ONLY ROWS WITH INVALID FEATURES
    # ========================================================

    before = len(df)

    df = df.dropna(
        subset=feature_columns
    ).copy()

    after = len(df)

    logger.info(
        f"🧹 Removed {before - after:,} rows "
        f"due to insufficient feature history."
    )

    # ========================================================
    # LATEST ROW INFORMATION
    # ========================================================

    if df.empty:

        raise ValueError(
            "❌ No valid feature rows remain."
        )

    latest_row = df.iloc[-1]

    logger.info(
        "================================================"
    )

    logger.info(
        f"📅 Latest feature date: "
        f"{latest_row['date'].date()}"
    )

    logger.info(
        f"💰 Latest close: "
        f"{float(latest_row['close']):,.2f}"
    )

    if pd.isna(
        latest_row["target_return"]
    ):

        logger.info(
            "🎯 Latest target_return: NULL "
            "(expected - next day not available yet)"
        )

    else:

        logger.info(
            f"🎯 Latest target_return: "
            f"{float(latest_row['target_return']):+.6%}"
        )

    logger.info(
        f"✅ Final ML feature dataset: "
        f"{len(df):,} rows"
    )

    logger.info(
        "================================================"
    )

    return df


# ============================================================
# CREATE ML TABLE
# ============================================================

def create_ml_table(conn):

    logger.info(
        "🗄️ Creating btc_ml_features table..."
    )

    cursor = conn.cursor()

    cursor.execute(
        "DROP TABLE IF EXISTS btc_ml_features"
    )

    create_query = """
        CREATE TABLE btc_ml_features (

            date DATE PRIMARY KEY,

            open DECIMAL(20, 8),
            high DECIMAL(20, 8),
            low DECIMAL(20, 8),
            close DECIMAL(20, 8),
            volume BIGINT,

            return_1d DOUBLE,
            return_3d DOUBLE,
            return_7d DOUBLE,
            return_14d DOUBLE,
            return_30d DOUBLE,

            price_change DOUBLE,
            price_change_pct DOUBLE,

            candle_body DOUBLE,
            candle_body_pct DOUBLE,

            upper_wick DOUBLE,
            lower_wick DOUBLE,

            upper_wick_pct DOUBLE,
            lower_wick_pct DOUBLE,

            daily_range DOUBLE,
            daily_range_pct DOUBLE,

            sma_7 DOUBLE,
            sma_14 DOUBLE,
            sma_30 DOUBLE,
            sma_50 DOUBLE,
            sma_100 DOUBLE,
            sma_200 DOUBLE,

            ema_12 DOUBLE,
            ema_26 DOUBLE,
            ema_50 DOUBLE,

            rsi_14 DOUBLE,

            roc_7 DOUBLE,
            roc_14 DOUBLE,

            volatility_7 DOUBLE,
            volatility_14 DOUBLE,
            volatility_30 DOUBLE,

            volume_change DOUBLE,
            volume_sma_7 DOUBLE,
            volume_sma_30 DOUBLE,
            volume_ratio DOUBLE,

            sma_7_30_ratio DOUBLE,
            sma_30_200_ratio DOUBLE,

            bb_middle DOUBLE,
            bb_upper DOUBLE,
            bb_lower DOUBLE,
            bb_width DOUBLE,
            bb_position DOUBLE,

            atr_14 DOUBLE,

            macd DOUBLE,
            macd_signal DOUBLE,
            macd_hist DOUBLE,

            target_return DOUBLE NULL,
            target_direction TINYINT NULL

        )
    """

    cursor.execute(
        create_query
    )

    conn.commit()

    cursor.close()

    logger.info(
        "✅ btc_ml_features table created"
    )


# ============================================================
# STORE FEATURES
# ============================================================

def store_features(conn, df):

    logger.info(
        "💾 Storing ML features..."
    )

    cursor = conn.cursor()

    columns = [

        "date",

        "open",
        "high",
        "low",
        "close",
        "volume",

        "return_1d",
        "return_3d",
        "return_7d",
        "return_14d",
        "return_30d",

        "price_change",
        "price_change_pct",

        "candle_body",
        "candle_body_pct",

        "upper_wick",
        "lower_wick",

        "upper_wick_pct",
        "lower_wick_pct",

        "daily_range",
        "daily_range_pct",

        "sma_7",
        "sma_14",
        "sma_30",
        "sma_50",
        "sma_100",
        "sma_200",

        "ema_12",
        "ema_26",
        "ema_50",

        "rsi_14",

        "roc_7",
        "roc_14",

        "volatility_7",
        "volatility_14",
        "volatility_30",

        "volume_change",
        "volume_sma_7",
        "volume_sma_30",
        "volume_ratio",

        "sma_7_30_ratio",
        "sma_30_200_ratio",

        "bb_middle",
        "bb_upper",
        "bb_lower",
        "bb_width",
        "bb_position",

        "atr_14",

        "macd",
        "macd_signal",
        "macd_hist",

        "target_return",
        "target_direction"
    ]

    placeholders = ", ".join(
        ["%s"] * len(columns)
    )

    column_names = ", ".join(
        columns
    )

    query = f"""
        INSERT INTO btc_ml_features
        ({column_names})
        VALUES ({placeholders})
    """

    data = []

    for _, row in df.iterrows():

        values = []

        for column in columns:

            value = row[column]

            if column == "date":

                value = value.date()

            elif pd.isna(value):

                value = None

            elif isinstance(
                value,
                (np.integer,)
            ):

                value = int(value)

            elif isinstance(
                value,
                (np.floating,)
            ):

                value = float(value)

            values.append(value)

        data.append(
            tuple(values)
        )

    cursor.executemany(
        query,
        data
    )

    conn.commit()

    cursor.close()

    logger.info(
        f"✅ Stored {len(data):,} ML records"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    logger.info(
        "🚀 Starting BTC ML feature preparation..."
    )

    conn = None

    try:

        conn = get_connection()

        df = load_raw_data(
            conn
        )

        ml_df = create_features(
            df
        )

        create_ml_table(
            conn
        )

        store_features(
            conn,
            ml_df
        )

        logger.info(
            "========================================"
        )

        logger.info(
            "🎉 ML DATA PREPARATION COMPLETED!"
        )

        logger.info(
            f"📊 Original records: "
            f"{len(df):,}"
        )

        logger.info(
            f"📊 ML records: "
            f"{len(ml_df):,}"
        )

        logger.info(
            f"📅 ML latest date: "
            f"{ml_df['date'].max().date()}"
        )

        latest_target = ml_df.iloc[-1][
            "target_return"
        ]

        if pd.isna(latest_target):

            logger.info(
                "🎯 Latest row target: NULL "
                "→ ready for next-day prediction"
            )

        logger.info(
            "🗄️ Original table: btc_price_history"
        )

        logger.info(
            "🗄️ ML table: btc_ml_features"
        )

        logger.info(
            "========================================"
        )

    except Exception as e:

        logger.error(
            f"❌ Process failed: {e}"
        )

        if conn:

            conn.rollback()

        raise

    finally:

        if conn and conn.is_connected():

            conn.close()

            logger.info(
                "🔒 Database connection closed"
            )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()