from pathlib import Path

import numpy as np
import pandas as pd

from src.backtest import run_backtest, validate_backtest
from src.config import (
    BACKTEST_END,
    BACKTEST_START,
    MAX_ASSET_WEIGHT,
    TICKERS,
)

TRAIN_AVERAGE_RISKY_EXPOSURE = 0.6699

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

STRATEGY_REBALANCE_WEIGHTS_PATH = Path(
    "data/processed/rebalance_weights.parquet"
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

def allocate_inverse_vol_with_cap(
    inverse_vol: pd.Series,
    target_exposure: float,
) -> pd.Series:
    """
    Allocate target_exposure proportionally to inverse volatility,
    subject to the per-asset weight cap.

    Any weight prevented by the cap is redistributed among
    the remaining uncapped assets.
    """

    TRAIN_AVERAGE_RISKY_EXPOSURE = 0.6699

    weights = pd.Series(
        0.0,
        index=inverse_vol.index,
    )

    remaining_assets = list(inverse_vol.index)
    remaining_exposure = target_exposure

    tolerance = 1e-12

    while (
        remaining_assets
        and remaining_exposure > tolerance
    ):
        scores = inverse_vol.loc[
            remaining_assets
        ]

        proposed = (
            remaining_exposure
            * scores
            / scores.sum()
        )

        capped = proposed > MAX_ASSET_WEIGHT

        if not capped.any():
            weights.loc[remaining_assets] = proposed
            remaining_exposure = 0.0
            break

        capped_assets = list(
            proposed.index[capped]
        )

        weights.loc[capped_assets] = (
            MAX_ASSET_WEIGHT
        )

        remaining_exposure -= (
            MAX_ASSET_WEIGHT
            * len(capped_assets)
        )

        remaining_assets = [
            ticker
            for ticker in remaining_assets
            if ticker not in capped_assets
        ]

    if remaining_exposure > 1e-10:
        raise RuntimeError(
            "Could not allocate target exposure "
            "under the asset weight cap."
        )

    return weights

def build_exposure_matched_inverse_vol_weights(
    volatility: pd.DataFrame,
    schedule: pd.DataFrame,
    strategy_weights: pd.DataFrame,
) -> pd.DataFrame:
    """
    Inverse-volatility benchmark with exactly the same
    target risky exposure as Strategy 0 at every rebalance.

    All eight ETFs remain eligible.
    """

    rows = []

    for row in schedule.itertuples():

        execution_date = row.execution_date

        strategy_target = strategy_weights.loc[
            execution_date
        ]

        target_exposure = (
            strategy_target[TICKERS].sum()
        )

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

        weights = allocate_inverse_vol_with_cap(
            inverse_vol=inverse_vol,
            target_exposure=target_exposure,
        )

        result = weights.to_dict()

        result["CASH"] = (
            1.0 - weights.sum()
        )

        result["execution_date"] = execution_date

        rows.append(result)

    benchmark = (
        pd.DataFrame(rows)
        .set_index("execution_date")
    )

    strategy_exposure = (
        strategy_weights
        .loc[benchmark.index, TICKERS]
        .sum(axis=1)
    )

    benchmark_exposure = (
        benchmark[TICKERS]
        .sum(axis=1)
    )

    if not np.allclose(
        benchmark_exposure.to_numpy(),
        strategy_exposure.to_numpy(),
        atol=1e-10,
    ):
        raise RuntimeError(
            "Exposure-matched benchmark does not "
            "match Strategy 0 risky exposure."
        )

    return benchmark

def build_constant_exposure_inverse_vol_weights(
    volatility: pd.DataFrame,
    schedule: pd.DataFrame,
    target_exposure: float,
) -> pd.DataFrame:
    """
    Inverse-volatility benchmark with constant risky exposure.

    All ETFs are always eligible.
    The risky exposure is fixed through time.
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

        weights = allocate_inverse_vol_with_cap(
            inverse_vol=inverse_vol,
            target_exposure=target_exposure,
        )

        result = weights.to_dict()

        result["CASH"] = 1.0 - weights.sum()
        result["execution_date"] = row.execution_date

        rows.append(result)

    benchmark = (
        pd.DataFrame(rows)
        .set_index("execution_date")
    )

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

    strategy_weights = pd.read_parquet(
    STRATEGY_REBALANCE_WEIGHTS_PATH
    )

    exposure_matched_inverse_vol = (
        build_exposure_matched_inverse_vol_weights(
            volatility=volatility,
            schedule=schedule,
            strategy_weights=strategy_weights,
        )
    )

    constant_exposure_inverse_vol = (
        build_constant_exposure_inverse_vol_weights(
            volatility=volatility,
            schedule=schedule,
            target_exposure=TRAIN_AVERAGE_RISKY_EXPOSURE,
        )
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

    run_and_save(
        name="exposure_matched_inverse_vol",
        weights=exposure_matched_inverse_vol,
        adjusted_ohlc=adjusted_ohlc,
    )

    run_and_save(
        name="constant_exposure_inverse_vol",
        weights=constant_exposure_inverse_vol,
        adjusted_ohlc=adjusted_ohlc,
    )

    print("\nBenchmark backtests completed.")


if __name__ == "__main__":
    main()