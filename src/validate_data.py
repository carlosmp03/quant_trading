from pathlib import Path

import pandas as pd

from src.config import BACKTEST_END, BACKTEST_START, TICKERS


RAW_DATA_PATH = Path("data/raw/etf_daily.parquet")


def load_raw_data() -> pd.DataFrame:
    if not RAW_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Raw data file not found: {RAW_DATA_PATH}"
        )

    return pd.read_parquet(RAW_DATA_PATH)


def validate_tickers(data: pd.DataFrame) -> None:
    available_tickers = set(data.columns.get_level_values("Ticker"))

    expected_tickers = set(TICKERS)

    missing = expected_tickers - available_tickers
    extra = available_tickers - expected_tickers

    print("\n=== TICKERS ===")
    print("Expected:", sorted(expected_tickers))
    print("Available:", sorted(available_tickers))

    if missing:
        print("Missing tickers:", sorted(missing))

    if extra:
        print("Unexpected tickers:", sorted(extra))

    if not missing:
        print("All expected tickers are present.")


def print_data_availability(data: pd.DataFrame) -> None:
    print("\n=== DATA AVAILABILITY ===")

    adj_close = data["Adj Close"]

    for ticker in TICKERS:
        series = adj_close[ticker]

        first_valid = series.first_valid_index()
        last_valid = series.last_valid_index()
        missing_count = series.isna().sum()

        print(
            f"{ticker:4} | "
            f"first={first_valid.date() if first_valid else None} | "
            f"last={last_valid.date() if last_valid else None} | "
            f"missing={missing_count}"
        )


def validate_backtest_period(data: pd.DataFrame) -> None:
    print("\n=== BACKTEST PERIOD ===")

    backtest_data = data.loc[
        BACKTEST_START:BACKTEST_END,
        "Adj Close",
    ]

    missing = backtest_data.isna().sum()

    print("Missing Adj Close observations during backtest:")
    print(missing)

    problematic = missing[missing > 0]

    if problematic.empty:
        print("\nAll tickers have complete Adj Close data during backtest.")
    else:
        print("\nWARNING: missing observations found:")
        print(problematic)


def validate_prices(data: pd.DataFrame) -> None:
    print("\n=== PRICE CHECK ===")

    adj_close = data["Adj Close"]

    non_positive = (adj_close <= 0).sum()

    if (non_positive == 0).all():
        print("No zero or negative adjusted prices found.")
    else:
        print("WARNING: non-positive prices found:")
        print(non_positive[non_positive > 0])


def main() -> None:
    data = load_raw_data()

    print("Dataset shape:", data.shape)
    print("Date range:", data.index.min(), "->", data.index.max())

    validate_tickers(data)
    print_data_availability(data)
    validate_backtest_period(data)
    validate_prices(data)


if __name__ == "__main__":
    main()