# ============================================================
# evaluate_prediction.py
#
# BTC Prediction Evaluation
#
# Purpose:
#   Evaluate previously generated next-day predictions once
#   the actual BTC candle becomes available.
#
# Example:
#
#   Feature date:
#       2026-09-04
#
#   Prediction date:
#       2026-09-05
#
#   Prediction:
#       Sep 5 BTC return/price
#
#   Once Sep 5 actual candle is available:
#       evaluate Sep 5 prediction
#
# IMPORTANT:
#   prediction_date already represents the date being predicted.
#
#   Therefore:
#
#       p.prediction_date = n.date
#
#   NOT:
#
#       p.prediction_date + 1 day
# ============================================================

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
# DATABASE CONNECTION
# ============================================================

def get_connection():

    try:

        conn = mysql.connector.connect(
            **DB_CONFIG
        )

        if not conn.is_connected():

            raise RuntimeError(
                "Could not connect to MySQL."
            )

        return conn

    except mysql.connector.Error as e:

        raise RuntimeError(
            f"MySQL connection failed: {e}"
        )


# ============================================================
# VALIDATE CONFIG
# ============================================================

def validate_config():

    missing = []

    for key, value in DB_CONFIG.items():

        if not value:

            missing.append(
                key
            )

    if missing:

        raise ValueError(
            "Missing database configuration: "
            + ", ".join(missing)
        )


# ============================================================
# EVALUATE PREDICTIONS
# ============================================================

def evaluate_predictions():

    conn = get_connection()

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # prediction_date is already the actual date being
    # predicted.
    #
    # Example:
    #
    # prediction_date = 2026-09-05
    #
    # Actual data:
    #
    # btc_ml_features.date = 2026-09-05
    #
    # Therefore:
    #
    # n.date = p.prediction_date
    #
    # --------------------------------------------------------

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

    INNER JOIN btc_ml_features n

        ON n.date = p.prediction_date

    WHERE

        p.evaluated = 0

        AND n.close IS NOT NULL

    ORDER BY

        p.prediction_date ASC,

        p.model_name ASC

    """

    try:

        df = pd.read_sql(
            query,
            conn
        )

    except Exception:

        conn.close()

        raise

    # ========================================================
    # NOTHING TO EVALUATE
    # ========================================================

    if df.empty:

        conn.close()

        print(
            "\nNo predictions available "
            "for evaluation."
        )

        print(
            "This usually means either:"
        )

        print(
            "1. There are no unevaluated predictions."
        )

        print(
            "2. The actual prediction-date candle "
            "is not available yet."
        )

        return

    # ========================================================
    # UPDATE QUERY
    # ========================================================

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

        AND evaluated = 0

    """

    cursor = conn.cursor()

    evaluated_count = 0

    # ========================================================
    # EVALUATE EACH PREDICTION
    # ========================================================

    print("\n")

    print(
        "=" * 100
    )

    print(
        "BTC PREDICTION EVALUATION"
    )

    print(
        "=" * 100
    )

    for _, row in df.iterrows():

        try:

            # ------------------------------------------------
            # Dates
            # ------------------------------------------------

            prediction_date = pd.Timestamp(
                row["prediction_date"]
            ).date()

            # ------------------------------------------------
            # Prices
            # ------------------------------------------------

            current_price = float(
                row["current_close"]
            )

            actual_price = float(
                row["actual_price"]
            )

            # ------------------------------------------------
            # Predicted values
            # ------------------------------------------------

            predicted_return = float(
                row["predicted_return"]
            )

            predicted_direction = int(
                row["predicted_direction"]
            )

            # ------------------------------------------------
            # Actual return
            #
            # Current close = feature/source day close
            #
            # Actual price = prediction day close
            # ------------------------------------------------

            actual_return = (

                actual_price
                /
                current_price

            ) - 1

            # ------------------------------------------------
            # Actual direction
            # ------------------------------------------------

            actual_direction = (

                1
                if actual_return > 0
                else 0

            )

            # ------------------------------------------------
            # Direction result
            # ------------------------------------------------

            direction_correct = (

                predicted_direction
                ==
                actual_direction

            )

            result_text = (

                "CORRECT"
                if direction_correct
                else "WRONG"

            )

            # ------------------------------------------------
            # Update database
            # ------------------------------------------------

            cursor.execute(

                update_query,

                (

                    actual_price,

                    actual_return,

                    actual_direction,

                    prediction_date,

                    row["model_name"]

                )

            )

            # ------------------------------------------------
            # Count only if row was actually updated
            # ------------------------------------------------

            if cursor.rowcount > 0:

                evaluated_count += 1

            # ------------------------------------------------
            # Display
            # ------------------------------------------------

            predicted_direction_text = (

                "UP"
                if predicted_direction == 1
                else "DOWN"

            )

            actual_direction_text = (

                "UP"
                if actual_direction == 1
                else "DOWN"

            )

            print(

                f"{str(row['model_name']):<20}"

                f" | Date: "
                f"{prediction_date}"

                f" | Pred Return: "
                f"{predicted_return:+.4%}"

                f" | Actual Return: "
                f"{actual_return:+.4%}"

                f" | Pred: "
                f"{predicted_direction_text:<4}"

                f" | Actual: "
                f"{actual_direction_text:<4}"

                f" | {result_text}"

            )

        except Exception as e:

            print(

                f"[ERROR] "
                f"{row.get('model_name', 'Unknown')}"
                f" | "
                f"{row.get('prediction_date', 'Unknown')}"
                f" | {e}"

            )

    # ========================================================
    # COMMIT
    # ========================================================

    conn.commit()

    cursor.close()

    conn.close()

    # ========================================================
    # SUMMARY
    # ========================================================

    print(
        "=" * 100
    )

    print(
        f"Evaluated {evaluated_count} predictions."
    )

    print(
        "=" * 100
    )


# ============================================================
# DISPLAY EVALUATION SUMMARY
# ============================================================

def display_evaluation_summary():

    conn = get_connection()

    query = """

    SELECT

        model_name,

        COUNT(*) AS total_predictions,

        AVG(
            ABS(
                predicted_return
                -
                actual_return
            )
        ) AS mae,

        SQRT(
            AVG(
                POW(
                    predicted_return
                    -
                    actual_return,
                    2
                )
            )
        ) AS rmse,

        AVG(

            CASE

                WHEN predicted_direction
                     =
                     actual_direction

                THEN 1

                ELSE 0

            END

        ) * 100 AS directional_accuracy

    FROM btc_predictions

    WHERE

        evaluated = 1

    GROUP BY

        model_name

    ORDER BY

        directional_accuracy DESC

    """

    try:

        df = pd.read_sql(
            query,
            conn
        )

    finally:

        conn.close()

    if df.empty:

        print(
            "\nNo evaluated predictions found."
        )

        return

    print("\n")

    print(
        "=" * 90
    )

    print(
        "OVERALL EVALUATION SUMMARY"
    )

    print(
        "=" * 90
    )

    display_df = df.copy()

    display_df["mae"] = (
        display_df["mae"]
        .map(
            lambda x: f"{x:.4%}"
        )
    )

    display_df["rmse"] = (
        display_df["rmse"]
        .map(
            lambda x: f"{x:.4%}"
        )
    )

    display_df["directional_accuracy"] = (
        display_df[
            "directional_accuracy"
        ]
        .map(
            lambda x: f"{x:.2f}%"
        )
    )

    display_df = display_df.rename(

        columns={

            "model_name":
                "Model",

            "total_predictions":
                "Predictions",

            "mae":
                "MAE",

            "rmse":
                "RMSE",

            "directional_accuracy":
                "Direction Accuracy"

        }

    )

    print(
        display_df.to_string(
            index=False
        )
    )

    print(
        "=" * 90
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")

    print(
        "=" * 100
    )

    print(
        "BTC PREDICTION EVALUATION SYSTEM"
    )

    print(
        "=" * 100
    )

    try:

        # ----------------------------------------------------
        # Validate DB config
        # ----------------------------------------------------

        validate_config()

        # ----------------------------------------------------
        # Evaluate predictions
        # ----------------------------------------------------

        evaluate_predictions()

        # ----------------------------------------------------
        # Show summary
        # ----------------------------------------------------

        display_evaluation_summary()

        # ----------------------------------------------------
        # Complete
        # ----------------------------------------------------

        print("\n")

        print(
            "Prediction evaluation completed successfully."
        )

    except Exception as e:

        print("\n")

        print(
            "=" * 100
        )

        print(
            "PREDICTION EVALUATION FAILED"
        )

        print(
            "=" * 100
        )

        print(
            f"Error: {e}"
        )

        raise


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()