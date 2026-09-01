from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    BACKTEST_END,
    BACKTEST_START,
    TICKERS,
    TRANSACTION_COST_BPS,
)


ADJ_OHLC_PATH = Path(
    "data/processed/adjusted_ohlc.parquet"
)

REBALANCE_WEIGHTS_PATH = Path(
    "data/processed/rebalance_weights.parquet"
)

BACKTEST_PATH = Path(
    "data/processed/backtest_daily.parquet"
)

REALIZED_WEIGHTS_PATH = Path(
    "data/processed/realized_weights.parquet"
)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    adjusted_ohlc = pd.read_parquet(
        ADJ_OHLC_PATH
    )

    rebalance_weights = pd.read_parquet(
        REBALANCE_WEIGHTS_PATH
    )

    return adjusted_ohlc, rebalance_weights


def run_backtest(
    adjusted_ohlc: pd.DataFrame,
    rebalance_weights: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Simulate Strategy 0.

    Timeline on each trading day:

    previous Close
        ->
    today's Open
        ->
    rebalance at Open, if scheduled
        ->
    transaction costs
        ->
    today's Close
    """

    cost_rate = TRANSACTION_COST_BPS / 10_000

    open_prices = (
        adjusted_ohlc["Open"][TICKERS]
        .loc[BACKTEST_START:BACKTEST_END]
    )

    close_prices = (
        adjusted_ohlc["Close"][TICKERS]
        .loc[BACKTEST_START:BACKTEST_END]
    )

    if not open_prices.index.equals(close_prices.index):
        raise ValueError(
            "Open and Close indices do not match."
        )

    trading_dates = open_prices.index

    # Start completely in cash.
    asset_values = pd.Series(
        0.0,
        index=TICKERS,
    )

    cash = 1.0

    previous_close_prices = None
    previous_portfolio_value = 1.0

    daily_rows = []
    realized_weight_rows = []

    execution_dates = set(
        rebalance_weights.index
    )

    for date in trading_dates:

        today_open = open_prices.loc[date]
        today_close = close_prices.loc[date]

        # -------------------------------------------------
        # 1. Previous Close -> today's Open
        # -------------------------------------------------

        if previous_close_prices is not None:

            overnight_growth = (
                today_open / previous_close_prices
            )

            asset_values = (
                asset_values * overnight_growth
            )

        portfolio_value_open = (
            asset_values.sum() + cash
        )

        if portfolio_value_open <= 0:
            raise RuntimeError(
                f"Non-positive portfolio value "
                f"on {date.date()}."
            )

        # Portfolio weights immediately BEFORE trading.
        pre_trade_weights = (
            asset_values / portfolio_value_open
        )

        turnover = 0.0
        transaction_cost = 0.0
        rebalanced = False

        # -------------------------------------------------
        # 2. Rebalance at today's Open
        # -------------------------------------------------

        if date in execution_dates:

            target = rebalance_weights.loc[date]

            target_asset_weights = target[TICKERS]
            target_cash_weight = target["CASH"]

            # Turnover is calculated against actual
            # pre-trade weights, which may have drifted
            # since the previous rebalance.
            turnover = (
                target_asset_weights
                - pre_trade_weights
            ).abs().sum()

            transaction_cost = (
                portfolio_value_open
                * cost_rate
                * turnover
            )

            portfolio_value_after_cost = (
                portfolio_value_open
                - transaction_cost
            )

            if portfolio_value_after_cost <= 0:
                raise RuntimeError(
                    f"Transaction costs exhausted "
                    f"portfolio on {date.date()}."
                )

            # Reset holdings to target weights AFTER costs.
            asset_values = (
                target_asset_weights
                * portfolio_value_after_cost
            )

            cash = (
                target_cash_weight
                * portfolio_value_after_cost
            )

            rebalanced = True

        # -------------------------------------------------
        # 3. Today's Open -> today's Close
        # -------------------------------------------------

        intraday_growth = (
            today_close / today_open
        )

        asset_values = (
            asset_values * intraday_growth
        )

        portfolio_value_close = (
            asset_values.sum() + cash
        )

        daily_return = (
            portfolio_value_close
            / previous_portfolio_value
            - 1
        )

        # Realized weights at the CLOSE.
        realized_asset_weights = (
            asset_values / portfolio_value_close
        )

        realized_cash_weight = (
            cash / portfolio_value_close
        )

        daily_rows.append(
            {
                "Date": date,
                "portfolio_value": portfolio_value_close,
                "daily_return": daily_return,
                "turnover": turnover,
                "transaction_cost": transaction_cost,
                "rebalanced": rebalanced,
            }
        )

        realized_row = {
            "Date": date,
            **realized_asset_weights.to_dict(),
            "CASH": realized_cash_weight,
        }

        realized_weight_rows.append(
            realized_row
        )

        previous_close_prices = today_close
        previous_portfolio_value = (
            portfolio_value_close
        )

    backtest = (
        pd.DataFrame(daily_rows)
        .set_index("Date")
    )

    realized_weights = (
        pd.DataFrame(realized_weight_rows)
        .set_index("Date")
    )

    return backtest, realized_weights


def validate_backtest(
    backtest: pd.DataFrame,
    realized_weights: pd.DataFrame,
) -> None:

    if backtest.empty:
        raise RuntimeError(
            "Backtest output is empty."
        )

    if backtest.index.has_duplicates:
        raise RuntimeError(
            "Duplicate backtest dates found."
        )

    if not (
        backtest["portfolio_value"] > 0
    ).all():
        raise RuntimeError(
            "Non-positive portfolio value found."
        )

    if not np.isfinite(
        backtest["daily_return"]
    ).all():
        raise RuntimeError(
            "Non-finite daily return found."
        )

    if (
        backtest["transaction_cost"] < 0
    ).any():
        raise RuntimeError(
            "Negative transaction cost found."
        )

    if (
        backtest["turnover"] < 0
    ).any():
        raise RuntimeError(
            "Negative turnover found."
        )

    weight_totals = (
        realized_weights.sum(axis=1)
    )

    if not np.allclose(
        weight_totals.to_numpy(),
        1.0,
        atol=1e-10,
    ):
        raise RuntimeError(
            "Realized portfolio weights "
            "do not sum to 1."
        )


def print_summary(
    backtest: pd.DataFrame,
    realized_weights: pd.DataFrame,
) -> None:

    print("\n=== BACKTEST ===")
    print(backtest.head(10))

    print("\nDate range:")
    print(
        backtest.index.min(),
        "->",
        backtest.index.max(),
    )

    print("\nInitial portfolio value:")
    print(
        f"{backtest['portfolio_value'].iloc[0]:.6f}"
    )

    print("\nFinal portfolio value:")
    print(
        f"{backtest['portfolio_value'].iloc[-1]:.6f}"
    )

    print("\nNumber of executed rebalances:")
    print(
        int(backtest["rebalanced"].sum())
    )

    print("\nTotal turnover:")
    print(
        f"{backtest['turnover'].sum():.4f}"
    )

    print("\nTotal transaction costs:")
    print(
        f"{backtest['transaction_cost'].sum():.6f}"
    )

    print("\nFirst rebalance day:")

    first_rebalance = (
        backtest[backtest["rebalanced"]]
        .iloc[0]
    )

    first_rebalance_date = (
        backtest[backtest["rebalanced"]]
        .index[0]
    )

    print(first_rebalance_date)
    print(first_rebalance)

    print("\nRealized weights after first rebalance day:")
    print(
        realized_weights.loc[first_rebalance_date]
    )


def main() -> None:
    adjusted_ohlc, rebalance_weights = (
        load_inputs()
    )

    backtest, realized_weights = run_backtest(
        adjusted_ohlc=adjusted_ohlc,
        rebalance_weights=rebalance_weights,
    )

    validate_backtest(
        backtest=backtest,
        realized_weights=realized_weights,
    )

    backtest.to_parquet(
        BACKTEST_PATH
    )

    realized_weights.to_parquet(
        REALIZED_WEIGHTS_PATH
    )

    print_summary(
        backtest=backtest,
        realized_weights=realized_weights,
    )

    print("\nBacktest validation passed.")

    print("\nSaved:")
    print(BACKTEST_PATH)
    print(REALIZED_WEIGHTS_PATH)


if __name__ == "__main__":
    main()