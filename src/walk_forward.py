from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    BACKTEST_END,
    BACKTEST_START,
)
from src.metrics import (
    calculate_drawdown,
    calculate_period_metrics,
)


# =========================================================
# PATHS
# =========================================================

BACKTEST_PATH = Path(
    "data/processed/backtest_daily.parquet"
)

REALIZED_WEIGHTS_PATH = Path(
    "data/processed/realized_weights.parquet"
)

OUTPUT_DIR = Path(
    "data/processed/walk_forward"
)

BLOCK_RESULTS_CSV = (
    OUTPUT_DIR
    / "walk_forward_blocks.csv"
)

BLOCK_RESULTS_PARQUET = (
    OUTPUT_DIR
    / "walk_forward_blocks.parquet"
)

OOS_DAILY_CSV = (
    OUTPUT_DIR
    / "walk_forward_oos_daily.csv"
)

OOS_DAILY_PARQUET = (
    OUTPUT_DIR
    / "walk_forward_oos_daily.parquet"
)


# =========================================================
# WALK-FORWARD SPECIFICATION
# =========================================================

# Strategy 0 has no fitted model parameters.
# Therefore this is a fixed-parameter walk-forward
# evaluation, not walk-forward optimization.
#
# We require five complete calendar years of historical
# observations before the first OOS block.
INITIAL_HISTORY_YEARS = 5

# Each OOS block is one complete calendar year.
OOS_BLOCK_YEARS = 1


# =========================================================
# LOAD
# =========================================================

def load_inputs() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    required = [
        BACKTEST_PATH,
        REALIZED_WEIGHTS_PATH,
    ]

    for path in required:
        if not path.exists():
            raise FileNotFoundError(
                f"Required file not found: {path}"
            )

    backtest = pd.read_parquet(
        BACKTEST_PATH
    )

    realized_weights = pd.read_parquet(
        REALIZED_WEIGHTS_PATH
    )

    if not backtest.index.equals(
        realized_weights.index
    ):
        raise RuntimeError(
            "Backtest and realized weights "
            "indices do not match."
        )

    if backtest.index.has_duplicates:
        raise RuntimeError(
            "Duplicate dates found in backtest."
        )

    if not backtest.index.is_monotonic_increasing:
        raise RuntimeError(
            "Backtest dates are not sorted."
        )

    return (
        backtest,
        realized_weights,
    )


# =========================================================
# WALK-FORWARD BLOCKS
# =========================================================

def build_walk_forward_blocks(
    backtest: pd.DataFrame,
) -> list[dict]:
    """
    Build expanding-history, one-year OOS blocks.

    Example with five initial history years:

        history: 2007-2011 -> OOS: 2012
        history: 2007-2012 -> OOS: 2013
        ...
        history: 2007-2024 -> OOS: 2025

    No parameter is chosen or changed at any step.
    """

    first_year = int(
        backtest.index.min().year
    )

    last_year = int(
        backtest.index.max().year
    )

    first_oos_year = (
        first_year
        + INITIAL_HISTORY_YEARS
    )

    if first_oos_year > last_year:
        raise RuntimeError(
            "Not enough data for walk-forward "
            "evaluation."
        )

    blocks = []

    for oos_year in range(
        first_oos_year,
        last_year + 1,
        OOS_BLOCK_YEARS,
    ):
        history_start = pd.Timestamp(
            year=first_year,
            month=1,
            day=1,
        )

        history_end = pd.Timestamp(
            year=oos_year - 1,
            month=12,
            day=31,
        )

        oos_start = pd.Timestamp(
            year=oos_year,
            month=1,
            day=1,
        )

        oos_end = pd.Timestamp(
            year=min(
                oos_year
                + OOS_BLOCK_YEARS
                - 1,
                last_year,
            ),
            month=12,
            day=31,
        )

        blocks.append(
            {
                "history_start":
                    history_start,
                "history_end":
                    history_end,
                "oos_start":
                    oos_start,
                "oos_end":
                    oos_end,
            }
        )

    return blocks


# =========================================================
# METRICS
# =========================================================

def metrics_to_prefixed_row(
    metrics: dict,
    prefix: str,
) -> dict:
    return {
        f"{prefix}_total_return":
            metrics["Total Return"],
        f"{prefix}_cagr":
            metrics["CAGR"],
        f"{prefix}_volatility":
            metrics["Annual Volatility"],
        f"{prefix}_sharpe":
            metrics["Sharpe"],
        f"{prefix}_sortino":
            metrics["Sortino"],
        f"{prefix}_max_drawdown":
            metrics["Max Drawdown"],
        f"{prefix}_calmar":
            metrics["Calmar"],
        f"{prefix}_annual_turnover":
            metrics["Annual Turnover"],
        f"{prefix}_average_cash":
            metrics["Average Cash"],
        f"{prefix}_transaction_costs":
            metrics["Transaction Costs"],
        f"{prefix}_rebalances":
            metrics["Rebalances"],
    }


def calculate_block_results(
    backtest: pd.DataFrame,
    realized_weights: pd.DataFrame,
    blocks: list[dict],
) -> pd.DataFrame:
    rows = []

    for block_id, block in enumerate(
        blocks,
        start=1,
    ):
        history_start = block[
            "history_start"
        ]

        history_end = block[
            "history_end"
        ]

        oos_start = block[
            "oos_start"
        ]

        oos_end = block[
            "oos_end"
        ]

        history_metrics = (
            calculate_period_metrics(
                backtest=backtest,
                realized_weights=
                    realized_weights,
                start=str(
                    history_start.date()
                ),
                end=str(
                    history_end.date()
                ),
            )
        )

        oos_metrics = (
            calculate_period_metrics(
                backtest=backtest,
                realized_weights=
                    realized_weights,
                start=str(
                    oos_start.date()
                ),
                end=str(
                    oos_end.date()
                ),
            )
        )

        row = {
            "block_id":
                block_id,
            "history_start":
                history_start,
            "history_end":
                history_end,
            "oos_start":
                oos_start,
            "oos_end":
                oos_end,
            "oos_year":
                int(oos_start.year),
        }

        row.update(
            metrics_to_prefixed_row(
                history_metrics,
                "history",
            )
        )

        row.update(
            metrics_to_prefixed_row(
                oos_metrics,
                "oos",
            )
        )

        rows.append(row)

    return pd.DataFrame(rows)


# =========================================================
# STITCHED OOS SERIES
# =========================================================

def build_stitched_oos_series(
    backtest: pd.DataFrame,
    blocks: list[dict],
) -> pd.DataFrame:
    """
    Concatenate the non-overlapping OOS blocks into one
    continuous out-of-sample return series.
    """

    pieces = []

    for block in blocks:
        piece = backtest.loc[
            block["oos_start"]:
            block["oos_end"],
            [
                "daily_return",
                "turnover",
                "transaction_cost",
                "rebalanced",
            ],
        ].copy()

        pieces.append(piece)

    oos = pd.concat(
        pieces,
        axis=0,
    )

    if oos.index.has_duplicates:
        raise RuntimeError(
            "Overlapping OOS blocks detected."
        )

    oos = oos.sort_index()

    oos["oos_portfolio_value"] = (
        1.0
        + oos["daily_return"]
    ).cumprod()

    oos["oos_drawdown"] = (
        calculate_drawdown(
            oos[
                "oos_portfolio_value"
            ]
        )
    )

    return oos


# =========================================================
# VALIDATION
# =========================================================

def validate_walk_forward(
    backtest: pd.DataFrame,
    blocks: list[dict],
    oos_daily: pd.DataFrame,
) -> None:
    if not blocks:
        raise RuntimeError(
            "No walk-forward blocks created."
        )

    first_oos_date = (
        oos_daily.index.min()
    )

    last_oos_date = (
        oos_daily.index.max()
    )

    baseline_oos = backtest.loc[
        first_oos_date:
        last_oos_date
    ]

    if not oos_daily.index.equals(
        baseline_oos.index
    ):
        raise RuntimeError(
            "Stitched OOS dates do not reproduce "
            "the corresponding baseline period."
        )

    if not np.allclose(
        oos_daily[
            "daily_return"
        ].to_numpy(),
        baseline_oos[
            "daily_return"
        ].to_numpy(),
        rtol=0.0,
        atol=1e-12,
    ):
        raise RuntimeError(
            "Stitched OOS returns differ from "
            "the frozen Strategy 0 backtest."
        )

    for i in range(
        1,
        len(blocks),
    ):
        previous = blocks[
            i - 1
        ]

        current = blocks[i]

        if (
            current[
                "oos_start"
            ]
            <= previous[
                "oos_end"
            ]
        ):
            raise RuntimeError(
                "OOS blocks overlap."
            )

        if (
            current[
                "history_end"
            ]
            >= current[
                "oos_start"
            ]
        ):
            raise RuntimeError(
                "History overlaps future OOS data."
            )

    print(
        "\nWalk-forward validation passed."
    )

    print(
        "Stitched OOS returns exactly reproduce "
        "the corresponding frozen Strategy 0 "
        "daily returns."
    )


# =========================================================
# AGGREGATE OOS METRICS
# =========================================================

def calculate_aggregate_oos_metrics(
    backtest: pd.DataFrame,
    realized_weights: pd.DataFrame,
    blocks: list[dict],
) -> dict:
    start = blocks[0][
        "oos_start"
    ]

    end = blocks[-1][
        "oos_end"
    ]

    return calculate_period_metrics(
        backtest=backtest,
        realized_weights=realized_weights,
        start=str(start.date()),
        end=str(end.date()),
    )


# =========================================================
# PRINT
# =========================================================

def print_block_results(
    results: pd.DataFrame,
) -> None:
    table = pd.DataFrame(
        {
            "OOS":
                results[
                    "oos_year"
                ].astype(int),
            "History Sharpe":
                results[
                    "history_sharpe"
                ].map(
                    lambda x:
                    f"{x:.3f}"
                ),
            "OOS Return":
                results[
                    "oos_total_return"
                ].map(
                    lambda x:
                    f"{x:.2%}"
                ),
            "OOS Vol":
                results[
                    "oos_volatility"
                ].map(
                    lambda x:
                    f"{x:.2%}"
                ),
            "OOS Sharpe":
                results[
                    "oos_sharpe"
                ].map(
                    lambda x:
                    f"{x:.3f}"
                ),
            "OOS MaxDD":
                results[
                    "oos_max_drawdown"
                ].map(
                    lambda x:
                    f"{x:.2%}"
                ),
            "OOS Cash":
                results[
                    "oos_average_cash"
                ].map(
                    lambda x:
                    f"{x:.2%}"
                ),
            "Turnover":
                results[
                    "oos_annual_turnover"
                ].map(
                    lambda x:
                    f"{x:.3f}"
                ),
        }
    )

    print(
        "\n=== WALK-FORWARD OOS BLOCKS ===\n"
    )

    print(
        table.to_string(
            index=False
        )
    )


def print_aggregate_metrics(
    metrics: dict,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> None:
    print(
        "\n=== STITCHED OOS PERFORMANCE ==="
    )

    print(
        f"\nPeriod: "
        f"{start.date()} -> "
        f"{end.date()}"
    )

    print(
        f"CAGR       "
        f"{metrics['CAGR']:.2%}"
    )

    print(
        f"Volatility "
        f"{metrics['Annual Volatility']:.2%}"
    )

    print(
        f"Sharpe     "
        f"{metrics['Sharpe']:.3f}"
    )

    print(
        f"MaxDD      "
        f"{metrics['Max Drawdown']:.2%}"
    )

    print(
        f"Calmar     "
        f"{metrics['Calmar']:.3f}"
    )

    print(
        f"Cash       "
        f"{metrics['Average Cash']:.2%}"
    )

    print(
        f"Turnover   "
        f"{metrics['Annual Turnover']:.3f}"
    )


# =========================================================
# SAVE
# =========================================================

def save_results(
    block_results: pd.DataFrame,
    oos_daily: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    block_results.to_csv(
        BLOCK_RESULTS_CSV,
        index=False,
    )

    block_results.to_parquet(
        BLOCK_RESULTS_PARQUET,
        index=False,
    )

    oos_daily.to_csv(
        OOS_DAILY_CSV,
        index=True,
    )

    oos_daily.to_parquet(
        OOS_DAILY_PARQUET,
        index=True,
    )

    print(
        "\nSaved:"
    )

    print(
        BLOCK_RESULTS_CSV
    )

    print(
        BLOCK_RESULTS_PARQUET
    )

    print(
        OOS_DAILY_CSV
    )

    print(
        OOS_DAILY_PARQUET
    )


# =========================================================
# MAIN
# =========================================================

def main() -> None:
    (
        backtest,
        realized_weights,
    ) = load_inputs()

    print(
        "\n=== STRATEGY 0 WALK-FORWARD ==="
    )

    print(
        "\nMode: fixed-parameter, expanding history"
    )

    print(
        f"Initial history: "
        f"{INITIAL_HISTORY_YEARS} calendar years"
    )

    print(
        f"OOS block: "
        f"{OOS_BLOCK_YEARS} calendar year"
    )

    print(
        "\nNo parameter optimization is performed."
    )

    blocks = build_walk_forward_blocks(
        backtest=backtest
    )

    block_results = (
        calculate_block_results(
            backtest=backtest,
            realized_weights=
                realized_weights,
            blocks=blocks,
        )
    )

    oos_daily = (
        build_stitched_oos_series(
            backtest=backtest,
            blocks=blocks,
        )
    )

    validate_walk_forward(
        backtest=backtest,
        blocks=blocks,
        oos_daily=oos_daily,
    )

    aggregate_metrics = (
        calculate_aggregate_oos_metrics(
            backtest=backtest,
            realized_weights=
                realized_weights,
            blocks=blocks,
        )
    )

    print_block_results(
        results=block_results
    )

    print_aggregate_metrics(
        metrics=aggregate_metrics,
        start=blocks[0][
            "oos_start"
        ],
        end=blocks[-1][
            "oos_end"
        ],
    )

    save_results(
        block_results=
            block_results,
        oos_daily=oos_daily,
    )

    print(
        "\nWalk-forward analysis completed."
    )


if __name__ == "__main__":
    main()
