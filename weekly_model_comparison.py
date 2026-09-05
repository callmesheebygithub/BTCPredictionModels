# ============================================================
# model_performance.py
#
# BTC Model Performance Evaluation
#
# Evaluates the latest 7 completed prediction days for:
#
#   1. Linear Regression
#   2. Random Forest
#   3. XGBoost
#   4. LightGBM
#   5. LSTM
#   6. GRU
#
# Metrics:
#   - MAE
#   - RMSE
#   - Directional Accuracy
#   - Average Predicted Return
#   - Average Actual Return
#   - Total Strategy Return
#   - Compounded Strategy Return
#   - Win Rate
#   - Model Rank
#
# Important:
#   - Only evaluated predictions are used.
#   - Latest 7 COMPLETED prediction dates are used.
#   - Current unfinished prediction is ignored.
#   - No future leakage.
#   - Automatically updates as new predictions are evaluated.
# ============================================================

import os
import warnings

import mysql.connector
import numpy as np
import pandas as pd

from dotenv import load_dotenv


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

PERFORMANCE_DAYS = 7


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
# CHECK DATABASE CONFIG
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
# CREATE PERFORMANCE TABLE
# ============================================================

def create_table():

    conn = get_connection()

    cursor = conn.cursor()

    query = """

    CREATE TABLE IF NOT EXISTS btc_model_performance (

        evaluation_date DATE NOT NULL,

        period_start DATE NOT NULL,

        period_end DATE NOT NULL,

        model_name VARCHAR(50) NOT NULL,

        total_predictions INT NOT NULL,

        mae DOUBLE,

        rmse DOUBLE,

        directional_accuracy DOUBLE,

        avg_predicted_return DOUBLE,

        avg_actual_return DOUBLE,

        total_strategy_return DOUBLE,

        compounded_strategy_return DOUBLE,

        win_rate DOUBLE,

        model_rank INT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        PRIMARY KEY (
            evaluation_date,
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
# CHECK / ADD NEW COLUMN IF TABLE ALREADY EXISTS
# ============================================================

def migrate_table():

    """
    CREATE TABLE IF NOT EXISTS does not modify an existing
    table.

    Therefore, if btc_model_performance already existed
    without compounded_strategy_return, add it safely.
    """

    conn = get_connection()

    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SHOW COLUMNS
            FROM btc_model_performance
            LIKE 'compounded_strategy_return'
            """
        )

        result = cursor.fetchone()

        if result is None:

            print(
                "Adding compounded_strategy_return "
                "column..."
            )

            cursor.execute(
                """
                ALTER TABLE btc_model_performance
                ADD COLUMN compounded_strategy_return DOUBLE
                AFTER total_strategy_return
                """
            )

            conn.commit()

            print(
                "Column added successfully."
            )

    finally:

        cursor.close()

        conn.close()


# ============================================================
# LOAD EVALUATED PREDICTIONS
# ============================================================

def load_predictions():

    conn = get_connection()

    query = """

    SELECT

        prediction_date,

        model_name,

        current_close,

        predicted_return,

        predicted_price,

        predicted_direction,

        actual_return,

        actual_price,

        actual_direction,

        evaluated

    FROM btc_predictions

    WHERE
        evaluated = 1

        AND actual_return IS NOT NULL

        AND actual_price IS NOT NULL

        AND actual_direction IS NOT NULL

    ORDER BY
        prediction_date ASC,
        model_name ASC

    """

    try:

        df = pd.read_sql(
            query,
            conn
        )

    finally:

        conn.close()

    if df.empty:

        return df

    # --------------------------------------------------------
    # Normalize dates
    # --------------------------------------------------------

    df["prediction_date"] = pd.to_datetime(
        df["prediction_date"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Remove invalid rows
    # --------------------------------------------------------

    df = df.dropna(
        subset=[
            "prediction_date",
            "predicted_return",
            "actual_return",
            "predicted_direction",
            "actual_direction"
        ]
    ).copy()

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    df = df.sort_values(
        [
            "prediction_date",
            "model_name"
        ]
    ).reset_index(
        drop=True
    )

    return df


# ============================================================
# SELECT LATEST COMPLETED PREDICTION DAYS
# ============================================================

def select_latest_period(df):

    if df.empty:

        return df, None, None

    # --------------------------------------------------------
    # Get unique completed prediction dates
    # --------------------------------------------------------

    unique_dates = sorted(
        df["prediction_date"]
        .dt.date
        .unique()
    )

    if not unique_dates:

        return df.iloc[0:0], None, None

    # --------------------------------------------------------
    # Last 7 completed prediction days
    # --------------------------------------------------------

    selected_dates = unique_dates[
        -PERFORMANCE_DAYS:
    ]

    period_start = selected_dates[0]

    period_end = selected_dates[-1]

    period_df = df[
        df["prediction_date"]
        .dt.date
        .isin(selected_dates)
    ].copy()

    return (
        period_df,
        period_start,
        period_end
    )


# ============================================================
# CALCULATE COMPOUNDED STRATEGY RETURN
# ============================================================

def calculate_compounded_return(
    strategy_returns
):

    if len(strategy_returns) == 0:

        return 0.0

    # --------------------------------------------------------
    # Each day's strategy return is treated as a percentage
    # return on the portfolio.
    #
    # Example:
    #
    # Day 1 = +5%
    # Day 2 = +3%
    #
    # Compounded:
    #
    # (1.05 * 1.03) - 1 = 8.15%
    # --------------------------------------------------------

    compounded = np.prod(
        1 + strategy_returns
    ) - 1

    return float(
        compounded
    )


# ============================================================
# CALCULATE MODEL METRICS
# ============================================================

def calculate_metrics(df):

    if df.empty:

        return pd.DataFrame()

    results = []

    # --------------------------------------------------------
    # Evaluate each model separately
    # --------------------------------------------------------

    for model_name, group in df.groupby(
        "model_name"
    ):

        group = group.copy()

        # ----------------------------------------------------
        # Error
        # ----------------------------------------------------

        group["error"] = (
            group["predicted_return"]
            -
            group["actual_return"]
        )

        # ----------------------------------------------------
        # MAE
        # ----------------------------------------------------

        mae = (
            group["error"]
            .abs()
            .mean()
        )

        # ----------------------------------------------------
        # RMSE
        # ----------------------------------------------------

        rmse = np.sqrt(
            (
                group["error"] ** 2
            ).mean()
        )

        # ----------------------------------------------------
        # Directional Accuracy
        # ----------------------------------------------------

        direction_correct = (

            group["predicted_direction"]
            ==
            group["actual_direction"]

        )

        directional_accuracy = (
            direction_correct.mean()
            * 100
        )

        # ----------------------------------------------------
        # Long / Short strategy
        #
        # Prediction UP:
        #     profit = actual return
        #
        # Prediction DOWN:
        #     profit = -actual return
        # ----------------------------------------------------

        group["strategy_return"] = np.where(

            group["predicted_direction"] == 1,

            group["actual_return"],

            -group["actual_return"]

        )

        # ----------------------------------------------------
        # Total strategy return
        # ----------------------------------------------------

        total_strategy_return = (
            group["strategy_return"]
            .sum()
        )

        # ----------------------------------------------------
        # Compounded strategy return
        # ----------------------------------------------------

        compounded_strategy_return = (
            calculate_compounded_return(
                group["strategy_return"]
                .values
            )
        )

        # ----------------------------------------------------
        # Win rate
        # ----------------------------------------------------

        win_rate = (

            (
                group["strategy_return"]
                > 0
            ).mean()

            * 100

        )

        # ----------------------------------------------------
        # Average predicted return
        # ----------------------------------------------------

        avg_predicted_return = (
            group["predicted_return"]
            .mean()
        )

        # ----------------------------------------------------
        # Average actual return
        # ----------------------------------------------------

        avg_actual_return = (
            group["actual_return"]
            .mean()
        )

        results.append({

            "model_name":
                model_name,

            "total_predictions":
                len(group),

            "mae":
                float(mae),

            "rmse":
                float(rmse),

            "directional_accuracy":
                float(
                    directional_accuracy
                ),

            "avg_predicted_return":
                float(
                    avg_predicted_return
                ),

            "avg_actual_return":
                float(
                    avg_actual_return
                ),

            "total_strategy_return":
                float(
                    total_strategy_return
                ),

            "compounded_strategy_return":
                float(
                    compounded_strategy_return
                ),

            "win_rate":
                float(
                    win_rate
                )
        })

    results_df = pd.DataFrame(
        results
    )

    if results_df.empty:

        return results_df

    # ========================================================
    # MODEL RANKING
    #
    # Primary:
    #   Directional Accuracy
    #
    # Secondary:
    #   Compounded Strategy Return
    #
    # Tertiary:
    #   Lower RMSE
    # ========================================================

    results_df = results_df.sort_values(

        by=[
            "directional_accuracy",
            "compounded_strategy_return",
            "rmse"
        ],

        ascending=[
            False,
            False,
            True
        ]
    ).reset_index(
        drop=True
    )

    results_df["model_rank"] = (
        np.arange(
            1,
            len(results_df) + 1
        )
    )

    return results_df


# ============================================================
# SAVE PERFORMANCE
# ============================================================

def save_results(
    results,
    period_start,
    period_end
):

    if results.empty:

        print(
            "No performance results to save."
        )

        return

    conn = get_connection()

    cursor = conn.cursor()

    # --------------------------------------------------------
    # Evaluation date
    #
    # Use the actual latest completed prediction date rather
    # than the computer's current date.
    # --------------------------------------------------------

    evaluation_date = period_end

    query = """

    INSERT INTO btc_model_performance

    (

        evaluation_date,

        period_start,

        period_end,

        model_name,

        total_predictions,

        mae,

        rmse,

        directional_accuracy,

        avg_predicted_return,

        avg_actual_return,

        total_strategy_return,

        compounded_strategy_return,

        win_rate,

        model_rank

    )

    VALUES

    (

        %s,

        %s,

        %s,

        %s,

        %s,

        %s,

        %s,

        %s,

        %s,

        %s,

        %s,

        %s,

        %s,

        %s

    )

    ON DUPLICATE KEY UPDATE

        period_start =
            VALUES(period_start),

        period_end =
            VALUES(period_end),

        total_predictions =
            VALUES(total_predictions),

        mae =
            VALUES(mae),

        rmse =
            VALUES(rmse),

        directional_accuracy =
            VALUES(directional_accuracy),

        avg_predicted_return =
            VALUES(avg_predicted_return),

        avg_actual_return =
            VALUES(avg_actual_return),

        total_strategy_return =
            VALUES(total_strategy_return),

        compounded_strategy_return =
            VALUES(compounded_strategy_return),

        win_rate =
            VALUES(win_rate),

        model_rank =
            VALUES(model_rank),

        created_at =
            CURRENT_TIMESTAMP

    """

    try:

        for _, row in results.iterrows():

            cursor.execute(

                query,

                (

                    evaluation_date,

                    period_start,

                    period_end,

                    row["model_name"],

                    int(
                        row["total_predictions"]
                    ),

                    float(
                        row["mae"]
                    ),

                    float(
                        row["rmse"]
                    ),

                    float(
                        row["directional_accuracy"]
                    ),

                    float(
                        row["avg_predicted_return"]
                    ),

                    float(
                        row["avg_actual_return"]
                    ),

                    float(
                        row["total_strategy_return"]
                    ),

                    float(
                        row[
                            "compounded_strategy_return"
                        ]
                    ),

                    float(
                        row["win_rate"]
                    ),

                    int(
                        row["model_rank"]
                    )
                )
            )

        conn.commit()

    finally:

        cursor.close()

        conn.close()

    print(
        "\nPerformance successfully saved "
        "to btc_model_performance."
    )


# ============================================================
# DISPLAY PERFORMANCE
# ============================================================

def display_results(
    results,
    period_start,
    period_end
):

    print("\n")

    print(
        "=" * 110
    )

    print(
        "BTC MODEL PERFORMANCE"
    )

    print(
        "=" * 110
    )

    print(
        f"Evaluation period: "
        f"{period_start} → {period_end}"
    )

    print(
        f"Performance window: "
        f"Latest {PERFORMANCE_DAYS} completed prediction days"
    )

    print(
        "=" * 110
    )

    if results.empty:

        print(
            "No performance data available."
        )

        return

    display_df = results.copy()

    # --------------------------------------------------------
    # Format percentages for display
    # --------------------------------------------------------

    display_df["MAE"] = (
        display_df["mae"]
        .map(
            lambda x: f"{x:.4%}"
        )
    )

    display_df["RMSE"] = (
        display_df["rmse"]
        .map(
            lambda x: f"{x:.4%}"
        )
    )

    display_df["Direction Accuracy"] = (
        display_df[
            "directional_accuracy"
        ]
        .map(
            lambda x: f"{x:.2f}%"
        )
    )

    display_df["Win Rate"] = (
        display_df[
            "win_rate"
        ]
        .map(
            lambda x: f"{x:.2f}%"
        )
    )

    display_df["Avg Predicted Return"] = (
        display_df[
            "avg_predicted_return"
        ]
        .map(
            lambda x: f"{x:+.4%}"
        )
    )

    display_df["Avg Actual Return"] = (
        display_df[
            "avg_actual_return"
        ]
        .map(
            lambda x: f"{x:+.4%}"
        )
    )

    display_df["Total Strategy Return"] = (
        display_df[
            "total_strategy_return"
        ]
        .map(
            lambda x: f"{x:+.4%}"
        )
    )

    display_df["Compounded Strategy Return"] = (
        display_df[
            "compounded_strategy_return"
        ]
        .map(
            lambda x: f"{x:+.4%}"
        )
    )

    final_display = display_df[

        [

            "model_rank",

            "model_name",

            "total_predictions",

            "MAE",

            "RMSE",

            "Direction Accuracy",

            "Win Rate",

            "Avg Predicted Return",

            "Avg Actual Return",

            "Total Strategy Return",

            "Compounded Strategy Return"

        ]

    ].rename(

        columns={

            "model_rank":
                "Rank",

            "model_name":
                "Model",

            "total_predictions":
                "Predictions"

        }

    )

    print(
        final_display.to_string(
            index=False
        )
    )

    print(
        "=" * 110
    )


# ============================================================
# SHOW BEST MODEL
# ============================================================

def display_best_model(results):

    if results.empty:

        return

    best_model = results.iloc[0]

    print("\n")

    print(
        "🏆 CURRENT BEST MODEL"
    )

    print(
        "-" * 50
    )

    print(
        f"Model: "
        f"{best_model['model_name']}"
    )

    print(
        f"Rank: "
        f"{int(best_model['model_rank'])}"
    )

    print(
        f"Directional Accuracy: "
        f"{best_model['directional_accuracy']:.2f}%"
    )

    print(
        f"Win Rate: "
        f"{best_model['win_rate']:.2f}%"
    )

    print(
        f"Compounded Strategy Return: "
        f"{best_model['compounded_strategy_return']:+.4%}"
    )

    print(
        "-" * 50
    )


# ============================================================
# SHOW DATA STATUS
# ============================================================

def display_data_status(
    df,
    period_df
):

    print("\n")

    print(
        "DATA STATUS"
    )

    print(
        "-" * 50
    )

    print(
        f"Total evaluated predictions: "
        f"{len(df)}"
    )

    print(
        f"Latest {PERFORMANCE_DAYS}-day predictions: "
        f"{len(period_df)}"
    )

    if not period_df.empty:

        unique_dates = (
            period_df[
                "prediction_date"
            ]
            .dt.date
            .nunique()
        )

        print(
            f"Completed prediction days: "
            f"{unique_dates}"
        )

        print(
            f"Period: "
            f"{period_df['prediction_date'].min().date()}"
            f" → "
            f"{period_df['prediction_date'].max().date()}"
        )

    print(
        "-" * 50
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")

    print(
        "=" * 110
    )

    print(
        "BTC MODEL PERFORMANCE EVALUATION"
    )

    print(
        "=" * 110
    )

    try:

        # ----------------------------------------------------
        # Validate database config
        # ----------------------------------------------------

        validate_config()

        # ----------------------------------------------------
        # Create performance table
        # ----------------------------------------------------

        create_table()

        # ----------------------------------------------------
        # Migrate existing table if necessary
        # ----------------------------------------------------

        migrate_table()

        # ----------------------------------------------------
        # Load evaluated predictions
        # ----------------------------------------------------

        print(
            "\nLoading evaluated predictions..."
        )

        df = load_predictions()

        if df.empty:

            print(
                "\nNo evaluated predictions available."
            )

            print(
                "Run daily_btc_prediction.py first "
                "and wait until actual data becomes available."
            )

            return

        # ----------------------------------------------------
        # Select latest 7 completed prediction days
        # ----------------------------------------------------

        period_df, period_start, period_end = (
            select_latest_period(
                df
            )
        )

        if period_df.empty:

            print(
                "\nNo completed prediction period available."
            )

            return

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        display_data_status(
            df,
            period_df
        )

        # ----------------------------------------------------
        # Calculate metrics
        # ----------------------------------------------------

        results = calculate_metrics(
            period_df
        )

        if results.empty:

            print(
                "\nCould not calculate model performance."
            )

            return

        # ----------------------------------------------------
        # Display
        # ----------------------------------------------------

        display_results(

            results,

            period_start,

            period_end

        )

        # ----------------------------------------------------
        # Best model
        # ----------------------------------------------------

        display_best_model(
            results
        )

        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        save_results(

            results,

            period_start,

            period_end

        )

        # ----------------------------------------------------
        # Complete
        # ----------------------------------------------------

        print("\n")

        print(
            "=" * 110
        )

        print(
            "MODEL PERFORMANCE COMPLETED SUCCESSFULLY"
        )

        print(
            "=" * 110
        )

    except Exception as e:

        print("\n")

        print(
            "=" * 110
        )

        print(
            "MODEL PERFORMANCE FAILED"
        )

        print(
            "=" * 110
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