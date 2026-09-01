from pathlib import Path

import pandas as pd

from src.backtest import run_backtest, validate_backtest
from src.config import (
    BACKTEST_END,
    BACKTEST_START,
    MAX_ASSET_WEIGHT,
    TICKERS,
)


VOLATILITY_PATH = Path(
    "data/processed/volatility.parquet"
)

ADJ_OHLC_PATH = Path(
    "data/processed/adjusted_ohlc.parquet"
)

SCHEDULE_PATH = Path(
    "data/processed/rebalance_schedule.parquet"
)

OUTPUT_DIR = Path(
    "data/processed/benchmarks"
)


def load_inputs():
    volatility = pd.read_parquet(
        VOLATILITY_PATH
    )

    adjusted_ohlc = pd.read_parquet(
        ADJ_OHLC_PATH
    )

    schedule = pd.read_parquet(
        SCHEDULE_PATH
    )

    schedule["decision_date"] = pd.to_datetime(
        schedule["decision_date"]
    )

    schedule["execution_date"] = pd.to_datetime(
        schedule["execution_date"]
    )

    return volatility, adjusted_ohlc, schedule


def build_inverse_vol_weights(
    volatility: pd.DataFrame,
    schedule: pd.DataFrame,
) -> pd.DataFrame:
    """
    Benchmark 1:
    all eight ETFs are always active.

    Relative asset weights are inverse-volatility.
    25% asset cap is retained.

    Any capital left because of the cap remains in cash.
    """

    rows = []

    for row in schedule.itertuples():

        vol = volatility.loc[
            row.decision_date,
            TICKERS,
        ]

        if vol.isna().any():
            raise ValueError(
                f"Missing volatility on "
                f"{row.decision_date.date()}."
            )

        inverse_vol = 1.0 / vol

        weights = (
            inverse_vol / inverse_vol.sum()
        )

        weights = weights.clip(
            upper=MAX_ASSET_WEIGHT
        )

        result = weights.to_dict()

        result["CASH"] = (
            1.0 - weights.sum()
        )

        result["execution_date"] = (
            row.execution_date
        )

        rows.append(result)

    benchmark = (
        pd.DataFrame(rows)
        .set_index("execution_date")
    )

    return benchmark


def build_equal_weight_weights(
    schedule: pd.DataFrame,
) -> pd.DataFrame:
    """
    Benchmark 2:
    continuously invested 1/8 in each ETF,
    rebalanced weekly.
    """

    rows = []

    asset_weight = 1.0 / len(TICKERS)

    for row in schedule.itertuples():

        result = {
            ticker: asset_weight
            for ticker in TICKERS
        }

        result["CASH"] = 0.0

        result["execution_date"] = (
            row.execution_date
        )

        rows.append(result)

    benchmark = (
        pd.DataFrame(rows)
        .set_index("execution_date")
    )

    return benchmark


def build_spy_buy_hold_weights(
    adjusted_ohlc: pd.DataFrame,
) -> pd.DataFrame:
    """
    Benchmark 3:
    buy SPY once at the first Open of the
    backtest and hold it until the end.
    """

    trading_dates = (
        adjusted_ohlc
        .loc[BACKTEST_START:BACKTEST_END]
        .index
    )

    first_date = trading_dates[0]

    row = {
        ticker: 0.0
        for ticker in TICKERS
    }

    row["SPY"] = 1.0
    row["CASH"] = 0.0

    benchmark = pd.DataFrame(
        [row],
        index=[first_date],
    )

    benchmark.index.name = "execution_date"

    return benchmark


def run_and_save(
    name: str,
    weights: pd.DataFrame,
    adjusted_ohlc: pd.DataFrame,
) -> None:

    backtest, realized_weights = run_backtest(
        adjusted_ohlc=adjusted_ohlc,
        rebalance_weights=weights,
    )

    validate_backtest(
        backtest=backtest,
        realized_weights=realized_weights,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    backtest.to_parquet(
        OUTPUT_DIR / f"{name}_daily.parquet"
    )

    realized_weights.to_parquet(
        OUTPUT_DIR / f"{name}_weights.parquet"
    )

    print(
        f"{name:20} | "
        f"final value = "
        f"{backtest['portfolio_value'].iloc[-1]:.4f}"
    )


def main() -> None:
    volatility, adjusted_ohlc, schedule = (
        load_inputs()
    )

    inverse_vol = build_inverse_vol_weights(
        volatility=volatility,
        schedule=schedule,
    )

    equal_weight = build_equal_weight_weights(
        schedule=schedule,
    )

    spy_buy_hold = build_spy_buy_hold_weights(
        adjusted_ohlc=adjusted_ohlc,
    )

    print("\n=== BENCHMARK BACKTESTS ===")

    run_and_save(
        name="inverse_vol",
        weights=inverse_vol,
        adjusted_ohlc=adjusted_ohlc,
    )

    run_and_save(
        name="equal_weight",
        weights=equal_weight,
        adjusted_ohlc=adjusted_ohlc,
    )

    run_and_save(
        name="spy_buy_hold",
        weights=spy_buy_hold,
        adjusted_ohlc=adjusted_ohlc,
    )

    print("\nBenchmark backtests completed.")


if __name__ == "__main__":
    main()