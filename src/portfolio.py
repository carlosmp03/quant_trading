from pathlib import Path

import numpy as np
import pandas as pd

from src.config import MAX_ASSET_WEIGHT, TICKERS


SIGNALS_PATH = Path("data/processed/signals.parquet")
VOLATILITY_PATH = Path("data/processed/volatility.parquet")

WEIGHTS_PATH = Path("data/processed/target_weights.parquet")


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    signals = pd.read_parquet(SIGNALS_PATH)
    volatility = pd.read_parquet(VOLATILITY_PATH)

    signals = signals[TICKERS]
    volatility = volatility[TICKERS]

    if not signals.index.equals(volatility.index):
        raise ValueError(
            "Signals and volatility have different date indices."
        )

    return signals, volatility


def calculate_target_weights(
    signals: pd.DataFrame,
    volatility: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate Strategy 0 target weights.

    1. Assets with signal = 1 are active.
    2. Gross exposure = number of active assets / 8.
    3. Active assets are weighted inversely to volatility.
    4. Each individual asset is capped at MAX_ASSET_WEIGHT.
    5. Unallocated capital remains in cash.
    """

    weights = pd.DataFrame(
        0.0,
        index=signals.index,
        columns=TICKERS,
    )

    for date in signals.index:
        signal_row = signals.loc[date]
        vol_row = volatility.loc[date]

        active = signal_row == 1.0

        active_tickers = signal_row.index[active]

        if len(active_tickers) == 0:
            continue

        # A positive signal must have a valid volatility estimate.
        missing_vol = vol_row[active_tickers].isna()

        if missing_vol.any():
            bad_tickers = list(
                vol_row[active_tickers][missing_vol].index
            )

            raise ValueError(
                f"Missing volatility for active assets "
                f"on {date.date()}: {bad_tickers}"
            )

        n_active = len(active_tickers)

        # G_t = N_t / 8
        gross_exposure = n_active / len(TICKERS)

        inverse_vol = 1.0 / vol_row[active_tickers]

        normalized_inverse_vol = (
            inverse_vol / inverse_vol.sum()
        )

        raw_weights = (
            gross_exposure * normalized_inverse_vol
        )

        # Apply the 25% position cap.
        capped_weights = raw_weights.clip(
            upper=MAX_ASSET_WEIGHT
        )

        weights.loc[
            date,
            active_tickers,
        ] = capped_weights

    return weights


def add_cash_weight(
    weights: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add cash as the residual portfolio weight.
    """

    portfolio = weights.copy()

    portfolio["CASH"] = 1.0 - portfolio.sum(axis=1)

    return portfolio


def validate_weights(
    portfolio: pd.DataFrame,
) -> None:
    asset_weights = portfolio[TICKERS]

    tolerance = 1e-10

    if (asset_weights < -tolerance).any().any():
        raise RuntimeError(
            "Negative asset weight found."
        )

    if (
        asset_weights > MAX_ASSET_WEIGHT + tolerance
    ).any().any():
        raise RuntimeError(
            "Asset weight exceeds maximum allowed weight."
        )

    if (portfolio["CASH"] < -tolerance).any():
        raise RuntimeError(
            "Negative cash weight found."
        )

    total_weight = portfolio.sum(axis=1)

    if not np.allclose(
        total_weight.to_numpy(),
        1.0,
        atol=1e-10,
    ):
        raise RuntimeError(
            "Portfolio weights do not sum to 1."
        )


def print_summary(
    portfolio: pd.DataFrame,
) -> None:
    print("\n=== TARGET WEIGHTS ===")

    # Show first date where at least one asset has a position.
    invested = portfolio[TICKERS].sum(axis=1) > 0

    print(
        portfolio.loc[invested].head()
    )

    print("\nAverage asset weights:")
    print(
        portfolio[TICKERS]
        .mean()
        .sort_values(ascending=False)
    )

    print("\nAverage cash weight:")
    print(
        f"{portfolio['CASH'].mean():.4f}"
    )

    print("\nMaximum observed asset weight:")
    print(
        f"{portfolio[TICKERS].max().max():.4f}"
    )

    print("\nMinimum cash weight:")
    print(
        f"{portfolio['CASH'].min():.4f}"
    )

    print("\nMaximum cash weight:")
    print(
        f"{portfolio['CASH'].max():.4f}"
    )


def main() -> None:
    signals, volatility = load_inputs()

    weights = calculate_target_weights(
        signals=signals,
        volatility=volatility,
    )

    portfolio = add_cash_weight(weights)

    validate_weights(portfolio)

    portfolio.to_parquet(WEIGHTS_PATH)

    print_summary(portfolio)

    print("\nPortfolio validation passed.")
    print(f"Saved: {WEIGHTS_PATH}")


if __name__ == "__main__":
    main()