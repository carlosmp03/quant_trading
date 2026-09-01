from pathlib import Path

import numpy as np
import pandas as pd

from src.config import TICKERS


RAW_DATA_PATH = Path("data/raw/etf_daily.parquet")
ADJ_OHLC_PATH = Path("data/processed/adjusted_ohlc.parquet")


def main() -> None:
    raw = pd.read_parquet(RAW_DATA_PATH)
    adjusted = pd.read_parquet(ADJ_OHLC_PATH)

    # IMPORTANT:
    # enforce exactly the same ticker order on both datasets.
    close = raw["Close"][TICKERS]
    adj_close = raw["Adj Close"][TICKERS]

    open_ = raw["Open"][TICKERS]
    high = raw["High"][TICKERS]
    low = raw["Low"][TICKERS]

    factor = adj_close / close

    reconstructed_open = open_ * factor
    reconstructed_high = high * factor
    reconstructed_low = low * factor

    adjusted_open = adjusted["Open"][TICKERS]
    adjusted_high = adjusted["High"][TICKERS]
    adjusted_low = adjusted["Low"][TICKERS]
    adjusted_close = adjusted["Close"][TICKERS]

    checks = {
        "Open": np.allclose(
            reconstructed_open.to_numpy(),
            adjusted_open.to_numpy(),
            equal_nan=True,
        ),
        "High": np.allclose(
            reconstructed_high.to_numpy(),
            adjusted_high.to_numpy(),
            equal_nan=True,
        ),
        "Low": np.allclose(
            reconstructed_low.to_numpy(),
            adjusted_low.to_numpy(),
            equal_nan=True,
        ),
        "Close": np.allclose(
            adj_close.to_numpy(),
            adjusted_close.to_numpy(),
            equal_nan=True,
        ),
    }

    print("=== ADJUSTMENT VALIDATION ===")

    for field, result in checks.items():
        print(f"{field:5}: {'OK' if result else 'FAILED'}")

    if not all(checks.values()):
        raise RuntimeError("Adjusted OHLC validation failed.")

    print("\nAll adjusted OHLC checks passed.")


if __name__ == "__main__":
    main()