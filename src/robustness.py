from pathlib import Path

import numpy as np
import pandas as pd

import src.backtest as backtest_module
from src.backtest import validate_backtest
from src.config import (
    BACKTEST_END,
    BACKTEST_START,
    MAX_ASSET_WEIGHT,
    MOMENTUM_WINDOW,
    TEST_END,
    TEST_START,
    TICKERS,
    TRAIN_END,
    TRAIN_START,
    TRANSACTION_COST_BPS,
    VALIDATION_END,
    VALIDATION_START,
    VOLATILITY_WINDOW,
)
from src.metrics import calculate_period_metrics
from src.portfolio import add_cash_weight, calculate_target_weights, validate_weights
from src.rebalance import (
    build_rebalance_schedule,
    get_next_trading_day,
    get_weekly_decision_dates,
    validate_schedule,
)
from src.signals import calculate_signals, validate_signals


# =========================================================
# PATHS
# =========================================================

ADJ_CLOSE_PATH = Path("data/processed/adj_close.parquet")
RETURNS_PATH = Path("data/processed/returns.parquet")
ADJ_OHLC_PATH = Path("data/processed/adjusted_ohlc.parquet")
BASELINE_BACKTEST_PATH = Path("data/processed/backtest_daily.parquet")

ROBUSTNESS_DIR = Path("data/processed/robustness")


# =========================================================
# ROBUSTNESS SPECIFICATION
# =========================================================

# Strategy 0 remains frozen at:
# momentum = 252 trading days
# volatility = 60 trading days
# rebalance = weekly
# transaction costs = 5 bps
#
# The variants below are diagnostic only.
# They are NOT used to re-optimize Strategy 0.

MOMENTUM_LOOKBACKS = [126, 189, 252, 378]
VOLATILITY_WINDOWS = [40, 60, 90]
REBALANCE_FREQUENCIES = ["weekly", "biweekly", "monthly"]
TRANSACTION_COSTS_BPS = [0, 5, 10, 20]

PERIODS = {
    "TRAIN": (TRAIN_START, TRAIN_END),
    "VALIDATION": (VALIDATION_START, VALIDATION_END),
    "TEST": (TEST_START, TEST_END),
}


# =========================================================
# DATA
# =========================================================

def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required_paths = [
        ADJ_CLOSE_PATH,
        RETURNS_PATH,
        ADJ_OHLC_PATH,
    ]

    for path in required_paths:
        if not path.exists():
            raise FileNotFoundError(
                f"Required file not found: {path}"
            )

    adj_close = pd.read_parquet(ADJ_CLOSE_PATH)
    returns = pd.read_parquet(RETURNS_PATH)
    adjusted_ohlc = pd.read_parquet(ADJ_OHLC_PATH)

    return adj_close, returns, adjusted_ohlc


# =========================================================
# FEATURES
# =========================================================

def calculate_momentum_for_window(
    adj_close: pd.DataFrame,
    lookback: int,
) -> pd.DataFrame:
    if lookback <= 0:
        raise ValueError(
            "Momentum lookback must be positive."
        )

    return (
        adj_close
        / adj_close.shift(lookback)
        - 1.0
    )


def calculate_volatility_for_window(
    returns: pd.DataFrame,
    window: int,
) -> pd.DataFrame:
    if window <= 1:
        raise ValueError(
            "Volatility window must be greater than 1."
        )

    return (
        returns
        .rolling(
            window=window,
            min_periods=window,
        )
        .std()
        * np.sqrt(252)
    )


# =========================================================
# PORTFOLIO CONSTRUCTION
# =========================================================

def calculate_target_weights_for_universe(
    signals: pd.DataFrame,
    volatility: pd.DataFrame,
    universe: list[str],
) -> pd.DataFrame:
    """
    Strategy 0 portfolio construction on a reduced universe.

    The omitted ETF remains present in the output columns with
    zero weight so the existing backtest engine can be reused.

    With reduced universe U:
        G_t = N_t / |U|
    """
    if not universe:
        raise ValueError(
            "Universe must contain at least one asset."
        )

    unknown = set(universe) - set(TICKERS)

    if unknown:
        raise ValueError(
            f"Unknown tickers in universe: {sorted(unknown)}"
        )

    weights = pd.DataFrame(
        0.0,
        index=signals.index,
        columns=TICKERS,
    )

    for date in signals.index:
        signal_row = signals.loc[date, universe]
        vol_row = volatility.loc[date, universe]

        active_tickers = list(
            signal_row.index[
                signal_row == 1.0
            ]
        )

        if not active_tickers:
            continue

        missing_vol = (
            vol_row[
                active_tickers
            ]
            .isna()
        )

        if missing_vol.any():
            bad_tickers = list(
                vol_row[
                    active_tickers
                ][missing_vol].index
            )

            raise ValueError(
                f"Missing volatility for active assets "
                f"on {date.date()}: {bad_tickers}"
            )

        gross_exposure = (
            len(active_tickers)
            / len(universe)
        )

        inverse_vol = (
            1.0
            / vol_row[
                active_tickers
            ]
        )

        normalized_inverse_vol = (
            inverse_vol
            / inverse_vol.sum()
        )

        raw_weights = (
            gross_exposure
            * normalized_inverse_vol
        )

        capped_weights = raw_weights.clip(
            upper=MAX_ASSET_WEIGHT
        )

        weights.loc[
            date,
            active_tickers,
        ] = capped_weights

    return weights


def build_target_portfolio(
    momentum: pd.DataFrame,
    volatility: pd.DataFrame,
    universe: list[str],
) -> pd.DataFrame:
    signals = calculate_signals(
        momentum=momentum
    )

    validate_signals(
        momentum=momentum,
        signals=signals,
    )

    if list(universe) == list(TICKERS):
        asset_weights = calculate_target_weights(
            signals=signals,
            volatility=volatility,
        )
    else:
        asset_weights = calculate_target_weights_for_universe(
            signals=signals,
            volatility=volatility,
            universe=universe,
        )

    portfolio = add_cash_weight(
        weights=asset_weights
    )

    validate_weights(
        portfolio=portfolio
    )

    return portfolio


# =========================================================
# REBALANCE SCHEDULES
# =========================================================

def get_monthly_decision_dates(
    trading_index: pd.DatetimeIndex,
) -> pd.DatetimeIndex:
    mask = (
        (
            trading_index
            >= pd.Timestamp(BACKTEST_START)
        )
        & (
            trading_index
            <= pd.Timestamp(BACKTEST_END)
        )
    )

    dates = trading_index[mask]

    date_series = pd.Series(
        dates,
        index=dates,
    )

    decision_dates = (
        date_series
        .groupby(
            dates.to_period("M")
        )
        .max()
    )

    return pd.DatetimeIndex(
        decision_dates
    )


def build_schedule_from_decision_dates(
    target_weights: pd.DataFrame,
    trading_index: pd.DatetimeIndex,
    decision_dates: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    schedule_rows = []
    execution_rows = []

    for decision_date in decision_dates:
        execution_date = get_next_trading_day(
            decision_date,
            trading_index,
        )

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

    schedule = pd.DataFrame(
        schedule_rows
    )

    execution_weights = pd.DataFrame(
        execution_rows
    )

    execution_weights.index.name = (
        "execution_date"
    )

    validate_schedule(
        schedule=schedule,
        execution_weights=execution_weights,
        trading_index=trading_index,
    )

    return schedule, execution_weights


def build_schedule_for_frequency(
    target_weights: pd.DataFrame,
    trading_index: pd.DatetimeIndex,
    frequency: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frequency == "weekly":
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

        return schedule, execution_weights

    if frequency == "biweekly":
        weekly_dates = get_weekly_decision_dates(
            trading_index
        )
        decision_dates = weekly_dates[::2]

    elif frequency == "monthly":
        decision_dates = get_monthly_decision_dates(
            trading_index
        )

    else:
        raise ValueError(
            f"Unsupported rebalance frequency: {frequency}"
        )

    return build_schedule_from_decision_dates(
        target_weights=target_weights,
        trading_index=trading_index,
        decision_dates=decision_dates,
    )


# =========================================================
# BACKTEST
# =========================================================

def run_backtest_with_cost(
    adjusted_ohlc: pd.DataFrame,
    rebalance_weights: pd.DataFrame,
    transaction_cost_bps: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    backtest.py imports TRANSACTION_COST_BPS into its module
    namespace. For a robustness run, temporarily replace that
    module-global value and immediately restore it afterwards.
    """
    if transaction_cost_bps < 0:
        raise ValueError(
            "Transaction costs cannot be negative."
        )

    original_cost = (
        backtest_module.TRANSACTION_COST_BPS
    )

    try:
        backtest_module.TRANSACTION_COST_BPS = (
            transaction_cost_bps
        )

        backtest, realized_weights = (
            backtest_module.run_backtest(
                adjusted_ohlc=adjusted_ohlc,
                rebalance_weights=rebalance_weights,
            )
        )

    finally:
        backtest_module.TRANSACTION_COST_BPS = (
            original_cost
        )

    validate_backtest(
        backtest=backtest,
        realized_weights=realized_weights,
    )

    return backtest, realized_weights


# =========================================================
# GENERIC VARIANT
# =========================================================

def run_strategy_variant(
    adj_close: pd.DataFrame,
    returns: pd.DataFrame,
    adjusted_ohlc: pd.DataFrame,
    momentum_lookback: int = MOMENTUM_WINDOW,
    volatility_window: int = VOLATILITY_WINDOW,
    rebalance_frequency: str = "weekly",
    transaction_cost_bps: int = TRANSACTION_COST_BPS,
    universe: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if universe is None:
        universe = list(TICKERS)

    momentum = calculate_momentum_for_window(
        adj_close=adj_close,
        lookback=momentum_lookback,
    )

    volatility = calculate_volatility_for_window(
        returns=returns,
        window=volatility_window,
    )

    target_portfolio = build_target_portfolio(
        momentum=momentum,
        volatility=volatility,
        universe=universe,
    )

    _, rebalance_weights = (
        build_schedule_for_frequency(
            target_weights=target_portfolio,
            trading_index=adjusted_ohlc.index,
            frequency=rebalance_frequency,
        )
    )

    return run_backtest_with_cost(
        adjusted_ohlc=adjusted_ohlc,
        rebalance_weights=rebalance_weights,
        transaction_cost_bps=transaction_cost_bps,
    )


# =========================================================
# BASELINE SANITY CHECK
# =========================================================

def validate_baseline_reproduction(
    robustness_backtest: pd.DataFrame,
) -> None:
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
                    candidate
                    - reference
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
        "robustness pipeline reproduces Strategy 0."
    )


# =========================================================
# METRICS
# =========================================================

def collect_period_results(
    experiment: str,
    variant: str,
    backtest: pd.DataFrame,
    realized_weights: pd.DataFrame,
) -> list[dict]:
    rows = []

    final_value = float(
        backtest[
            "portfolio_value"
        ].iloc[-1]
    )

    for period, (
        start,
        end,
    ) in PERIODS.items():
        metrics = calculate_period_metrics(
            backtest=backtest,
            realized_weights=realized_weights,
            start=start,
            end=end,
        )

        rows.append(
            {
                "experiment": experiment,
                "variant": variant,
                "period": period,
                "total_return":
                    metrics["Total Return"],
                "cagr":
                    metrics["CAGR"],
                "annual_volatility":
                    metrics["Annual Volatility"],
                "sharpe":
                    metrics["Sharpe"],
                "sortino":
                    metrics["Sortino"],
                "max_drawdown":
                    metrics["Max Drawdown"],
                "calmar":
                    metrics["Calmar"],
                "annual_turnover":
                    metrics["Annual Turnover"],
                "average_cash":
                    metrics["Average Cash"],
                "transaction_costs":
                    metrics["Transaction Costs"],
                "rebalances":
                    metrics["Rebalances"],
                "final_value_full_period":
                    final_value,
            }
        )

    return rows


# =========================================================
# OUTPUT
# =========================================================

def print_results(
    results: pd.DataFrame,
    title: str,
) -> None:
    print(
        f"\n=== {title} ==="
    )

    for period in PERIODS:
        subset = (
            results[
                results["period"] == period
            ]
            .copy()
        )

        table = pd.DataFrame(
            {
                "Variant":
                    subset["variant"],
                "CAGR":
                    subset["cagr"].map(
                        lambda x: f"{x:.2%}"
                    ),
                "Vol":
                    subset[
                        "annual_volatility"
                    ].map(
                        lambda x: f"{x:.2%}"
                    ),
                "Sharpe":
                    subset["sharpe"].map(
                        lambda x: f"{x:.3f}"
                    ),
                "MaxDD":
                    subset[
                        "max_drawdown"
                    ].map(
                        lambda x: f"{x:.2%}"
                    ),
                "Calmar":
                    subset["calmar"].map(
                        lambda x: f"{x:.3f}"
                    ),
                "Cash":
                    subset[
                        "average_cash"
                    ].map(
                        lambda x: f"{x:.2%}"
                    ),
                "Turnover":
                    subset[
                        "annual_turnover"
                    ].map(
                        lambda x: f"{x:.3f}"
                    ),
                "Rebalances":
                    subset[
                        "rebalances"
                    ].astype(int),
            }
        )

        print(
            f"\n--- {period} ---\n"
        )
        print(
            table.to_string(
                index=False
            )
        )


def save_experiment_results(
    results: pd.DataFrame,
    stem: str,
) -> None:
    ROBUSTNESS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_path = (
        ROBUSTNESS_DIR
        / f"{stem}.csv"
    )

    parquet_path = (
        ROBUSTNESS_DIR
        / f"{stem}.parquet"
    )

    results.to_csv(
        csv_path,
        index=False,
    )

    results.to_parquet(
        parquet_path,
        index=False,
    )

    print(
        f"\nSaved: {csv_path}"
    )
    print(
        f"Saved: {parquet_path}"
    )


# =========================================================
# EXPERIMENT 1: MOMENTUM
# =========================================================

def run_momentum_experiment(
    adj_close: pd.DataFrame,
    returns: pd.DataFrame,
    adjusted_ohlc: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    print(
        "\nRunning momentum lookback robustness..."
    )

    for lookback in MOMENTUM_LOOKBACKS:
        baseline_label = (
            " [BASELINE]"
            if lookback == MOMENTUM_WINDOW
            else ""
        )

        print(
            f"  momentum = "
            f"{lookback}{baseline_label}"
        )

        backtest, realized_weights = (
            run_strategy_variant(
                adj_close=adj_close,
                returns=returns,
                adjusted_ohlc=adjusted_ohlc,
                momentum_lookback=lookback,
            )
        )

        rows.extend(
            collect_period_results(
                experiment="momentum_lookback",
                variant=str(lookback),
                backtest=backtest,
                realized_weights=realized_weights,
            )
        )

    results = pd.DataFrame(rows)

    print_results(
        results,
        "MOMENTUM LOOKBACK ROBUSTNESS",
    )

    save_experiment_results(
        results,
        "momentum_lookback_results",
    )

    return results


# =========================================================
# EXPERIMENT 2: VOLATILITY WINDOW
# =========================================================

def run_volatility_experiment(
    adj_close: pd.DataFrame,
    returns: pd.DataFrame,
    adjusted_ohlc: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    print(
        "\nRunning volatility-window robustness..."
    )

    for window in VOLATILITY_WINDOWS:
        baseline_label = (
            " [BASELINE]"
            if window == VOLATILITY_WINDOW
            else ""
        )

        print(
            f"  volatility window = "
            f"{window}{baseline_label}"
        )

        backtest, realized_weights = (
            run_strategy_variant(
                adj_close=adj_close,
                returns=returns,
                adjusted_ohlc=adjusted_ohlc,
                volatility_window=window,
            )
        )

        rows.extend(
            collect_period_results(
                experiment="volatility_window",
                variant=str(window),
                backtest=backtest,
                realized_weights=realized_weights,
            )
        )

    results = pd.DataFrame(rows)

    print_results(
        results,
        "VOLATILITY WINDOW ROBUSTNESS",
    )

    save_experiment_results(
        results,
        "volatility_window_results",
    )

    return results


# =========================================================
# EXPERIMENT 3: REBALANCE FREQUENCY
# =========================================================

def run_rebalance_experiment(
    adj_close: pd.DataFrame,
    returns: pd.DataFrame,
    adjusted_ohlc: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    print(
        "\nRunning rebalance-frequency robustness..."
    )

    for frequency in REBALANCE_FREQUENCIES:
        baseline_label = (
            " [BASELINE]"
            if frequency == "weekly"
            else ""
        )

        print(
            f"  rebalance = "
            f"{frequency}{baseline_label}"
        )

        backtest, realized_weights = (
            run_strategy_variant(
                adj_close=adj_close,
                returns=returns,
                adjusted_ohlc=adjusted_ohlc,
                rebalance_frequency=frequency,
            )
        )

        rows.extend(
            collect_period_results(
                experiment="rebalance_frequency",
                variant=frequency,
                backtest=backtest,
                realized_weights=realized_weights,
            )
        )

    results = pd.DataFrame(rows)

    print_results(
        results,
        "REBALANCE FREQUENCY ROBUSTNESS",
    )

    save_experiment_results(
        results,
        "rebalance_frequency_results",
    )

    return results


# =========================================================
# EXPERIMENT 4: TRANSACTION COSTS
# =========================================================

def run_cost_experiment(
    adj_close: pd.DataFrame,
    returns: pd.DataFrame,
    adjusted_ohlc: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    print(
        "\nRunning transaction-cost robustness..."
    )

    for cost_bps in TRANSACTION_COSTS_BPS:
        baseline_label = (
            " [BASELINE]"
            if cost_bps == TRANSACTION_COST_BPS
            else ""
        )

        print(
            f"  costs = "
            f"{cost_bps} bps{baseline_label}"
        )

        backtest, realized_weights = (
            run_strategy_variant(
                adj_close=adj_close,
                returns=returns,
                adjusted_ohlc=adjusted_ohlc,
                transaction_cost_bps=cost_bps,
            )
        )

        rows.extend(
            collect_period_results(
                experiment="transaction_costs",
                variant=f"{cost_bps} bps",
                backtest=backtest,
                realized_weights=realized_weights,
            )
        )

    results = pd.DataFrame(rows)

    print_results(
        results,
        "TRANSACTION COST ROBUSTNESS",
    )

    save_experiment_results(
        results,
        "transaction_cost_results",
    )

    return results


# =========================================================
# EXPERIMENT 5: LEAVE ONE ETF OUT
# =========================================================

def run_leave_one_out_experiment(
    adj_close: pd.DataFrame,
    returns: pd.DataFrame,
    adjusted_ohlc: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    print(
        "\nRunning leave-one-ETF-out robustness..."
    )

    variants = [
        None,
        *list(TICKERS),
    ]

    for omitted in variants:
        if omitted is None:
            universe = list(TICKERS)
            variant = "BASELINE"

            print(
                "  universe = BASELINE"
            )

        else:
            universe = [
                ticker
                for ticker in TICKERS
                if ticker != omitted
            ]

            variant = (
                f"without_{omitted}"
            )

            print(
                f"  universe = without {omitted}"
            )

        backtest, realized_weights = (
            run_strategy_variant(
                adj_close=adj_close,
                returns=returns,
                adjusted_ohlc=adjusted_ohlc,
                universe=universe,
            )
        )

        rows.extend(
            collect_period_results(
                experiment="leave_one_etf_out",
                variant=variant,
                backtest=backtest,
                realized_weights=realized_weights,
            )
        )

    results = pd.DataFrame(rows)

    print_results(
        results,
        "LEAVE-ONE-ETF-OUT ROBUSTNESS",
    )

    save_experiment_results(
        results,
        "leave_one_etf_out_results",
    )

    return results


# =========================================================
# MAIN
# =========================================================

def main() -> None:
    adj_close, returns, adjusted_ohlc = (
        load_inputs()
    )

    print(
        "\n=== STRATEGY 0 ROBUSTNESS TESTS ==="
    )

    print(
        "\nFrozen baseline:"
    )
    print(
        f"  momentum = {MOMENTUM_WINDOW}"
    )
    print(
        f"  volatility = {VOLATILITY_WINDOW}"
    )
    print(
        "  rebalance = weekly"
    )
    print(
        f"  costs = {TRANSACTION_COST_BPS} bps"
    )

    baseline_backtest, _ = (
        run_strategy_variant(
            adj_close=adj_close,
            returns=returns,
            adjusted_ohlc=adjusted_ohlc,
        )
    )

    validate_baseline_reproduction(
        robustness_backtest=baseline_backtest
    )

    all_results = []

    all_results.append(
        run_momentum_experiment(
            adj_close,
            returns,
            adjusted_ohlc,
        )
    )

    all_results.append(
        run_volatility_experiment(
            adj_close,
            returns,
            adjusted_ohlc,
        )
    )

    all_results.append(
        run_rebalance_experiment(
            adj_close,
            returns,
            adjusted_ohlc,
        )
    )

    all_results.append(
        run_cost_experiment(
            adj_close,
            returns,
            adjusted_ohlc,
        )
    )

    all_results.append(
        run_leave_one_out_experiment(
            adj_close,
            returns,
            adjusted_ohlc,
        )
    )

    combined = pd.concat(
        all_results,
        ignore_index=True,
    )

    save_experiment_results(
        combined,
        "all_robustness_results",
    )

    print(
        "\nAll Strategy 0 robustness "
        "tests completed."
    )


if __name__ == "__main__":
    main()
