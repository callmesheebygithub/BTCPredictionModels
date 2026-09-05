"""
Professional historical backtesting for BTC model predictions.

Each model gets its own virtual account and takes one daily long/short
trade from evaluated rows in btc_predictions.
"""

import os
from datetime import date

import mysql.connector
import numpy as np
import pandas as pd
from dotenv import load_dotenv


load_dotenv()

DB_CONFIG = {
    "host": os.getenv("db_host"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password"),
    "database": os.getenv("db_name")
}

MODEL_ORDER = [
    "linear_regression",
    "random_forest",
    "xgboost",
    "lightgbm",
    "lstm",
    "gru"
]

DEFAULT_INITIAL_CAPITAL = 10000.0
DEFAULT_RISK_PER_TRADE = 0.02
DEFAULT_FEE_BPS = 10.0
DEFAULT_SLIPPAGE_BPS = 5.0


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def create_backtest_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS btc_backtest_summary (
            run_date DATE NOT NULL,
            model_name VARCHAR(50) NOT NULL,
            initial_capital DOUBLE NOT NULL,
            final_capital DOUBLE NOT NULL,
            roi_pct DOUBLE NOT NULL,
            win_rate_pct DOUBLE NOT NULL,
            max_drawdown_pct DOUBLE NOT NULL,
            sharpe_ratio DOUBLE NOT NULL,
            total_trades INT NOT NULL,
            winning_trades INT NOT NULL,
            losing_trades INT NOT NULL,
            gross_pnl DOUBLE NOT NULL,
            net_pnl DOUBLE NOT NULL,
            total_fees DOUBLE NOT NULL,
            total_slippage DOUBLE NOT NULL,
            risk_per_trade_pct DOUBLE NOT NULL,
            fee_bps DOUBLE NOT NULL,
            slippage_bps DOUBLE NOT NULL,
            best_trade_pct DOUBLE,
            worst_trade_pct DOUBLE,
            avg_trade_return_pct DOUBLE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (run_date, model_name)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS btc_backtest_trades (
            run_date DATE NOT NULL,
            trade_date DATE NOT NULL,
            model_name VARCHAR(50) NOT NULL,
            side VARCHAR(5) NOT NULL,
            entry_price DOUBLE NOT NULL,
            exit_price DOUBLE NOT NULL,
            actual_return DOUBLE NOT NULL,
            strategy_return DOUBLE NOT NULL,
            capital_before DOUBLE NOT NULL,
            position_notional DOUBLE NOT NULL,
            gross_pnl DOUBLE NOT NULL,
            fee_amount DOUBLE NOT NULL,
            slippage_amount DOUBLE NOT NULL,
            net_pnl DOUBLE NOT NULL,
            capital_after DOUBLE NOT NULL,
            drawdown_pct DOUBLE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (run_date, trade_date, model_name)
        )
        """
    )

    conn.commit()
    cursor.close()
    conn.close()


def load_evaluated_predictions():
    conn = get_connection()

    query = """
        SELECT
            prediction_date,
            model_name,
            current_close,
            predicted_direction,
            actual_return,
            actual_price,
            evaluated
        FROM btc_predictions
        WHERE evaluated = 1
          AND actual_return IS NOT NULL
          AND actual_price IS NOT NULL
          AND current_close IS NOT NULL
          AND predicted_direction IS NOT NULL
        ORDER BY prediction_date ASC, model_name ASC
    """

    df = pd.read_sql(query, conn)
    conn.close()

    if not df.empty:
        df["prediction_date"] = pd.to_datetime(df["prediction_date"])

    return df


def calculate_model_backtest(
    predictions,
    model_name,
    initial_capital=DEFAULT_INITIAL_CAPITAL,
    risk_per_trade=DEFAULT_RISK_PER_TRADE,
    fee_bps=DEFAULT_FEE_BPS,
    slippage_bps=DEFAULT_SLIPPAGE_BPS
):
    model_df = predictions[
        predictions["model_name"] == model_name
    ].copy()

    if model_df.empty:
        return None, pd.DataFrame()

    model_df = model_df.sort_values("prediction_date")

    capital = float(initial_capital)
    peak_capital = capital
    trade_records = []
    return_series = []

    fee_rate = float(fee_bps) / 10000.0
    slippage_rate = float(slippage_bps) / 10000.0

    for _, row in model_df.iterrows():
        try:
            capital_before = capital
            actual_return = float(row["actual_return"])
            direction = int(row["predicted_direction"])
            side = "LONG" if direction == 1 else "SHORT"
            strategy_return = (
                actual_return
                if direction == 1
                else -actual_return
            )

            position_notional = capital_before * float(risk_per_trade)
            gross_pnl = position_notional * strategy_return
            fee_amount = position_notional * fee_rate * 2
            slippage_amount = position_notional * slippage_rate * 2
            net_pnl = gross_pnl - fee_amount - slippage_amount

            capital = capital_before + net_pnl
            capital = max(capital, 0.0)

            peak_capital = max(peak_capital, capital)
            drawdown_pct = (
                (capital / peak_capital - 1) * 100
                if peak_capital > 0
                else 0.0
            )

            trade_return = (
                net_pnl / capital_before
                if capital_before > 0
                else 0.0
            )
            return_series.append(trade_return)

            trade_records.append(
                {
                    "trade_date": row["prediction_date"].date(),
                    "model_name": model_name,
                    "side": side,
                    "entry_price": float(row["current_close"]),
                    "exit_price": float(row["actual_price"]),
                    "actual_return": actual_return,
                    "strategy_return": strategy_return,
                    "capital_before": capital_before,
                    "position_notional": position_notional,
                    "gross_pnl": gross_pnl,
                    "fee_amount": fee_amount,
                    "slippage_amount": slippage_amount,
                    "net_pnl": net_pnl,
                    "capital_after": capital,
                    "drawdown_pct": drawdown_pct
                }
            )
        except Exception:
            continue

    trades = pd.DataFrame(trade_records)

    if trades.empty:
        return None, trades

    total_trades = len(trades)
    winning_trades = int((trades["net_pnl"] > 0).sum())
    losing_trades = int((trades["net_pnl"] <= 0).sum())
    return_array = np.array(return_series, dtype=float)

    sharpe_ratio = 0.0
    if len(return_array) > 1 and np.std(return_array, ddof=1) > 0:
        sharpe_ratio = (
            np.mean(return_array)
            / np.std(return_array, ddof=1)
            * np.sqrt(365)
        )

    summary = {
        "model_name": model_name,
        "initial_capital": float(initial_capital),
        "final_capital": float(trades["capital_after"].iloc[-1]),
        "roi_pct": (
            trades["capital_after"].iloc[-1]
            / float(initial_capital)
            - 1
        ) * 100,
        "win_rate_pct": winning_trades / total_trades * 100,
        "max_drawdown_pct": float(trades["drawdown_pct"].min()),
        "sharpe_ratio": float(sharpe_ratio),
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "gross_pnl": float(trades["gross_pnl"].sum()),
        "net_pnl": float(trades["net_pnl"].sum()),
        "total_fees": float(trades["fee_amount"].sum()),
        "total_slippage": float(trades["slippage_amount"].sum()),
        "risk_per_trade_pct": float(risk_per_trade) * 100,
        "fee_bps": float(fee_bps),
        "slippage_bps": float(slippage_bps),
        "best_trade_pct": float(trades["strategy_return"].max() * 100),
        "worst_trade_pct": float(trades["strategy_return"].min() * 100),
        "avg_trade_return_pct": float(np.mean(return_array) * 100)
    }

    return summary, trades


def save_backtest_results(summary_rows, trade_frames, run_date=None):
    run_date = run_date or date.today()

    conn = get_connection()
    cursor = conn.cursor()

    summary_sql = """
        INSERT INTO btc_backtest_summary (
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
            avg_trade_return_pct
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            initial_capital = VALUES(initial_capital),
            final_capital = VALUES(final_capital),
            roi_pct = VALUES(roi_pct),
            win_rate_pct = VALUES(win_rate_pct),
            max_drawdown_pct = VALUES(max_drawdown_pct),
            sharpe_ratio = VALUES(sharpe_ratio),
            total_trades = VALUES(total_trades),
            winning_trades = VALUES(winning_trades),
            losing_trades = VALUES(losing_trades),
            gross_pnl = VALUES(gross_pnl),
            net_pnl = VALUES(net_pnl),
            total_fees = VALUES(total_fees),
            total_slippage = VALUES(total_slippage),
            risk_per_trade_pct = VALUES(risk_per_trade_pct),
            fee_bps = VALUES(fee_bps),
            slippage_bps = VALUES(slippage_bps),
            best_trade_pct = VALUES(best_trade_pct),
            worst_trade_pct = VALUES(worst_trade_pct),
            avg_trade_return_pct = VALUES(avg_trade_return_pct)
    """

    trade_sql = """
        INSERT INTO btc_backtest_trades (
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
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            side = VALUES(side),
            entry_price = VALUES(entry_price),
            exit_price = VALUES(exit_price),
            actual_return = VALUES(actual_return),
            strategy_return = VALUES(strategy_return),
            capital_before = VALUES(capital_before),
            position_notional = VALUES(position_notional),
            gross_pnl = VALUES(gross_pnl),
            fee_amount = VALUES(fee_amount),
            slippage_amount = VALUES(slippage_amount),
            net_pnl = VALUES(net_pnl),
            capital_after = VALUES(capital_after),
            drawdown_pct = VALUES(drawdown_pct)
    """

    try:
        for row in summary_rows:
            cursor.execute(
                summary_sql,
                (
                    run_date,
                    row["model_name"],
                    row["initial_capital"],
                    row["final_capital"],
                    row["roi_pct"],
                    row["win_rate_pct"],
                    row["max_drawdown_pct"],
                    row["sharpe_ratio"],
                    row["total_trades"],
                    row["winning_trades"],
                    row["losing_trades"],
                    row["gross_pnl"],
                    row["net_pnl"],
                    row["total_fees"],
                    row["total_slippage"],
                    row["risk_per_trade_pct"],
                    row["fee_bps"],
                    row["slippage_bps"],
                    row["best_trade_pct"],
                    row["worst_trade_pct"],
                    row["avg_trade_return_pct"]
                )
            )

        for trades in trade_frames:
            for _, trade in trades.iterrows():
                cursor.execute(
                    trade_sql,
                    (
                        run_date,
                        trade["trade_date"],
                        trade["model_name"],
                        trade["side"],
                        trade["entry_price"],
                        trade["exit_price"],
                        trade["actual_return"],
                        trade["strategy_return"],
                        trade["capital_before"],
                        trade["position_notional"],
                        trade["gross_pnl"],
                        trade["fee_amount"],
                        trade["slippage_amount"],
                        trade["net_pnl"],
                        trade["capital_after"],
                        trade["drawdown_pct"]
                    )
                )

        conn.commit()
    finally:
        cursor.close()
        conn.close()


def run_backtests(
    initial_capital=DEFAULT_INITIAL_CAPITAL,
    risk_per_trade=DEFAULT_RISK_PER_TRADE,
    fee_bps=DEFAULT_FEE_BPS,
    slippage_bps=DEFAULT_SLIPPAGE_BPS,
    run_date=None
):
    create_backtest_tables()

    predictions = load_evaluated_predictions()

    if predictions.empty:
        return pd.DataFrame(), pd.DataFrame()

    summaries = []
    trade_frames = []

    for model_name in MODEL_ORDER:
        summary, trades = calculate_model_backtest(
            predictions,
            model_name,
            initial_capital=initial_capital,
            risk_per_trade=risk_per_trade,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps
        )

        if summary is not None and not trades.empty:
            summaries.append(summary)
            trade_frames.append(trades)

    if summaries:
        save_backtest_results(summaries, trade_frames, run_date=run_date)

    trades_df = (
        pd.concat(trade_frames, ignore_index=True)
        if trade_frames
        else pd.DataFrame()
    )

    return pd.DataFrame(summaries), trades_df


def main():
    summary, trades = run_backtests()

    if summary.empty:
        print("No evaluated predictions available for backtesting.")
        return

    print("Backtest summary saved to database.")
    print(summary.sort_values("roi_pct", ascending=False).to_string(index=False))
    print(f"Saved {len(trades):,} trade rows.")


if __name__ == "__main__":
    main()
