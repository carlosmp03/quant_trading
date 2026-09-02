from pathlib import Path

import numpy as np
import pandas as pd

from src.backtest import run_backtest, validate_backtest
from src.config import (
    MOMENTUM_WINDOW,
    TEST_END,
    TEST_START,
    TRAIN_END,
    TRAIN_START,
    VALIDATION_END,
    VALIDATION_START,
)
from src.metrics import calculate_period_metrics
from src.portfolio import (
    add_cash_weight,
    calculate_target_weights,
    validate_weights,
)
from src.rebalance import (
    build_rebalance_schedule,
    validate_schedule,
)
from src.signals import (
    calculate_signals,
    validate_signals,
)


ADJ_CLOSE_PATH = Path("data/processed/adj_close.parquet")
VOLATILITY_PATH = Path("data/processed/volatility.parquet")
ADJ_OHLC_PATH = Path("data/processed/adjusted_ohlc.parquet")
BASELINE_BACKTEST_PATH = Path("data/processed/backtest_daily.parquet")

ROBUSTNESS_DIR = Path("data/processed/robustness")
RESULTS_CSV_PATH = ROBUSTNESS_DIR / "momentum_lookback_results.csv"
RESULTS_PARQUET_PATH = ROBUSTNESS_DIR / "momentum_lookback_results.parquet"


# Strategy 0 remains frozen at 252 days.
# These are robustness variants, not candidates for re-optimization.
MOMENTUM_LOOKBACKS = [
    126,
    189,
    252,
    378,
]

PERIODS = {
    "TRAIN": (TRAIN_START, TRAIN_END),
    "VALIDATION": (VALIDATION_START, VALIDATION_END),
    "TEST": (TEST_START, TEST_END),
}


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load prepared data without overwriting any Strategy 0 artifacts.

    volatility.parquet is the frozen 60-day volatility estimate
    used by Strategy 0.
    """
    required_paths = [
        ADJ_CLOSE_PATH,
        VOLATILITY_PATH,
        ADJ_OHLC_PATH,
    ]

    for path in required_paths:
        if not path.exists():
            raise FileNotFoundError(
                f"Required file not found: {path}"
            )

    adj_close = pd.read_parquet(ADJ_CLOSE_PATH)
    volatility = pd.read_parquet(VOLATILITY_PATH)
    adjusted_ohlc = pd.read_parquet(ADJ_OHLC_PATH)

    return adj_close, volatility, adjusted_ohlc


def calculate_momentum_for_window(
    adj_close: pd.DataFrame,
    lookback: int,
) -> pd.DataFrame:
    """
    Momentum robustness variant:

        M_t = P_t / P_{t-lookback} - 1
    """
    if lookback <= 0:
        raise ValueError(
            "Momentum lookback must be positive."
        )

    return (
        adj_close
        / adj_close.shift(lookback)
        - 1.0
    )


def run_momentum_variant(
    lookback: int,
    adj_close: pd.DataFrame,
    volatility: pd.DataFrame,
    adjusted_ohlc: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run Strategy 0 with only the momentum lookback changed.

    Frozen:
    - volatility window = 60 trading days;
    - inverse-volatility sizing;
    - gross exposure = N_t / 8;
    - max ETF weight = 25%;
    - weekly rebalancing;
    - execution at next trading-day Open;
    - transaction costs = 5 bps;
    - no shorting or leverage.
    """
    momentum = calculate_momentum_for_window(
        adj_close=adj_close,
        lookback=lookback,
    )

    signals = calculate_signals(momentum)

    validate_signals(
        momentum=momentum,
        signals=signals,
    )

    asset_weights = calculate_target_weights(
        signals=signals,
        volatility=volatility,
    )

    target_weights = add_cash_weight(
        weights=asset_weights
    )

    validate_weights(target_weights)

    trading_index = adjusted_ohlc.index

    schedule, rebalance_weights = build_rebalance_schedule(
        target_weights=target_weights,
        trading_index=trading_index,
    )

    validate_schedule(
        schedule=schedule,
        execution_weights=rebalance_weights,
        trading_index=trading_index,
    )

    backtest, realized_weights = run_backtest(
        adjusted_ohlc=adjusted_ohlc,
        rebalance_weights=rebalance_weights,
    )

    validate_backtest(
        backtest=backtest,
        realized_weights=realized_weights,
    )

    return backtest, realized_weights


def validate_baseline_reproduction(
    robustness_backtest: pd.DataFrame,
) -> None:
    """
    The 252-day robustness run must reproduce the frozen
    Strategy 0 backtest. Otherwise the robustness pipeline
    is not comparable with the baseline.
    """
    if not BASELINE_BACKTEST_PATH.exists():
        raise FileNotFoundError(
            "Baseline backtest file not found: "
            f"{BASELINE_BACKTEST_PATH}"
        )

    baseline = pd.read_parquet(
        BASELINE_BACKTEST_PATH
    )

    if not robustness_backtest.index.equals(
        baseline.index
    ):
        raise RuntimeError(
            "Baseline sanity check failed: "
            "date indices differ."
        )

    numeric_columns = [
        "portfolio_value",
        "daily_return",
        "turnover",
        "transaction_cost",
    ]

    for column in numeric_columns:
        candidate = robustness_backtest[
            column
        ].to_numpy()

        reference = baseline[
            column
        ].to_numpy()

        if not np.allclose(
            candidate,
            reference,
            rtol=0.0,
            atol=1e-12,
        ):
            max_difference = np.max(
                np.abs(
                    candidate - reference
                )
            )

            raise RuntimeError(
                "Baseline sanity check failed for "
                f"'{column}'. Maximum difference: "
                f"{max_difference:.3e}"
            )

    if not np.array_equal(
        robustness_backtest[
            "rebalanced"
        ].to_numpy(),
        baseline[
            "rebalanced"
        ].to_numpy(),
    ):
        raise RuntimeError(
            "Baseline sanity check failed: "
            "rebalance flags differ."
        )

    print(
        "\nBaseline sanity check passed: "
        f"{MOMENTUM_WINDOW}-day run reproduces Strategy 0."
    )


def collect_period_results(
    lookback: int,
    backtest: pd.DataFrame,
    realized_weights: pd.DataFrame,
) -> list[dict]:
    rows = []

    for period, (start, end) in PERIODS.items():
        metrics = calculate_period_metrics(
            backtest=backtest,
            realized_weights=realized_weights,
            start=start,
            end=end,
        )

        rows.append(
            {
                "period": period,
                "momentum_lookback": lookback,
                "total_return": metrics["Total Return"],
                "cagr": metrics["CAGR"],
                "annual_volatility": metrics["Annual Volatility"],
                "sharpe": metrics["Sharpe"],
                "sortino": metrics["Sortino"],
                "max_drawdown": metrics["Max Drawdown"],
                "calmar": metrics["Calmar"],
                "annual_turnover": metrics["Annual Turnover"],
                "average_cash": metrics["Average Cash"],
                "transaction_costs": metrics["Transaction Costs"],
                "rebalances": metrics["Rebalances"],
            }
        )

    return rows


def print_results(
    results: pd.DataFrame,
) -> None:
    print(
        "\n=== MOMENTUM LOOKBACK ROBUSTNESS ==="
    )
    print(
        "\nOnly the momentum lookback changes. "
        "All other Strategy 0 parameters remain frozen."
    )
    print(
        f"Baseline = {MOMENTUM_WINDOW} trading days."
    )

    for period in PERIODS:
        subset = (
            results[
                results["period"] == period
            ]
            .copy()
            .sort_values("momentum_lookback")
        )

        table = pd.DataFrame(
            {
                "Lookback": subset[
                    "momentum_lookback"
                ].astype(int),
                "CAGR": subset["cagr"].map(
                    lambda x: f"{x:.2%}"
                ),
                "Vol": subset[
                    "annual_volatility"
                ].map(
                    lambda x: f"{x:.2%}"
                ),
                "Sharpe": subset["sharpe"].map(
                    lambda x: f"{x:.3f}"
                ),
                "MaxDD": subset[
                    "max_drawdown"
                ].map(
                    lambda x: f"{x:.2%}"
                ),
                "Calmar": subset["calmar"].map(
                    lambda x: f"{x:.3f}"
                ),
                "Cash": subset[
                    "average_cash"
                ].map(
                    lambda x: f"{x:.2%}"
                ),
                "Turnover": subset[
                    "annual_turnover"
                ].map(
                    lambda x: f"{x:.3f}"
                ),
            }
        )

        print(f"\n--- {period} ---\n")
        print(
            table.to_string(
                index=False
            )
        )


def save_results(
    results: pd.DataFrame,
) -> None:
    ROBUSTNESS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results.to_csv(
        RESULTS_CSV_PATH,
        index=False,
    )

    results.to_parquet(
        RESULTS_PARQUET_PATH,
        index=False,
    )

    print("\nSaved:")
    print(RESULTS_CSV_PATH)
    print(RESULTS_PARQUET_PATH)


def main() -> None:
    (
        adj_close,
        volatility,
        adjusted_ohlc,
    ) = load_inputs()

    rows = []

    print("\n=== ROBUSTNESS TESTS ===")

    for lookback in MOMENTUM_LOOKBACKS:
        baseline_label = (
            " [BASELINE]"
            if lookback == MOMENTUM_WINDOW
            else ""
        )

        print(
            f"\nRunning momentum lookback "
            f"{lookback}{baseline_label}..."
        )

        backtest, realized_weights = run_momentum_variant(
            lookback=lookback,
            adj_close=adj_close,
            volatility=volatility,
            adjusted_ohlc=adjusted_ohlc,
        )

        if lookback == MOMENTUM_WINDOW:
            validate_baseline_reproduction(
                robustness_backtest=backtest
            )

        rows.extend(
            collect_period_results(
                lookback=lookback,
                backtest=backtest,
                realized_weights=realized_weights,
            )
        )

        print(
            f"Completed {lookback}: "
            f"final value = "
            f"{backtest['portfolio_value'].iloc[-1]:.4f}"
        )

    results = pd.DataFrame(rows)

    print_results(results)
    save_results(results)

    print(
        "\nMomentum lookback robustness "
        "tests completed."
    )


if __name__ == "__main__":
    main()
