TICKERS = [
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "IEF",
    "GLD",
    "DBC",
]

# Warm-up начинается раньше самого backtest,
# чтобы к 01.01.2007 уже можно было рассчитать momentum.
DATA_START = "2005-01-01"

# yfinance трактует end как исключительную границу,
# поэтому для получения данных по 31.12.2025 указываем 01.01.2026.
DATA_END = "2026-01-01"

BACKTEST_START = "2007-01-01"
BACKTEST_END = "2025-12-31"

MOMENTUM_WINDOW = 252
VOLATILITY_WINDOW = 60

TRANSACTION_COST_BPS = 5
MAX_ASSET_WEIGHT = 0.25

TRAIN_START = "2007-01-01"
TRAIN_END = "2015-12-31"

VALIDATION_START = "2016-01-01"
VALIDATION_END = "2020-12-31"

TEST_START = "2021-01-01"
TEST_END = "2025-12-31"