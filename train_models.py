# ============================================================
# train_classical_models.py
# BTC Classical Machine Learning Model Training
#
# Models:
#   1. Linear Regression
#   2. Random Forest
#   3. XGBoost
#   4. LightGBM
#
# Important:
# - Latest unlabeled row is NOT used for training
# - Historical labeled rows are used for training/testing
# - Chronological 80/20 split
# - No future-data leakage
# ============================================================

import os
import warnings
import joblib
import mysql.connector
import numpy as np
import pandas as pd

from dotenv import load_dotenv

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

from xgboost import XGBRegressor
from lightgbm import LGBMRegressor


# ============================================================
# SETTINGS
# ============================================================

warnings.filterwarnings("ignore")

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("db_host"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password"),
    "database": os.getenv("db_name")
}

MODEL_DIR = "models"

os.makedirs(MODEL_DIR, exist_ok=True)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)

        if conn.is_connected():
            return conn

        raise RuntimeError("Could not connect to MySQL.")

    except mysql.connector.Error as e:
        raise RuntimeError(f"MySQL connection failed: {e}")


# ============================================================
# LOAD ML DATA
# ============================================================

def load_data():

    conn = get_connection()

    query = """
        SELECT *
        FROM btc_ml_features
        ORDER BY date ASC
    """

    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    return df


# ============================================================
# GET FEATURE COLUMNS
# ============================================================

def get_feature_columns(df):

    excluded_columns = [
        "date",
        "target_return",
        "target_direction"
    ]

    features = [
        col
        for col in df.columns
        if col not in excluded_columns
    ]

    return features


# ============================================================
# CALCULATE METRICS
# ============================================================

def calculate_metrics(y_true, y_pred):

    mae = mean_absolute_error(
        y_true,
        y_pred
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_true,
            y_pred
        )
    )

    r2 = r2_score(
        y_true,
        y_pred
    )

    directional_accuracy = (
        np.mean(
            np.sign(y_true) == np.sign(y_pred)
        ) * 100
    )

    return {
        "MAE": mae,
        "RMSE": rmse,
        "R2": r2,
        "Directional_Accuracy": directional_accuracy
    }


# ============================================================
# TRAIN CLASSICAL MODELS
# ============================================================

def train_classical_models(df):

    print("\n========================================")
    print("PREPARING CLASSICAL ML DATA")
    print("========================================")

    # --------------------------------------------------------
    # Make sure date is datetime
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df = df.sort_values(
        "date"
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # Get feature columns
    # --------------------------------------------------------

    features = get_feature_columns(df)

    print(f"Total feature columns : {len(features)}")

    # --------------------------------------------------------
    # Keep only rows where target is known
    #
    # Latest row normally has:
    #
    # target_return = NULL
    #
    # because next day's actual price is not available yet.
    #
    # We DO NOT train on that row.
    # --------------------------------------------------------

    labeled_df = df[
        df["target_return"].notna()
    ].copy()

    print(f"Total rows in table   : {len(df)}")
    print(f"Labeled rows          : {len(labeled_df)}")
    print(f"Unlabeled rows        : {len(df) - len(labeled_df)}")

    if labeled_df.empty:

        raise ValueError(
            "No labeled rows available for training."
        )

    # --------------------------------------------------------
    # Clean infinite values
    # --------------------------------------------------------

    labeled_df[features] = labeled_df[
        features
    ].replace(
        [np.inf, -np.inf],
        np.nan
    )

    # --------------------------------------------------------
    # Remove rows where features/target are missing
    #
    # IMPORTANT:
    # We don't use bfill/ffill because that can introduce
    # unwanted data leakage.
    # --------------------------------------------------------

    before_cleaning = len(labeled_df)

    labeled_df = labeled_df.dropna(
        subset=features + ["target_return"]
    ).reset_index(drop=True)

    removed_rows = (
        before_cleaning - len(labeled_df)
    )

    if removed_rows > 0:

        print(
            f"Removed rows with missing values: "
            f"{removed_rows}"
        )

    if len(labeled_df) < 100:

        raise ValueError(
            "Not enough clean labeled data for training."
        )

    # --------------------------------------------------------
    # Prepare X and y
    # --------------------------------------------------------

    X = labeled_df[features].copy()

    y = labeled_df[
        "target_return"
    ].copy()

    # --------------------------------------------------------
    # Chronological 80/20 split
    #
    # NEVER randomly shuffle time-series data.
    # --------------------------------------------------------

    train_size = int(
        len(labeled_df) * 0.80
    )

    X_train = X.iloc[
        :train_size
    ].copy()

    X_test = X.iloc[
        train_size:
    ].copy()

    y_train = y.iloc[
        :train_size
    ].copy()

    y_test = y.iloc[
        train_size:
    ].copy()

    print("\n========================================")
    print("TRAIN / TEST SPLIT")
    print("========================================")

    print(
        f"Training rows : {len(X_train)}"
    )

    print(
        f"Testing rows  : {len(X_test)}"
    )

    print(
        f"Training dates: "
        f"{labeled_df['date'].iloc[0].date()} "
        f"→ "
        f"{labeled_df['date'].iloc[train_size - 1].date()}"
    )

    print(
        f"Testing dates : "
        f"{labeled_df['date'].iloc[train_size].date()} "
        f"→ "
        f"{labeled_df['date'].iloc[-1].date()}"
    )

    # ========================================================
    # 1. LINEAR REGRESSION
    # ========================================================

    print("\n========================================")
    print("1/4 - TRAINING LINEAR REGRESSION")
    print("========================================")

    linear_model = LinearRegression()

    linear_model.fit(
        X_train,
        y_train
    )

    linear_pred = linear_model.predict(
        X_test
    )

    linear_metrics = calculate_metrics(
        y_test,
        linear_pred
    )

    print("\nLinear Regression Results:")

    for key, value in linear_metrics.items():
        print(
            f"{key}: {value:.8f}"
        )

    joblib.dump(
        {
            "model": linear_model,
            "features": features
        },
        os.path.join(
            MODEL_DIR,
            "linear_regression.pkl"
        )
    )

    print(
        "\nSaved: models/linear_regression.pkl"
    )

    # ========================================================
    # 2. RANDOM FOREST
    # ========================================================

    print("\n========================================")
    print("2/4 - TRAINING RANDOM FOREST")
    print("========================================")

    rf_model = RandomForestRegressor(
        n_estimators=300,
        max_depth=12,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )

    rf_model.fit(
        X_train,
        y_train
    )

    rf_pred = rf_model.predict(
        X_test
    )

    rf_metrics = calculate_metrics(
        y_test,
        rf_pred
    )

    print("\nRandom Forest Results:")

    for key, value in rf_metrics.items():
        print(
            f"{key}: {value:.8f}"
        )

    joblib.dump(
        {
            "model": rf_model,
            "features": features
        },
        os.path.join(
            MODEL_DIR,
            "random_forest.pkl"
        )
    )

    print(
        "\nSaved: models/random_forest.pkl"
    )

    # ========================================================
    # 3. XGBOOST
    # ========================================================

    print("\n========================================")
    print("3/4 - TRAINING XGBOOST")
    print("========================================")

    xgb_model = XGBRegressor(
        n_estimators=500,
        learning_rate=0.03,
        max_depth=6,
        min_child_weight=3,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        eval_metric="rmse",
        random_state=42,
        n_jobs=-1
    )

    xgb_model.fit(
        X_train,
        y_train
    )

    xgb_pred = xgb_model.predict(
        X_test
    )

    xgb_metrics = calculate_metrics(
        y_test,
        xgb_pred
    )

    print("\nXGBoost Results:")

    for key, value in xgb_metrics.items():
        print(
            f"{key}: {value:.8f}"
        )

    joblib.dump(
        {
            "model": xgb_model,
            "features": features
        },
        os.path.join(
            MODEL_DIR,
            "xgboost.pkl"
        )
    )

    print(
        "\nSaved: models/xgboost.pkl"
    )

    # ========================================================
    # 4. LIGHTGBM
    # ========================================================

    print("\n========================================")
    print("4/4 - TRAINING LIGHTGBM")
    print("========================================")

    lgb_model = LGBMRegressor(
        n_estimators=500,
        learning_rate=0.03,
        max_depth=8,
        num_leaves=31,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=-1
    )

    lgb_model.fit(
        X_train,
        y_train
    )

    lgb_pred = lgb_model.predict(
        X_test
    )

    lgb_metrics = calculate_metrics(
        y_test,
        lgb_pred
    )

    print("\nLightGBM Results:")

    for key, value in lgb_metrics.items():
        print(
            f"{key}: {value:.8f}"
        )

    joblib.dump(
        {
            "model": lgb_model,
            "features": features
        },
        os.path.join(
            MODEL_DIR,
            "lightgbm.pkl"
        )
    )

    print(
        "\nSaved: models/lightgbm.pkl"
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("\n========================================")
    print("CLASSICAL MODEL SUMMARY")
    print("========================================")

    summary = pd.DataFrame(
        {
            "Model": [
                "Linear Regression",
                "Random Forest",
                "XGBoost",
                "LightGBM"
            ],
            "MAE": [
                linear_metrics["MAE"],
                rf_metrics["MAE"],
                xgb_metrics["MAE"],
                lgb_metrics["MAE"]
            ],
            "RMSE": [
                linear_metrics["RMSE"],
                rf_metrics["RMSE"],
                xgb_metrics["RMSE"],
                lgb_metrics["RMSE"]
            ],
            "R2": [
                linear_metrics["R2"],
                rf_metrics["R2"],
                xgb_metrics["R2"],
                lgb_metrics["R2"]
            ],
            "Directional Accuracy %": [
                linear_metrics["Directional_Accuracy"],
                rf_metrics["Directional_Accuracy"],
                xgb_metrics["Directional_Accuracy"],
                lgb_metrics["Directional_Accuracy"]
            ]
        }
    )

    print(
        summary.to_string(
            index=False
        )
    )

    # ========================================================
    # LATEST FEATURE INFORMATION
    # ========================================================

    latest_row = df.iloc[-1]

    print("\n========================================")
    print("LATEST FEATURE ROW")
    print("========================================")

    print(
        f"Latest feature date : "
        f"{latest_row['date'].date()}"
    )

    if pd.isna(
        latest_row["target_return"]
    ):

        print(
            "Latest target       : NULL"
        )

        print(
            "Status              : "
            "Ready for next-day prediction"
        )

    else:

        print(
            f"Latest target       : "
            f"{latest_row['target_return']:.8f}"
        )

    # ========================================================
    # MODEL DIRECTORY
    # ========================================================

    print("\n========================================")
    print("CLASSICAL MODELS TRAINED SUCCESSFULLY")
    print("========================================")

    print(
        f"Models saved in: "
        f"{os.path.abspath(MODEL_DIR)}"
    )

    print("\nFiles:")

    print(
        "  ✓ linear_regression.pkl"
    )

    print(
        "  ✓ random_forest.pkl"
    )

    print(
        "  ✓ xgboost.pkl"
    )

    print(
        "  ✓ lightgbm.pkl"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")
    print("========================================")
    print("BTC CLASSICAL ML TRAINING")
    print("========================================")

    try:

        # ----------------------------------------------------
        # Check DB configuration
        # ----------------------------------------------------

        missing_config = []

        for key, value in DB_CONFIG.items():

            if not value:

                missing_config.append(
                    key
                )

        if missing_config:

            raise ValueError(
                "Missing database configuration: "
                + ", ".join(missing_config)
            )

        # ----------------------------------------------------
        # Load data
        # ----------------------------------------------------

        print(
            "\nLoading BTC ML data..."
        )

        df = load_data()

        if df.empty:

            print(
                "No data found in btc_ml_features."
            )

            return

        print(
            f"Loaded {len(df)} records."
        )

        # ----------------------------------------------------
        # Train models
        # ----------------------------------------------------

        train_classical_models(
            df
        )

        print(
            "\nTraining completed successfully."
        )

    except Exception as e:

        print(
            "\n========================================"
        )

        print(
            "TRAINING FAILED"
        )

        print(
            "========================================"
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