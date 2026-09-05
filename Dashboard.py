# ============================================================
# btc_dashboard_streamlit.py
# BTC Technical Analysis + ML Prediction Dashboard
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import os
import sys

# MySQL
import mysql.connector
from mysql.connector import Error

# Auto refresh
try:
    from streamlit_autorefresh import st_autorefresh
    AUTO_REFRESH_AVAILABLE = True
except ImportError:
    AUTO_REFRESH_AVAILABLE = False

# dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ============================================================
# IMPORT EXISTING INDICATOR MODULE
# ============================================================

try:
    from btc_indicators import BTCIndicators
except ImportError:
    st.error("❌ btc_indicators.py not found!")
    st.stop()


# ============================================================
# IMPORT EMAIL SENDER
# ============================================================

try:
    from btc_email_sender import BTCEmailSender
except ImportError:
    BTCEmailSender = None


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="BTC AI Trading Dashboard",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

.main-header {
    background: linear-gradient(135deg, #f7931a, #f9a825);
    padding: 20px;
    border-radius: 10px;
    color: white;
    text-align: center;
    margin-bottom: 30px;
}

.main-header h1 {
    margin-bottom: 5px;
}

.main-header p {
    margin: 0;
    font-size: 16px;
}

.metric-card {
    background: #1e1e2f;
    padding: 20px;
    border-radius: 10px;
    border-left: 4px solid #f7931a;
    margin: 10px 0;
}

.ml-header {
    background: linear-gradient(135deg, #111827, #1f2937);
    padding: 20px;
    border-radius: 12px;
    color: white;
    margin-top: 30px;
    margin-bottom: 20px;
    border-left: 5px solid #f7931a;
}

.winner-card {
    background: linear-gradient(135deg, #1e1e2f, #25253d);
    padding: 25px;
    border-radius: 15px;
    border: 2px solid #f7931a;
    text-align: center;
    margin-bottom: 20px;
}

.winner-model {
    font-size: 30px;
    font-weight: bold;
    color: #f7931a;
}

.winner-label {
    font-size: 14px;
    color: #aaa;
    margin-bottom: 8px;
}

.prediction-up {
    color: #00ff88;
    font-weight: bold;
}

.prediction-down {
    color: #ff4757;
    font-weight: bold;
}

.prediction-neutral {
    color: #ffd93d;
    font-weight: bold;
}

.signal-buy {
    background: #00ff88;
    color: #000;
    padding: 10px;
    border-radius: 10px;
    text-align: center;
    font-weight: bold;
    font-size: 24px;
}

.signal-sell {
    background: #ff4757;
    color: #fff;
    padding: 10px;
    border-radius: 10px;
    text-align: center;
    font-weight: bold;
    font-size: 24px;
}

.signal-neutral {
    background: #ffd93d;
    color: #000;
    padding: 10px;
    border-radius: 10px;
    text-align: center;
    font-weight: bold;
    font-size: 24px;
}

.confidence-high {
    color: #00ff88;
    font-weight: bold;
}

.confidence-medium {
    color: #ffd93d;
    font-weight: bold;
}

.confidence-low {
    color: #ff6b6b;
    font-weight: bold;
}

.stButton button {
    width: 100%;
    background: #f7931a;
    color: white;
    font-weight: bold;
    font-size: 16px;
    padding: 10px;
}

.stButton button:hover {
    background: #f9a825;
}

.info-box {
    background: #1e1e2f;
    padding: 15px;
    border-radius: 10px;
    border-left: 4px solid #f7931a;
    margin: 10px 0;
}

.section-divider {
    margin-top: 30px;
    margin-bottom: 30px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# SESSION STATE
# ============================================================

if "results" not in st.session_state:
    st.session_state.results = None

if "last_update" not in st.session_state:
    st.session_state.last_update = None

if "loading" not in st.session_state:
    st.session_state.loading = False

if "ml_data" not in st.session_state:
    st.session_state.ml_data = None

if "ml_performance" not in st.session_state:
    st.session_state.ml_performance = None


# ============================================================
# DATABASE CONFIG
# ============================================================

def get_db_config():
    """
    Reads MySQL configuration from .env
    """

    return {
        "host": os.getenv("db_host", os.getenv("DB_HOST", "localhost")),
        "user": os.getenv("db_user", os.getenv("DB_USER", "root")),
        "password": os.getenv("db_password", os.getenv("DB_PASSWORD", "")),
        "database": os.getenv("db_name", os.getenv("DB_NAME", "btc_prediction"))
    }


def get_db_connection():
    """
    Create MySQL connection.
    """

    config = get_db_config()

    try:
        connection = mysql.connector.connect(
            host=config["host"],
            user=config["user"],
            password=config["password"],
            database=config["database"]
        )

        return connection

    except Error as e:
        st.error(f"❌ MySQL connection error: {e}")
        return None


# ============================================================
# INDICATOR FUNCTIONS
# ============================================================

def load_indicators():
    """
    Load indicators from btc_indicators.py
    """

    with st.spinner("🔄 Loading technical indicators..."):

        try:

            indicator = BTCIndicators()

            results = indicator.calculate_all_indicators()

            indicator.close()

            if results:

                st.session_state.results = results

                st.session_state.last_update = (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )

                st.session_state.loading = False

                return True

            else:

                st.error("❌ Failed to load indicators!")

                st.session_state.loading = False

                return False

        except Exception as e:

            st.error(f"❌ Indicator error: {str(e)}")

            st.session_state.loading = False

            return False


# ============================================================
# ML DATA FUNCTIONS
# ============================================================

def load_ml_predictions(days=7):
    """
    Load latest ML predictions from btc_predictions.
    """

    connection = get_db_connection()

    if connection is None:
        return pd.DataFrame()

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
            evaluated,
            created_at
        FROM btc_predictions
        WHERE prediction_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        ORDER BY prediction_date ASC, model_name ASC
    """

    try:

        df = pd.read_sql(query, connection, params=(days,))

        connection.close()

        if not df.empty:
            df["prediction_date"] = pd.to_datetime(
                df["prediction_date"]
            )

        return df

    except Exception as e:

        connection.close()

        st.warning(f"⚠️ Could not load ML predictions: {e}")

        return pd.DataFrame()


def load_all_ml_predictions():
    """
    Load complete prediction history.
    Used for determining latest available prediction.
    """

    connection = get_db_connection()

    if connection is None:
        return pd.DataFrame()

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
            evaluated,
            created_at
        FROM btc_predictions
        ORDER BY prediction_date ASC, model_name ASC
    """

    try:

        df = pd.read_sql(query, connection)

        connection.close()

        if not df.empty:

            df["prediction_date"] = pd.to_datetime(
                df["prediction_date"]
            )

        return df

    except Exception as e:

        connection.close()

        return pd.DataFrame()


def load_model_performance():
    """
    Load model performance from btc_model_performance.
    """

    connection = get_db_connection()

    if connection is None:
        return pd.DataFrame()

    query = """
        SELECT
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
            model_rank,
            created_at
        FROM btc_model_performance
        ORDER BY evaluation_date DESC, model_rank ASC
    """

    try:

        df = pd.read_sql(query, connection)

        connection.close()

        if not df.empty:

            df["evaluation_date"] = pd.to_datetime(
                df["evaluation_date"]
            )

            if "period_start" in df.columns:
                df["period_start"] = pd.to_datetime(
                    df["period_start"]
                )

            if "period_end" in df.columns:
                df["period_end"] = pd.to_datetime(
                    df["period_end"]
                )

        return df

    except Exception as e:

        connection.close()

        return pd.DataFrame()


# ============================================================
# FALLBACK WEEKLY PERFORMANCE CALCULATION
# ============================================================

def calculate_weekly_performance(predictions_df):
    """
    Calculate model performance from last 7 days if
    btc_model_performance doesn't have usable data.
    """

    if predictions_df.empty:
        return pd.DataFrame()

    df = predictions_df.copy()

    df = df[df["evaluated"] == 1].copy()

    if df.empty:
        return pd.DataFrame()

    latest_date = df["prediction_date"].max()

    start_date = latest_date - timedelta(days=6)

    df = df[
        df["prediction_date"] >= start_date
    ].copy()

    if df.empty:
        return pd.DataFrame()

    records = []

    for model_name, group in df.groupby("model_name"):

        group = group.copy()

        group["error"] = (
            group["predicted_return"] -
            group["actual_return"]
        )

        group["squared_error"] = group["error"] ** 2

        mae = group["error"].abs().mean()

        rmse = np.sqrt(
            group["squared_error"].mean()
        )

        directional_accuracy = (
            group["predicted_direction"] ==
            group["actual_direction"]
        ).mean() * 100

        win_rate = (
            group["predicted_direction"] ==
            group["actual_direction"]
        ).mean() * 100

        strategy_returns = []

        for _, row in group.iterrows():

            predicted_direction = int(
                row["predicted_direction"]
            )

            actual_return = float(
                row["actual_return"]
            )

            if predicted_direction == 1:
                strategy_return = actual_return
            else:
                strategy_return = -actual_return

            strategy_returns.append(strategy_return)

        total_strategy_return = (
            np.prod(
                [1 + r for r in strategy_returns]
            ) - 1
        ) * 100

        records.append({

            "model_name": model_name,

            "total_predictions": len(group),

            "mae": mae,

            "rmse": rmse,

            "directional_accuracy":
                directional_accuracy,

            "avg_predicted_return":
                group["predicted_return"].mean() * 100,

            "avg_actual_return":
                group["actual_return"].mean() * 100,

            "total_strategy_return":
                total_strategy_return,

            "win_rate":
                win_rate

        })

    result = pd.DataFrame(records)

    if result.empty:
        return result

    result = result.sort_values(
        by=[
            "directional_accuracy",
            "total_strategy_return"
        ],
        ascending=False
    ).reset_index(drop=True)

    result["model_rank"] = (
        result.index + 1
    )

    return result


# ============================================================
# GET LATEST WEEKLY PERFORMANCE
# ============================================================

def get_latest_weekly_performance():

    performance = load_model_performance()

    if performance.empty:

        predictions = load_all_ml_predictions()

        return calculate_weekly_performance(predictions)

    latest_evaluation_date = (
        performance["evaluation_date"].max()
    )

    latest = performance[
        performance["evaluation_date"] ==
        latest_evaluation_date
    ].copy()

    if latest.empty:

        predictions = load_all_ml_predictions()

        return calculate_weekly_performance(predictions)

    return latest.sort_values(
        "model_rank"
    ).reset_index(drop=True)


# ============================================================
# EMAIL REPORT
# ============================================================

def send_email_report():

    if BTCEmailSender is None:

        st.error(
            "❌ btc_email_sender.py could not be imported."
        )

        return

    with st.spinner("📧 Sending email..."):

        try:

            email_sender = BTCEmailSender()

            email_sender.results = (
                st.session_state.results
            )

            html_content = (
                email_sender.create_html_email()
            )

            if html_content:

                subject = (
                    f"🚀 BTC Daily Report - "
                    f"{datetime.now().strftime('%Y-%m-%d')}"
                )

                success = email_sender.send_email(
                    subject,
                    html_content
                )

                if success:

                    st.success(
                        "✅ Email sent successfully!"
                    )

                else:

                    st.error(
                        "❌ Failed to send email!"
                    )

            else:

                st.error(
                    "❌ Failed to create email content!"
                )

        except Exception as e:

            st.error(
                f"❌ Email error: {str(e)}"
            )


# ============================================================
# EXPORT JSON
# ============================================================

def export_json():

    try:

        filename = (
            f"btc_indicators_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        def convert(obj):

            if hasattr(obj, "item"):
                return obj.item()

            return obj

        with open(filename, "w") as f:

            json.dump(
                st.session_state.results,
                f,
                default=convert,
                indent=2
            )

        st.success(
            f"✅ Data exported to {filename}"
        )

        with open(filename, "r") as f:

            json_data = f.read()

            st.download_button(
                label="📥 Download JSON",
                data=json_data,
                file_name=filename,
                mime="application/json",
                use_container_width=True
            )

    except Exception as e:

        st.error(
            f"❌ Failed to export: {str(e)}"
        )


# ============================================================
# ML DISPLAY HELPERS
# ============================================================

def direction_text(direction):

    try:

        direction = int(direction)

        if direction == 1:
            return "🟢 UP"

        return "🔴 DOWN"

    except:

        return "⚪ N/A"


def direction_html(direction):

    try:

        direction = int(direction)

        if direction == 1:

            return (
                '<span class="prediction-up">'
                '🟢 UP'
                '</span>'
            )

        return (
            '<span class="prediction-down">'
            '🔴 DOWN'
            '</span>'
        )

    except:

        return (
            '<span class="prediction-neutral">'
            '⚪ N/A'
            '</span>'
        )


# ============================================================
# ML PREDICTION CENTER
# ============================================================

def display_ml_dashboard():

    st.markdown(
        """
        <div class="ml-header">
            <h2>🤖 AI / ML Prediction Center</h2>
            <p>
                Six machine-learning models predicting the next BTC move
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    predictions = load_ml_predictions(days=7)

    performance = get_latest_weekly_performance()

    st.session_state.ml_data = predictions

    st.session_state.ml_performance = performance

    if predictions.empty:

        st.warning(
            "⚠️ No ML predictions found yet. "
            "Run daily_prediction.py first."
        )

        st.info(
            "Expected table: btc_predictions"
        )

        return

    # --------------------------------------------------------
    # Latest prediction
    # --------------------------------------------------------

    latest_prediction_date = (
        predictions["prediction_date"].max()
    )

    latest_predictions = predictions[
        predictions["prediction_date"] ==
        latest_prediction_date
    ].copy()

    # --------------------------------------------------------
    # Winner
    # --------------------------------------------------------

    winner = None

    if not performance.empty:

        performance = performance.sort_values(
            "model_rank"
        )

        winner = performance.iloc[0]

    # --------------------------------------------------------
    # Top cards
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    # Winner
    with col1:

        if winner is not None:

            st.metric(
                "🏆 Weekly Winner",
                str(winner["model_name"])
            )

        else:

            st.metric(
                "🏆 Weekly Winner",
                "N/A"
            )

    # Accuracy
    with col2:

        if winner is not None:

            accuracy = float(
                winner["directional_accuracy"]
            )

            st.metric(
                "🎯 Direction Accuracy",
                f"{accuracy:.2f}%"
            )

        else:

            st.metric(
                "🎯 Direction Accuracy",
                "N/A"
            )

    # Strategy return
    with col3:

        if winner is not None:

            strategy_return = float(
                winner["total_strategy_return"]
            )

            st.metric(
                "📈 Weekly Strategy Return",
                f"{strategy_return:+.2f}%"
            )

        else:

            st.metric(
                "📈 Weekly Strategy Return",
                "N/A"
            )

    # Prediction date
    with col4:

        st.metric(
            "📅 Latest Prediction",
            latest_prediction_date.strftime(
                "%d %b %Y"
            )
        )

    # --------------------------------------------------------
    # Winner card
    # --------------------------------------------------------

    if winner is not None:

        st.markdown(
            f"""
            <div class="winner-card">

                <div class="winner-label">
                    🏆 CURRENT WEEKLY WINNER
                </div>

                <div class="winner-model">
                    {winner['model_name']}
                </div>

                <hr>

                <div>
                    Directional Accuracy:
                    <b>{float(winner['directional_accuracy']):.2f}%</b>
                </div>

                <div>
                    Win Rate:
                    <b>{float(winner['win_rate']):.2f}%</b>
                </div>

                <div>
                    Strategy Return:
                    <b>{float(winner['total_strategy_return']):+.2f}%</b>
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

    # ========================================================
    # CURRENT MODEL PREDICTIONS
    # ========================================================

    st.subheader(
        f"🔮 Current Predictions — "
        f"{latest_prediction_date.strftime('%d %b %Y')}"
    )

    model_order = [
        "linear_regression",
        "random_forest",
        "xgboost",
        "lightgbm",
        "lstm",
        "gru"
    ]

    display_names = {
        "linear_regression": "Linear Regression",
        "random_forest": "Random Forest",
        "xgboost": "XGBoost",
        "lightgbm": "LightGBM",
        "lstm": "LSTM",
        "gru": "GRU"
    }

    existing_models = [
        model for model in model_order
        if model in latest_predictions["model_name"].values
    ]

    if existing_models:

        cols = st.columns(
            min(len(existing_models), 3)
        )

        for index, model_name in enumerate(existing_models):

            row = latest_predictions[
                latest_predictions["model_name"] ==
                model_name
            ]

            if row.empty:
                continue

            row = row.iloc[0]

            col = cols[index % len(cols)]

            with col:

                predicted_price = row[
                    "predicted_price"
                ]

                predicted_return = row[
                    "predicted_return"
                ]

                predicted_direction = row[
                    "predicted_direction"
                ]

                st.markdown(
                    f"""
                    <div class="metric-card">

                        <h4>
                            🤖 {display_names.get(
                                model_name,
                                model_name
                            )}
                        </h4>

                        <h2>
                            ${float(predicted_price):,.2f}
                        </h2>

                        <p>
                            Expected Return:
                            <b>
                                {float(predicted_return) * 100:+.2f}%
                            </b>
                        </p>

                        <p>
                            Direction:
                            {direction_html(
                                predicted_direction
                            )}
                        </p>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

    # ========================================================
    # PREDICTION TABLE
    # ========================================================

    st.subheader("📅 7-Day Model Predictions")

    table = predictions.copy()

    table["Model"] = table[
        "model_name"
    ].map(
        lambda x: display_names.get(x, x)
    )

    table["Date"] = table[
        "prediction_date"
    ].dt.strftime("%d %b")

    table["Predicted Price"] = table[
        "predicted_price"
    ].apply(
        lambda x: (
            f"${x:,.2f}"
            if pd.notna(x)
            else "N/A"
        )
    )

    table["Predicted Return"] = table[
        "predicted_return"
    ].apply(
        lambda x: (
            f"{x * 100:+.2f}%"
            if pd.notna(x)
            else "N/A"
        )
    )

    table["Direction"] = table[
        "predicted_direction"
    ].apply(direction_text)

    table["Actual Price"] = table[
        "actual_price"
    ].apply(
        lambda x: (
            f"${x:,.2f}"
            if pd.notna(x)
            else "Pending"
        )
    )

    table["Actual Return"] = table[
        "actual_return"
    ].apply(
        lambda x: (
            f"{x * 100:+.2f}%"
            if pd.notna(x)
            else "Pending"
        )
    )

    table["Result"] = table.apply(
        lambda row:
            "✅ Correct"
            if (
                pd.notna(row["actual_direction"])
                and
                int(row["predicted_direction"]) ==
                int(row["actual_direction"])
            )
            else (
                "❌ Wrong"
                if pd.notna(row["actual_direction"])
                else "⏳ Pending"
            ),
        axis=1
    )

    display_table = table[
        [
            "Date",
            "Model",
            "Predicted Price",
            "Predicted Return",
            "Direction",
            "Actual Price",
            "Actual Return",
            "Result"
        ]
    ]

    st.dataframe(
        display_table,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # MODEL PERFORMANCE
    # ========================================================

    st.subheader("🏆 Weekly Model Performance")

    if performance.empty:

        st.info(
            "No evaluated weekly performance available yet."
        )

    else:

        performance_display = performance.copy()

        performance_display["Model"] = (
            performance_display["model_name"].map(
                lambda x: display_names.get(x, x)
            )
        )

        performance_display["Rank"] = (
            performance_display["model_rank"]
        )

        performance_display["Predictions"] = (
            performance_display["total_predictions"]
        )

        performance_display["MAE"] = (
            performance_display["mae"]
            .apply(lambda x: f"{x:.5f}")
        )

        performance_display["RMSE"] = (
            performance_display["rmse"]
            .apply(lambda x: f"{x:.5f}")
        )

        performance_display["Accuracy"] = (
            performance_display[
                "directional_accuracy"
            ]
            .apply(lambda x: f"{x:.2f}%")
        )

        performance_display["Win Rate"] = (
            performance_display["win_rate"]
            .apply(lambda x: f"{x:.2f}%")
        )

        performance_display["Strategy Return"] = (
            performance_display[
                "total_strategy_return"
            ]
            .apply(lambda x: f"{x:+.2f}%")
        )

        performance_display = performance_display[
            [
                "Rank",
                "Model",
                "Predictions",
                "MAE",
                "RMSE",
                "Accuracy",
                "Win Rate",
                "Strategy Return"
            ]
        ]

        st.dataframe(
            performance_display,
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # PREDICTED VS ACTUAL PRICE CHART
    # ========================================================

    st.subheader("📈 7-Day Predicted vs Actual BTC Price")

    chart_df = predictions.copy()

    if not chart_df.empty:

        chart_df["date"] = (
            chart_df["prediction_date"]
            .dt.strftime("%d %b")
        )

        fig = go.Figure()

        # Actual price
        actual = (
            chart_df[
                [
                    "prediction_date",
                    "actual_price"
                ]
            ]
            .drop_duplicates()
            .sort_values("prediction_date")
        )

        if not actual.empty:

            actual = actual[
                actual["actual_price"].notna()
            ]

            if not actual.empty:

                fig.add_trace(
                    go.Scatter(
                        x=actual["prediction_date"],
                        y=actual["actual_price"],
                        mode="lines+markers",
                        name="Actual BTC Price",
                        line=dict(
                            width=4
                        )
                    )
                )

        # Each model
        for model_name in model_order:

            model_data = chart_df[
                chart_df["model_name"] ==
                model_name
            ].sort_values(
                "prediction_date"
            )

            if model_data.empty:
                continue

            fig.add_trace(
                go.Scatter(
                    x=model_data[
                        "prediction_date"
                    ],
                    y=model_data[
                        "predicted_price"
                    ],
                    mode="lines+markers",
                    name=display_names.get(
                        model_name,
                        model_name
                    )
                )
            )

        fig.update_layout(
            height=500,
            xaxis_title="Prediction Date",
            yaxis_title="BTC Price (USD)",
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            )
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    # ========================================================
    # MODEL ACCURACY CHART
    # ========================================================

    if not performance.empty:

        st.subheader(
            "🎯 Model Directional Accuracy"
        )

        accuracy_df = performance.copy()

        accuracy_df["Model"] = (
            accuracy_df["model_name"].map(
                lambda x: display_names.get(x, x)
            )
        )

        accuracy_df = accuracy_df.sort_values(
            "directional_accuracy",
            ascending=True
        )

        fig_accuracy = go.Figure()

        fig_accuracy.add_trace(
            go.Bar(
                x=accuracy_df[
                    "directional_accuracy"
                ],
                y=accuracy_df["Model"],
                orientation="h",
                text=accuracy_df[
                    "directional_accuracy"
                ].apply(
                    lambda x: f"{x:.1f}%"
                ),
                textposition="auto"
            )
        )

        fig_accuracy.update_layout(
            height=400,
            xaxis_title="Directional Accuracy (%)",
            yaxis_title="Model",
            xaxis=dict(
                range=[
                    0,
                    max(
                        100,
                        accuracy_df[
                            "directional_accuracy"
                        ].max() + 10
                    )
                ]
            )
        )

        st.plotly_chart(
            fig_accuracy,
            use_container_width=True
        )

    # ========================================================
    # STRATEGY RETURN CHART
    # ========================================================

    if not performance.empty:

        st.subheader(
            "💰 Weekly Strategy Return by Model"
        )

        return_df = performance.copy()

        return_df["Model"] = (
            return_df["model_name"].map(
                lambda x: display_names.get(x, x)
            )
        )

        return_df = return_df.sort_values(
            "total_strategy_return",
            ascending=True
        )

        fig_return = go.Figure()

        fig_return.add_trace(
            go.Bar(
                x=return_df[
                    "total_strategy_return"
                ],
                y=return_df["Model"],
                orientation="h",
                text=return_df[
                    "total_strategy_return"
                ].apply(
                    lambda x: f"{x:+.2f}%"
                ),
                textposition="auto"
            )
        )

        fig_return.update_layout(
            height=400,
            xaxis_title="Strategy Return (%)",
            yaxis_title="Model"
        )

        st.plotly_chart(
            fig_return,
            use_container_width=True
        )

    # ========================================================
    # MODEL DETAILS
    # ========================================================

    if not performance.empty:

        with st.expander(
            "📊 Detailed Model Statistics"
        ):

            for _, row in performance.iterrows():

                model_name = display_names.get(
                    row["model_name"],
                    row["model_name"]
                )

                st.markdown(
                    f"### {model_name}"
                )

                c1, c2, c3, c4, c5 = st.columns(5)

                with c1:
                    st.metric(
                        "Rank",
                        f"#{int(row['model_rank'])}"
                    )

                with c2:
                    st.metric(
                        "MAE",
                        f"{float(row['mae']):.5f}"
                    )

                with c3:
                    st.metric(
                        "RMSE",
                        f"{float(row['rmse']):.5f}"
                    )

                with c4:
                    st.metric(
                        "Accuracy",
                        f"{float(row['directional_accuracy']):.2f}%"
                    )

                with c5:
                    st.metric(
                        "Return",
                        f"{float(row['total_strategy_return']):+.2f}%"
                    )

                st.markdown("---")


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Bitcoin.svg/800px-Bitcoin.svg.png",
        width=100
    )

    st.markdown("## 📊 Dashboard Controls")

    # --------------------------------------------------------
    # Refresh button
    # --------------------------------------------------------

    if st.button(
        "🔄 Refresh Data",
        use_container_width=True
    ):

        st.session_state.loading = True

        st.rerun()

    # --------------------------------------------------------
    # Auto refresh
    # --------------------------------------------------------

    st.markdown("---")

    st.markdown("### 🔄 Auto Refresh")

    auto_refresh = st.checkbox(
        "Enable auto refresh",
        value=True
    )

    refresh_seconds = st.selectbox(
        "Refresh interval",
        [30, 60, 120, 300, 600],
        index=1,
        format_func=lambda x: (
            f"{x} seconds"
            if x < 60
            else f"{x // 60} minute(s)"
        )
    )

    if auto_refresh:

        if AUTO_REFRESH_AVAILABLE:

            st_autorefresh(
                interval=refresh_seconds * 1000,
                key="btc_dashboard_autorefresh"
            )

            st.caption(
                f"♻️ Auto-refreshing every "
                f"{refresh_seconds} seconds"
            )

        else:

            st.warning(
                "Install streamlit-autorefresh "
                "to enable automatic refresh."
            )

    # --------------------------------------------------------
    # Email
    # --------------------------------------------------------

    if st.button(
        "📧 Send Email Report",
        use_container_width=True
    ):

        if st.session_state.results:

            send_email_report()

        else:

            st.error(
                "❌ No data available! "
                "Please refresh first."
            )

    # --------------------------------------------------------
    # Export
    # --------------------------------------------------------

    if st.button(
        "💾 Export JSON",
        use_container_width=True
    ):

        if st.session_state.results:

            export_json()

        else:

            st.error(
                "❌ No data available! "
                "Please refresh first."
            )

    # --------------------------------------------------------
    # Info
    # --------------------------------------------------------

    st.markdown("---")

    st.markdown("### 📈 Dashboard Info")

    if st.session_state.last_update:

        st.write(
            f"🕐 Last Update: "
            f"{st.session_state.last_update}"
        )

    st.markdown("---")

    st.markdown("### 🤖 ML Models")

    st.write("• Linear Regression")
    st.write("• Random Forest")
    st.write("• XGBoost")
    st.write("• LightGBM")
    st.write("• LSTM")
    st.write("• GRU")

    st.markdown("---")

    st.markdown("### 📊 Technical Indicators")

    st.write("• Support & Resistance")
    st.write("• Market Structure")
    st.write("• BOS / CHOCH")
    st.write("• Moving Averages")
    st.write("• RSI")
    st.write("• MACD")
    st.write("• Bollinger Bands")
    st.write("• Fibonacci")
    st.write("• Pivot Points")
    st.write("• Volume Liquidity")
    st.write("• ATR")


# ============================================================
# MAIN HEADER
# ============================================================

st.markdown(
    """
    <div class="main-header">

        <h1>₿ BTC AI Trading Dashboard</h1>

        <p>
            Technical Analysis + Machine Learning
            + Deep Learning Predictions
        </p>

    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# LOAD TECHNICAL INDICATORS
# ============================================================

if (
    st.session_state.loading
    or
    st.session_state.results is None
):

    load_indicators()


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

if st.session_state.results:

    results = st.session_state.results

    # ========================================================
    # TOP ROW
    # ========================================================

    col1, col2, col3, col4 = st.columns(4)

    # Current Price
    with col1:

        current_price = results.get(
            "current_price",
            0
        )

        st.metric(
            label="💰 Current Price",
            value=f"${current_price:,.2f}"
        )

    # Signal
    with col2:

        if "overall_signal" in results:

            signal = results[
                "overall_signal"
            ]

            direction = signal.get(
                "direction",
                "NEUTRAL"
            )

            confidence = signal.get(
                "confidence",
                "Unknown"
            )

            if "BUY" in direction:

                st.markdown(
                    '<div class="signal-buy">'
                    '🟢 BUY'
                    '</div>',
                    unsafe_allow_html=True
                )

            elif "SELL" in direction:

                st.markdown(
                    '<div class="signal-sell">'
                    '🔴 SELL'
                    '</div>',
                    unsafe_allow_html=True
                )

            else:

                st.markdown(
                    '<div class="signal-neutral">'
                    '🟡 NEUTRAL'
                    '</div>',
                    unsafe_allow_html=True
                )

            if confidence == "High":

                st.markdown(
                    f"""
                    <p style="text-align:center;">
                    <span class="confidence-high">
                    Confidence: {confidence}
                    </span>
                    </p>
                    """,
                    unsafe_allow_html=True
                )

            elif confidence == "Medium":

                st.markdown(
                    f"""
                    <p style="text-align:center;">
                    <span class="confidence-medium">
                    Confidence: {confidence}
                    </span>
                    </p>
                    """,
                    unsafe_allow_html=True
                )

            else:

                st.markdown(
                    f"""
                    <p style="text-align:center;">
                    <span class="confidence-low">
                    Confidence: {confidence}
                    </span>
                    </p>
                    """,
                    unsafe_allow_html=True
                )

    # RSI
    with col3:

        if "rsi" in results:

            rsi = results["rsi"]

            st.metric(
                label="📊 RSI",
                value=f"{rsi.get('value', 0):.1f}",
                delta=rsi.get(
                    "status",
                    "Neutral"
                )
            )

    # ATR
    with col4:

        if "atr" in results:

            atr = results["atr"]

            st.metric(
                label="📊 ATR",
                value=f"${atr.get('atr', 0):.2f}",
                delta=(
                    f"{atr.get('percentile', 0):.0f}"
                    f"th percentile"
                )
            )

            if (
                "overall_signal" in results
                and
                "atr_info" in results["overall_signal"]
            ):

                atr_info = results[
                    "overall_signal"
                ]["atr_info"]

                st.caption(
                    f"Stop Loss: "
                    f"${atr_info['suggested_stop_loss']:.2f}"
                )


    # ========================================================
    # MARKET STRUCTURE / SUPPORT RESISTANCE
    # ========================================================

    col1, col2 = st.columns(2)

    with col1:

        with st.container():

            st.subheader(
                "📊 Market Structure"
            )

            if "market_structure" in results:

                structure = results[
                    "market_structure"
                ]

                trend = structure.get(
                    "trend_regime",
                    "Unknown"
                )

                if trend == "Uptrend":

                    st.success(
                        f"📈 {trend}"
                    )

                elif trend == "Downtrend":

                    st.error(
                        f"📉 {trend}"
                    )

                elif trend == "Range":

                    st.warning(
                        f"➡️ {trend}"
                    )

                else:

                    st.info(
                        f"❓ {trend}"
                    )

                bos = structure.get(
                    "bos",
                    []
                )

                if bos:

                    st.write(
                        "**Break of Structure (BOS):**"
                    )

                    for b in bos:

                        st.write(
                            f"• {b['type']} "
                            f"at ${b['price']:,.2f}"
                        )

                else:

                    st.write(
                        "**BOS:** None"
                    )

                choch = structure.get(
                    "choch",
                    []
                )

                if choch:

                    st.write(
                        "**Change of Character (CHOCH):**"
                    )

                    for c in choch:

                        st.write(
                            f"• {c['type']}"
                        )

                else:

                    st.write(
                        "**CHOCH:** None"
                    )

                if "hh_hl_lh_ll" in structure:

                    hh_hl = structure[
                        "hh_hl_lh_ll"
                    ]

                    st.write(
                        f"**HH:** {hh_hl.get('HH', 0)} | "
                        f"**HL:** {hh_hl.get('HL', 0)} | "
                        f"**LH:** {hh_hl.get('LH', 0)} | "
                        f"**LL:** {hh_hl.get('LL', 0)}"
                    )

    with col2:

        with st.container():

            st.subheader(
                "🎯 Support & Resistance"
            )

            if "support_resistance" in results:

                sr = results[
                    "support_resistance"
                ]

                support = sr.get(
                    "nearest_support",
                    {}
                )

                resistance = sr.get(
                    "nearest_resistance",
                    {}
                )

                col_a, col_b = st.columns(2)

                with col_a:

                    if support:

                        st.metric(
                            "Support",
                            f"${support.get('price', 0):,.2f}",
                            f"Strength: "
                            f"{support.get('strength', 0)}"
                        )

                    else:

                        st.metric(
                            "Support",
                            "N/A"
                        )

                with col_b:

                    if resistance:

                        st.metric(
                            "Resistance",
                            f"${resistance.get('price', 0):,.2f}",
                            f"Strength: "
                            f"{resistance.get('strength', 0)}"
                        )

                    else:

                        st.metric(
                            "Resistance",
                            "N/A"
                        )

                if (
                    "support_levels" in sr
                    and
                    sr["support_levels"]
                ):

                    with st.expander(
                        "📊 All Support Levels"
                    ):

                        supports = pd.DataFrame(
                            [
                                {
                                    "Level": i + 1,
                                    "Price":
                                        f"${s['price']:,.2f}",
                                    "Strength":
                                        f"{s['strength']} touches"
                                }
                                for i, s in enumerate(
                                    sr["support_levels"][:5]
                                )
                            ]
                        )

                        st.dataframe(
                            supports,
                            use_container_width=True,
                            hide_index=True
                        )

                if (
                    "resistance_levels" in sr
                    and
                    sr["resistance_levels"]
                ):

                    with st.expander(
                        "📊 All Resistance Levels"
                    ):

                        resistances = pd.DataFrame(
                            [
                                {
                                    "Level": i + 1,
                                    "Price":
                                        f"${r['price']:,.2f}",
                                    "Strength":
                                        f"{r['strength']} touches"
                                }
                                for i, r in enumerate(
                                    sr["resistance_levels"][:5]
                                )
                            ]
                        )

                        st.dataframe(
                            resistances,
                            use_container_width=True,
                            hide_index=True
                        )


    # ========================================================
    # MOVING AVERAGES
    # ========================================================

    st.subheader(
        "📈 Moving Averages"
    )

    if "moving_averages" in results:

        ma = results[
            "moving_averages"
        ]

        ma_data = []

        for period, data in ma.items():

            ma_data.append(
                {
                    "Period": period,
                    "Value":
                        f"${data['value']:,.2f}",
                    "EMA":
                        f"${data.get('ema', data['value']):,.2f}",
                    "Trend":
                        data.get(
                            "trend",
                            "Neutral"
                        ),
                    "Slope":
                        f"{data.get('slope', 0):.2f}%"
                }
            )

        ma_df = pd.DataFrame(
            ma_data
        )

        def color_trend(val):

            if (
                "Strong Bullish" in val
                or
                val == "Bullish"
            ):

                return (
                    "background-color: "
                    "#00ff88; color: black"
                )

            elif (
                "Strong Bearish" in val
                or
                val == "Bearish"
            ):

                return (
                    "background-color: "
                    "#ff4757; color: white"
                )

            else:

                return (
                    "background-color: "
                    "#ffd93d; color: black"
                )

        styled_df = ma_df.style.map(
            color_trend,
            subset=["Trend"]
        )

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True
        )


    # ========================================================
    # RSI / MACD
    # ========================================================

    col1, col2 = st.columns(2)

    with col1:

        with st.container():

            st.subheader(
                "📊 RSI"
            )

            if "rsi" in results:

                rsi = results["rsi"]

                fig = go.Figure(
                    go.Indicator(
                        mode="gauge+number+delta",
                        value=rsi.get(
                            "value",
                            0
                        ),
                        domain={
                            "x": [0, 1],
                            "y": [0, 1]
                        },
                        title={
                            "text":
                                "RSI (Wilder's Smoothing)"
                        },
                        delta={
                            "reference": 50
                        },
                        gauge={
                            "axis": {
                                "range": [0, 100]
                            },
                            "bar": {
                                "color":
                                    "darkblue"
                            },
                            "steps": [
                                {
                                    "range":
                                        [0, 30],
                                    "color":
                                        "red"
                                },
                                {
                                    "range":
                                        [30, 70],
                                    "color":
                                        "yellow"
                                },
                                {
                                    "range":
                                        [70, 100],
                                    "color":
                                        "green"
                                }
                            ],
                            "threshold": {
                                "line": {
                                    "color":
                                        "red",
                                    "width": 4
                                },
                                "thickness":
                                    0.75,
                                "value":
                                    rsi.get(
                                        "value",
                                        0
                                    )
                            }
                        }
                    )
                )

                fig.update_layout(
                    height=300
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

                st.info(
                    f"Status: "
                    f"{rsi.get('status', 'Neutral')} "
                    f"| Period: "
                    f"{rsi.get('period', 14)} days"
                )

    with col2:

        with st.container():

            st.subheader(
                "📊 MACD"
            )

            if "macd" in results:

                macd = results[
                    "macd"
                ]

                col_a, col_b, col_c = (
                    st.columns(3)
                )

                with col_a:

                    st.metric(
                        "MACD",
                        f"{macd.get('macd', 0):.2f}"
                    )

                with col_b:

                    st.metric(
                        "Signal",
                        f"{macd.get('signal', 0):.2f}"
                    )

                with col_c:

                    st.metric(
                        "Histogram",
                        f"{macd.get('histogram', 0):.2f}"
                    )

                st.info(
                    f"Signal Status: "
                    f"{macd.get('signal_status', 'Neutral')} "
                    f"| Histogram: "
                    f"{macd.get('histogram_status', 'Stable')}"
                )


    # ========================================================
    # BOLLINGER BANDS
    # ========================================================

    st.subheader(
        "📊 Bollinger Bands"
    )

    if "bollinger_bands" in results:

        bb = results[
            "bollinger_bands"
        ]

        col1, col2, col3, col4 = (
            st.columns(4)
        )

        with col1:

            st.metric(
                "Upper Band",
                f"${bb.get('upper_band', 0):,.2f}"
            )

        with col2:

            st.metric(
                "Middle Band",
                f"${bb.get('middle_band', 0):,.2f}"
            )

        with col3:

            st.metric(
                "Lower Band",
                f"${bb.get('lower_band', 0):,.2f}"
            )

        with col4:

            st.metric(
                "Position",
                bb.get(
                    "position",
                    "Inside Bands"
                )
            )

        st.info(
            f"Band Width: "
            f"${bb.get('band_width', 0):,.2f} "
            f"| Squeeze: "
            f"{bb.get('squeeze', 'No')} "
            f"| Percentile: "
            f"{bb.get('bandwidth_percentile', 0):.0f}%"
        )


    # ========================================================
    # FIBONACCI / PIVOT
    # ========================================================

    col1, col2 = st.columns(2)

    with col1:

        with st.container():

            st.subheader(
                "📊 Fibonacci (Swing-based)"
            )

            if "fibonacci" in results:

                fib = results[
                    "fibonacci"
                ]

                if fib:

                    st.write(
                        f"**Swing High:** "
                        f"${fib.get('swing_high', 0):,.2f} "
                        f"({fib.get('high_date', 'N/A')})"
                    )

                    st.write(
                        f"**Swing Low:** "
                        f"${fib.get('swing_low', 0):,.2f} "
                        f"({fib.get('low_date', 'N/A')})"
                    )

                    st.write(
                        f"**Range:** "
                        f"${fib.get('range', 0):,.2f}"
                    )

                    fib_data = []

                    for level, price in fib.get(
                        "fib_levels",
                        {}
                    ).items():

                        fib_data.append(
                            {
                                "Level": level,
                                "Price":
                                    f"${price:,.2f}"
                            }
                        )

                    fib_df = pd.DataFrame(
                        fib_data
                    )

                    st.dataframe(
                        fib_df,
                        use_container_width=True,
                        hide_index=True
                    )

                    if fib.get(
                        "current_fib_level"
                    ):

                        st.success(
                            f"📍 Current Level: "
                            f"{fib['current_fib_level']}"
                        )

                else:

                    st.warning(
                        "No swing points found for Fibonacci"
                    )

    with col2:

        with st.container():

            st.subheader(
                "📊 Pivot Points"
            )

            if "pivot_points" in results:

                pivot = results[
                    "pivot_points"
                ]

                col_a, col_b = (
                    st.columns(2)
                )

                with col_a:

                    st.metric(
                        "Pivot",
                        f"${pivot.get('pivot', 0):,.2f}"
                    )

                    st.metric(
                        "R1",
                        f"${pivot.get('resistance_1', 0):,.2f}"
                    )

                    st.metric(
                        "R2",
                        f"${pivot.get('resistance_2', 0):,.2f}"
                    )

                    st.metric(
                        "R3",
                        f"${pivot.get('resistance_3', 0):,.2f}"
                    )

                with col_b:

                    st.metric(
                        "Position",
                        pivot.get(
                            "current_position",
                            "N/A"
                        )
                    )

                    st.metric(
                        "S1",
                        f"${pivot.get('support_1', 0):,.2f}"
                    )

                    st.metric(
                        "S2",
                        f"${pivot.get('support_2', 0):,.2f}"
                    )

                    st.metric(
                        "S3",
                        f"${pivot.get('support_3', 0):,.2f}"
                    )

                st.caption(
                    f"Nearest: "
                    f"{pivot.get('nearest_level', 'N/A')} "
                    f"("
                    f"${pivot.get('distance_to_nearest', 0):.2f}"
                    f" away)"
                )


    # ========================================================
    # LIQUIDITY
    # ========================================================

    st.subheader(
        "💧 Liquidity Analysis (Volume-based)"
    )

    if "liquidity" in results:

        liq = results[
            "liquidity"
        ]

        col1, col2, col3 = (
            st.columns(3)
        )

        with col1:

            st.metric(
                "30-Day Avg Volume",
                f"{liq.get('avg_volume_30d', 0):,.0f}"
            )

        with col2:

            st.metric(
                "Overall Avg Volume",
                f"{liq.get('avg_volume_overall', 0):,.0f}"
            )

        with col3:

            st.metric(
                "Volume Ratio",
                f"{liq.get('volume_ratio', 0):.2f}x"
            )

        if "volume_profile" in liq:

            vp = liq[
                "volume_profile"
            ]

            if vp:

                col_a, col_b, col_c = (
                    st.columns(3)
                )

                with col_a:

                    st.metric(
                        "POC",
                        f"${vp.get('poc', 0):,.2f}"
                    )

                with col_b:

                    st.metric(
                        "VAH",
                        f"${vp.get('vah', 0):,.2f}"
                    )

                with col_c:

                    st.metric(
                        "VAL",
                        f"${vp.get('val', 0):,.2f}"
                    )

        if (
            "high_volume_nodes" in liq
            and
            liq["high_volume_nodes"]
        ):

            with st.expander(
                "📊 High Volume Nodes (HVN)"
            ):

                hvn_data = pd.DataFrame(
                    [
                        {
                            "Price Range":
                                node.get(
                                    "price_range",
                                    "N/A"
                                ),
                            "Volume":
                                f"{node.get('volume', 0):,.0f}"
                        }
                        for node in liq[
                            "high_volume_nodes"
                        ][:5]
                    ]
                )

                st.dataframe(
                    hvn_data,
                    use_container_width=True,
                    hide_index=True
                )

        if (
            "low_volume_nodes" in liq
            and
            liq["low_volume_nodes"]
        ):

            with st.expander(
                "📊 Low Volume Nodes (LVN)"
            ):

                lvn_data = pd.DataFrame(
                    [
                        {
                            "Price Range":
                                node.get(
                                    "price_range",
                                    "N/A"
                                ),
                            "Volume":
                                f"{node.get('volume', 0):,.0f}"
                        }
                        for node in liq[
                            "low_volume_nodes"
                        ][:5]
                    ]
                )

                st.dataframe(
                    lvn_data,
                    use_container_width=True,
                    hide_index=True
                )


    # ========================================================
    # SIGNAL FACTORS
    # ========================================================

    if "overall_signal" in results:

        signal = results[
            "overall_signal"
        ]

        st.subheader(
            "📋 Signal Factors"
        )

        col1, col2 = st.columns(2)

        with col1:

            st.write(
                "**Factors:**"
            )

            if (
                "factors" in signal
                and
                signal["factors"]
            ):

                for factor in signal[
                    "factors"
                ]:

                    st.write(
                        f"• {factor}"
                    )

        with col2:

            st.write(
                "**Weights:**"
            )

            if "weights" in signal:

                for key, weight in signal[
                    "weights"
                ].items():

                    st.write(
                        f"• {key}: "
                        f"{weight:.0%}"
                    )

            if "normalized_score" in signal:

                st.metric(
                    "Normalized Score",
                    f"{signal['normalized_score']:.2f}"
                )


    # ========================================================
    # ML DASHBOARD
    # ========================================================

    display_ml_dashboard()

else:

    st.info(
        "👈 Click 'Refresh Data' to load dashboard"
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.markdown(
    """
    <div style="
        text-align: center;
        color: #666;
        padding: 20px;
    ">

        <p>
            ₿ BTC AI Trading Dashboard
            | Powered by Streamlit
        </p>

        <p>
            Technical Analysis +
            ML + Deep Learning
        </p>

        <p>
            Models:
            Linear Regression |
            Random Forest |
            XGBoost |
            LightGBM |
            LSTM |
            GRU
        </p>

        <p>
            © 2026 All Rights Reserved
        </p>

    </div>
    """,
    unsafe_allow_html=True
)
