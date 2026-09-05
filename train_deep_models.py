import os
import mysql.connector
import numpy as np
import pandas as pd

from dotenv import load_dotenv
from sklearn.preprocessing import StandardScaler

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, GRU, Dense, Dropout
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

os.makedirs(MODEL_DIR, exist_ok=True)

SEQUENCE_LENGTH = 30


# ============================================================
# DATABASE
# ============================================================

def load_data():

    conn = mysql.connector.connect(**DB_CONFIG)

    query = """
        SELECT *
        FROM btc_ml_features
        ORDER BY date ASC
    """

    df = pd.read_sql(query, conn)

    conn.close()

    return df


# ============================================================
# CREATE SEQUENCES
# ============================================================

def create_sequences(X, y, sequence_length):

    X_sequences = []
    y_sequences = []

    for i in range(sequence_length, len(X)):

        X_sequences.append(
            X[i-sequence_length:i]
        )

        y_sequences.append(
            y[i]
        )

    return np.array(X_sequences), np.array(y_sequences)


# ============================================================
# MAIN
# ============================================================

def main():

    print("\nLoading data...")

    df = load_data()

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

    X = df[features].values
    y = df["target_return"].values

    # --------------------------------------------------------
    # Scale
    # --------------------------------------------------------

    scaler = StandardScaler()

    X_scaled = scaler.fit_transform(X)

    # Save scaler
    import joblib

    joblib.dump(
        {
            "scaler": scaler,
            "features": features
        },
        f"{MODEL_DIR}/deep_scaler.pkl"
    )

    # --------------------------------------------------------
    # Create sequences
    # --------------------------------------------------------

    X_seq, y_seq = create_sequences(
        X_scaled,
        y,
        SEQUENCE_LENGTH
    )

    train_size = int(len(X_seq) * 0.80)

    X_train = X_seq[:train_size]
    X_test = X_seq[train_size:]

    y_train = y_seq[:train_size]
    y_test = y_seq[train_size:]

    print("\nSequence shape:")
    print(X_seq.shape)

    # ========================================================
    # LSTM
    # ========================================================

    print("\nTraining LSTM...")

    lstm_model = Sequential([
        LSTM(
            64,
            return_sequences=True,
            input_shape=(
                X_train.shape[1],
                X_train.shape[2]
            )
        ),

        Dropout(0.2),

        LSTM(32),

        Dropout(0.2),

        Dense(16, activation="relu"),

        Dense(1)
    ])

    lstm_model.compile(
        optimizer="adam",
        loss="mse"
    )

    early_stop = EarlyStopping(
        monitor="val_loss",
        patience=10,
        restore_best_weights=True
    )

    lstm_model.fit(
        X_train,
        y_train,
        validation_split=0.15,
        epochs=100,
        batch_size=32,
        callbacks=[early_stop],
        verbose=1
    )

    lstm_model.save(
        f"{MODEL_DIR}/lstm.keras"
    )

    # ========================================================
    # GRU
    # ========================================================

    print("\nTraining GRU...")

    gru_model = Sequential([
        GRU(
            64,
            return_sequences=True,
            input_shape=(
                X_train.shape[1],
                X_train.shape[2]
            )
        ),

        Dropout(0.2),

        GRU(32),

        Dropout(0.2),

        Dense(16, activation="relu"),

        Dense(1)
    ])

    gru_model.compile(
        optimizer="adam",
        loss="mse"
    )

    gru_model.fit(
        X_train,
        y_train,
        validation_split=0.15,
        epochs=100,
        batch_size=32,
        callbacks=[early_stop],
        verbose=1
    )

    gru_model.save(
        f"{MODEL_DIR}/gru.keras"
    )

    print("\n========================================")
    print("LSTM & GRU TRAINING COMPLETE")
    print("========================================")


if __name__ == "__main__":
    main()