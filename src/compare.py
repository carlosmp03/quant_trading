from pathlib import Path

import pandas as pd

from src.config import (
    TEST_START,
    TEST_END,
)
from src.metrics import calculate_period_metrics


STRATEGIES = {
    "Strategy": (
        Path("data/processed/backtest_daily.parquet"),
        Path("data/processed/realized_weights.parquet"),
    ),
    "Inverse Vol": (
        Path("data/processed/benchmarks/inverse_vol_daily.parquet"),
        Path("data/processed/benchmarks/inverse_vol_weights.parquet"),
    ),
    "Equal Weight": (
        Path("data/processed/benchmarks/equal_weight_daily.parquet"),
        Path("data/processed/benchmarks/equal_weight_weights.parquet"),
    ),
    "SPY": (
        Path("data/processed/benchmarks/spy_buy_hold_daily.parquet"),
        Path("data/processed/benchmarks/spy_buy_hold_weights.parquet"),
    ),
}


METRICS_TO_SHOW = [
    "Total Return",
    "CAGR",
    "Annual Volatility",
    "Sharpe",
    "Sortino",
    "Max Drawdown",
    "Calmar",
    "Annual Turnover",
    "Average Cash",
]


def load_metrics(
    backtest_path: Path,
    weights_path: Path,
) -> dict:

    backtest = pd.read_parquet(
        backtest_path
    )

    weights = pd.read_parquet(
        weights_path
    )

    return calculate_period_metrics(
        backtest=backtest,
        realized_weights=weights,
        start=TEST_START,
        end=TEST_END,
    )


def main() -> None:

    results = {}

    for name, (
        backtest_path,
        weights_path,
    ) in STRATEGIES.items():

        metrics = load_metrics(
            backtest_path=backtest_path,
            weights_path=weights_path,
        )

        results[name] = {
            metric: metrics[metric]
            for metric in METRICS_TO_SHOW
        }

    table = pd.DataFrame(results)

    percentage_rows = [
        "Total Return",
        "CAGR",
        "Annual Volatility",
        "Max Drawdown",
        "Average Cash",
    ]

    print(
        "\n=== TEST PERIOD COMPARISON ==="
    )

    print(
        f"{TEST_START} -> {TEST_END}\n"
    )

    for metric in table.index:

        print(f"\n{metric}")

        for strategy in table.columns:

            value = table.loc[
                metric,
                strategy,
            ]

            if metric in percentage_rows:
                formatted = f"{value:.2%}"
            else:
                formatted = f"{value:.3f}"

            print(
                f"  {strategy:14} "
                f"{formatted}"
            )


if __name__ == "__main__":
    main()