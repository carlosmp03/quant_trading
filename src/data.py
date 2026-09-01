from pathlib import Path

import pandas as pd
import yfinance as yf

from src.config import DATA_END, DATA_START, TICKERS


RAW_DATA_DIR = Path("data/raw")


def download_market_data() -> pd.DataFrame:
    """
    Download daily OHLCV data for the fixed ETF universe.

    auto_adjust=False is intentional:
    we want to keep both Close and Adj Close separately.
    """
    data = yf.download(
        tickers=TICKERS,
        start=DATA_START,
        end=DATA_END,
        interval="1d",
        auto_adjust=False,
        actions=False,
        progress=True,
        group_by="column",
    )

    if data.empty:
        raise RuntimeError("Downloaded dataset is empty.")

    return data


def save_raw_data(data: pd.DataFrame) -> Path:
    """
    Save untouched downloaded data in Parquet format.
    """
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    output_path = RAW_DATA_DIR / "etf_daily.parquet"
    data.to_parquet(output_path)

    return output_path


def main() -> None:
    data = download_market_data()

    print("\nDownloaded data:")
    print(data.head())

    print("\nShape:")
    print(data.shape)

    print("\nDate range:")
    print(data.index.min(), "->", data.index.max())

    path = save_raw_data(data)

    print(f"\nRaw data saved to: {path}")


if __name__ == "__main__":
    main()