"""
train_btc_models.py

Train:
    LSTM
    GRU

Data source:
    btc_ml_features

Important:
    Rows with NULL target_return are NOT used for training.

Example:

    Sep 3:
        Features available
        target_return = Sep 4 return
        → TRAINING

    Sep 4:
        Features available
        target_return = NULL
        → NOT TRAINING

    Sep 4 will be used later by daily_prediction.py
    to predict Sep 5.
"""

import os
import mysql.connector
import numpy as np
import pandas as pd
import joblib

from dotenv import load_dotenv

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error
)

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import (
    Input,
    LSTM,
    GRU,
    Dense,
    Dropout
)

from tensorflow.keras.callbacks import EarlyStopping


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

os.makedirs(
    MODEL_DIR,
    exist_ok=True
)

SEQUENCE_LENGTH = 30

TRAIN_RATIO = 0.80

EPOCHS = 100

BATCH_SIZE = 32


# ============================================================
# DATABASE
# ============================================================

def load_data():

    print(
        "\nConnecting to MySQL..."
    )

    conn = mysql.connector.connect(
        **DB_CONFIG
    )

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
# CREATE SEQUENCES
# ============================================================

def create_sequences(
    X,
    y,
    dates,
    sequence_length
):

    X_sequences = []
    y_sequences = []
    sequence_dates = []

    for i in range(
        sequence_length,
        len(X)
    ):

        X_sequences.append(
            X[
                i - sequence_length:i
            ]
        )

        y_sequences.append(
            y[i]
        )

        sequence_dates.append(
            dates.iloc[i]
        )

    return (
        np.array(X_sequences),
        np.array(y_sequences),
        sequence_dates
    )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    y_true,
    y_pred
):

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

    actual_direction = (
        y_true > 0
    ).astype(int)

    predicted_direction = (
        y_pred > 0
    ).astype(int)

    directional_accuracy = (
        actual_direction
        ==
        predicted_direction
    ).mean() * 100

    return (
        mae,
        rmse,
        directional_accuracy
    )


# ============================================================
# BUILD LSTM
# ============================================================

def build_lstm(
    input_shape
):

    model = Sequential([

        Input(
            shape=input_shape
        ),

        LSTM(
            64,
            return_sequences=True
        ),

        Dropout(
            0.2
        ),

        LSTM(
            32
        ),

        Dropout(
            0.2
        ),

        Dense(
            16,
            activation="relu"
        ),

        Dense(
            1
        )
    ])

    model.compile(
        optimizer="adam",
        loss="mse"
    )

    return model


# ============================================================
# BUILD GRU
# ============================================================

def build_gru(
    input_shape
):

    model = Sequential([

        Input(
            shape=input_shape
        ),

        GRU(
            64,
            return_sequences=True
        ),

        Dropout(
            0.2
        ),

        GRU(
            32
        ),

        Dropout(
            0.2
        ),

        Dense(
            16,
            activation="relu"
        ),

        Dense(
            1
        )
    ])

    model.compile(
        optimizer="adam",
        loss="mse"
    )

    return model


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")
    print("=" * 60)
    print(
        "        BTC LSTM & GRU TRAINING"
    )
    print("=" * 60)

    # ========================================================
    # LOAD DATA
    # ========================================================

    print(
        "\nLoading data..."
    )

    df = load_data()

    if df.empty:

        raise ValueError(
            "btc_ml_features table is empty."
        )

    print(
        f"Total rows loaded: {len(df)}"
    )

    df["date"] = pd.to_datetime(
        df["date"]
    )

    df = df.sort_values(
        "date"
    ).reset_index(
        drop=True
    )

    print(
        f"Date range: "
        f"{df['date'].min().date()} "
        f"→ "
        f"{df['date'].max().date()}"
    )

    # ========================================================
    # FEATURES
    # ========================================================

    excluded = [
        "date",
        "target_return",
        "target_direction"
    ]

    features = [
        col
        for col in df.columns
        if col not in excluded
    ]

    print(
        f"\nNumber of features: "
        f"{len(features)}"
    )

    # ========================================================
    # TRAINING DATA
    # ========================================================

    training_df = df[
        df["target_return"].notna()
    ].copy()

    print(
        f"\nRows with known target: "
        f"{len(training_df)}"
    )

    if len(training_df) == 0:

        raise ValueError(
            "No rows with known target_return."
        )

    print(
        f"Training target range: "
        f"{training_df['date'].min().date()} "
        f"→ "
        f"{training_df['date'].max().date()}"
    )

    # ========================================================
    # PREPARE X/Y
    # ========================================================

    X_df = training_df[
        features
    ].copy()

    y = training_df[
        "target_return"
    ].values.astype(
        np.float32
    )

    dates = training_df[
        "date"
    ].reset_index(
        drop=True
    )

    # ========================================================
    # CLEAN FEATURES
    # ========================================================

    X_df = X_df.replace(
        [np.inf, -np.inf],
        np.nan
    )

    # At this point feature preparation should already
    # have removed insufficient-history rows.

    if X_df.isna().any().any():

        print(
            "\n⚠️ Missing feature values detected."
        )

        print(
            X_df.isna().sum()[
                X_df.isna().sum() > 0
            ]
        )

        X_df = X_df.ffill().bfill()

    if X_df.isna().any().any():

        X_df = X_df.fillna(0)

    X = X_df.values.astype(
        np.float32
    )

    # ========================================================
    # CHRONOLOGICAL SPLIT
    # ========================================================

    split_index = int(
        len(X)
        * TRAIN_RATIO
    )

    if split_index <= SEQUENCE_LENGTH:

        raise ValueError(
            "Training portion is too small "
            "for sequence generation."
        )

    if split_index >= len(X):

        raise ValueError(
            "Test set is empty."
        )

    print("\n")
    print("=" * 60)
    print(
        "CHRONOLOGICAL SPLIT"
    )
    print("=" * 60)

    print(
        f"Train rows: {split_index}"
    )

    print(
        f"Test rows: "
        f"{len(X) - split_index}"
    )

    print(
        f"Train period: "
        f"{dates.iloc[0].date()} "
        f"→ "
        f"{dates.iloc[split_index - 1].date()}"
    )

    print(
        f"Test period: "
        f"{dates.iloc[split_index].date()} "
        f"→ "
        f"{dates.iloc[-1].date()}"
    )

    # ========================================================
    # SCALE
    # ========================================================

    print(
        "\nScaling data..."
    )

    scaler = StandardScaler()

    scaler.fit(
        X[:split_index]
    )

    X_scaled = scaler.transform(
        X
    ).astype(
        np.float32
    )

    # ========================================================
    # SEQUENCES
    # ========================================================

    print(
        "\nCreating sequences..."
    )

    X_seq, y_seq, sequence_dates = create_sequences(
        X_scaled,
        y,
        dates,
        SEQUENCE_LENGTH
    )

    print(
        f"Sequence shape: "
        f"{X_seq.shape}"
    )

    print(
        f"Target shape: "
        f"{y_seq.shape}"
    )

    # ========================================================
    # SEQUENCE TRAIN / TEST SPLIT
    # ========================================================

    split_date = dates.iloc[
        split_index
    ]

    train_sequence_count = sum(
        date < split_date
        for date in sequence_dates
    )

    X_train = X_seq[
        :train_sequence_count
    ]

    y_train = y_seq[
        :train_sequence_count
    ]

    X_test = X_seq[
        train_sequence_count:
    ]

    y_test = y_seq[
        train_sequence_count:
    ]

    print("\n")
    print("=" * 60)
    print(
        "SEQUENCE SPLIT"
    )
    print("=" * 60)

    print(
        f"Training sequences: "
        f"{len(X_train)}"
    )

    print(
        f"Testing sequences: "
        f"{len(X_test)}"
    )

    if len(X_train) == 0:

        raise ValueError(
            "No training sequences."
        )

    if len(X_test) == 0:

        raise ValueError(
            "No testing sequences."
        )

    # ========================================================
    # SAVE SCALER
    # ========================================================

    scaler_path = os.path.join(
        MODEL_DIR,
        "deep_scaler.pkl"
    )

    joblib.dump(
        {
            "scaler": scaler,
            "features": features,
            "sequence_length": SEQUENCE_LENGTH
        },
        scaler_path
    )

    print(
        f"\nScaler saved: "
        f"{scaler_path}"
    )

    # ========================================================
    # EARLY STOPPING
    # ========================================================

    early_stop = EarlyStopping(

        monitor="val_loss",

        patience=10,

        restore_best_weights=True
    )

    # ========================================================
    # LSTM
    # ========================================================

    print("\n")
    print("=" * 60)
    print(
        "TRAINING LSTM"
    )
    print("=" * 60)

    lstm_model = build_lstm(
        (
            X_train.shape[1],
            X_train.shape[2]
        )
    )

    lstm_history = lstm_model.fit(

        X_train,

        y_train,

        validation_split=0.15,

        epochs=EPOCHS,

        batch_size=BATCH_SIZE,

        callbacks=[
            early_stop
        ],

        shuffle=False,

        verbose=1
    )

    # ========================================================
    # LSTM EVALUATION
    # ========================================================

    print(
        "\nEvaluating LSTM..."
    )

    lstm_pred = lstm_model.predict(
        X_test,
        verbose=0
    ).flatten()

    (
        lstm_mae,
        lstm_rmse,
        lstm_directional_accuracy
    ) = calculate_metrics(
        y_test,
        lstm_pred
    )

    print(
        f"LSTM MAE: "
        f"{lstm_mae:.8f}"
    )

    print(
        f"LSTM RMSE: "
        f"{lstm_rmse:.8f}"
    )

    print(
        f"LSTM Directional Accuracy: "
        f"{lstm_directional_accuracy:.2f}%"
    )

    # ========================================================
    # SAVE LSTM
    # ========================================================

    lstm_path = os.path.join(
        MODEL_DIR,
        "lstm.keras"
    )

    lstm_model.save(
        lstm_path
    )

    print(
        f"LSTM saved: "
        f"{lstm_path}"
    )

    # ========================================================
    # GRU
    # ========================================================

    print("\n")
    print("=" * 60)
    print(
        "TRAINING GRU"
    )
    print("=" * 60)

    gru_model = build_gru(
        (
            X_train.shape[1],
            X_train.shape[2]
        )
    )

    # New EarlyStopping object because the previous callback
    # has already been used by LSTM.

    gru_early_stop = EarlyStopping(

        monitor="val_loss",

        patience=10,

        restore_best_weights=True
    )

    gru_history = gru_model.fit(

        X_train,

        y_train,

        validation_split=0.15,

        epochs=EPOCHS,

        batch_size=BATCH_SIZE,

        callbacks=[
            gru_early_stop
        ],

        shuffle=False,

        verbose=1
    )

    # ========================================================
    # GRU EVALUATION
    # ========================================================

    print(
        "\nEvaluating GRU..."
    )

    gru_pred = gru_model.predict(
        X_test,
        verbose=0
    ).flatten()

    (
        gru_mae,
        gru_rmse,
        gru_directional_accuracy
    ) = calculate_metrics(
        y_test,
        gru_pred
    )

    print(
        f"GRU MAE: "
        f"{gru_mae:.8f}"
    )

    print(
        f"GRU RMSE: "
        f"{gru_rmse:.8f}"
    )

    print(
        f"GRU Directional Accuracy: "
        f"{gru_directional_accuracy:.2f}%"
    )

    # ========================================================
    # SAVE GRU
    # ========================================================

    gru_path = os.path.join(
        MODEL_DIR,
        "gru.keras"
    )

    gru_model.save(
        gru_path
    )

    print(
        f"GRU saved: "
        f"{gru_path}"
    )

    # ========================================================
    # FINAL RESULTS
    # ========================================================

    print("\n")
    print("=" * 60)
    print(
        "          DEEP LEARNING RESULTS"
    )
    print("=" * 60)

    print(
        f"{'Model':<10}"
        f"{'MAE':<18}"
        f"{'RMSE':<18}"
        f"Direction Accuracy"
    )

    print(
        f"{'LSTM':<10}"
        f"{lstm_mae:<18.8f}"
        f"{lstm_rmse:<18.8f}"
        f"{lstm_directional_accuracy:.2f}%"
    )

    print(
        f"{'GRU':<10}"
        f"{gru_mae:<18.8f}"
        f"{gru_rmse:<18.8f}"
        f"{gru_directional_accuracy:.2f}%"
    )

    print("\n")
    print("=" * 60)
    print(
        "LSTM & GRU TRAINING COMPLETE"
    )
    print("=" * 60)

    print(
        f"\nModels saved in: "
        f"{MODEL_DIR}"
    )

    print(
        "\nGenerated files:"
    )

    print(
        " - models/deep_scaler.pkl"
    )

    print(
        " - models/lstm.keras"
    )

    print(
        " - models/gru.keras"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()