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
# CREATE PREDICTION TABLE
# ============================================================

def create_prediction_table():

    conn = get_connection()

    cursor = conn.cursor()

    query = """

    CREATE TABLE IF NOT EXISTS btc_predictions (

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

    cursor.execute(query)

    conn.commit()

    cursor.close()

    conn.close()


# ============================================================
# LOAD DATA
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

    features = [
        column
        for column in df.columns
        if column not in excluded_columns
    ]

    return features


# ============================================================
# CLASSICAL MODELS
# ============================================================

def predict_classical_models(df):

    model_names = [
        "linear_regression",
        "random_forest",
        "xgboost",
        "lightgbm"
    ]

    results = []

    # Latest row for prediction
    latest_row = df.iloc[-1]

    current_close = float(
        latest_row["close"]
    )

    prediction_date = (
        latest_row["date"]
    )

    for model_name in model_names:

        model_path = os.path.join(
            MODEL_DIR,
            f"{model_name}.pkl"
        )

        if not os.path.exists(model_path):

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

            X_latest = latest_row[
                features
            ].values.reshape(1, -1)

            predicted_return = float(
                model.predict(
                    X_latest
                )[0]
            )

            predicted_price = (
                current_close
                *
                (
                    1 +
                    predicted_return
                )
            )

            predicted_direction = (
                1
                if predicted_return > 0
                else 0
            )

            results.append({

                "prediction_date":
                    prediction_date,

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

            })

            print(
                f"{model_name:<20}"
                f" Return: "
                f"{predicted_return:+.4%}"
                f" | Price: "
                f"{predicted_price:,.2f}"
            )

        except Exception as e:

            print(
                f"[ERROR] "
                f"{model_name}: {e}"
            )

    return results


# ============================================================
# LSTM / GRU PREDICTION
# ============================================================

def predict_deep_models(df):

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

        scaler = scaler_bundle["scaler"]

        features = scaler_bundle["features"]

    except Exception as e:

        print(
            f"[ERROR] Loading deep scaler: {e}"
        )

        return []

    # --------------------------------------------------------
    # Check enough rows
    # --------------------------------------------------------

    if len(df) < SEQUENCE_LENGTH:

        print(
            "Not enough data for "
            "LSTM/GRU prediction."
        )

        return []

    try:

        # ----------------------------------------------------
        # IMPORTANT:
        # Use latest 30 rows only.
        # ----------------------------------------------------

        recent_data = df[
            features
        ].tail(
            SEQUENCE_LENGTH
        )

        X_recent = recent_data.values

        X_scaled = scaler.transform(
            X_recent
        )

        X_sequence = X_scaled.reshape(
            1,
            SEQUENCE_LENGTH,
            len(features)
        )

        latest_row = df.iloc[-1]

        current_close = float(
            latest_row["close"]
        )

        prediction_date = (
            latest_row["date"]
        )

    except Exception as e:

        print(
            f"[ERROR] Preparing deep "
            f"learning input: {e}"
        )

        return []

    results = []

    # ========================================================
    # LSTM
    # ========================================================

    lstm_path = os.path.join(
        MODEL_DIR,
        "lstm.keras"
    )

    if os.path.exists(lstm_path):

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
                    1 +
                    predicted_return
                )
            )

            predicted_direction = (
                1
                if predicted_return > 0
                else 0
            )

            results.append({

                "prediction_date":
                    prediction_date,

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
                f"{predicted_price:,.2f}"
            )

        except Exception as e:

            print(
                f"[ERROR] LSTM: {e}"
            )

    else:

        print(
            "[WARNING] lstm.keras not found."
        )

    # ========================================================
    # GRU
    # ========================================================

    gru_path = os.path.join(
        MODEL_DIR,
        "gru.keras"
    )

    if os.path.exists(gru_path):

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
                    1 +
                    predicted_return
                )
            )

            predicted_direction = (
                1
                if predicted_return > 0
                else 0
            )

            results.append({

                "prediction_date":
                    prediction_date,

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
                f"{predicted_price:,.2f}"
            )

        except Exception as e:

            print(
                f"[ERROR] GRU: {e}"
            )

    else:

        print(
            "[WARNING] gru.keras not found."
        )

    return results


# ============================================================
# SAVE PREDICTIONS
# ============================================================

def save_predictions(results):

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
        %s
    )

    ON DUPLICATE KEY UPDATE

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
# DISPLAY SUMMARY
# ============================================================

def display_summary(results):

    print("\n")
    print("=" * 85)
    print("BTC NEXT-DAY PREDICTIONS")
    print("=" * 85)

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
            f" | Return: "
            f"{result['predicted_return']:+.4%}"
            f" | Price: "
            f"${result['predicted_price']:,.2f}"
            f" | Direction: "
            f"{direction}"
        )

    print("=" * 85)


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")
    print("=" * 85)
    print("BTC MULTI-MODEL DAILY PREDICTION")
    print("=" * 85)

    # --------------------------------------------------------
    # Create table
    # --------------------------------------------------------

    create_prediction_table()

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

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
        f"Loaded {len(df)} records."
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # We use the latest row directly.
    # We do NOT require target_return to be present.
    # --------------------------------------------------------

    latest = df.iloc[-1]

    print(
        f"\nLatest BTC date: "
        f"{latest['date']}"
    )

    print(
        f"Latest close: "
        f"${float(latest['close']):,.2f}"
    )

    # --------------------------------------------------------
    # Classical models
    # --------------------------------------------------------

    print("\n")
    print(
        "Running classical models..."
    )

    classical_results = (
        predict_classical_models(df)
    )

    # --------------------------------------------------------
    # LSTM / GRU
    # --------------------------------------------------------

    print("\n")
    print(
        "Running LSTM / GRU..."
    )

    deep_results = (
        predict_deep_models(df)
    )

    # --------------------------------------------------------
    # Combine
    # --------------------------------------------------------

    all_results = (
        classical_results
        +
        deep_results
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    save_predictions(
        all_results
    )

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

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