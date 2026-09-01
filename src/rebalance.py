from pathlib import Path

import numpy as np
import pandas as pd

from src.config import BACKTEST_END, BACKTEST_START, TICKERS


TARGET_WEIGHTS_PATH = Path(
    "data/processed/target_weights.parquet"
)

ADJ_OHLC_PATH = Path(
    "data/processed/adjusted_ohlc.parquet"
)

REBALANCE_WEIGHTS_PATH = Path(
    "data/processed/rebalance_weights.parquet"
)

REBALANCE_SCHEDULE_PATH = Path(
    "data/processed/rebalance_schedule.parquet"
)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    target_weights = pd.read_parquet(
        TARGET_WEIGHTS_PATH
    )

    adjusted_ohlc = pd.read_parquet(
        ADJ_OHLC_PATH
    )

    return target_weights, adjusted_ohlc


def get_weekly_decision_dates(
    trading_index: pd.DatetimeIndex,
) -> pd.DatetimeIndex:
    """
    Return the last actual trading day of each
    Monday-Friday trading week.

    If Friday is a holiday, Thursday (or the
    preceding actual trading day) is selected.
    """

    mask = (
        (trading_index >= pd.Timestamp(BACKTEST_START))
        & (trading_index <= pd.Timestamp(BACKTEST_END))
    )

    dates = trading_index[mask]

    date_series = pd.Series(
        dates,
        index=dates,
    )

    decision_dates = (
        date_series
        .groupby(dates.to_period("W-FRI"))
        .max()
    )

    return pd.DatetimeIndex(decision_dates)


def get_next_trading_day(
    date: pd.Timestamp,
    trading_index: pd.DatetimeIndex,
) -> pd.Timestamp | None:
    """
    Find the first trading day strictly after date.
    """

    position = trading_index.searchsorted(
        date,
        side="right",
    )

    if position >= len(trading_index):
        return None

    next_date = trading_index[position]

    if next_date > pd.Timestamp(BACKTEST_END):
        return None

    return next_date


def build_rebalance_schedule(
    target_weights: pd.DataFrame,
    trading_index: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build weekly decision/execution schedule.

    Weights observed after Close on decision_date
    become executable at Open on execution_date.
    """

    decision_dates = get_weekly_decision_dates(
        trading_index
    )

    schedule_rows = []
    execution_rows = []

    for decision_date in decision_dates:

        execution_date = get_next_trading_day(
            decision_date,
            trading_index,
        )

        # Example: the final week may have no
        # executable trading day inside the backtest.
        if execution_date is None:
            continue

        weights = target_weights.loc[
            decision_date
        ].copy()

        schedule_rows.append(
            {
                "decision_date": decision_date,
                "execution_date": execution_date,
            }
        )

        weights.name = execution_date
        execution_rows.append(weights)

    schedule = pd.DataFrame(schedule_rows)

    execution_weights = pd.DataFrame(
        execution_rows
    )

    execution_weights.index.name = "execution_date"

    return schedule, execution_weights


def validate_schedule(
    schedule: pd.DataFrame,
    execution_weights: pd.DataFrame,
    trading_index: pd.DatetimeIndex,
) -> None:

    if schedule.empty:
        raise RuntimeError(
            "Rebalance schedule is empty."
        )

    if not (
        schedule["decision_date"]
        < schedule["execution_date"]
    ).all():
        raise RuntimeError(
            "Execution must occur after decision."
        )

    # Verify that execution really is the
    # immediately following trading day.
    for row in schedule.itertuples():
        expected = get_next_trading_day(
            row.decision_date,
            trading_index,
        )

        if row.execution_date != expected:
            raise RuntimeError(
                f"Incorrect execution date after "
                f"{row.decision_date.date()}."
            )

    if execution_weights.index.has_duplicates:
        raise RuntimeError(
            "Duplicate execution dates found."
        )

    totals = execution_weights.sum(axis=1)

    if not np.allclose(
        totals.to_numpy(),
        1.0,
        atol=1e-10,
    ):
        raise RuntimeError(
            "Rebalance weights do not sum to 1."
        )

    if (
        execution_weights[TICKERS] < -1e-10
    ).any().any():
        raise RuntimeError(
            "Negative asset weights found."
        )


def print_summary(
    schedule: pd.DataFrame,
    execution_weights: pd.DataFrame,
) -> None:

    print("\n=== REBALANCE SCHEDULE ===")
    print(schedule.head(10))

    print("\nNumber of rebalances:")
    print(len(schedule))

    print("\nFirst decision:")
    print(schedule.iloc[0])

    print("\nLast decision:")
    print(schedule.iloc[-1])

    print("\n=== EXECUTION WEIGHTS ===")
    print(execution_weights.head())

    print("\nFirst execution portfolio:")
    print(execution_weights.iloc[0])


def main() -> None:
    target_weights, adjusted_ohlc = load_inputs()

    trading_index = adjusted_ohlc.index

    schedule, execution_weights = (
        build_rebalance_schedule(
            target_weights=target_weights,
            trading_index=trading_index,
        )
    )

    validate_schedule(
        schedule=schedule,
        execution_weights=execution_weights,
        trading_index=trading_index,
    )

    schedule.to_parquet(
        REBALANCE_SCHEDULE_PATH,
        index=False,
    )

    execution_weights.to_parquet(
        REBALANCE_WEIGHTS_PATH
    )

    print_summary(
        schedule=schedule,
        execution_weights=execution_weights,
    )

    print("\nRebalance validation passed.")

    print("\nSaved:")
    print(REBALANCE_SCHEDULE_PATH)
    print(REBALANCE_WEIGHTS_PATH)


if __name__ == "__main__":
    main()