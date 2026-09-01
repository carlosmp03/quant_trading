from pathlib import Path

import numpy as np
import pandas as pd

from src.config import MOMENTUM_WINDOW, VOLATILITY_WINDOW


ADJ_CLOSE_PATH = Path("data/processed/adj_close.parquet")
RETURNS_PATH = Path("data/processed/returns.parquet")

FEATURES_DIR = Path("data/processed")

MOMENTUM_PATH = FEATURES_DIR / "momentum.parquet"
VOLATILITY_PATH = FEATURES_DIR / "volatility.parquet"


def load_processed_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    adj_close = pd.read_parquet(ADJ_CLOSE_PATH)
    returns = pd.read_parquet(RETURNS_PATH)

    return adj_close, returns


def calculate_momentum(
    adj_close: pd.DataFrame,
) -> pd.DataFrame:
    """
    252-trading-day total return.

    M_t = P_t / P_{t-252} - 1
    """
    momentum = (
        adj_close / adj_close.shift(MOMENTUM_WINDOW)
    ) - 1

    return momentum


def calculate_volatility(
    returns: pd.DataFrame,
) -> pd.DataFrame:
    """
    Annualized historical volatility based on
    the previous 60 daily returns.
    """
    volatility = (
        returns
        .rolling(
            window=VOLATILITY_WINDOW,
            min_periods=VOLATILITY_WINDOW,
        )
        .std()
        * np.sqrt(252)
    )

    return volatility


def save_features(
    momentum: pd.DataFrame,
    volatility: pd.DataFrame,
) -> None:
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)

    momentum.to_parquet(MOMENTUM_PATH)
    volatility.to_parquet(VOLATILITY_PATH)


def print_summary(
    momentum: pd.DataFrame,
    volatility: pd.DataFrame,
) -> None:
    print("\n=== MOMENTUM ===")
    print(momentum.dropna(how="all").head())

    print("\nFirst valid momentum:")
    for ticker in momentum.columns:
        date = momentum[ticker].first_valid_index()
        print(
            f"{ticker:4} | "
            f"{date.date() if date is not None else None}"
        )

    print("\n=== VOLATILITY ===")
    print(volatility.dropna(how="all").head())

    print("\nFirst valid volatility:")
    for ticker in volatility.columns:
        date = volatility[ticker].first_valid_index()
        print(
            f"{ticker:4} | "
            f"{date.date() if date is not None else None}"
        )


def main() -> None:
    adj_close, returns = load_processed_data()

    momentum = calculate_momentum(adj_close)
    volatility = calculate_volatility(returns)

    save_features(
        momentum=momentum,
        volatility=volatility,
    )

    print_summary(
        momentum=momentum,
        volatility=volatility,
    )

    print("\nSaved:")
    print(MOMENTUM_PATH)
    print(VOLATILITY_PATH)


if __name__ == "__main__":
    main()