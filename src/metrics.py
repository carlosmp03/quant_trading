from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    TRAIN_START,
    TRAIN_END,
    VALIDATION_START,
    VALIDATION_END,
    TEST_START,
    TEST_END,
)


BACKTEST_PATH = Path(
    "data/processed/backtest_daily.parquet"
)

REALIZED_WEIGHTS_PATH = Path(
    "data/processed/realized_weights.parquet"
)


def calculate_drawdown(
    portfolio_value: pd.Series,
) -> pd.Series:
    running_max = portfolio_value.cummax()

    drawdown = (
        portfolio_value / running_max - 1.0
    )

    return drawdown


def calculate_metrics(
    backtest: pd.DataFrame,
    realized_weights: pd.DataFrame,
) -> dict:
    if backtest.empty:
        raise ValueError("Backtest slice is empty.")

    returns = backtest["daily_return"]
    normalized_value = (
    1.0 + returns
    ).cumprod()

    # ------------------------------------------
    # Length of sample
    # ------------------------------------------

    days = (
        backtest.index[-1]
        - backtest.index[0]
    ).days

    years = days / 365.25

    if years <= 0:
        raise ValueError(
            "Sample period must be positive."
        )

    # ------------------------------------------
    # Return
    # ------------------------------------------

    total_return = (
        normalized_value.iloc[-1] - 1.0
    )

    cagr = (
        normalized_value.iloc[-1]
    ) ** (1.0 / years) - 1.0

    # ------------------------------------------
    # Volatility
    # ------------------------------------------

    daily_std = returns.std()

    annual_volatility = (
        daily_std * np.sqrt(252)
    )

    # ------------------------------------------
    # Sharpe ratio
    # rf = 0 in Strategy 0
    # ------------------------------------------

    if daily_std > 0:
        sharpe = (
            returns.mean()
            / daily_std
            * np.sqrt(252)
        )
    else:
        sharpe = np.nan

    # ------------------------------------------
    # Sortino ratio
    # ------------------------------------------

    downside_returns = np.minimum(
        returns.to_numpy(),
        0.0,
    )

    daily_downside_deviation = np.sqrt(
        np.mean(
            downside_returns ** 2
        )
    )

    if daily_downside_deviation > 0:
        sortino = (
            returns.mean()
            / daily_downside_deviation
            * np.sqrt(252)
        )
    else:
        sortino = np.nan

    # ------------------------------------------
    # Drawdown
    # ------------------------------------------

    drawdown = calculate_drawdown(
        normalized_value
    )

    max_drawdown = drawdown.min()

    if max_drawdown < 0:
        calmar = (
            cagr / abs(max_drawdown)
        )
    else:
        calmar = np.nan

    # ------------------------------------------
    # Turnover
    # ------------------------------------------

    total_turnover = (
        backtest["turnover"].sum()
    )

    annual_turnover = (
        total_turnover / years
    )

    # ------------------------------------------
    # Cash
    # ------------------------------------------

    average_cash_weight = (
        realized_weights["CASH"].mean()
    )

    # ------------------------------------------
    # Positive periods
    # ------------------------------------------

    positive_day_fraction = (
        returns > 0
    ).mean()

    monthly_returns = (
        (1.0 + returns)
        .groupby(
            returns.index.to_period("M")
        )
        .prod()
        - 1.0
    )

    yearly_returns = (
        (1.0 + returns)
        .groupby(
            returns.index.to_period("Y")
        )
        .prod()
        - 1.0
    )

    positive_month_fraction = (
        monthly_returns > 0
    ).mean()

    positive_year_fraction = (
        yearly_returns > 0
    ).mean()

    # ------------------------------------------
    # Trading costs
    # ------------------------------------------

    total_transaction_cost = (
        backtest["transaction_cost"].sum()
    )

    number_of_rebalances = int(
        backtest["rebalanced"].sum()
    )

    return {
        "Total Return": total_return,
        "CAGR": cagr,
        "Annual Volatility": annual_volatility,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Max Drawdown": max_drawdown,
        "Calmar": calmar,
        "Annual Turnover": annual_turnover,
        "Average Cash": average_cash_weight,
        "Positive Days": positive_day_fraction,
        "Positive Months": positive_month_fraction,
        "Positive Years": positive_year_fraction,
        "Transaction Costs": total_transaction_cost,
        "Rebalances": number_of_rebalances,
    }


def calculate_period_metrics(
    backtest: pd.DataFrame,
    realized_weights: pd.DataFrame,
    start: str,
    end: str,
) -> dict:
    backtest_slice = backtest.loc[
        start:end
    ]

    weights_slice = realized_weights.loc[
        start:end
    ]

    return calculate_metrics(
        backtest=backtest_slice,
        realized_weights=weights_slice,
    )


def format_metrics_table(
    metrics: dict,
) -> pd.Series:
    percentages = {
        "Total Return",
        "CAGR",
        "Annual Volatility",
        "Max Drawdown",
        "Average Cash",
        "Positive Days",
        "Positive Months",
        "Positive Years",
    }

    formatted = {}

    for key, value in metrics.items():

        if key in percentages:
            formatted[key] = (
                f"{value:.2%}"
            )

        elif key == "Rebalances":
            formatted[key] = str(
                int(value)
            )

        else:
            formatted[key] = (
                f"{value:.3f}"
            )

    return pd.Series(formatted)


def main() -> None:
    backtest = pd.read_parquet(
        BACKTEST_PATH
    )

    realized_weights = pd.read_parquet(
        REALIZED_WEIGHTS_PATH
    )

    periods = {
        "Full": (
            backtest.index.min(),
            backtest.index.max(),
        ),
        "Train": (
            TRAIN_START,
            TRAIN_END,
        ),
        "Validation": (
            VALIDATION_START,
            VALIDATION_END,
        ),
        "Test": (
            TEST_START,
            TEST_END,
        ),
    }

    results = {}

    for name, (start, end) in periods.items():

        metrics = calculate_period_metrics(
            backtest=backtest,
            realized_weights=realized_weights,
            start=start,
            end=end,
        )

        results[name] = (
            format_metrics_table(metrics)
        )

    table = pd.DataFrame(results)

    print("\n=== STRATEGY METRICS ===")
    print(table)


if __name__ == "__main__":
    main()