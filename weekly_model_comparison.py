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
# CREATE PERFORMANCE TABLE
# ============================================================

def create_table():

    conn = get_connection()

    cursor = conn.cursor()

    query = """

    CREATE TABLE IF NOT EXISTS btc_model_performance (

        evaluation_date DATE NOT NULL,

        period_start DATE,

        period_end DATE,

        model_name VARCHAR(50) NOT NULL,

        total_predictions INT,

        mae DOUBLE,

        rmse DOUBLE,

        directional_accuracy DOUBLE,

        avg_predicted_return DOUBLE,

        avg_actual_return DOUBLE,

        total_strategy_return DOUBLE,

        win_rate DOUBLE,

        model_rank INT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        PRIMARY KEY (
            evaluation_date,
            model_name
        )

    )

    """

    cursor.execute(query)

    conn.commit()

    cursor.close()

    conn.close()


# ============================================================
# WEEKLY DATA
# ============================================================

def load_predictions():

    conn = get_connection()

    query = """

    SELECT *

    FROM btc_predictions

    WHERE evaluated = 1

    ORDER BY prediction_date ASC

    """

    df = pd.read_sql(query, conn)

    conn.close()

    return df


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(df):

    results = []

    for model_name, group in df.groupby(
        "model_name"
    ):

        group = group.copy()

        group["error"] = (
            group["predicted_return"]
            - group["actual_return"]
        )

        mae = group["error"].abs().mean()

        rmse = np.sqrt(
            (group["error"] ** 2).mean()
        )

        direction_correct = (

            group["predicted_direction"]
            ==
            group["actual_direction"]

        )

        directional_accuracy = (
            direction_correct.mean()
            * 100
        )

        # --------------------------------------------
        # Simple strategy
        # --------------------------------------------

        group["strategy_return"] = np.where(

            group["predicted_direction"] == 1,

            group["actual_return"],

            -group["actual_return"]

        )

        total_strategy_return = (
            group["strategy_return"].sum()
        )

        win_rate = (
            group["strategy_return"] > 0
        ).mean() * 100

        results.append({

            "model_name":
                model_name,

            "total_predictions":
                len(group),

            "mae":
                mae,

            "rmse":
                rmse,

            "directional_accuracy":
                directional_accuracy,

            "avg_predicted_return":
                group[
                    "predicted_return"
                ].mean(),

            "avg_actual_return":
                group[
                    "actual_return"
                ].mean(),

            "total_strategy_return":
                total_strategy_return,

            "win_rate":
                win_rate

        })

    results_df = pd.DataFrame(results)

    # --------------------------------------------------------
    # Ranking
    # --------------------------------------------------------

    results_df = results_df.sort_values(
        by=[
            "directional_accuracy",
            "total_strategy_return"
        ],
        ascending=False
    )

    results_df["model_rank"] = range(
        1,
        len(results_df) + 1
    )

    return results_df


# ============================================================
# SAVE
# ============================================================

def save_results(results):

    if results.empty:

        return

    conn = get_connection()

    cursor = conn.cursor()

    today = pd.Timestamp.now().date()

    period_end = pd.Timestamp.now().date()

    period_start = (
        pd.Timestamp.now()
        - pd.Timedelta(days=7)
    ).date()

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
        win_rate,
        model_rank
    )

    VALUES

    (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s
    )

    ON DUPLICATE KEY UPDATE

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

        win_rate =
            VALUES(win_rate),

        model_rank =
            VALUES(model_rank)

    """

    for _, row in results.iterrows():

        cursor.execute(
            query,

            (
                today,
                period_start,
                period_end,

                row["model_name"],

                int(row["total_predictions"]),

                float(row["mae"]),

                float(row["rmse"]),

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

                float(row["win_rate"]),

                int(row["model_rank"])
            )
        )

    conn.commit()

    cursor.close()

    conn.close()


# ============================================================
# MAIN
# ============================================================

def main():

    create_table()

    df = load_predictions()

    if df.empty:

        print(
            "No evaluated predictions available."
        )

        return

    results = calculate_metrics(df)

    print("\n")
    print("=" * 80)
    print("BTC MODEL PERFORMANCE")
    print("=" * 80)

    print(
        results[
            [
                "model_name",
                "total_predictions",
                "mae",
                "rmse",
                "directional_accuracy",
                "win_rate",
                "total_strategy_return",
                "model_rank"
            ]
        ].to_string(index=False)
    )

    save_results(results)

    print("\nPerformance saved to database.")

    best_model = results.iloc[0]["model_name"]

    print("\n🏆 CURRENT BEST MODEL:")
    print(best_model)


if __name__ == "__main__":

    main()