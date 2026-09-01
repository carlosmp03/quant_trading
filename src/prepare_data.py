from pathlib import Path

import pandas as pd

from src.config import TICKERS


RAW_DATA_PATH = Path("data/raw/etf_daily.parquet")
PROCESSED_DATA_DIR = Path("data/processed")

ADJ_CLOSE_PATH = PROCESSED_DATA_DIR / "adj_close.parquet"
ADJ_OHLC_PATH = PROCESSED_DATA_DIR / "adjusted_ohlc.parquet"
RETURNS_PATH = PROCESSED_DATA_DIR / "returns.parquet"


def load_raw_data() -> pd.DataFrame:
    if not RAW_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Raw data file not found: {RAW_DATA_PATH}"
        )

    data = pd.read_parquet(RAW_DATA_PATH)

    if not data.index.is_monotonic_increasing:
        data = data.sort_index()

    if data.index.has_duplicates:
        raise ValueError("Duplicate dates found in raw data.")

    return data


def extract_adjusted_close(data: pd.DataFrame) -> pd.DataFrame:
    """
    Extract adjusted closing prices and enforce ticker order.
    """
    if "Adj Close" not in data.columns.get_level_values("Price"):
        raise ValueError("Adj Close field is missing from raw data.")

    adj_close = data["Adj Close"].copy()

    missing_tickers = set(TICKERS) - set(adj_close.columns)

    if missing_tickers:
        raise ValueError(
            f"Missing tickers in Adj Close data: {sorted(missing_tickers)}"
        )

    return adj_close[TICKERS]


def calculate_adjustment_factor(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate the historical adjustment factor

        factor = Adj Close / Close

    for every ticker and trading day.
    """
    close = data["Close"][TICKERS]
    adj_close = data["Adj Close"][TICKERS]

    factor = adj_close / close

    return factor


def calculate_adjusted_ohlc(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construct adjusted Open, High, Low and Close prices
    on a consistent historical price scale.
    """
    factor = calculate_adjustment_factor(data)

    adjusted_open = data["Open"][TICKERS] * factor
    adjusted_high = data["High"][TICKERS] * factor
    adjusted_low = data["Low"][TICKERS] * factor
    adjusted_close = data["Adj Close"][TICKERS].copy()

    adjusted_ohlc = pd.concat(
        {
            "Open": adjusted_open,
            "High": adjusted_high,
            "Low": adjusted_low,
            "Close": adjusted_close,
        },
        axis=1,
    )

    return adjusted_ohlc


def calculate_returns(
    adj_close: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate simple daily total returns using adjusted prices.

    fill_method=None is intentional:
    missing prices must not be silently forward-filled.
    """
    returns = adj_close.pct_change(fill_method=None)

    return returns


def save_processed_data(
    adj_close: pd.DataFrame,
    adjusted_ohlc: pd.DataFrame,
    returns: pd.DataFrame,
) -> None:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    adj_close.to_parquet(ADJ_CLOSE_PATH)
    adjusted_ohlc.to_parquet(ADJ_OHLC_PATH)
    returns.to_parquet(RETURNS_PATH)


def print_summary(
    adj_close: pd.DataFrame,
    adjusted_ohlc: pd.DataFrame,
    returns: pd.DataFrame,
) -> None:
    print("\n=== ADJUSTED CLOSE ===")
    print(adj_close.head())
    print("\nShape:", adj_close.shape)

    print("\nMissing adjusted prices:")
    print(adj_close.isna().sum())

    print("\n=== ADJUSTED OHLC ===")
    print(adjusted_ohlc.head())

    print("\nAdjusted OHLC shape:")
    print(adjusted_ohlc.shape)

    print("\n=== RETURNS ===")
    print(returns.head())

    print("\nMissing returns:")
    print(returns.isna().sum())

    print("\nFirst valid return by ticker:")

    for ticker in TICKERS:
        first_valid = returns[ticker].first_valid_index()

        print(
            f"{ticker:4} | "
            f"{first_valid.date() if first_valid is not None else None}"
        )


def main() -> None:
    raw_data = load_raw_data()

    adj_close = extract_adjusted_close(raw_data)

    adjusted_ohlc = calculate_adjusted_ohlc(raw_data)

    returns = calculate_returns(adj_close)

    save_processed_data(
        adj_close=adj_close,
        adjusted_ohlc=adjusted_ohlc,
        returns=returns,
    )

    print_summary(
        adj_close=adj_close,
        adjusted_ohlc=adjusted_ohlc,
        returns=returns,
    )

    print("\nSaved:")
    print(ADJ_CLOSE_PATH)
    print(ADJ_OHLC_PATH)
    print(RETURNS_PATH)


if __name__ == "__main__":
    main()