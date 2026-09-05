import os
import warnings
import joblib
import mysql.connector
import numpy as np
import pandas as pd

from dotenv import load_dotenv

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

warnings.filterwarnings("ignore")

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
os.makedirs(MODEL_DIR, exist_ok=True)

# ============================================================
# DATABASE
# ============================================================

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def load_data():

    conn = get_connection()

    query = """
        SELECT *
        FROM btc_ml_features
        ORDER BY date ASC
    """

    df = pd.read_sql(query, conn)

    conn.close()

    return df


# ============================================================
# FEATURE SELECTION
# ============================================================

def get_feature_columns(df):

    excluded_columns = [
        "date",
        "target_return",
        "target_direction"
    ]

    features = [
        col for col in df.columns
        if col not in excluded_columns
    ]

    return features


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(y_true, y_pred):

    mae = mean_absolute_error(y_true, y_pred)

    rmse = np.sqrt(
        mean_squared_error(y_true, y_pred)
    )

    r2 = r2_score(y_true, y_pred)

    directional_accuracy = np.mean(
        np.sign(y_true) == np.sign(y_pred)
    ) * 100

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

    features = get_feature_columns(df)

    X = df[features]
    y = df["target_return"]

    # --------------------------------------------------------
    # Chronological split
    # --------------------------------------------------------

    train_size = int(len(df) * 0.80)

    X_train = X.iloc[:train_size]
    X_test = X.iloc[train_size:]

    y_train = y.iloc[:train_size]
    y_test = y.iloc[train_size:]

    print("\n========================================")
    print("TRAINING CLASSICAL MODELS")
    print("========================================")

    print(f"Total records : {len(df)}")
    print(f"Training      : {len(X_train)}")
    print(f"Testing       : {len(X_test)}")

    # ========================================================
    # 1. LINEAR REGRESSION
    # ========================================================

    print("\nTraining Linear Regression...")

    linear_model = LinearRegression()

    linear_model.fit(
        X_train,
        y_train
    )

    linear_pred = linear_model.predict(X_test)

    metrics = calculate_metrics(
        y_test,
        linear_pred
    )

    print("Linear Regression:")
    print(metrics)

    joblib.dump(
        {
            "model": linear_model,
            "features": features
        },
        f"{MODEL_DIR}/linear_regression.pkl"
    )

    # ========================================================
    # 2. RANDOM FOREST
    # ========================================================

    print("\nTraining Random Forest...")

    rf_model = RandomForestRegressor(
        n_estimators=300,
        max_depth=12,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    )

    rf_model.fit(
        X_train,
        y_train
    )

    rf_pred = rf_model.predict(X_test)

    metrics = calculate_metrics(
        y_test,
        rf_pred
    )

    print("Random Forest:")
    print(metrics)

    joblib.dump(
        {
            "model": rf_model,
            "features": features
        },
        f"{MODEL_DIR}/random_forest.pkl"
    )

    # ========================================================
    # 3. XGBOOST
    # ========================================================

    print("\nTraining XGBoost...")

    xgb_model = XGBRegressor(
        n_estimators=500,
        learning_rate=0.03,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=-1
    )

    xgb_model.fit(
        X_train,
        y_train
    )

    xgb_pred = xgb_model.predict(X_test)

    metrics = calculate_metrics(
        y_test,
        xgb_pred
    )

    print("XGBoost:")
    print(metrics)

    joblib.dump(
        {
            "model": xgb_model,
            "features": features
        },
        f"{MODEL_DIR}/xgboost.pkl"
    )

    # ========================================================
    # 4. LIGHTGBM
    # ========================================================

    print("\nTraining LightGBM...")

    lgb_model = LGBMRegressor(
        n_estimators=500,
        learning_rate=0.03,
        max_depth=8,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=-1
    )

    lgb_model.fit(
        X_train,
        y_train
    )

    lgb_pred = lgb_model.predict(X_test)

    metrics = calculate_metrics(
        y_test,
        lgb_pred
    )

    print("LightGBM:")
    print(metrics)

    joblib.dump(
        {
            "model": lgb_model,
            "features": features
        },
        f"{MODEL_DIR}/lightgbm.pkl"
    )

    print("\n========================================")
    print("CLASSICAL MODELS TRAINED")
    print("========================================")


# ============================================================
# MAIN
# ============================================================

def main():

    print("\nLoading BTC ML data...")

    df = load_data()

    if df.empty:
        print("No data found in btc_ml_features.")
        return

    print(f"Loaded {len(df)} records.")

    train_classical_models(df)

    print("\nTraining completed successfully.")

    print("\nModels saved in:")
    print(os.path.abspath(MODEL_DIR))


if __name__ == "__main__":
    main()