import os
import mysql.connector
import pandas as pd
import numpy as np

from dotenv import load_dotenv


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("db_host"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password"),
    "database": os.getenv("db_name")
}


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    return mysql.connector.connect(
        **DB_CONFIG
    )


# ============================================================
# EVALUATE
# ============================================================

def evaluate_predictions():

    conn = get_connection()

    query = """

    SELECT
        p.prediction_date,
        p.model_name,
        p.current_close,
        p.predicted_return,
        p.predicted_price,
        p.predicted_direction,
        n.close AS actual_price

    FROM btc_predictions p

    JOIN btc_ml_features n

        ON n.date = DATE_ADD(
            p.prediction_date,
            INTERVAL 1 DAY
        )

    WHERE p.evaluated = 0

    """

    df = pd.read_sql(query, conn)

    if df.empty:

        print("No predictions available for evaluation.")

        conn.close()

        return

    cursor = conn.cursor()

    update_query = """

    UPDATE btc_predictions

    SET

        actual_price = %s,

        actual_return = %s,

        actual_direction = %s,

        evaluated = 1

    WHERE

        prediction_date = %s

        AND model_name = %s

    """

    for _, row in df.iterrows():

        current_price = float(
            row["current_close"]
        )

        actual_price = float(
            row["actual_price"]
        )

        actual_return = (
            actual_price /
            current_price
        ) - 1

        actual_direction = (
            1
            if actual_return > 0
            else 0
        )

        cursor.execute(
            update_query,
            (
                actual_price,
                actual_return,
                actual_direction,
                row["prediction_date"],
                row["model_name"]
            )
        )

    conn.commit()

    cursor.close()

    conn.close()

    print(
        f"Evaluated {len(df)} predictions."
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    evaluate_predictions()