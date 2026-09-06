# ============================================================
# btc_dashboard_streamlit.py
# BTC Technical Analysis + AI/ML Prediction Dashboard
#
# Features:
# - Technical Analysis
# - 6 ML/DL Models
# - AI Consensus
# - Confidence Score
# - Signal Strength
# - Market Risk Score
# - Weekly Model Leaderboard
# - Prediction vs Actual
# - Prediction Error Analysis
# - Accuracy Over Time
# - Strategy Return
# - Compounded Return
# - Equity Curve
# - Maximum Drawdown
# - Historical Backtest
# - Feature Importance / Optional SHAP
# - Email Report
# - JSON Export
# - Auto Refresh
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import json
import os
import glob
import pickle
import warnings

import plotly.graph_objects as go
from plotly.subplots import make_subplots

# MySQL
import mysql.connector
from mysql.connector import Error

warnings.filterwarnings("ignore")


# ============================================================
# OPTIONAL AUTO REFRESH
# ============================================================

try:
    from streamlit_autorefresh import st_autorefresh

    AUTO_REFRESH_AVAILABLE = True

except ImportError:
    AUTO_REFRESH_AVAILABLE = False


# ============================================================
# DOTENV
# ============================================================

try:
    from dotenv import load_dotenv

    load_dotenv()

except ImportError:
    pass


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

try:

    from btc_indicators import BTCIndicators

except ImportError:

    st.error("❌ btc_indicators.py not found!")
    st.stop()


# ============================================================
# EMAIL
# ============================================================

try:

    from btc_email_sender import BTCEmailSender

except ImportError:

    BTCEmailSender = None


# ============================================================
# BACKTEST ENGINE
# ============================================================

try:

    from backtesting import run_backtests

except ImportError:

    run_backtests = None


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

st.markdown(
    """
    <style>

    .main-header {
        background: linear-gradient(
            135deg,
            #f7931a,
            #f9a825
        );
        padding: 24px;
        border-radius: 14px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
    }

    .main-header-title {
        font-size: 32px;
        font-weight: 700;
        margin-bottom: 6px;
    }

    .main-header-subtitle {
        font-size: 16px;
        opacity: 0.95;
    }

    .ml-header {
        background: linear-gradient(
            135deg,
            #111827,
            #1f2937
        );
        padding: 20px;
        border-radius: 12px;
        color: white;
        margin-top: 30px;
        margin-bottom: 20px;
        border-left: 5px solid #f7931a;
    }

    .stButton button {
        width: 100%;
        background: #f7931a;
        color: white;
        font-weight: bold;
        border-radius: 8px;
    }

    .dashboard-footer {
        text-align: center;
        padding: 25px 10px;
        color: #777;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "results": None,
    "last_update": None,
    "loading": False,
    "ml_data": None,
    "ml_performance": None
}

for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# MODEL CONFIG
# ============================================================

MODEL_ORDER = [
    "linear_regression",
    "random_forest",
    "xgboost",
    "lightgbm",
    "lstm",
    "gru"
]

DISPLAY_NAMES = {

    "linear_regression":
        "Linear Regression",

    "random_forest":
        "Random Forest",

    "xgboost":
        "XGBoost",

    "lightgbm":
        "LightGBM",

    "lstm":
        "LSTM",

    "gru":
        "GRU"
}


# ============================================================
# DATABASE CONFIG
# ============================================================

def get_db_config():

    return {

        "host": os.getenv(
            "db_host",
            os.getenv("DB_HOST", "localhost")
        ),

        "user": os.getenv(
            "db_user",
            os.getenv("DB_USER", "root")
        ),

        "password": os.getenv(
            "db_password",
            os.getenv("DB_PASSWORD", "")
        ),

        "database": os.getenv(
            "db_name",
            os.getenv(
                "DB_NAME",
                "btc_prediction"
            )
        )
    }


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    config = get_db_config()

    try:

        return mysql.connector.connect(
            host=config["host"],
            user=config["user"],
            password=config["password"],
            database=config["database"]
        )

    except Error as e:

        st.error(
            f"❌ MySQL connection error: {e}"
        )

        return None


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

def load_indicators():

    with st.spinner(
        "🔄 Loading technical indicators..."
    ):

        try:

            indicator = BTCIndicators()

            results = (
                indicator.calculate_all_indicators()
            )

            indicator.close()

            if results:

                st.session_state.results = results

                st.session_state.last_update = (
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

                st.session_state.loading = False

                return True

            st.error(
                "❌ Failed to load indicators!"
            )

            st.session_state.loading = False

            return False

        except Exception as e:

            st.error(
                f"❌ Indicator error: {str(e)}"
            )

            st.session_state.loading = False

            return False


# ============================================================
# LOAD ML PREDICTIONS
# ============================================================

def load_ml_predictions(days=7):

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
        WHERE prediction_date >=
              DATE_SUB(CURDATE(), INTERVAL %s DAY)
        ORDER BY
            prediction_date ASC,
            model_name ASC
    """

    try:

        df = pd.read_sql(
            query,
            connection,
            params=(days,)
        )

        connection.close()

        if not df.empty:

            df["prediction_date"] = pd.to_datetime(
                df["prediction_date"]
            )

        return df

    except Exception as e:

        try:
            connection.close()
        except:
            pass

        st.warning(
            f"⚠️ Could not load ML predictions: {e}"
        )

        return pd.DataFrame()


# ============================================================
# LOAD ALL ML PREDICTIONS
# ============================================================

def load_all_ml_predictions():

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
        ORDER BY
            prediction_date ASC,
            model_name ASC
    """

    try:

        df = pd.read_sql(
            query,
            connection
        )

        connection.close()

        if not df.empty:

            df["prediction_date"] = pd.to_datetime(
                df["prediction_date"]
            )

        return df

    except Exception:

        try:
            connection.close()
        except:
            pass

        return pd.DataFrame()


# ============================================================
# LOAD MODEL PERFORMANCE
# ============================================================

def load_model_performance():

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
            compounded_strategy_return,
            win_rate,
            model_rank,
            created_at
        FROM btc_model_performance
        ORDER BY
            evaluation_date DESC,
            model_rank ASC
    """

    try:

        df = pd.read_sql(
            query,
            connection
        )

        connection.close()

        if not df.empty:

            for column in [
                "evaluation_date",
                "period_start",
                "period_end",
                "created_at"
            ]:

                if column in df.columns:

                    df[column] = pd.to_datetime(
                        df[column]
                    )

        return df

    except Exception as e:

        try:
            connection.close()
        except:
            pass

        # Compatibility with older table
        try:

            connection = get_db_connection()

            if connection is None:
                return pd.DataFrame()

            fallback_query = """
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
                ORDER BY
                    evaluation_date DESC,
                    model_rank ASC
            """

            df = pd.read_sql(
                fallback_query,
                connection
            )

            connection.close()

            if not df.empty:

                df["compounded_strategy_return"] = (
                    df["total_strategy_return"]
                )

                for column in [
                    "evaluation_date",
                    "period_start",
                    "period_end",
                    "created_at"
                ]:

                    if column in df.columns:

                        df[column] = pd.to_datetime(
                            df[column]
                        )

            return df

        except Exception:

            try:
                connection.close()
            except:
                pass

            return pd.DataFrame()


# ============================================================
# LOAD PROFESSIONAL BACKTEST SUMMARY
# ============================================================

def load_backtest_summary():

    connection = get_db_connection()

    if connection is None:
        return pd.DataFrame()

    query = """
        SELECT
            run_date,
            model_name,
            initial_capital,
            final_capital,
            roi_pct,
            win_rate_pct,
            max_drawdown_pct,
            sharpe_ratio,
            total_trades,
            winning_trades,
            losing_trades,
            gross_pnl,
            net_pnl,
            total_fees,
            total_slippage,
            risk_per_trade_pct,
            fee_bps,
            slippage_bps,
            best_trade_pct,
            worst_trade_pct,
            avg_trade_return_pct,
            updated_at
        FROM btc_backtest_summary
        WHERE run_date = (
            SELECT MAX(run_date)
            FROM btc_backtest_summary
        )
        ORDER BY roi_pct DESC
    """

    try:

        df = pd.read_sql(
            query,
            connection
        )

        connection.close()

        if not df.empty:

            for column in [
                "run_date",
                "updated_at"
            ]:

                df[column] = pd.to_datetime(
                    df[column]
                )

        return df

    except Exception:

        try:
            connection.close()
        except:
            pass

        return pd.DataFrame()


# ============================================================
# LOAD PROFESSIONAL BACKTEST TRADES
# ============================================================

def load_backtest_trades(
    model_name=None
):

    connection = get_db_connection()

    if connection is None:
        return pd.DataFrame()

    params = []

    query = """
        SELECT
            run_date,
            trade_date,
            model_name,
            side,
            entry_price,
            exit_price,
            actual_return,
            strategy_return,
            capital_before,
            position_notional,
            gross_pnl,
            fee_amount,
            slippage_amount,
            net_pnl,
            capital_after,
            drawdown_pct
        FROM btc_backtest_trades
        WHERE run_date = (
            SELECT MAX(run_date)
            FROM btc_backtest_trades
        )
    """

    if model_name is not None:

        query += " AND model_name = %s"
        params.append(
            model_name
        )

    query += " ORDER BY trade_date ASC, model_name ASC"

    try:

        df = pd.read_sql(
            query,
            connection,
            params=tuple(params)
        )

        connection.close()

        if not df.empty:

            for column in [
                "run_date",
                "trade_date"
            ]:

                df[column] = pd.to_datetime(
                    df[column]
                )

        return df

    except Exception:

        try:
            connection.close()
        except:
            pass

        return pd.DataFrame()


# ============================================================
# FALLBACK WEEKLY PERFORMANCE
# IMPORTANT:
# Uses latest 7 completed prediction dates
# instead of simply last 7 calendar days.
# ============================================================

def calculate_weekly_performance(
    predictions_df
):

    if predictions_df.empty:
        return pd.DataFrame()

    df = predictions_df.copy()

    df = df[
        df["evaluated"] == 1
    ].copy()

    # Remove rows where actuals are unavailable
    df = df[
        df["actual_return"].notna()
        &
        df["actual_direction"].notna()
        &
        df["predicted_direction"].notna()
    ].copy()

    if df.empty:
        return pd.DataFrame()

    unique_dates = sorted(
        df[
            "prediction_date"
        ].dt.date.unique()
    )

    selected_dates = unique_dates[
        -7:
    ]

    df = df[
        df["prediction_date"].dt.date.isin(
            selected_dates
        )
    ].copy()

    if df.empty:
        return pd.DataFrame()

    records = []

    for model_name, group in df.groupby(
        "model_name"
    ):

        group = group.copy()

        error = (
            group["predicted_return"]
            -
            group["actual_return"]
        )

        mae = error.abs().mean()

        rmse = np.sqrt(
            (error ** 2).mean()
        )

        directional_accuracy = (
            group["predicted_direction"]
            ==
            group["actual_direction"]
        ).mean() * 100

        strategy_returns = []

        for _, row in group.iterrows():

            try:

                direction = int(
                    row["predicted_direction"]
                )

                actual_return = float(
                    row["actual_return"]
                )

                if direction == 1:

                    strategy_return = actual_return

                else:

                    strategy_return = -actual_return

                strategy_returns.append(
                    strategy_return
                )

            except Exception:

                continue

        if strategy_returns:

            compounded = (
                np.prod(
                    [
                        1 + r
                        for r in strategy_returns
                    ]
                )
                -
                1
            ) * 100

            total_strategy = sum(
                strategy_returns
            ) * 100

        else:

            compounded = 0.0
            total_strategy = 0.0

        records.append(
            {

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
                    ].mean() * 100,

                "avg_actual_return":
                    group[
                        "actual_return"
                    ].mean() * 100,

                "total_strategy_return":
                    total_strategy,

                "compounded_strategy_return":
                    compounded,

                "win_rate":
                    directional_accuracy
            }
        )

    result = pd.DataFrame(
        records
    )

    if result.empty:
        return result

    result = result.sort_values(
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

    result["model_rank"] = (
        result.index + 1
    )

    return result


# ============================================================
# LATEST WEEKLY PERFORMANCE
# ============================================================

def get_latest_weekly_performance():

    performance = (
        load_model_performance()
    )

    if performance.empty:

        predictions = (
            load_all_ml_predictions()
        )

        return calculate_weekly_performance(
            predictions
        )

    latest_evaluation_date = (
        performance[
            "evaluation_date"
        ].max()
    )

    latest = performance[
        performance[
            "evaluation_date"
        ]
        ==
        latest_evaluation_date
    ].copy()

    if latest.empty:

        predictions = (
            load_all_ml_predictions()
        )

        return calculate_weekly_performance(
            predictions
        )

    return latest.sort_values(
        "model_rank"
    ).reset_index(
        drop=True
    )


# ============================================================
# AI CONSENSUS
# ============================================================

def calculate_ai_consensus(
    latest_predictions
):

    if latest_predictions.empty:

        return {
            "direction": "N/A",
            "confidence": 0,
            "up_count": 0,
            "down_count": 0,
            "total": 0,
            "average_return": 0
        }

    df = latest_predictions.copy()

    df = df[
        df["predicted_direction"].notna()
    ].copy()

    if df.empty:

        return {
            "direction": "N/A",
            "confidence": 0,
            "up_count": 0,
            "down_count": 0,
            "total": 0,
            "average_return": 0
        }

    directions = pd.to_numeric(
        df["predicted_direction"],
        errors="coerce"
    ).dropna()

    up_count = int(
        (directions == 1).sum()
    )

    down_count = int(
        (directions == 0).sum()
    )

    total = len(directions)

    if up_count > down_count:

        direction = "BULLISH"

        confidence = (
            up_count / total
        ) * 100

    elif down_count > up_count:

        direction = "BEARISH"

        confidence = (
            down_count / total
        ) * 100

    else:

        direction = "NEUTRAL"

        confidence = 50

    average_return = pd.to_numeric(
        df["predicted_return"],
        errors="coerce"
    ).mean()

    if pd.isna(average_return):
        average_return = 0

    return {

        "direction":
            direction,

        "confidence":
            confidence,

        "up_count":
            up_count,

        "down_count":
            down_count,

        "total":
            total,

        "average_return":
            average_return
    }


# ============================================================
# SIGNAL STRENGTH
# ============================================================

def calculate_signal_strength(
    consensus,
    technical_results
):

    score = 50.0

    # AI consensus
    confidence = consensus.get(
        "confidence",
        50
    )

    if consensus.get(
        "direction"
    ) == "BULLISH":

        score += (
            confidence - 50
        ) * 0.50

    elif consensus.get(
        "direction"
    ) == "BEARISH":

        score -= (
            confidence - 50
        ) * 0.50

    # RSI
    try:

        rsi = float(
            technical_results[
                "rsi"
            ][
                "value"
            ]
        )

        if 50 < rsi < 70:
            score += 5

        elif 30 < rsi < 50:
            score -= 5

        elif rsi >= 70:
            score -= 8

        elif rsi <= 30:
            score += 8

    except Exception:
        pass

    # Market structure
    try:

        trend = (
            technical_results[
                "market_structure"
            ][
                "trend_regime"
            ]
        )

        if trend == "Uptrend":
            score += 8

        elif trend == "Downtrend":
            score -= 8

    except Exception:
        pass

    score = max(
        0,
        min(
            100,
            score
        )
    )

    if score >= 75:

        label = "STRONG BULLISH"

    elif score >= 60:

        label = "BULLISH"

    elif score <= 25:

        label = "STRONG BEARISH"

    elif score <= 40:

        label = "BEARISH"

    else:

        label = "NEUTRAL"

    return score, label


# ============================================================
# MARKET RISK SCORE
# ============================================================

def calculate_risk_score(
    results,
    predictions
):

    score = 50.0
    reasons = []

    # ATR volatility
    try:

        percentile = float(
            results[
                "atr"
            ].get(
                "percentile",
                50
            )
        )

        if percentile >= 80:

            score += 20
            reasons.append(
                "High ATR volatility"
            )

        elif percentile >= 60:

            score += 10
            reasons.append(
                "Elevated volatility"
            )

        elif percentile <= 20:

            score -= 10
            reasons.append(
                "Low volatility"
            )

    except Exception:
        pass

    # Bollinger squeeze
    try:

        squeeze = str(
            results[
                "bollinger_bands"
            ].get(
                "squeeze",
                "No"
            )
        ).lower()

        if squeeze in [
            "yes",
            "true",
            "1"
        ]:

            score += 8

            reasons.append(
                "Bollinger squeeze"
            )

    except Exception:
        pass

    # AI disagreement
    try:

        if not predictions.empty:

            latest_date = (
                predictions[
                    "prediction_date"
                ].max()
            )

            latest = predictions[
                predictions[
                    "prediction_date"
                ]
                ==
                latest_date
            ]

            dirs = pd.to_numeric(
                latest[
                    "predicted_direction"
                ],
                errors="coerce"
            ).dropna()

            if len(dirs) > 0:

                up_ratio = (
                    dirs == 1
                ).mean()

                disagreement = min(
                    up_ratio,
                    1 - up_ratio
                )

                if (
                    0.35
                    <
                    disagreement
                    <
                    0.50
                ):

                    score += 12

                    reasons.append(
                        "High model disagreement"
                    )

    except Exception:
        pass

    score = max(
        0,
        min(
            100,
            score
        )
    )

    if score >= 75:

        risk_level = "HIGH"

    elif score >= 55:

        risk_level = "MEDIUM"

    elif score >= 35:

        risk_level = "LOW"

    else:

        risk_level = "VERY LOW"

    return score, risk_level, reasons


# ============================================================
# HISTORICAL MODEL METRICS
# ============================================================

def calculate_historical_metrics(
    predictions
):

    if predictions.empty:
        return pd.DataFrame()

    df = predictions.copy()

    df = df[
        (df["evaluated"] == 1)
        &
        df["actual_return"].notna()
        &
        df["actual_direction"].notna()
    ].copy()

    if df.empty:
        return pd.DataFrame()

    records = []

    for model_name, group in df.groupby(
        "model_name"
    ):

        error = (
            group["predicted_return"]
            -
            group["actual_return"]
        )

        accuracy = (
            group["predicted_direction"]
            ==
            group["actual_direction"]
        ).mean() * 100

        strategy_returns = []

        for _, row in group.iterrows():

            try:

                actual = float(
                    row["actual_return"]
                )

                direction = int(
                    row["predicted_direction"]
                )

                strategy_returns.append(
                    actual
                    if direction == 1
                    else -actual
                )

            except Exception:
                pass

        if strategy_returns:

            compounded = (
                np.prod(
                    [
                        1 + r
                        for r in strategy_returns
                    ]
                )
                -
                1
            ) * 100

        else:

            compounded = 0

        records.append(
            {

                "model_name":
                    model_name,

                "predictions":
                    len(group),

                "accuracy":
                    accuracy,

                "mae":
                    error.abs().mean(),

                "rmse":
                    np.sqrt(
                        (error ** 2).mean()
                    ),

                "strategy_return":
                    sum(
                        strategy_returns
                    ) * 100,

                "compounded_return":
                    compounded
            }
        )

    return pd.DataFrame(
        records
    )


# ============================================================
# EQUITY CURVE
# ============================================================

def calculate_equity_curve(
    predictions,
    model_name,
    initial_capital=10000
):

    if predictions.empty:
        return pd.DataFrame()

    df = predictions[
        predictions["model_name"]
        ==
        model_name
    ].copy()

    df = df[
        (df["evaluated"] == 1)
        &
        df["actual_return"].notna()
        &
        df["predicted_direction"].notna()
    ].copy()

    if df.empty:
        return pd.DataFrame()

    df = df.sort_values(
        "prediction_date"
    )

    capital = float(
        initial_capital
    )

    records = []

    for _, row in df.iterrows():

        try:

            actual_return = float(
                row["actual_return"]
            )

            direction = int(
                row["predicted_direction"]
            )

            strategy_return = (
                actual_return
                if direction == 1
                else -actual_return
            )

            capital *= (
                1 + strategy_return
            )

            records.append(
                {
                    "date":
                        row["prediction_date"],

                    "strategy_return":
                        strategy_return * 100,

                    "equity":
                        capital
                }
            )

        except Exception:
            continue

    return pd.DataFrame(
        records
    )


# ============================================================
# MAX DRAWDOWN
# ============================================================

def calculate_max_drawdown(
    equity_df
):

    if equity_df.empty:
        return 0.0

    equity = equity_df[
        "equity"
    ]

    running_max = (
        equity.cummax()
    )

    drawdown = (
        equity / running_max
        - 1
    ) * 100

    return float(
        drawdown.min()
    )


# ============================================================
# SEND EMAIL
# ============================================================

def send_email_report():

    if BTCEmailSender is None:

        st.error(
            "❌ btc_email_sender.py could not be imported."
        )

        return

    with st.spinner(
        "📧 Sending email..."
    ):

        try:

            email_sender = (
                BTCEmailSender()
            )

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

                success = (
                    email_sender.send_email(
                        subject,
                        html_content
                    )
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

        with open(
            filename,
            "w"
        ) as f:

            json.dump(
                st.session_state.results,
                f,
                default=convert,
                indent=2
            )

        st.success(
            f"✅ Data exported to {filename}"
        )

        with open(
            filename,
            "r"
        ) as f:

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
# DIRECTION TEXT
# ============================================================

def direction_text(direction):

    try:

        direction = int(direction)

        if direction == 1:
            return "🟢 UP"

        return "🔴 DOWN"

    except Exception:

        return "⚪ N/A"


# ============================================================
# ML DASHBOARD
# ============================================================

def display_ml_dashboard():

    st.markdown(
        """
        <div class="ml-header">
        <b>🤖 AI / ML Prediction Center</b>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.caption(
        "Six machine-learning and deep-learning models "
        "predicting the next BTC move."
    )

    # ========================================================
    # DATA
    # ========================================================

    predictions = load_ml_predictions(
        days=7
    )

    performance = (
        get_latest_weekly_performance()
    )

    all_predictions = (
        load_all_ml_predictions()
    )

    st.session_state.ml_data = predictions
    st.session_state.ml_performance = performance

    if predictions.empty:

        st.warning(
            "⚠️ No ML predictions found yet."
        )

        st.info(
            "Run daily_prediction.py first."
        )

        return

    # ========================================================
    # LATEST PREDICTIONS
    # ========================================================

    latest_prediction_date = (
        predictions[
            "prediction_date"
        ].max()
    )

    latest_predictions = predictions[
        predictions[
            "prediction_date"
        ]
        ==
        latest_prediction_date
    ].copy()

    # ========================================================
    # AI CONSENSUS
    # ========================================================

    consensus = calculate_ai_consensus(
        latest_predictions
    )

    signal_strength, signal_label = (
        calculate_signal_strength(
            consensus,
            st.session_state.results
            or {}
        )
    )

    risk_score, risk_level, risk_reasons = (
        calculate_risk_score(
            st.session_state.results
            or {},
            predictions
        )
    )

    # ========================================================
    # AI CONSENSUS SECTION
    # ========================================================

    st.subheader(
        "🧠 AI Model Consensus"
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:

        if consensus["direction"] == "BULLISH":

            st.success(
                "🟢 BULLISH"
            )

        elif consensus["direction"] == "BEARISH":

            st.error(
                "🔴 BEARISH"
            )

        else:

            st.warning(
                "🟡 NEUTRAL"
            )

        st.caption(
            "Overall AI Direction"
        )

    with c2:

        st.metric(
            "🎯 Consensus Confidence",
            f"{consensus['confidence']:.1f}%"
        )

    with c3:

        st.metric(
            "🟢 UP Models",
            consensus["up_count"]
        )

    with c4:

        st.metric(
            "🔴 DOWN Models",
            consensus["down_count"]
        )

    with c5:

        st.metric(
            "📈 Avg Expected Return",
            f"{consensus['average_return'] * 100:+.2f}%"
        )

    # ========================================================
    # SIGNAL STRENGTH + RISK
    # ========================================================

    c1, c2 = st.columns(2)

    with c1:

        st.subheader(
            "🔥 Signal Strength"
        )

        st.progress(
            int(signal_strength)
        )

        st.metric(
            "Signal Score",
            f"{signal_strength:.0f}/100"
        )

        st.caption(
            signal_label
        )

    with c2:

        st.subheader(
            "⚠️ Market Risk"
        )

        st.progress(
            int(risk_score)
        )

        st.metric(
            "Risk Score",
            f"{risk_score:.0f}/100"
        )

        st.caption(
            f"Risk Level: {risk_level}"
        )

        if risk_reasons:

            st.write(
                "**Risk Factors:**"
            )

            for reason in risk_reasons:

                st.write(
                    f"• {reason}"
                )

    # ========================================================
    # TOP METRICS
    # ========================================================

    winner = None

    if not performance.empty:

        performance = (
            performance.sort_values(
                "model_rank"
            )
        )

        winner = performance.iloc[0]

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "🏆 Weekly Winner",
            DISPLAY_NAMES.get(
                winner["model_name"],
                winner["model_name"]
            )
            if winner is not None
            else "N/A"
        )

    with c2:

        st.metric(
            "🎯 Best Accuracy",
            (
                f"{float(winner['directional_accuracy']):.2f}%"
                if winner is not None
                else "N/A"
            )
        )

    with c3:

        if winner is not None:

            compounded = winner.get(
                "compounded_strategy_return",
                winner.get(
                    "total_strategy_return",
                    0
                )
            )

            st.metric(
                "📈 Compounded Return",
                f"{float(compounded):+.2f}%"
            )

        else:

            st.metric(
                "📈 Compounded Return",
                "N/A"
            )

    with c4:

        st.metric(
            "📅 Latest Prediction",
            latest_prediction_date.strftime(
                "%d %b %Y"
            )
        )

    # ========================================================
    # MODEL PREDICTION CARDS
    # ========================================================

    st.subheader(
        f"🔮 Current Predictions — "
        f"{latest_prediction_date.strftime('%d %b %Y')}"
    )

    existing_models = [
        model
        for model in MODEL_ORDER
        if model in
        latest_predictions[
            "model_name"
        ].values
    ]

    cols = st.columns(3)

    for index, model_name in enumerate(
        existing_models
    ):

        row = latest_predictions[
            latest_predictions[
                "model_name"
            ]
            ==
            model_name
        ]

        if row.empty:
            continue

        row = row.iloc[0]

        with cols[
            index % 3
        ]:

            with st.container(
                border=True
            ):

                st.markdown(
                    f"### 🤖 "
                    f"{DISPLAY_NAMES.get(model_name, model_name)}"
                )

                predicted_price = row[
                    "predicted_price"
                ]

                predicted_return = row[
                    "predicted_return"
                ]

                predicted_direction = row[
                    "predicted_direction"
                ]

                if pd.notna(
                    predicted_price
                ):

                    st.metric(
                        "Predicted BTC Price",
                        f"${float(predicted_price):,.2f}"
                    )

                else:

                    st.metric(
                        "Predicted BTC Price",
                        "N/A"
                    )

                if pd.notna(
                    predicted_return
                ):

                    st.write(
                        "**Expected Return:** "
                        f"{float(predicted_return) * 100:+.2f}%"
                    )

                else:

                    st.write(
                        "**Expected Return:** N/A"
                    )

                if pd.notna(
                    predicted_direction
                ):

                    if int(
                        predicted_direction
                    ) == 1:

                        st.success(
                            "🟢 Direction: UP"
                        )

                    else:

                        st.error(
                            "🔴 Direction: DOWN"
                        )

    # ========================================================
    # MODEL LEADERBOARD
    # ========================================================

    st.subheader(
        "🏆 Model Leaderboard"
    )

    if performance.empty:

        st.info(
            "No evaluated model performance available."
        )

    else:

        leaderboard = performance.copy()

        leaderboard["Model"] = (
            leaderboard[
                "model_name"
            ].map(
                lambda x:
                    DISPLAY_NAMES.get(
                        x,
                        x
                    )
            )
        )

        leaderboard["Rank"] = (
            leaderboard[
                "model_rank"
            ].astype(int)
        )

        leaderboard["Accuracy"] = (
            leaderboard[
                "directional_accuracy"
            ].apply(
                lambda x:
                    f"{float(x):.2f}%"
            )
        )

        leaderboard["MAE"] = (
            leaderboard[
                "mae"
            ].apply(
                lambda x:
                    f"{float(x):.5f}"
            )
        )

        leaderboard["RMSE"] = (
            leaderboard[
                "rmse"
            ].apply(
                lambda x:
                    f"{float(x):.5f}"
            )
        )

        leaderboard["Win Rate"] = (
            leaderboard[
                "win_rate"
            ].apply(
                lambda x:
                    f"{float(x):.2f}%"
            )
        )

        leaderboard["Simple Return"] = (
            leaderboard[
                "total_strategy_return"
            ].apply(
                lambda x:
                    f"{float(x):+.2f}%"
            )
        )

        leaderboard["Compounded Return"] = (
            leaderboard[
                "compounded_strategy_return"
            ].apply(
                lambda x:
                    f"{float(x):+.2f}%"
            )
        )

        leaderboard = leaderboard[
            [
                "Rank",
                "Model",
                "Accuracy",
                "MAE",
                "RMSE",
                "Win Rate",
                "Simple Return",
                "Compounded Return"
            ]
        ]

        st.dataframe(
            leaderboard,
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # 7 DAY PREDICTION TABLE
    # ========================================================

    st.subheader(
        "📅 7-Day Model Predictions"
    )

    table = predictions.copy()

    table["Model"] = (
        table[
            "model_name"
        ].map(
            lambda x:
                DISPLAY_NAMES.get(
                    x,
                    x
                )
        )
    )

    table["Date"] = (
        table[
            "prediction_date"
        ].dt.strftime(
            "%d %b"
        )
    )

    table["Predicted Price"] = (
        table[
            "predicted_price"
        ].apply(
            lambda x:
                f"${x:,.2f}"
                if pd.notna(x)
                else "N/A"
        )
    )

    table["Predicted Return"] = (
        table[
            "predicted_return"
        ].apply(
            lambda x:
                f"{x * 100:+.2f}%"
                if pd.notna(x)
                else "N/A"
        )
    )

    table["Direction"] = (
        table[
            "predicted_direction"
        ].apply(
            direction_text
        )
    )

    table["Actual Price"] = (
        table[
            "actual_price"
        ].apply(
            lambda x:
                f"${x:,.2f}"
                if pd.notna(x)
                else "Pending"
        )
    )

    table["Actual Return"] = (
        table[
            "actual_return"
        ].apply(
            lambda x:
                f"{x * 100:+.2f}%"
                if pd.notna(x)
                else "Pending"
        )
    )

    def result_status(row):

        try:

            if pd.notna(
                row["actual_direction"]
            ):

                if (
                    int(
                        row[
                            "predicted_direction"
                        ]
                    )
                    ==
                    int(
                        row[
                            "actual_direction"
                        ]
                    )
                ):

                    return "✅ Correct"

                return "❌ Wrong"

            return "⏳ Pending"

        except Exception:

            return "⏳ Pending"

    table["Result"] = (
        table.apply(
            result_status,
            axis=1
        )
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
    # PREDICTION ERROR ANALYSIS
    # ========================================================

    st.subheader(
        "🎯 Prediction Error Analysis"
    )

    evaluated = all_predictions[
        (all_predictions["evaluated"] == 1)
        &
        all_predictions[
            "actual_return"
        ].notna()
    ].copy()

    if evaluated.empty:

        st.info(
            "Not enough evaluated predictions yet."
        )

    else:

        evaluated["error"] = (
            evaluated[
                "predicted_return"
            ]
            -
            evaluated[
                "actual_return"
            ]
        )

        error_summary = (
            evaluated
            .groupby("model_name")
            .agg(
                predictions=(
                    "error",
                    "count"
                ),
                mean_error=(
                    "error",
                    "mean"
                ),
                mae=(
                    "error",
                    lambda x:
                        np.abs(x).mean()
                ),
                rmse=(
                    "error",
                    lambda x:
                        np.sqrt(
                            np.mean(
                                x ** 2
                            )
                        )
                )
            )
            .reset_index()
        )

        error_summary["Model"] = (
            error_summary[
                "model_name"
            ].map(
                lambda x:
                    DISPLAY_NAMES.get(
                        x,
                        x
                    )
            )
        )

        error_display = error_summary[
            [
                "Model",
                "predictions",
                "mean_error",
                "mae",
                "rmse"
            ]
        ].copy()

        error_display.columns = [
            "Model",
            "Predictions",
            "Mean Error",
            "MAE",
            "RMSE"
        ]

        error_display["Mean Error"] = (
            error_display[
                "Mean Error"
            ] * 100
        ).map(
            lambda x:
                f"{x:+.3f}%"
        )

        error_display["MAE"] = (
            error_display[
                "MAE"
            ] * 100
        ).map(
            lambda x:
                f"{x:.3f}%"
        )

        error_display["RMSE"] = (
            error_display[
                "RMSE"
            ] * 100
        ).map(
            lambda x:
                f"{x:.3f}%"
        )

        st.dataframe(
            error_display,
            use_container_width=True,
            hide_index=True
        )

        fig_error = go.Figure()

        for model_name in MODEL_ORDER:

            model_data = evaluated[
                evaluated[
                    "model_name"
                ]
                ==
                model_name
            ].sort_values(
                "prediction_date"
            )

            if model_data.empty:
                continue

            fig_error.add_trace(
                go.Scatter(
                    x=model_data[
                        "prediction_date"
                    ],
                    y=model_data[
                        "error"
                    ] * 100,
                    mode="lines+markers",
                    name=DISPLAY_NAMES.get(
                        model_name,
                        model_name
                    )
                )
            )

        fig_error.add_hline(
            y=0,
            line_dash="dash"
        )

        fig_error.update_layout(
            height=450,
            title="Prediction Error Over Time",
            xaxis_title="Date",
            yaxis_title="Prediction Error (%)",
            hovermode="x unified"
        )

        st.plotly_chart(
            fig_error,
            use_container_width=True
        )

    # ========================================================
    # WEEKLY MODEL PERFORMANCE
    # ========================================================

    st.subheader(
        "🏆 Weekly Model Performance"
    )

    if performance.empty:

        st.info(
            "No evaluated weekly performance available yet."
        )

    else:

        performance_display = performance.copy()

        performance_display["Model"] = (
            performance_display[
                "model_name"
            ].map(
                lambda x:
                    DISPLAY_NAMES.get(
                        x,
                        x
                    )
            )
        )

        performance_display["Rank"] = (
            performance_display[
                "model_rank"
            ].astype(int)
        )

        performance_display["Predictions"] = (
            performance_display[
                "total_predictions"
            ]
        )

        performance_display["MAE"] = (
            performance_display[
                "mae"
            ].apply(
                lambda x:
                    f"{float(x):.5f}"
            )
        )

        performance_display["RMSE"] = (
            performance_display[
                "rmse"
            ].apply(
                lambda x:
                    f"{float(x):.5f}"
            )
        )

        performance_display["Accuracy"] = (
            performance_display[
                "directional_accuracy"
            ].apply(
                lambda x:
                    f"{float(x):.2f}%"
            )
        )

        performance_display["Win Rate"] = (
            performance_display[
                "win_rate"
            ].apply(
                lambda x:
                    f"{float(x):.2f}%"
            )
        )

        performance_display[
            "Strategy Return"
        ] = (
            performance_display[
                "total_strategy_return"
            ].apply(
                lambda x:
                    f"{float(x):+.2f}%"
            )
        )

        performance_display[
            "Compounded Return"
        ] = (
            performance_display[
                "compounded_strategy_return"
            ].apply(
                lambda x:
                    f"{float(x):+.2f}%"
            )
        )

        performance_display = (
            performance_display[
                [
                    "Rank",
                    "Model",
                    "Predictions",
                    "MAE",
                    "RMSE",
                    "Accuracy",
                    "Win Rate",
                    "Strategy Return",
                    "Compounded Return"
                ]
            ]
        )

        st.dataframe(
            performance_display,
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # PREDICTED VS ACTUAL PRICE
    # ========================================================

    st.subheader(
        "📈 Predicted vs Actual BTC Price"
    )

    chart_df = predictions.copy()

    fig = go.Figure()

    actual = (
        chart_df[
            [
                "prediction_date",
                "actual_price"
            ]
        ]
        .drop_duplicates()
        .sort_values(
            "prediction_date"
        )
    )

    actual = actual[
        actual[
            "actual_price"
        ].notna()
    ]

    if not actual.empty:

        fig.add_trace(
            go.Scatter(
                x=actual[
                    "prediction_date"
                ],
                y=actual[
                    "actual_price"
                ],
                mode="lines+markers",
                name="Actual BTC Price",
                line=dict(
                    width=4
                )
            )
        )

    for model_name in MODEL_ORDER:

        model_data = chart_df[
            chart_df[
                "model_name"
            ]
            ==
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
                name=DISPLAY_NAMES.get(
                    model_name,
                    model_name
                )
            )
        )

    fig.update_layout(
        height=500,
        xaxis_title="Prediction Date",
        yaxis_title="BTC Price (USD)",
        hovermode="x unified"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # ========================================================
    # ACCURACY OVER TIME
    # ========================================================

    st.subheader(
        "📈 Model Accuracy Over Time"
    )

    if evaluated.empty:

        st.info(
            "Not enough evaluated predictions."
        )

    else:

        accuracy_time = (
            evaluated
            .copy()
        )

        accuracy_time["correct"] = (
            accuracy_time[
                "predicted_direction"
            ]
            ==
            accuracy_time[
                "actual_direction"
            ]
        ).astype(int)

        accuracy_time = (
            accuracy_time
            .sort_values(
                "prediction_date"
            )
        )

        fig_acc_time = go.Figure()

        for model_name in MODEL_ORDER:

            model_data = (
                accuracy_time[
                    accuracy_time[
                        "model_name"
                    ]
                    ==
                    model_name
                ]
                .copy()
            )

            if model_data.empty:
                continue

            model_data[
                "rolling_accuracy"
            ] = (
                model_data[
                    "correct"
                ]
                .rolling(
                    7,
                    min_periods=1
                )
                .mean()
                * 100
            )

            fig_acc_time.add_trace(
                go.Scatter(
                    x=model_data[
                        "prediction_date"
                    ],
                    y=model_data[
                        "rolling_accuracy"
                    ],
                    mode="lines",
                    name=DISPLAY_NAMES.get(
                        model_name,
                        model_name
                    )
                )
            )

        fig_acc_time.add_hline(
            y=50,
            line_dash="dash",
            annotation_text="50% baseline"
        )

        fig_acc_time.update_layout(
            height=450,
            xaxis_title="Prediction Date",
            yaxis_title="7-Prediction Rolling Accuracy (%)",
            hovermode="x unified"
        )

        st.plotly_chart(
            fig_acc_time,
            use_container_width=True
        )

    # ========================================================
    # ACCURACY BAR
    # ========================================================

    if not performance.empty:

        st.subheader(
            "🎯 Model Directional Accuracy"
        )

        accuracy_df = performance.copy()

        accuracy_df["Model"] = (
            accuracy_df[
                "model_name"
            ].map(
                lambda x:
                    DISPLAY_NAMES.get(
                        x,
                        x
                    )
            )
        )

        accuracy_df = (
            accuracy_df.sort_values(
                "directional_accuracy",
                ascending=True
            )
        )

        fig_accuracy = go.Figure()

        fig_accuracy.add_trace(
            go.Bar(
                x=accuracy_df[
                    "directional_accuracy"
                ],
                y=accuracy_df[
                    "Model"
                ],
                orientation="h",
                text=accuracy_df[
                    "directional_accuracy"
                ].apply(
                    lambda x:
                        f"{x:.1f}%"
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
                        ].max()
                        + 10
                    )
                ]
            )
        )

        st.plotly_chart(
            fig_accuracy,
            use_container_width=True
        )

    # ========================================================
    # STRATEGY RETURN
    # ========================================================

    if not performance.empty:

        st.subheader(
            "💰 Strategy Returns"
        )

        return_df = performance.copy()

        return_df["Model"] = (
            return_df[
                "model_name"
            ].map(
                lambda x:
                    DISPLAY_NAMES.get(
                        x,
                        x
                    )
            )
        )

        fig_return = go.Figure()

        fig_return.add_trace(
            go.Bar(
                x=return_df[
                    "compounded_strategy_return"
                ],
                y=return_df[
                    "Model"
                ],
                orientation="h",
                text=return_df[
                    "compounded_strategy_return"
                ].apply(
                    lambda x:
                        f"{x:+.2f}%"
                ),
                textposition="auto"
            )
        )

        fig_return.update_layout(
            height=400,
            title="Compounded Strategy Return",
            xaxis_title="Return (%)",
            yaxis_title="Model"
        )

        st.plotly_chart(
            fig_return,
            use_container_width=True
        )

    # ========================================================
    # HISTORICAL BACKTEST
    # ========================================================

    st.subheader(
        "🧪 Historical Backtest"
    )

    backtest_summary = load_backtest_summary()

    bt1, bt2, bt3, bt4 = st.columns(4)

    with bt1:

        backtest_initial_capital = st.number_input(
            "Initial Capital ($)",
            min_value=100.0,
            value=10000.0,
            step=1000.0,
            key="professional_backtest_initial_capital"
        )

    with bt2:

        backtest_risk = st.number_input(
            "Risk Per Trade (%)",
            min_value=0.1,
            max_value=100.0,
            value=2.0,
            step=0.1,
            key="professional_backtest_risk"
        )

    with bt3:

        backtest_fee_bps = st.number_input(
            "Fee Per Side (bps)",
            min_value=0.0,
            value=10.0,
            step=1.0,
            key="professional_backtest_fee_bps"
        )

    with bt4:

        backtest_slippage_bps = st.number_input(
            "Slippage Per Side (bps)",
            min_value=0.0,
            value=5.0,
            step=1.0,
            key="professional_backtest_slippage_bps"
        )

    if st.button(
        "Run / Refresh Backtest",
        key="run_professional_backtest"
    ):

        if run_backtests is None:

            st.error(
                "backtesting.py could not be imported."
            )

        else:

            with st.spinner(
                "Running model backtests and saving stats..."
            ):

                try:

                    summary_df, trades_df = run_backtests(
                        initial_capital=backtest_initial_capital,
                        risk_per_trade=backtest_risk / 100,
                        fee_bps=backtest_fee_bps,
                        slippage_bps=backtest_slippage_bps
                    )

                    if summary_df.empty:

                        st.warning(
                            "No evaluated predictions available "
                            "for backtesting yet."
                        )

                    else:

                        st.success(
                            f"Backtest saved: "
                            f"{len(summary_df)} models, "
                            f"{len(trades_df):,} trades."
                        )

                        backtest_summary = load_backtest_summary()

                except Exception as e:

                    st.error(
                        f"Backtest failed: {e}"
                    )

    if not backtest_summary.empty:
        best_backtest = backtest_summary.iloc[0]

        m1, m2, m3, m4 = st.columns(4)

        with m1:
            best_model_name = best_backtest["model_name"]
            st.metric(
                "Best Model",
                DISPLAY_NAMES.get(best_model_name, best_model_name)
            )

        with m2:
            st.metric(
                "Final Capital",
                f"${best_backtest['final_capital']:,.2f}"
            )

        with m3:
            st.metric(
                "ROI",
                f"{best_backtest['roi_pct']:+.2f}%"
            )

        with m4:
            st.metric(
                "Sharpe Ratio",
                f"{best_backtest['sharpe_ratio']:.2f}"
            )

        comparison = backtest_summary.copy()

        comparison["Model"] = comparison["model_name"].map(
            lambda x:
                DISPLAY_NAMES.get(
                    x,
                    x
                )
        )

        for column, label, template in [
            ("final_capital", "Final Capital", "${:,.2f}"),
            ("roi_pct", "ROI", "{:+.2f}%"),
            ("win_rate_pct", "Win Rate", "{:.2f}%"),
            ("max_drawdown_pct", "Max Drawdown", "{:.2f}%"),
            ("sharpe_ratio", "Sharpe", "{:.2f}"),
            ("net_pnl", "Net PnL", "${:,.2f}"),
            ("total_fees", "Fees", "${:,.2f}"),
            ("total_slippage", "Slippage", "${:,.2f}")
        ]:

            comparison[label] = comparison[column].map(
                lambda x, fmt=template:
                    fmt.format(x)
            )

        comparison_table = comparison[
            [
                "Model",
                "Final Capital",
                "ROI",
                "Win Rate",
                "Max Drawdown",
                "Sharpe",
                "total_trades",
                "winning_trades",
                "losing_trades",
                "Net PnL",
                "Fees",
                "Slippage"
            ]
        ]

        comparison_table.columns = [
            "Model",
            "Final Capital",
            "ROI",
            "Win Rate",
            "Max Drawdown",
            "Sharpe",
            "Trades",
            "Winning",
            "Losing",
            "Net PnL",
            "Fees",
            "Slippage"
        ]

        st.dataframe(
            comparison_table,
            use_container_width=True,
            hide_index=True
        )

        valid_models = backtest_summary["model_name"].tolist()

        selected_model = st.selectbox(
            "Select Model",
            valid_models,
            format_func=lambda x:
                DISPLAY_NAMES.get(
                    x,
                    x
                ),
            key="professional_backtest_model"
        )

        selected_summary = backtest_summary[
            backtest_summary["model_name"]
            ==
            selected_model
        ].iloc[0]

        s1, s2, s3, s4 = st.columns(4)

        with s1:

            st.metric(
                "Trades",
                f"{int(selected_summary['total_trades'])}"
            )

        with s2:

            st.metric(
                "Winning / Losing",
                (
                    f"{int(selected_summary['winning_trades'])}"
                    f" / "
                    f"{int(selected_summary['losing_trades'])}"
                )
            )

        with s3:

            st.metric(
                "Total Fees",
                f"${selected_summary['total_fees']:,.2f}"
            )

        with s4:

            st.metric(
                "Total Slippage",
                f"${selected_summary['total_slippage']:,.2f}"
            )

        trades = load_backtest_trades(
            selected_model
        )

        if not trades.empty:
            fig_equity = go.Figure()

            fig_equity.add_trace(
                go.Scatter(
                    x=trades["trade_date"],
                    y=trades["capital_after"],
                    mode="lines+markers",
                    name="Equity"
                )
            )

            fig_equity.update_layout(
                height=450,
                title=f"Equity Curve - {DISPLAY_NAMES.get(selected_model, selected_model)}",
                xaxis_title="Date",
                yaxis_title="Portfolio Value ($)",
                hovermode="x unified"
            )

            st.plotly_chart(
                fig_equity,
                use_container_width=True
            )

            trade_view = trades.tail(25).copy()

            trade_view["Date"] = trade_view[
                "trade_date"
            ].dt.strftime(
                "%Y-%m-%d"
            )

            trade_view["Return"] = trade_view[
                "strategy_return"
            ].map(
                lambda x:
                    f"{x * 100:+.2f}%"
            )

            trade_view["Net PnL"] = trade_view[
                "net_pnl"
            ].map(
                lambda x:
                    f"${x:,.2f}"
            )

            trade_view["Capital"] = trade_view[
                "capital_after"
            ].map(
                lambda x:
                    f"${x:,.2f}"
            )

            st.dataframe(
                trade_view[
                    [
                        "Date",
                        "side",
                        "entry_price",
                        "exit_price",
                        "Return",
                        "position_notional",
                        "Net PnL",
                        "Capital",
                        "drawdown_pct"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

    if backtest_summary.empty:

        st.info(
            "Professional backtest stats will appear after "
            "running backtesting.py or clicking refresh above."
        )

    show_legacy_backtest = False

    if show_legacy_backtest and all_predictions.empty:

        st.info(
            "No historical prediction data available."
        )

    elif show_legacy_backtest:

        valid_models = [
            m
            for m in MODEL_ORDER
            if m in all_predictions[
                "model_name"
            ].unique()
        ]

        if valid_models:

            selected_model = st.selectbox(
                "Select Model",
                valid_models,
                format_func=lambda x:
                    DISPLAY_NAMES.get(
                        x,
                        x
                    ),
                key="backtest_model"
            )

            initial_capital = st.number_input(
                "Initial Capital ($)",
                min_value=100.0,
                value=10000.0,
                step=1000.0
            )

            equity = calculate_equity_curve(
                all_predictions,
                selected_model,
                initial_capital
            )

            if equity.empty:

                st.info(
                    "Not enough evaluated predictions "
                    "for backtesting."
                )

            else:

                final_equity = float(
                    equity[
                        "equity"
                    ].iloc[-1]
                )

                total_return = (
                    final_equity
                    /
                    initial_capital
                    - 1
                ) * 100

                max_drawdown = (
                    calculate_max_drawdown(
                        equity
                    )
                )

                wins = (
                    equity[
                        "strategy_return"
                    ] > 0
                ).sum()

                losses = (
                    equity[
                        "strategy_return"
                    ] <= 0
                ).sum()

                total_trades = (
                    wins + losses
                )

                win_rate = (
                    wins
                    /
                    total_trades
                    * 100
                    if total_trades > 0
                    else 0
                )

                c1, c2, c3, c4 = st.columns(4)

                with c1:

                    st.metric(
                        "Initial Capital",
                        f"${initial_capital:,.2f}"
                    )

                with c2:

                    st.metric(
                        "Final Capital",
                        f"${final_equity:,.2f}"
                    )

                with c3:

                    st.metric(
                        "Total Return",
                        f"{total_return:+.2f}%"
                    )

                with c4:

                    st.metric(
                        "Max Drawdown",
                        f"{max_drawdown:.2f}%"
                    )

                st.metric(
                    "Backtest Win Rate",
                    f"{win_rate:.2f}%"
                )

                fig_equity = go.Figure()

                fig_equity.add_trace(
                    go.Scatter(
                        x=equity[
                            "date"
                        ],
                        y=equity[
                            "equity"
                        ],
                        mode="lines+markers",
                        name="Equity"
                    )
                )

                fig_equity.update_layout(
                    height=450,
                    title=(
                        f"Equity Curve — "
                        f"{DISPLAY_NAMES.get(selected_model, selected_model)}"
                    ),
                    xaxis_title="Date",
                    yaxis_title="Portfolio Value ($)",
                    hovermode="x unified"
                )

                st.plotly_chart(
                    fig_equity,
                    use_container_width=True
                )

    # ========================================================
    # MODEL ERROR / HISTORICAL METRICS
    # ========================================================

    st.subheader(
        "📊 Historical Model Statistics"
    )

    historical_metrics = (
        calculate_historical_metrics(
            all_predictions
        )
    )

    if historical_metrics.empty:

        st.info(
            "Historical metrics will appear after "
            "predictions are evaluated."
        )

    else:

        hist_display = historical_metrics.copy()

        hist_display["Model"] = (
            hist_display[
                "model_name"
            ].map(
                lambda x:
                    DISPLAY_NAMES.get(
                        x,
                        x
                    )
            )
        )

        hist_display["Accuracy"] = (
            hist_display[
                "accuracy"
            ].map(
                lambda x:
                    f"{x:.2f}%"
            )
        )

        hist_display["MAE"] = (
            hist_display[
                "mae"
            ].map(
                lambda x:
                    f"{x:.5f}"
            )
        )

        hist_display["RMSE"] = (
            hist_display[
                "rmse"
            ].map(
                lambda x:
                    f"{x:.5f}"
            )
        )

        hist_display["Strategy Return"] = (
            hist_display[
                "strategy_return"
            ].map(
                lambda x:
                    f"{x:+.2f}%"
            )
        )

        hist_display["Compounded Return"] = (
            hist_display[
                "compounded_return"
            ].map(
                lambda x:
                    f"{x:+.2f}%"
            )
        )

        hist_display = hist_display[
            [
                "Model",
                "predictions",
                "Accuracy",
                "MAE",
                "RMSE",
                "Strategy Return",
                "Compounded Return"
            ]
        ]

        hist_display.columns = [
            "Model",
            "Predictions",
            "Accuracy",
            "MAE",
            "RMSE",
            "Strategy Return",
            "Compounded Return"
        ]

        st.dataframe(
            hist_display,
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # OPTIONAL FEATURE IMPORTANCE
    # ========================================================

    st.subheader(
        "🧠 Model Feature Importance"
    )

    st.caption(
        "Feature importance is loaded from available "
        "classical ML model files when possible."
    )

    models_dir = os.path.join(
        os.path.dirname(
            os.path.abspath(__file__)
        ),
        "models"
    )

    importance_records = []

    for model_name in [
        "random_forest",
        "xgboost",
        "lightgbm"
    ]:

        model_path = os.path.join(
            models_dir,
            f"{model_name}.pkl"
        )

        if not os.path.exists(
            model_path
        ):
            continue

        try:

            with open(
                model_path,
                "rb"
            ) as f:

                bundle = pickle.load(f)

            model = bundle

            features = None

            if isinstance(
                bundle,
                dict
            ):

                features = (
                    bundle.get(
                        "features"
                    )
                    or
                    bundle.get(
                        "feature_names"
                    )
                )

                model = (
                    bundle.get(
                        "model",
                        bundle.get(
                            "estimator",
                            bundle
                        )
                    )
                )

            if hasattr(
                model,
                "feature_importances_"
            ):

                importances = np.asarray(
                    model.feature_importances_
                )

                if features is None:

                    features = [
                        f"Feature_{i+1}"
                        for i in range(
                            len(importances)
                        )
                    ]

                for feature, importance in zip(
                    features,
                    importances
                ):

                    importance_records.append(
                        {
                            "Model":
                                DISPLAY_NAMES.get(
                                    model_name,
                                    model_name
                                ),

                            "Feature":
                                feature,

                            "Importance":
                                float(
                                    importance
                                )
                        }
                    )

        except Exception:
            continue

    if importance_records:

        importance_df = pd.DataFrame(
            importance_records
        )

        top_features = (
            importance_df
            .sort_values(
                "Importance",
                ascending=False
            )
            .groupby(
                "Model"
            )
            .head(10)
            .sort_values(
                "Importance"
            )
        )

        selected_importance_model = st.selectbox(
            "Select model for feature importance",
            sorted(
                top_features[
                    "Model"
                ].unique()
            ),
            key="importance_model"
        )

        selected_features = (
            top_features[
                top_features[
                    "Model"
                ]
                ==
                selected_importance_model
            ]
        )

        fig_importance = go.Figure()

        fig_importance.add_trace(
            go.Bar(
                x=selected_features[
                    "Importance"
                ],
                y=selected_features[
                    "Feature"
                ],
                orientation="h"
            )
        )

        fig_importance.update_layout(
            height=500,
            title=(
                f"Top Features — "
                f"{selected_importance_model}"
            ),
            xaxis_title="Importance",
            yaxis_title="Feature"
        )

        st.plotly_chart(
            fig_importance,
            use_container_width=True
        )

    else:

        st.info(
            "Feature importance could not be loaded. "
            "Make sure the classical model .pkl files "
            "contain trained estimators with "
            "feature_importances_."
        )

    # ========================================================
    # DETAILED MODEL STATISTICS
    # ========================================================

    if not performance.empty:

        with st.expander(
            "📊 Detailed Model Statistics"
        ):

            for _, row in (
                performance.iterrows()
            ):

                model_name = (
                    DISPLAY_NAMES.get(
                        row["model_name"],
                        row["model_name"]
                    )
                )

                st.markdown(
                    f"### {model_name}"
                )

                c1, c2, c3, c4, c5 = (
                    st.columns(5)
                )

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

                    compounded = row.get(
                        "compounded_strategy_return",
                        row.get(
                            "total_strategy_return",
                            0
                        )
                    )

                    st.metric(
                        "Return",
                        f"{float(compounded):+.2f}%"
                    )

                st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Bitcoin.svg/800px-Bitcoin.svg.png",
        width=100
    )

    st.markdown(
        "## 📊 Dashboard Controls"
    )

    # ========================================================
    # REFRESH
    # ========================================================

    if st.button(
        "🔄 Refresh Data",
        use_container_width=True
    ):

        st.session_state.loading = True

        st.rerun()

    # ========================================================
    # AUTO REFRESH
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 🔄 Auto Refresh"
    )

    auto_refresh = st.checkbox(
        "Enable auto refresh",
        value=True
    )

    refresh_seconds = st.selectbox(
        "Refresh interval",
        [30, 60, 120, 300, 600],
        index=1,
        format_func=lambda x:
            (
                f"{x} seconds"
                if x < 60
                else
                f"{x // 60} minute(s)"
            )
    )

    if auto_refresh:

        if AUTO_REFRESH_AVAILABLE:

            st_autorefresh(
                interval=(
                    refresh_seconds * 1000
                ),
                key=(
                    "btc_dashboard_autorefresh"
                )
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

    # ========================================================
    # EMAIL
    # ========================================================

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

    # ========================================================
    # EXPORT
    # ========================================================

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

    # ========================================================
    # INFO
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 📈 Dashboard Info"
    )

    if st.session_state.last_update:

        st.write(
            f"🕐 Last Update: "
            f"{st.session_state.last_update}"
        )

    # ========================================================
    # ML MODELS
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 🤖 ML Models"
    )

    for model in MODEL_ORDER:

        st.write(
            f"• {DISPLAY_NAMES[model]}"
        )

    # ========================================================
    # TECHNICAL INDICATORS
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 📊 Technical Indicators"
    )

    indicators = [
        "Support & Resistance",
        "Market Structure",
        "BOS / CHOCH",
        "Moving Averages",
        "RSI",
        "MACD",
        "Bollinger Bands",
        "Fibonacci",
        "Pivot Points",
        "Volume Liquidity",
        "ATR"
    ]

    for item in indicators:

        st.write(
            f"• {item}"
        )

    # ========================================================
    # NEW FEATURES
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 🚀 AI Features"
    )

    st.write("• AI Consensus")
    st.write("• Confidence Score")
    st.write("• Signal Strength")
    st.write("• Market Risk Score")
    st.write("• Model Leaderboard")
    st.write("• Prediction Error")
    st.write("• Accuracy Over Time")
    st.write("• Historical Backtest")
    st.write("• Equity Curve")
    st.write("• Max Drawdown")
    st.write("• Feature Importance")


# ============================================================
# MAIN HEADER
# ============================================================

# ============================================================
# MAIN DASHBOARD HEADER
# ============================================================

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #ff9800, #ffad33);
    padding: 28px 30px;
    border-radius: 18px;
    margin-bottom: 25px;
    text-align: center;
}

.main-header-title {
    font-size: 32px;
    font-weight: 700;
    color: white;
    margin-bottom: 8px;
}

.main-header-subtitle {
    font-size: 16px;
    color: white;
    opacity: 0.95;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <div class="main-header-title">
        ₿ BTC AI Trading Dashboard
    </div>
    <div class="main-header-subtitle">
        Technical Analysis + Machine Learning<br>
        + Deep Learning + AI Consensus
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# LOAD TECHNICAL DATA
# ============================================================

if (
    st.session_state.loading
    or
    st.session_state.results is None
):

    load_indicators()


# ============================================================
# MAIN TECHNICAL DASHBOARD
# ============================================================

if st.session_state.results:

    results = (
        st.session_state.results
    )

    # ========================================================
    # TOP METRICS
    # ========================================================

    col1, col2, col3, col4 = st.columns(4)

    # Current Price
    with col1:

        current_price = results.get(
            "current_price",
            0
        )

        st.metric(
            "💰 Current Price",
            f"${current_price:,.2f}"
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

                st.success(
                    "🟢 BUY"
                )

            elif "SELL" in direction:

                st.error(
                    "🔴 SELL"
                )

            else:

                st.warning(
                    "🟡 NEUTRAL"
                )

            st.caption(
                f"Confidence: {confidence}"
            )

    # RSI
    with col3:

        if "rsi" in results:

            rsi = results[
                "rsi"
            ]

            st.metric(
                "📊 RSI",
                f"{rsi.get('value', 0):.1f}",
                rsi.get(
                    "status",
                    "Neutral"
                )
            )

    # ATR
    with col4:

        if "atr" in results:

            atr = results[
                "atr"
            ]

            st.metric(
                "📊 ATR",
                f"${atr.get('atr', 0):,.2f}",
                f"{atr.get('percentile', 0):.0f}th percentile"
            )

            if (
                "overall_signal" in results
                and
                "atr_info"
                in results[
                    "overall_signal"
                ]
            ):

                atr_info = results[
                    "overall_signal"
                ][
                    "atr_info"
                ]

                st.caption(
                    f"Stop Loss: "
                    f"${atr_info.get('suggested_stop_loss', 0):,.2f}"
                )

    # ========================================================
    # MARKET STRUCTURE / S&R
    # ========================================================

    col1, col2 = st.columns(2)

    with col1:

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
                        f"• {b.get('type', 'N/A')} "
                        f"at ${b.get('price', 0):,.2f}"
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
                        f"• {c.get('type', 'N/A')}"
                    )

            else:

                st.write(
                    "**CHOCH:** None"
                )

            hh_hl = structure.get(
                "hh_hl_lh_ll"
            )

            if hh_hl:

                st.write(
                    f"**HH:** {hh_hl.get('HH', 0)} | "
                    f"**HL:** {hh_hl.get('HL', 0)} | "
                    f"**LH:** {hh_hl.get('LH', 0)} | "
                    f"**LL:** {hh_hl.get('LL', 0)}"
                )

    with col2:

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
                        f"Strength: {support.get('strength', 0)}"
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
                        f"Strength: {resistance.get('strength', 0)}"
                    )

                else:

                    st.metric(
                        "Resistance",
                        "N/A"
                    )

            if sr.get(
                "support_levels"
            ):

                with st.expander(
                    "📊 All Support Levels"
                ):

                    supports = pd.DataFrame(
                        [
                            {
                                "Level":
                                    i + 1,

                                "Price":
                                    f"${s.get('price', 0):,.2f}",

                                "Strength":
                                    f"{s.get('strength', 0)} touches"
                            }

                            for i, s
                            in enumerate(
                                sr[
                                    "support_levels"
                                ][:5]
                            )
                        ]
                    )

                    st.dataframe(
                        supports,
                        use_container_width=True,
                        hide_index=True
                    )

            if sr.get(
                "resistance_levels"
            ):

                with st.expander(
                    "📊 All Resistance Levels"
                ):

                    resistances = pd.DataFrame(
                        [
                            {
                                "Level":
                                    i + 1,

                                "Price":
                                    f"${r.get('price', 0):,.2f}",

                                "Strength":
                                    f"{r.get('strength', 0)} touches"
                            }

                            for i, r
                            in enumerate(
                                sr[
                                    "resistance_levels"
                                ][:5]
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

        ma_data = []

        for period, data in results[
            "moving_averages"
        ].items():

            ma_data.append(
                {
                    "Period":
                        period,

                    "Value":
                        f"${data.get('value', 0):,.2f}",

                    "EMA":
                        f"${data.get('ema', data.get('value', 0)):,.2f}",

                    "Trend":
                        data.get(
                            "trend",
                            "Neutral"
                        ),

                    "Slope":
                        f"{data.get('slope', 0):.2f}%"
                }
            )

        st.dataframe(
            pd.DataFrame(
                ma_data
            ),
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # RSI / MACD
    # ========================================================

    col1, col2 = st.columns(2)

    with col1:

        st.subheader(
            "📊 RSI"
        )

        if "rsi" in results:

            rsi = results[
                "rsi"
            ]

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
                            "range": [
                                0,
                                100
                            ]
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
                        ]
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

        st.subheader(
            "📊 MACD"
        )

        if "macd" in results:

            macd = results[
                "macd"
            ]

            a, b, c = st.columns(3)

            with a:

                st.metric(
                    "MACD",
                    f"{macd.get('macd', 0):.2f}"
                )

            with b:

                st.metric(
                    "Signal",
                    f"{macd.get('signal', 0):.2f}"
                )

            with c:

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
    # BOLLINGER
    # ========================================================

    st.subheader(
        "📊 Bollinger Bands"
    )

    if "bollinger_bands" in results:

        bb = results[
            "bollinger_bands"
        ]

        c1, c2, c3, c4 = st.columns(4)

        with c1:

            st.metric(
                "Upper Band",
                f"${bb.get('upper_band', 0):,.2f}"
            )

        with c2:

            st.metric(
                "Middle Band",
                f"${bb.get('middle_band', 0):,.2f}"
            )

        with c3:

            st.metric(
                "Lower Band",
                f"${bb.get('lower_band', 0):,.2f}"
            )

        with c4:

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
    # FIBONACCI / PIVOTS
    # ========================================================

    col1, col2 = st.columns(2)

    with col1:

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
                    f"${fib.get('swing_high', 0):,.2f}"
                )

                st.write(
                    f"**Swing Low:** "
                    f"${fib.get('swing_low', 0):,.2f}"
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
                            "Level":
                                level,

                            "Price":
                                f"${price:,.2f}"
                        }
                    )

                st.dataframe(
                    pd.DataFrame(
                        fib_data
                    ),
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

    with col2:

        st.subheader(
            "📊 Pivot Points"
        )

        if "pivot_points" in results:

            pivot = results[
                "pivot_points"
            ]

            a, b = st.columns(2)

            with a:

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

            with b:

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

    # ========================================================
    # LIQUIDITY
    # ========================================================

    st.subheader(
        "💧 Liquidity Analysis"
    )

    if "liquidity" in results:

        liq = results[
            "liquidity"
        ]

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "30-Day Avg Volume",
                f"{liq.get('avg_volume_30d', 0):,.0f}"
            )

        with c2:

            st.metric(
                "Overall Avg Volume",
                f"{liq.get('avg_volume_overall', 0):,.0f}"
            )

        with c3:

            st.metric(
                "Volume Ratio",
                f"{liq.get('volume_ratio', 0):,.2f}x"
            )

        if liq.get(
            "volume_profile"
        ):

            vp = liq[
                "volume_profile"
            ]

            a, b, c = st.columns(3)

            with a:

                st.metric(
                    "POC",
                    f"${vp.get('poc', 0):,.2f}"
                )

            with b:

                st.metric(
                    "VAH",
                    f"${vp.get('vah', 0):,.2f}"
                )

            with c:

                st.metric(
                    "VAL",
                    f"${vp.get('val', 0):,.2f}"
                )

        if liq.get(
            "high_volume_nodes"
        ):

            with st.expander(
                "📊 High Volume Nodes"
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

        if liq.get(
            "low_volume_nodes"
        ):

            with st.expander(
                "📊 Low Volume Nodes"
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

            for factor in signal.get(
                "factors",
                []
            ):

                st.write(
                    f"• {factor}"
                )

        with col2:

            st.write(
                "**Weights:**"
            )

            for key, weight in signal.get(
                "weights",
                {}
            ).items():

                try:

                    st.write(
                        f"• {key}: {float(weight):.0%}"
                    )

                except Exception:

                    st.write(
                        f"• {key}: {weight}"
                    )

            if "normalized_score" in signal:

                st.metric(
                    "Normalized Score",
                    f"{signal['normalized_score']:.2f}"
                )

    # ========================================================
    # ML
    # ========================================================

    display_ml_dashboard()

else:

    st.info(
        "👈 Click 'Refresh Data' "
        "to load dashboard"
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "₿ BTC AI Trading Dashboard | "
    "Technical Analysis + ML + Deep Learning + AI Consensus"
)

st.caption(
    "Models: Linear Regression | "
    "Random Forest | XGBoost | LightGBM | LSTM | GRU"
)

st.caption(
    "© 2026 All Rights Reserved"
)
