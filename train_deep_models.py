import os
import mysql.connector
import numpy as np
import pandas as pd
import joblib

from dotenv import load_dotenv
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Input, LSTM, GRU, Dense, Dropout
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

TRAIN_RATIO = 0.80

EPOCHS = 100

BATCH_SIZE = 32


# ============================================================
# DATABASE
# ============================================================

def load_data():

    print("\nConnecting to MySQL...")

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

def create_sequences(X, y, dates, sequence_length):

    X_sequences = []
    y_sequences = []
    sequence_dates = []

    for i in range(sequence_length, len(X)):

        X_sequences.append(
            X[i - sequence_length:i]
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

    # Directional accuracy
    actual_direction = (
        y_true > 0
    ).astype(int)

    predicted_direction = (
        y_pred > 0
    ).astype(int)

    directional_accuracy = (
        actual_direction == predicted_direction
    ).mean() * 100

    return mae, rmse, directional_accuracy


# ============================================================
# BUILD LSTM MODEL
# ============================================================

def build_lstm(input_shape):

    model = Sequential([

        Input(
            shape=input_shape
        ),

        LSTM(
            64,
            return_sequences=True
        ),

        Dropout(0.2),

        LSTM(
            32
        ),

        Dropout(0.2),

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
# BUILD GRU MODEL
# ============================================================

def build_gru(input_shape):

    model = Sequential([

        Input(
            shape=input_shape
        ),

        GRU(
            64,
            return_sequences=True
        ),

        Dropout(0.2),

        GRU(
            32
        ),

        Dropout(0.2),

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
    print("============================================================")
    print("        BTC LSTM & GRU TRAINING")
    print("============================================================")


    # ========================================================
    # LOAD DATA
    # ========================================================

    print("\nLoading data...")

    df = load_data()

    if df.empty:

        raise ValueError(
            "btc_ml_features table is empty."
        )

    print(
        f"Total rows loaded: {len(df)}"
    )


    # ========================================================
    # CLEAN DATA
    # ========================================================

    df["date"] = pd.to_datetime(
        df["date"]
    )

    # Features that must NOT be used as X
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
        f"Number of features: {len(features)}"
    )

    print("\nFeatures:")

    for i, feature in enumerate(features, 1):

        print(
            f"{i:02d}. {feature}"
        )


    # ========================================================
    # KEEP ONLY ROWS WITH VALID TARGET
    # ========================================================

    # For training we need an actual target_return.
    #
    # The latest candle may have NULL target_return because
    # tomorrow's close is not available yet.
    #
    # Therefore:
    # - Training uses rows with known target_return.
    # - We do NOT delete the latest candle from the database.
    # - daily_prediction.py can separately use the latest row.

    training_df = df.dropna(
        subset=["target_return"]
    ).copy()

    if len(training_df) < SEQUENCE_LENGTH + 100:

        raise ValueError(
            f"Not enough training data. "
            f"Required at least {SEQUENCE_LENGTH + 100} rows, "
            f"but only {len(training_df)} rows are available."
        )


    # ========================================================
    # HANDLE FEATURES
    # ========================================================

    X_df = training_df[
        features
    ].copy()

    y = training_df[
        "target_return"
    ].values.astype(np.float32)

    dates = training_df[
        "date"
    ]


    # Replace infinite values
    X_df = X_df.replace(
        [np.inf, -np.inf],
        np.nan
    )

    # Forward fill / backward fill indicators
    X_df = X_df.ffill().bfill()

    # Final safety check
    if X_df.isna().any().any():

        print(
            "\nWARNING: NaN values still exist."
        )

        X_df = X_df.fillna(0)


    X = X_df.values.astype(
        np.float32
    )


    # ========================================================
    # CHRONOLOGICAL TRAIN / TEST SPLIT
    # ========================================================

    split_index = int(
        len(X) * TRAIN_RATIO
    )

    print("\n============================================================")
    print("CHRONOLOGICAL SPLIT")
    print("============================================================")

    print(
        f"Train rows: {split_index}"
    )

    print(
        f"Test rows:  {len(X) - split_index}"
    )

    print(
        f"Train period: "
        f"{training_df['date'].iloc[0].date()} "
        f"→ "
        f"{training_df['date'].iloc[split_index - 1].date()}"
    )

    print(
        f"Test period:  "
        f"{training_df['date'].iloc[split_index].date()} "
        f"→ "
        f"{training_df['date'].iloc[-1].date()}"
    )


    # ========================================================
    # SCALE WITHOUT DATA LEAKAGE
    # ========================================================

    print("\nScaling data...")

    scaler = StandardScaler()

    # IMPORTANT:
    # Fit ONLY on training data
    scaler.fit(
        X[:split_index]
    )

    # Transform entire dataset using
    # training-fitted scaler
    X_scaled = scaler.transform(
        X
    ).astype(np.float32)


    # ========================================================
    # CREATE SEQUENCES
    # ========================================================

    print("\nCreating sequences...")

    X_seq, y_seq, sequence_dates = create_sequences(
        X_scaled,
        y,
        dates,
        SEQUENCE_LENGTH
    )

    print(
        f"Sequence shape: {X_seq.shape}"
    )

    print(
        f"Target shape:   {y_seq.shape}"
    )


    # ========================================================
    # FIND SEQUENCE TRAIN/TEST SPLIT
    # ========================================================

    # Sequence target at index i corresponds to
    # original row i.
    #
    # Therefore the original chronological split index
    # can be used to divide sequences.

    train_sequence_count = sum(
        date < training_df["date"].iloc[split_index]
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


    print("\n============================================================")
    print("SEQUENCE SPLIT")
    print("============================================================")

    print(
        f"Training sequences: {len(X_train)}"
    )

    print(
        f"Testing sequences:  {len(X_test)}"
    )


    if len(X_train) == 0:

        raise ValueError(
            "No training sequences were created."
        )

    if len(X_test) == 0:

        raise ValueError(
            "No test sequences were created."
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
        f"\nScaler saved: {scaler_path}"
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
    print("============================================================")
    print("TRAINING LSTM")
    print("============================================================")

    lstm_model = build_lstm(
        (
            X_train.shape[1],
            X_train.shape[2]
        )
    )

    lstm_model.summary()


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
    # LSTM TEST PREDICTION
    # ========================================================

    print("\nEvaluating LSTM...")

    lstm_pred = lstm_model.predict(
        X_test,
        verbose=0
    ).flatten()

    lstm_mae, lstm_rmse, lstm_directional_accuracy = calculate_metrics(
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
        f"LSTM saved: {lstm_path}"
    )


    # ========================================================
    # GRU
    # ========================================================

    print("\n")
    print("============================================================")
    print("TRAINING GRU")
    print("============================================================")

    gru_model = build_gru(
        (
            X_train.shape[1],
            X_train.shape[2]
        )
    )

    gru_model.summary()


    gru_history = gru_model.fit(

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
    # GRU TEST PREDICTION
    # ========================================================

    print("\nEvaluating GRU...")

    gru_pred = gru_model.predict(
        X_test,
        verbose=0
    ).flatten()

    gru_mae, gru_rmse, gru_directional_accuracy = calculate_metrics(
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
        f"GRU saved: {gru_path}"
    )


    # ========================================================
    # FINAL RESULTS
    # ========================================================

    print("\n")
    print("============================================================")
    print("          DEEP LEARNING RESULTS")
    print("============================================================")

    print(
        f"{'Model':<10}"
        f"{'MAE':<18}"
        f"{'RMSE':<18}"
        f"{'Direction Accuracy'}"
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
    print("============================================================")
    print("LSTM & GRU TRAINING COMPLETE")
    print("============================================================")

    print(
        f"\nModels saved in: {MODEL_DIR}"
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
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()