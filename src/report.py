from pathlib import Path

import pandas as pd

from src.config import (
    TRAIN_START,
    TRAIN_END,
    VALIDATION_START,
    VALIDATION_END,
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

    "Exposure Matched InvVol": (
        Path(
            "data/processed/benchmarks/"
            "exposure_matched_inverse_vol_daily.parquet"
        ),
        Path(
            "data/processed/benchmarks/"
            "exposure_matched_inverse_vol_weights.parquet"
        ),
    ), 

    "Constant Exposure InvVol": (
        Path(
            "data/processed/benchmarks/"
            "constant_exposure_inverse_vol_daily.parquet"
        ),
        Path(
            "data/processed/benchmarks/"
            "constant_exposure_inverse_vol_weights.parquet"
        ),
    ),

}


PERIODS = {
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


def load_strategy(
    backtest_path: Path,
    weights_path: Path,
):
    backtest = pd.read_parquet(
        backtest_path
    )

    weights = pd.read_parquet(
        weights_path
    )

    return backtest, weights


def build_period_table() -> pd.DataFrame:
    rows = []

    for strategy_name, paths in STRATEGIES.items():

        backtest, weights = load_strategy(
            *paths
        )

        for period_name, (
            start,
            end,
        ) in PERIODS.items():

            metrics = calculate_period_metrics(
                backtest=backtest,
                realized_weights=weights,
                start=start,
                end=end,
            )

            rows.append(
                {
                    "Strategy": strategy_name,
                    "Period": period_name,
                    "CAGR": metrics["CAGR"],
                    "Volatility": metrics[
                        "Annual Volatility"
                    ],
                    "Sharpe": metrics["Sharpe"],
                    "MaxDD": metrics[
                        "Max Drawdown"
                    ],
                    "Calmar": metrics["Calmar"],
                    "Average Cash": metrics[
                        "Average Cash"
                    ],
                }
            )

    return pd.DataFrame(rows)


def build_yearly_returns() -> pd.DataFrame:
    yearly = {}

    for strategy_name, (
        backtest_path,
        _,
    ) in STRATEGIES.items():

        backtest = pd.read_parquet(
            backtest_path
        )

        returns = backtest[
            "daily_return"
        ]

        yearly_returns = (
            (1.0 + returns)
            .groupby(
                returns.index.year
            )
            .prod()
            - 1.0
        )

        yearly[strategy_name] = (
            yearly_returns
        )

    return pd.DataFrame(yearly)


def print_period_table(
    table: pd.DataFrame,
) -> None:

    print(
        "\n=== TRAIN / VALIDATION / TEST ===\n"
    )

    for period in PERIODS:

        print(
            f"\n--- {period.upper()} ---"
        )

        subset = (
            table[
                table["Period"] == period
            ]
            .set_index("Strategy")
        )

        for strategy, row in subset.iterrows():

            print(
                f"\n{strategy}"
            )

            print(
                f"  CAGR       "
                f"{row['CAGR']:.2%}"
            )

            print(
                f"  Volatility "
                f"{row['Volatility']:.2%}"
            )

            print(
                f"  Sharpe     "
                f"{row['Sharpe']:.3f}"
            )

            print(
                f"  MaxDD      "
                f"{row['MaxDD']:.2%}"
            )

            print(
                f"  Calmar     "
                f"{row['Calmar']:.3f}"
            )

            print(
                f"  Cash       "
                f"{row['Average Cash']:.2%}"
            )


def print_yearly_returns(
    yearly: pd.DataFrame,
) -> None:

    print(
        "\n=== CALENDAR YEAR RETURNS ===\n"
    )

    formatted = yearly.map(
        lambda x: f"{x:.2%}"
    )

    print(formatted)


def main() -> None:

    period_table = build_period_table()

    yearly_returns = build_yearly_returns()

    print_period_table(
        period_table
    )

    print_yearly_returns(
        yearly_returns
    )


if __name__ == "__main__":
    main()