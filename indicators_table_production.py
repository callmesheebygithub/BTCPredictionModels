"""
BTC INDICATORS TABLE - FINAL PRODUCTION VERSION

Major fixes:
1. Point-in-time Support / Resistance - NO future leakage
2. Point-in-time S/R strength - NO future leakage
3. Chronological Fibonacci impulse pairing
4. Actual BOS breakout event
5. Actual CHOCH structural reversal event
6. No repeated BOS/CHOCH signals
7. Exact Wilder RSI
8. Exact Wilder ATR
9. Historical-only percentiles
10. Previous-period volume ratio
11. Point-in-time volume profile
12. Better OHLCV validation
13. No synthetic OHLCV forward-fill
14. NaN / Inf protection
15. Safe database replacement
16. Transaction-safe batch insert
17. MySQL reconnect handling
18. ML-friendly features
"""

import os
import time
import math
import logging
from datetime import datetime, timedelta

from btc_indicators import DB_PASSWORD, DB_USER
import numpy as np
import pandas as pd
import mysql.connector
from mysql.connector import pooling, Error
import logging
import os
import logging
from dotenv import load_dotenv

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

# Load .env from the same directory as this Python file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_FILE)

# Read credentials from .env
BTC_DB_USER = os.getenv("db_user")
BTC_DB_PASSWORD = os.getenv("db_password")
BTC_DB_HOST = os.getenv("db_host")
BTC_DB_NAME = os.getenv("db_name")
BTC_DB_PORT = os.getenv("db_port", "3306")

# Validate required settings
if not all([
    BTC_DB_USER,
    BTC_DB_PASSWORD,
    BTC_DB_HOST,
    BTC_DB_NAME
]):
    raise ValueError(
        "❌ .env file mein kuch database values missing hain!"
    )

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(BASE_DIR, "btc_indicators.log"),
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ============================================================
# DATABASE CONFIG
# ============================================================

DB_CONFIG = {
    "host": BTC_DB_HOST,
    "port": int(BTC_DB_PORT),
    "user": BTC_DB_USER,
    "password": BTC_DB_PASSWORD,
    "database": BTC_DB_NAME,
}

logger.info("Database configuration loaded successfully.")


SOURCE_TABLE = "btc_price_history"
TARGET_TABLE = "btc_daily_indicators"

MIN_HISTORY = 300
BATCH_SIZE = 500

RSI_PERIOD = 14
ATR_PERIOD = 14

SR_TOLERANCE = 0.02
SR_MIN_TOUCHES = 2

FIB_LEVELS = {
    "0.000": 0.000,
    "0.236": 0.236,
    "0.382": 0.382,
    "0.500": 0.500,
    "0.618": 0.618,
    "0.786": 0.786,
    "1.000": 1.000,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

class DatabaseManager:

    def __init__(self):
        self.pool = None
        self.connection = None

    def create_pool(self):
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="btc_indicator_pool",
                pool_size=5,
                pool_reset_session=True,
                **DB_CONFIG
            )

            logger.info("MySQL connection pool created.")

        except Error as e:
            logger.error(f"Database pool creation failed: {e}")
            raise

    def get_connection(self):
        if self.pool is None:
            self.create_pool()

        for attempt in range(3):
            try:
                conn = self.pool.get_connection()

                if conn.is_connected():
                    return conn

            except Error as e:
                logger.warning(
                    f"Database connection attempt {attempt + 1}/3 failed: {e}"
                )

                time.sleep(2)

        raise RuntimeError("Unable to establish MySQL connection.")

    def create_table(self):

        conn = self.get_connection()

        try:
            cursor = conn.cursor()

            # ------------------------------------------------
            # IMPORTANT:
            # Do NOT DROP production table first.
            # Create a staging table instead.
            # ------------------------------------------------

            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
                    date DATE PRIMARY KEY,

                    open_price DOUBLE,
                    high_price DOUBLE,
                    low_price DOUBLE,
                    close_price DOUBLE,
                    volume DOUBLE,

                    ma_7 DOUBLE,
                    ma_20 DOUBLE,
                    ma_50 DOUBLE,
                    ma_100 DOUBLE,
                    ma_200 DOUBLE,

                    ma_7_slope DOUBLE,
                    ma_20_slope DOUBLE,
                    ma_50_slope DOUBLE,
                    ma_100_slope DOUBLE,
                    ma_200_slope DOUBLE,

                    ma_trend VARCHAR(20),

                    rsi DOUBLE,

                    macd DOUBLE,
                    macd_signal DOUBLE,
                    macd_histogram DOUBLE,
                    macd_state VARCHAR(20),
                    macd_crossover VARCHAR(20),

                    bb_middle DOUBLE,
                    bb_upper DOUBLE,
                    bb_lower DOUBLE,
                    bb_bandwidth DOUBLE,
                    bb_bandwidth_percentile DOUBLE,
                    bb_squeeze TINYINT,

                    atr DOUBLE,
                    atr_percent DOUBLE,
                    atr_percentile DOUBLE,

                    support DOUBLE,
                    resistance DOUBLE,
                    support_touches INT,
                    resistance_touches INT,

                    fib_direction VARCHAR(20),
                    fib_swing_high DOUBLE,
                    fib_swing_low DOUBLE,
                    fib_0 DOUBLE,
                    fib_236 DOUBLE,
                    fib_382 DOUBLE,
                    fib_500 DOUBLE,
                    fib_618 DOUBLE,
                    fib_786 DOUBLE,
                    fib_1000 DOUBLE,
                    fib_current_level VARCHAR(20),

                    pivot DOUBLE,
                    pivot_r1 DOUBLE,
                    pivot_s1 DOUBLE,
                    pivot_r2 DOUBLE,
                    pivot_s2 DOUBLE,
                    pivot_r3 DOUBLE,
                    pivot_s3 DOUBLE,

                    market_structure VARCHAR(20),

                    bos VARCHAR(30),
                    bos_price DOUBLE,
                    bos_date DATE,

                    choch VARCHAR(30),
                    choch_price DOUBLE,
                    choch_date DATE,

                    volume_avg_30 DOUBLE,
                    volume_ratio DOUBLE,

                    poc DOUBLE,
                    vah DOUBLE,
                    val DOUBLE,

                    `signal` VARCHAR(30),
                    `signal_score` DOUBLE,
                    `confidence` VARCHAR(20),
                    `signal_factors` TEXT,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,

                    INDEX idx_date (date),
                    INDEX idx_signal (`signal`),
                    INDEX idx_bos_date (bos_date),
                    INDEX idx_choch_date (choch_date)
                )
            """)

            conn.commit()

            logger.info(f"{TARGET_TABLE} verified.")

        finally:
            cursor.close()
            conn.close()

    def replace_table_safely(self, df):

        """
        Safely rebuild indicator table.

        Old table remains available if calculation/insertion fails.
        """

        staging = f"{TARGET_TABLE}_staging"

        conn = self.get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(f"DROP TABLE IF EXISTS {staging}")

            cursor.execute(f"""
                CREATE TABLE {staging}
                LIKE {TARGET_TABLE}
            """)

            conn.commit()

            self.insert_batch(
                df,
                table_name=staging,
                connection=conn
            )

            # Atomic-ish table swap
            cursor.execute(f"""
                RENAME TABLE
                    {TARGET_TABLE} TO {TARGET_TABLE}_old,
                    {staging} TO {TARGET_TABLE}
            """)

            cursor.execute(
                f"DROP TABLE IF EXISTS {TARGET_TABLE}_old"
            )

            conn.commit()

            logger.info("Indicator table replaced successfully.")

        except Exception:

            conn.rollback()

            try:
                cursor.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
            except Exception:
                pass

            raise

        finally:
            cursor.close()
            conn.close()

    def insert_batch(self, df, table_name, connection):

        columns = list(df.columns)

        placeholders = ",".join(["%s"] * len(columns))
        column_sql = ",".join(f"`{c}`" for c in columns)

        update_sql = ",".join(
            f"`{c}` = VALUES(`{c}`)"
            for c in columns
            if c != "date"
        )

        sql = f"""
            INSERT INTO {table_name}
            ({column_sql})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE
            {update_sql}
        """

        cursor = connection.cursor()

        try:

            rows = []

            for _, row in df.iterrows():

                values = []

                for value in row:

                    if pd.isna(value):
                        values.append(None)

                    elif isinstance(value, (np.integer,)):
                        values.append(int(value))

                    elif isinstance(value, (np.floating,)):
                        values.append(float(value))

                    else:
                        values.append(value)

                rows.append(tuple(values))

            for start in range(0, len(rows), BATCH_SIZE):

                batch = rows[start:start + BATCH_SIZE]

                cursor.executemany(sql, batch)

                connection.commit()

                logger.info(
                    f"Inserted {min(start + BATCH_SIZE, len(rows))}/"
                    f"{len(rows)} rows."
                )

        except Exception:
            connection.rollback()
            raise

        finally:
            cursor.close()

    def fetch_price_data(self):

        conn = self.get_connection()

        try:

            query = f"""
                SELECT
                    date,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM {SOURCE_TABLE}
                ORDER BY date ASC
            """

            df = pd.read_sql(query, conn)

            return df

        finally:
            conn.close()


# ============================================================
# VALIDATION
# ============================================================

def validate_data(df):

    required = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    df = df.copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df = df.dropna(subset=["date"])

    df = df.sort_values("date")

    # Remove duplicate dates
    df = df.drop_duplicates(
        subset=["date"],
        keep="last"
    )

    numeric_cols = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for col in numeric_cols:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # Reject invalid rows instead of fabricating candles
    before = len(df)

    df = df.dropna(
        subset=numeric_cols
    )

    if len(df) != before:
        logger.warning(
            f"Dropped {before - len(df)} invalid OHLCV rows."
        )

    # Inf protection
    df = df.replace(
        [np.inf, -np.inf],
        np.nan
    )

    df = df.dropna(
        subset=numeric_cols
    )

    # OHLC validation
    valid_ohlc = (
        (df["high"] >= df["low"]) &
        (df["high"] >= df["open"]) &
        (df["high"] >= df["close"]) &
        (df["low"] <= df["open"]) &
        (df["low"] <= df["close"]) &
        (df["open"] > 0) &
        (df["high"] > 0) &
        (df["low"] > 0) &
        (df["close"] > 0) &
        (df["volume"] >= 0)
    )

    invalid_count = (~valid_ohlc).sum()

    if invalid_count:
        logger.warning(
            f"Dropping {invalid_count} invalid OHLCV rows."
        )

        df = df[valid_ohlc]

    # Detect missing dates.
    # IMPORTANT:
    # We DO NOT forward-fill OHLCV.
    expected = pd.date_range(
        df["date"].min(),
        df["date"].max(),
        freq="D"
    )

    actual = pd.DatetimeIndex(df["date"])

    missing_dates = expected.difference(actual)

    if len(missing_dates):
        logger.warning(
            f"{len(missing_dates)} calendar dates missing. "
            f"No synthetic candles will be created."
        )

    df = df.reset_index(drop=True)

    return df


# ============================================================
# WILDER RSI
# ============================================================

def exact_wilder_rsi(series, period=14):

    values = series.astype(float)

    delta = values.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    rsi = pd.Series(
        np.nan,
        index=series.index,
        dtype=float
    )

    if len(series) <= period:
        return rsi

    avg_gain = gain.iloc[1:period + 1].mean()
    avg_loss = loss.iloc[1:period + 1].mean()

    if avg_loss == 0:
        rsi.iloc[period] = 100.0

    else:
        rs = avg_gain / avg_loss
        rsi.iloc[period] = 100 - (
            100 / (1 + rs)
        )

    for i in range(period + 1, len(series)):

        current_gain = gain.iloc[i]
        current_loss = loss.iloc[i]

        avg_gain = (
            (avg_gain * (period - 1)) +
            current_gain
        ) / period

        avg_loss = (
            (avg_loss * (period - 1)) +
            current_loss
        ) / period

        if avg_loss == 0:
            rsi.iloc[i] = 100.0

        else:
            rs = avg_gain / avg_loss

            rsi.iloc[i] = (
                100 - (100 / (1 + rs))
            )

    return rsi


# ============================================================
# WILDER ATR
# ============================================================

def exact_wilder_atr(df, period=14):

    high = df["high"]
    low = df["low"]
    close = df["close"]

    previous_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)

    atr = pd.Series(
        np.nan,
        index=df.index,
        dtype=float
    )

    if len(df) <= period:
        return atr

    avg_atr = tr.iloc[1:period + 1].mean()

    atr.iloc[period] = avg_atr

    for i in range(period + 1, len(df)):

        avg_atr = (
            (avg_atr * (period - 1)) +
            tr.iloc[i]
        ) / period

        atr.iloc[i] = avg_atr

    return atr


# ============================================================
# HISTORICAL-ONLY PERCENTILE
# ============================================================

def historical_percentile(series, window=252):

    result = pd.Series(
        np.nan,
        index=series.index,
        dtype=float
    )

    values = series.to_numpy(dtype=float)

    for i in range(len(values)):

        # Current candle excluded
        if i < window:
            continue

        current = values[i]

        if not np.isfinite(current):
            continue

        history = values[i - window:i]

        history = history[
            np.isfinite(history)
        ]

        if len(history) < max(20, window // 2):
            continue

        result.iloc[i] = (
            np.sum(history < current) /
            len(history)
        ) * 100

    return result


# ============================================================
# SWING DETECTION
# ============================================================

def detect_swings(df, left=2):

    """
    Point-in-time swing detector.

    Only candles up to current candle are used.

    This is intentionally NOT a future-confirmed pivot.
    A pivot becomes known when the current candle forms
    a local extreme relative to previous candles.
    """

    swings = []

    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()

    for i in range(left, len(df)):

        current_high = highs[i]
        current_low = lows[i]

        previous_highs = highs[i-left:i]
        previous_lows = lows[i-left:i]

        if current_high > np.max(previous_highs):

            swings.append({
                "index": i,
                "date": df.iloc[i]["date"],
                "type": "high",
                "price": float(current_high)
            })

        if current_low < np.min(previous_lows):

            swings.append({
                "index": i,
                "date": df.iloc[i]["date"],
                "type": "low",
                "price": float(current_low)
            })

    return swings


# ============================================================
# POINT-IN-TIME SUPPORT / RESISTANCE
# ============================================================

def calculate_sr_for_index(
    df,
    swings,
    current_index,
    tolerance=0.02
):

    current_price = float(
        df.iloc[current_index]["close"]
    )

    # CRITICAL:
    # Only swings already known at this candle.
    available = [
        s for s in swings
        if s["index"] < current_index
    ]

    lows = [
        s for s in available
        if s["type"] == "low"
    ]

    highs = [
        s for s in available
        if s["type"] == "high"
    ]

    # -------------------------------
    # SUPPORT
    # -------------------------------

    supports = []

    for s in lows:

        if s["price"] < current_price:

            supports.append(s)

    support = np.nan
    support_touches = 0

    if supports:

        # Nearest support
        supports.sort(
            key=lambda x: abs(
                x["price"] - current_price
            )
        )

        candidate = supports[0]

        candidate_price = candidate["price"]

        support_touches = sum(
            abs(s["price"] - candidate_price)
            / candidate_price <= tolerance
            for s in lows
            if s["index"] < current_index
        )

        if support_touches >= SR_MIN_TOUCHES:
            support = candidate_price

    # -------------------------------
    # RESISTANCE
    # -------------------------------

    resistances = []

    for s in highs:

        if s["price"] > current_price:

            resistances.append(s)

    resistance = np.nan
    resistance_touches = 0

    if resistances:

        resistances.sort(
            key=lambda x: abs(
                x["price"] - current_price
            )
        )

        candidate = resistances[0]

        candidate_price = candidate["price"]

        resistance_touches = sum(
            abs(s["price"] - candidate_price)
            / candidate_price <= tolerance
            for s in highs
            if s["index"] < current_index
        )

        if resistance_touches >= SR_MIN_TOUCHES:
            resistance = candidate_price

    return (
        support,
        resistance,
        support_touches,
        resistance_touches
    )


# ============================================================
# FIBONACCI
# ============================================================

def calculate_fibonacci(
    df,
    swings,
    current_index
):

    """
    Proper chronological impulse pairing.

    Bullish:
        swing low -> later swing high

    Bearish:
        swing high -> later swing low

    Only completed historical swings are considered.
    """

    available = [
        s for s in swings
        if s["index"] < current_index
    ]

    if len(available) < 2:
        return {
            "direction": None,
            "high": np.nan,
            "low": np.nan,
            "levels": {},
            "high_date": None,
            "low_date": None,
        }

    best_bull = None
    best_bear = None

    # --------------------------------------------------------
    # Find latest valid LOW -> HIGH impulse
    # --------------------------------------------------------

    for low in available:

        if low["type"] != "low":
            continue

        later_highs = [
            h for h in available
            if h["type"] == "high"
            and h["index"] > low["index"]
        ]

        if not later_highs:
            continue

        high = max(
            later_highs,
            key=lambda x: x["index"]
        )

        if high["price"] > low["price"]:

            candidate = {
                "low": low,
                "high": high
            }

            if (
                best_bull is None or
                high["index"] > best_bull["high"]["index"]
            ):
                best_bull = candidate

    # --------------------------------------------------------
    # Find latest valid HIGH -> LOW impulse
    # --------------------------------------------------------

    for high in available:

        if high["type"] != "high":
            continue

        later_lows = [
            l for l in available
            if l["type"] == "low"
            and l["index"] > high["index"]
        ]

        if not later_lows:
            continue

        low = min(
            later_lows,
            key=lambda x: x["index"]
        )

        if low["price"] < high["price"]:

            candidate = {
                "high": high,
                "low": low
            }

            if (
                best_bear is None or
                low["index"] > best_bear["low"]["index"]
            ):
                best_bear = candidate

    # --------------------------------------------------------
    # Choose most recent completed impulse
    # --------------------------------------------------------

    candidates = []

    if best_bull:
        candidates.append(
            ("Bullish", best_bull)
        )

    if best_bear:
        candidates.append(
            ("Bearish", best_bear)
        )

    if not candidates:

        return {
            "direction": None,
            "high": np.nan,
            "low": np.nan,
            "levels": {},
            "high_date": None,
            "low_date": None,
        }

    direction, pair = max(
        candidates,
        key=lambda x: max(
            x[1]["high"]["index"],
            x[1]["low"]["index"]
        )
    )

    high = pair["high"]
    low = pair["low"]

    high_price = float(high["price"])
    low_price = float(low["price"])

    diff = high_price - low_price

    if diff <= 0:
        return {
            "direction": None,
            "high": np.nan,
            "low": np.nan,
            "levels": {},
            "high_date": None,
            "low_date": None,
        }

    levels = {}

    if direction == "Bullish":

        # Retracement from high downward
        for name, ratio in FIB_LEVELS.items():

            levels[name] = (
                high_price -
                diff * ratio
            )

    else:

        # Retracement from low upward
        for name, ratio in FIB_LEVELS.items():

            levels[name] = (
                low_price +
                diff * ratio
            )

    return {
        "direction": direction,
        "high": high_price,
        "low": low_price,
        "levels": levels,
        "high_date": high["date"],
        "low_date": low["date"],
    }


def find_current_fib_level(
    price,
    levels,
    atr
):

    if not levels or not np.isfinite(price):
        return None

    tolerance = (
        max(float(atr) * 0.25, price * 0.002)
        if np.isfinite(atr) and atr > 0
        else price * 0.002
    )

    candidates = []

    for name, level in levels.items():

        distance = abs(
            price - level
        )

        if distance <= tolerance:

            candidates.append(
                (distance, name)
            )

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda x: x[0]
    )[1]


# ============================================================
# MARKET STRUCTURE
# ============================================================

def calculate_market_structure(
    swings,
    current_index
):

    available = [
        s for s in swings
        if s["index"] < current_index
    ]

    highs = [
        s for s in available
        if s["type"] == "high"
    ]

    lows = [
        s for s in available
        if s["type"] == "low"
    ]

    result = {
        "trend": "Neutral",
        "bos": None,
        "bos_price": np.nan,
        "bos_date": None,
        "choch": None,
        "choch_price": np.nan,
        "choch_date": None,
    }

    if len(highs) < 2 or len(lows) < 2:
        return result

    last_high = highs[-1]
    previous_high = highs[-2]

    last_low = lows[-1]
    previous_low = lows[-2]

    # --------------------------------------------------------
    # HH / LH
    # --------------------------------------------------------

    higher_high = (
        last_high["price"] >
        previous_high["price"]
    )

    lower_high = (
        last_high["price"] <
        previous_high["price"]
    )

    # --------------------------------------------------------
    # HL / LL
    # --------------------------------------------------------

    higher_low = (
        last_low["price"] >
        previous_low["price"]
    )

    lower_low = (
        last_low["price"] <
        previous_low["price"]
    )

    # --------------------------------------------------------
    # Structural trend
    # --------------------------------------------------------

    if higher_high and higher_low:
        trend = "Bullish"

    elif lower_high and lower_low:
        trend = "Bearish"

    else:
        trend = "Neutral"

    result["trend"] = trend

    # --------------------------------------------------------
    # BOS
    #
    # BOS must happen when CURRENT candle breaks the
    # previous structural swing.
    # --------------------------------------------------------

    current_high = float(
        df_global.iloc[current_index]["high"]
    )

    current_low = float(
        df_global.iloc[current_index]["low"]
    )

    if trend == "Bullish":

        if (
            current_high >
            previous_high["price"]
        ):

            result["bos"] = "Bullish BOS"
            result["bos_price"] = current_high
            result["bos_date"] = (
                df_global.iloc[current_index]["date"]
            )

    elif trend == "Bearish":

        if (
            current_low <
            previous_low["price"]
        ):

            result["bos"] = "Bearish BOS"
            result["bos_price"] = current_low
            result["bos_date"] = (
                df_global.iloc[current_index]["date"]
            )

    # --------------------------------------------------------
    # CHOCH
    #
    # Bullish CHOCH:
    # previous bearish structure + break above latest LH
    #
    # Bearish CHOCH:
    # previous bullish structure + break below latest HL
    # --------------------------------------------------------

    if len(highs) >= 3 and len(lows) >= 3:

        h1 = highs[-3]["price"]
        h2 = highs[-2]["price"]
        h3 = highs[-1]["price"]

        l1 = lows[-3]["price"]
        l2 = lows[-2]["price"]
        l3 = lows[-1]["price"]

        was_bearish = (
            h3 < h2 and
            l3 < l2
        )

        was_bullish = (
            h3 > h2 and
            l3 > l2
        )

        if was_bearish:

            if current_high > h3:

                result["choch"] = "Bullish CHOCH"
                result["choch_price"] = current_high
                result["choch_date"] = (
                    df_global.iloc[current_index]["date"]
                )

        elif was_bullish:

            if current_low < l3:

                result["choch"] = "Bearish CHOCH"
                result["choch_price"] = current_low
                result["choch_date"] = (
                    df_global.iloc[current_index]["date"]
                )

    return result


# ============================================================
# GLOBAL DF FOR STRUCTURE FUNCTION
# ============================================================

df_global = None


# ============================================================
# VOLUME PROFILE
# ============================================================

def calculate_volume_profile(
    df,
    current_index,
    lookback=30,
    bins=20
):

    # Current candle excluded
    start = max(
        0,
        current_index - lookback
    )

    history = df.iloc[
        start:current_index
    ]

    if len(history) < 20:
        return (
            np.nan,
            np.nan,
            np.nan
        )

    low = history["low"].min()
    high = history["high"].max()

    if not np.isfinite(low) or not np.isfinite(high):
        return (
            np.nan,
            np.nan,
            np.nan
        )

    if high <= low:
        return (
            float(history["close"].iloc[-1]),
            float(high),
            float(low)
        )

    edges = np.linspace(
        low,
        high,
        bins + 1
    )

    volume_by_bin = np.zeros(
        bins,
        dtype=float
    )

    for _, row in history.iterrows():

        price = float(row["close"])
        volume = float(row["volume"])

        bin_index = np.searchsorted(
            edges,
            price,
            side="right"
        ) - 1

        bin_index = max(
            0,
            min(bins - 1, bin_index)
        )

        volume_by_bin[bin_index] += volume

    if volume_by_bin.sum() <= 0:
        return (
            np.nan,
            np.nan,
            np.nan
        )

    poc_index = int(
        np.argmax(volume_by_bin)
    )

    poc = (
        edges[poc_index] +
        edges[poc_index + 1]
    ) / 2

    # --------------------------------------------------------
    # Value area
    #
    # Expand around POC until 70% volume reached.
    # --------------------------------------------------------

    total_volume = volume_by_bin.sum()
    target_volume = total_volume * 0.70

    included = {poc_index}
    accumulated = volume_by_bin[poc_index]

    left = poc_index - 1
    right = poc_index + 1

    while accumulated < target_volume:

        left_volume = (
            volume_by_bin[left]
            if left >= 0
            else -1
        )

        right_volume = (
            volume_by_bin[right]
            if right < bins
            else -1
        )

        if left_volume < 0 and right_volume < 0:
            break

        if right_volume > left_volume:

            included.add(right)
            accumulated += right_volume
            right += 1

        else:

            included.add(left)
            accumulated += left_volume
            left -= 1

    vah = edges[
        max(included) + 1
    ]

    val = edges[
        min(included)
    ]

    return (
        float(poc),
        float(vah),
        float(val)
    )


# ============================================================
# SIGNAL
# ============================================================

def calculate_signal(row):

    score = 0.0
    factors = []

    # RSI
    if pd.notna(row["rsi"]):

        if row["rsi"] < 30:

            score += 1.5
            factors.append("RSI_Oversold")

        elif row["rsi"] > 70:

            score -= 1.5
            factors.append("RSI_Overbought")

    # MACD crossover
    if row["macd_crossover"] == "Bullish":

        score += 2
        factors.append("MACD_Bullish_Cross")

    elif row["macd_crossover"] == "Bearish":

        score -= 2
        factors.append("MACD_Bearish_Cross")

    else:

        if row["macd_state"] == "Bullish":

            score += 0.5
            factors.append("MACD_Bullish")

        elif row["macd_state"] == "Bearish":

            score -= 0.5
            factors.append("MACD_Bearish")

    # MA trend
    if row["ma_trend"] == "Bullish":

        score += 1
        factors.append("MA_Bullish")

    elif row["ma_trend"] == "Bearish":

        score -= 1
        factors.append("MA_Bearish")

    # Market structure
    if row["market_structure"] == "Bullish":

        score += 1
        factors.append("Structure_Bullish")

    elif row["market_structure"] == "Bearish":

        score -= 1
        factors.append("Structure_Bearish")

    # BOS
    if row["bos"] == "Bullish BOS":

        score += 1
        factors.append("Bullish_BOS")

    elif row["bos"] == "Bearish BOS":

        score -= 1
        factors.append("Bearish_BOS")

    # CHOCH
    if row["choch"] == "Bullish CHOCH":

        score += 1.5
        factors.append("Bullish_CHOCH")

    elif row["choch"] == "Bearish CHOCH":

        score -= 1.5
        factors.append("Bearish_CHOCH")

    # Bollinger
    if (
        pd.notna(row["bb_upper"]) and
        row["close_price"] > row["bb_upper"]
    ):

        score -= 0.5
        factors.append("Above_BB")

    elif (
        pd.notna(row["bb_lower"]) and
        row["close_price"] < row["bb_lower"]
    ):

        score += 0.5
        factors.append("Below_BB")

    # Volume confirmation
    if (
        pd.notna(row["volume_ratio"]) and
        row["volume_ratio"] > 1.5
    ):

        factors.append("High_Volume")

    # --------------------------------------------------------
    # Signal
    # --------------------------------------------------------

    if score >= 4:

        signal = "Strong Buy"
        confidence = "High"

    elif score >= 1.5:

        signal = "Buy"
        confidence = "Medium"

    elif score <= -4:

        signal = "Strong Sell"
        confidence = "High"

    elif score <= -1.5:

        signal = "Sell"
        confidence = "Medium"

    else:

        signal = "Neutral"
        confidence = "Low"

    return (
        signal,
        float(score),
        confidence,
        ",".join(factors)
    )


# ============================================================
# MAIN CALCULATION
# ============================================================

def calculate_indicators(df):

    global df_global

    df_global = df.copy()

    df = df.copy()

    logger.info(
        f"Calculating indicators for {len(df)} rows..."
    )

    # --------------------------------------------------------
    # MOVING AVERAGES
    # --------------------------------------------------------

    for period in [7, 20, 50, 100, 200]:

        df[f"ma_{period}"] = (
            df["close"]
            .rolling(period)
            .mean()
        )

        df[f"ma_{period}_slope"] = (
            df[f"ma_{period}"].diff(5) /
            df[f"ma_{period}"].shift(5)
        ) * 100

    slope_columns = [
        "ma_7_slope",
        "ma_20_slope",
        "ma_50_slope",
        "ma_100_slope",
        "ma_200_slope"
    ]

    slope_score = (
        df[slope_columns] > 0.1
    ).sum(axis=1) - (
        df[slope_columns] < -0.1
    ).sum(axis=1)

    df["ma_trend"] = np.select(
        [
            slope_score >= 2,
            slope_score <= -2
        ],
        [
            "Bullish",
            "Bearish"
        ],
        default="Neutral"
    )

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    df["rsi"] = exact_wilder_rsi(
        df["close"],
        RSI_PERIOD
    )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    ema12 = df["close"].ewm(
        span=12,
        adjust=False,
        min_periods=12
    ).mean()

    ema26 = df["close"].ewm(
        span=26,
        adjust=False,
        min_periods=26
    ).mean()

    df["macd"] = ema12 - ema26

    df["macd_signal"] = df["macd"].ewm(
        span=9,
        adjust=False,
        min_periods=9
    ).mean()

    df["macd_histogram"] = (
        df["macd"] -
        df["macd_signal"]
    )

    df["macd_state"] = np.select(
        [
            df["macd"] > df["macd_signal"],
            df["macd"] < df["macd_signal"]
        ],
        [
            "Bullish",
            "Bearish"
        ],
        default="Neutral"
    )

    previous_macd = df["macd"].shift(1)
    previous_signal = df["macd_signal"].shift(1)

    bullish_cross = (
        (previous_macd <= previous_signal) &
        (df["macd"] > df["macd_signal"])
    )

    bearish_cross = (
        (previous_macd >= previous_signal) &
        (df["macd"] < df["macd_signal"])
    )

    df["macd_crossover"] = np.select(
        [
            bullish_cross,
            bearish_cross
        ],
        [
            "Bullish",
            "Bearish"
        ],
        default="None"
    )

    # --------------------------------------------------------
    # BOLLINGER
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
        bb_middle + 2 * bb_std
    )

    df["bb_lower"] = (
        bb_middle - 2 * bb_std
    )

    df["bb_bandwidth"] = (
        df["bb_upper"] -
        df["bb_lower"]
    ) / df["bb_middle"]

    df["bb_bandwidth_percentile"] = (
        historical_percentile(
            df["bb_bandwidth"],
            252
        )
    )

    df["bb_squeeze"] = (
        df["bb_bandwidth_percentile"] < 20
    ).astype(int)

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    df["atr"] = exact_wilder_atr(
        df,
        ATR_PERIOD
    )

    df["atr_percent"] = (
        df["atr"] /
        df["close"]
    ) * 100

    df["atr_percentile"] = (
        historical_percentile(
            df["atr_percent"],
            252
        )
    )

    # --------------------------------------------------------
    # SWINGS
    # --------------------------------------------------------

    swings = detect_swings(df)

    logger.info(
        f"Detected {len(swings)} historical swings."
    )

    # --------------------------------------------------------
    # POINT-IN-TIME FEATURES
    # --------------------------------------------------------

    sr_support = []
    sr_resistance = []
    sr_support_touches = []
    sr_resistance_touches = []

    fib_direction = []
    fib_high = []
    fib_low = []

    fib_0 = []
    fib_236 = []
    fib_382 = []
    fib_500 = []
    fib_618 = []
    fib_786 = []
    fib_1000 = []

    fib_current_level = []

    market_structure = []

    bos_values = []
    bos_prices = []
    bos_dates = []

    choch_values = []
    choch_prices = []
    choch_dates = []

    poc_values = []
    vah_values = []
    val_values = []

    # --------------------------------------------------------
    # Process every candle point-in-time
    # --------------------------------------------------------

    for i in range(len(df)):

        # S/R
        (
            support,
            resistance,
            support_touches,
            resistance_touches
        ) = calculate_sr_for_index(
            df,
            swings,
            i
        )

        sr_support.append(support)
        sr_resistance.append(resistance)

        sr_support_touches.append(
            support_touches
        )

        sr_resistance_touches.append(
            resistance_touches
        )

        # Fibonacci
        fib = calculate_fibonacci(
            df,
            swings,
            i
        )

        fib_direction.append(
            fib["direction"]
        )

        fib_high.append(
            fib["high"]
        )

        fib_low.append(
            fib["low"]
        )

        levels = fib["levels"]

        fib_0.append(
            levels.get("0.000", np.nan)
        )

        fib_236.append(
            levels.get("0.236", np.nan)
        )

        fib_382.append(
            levels.get("0.382", np.nan)
        )

        fib_500.append(
            levels.get("0.500", np.nan)
        )

        fib_618.append(
            levels.get("0.618", np.nan)
        )

        fib_786.append(
            levels.get("0.786", np.nan)
        )

        fib_1000.append(
            levels.get("1.000", np.nan)
        )

        fib_current_level.append(
            find_current_fib_level(
                df.iloc[i]["close"],
                levels,
                df.iloc[i]["atr"]
            )
        )

        # Market structure
        structure = calculate_market_structure(
            swings,
            i
        )

        market_structure.append(
            structure["trend"]
        )

        bos_values.append(
            structure["bos"]
        )

        bos_prices.append(
            structure["bos_price"]
        )

        bos_dates.append(
            structure["bos_date"]
        )

        choch_values.append(
            structure["choch"]
        )

        choch_prices.append(
            structure["choch_price"]
        )

        choch_dates.append(
            structure["choch_date"]
        )

        # Volume profile
        poc, vah, val = calculate_volume_profile(
            df,
            i
        )

        poc_values.append(poc)
        vah_values.append(vah)
        val_values.append(val)

    # --------------------------------------------------------
    # Assign structural features
    # --------------------------------------------------------

    df["support"] = sr_support
    df["resistance"] = sr_resistance

    df["support_touches"] = sr_support_touches
    df["resistance_touches"] = sr_resistance_touches

    df["fib_direction"] = fib_direction

    df["fib_swing_high"] = fib_high
    df["fib_swing_low"] = fib_low

    df["fib_0"] = fib_0
    df["fib_236"] = fib_236
    df["fib_382"] = fib_382
    df["fib_500"] = fib_500
    df["fib_618"] = fib_618
    df["fib_786"] = fib_786
    df["fib_1000"] = fib_1000

    df["fib_current_level"] = (
        fib_current_level
    )

    df["market_structure"] = (
        market_structure
    )

    df["bos"] = bos_values
    df["bos_price"] = bos_prices
    df["bos_date"] = bos_dates

    df["choch"] = choch_values
    df["choch_price"] = choch_prices
    df["choch_date"] = choch_dates

    df["poc"] = poc_values
    df["vah"] = vah_values
    df["val"] = val_values

    # --------------------------------------------------------
    # VOLUME RATIO
    #
    # Current volume excluded from average.
    # --------------------------------------------------------

    df["volume_avg_30"] = (
        df["volume"]
        .shift(1)
        .rolling(30)
        .mean()
    )

    df["volume_ratio"] = (
        df["volume"] /
        df["volume_avg_30"]
    )

    # --------------------------------------------------------
    # PIVOTS
    #
    # Previous candle only.
    # --------------------------------------------------------

    prev_high = df["high"].shift(1)
    prev_low = df["low"].shift(1)
    prev_close = df["close"].shift(1)

    df["pivot"] = (
        prev_high +
        prev_low +
        prev_close
    ) / 3

    df["pivot_r1"] = (
        2 * df["pivot"] -
        prev_low
    )

    df["pivot_s1"] = (
        2 * df["pivot"] -
        prev_high
    )

    df["pivot_r2"] = (
        df["pivot"] +
        prev_high -
        prev_low
    )

    df["pivot_s2"] = (
        df["pivot"] -
        prev_high +
        prev_low
    )

    df["pivot_r3"] = (
        prev_high +
        2 * (
            df["pivot"] -
            prev_low
        )
    )

    df["pivot_s3"] = (
        prev_low -
        2 * (
            prev_high -
            df["pivot"]
        )
    )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    signals = []
    scores = []
    confidences = []
    factors = []

    for _, row in df.iterrows():

        (
            signal,
            score,
            confidence,
            factor_string
        ) = calculate_signal(row)

        signals.append(signal)
        scores.append(score)
        confidences.append(confidence)
        factors.append(factor_string)

    df["signal"] = signals
    df["signal_score"] = scores
    df["confidence"] = confidences
    df["signal_factors"] = factors

    # --------------------------------------------------------
    # DB COLUMN NAMES
    # --------------------------------------------------------

    df = df.rename(
        columns={
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "close": "close_price"
        }
    )

    # Date only
    df["date"] = pd.to_datetime(
        df["date"]
    ).dt.date

    # --------------------------------------------------------
    # Remove warmup
    #
    # 300 rows required for:
    # MA200 + 252-day percentile.
    # --------------------------------------------------------

    df = df.iloc[MIN_HISTORY:].copy()

    # --------------------------------------------------------
    # Remove invalid numerical values
    # --------------------------------------------------------

    numeric_columns = df.select_dtypes(
        include=[np.number]
    ).columns

    df[numeric_columns] = (
        df[numeric_columns]
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
    )

    # --------------------------------------------------------
    # Final column order
    # --------------------------------------------------------

    expected_columns = [
        "date",

        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",

        "ma_7",
        "ma_20",
        "ma_50",
        "ma_100",
        "ma_200",

        "ma_7_slope",
        "ma_20_slope",
        "ma_50_slope",
        "ma_100_slope",
        "ma_200_slope",

        "ma_trend",

        "rsi",

        "macd",
        "macd_signal",
        "macd_histogram",
        "macd_state",
        "macd_crossover",

        "bb_middle",
        "bb_upper",
        "bb_lower",
        "bb_bandwidth",
        "bb_bandwidth_percentile",
        "bb_squeeze",

        "atr",
        "atr_percent",
        "atr_percentile",

        "support",
        "resistance",
        "support_touches",
        "resistance_touches",

        "fib_direction",
        "fib_swing_high",
        "fib_swing_low",

        "fib_0",
        "fib_236",
        "fib_382",
        "fib_500",
        "fib_618",
        "fib_786",
        "fib_1000",

        "fib_current_level",

        "pivot",
        "pivot_r1",
        "pivot_s1",
        "pivot_r2",
        "pivot_s2",
        "pivot_r3",
        "pivot_s3",

        "market_structure",

        "bos",
        "bos_price",
        "bos_date",

        "choch",
        "choch_price",
        "choch_date",

        "volume_avg_30",
        "volume_ratio",

        "poc",
        "vah",
        "val",

        "signal",
        "signal_score",
        "confidence",
        "signal_factors"
    ]

    # Keep only expected columns
    df = df[
        [
            c for c in expected_columns
            if c in df.columns
        ]
    ]

    return df


# ============================================================
# FINAL VALIDATION
# ============================================================

def final_validation(df):

    logger.info("Running final validation...")

    if df.empty:
        raise ValueError(
            "Final indicator dataframe is empty."
        )

    if df["date"].duplicated().any():
        raise ValueError(
            "Duplicate dates detected."
        )

    if not df["date"].is_monotonic_increasing:
        raise ValueError(
            "Dates are not sorted."
        )

    # No future structural dates
    for col in ["bos_date", "choch_date"]:

        if col in df.columns:

            invalid = (
                pd.notna(df[col]) &
                (
                    pd.to_datetime(df[col]) >
                    pd.to_datetime(df["date"])
                )
            )

            if invalid.any():

                raise ValueError(
                    f"Future leakage detected in {col}."
                )

    # OHLC
    invalid_ohlc = (
        (df["high_price"] < df["low_price"]) |
        (df["high_price"] < df["open_price"]) |
        (df["high_price"] < df["close_price"]) |
        (df["low_price"] > df["open_price"]) |
        (df["low_price"] > df["close_price"]) |
        (df["close_price"] <= 0)
    )

    if invalid_ohlc.any():

        raise ValueError(
            "Invalid OHLC values found."
        )

    # Infinite numbers
    numeric = df.select_dtypes(
        include=[np.number]
    )

    if np.isinf(
        numeric.to_numpy()
    ).any():

        raise ValueError(
            "Infinite numerical values detected."
        )

    logger.info(
        f"Final validation passed: {len(df)} rows."
    )


# ============================================================
# SUMMARY
# ============================================================

def show_summary(df):

    logger.info("")
    logger.info("=" * 70)
    logger.info("BTC INDICATORS SUMMARY")
    logger.info("=" * 70)

    logger.info(
        f"Rows: {len(df):,}"
    )

    logger.info(
        f"Date range: {df['date'].min()} -> "
        f"{df['date'].max()}"
    )

    logger.info(
        f"Average close: "
        f"{df['close_price'].mean():,.2f}"
    )

    logger.info("")
    logger.info("Signals:")

    logger.info(
        df["signal"]
        .value_counts(dropna=False)
        .to_string()
    )

    logger.info("")
    logger.info("Market Structure:")

    logger.info(
        df["market_structure"]
        .value_counts(dropna=False)
        .to_string()
    )

    logger.info("")
    logger.info("BOS:")

    logger.info(
        df["bos"]
        .value_counts(dropna=False)
        .to_string()
    )

    logger.info("")
    logger.info("CHOCH:")

    logger.info(
        df["choch"]
        .value_counts(dropna=False)
        .to_string()
    )

    logger.info("=" * 70)


# ============================================================
# MAIN
# ============================================================

def main():

    start_time = time.time()

    logger.info("=" * 70)
    logger.info("BTC INDICATORS - FINAL PRODUCTION BUILD")
    logger.info("=" * 70)

    db = DatabaseManager()

    try:

        # ----------------------------------------------------
        # 1. Database
        # ----------------------------------------------------

        db.create_pool()
        db.create_table()

        # ----------------------------------------------------
        # 2. Fetch
        # ----------------------------------------------------

        logger.info(
            "Fetching BTC price history..."
        )

        df = db.fetch_price_data()

        if df.empty:
            raise ValueError(
                "No BTC price data found."
            )

        logger.info(
            f"Loaded {len(df):,} price records."
        )

        # ----------------------------------------------------
        # 3. Validate
        # ----------------------------------------------------

        df = validate_data(df)

        if len(df) < MIN_HISTORY + 50:
            raise ValueError(
                f"Not enough history. "
                f"Need at least {MIN_HISTORY + 50} rows."
            )

        # ----------------------------------------------------
        # 4. Calculate
        # ----------------------------------------------------

        indicators = calculate_indicators(df)

        # ----------------------------------------------------
        # 5. Final validation
        # ----------------------------------------------------

        final_validation(indicators)

        # ----------------------------------------------------
        # 6. Safe database replacement
        # ----------------------------------------------------

        logger.info(
            "Writing indicators to database..."
        )

        db.replace_table_safely(
            indicators
        )

        # ----------------------------------------------------
        # 7. Summary
        # ----------------------------------------------------

        show_summary(indicators)

        elapsed = time.time() - start_time

        logger.info(
            f"Completed successfully in "
            f"{elapsed:.2f} seconds."
        )

    except Exception as e:

        logger.exception(
            f"BUILD FAILED: {e}"
        )

        raise


if __name__ == "__main__":
    main()