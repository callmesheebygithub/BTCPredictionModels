"""
YahooFinanceDataOnce.py
Fetch BTC data from Yahoo Finance and store in MySQL
"""

import mysql.connector
from mysql.connector import Error
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
import os


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
# BITCOIN DATA FETCHER
# ============================================================

class BitcoinDataFetcher:

    def __init__(self):
        """Initialize database connection"""
        self.conn = None
        self.cursor = None
        self.connect()

    # --------------------------------------------------------
    # DATABASE CONNECTION
    # --------------------------------------------------------

    def connect(self):
        """Connect to MySQL database"""

        try:
            self.conn = mysql.connector.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )

            self.cursor = self.conn.cursor()

            logger.info("✅ Connected to database")

            return True

        except Error as e:
            logger.error(f"❌ Connection failed: {e}")
            return False

    # --------------------------------------------------------
    # FETCH BTC DATA
    # --------------------------------------------------------

    def fetch_btc_data(self, start_date="2014-09-17", end_date=None):
        """Fetch Bitcoin data from Yahoo Finance"""

        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(
            f"📥 Fetching BTC data from {start_date} to {end_date}"
        )

        try:

            btc = yf.Ticker("BTC-USD")

            df = btc.history(
                start=start_date,
                end=end_date
            )

            if df.empty:
                logger.warning("⚠️ No data fetched")
                return None

            logger.info(
                f"✅ Fetched {len(df)} records"
            )

            return df

        except Exception as e:

            logger.error(
                f"❌ Error fetching data: {e}"
            )

            return None

    # --------------------------------------------------------
    # CLEAN DATA
    # --------------------------------------------------------

    def clean_data(self, df):
        """Clean Yahoo Finance data"""

        try:

            # Reset index
            df = df.reset_index()

            # Convert column names to lowercase
            df.columns = df.columns.str.lower()

            # Convert date
            df["date"] = pd.to_datetime(
                df["date"]
            ).dt.date

            # Keep required columns
            df = df[
                [
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume"
                ]
            ]

            # Remove duplicate dates
            df = df.drop_duplicates(
                subset=["date"]
            )

            # Remove NULL values
            df = df.dropna()

            # Convert volume to integer
            df["volume"] = df["volume"].astype("int64")

            logger.info(
                f"✅ Cleaned {len(df)} records"
            )

            return df

        except Exception as e:

            logger.error(
                f"❌ Error cleaning data: {e}"
            )

            return None

    # --------------------------------------------------------
    # STORE DATA
    # --------------------------------------------------------

    def store_data(self, df):
        """
        Insert/update BTC data.

        'date' is the PRIMARY KEY.
        If date already exists, the record is updated.
        """

        if df is None or df.empty:

            logger.warning(
                "⚠️ No data to store"
            )

            return False

        try:

            query = """
                INSERT INTO btc_price_history
                (
                    date,
                    open,
                    high,
                    low,
                    close,
                    volume
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                ON DUPLICATE KEY UPDATE
                    open = VALUES(open),
                    high = VALUES(high),
                    low = VALUES(low),
                    close = VALUES(close),
                    volume = VALUES(volume)
            """

            data = []

            for _, row in df.iterrows():

                data.append(
                    (
                        row["date"],
                        float(row["open"]),
                        float(row["high"]),
                        float(row["low"]),
                        float(row["close"]),
                        int(row["volume"])
                    )
                )

            # Execute all rows
            self.cursor.executemany(
                query,
                data
            )

            self.conn.commit()

            logger.info(
                f"✅ Successfully stored {len(data)} records"
            )

            return True

        except Error as e:

            logger.error(
                f"❌ Error storing data: {e}"
            )

            if self.conn:
                self.conn.rollback()

            return False

    # --------------------------------------------------------
    # GET LAST DATE
    # --------------------------------------------------------

    def get_last_date(self):
        """Get latest date already stored in database"""

        try:

            self.cursor.execute(
                "SELECT MAX(date) FROM btc_price_history"
            )

            result = self.cursor.fetchone()

            if result and result[0]:
                return result[0]

            return None

        except Error as e:

            logger.error(
                f"❌ Error getting last date: {e}"
            )

            return None

    # --------------------------------------------------------
    # CLOSE CONNECTION
    # --------------------------------------------------------

    def close(self):
        """Close database connection"""

        if self.cursor:
            self.cursor.close()

        if self.conn:
            self.conn.close()

            logger.info(
                "🔒 Connection closed"
            )


# ============================================================
# MAIN
# ============================================================

def main():

    fetcher = BitcoinDataFetcher()

    # Stop if database connection failed
    if not fetcher.conn:
        return

    try:

        # ----------------------------------------------------
        # CHECK LAST DATE
        # ----------------------------------------------------

        last_date = fetcher.get_last_date()

        if last_date:

            start_date = (
                last_date + timedelta(days=1)
            ).strftime("%Y-%m-%d")

            logger.info(
                f"📅 Found data till {last_date}. "
                f"Fetching from {start_date}"
            )

        else:

            start_date = "2014-09-17"

            logger.info(
                f"📅 No data found. "
                f"Starting from {start_date}"
            )

        # ----------------------------------------------------
        # FETCH DATA
        # ----------------------------------------------------

        df = fetcher.fetch_btc_data(
            start_date=start_date
        )

        # ----------------------------------------------------
        # CLEAN + STORE
        # ----------------------------------------------------

        if df is not None and not df.empty:

            cleaned_df = fetcher.clean_data(df)

            if (
                cleaned_df is not None
                and not cleaned_df.empty
            ):

                fetcher.store_data(
                    cleaned_df
                )

        else:

            logger.info(
                "ℹ️ No new BTC data available."
            )

    finally:

        fetcher.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()