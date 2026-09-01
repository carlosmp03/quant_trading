from pathlib import Path

import pandas as pd


MOMENTUM_PATH = Path("data/processed/momentum.parquet")
SIGNALS_PATH = Path("data/processed/signals.parquet")


def load_momentum() -> pd.DataFrame:
    if not MOMENTUM_PATH.exists():
        raise FileNotFoundError(
            f"Momentum file not found: {MOMENTUM_PATH}"
        )

    return pd.read_parquet(MOMENTUM_PATH)


def calculate_signals(
    momentum: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generate the Strategy 0 trend signal.

    Signal:
        1 -> positive 252-day momentum
        0 -> non-positive 252-day momentum
        NaN -> insufficient historical data
    """

    signals = pd.DataFrame(
        index=momentum.index,
        columns=momentum.columns,
        dtype=float,
    )

    # Only create a signal when momentum itself is available.
    valid = momentum.notna()

    signals[valid & (momentum > 0)] = 1.0
    signals[valid & (momentum <= 0)] = 0.0

    return signals


def validate_signals(
    momentum: pd.DataFrame,
    signals: pd.DataFrame,
) -> None:
    """
    Basic checks that signals are consistent with momentum.
    """

    valid_values = signals.stack().dropna().unique()

    unexpected_values = set(valid_values) - {0.0, 1.0}

    if unexpected_values:
        raise ValueError(
            f"Unexpected signal values: {unexpected_values}"
        )

    positive_wrong = (
        (momentum > 0)
        & (signals != 1.0)
    )

    non_positive_wrong = (
        (momentum <= 0)
        & momentum.notna()
        & (signals != 0.0)
    )

    if positive_wrong.any().any():
        raise RuntimeError(
            "Positive momentum does not always produce signal = 1."
        )

    if non_positive_wrong.any().any():
        raise RuntimeError(
            "Non-positive momentum does not always produce signal = 0."
        )

    # Missing momentum must remain missing in signals.
    missing_wrong = (
        momentum.isna()
        & signals.notna()
    )

    if missing_wrong.any().any():
        raise RuntimeError(
            "Signal exists where momentum is unavailable."
        )


def print_summary(
    signals: pd.DataFrame,
) -> None:
    print("\n=== SIGNALS ===")
    print(signals.dropna(how="all").head())

    print("\nFirst valid signal:")

    for ticker in signals.columns:
        date = signals[ticker].first_valid_index()

        print(
            f"{ticker:4} | "
            f"{date.date() if date is not None else None}"
        )

    print("\nSignal counts:")

    for ticker in signals.columns:
        counts = signals[ticker].value_counts(
            dropna=False
        )

        long_count = int(counts.get(1.0, 0))
        out_count = int(counts.get(0.0, 0))
        missing_count = int(signals[ticker].isna().sum())

        print(
            f"{ticker:4} | "
            f"LONG={long_count:4} | "
            f"OUT={out_count:4} | "
            f"NA={missing_count:4}"
        )


def main() -> None:
    momentum = load_momentum()

    signals = calculate_signals(momentum)

    validate_signals(
        momentum=momentum,
        signals=signals,
    )

    signals.to_parquet(SIGNALS_PATH)

    print_summary(signals)

    print("\nSignal validation passed.")
    print(f"Saved: {SIGNALS_PATH}")


if __name__ == "__main__":
    main()