"""
daily_btc_prediction.py

Purpose:
    Generate next-day BTC predictions using:

        Linear Regression
        Random Forest
        XGBoost
        LightGBM
        LSTM
        GRU

Example:

    Latest available candle:
        2026-09-04

    Current close:
        $XXX

    Prediction:
        2026-09-05

The latest candle does NOT need a target_return.

Prediction flow:

    Sep 3 -> known Sep 4 result -> training/evaluation
    Sep 4 -> unknown Sep 5 result -> prediction
    Sep 5 -> later becomes actual -> evaluate Sep 4 prediction
"""

import os
import joblib
import mysql.connector
import numpy as np
import pandas as pd

from dotenv import load_dotenv

from tensorflow.keras.models import load_model


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

MODEL_DIR = "models"

SEQUENCE_LENGTH = 30


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    return mysql.connector.connect(
        **DB_CONFIG
    )


# ============================================================
# CREATE / MIGRATE PREDICTION TABLE
# ============================================================

def create_prediction_table():

    conn = get_connection()

    cursor = conn.cursor()

    # --------------------------------------------------------
    # New table structure
    # --------------------------------------------------------

    query = """

    CREATE TABLE IF NOT EXISTS btc_predictions (

        feature_date DATE NOT NULL,

        prediction_date DATE NOT NULL,

        model_name VARCHAR(50) NOT NULL,

        current_close DOUBLE,

        predicted_return DOUBLE,

        predicted_price DOUBLE,

        predicted_direction TINYINT,

        actual_return DOUBLE NULL,

        actual_price DOUBLE NULL,

        actual_direction TINYINT NULL,

        evaluated TINYINT DEFAULT 0,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        PRIMARY KEY (
            prediction_date,
            model_name
        )

    )

    """

    cursor.execute(
        query
    )

    conn.commit()

    cursor.close()

    conn.close()


# ============================================================
# LOAD ML DATA
# ============================================================

def load_ml_data():

    conn = get_connection()

    query = """

        SELECT *
        FROM btc_ml_features
        ORDER BY date ASC

    """

    df = pd.read_sql(
        query,
        conn
    )

    conn.close()

    if not df.empty:

        df["date"] = pd.to_datetime(
            df["date"]
        )

    return df


# ============================================================
# GET FEATURES
# ============================================================

def get_feature_columns(df):

    excluded_columns = [
        "date",
        "target_return",
        "target_direction"
    ]

    return [
        column
        for column in df.columns
        if column not in excluded_columns
    ]


# ============================================================
# FIND LATEST VALID FEATURE ROW
# ============================================================

def get_latest_prediction_row(df):

    features = get_feature_columns(
        df
    )

    # Find rows where all model features exist.
    valid_mask = (
        df[features]
        .notna()
        .all(axis=1)
    )

    valid_df = df[
        valid_mask
    ].copy()

    if valid_df.empty:

        raise ValueError(
            "❌ No row contains a complete "
            "feature set for prediction."
        )

    latest_row = valid_df.iloc[-1]

    return latest_row


# ============================================================
# CLASSICAL MODELS
# ============================================================

def predict_classical_models(
    df,
    latest_row
):

    model_names = [

        "linear_regression",
        "random_forest",
        "xgboost",
        "lightgbm"
    ]

    results = []

    feature_date = pd.Timestamp(
        latest_row["date"]
    )

    prediction_date = (
        feature_date
        + pd.Timedelta(days=1)
    )

    current_close = float(
        latest_row["close"]
    )

    for model_name in model_names:

        model_path = os.path.join(
            MODEL_DIR,
            f"{model_name}.pkl"
        )

        if not os.path.exists(
            model_path
        ):

            print(
                f"[WARNING] "
                f"{model_name}.pkl not found."
            )

            continue

        try:

            bundle = joblib.load(
                model_path
            )

            model = bundle["model"]

            features = bundle["features"]

            # ------------------------------------------------
            # Make sure all required features exist
            # ------------------------------------------------

            missing_features = [
                feature
                for feature in features
                if feature not in latest_row.index
            ]

            if missing_features:

                raise ValueError(
                    f"Missing features: "
                    f"{missing_features}"
                )

            X_latest = (
                latest_row[
                    features
                ]
                .values
                .reshape(1, -1)
            )

            # ------------------------------------------------
            # Prediction
            # ------------------------------------------------

            predicted_return = float(
                model.predict(
                    X_latest
                )[0]
            )

            predicted_price = (
                current_close
                *
                (
                    1
                    +
                    predicted_return
                )
            )

            predicted_direction = (
                1
                if predicted_return > 0
                else 0
            )

            result = {

                "feature_date":
                    feature_date.date(),

                "prediction_date":
                    prediction_date.date(),

                "model_name":
                    model_name,

                "current_close":
                    current_close,

                "predicted_return":
                    predicted_return,

                "predicted_price":
                    predicted_price,

                "predicted_direction":
                    predicted_direction
            }

            results.append(
                result
            )

            print(
                f"{model_name:<20}"
                f" Return: "
                f"{predicted_return:+.4%}"
                f" | Price: "
                f"${predicted_price:,.2f}"
                f" | Predicting: "
                f"{prediction_date.date()}"
            )

        except Exception as e:

            print(
                f"[ERROR] "
                f"{model_name}: {e}"
            )

    return results


# ============================================================
# DEEP MODEL PREDICTION
# ============================================================

def predict_deep_models(
    df,
    latest_row
):

    scaler_path = os.path.join(
        MODEL_DIR,
        "deep_scaler.pkl"
    )

    if not os.path.exists(
        scaler_path
    ):

        print(
            "[WARNING] "
            "deep_scaler.pkl not found."
        )

        return []

    try:

        scaler_bundle = joblib.load(
            scaler_path
        )

        scaler = scaler_bundle[
            "scaler"
        ]

        features = scaler_bundle[
            "features"
        ]

        saved_sequence_length = (
            scaler_bundle.get(
                "sequence_length",
                SEQUENCE_LENGTH
            )
        )

    except Exception as e:

        print(
            f"[ERROR] Loading deep scaler: "
            f"{e}"
        )

        return []

    sequence_length = (
        saved_sequence_length
    )

    # --------------------------------------------------------
    # Check features
    # --------------------------------------------------------

    missing_features = [
        feature
        for feature in features
        if feature not in df.columns
    ]

    if missing_features:

        print(
            "[ERROR] Deep model missing features:"
        )

        print(
            missing_features
        )

        return []

    # --------------------------------------------------------
    # Use rows with complete deep-model features
    # --------------------------------------------------------

    valid_df = df[
        features
    ].replace(
        [np.inf, -np.inf],
        np.nan
    )

    valid_mask = (
        valid_df
        .notna()
        .all(axis=1)
    )

    usable_df = df[
        valid_mask
    ].copy()

    if len(usable_df) < sequence_length:

        print(
            "Not enough valid rows for "
            "LSTM/GRU prediction."
        )

        return []

    # --------------------------------------------------------
    # Latest sequence
    # --------------------------------------------------------

    recent_data = usable_df[
        features
    ].tail(
        sequence_length
    )

    X_recent = (
        recent_data
        .values
        .astype(np.float32)
    )

    try:

        X_scaled = scaler.transform(
            X_recent
        ).astype(
            np.float32
        )

    except Exception as e:

        print(
            f"[ERROR] Scaling deep input: "
            f"{e}"
        )

        return []

    X_sequence = X_scaled.reshape(
        1,
        sequence_length,
        len(features)
    )

    feature_date = pd.Timestamp(
        latest_row["date"]
    )

    prediction_date = (
        feature_date
        + pd.Timedelta(days=1)
    )

    current_close = float(
        latest_row["close"]
    )

    results = []

    # ========================================================
    # LSTM
    # ========================================================

    lstm_path = os.path.join(
        MODEL_DIR,
        "lstm.keras"
    )

    if os.path.exists(
        lstm_path
    ):

        try:

            lstm_model = load_model(
                lstm_path
            )

            predicted_return = float(
                lstm_model.predict(
                    X_sequence,
                    verbose=0
                )[0][0]
            )

            predicted_price = (
                current_close
                *
                (
                    1
                    +
                    predicted_return
                )
            )

            predicted_direction = (
                1
                if predicted_return > 0
                else 0
            )

            results.append({

                "feature_date":
                    feature_date.date(),

                "prediction_date":
                    prediction_date.date(),

                "model_name":
                    "lstm",

                "current_close":
                    current_close,

                "predicted_return":
                    predicted_return,

                "predicted_price":
                    predicted_price,

                "predicted_direction":
                    predicted_direction
            })

            print(
                f"{'LSTM':<20}"
                f" Return: "
                f"{predicted_return:+.4%}"
                f" | Price: "
                f"${predicted_price:,.2f}"
                f" | Predicting: "
                f"{prediction_date.date()}"
            )

        except Exception as e:

            print(
                f"[ERROR] LSTM: {e}"
            )

    else:

        print(
            "[WARNING] "
            "lstm.keras not found."
        )

    # ========================================================
    # GRU
    # ========================================================

    gru_path = os.path.join(
        MODEL_DIR,
        "gru.keras"
    )

    if os.path.exists(
        gru_path
    ):

        try:

            gru_model = load_model(
                gru_path
            )

            predicted_return = float(
                gru_model.predict(
                    X_sequence,
                    verbose=0
                )[0][0]
            )

            predicted_price = (
                current_close
                *
                (
                    1
                    +
                    predicted_return
                )
            )

            predicted_direction = (
                1
                if predicted_return > 0
                else 0
            )

            results.append({

                "feature_date":
                    feature_date.date(),

                "prediction_date":
                    prediction_date.date(),

                "model_name":
                    "gru",

                "current_close":
                    current_close,

                "predicted_return":
                    predicted_return,

                "predicted_price":
                    predicted_price,

                "predicted_direction":
                    predicted_direction
            })

            print(
                f"{'GRU':<20}"
                f" Return: "
                f"{predicted_return:+.4%}"
                f" | Price: "
                f"${predicted_price:,.2f}"
                f" | Predicting: "
                f"{prediction_date.date()}"
            )

        except Exception as e:

            print(
                f"[ERROR] GRU: {e}"
            )

    else:

        print(
            "[WARNING] "
            "gru.keras not found."
        )

    return results


# ============================================================
# SAVE PREDICTIONS
# ============================================================

def save_predictions(
    results
):

    if not results:

        print(
            "No predictions to save."
        )

        return

    conn = get_connection()

    cursor = conn.cursor()

    query = """

    INSERT INTO btc_predictions
    (
        feature_date,
        prediction_date,
        model_name,
        current_close,
        predicted_return,
        predicted_price,
        predicted_direction
    )

    VALUES
    (
        %s,
        %s,
        %s,
        %s,
        %s,
        %s,
        %s
    )

    ON DUPLICATE KEY UPDATE

        feature_date =
            VALUES(feature_date),

        current_close =
            VALUES(current_close),

        predicted_return =
            VALUES(predicted_return),

        predicted_price =
            VALUES(predicted_price),

        predicted_direction =
            VALUES(predicted_direction),

        created_at =
            CURRENT_TIMESTAMP

    """

    for result in results:

        cursor.execute(
            query,
            (
                result["feature_date"],
                result["prediction_date"],
                result["model_name"],
                result["current_close"],
                result["predicted_return"],
                result["predicted_price"],
                result["predicted_direction"]
            )
        )

    conn.commit()

    cursor.close()

    conn.close()

    print(
        f"\nSaved {len(results)} model "
        f"predictions to database."
    )


# ============================================================
# EVALUATE PREVIOUS PREDICTIONS
# ============================================================

def evaluate_previous_predictions():

    """
    Evaluate predictions once the actual target day
    becomes available.

    Example:

        Prediction:
            feature_date = Sep 4
            prediction_date = Sep 5

        Once Sep 5 data exists:

            actual_return =
                Sep 5 close / Sep 4 close - 1

            actual_price =
                Sep 5 close

            actual_direction =
                actual_return > 0
    """

    conn = get_connection()

    cursor = conn.cursor(
        dictionary=True
    )

    query = """

        SELECT
            p.prediction_date,
            p.model_name,
            p.current_close,
            p.predicted_return,
            p.predicted_price,
            p.predicted_direction,

            d.close AS actual_price

        FROM btc_predictions p

        INNER JOIN btc_ml_features d
            ON d.date = p.prediction_date

        WHERE
            p.evaluated = 0

    """

    cursor.execute(
        query
    )

    rows = cursor.fetchall()

    if not rows:

        cursor.close()

        conn.close()

        print(
            "No previous predictions ready "
            "for evaluation."
        )

        return

    print("\n")
    print("=" * 85)
    print(
        "EVALUATING PREVIOUS PREDICTIONS"
    )
    print("=" * 85)

    update_query = """

        UPDATE btc_predictions

        SET
            actual_return = %s,
            actual_price = %s,
            actual_direction = %s,
            evaluated = 1

        WHERE
            prediction_date = %s
            AND model_name = %s

    """

    evaluated_count = 0

    for row in rows:

        prediction_date = pd.Timestamp(
            row["prediction_date"]
        )

        actual_price = float(
            row["actual_price"]
        )

        current_close = float(
            row["current_close"]
        )

        actual_return = (
            actual_price
            /
            current_close
            - 1
        )

        actual_direction = (
            1
            if actual_return > 0
            else 0
        )

        predicted_return = float(
            row["predicted_return"]
        )

        predicted_direction = int(
            row["predicted_direction"]
        )

        direction_correct = (
            predicted_direction
            ==
            actual_direction
        )

        update_values = (

            actual_return,

            actual_price,

            actual_direction,

            row["prediction_date"],

            row["model_name"]
        )

        cursor.execute(
            update_query,
            update_values
        )

        evaluated_count += 1

        result_text = (
            "CORRECT"
            if direction_correct
            else "WRONG"
        )

        print(
            f"{str(row['model_name']):<20}"
            f" | Date: "
            f"{prediction_date.date()}"
            f" | Pred: "
            f"{predicted_return:+.4%}"
            f" | Actual: "
            f"{actual_return:+.4%}"
            f" | {result_text}"
        )

    conn.commit()

    cursor.close()

    conn.close()

    print(
        f"\nEvaluated {evaluated_count} "
        f"previous predictions."
    )


# ============================================================
# DISPLAY SUMMARY
# ============================================================

def display_summary(
    results
):

    print("\n")
    print("=" * 100)
    print(
        "BTC NEXT-DAY PREDICTIONS"
    )
    print("=" * 100)

    if not results:

        print(
            "No predictions generated."
        )

        return

    for result in results:

        direction = (
            "UP"
            if result["predicted_direction"] == 1
            else "DOWN"
        )

        print(
            f"{result['model_name']:<20}"
            f" | From: "
            f"{result['feature_date']}"
            f" | Predicting: "
            f"{result['prediction_date']}"
            f" | Return: "
            f"{result['predicted_return']:+.4%}"
            f" | Price: "
            f"${result['predicted_price']:,.2f}"
            f" | Direction: "
            f"{direction}"
        )

    print(
        "=" * 100
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")
    print("=" * 100)
    print(
        "BTC MULTI-MODEL DAILY PREDICTION"
    )
    print("=" * 100)

    # ========================================================
    # CREATE TABLE
    # ========================================================

    create_prediction_table()

    # ========================================================
    # LOAD DATA
    # ========================================================

    print(
        "\nLoading BTC ML data..."
    )

    df = load_ml_data()

    if df.empty:

        print(
            "No data found in "
            "btc_ml_features."
        )

        return

    print(
        f"Loaded {len(df):,} records."
    )

    # ========================================================
    # LATEST FEATURE ROW
    # ========================================================

    latest = get_latest_prediction_row(
        df
    )

    feature_date = pd.Timestamp(
        latest["date"]
    )

    prediction_date = (
        feature_date
        + pd.Timedelta(days=1)
    )

    current_close = float(
        latest["close"]
    )

    print("\n")
    print("=" * 70)

    print(
        f"Latest feature date: "
        f"{feature_date.date()}"
    )

    print(
        f"Latest close: "
        f"${current_close:,.2f}"
    )

    print(
        f"🎯 Prediction date: "
        f"{prediction_date.date()}"
    )

    print(
        "=" * 70
    )

    # ========================================================
    # EVALUATE OLD PREDICTIONS FIRST
    # ========================================================

    evaluate_previous_predictions()

    # ========================================================
    # CLASSICAL MODELS
    # ========================================================

    print("\n")
    print(
        "Running classical models..."
    )

    classical_results = (
        predict_classical_models(
            df,
            latest
        )
    )

    # ========================================================
    # LSTM / GRU
    # ========================================================

    print("\n")
    print(
        "Running LSTM / GRU..."
    )

    deep_results = (
        predict_deep_models(
            df,
            latest
        )
    )

    # ========================================================
    # COMBINE
    # ========================================================

    all_results = (
        classical_results
        +
        deep_results
    )

    # ========================================================
    # SAVE
    # ========================================================

    save_predictions(
        all_results
    )

    # ========================================================
    # DISPLAY
    # ========================================================

    display_summary(
        all_results
    )

    print(
        "\nDaily prediction completed."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()