# Strategy 0 — Walk-Forward Plan

This document fixes the walk-forward evaluation design before reviewing
the results.

Strategy 0 remains frozen.

## Why this is not walk-forward optimization

Strategy 0 has no fitted statistical or machine-learning model and no
parameter is re-estimated from an in-sample objective.

Its signal and volatility estimates are already rolling and causal:
they use only information available up to the decision date.

Therefore, for Strategy 0 the relevant walk-forward exercise is a
fixed-parameter sequential out-of-sample evaluation rather than
repeated parameter optimization.

No momentum lookback, volatility window, rebalance frequency, universe
choice, or transaction-cost assumption is selected using walk-forward
results.

## Frozen Strategy 0

- Universe: SPY, QQQ, IWM, EFA, EEM, IEF, GLD, DBC
- Momentum lookback: 252 trading days
- Volatility window: 60 trading days
- Rebalance frequency: weekly
- Transaction costs: 5 bps
- Maximum ETF weight: 25%
- Long-only
- No leverage
- No derivatives

## Walk-forward design

Mode:

- expanding historical window;
- one-year out-of-sample blocks;
- five complete calendar years of history before the first OOS block.

With the existing 2007-2025 backtest, the sequence is:

- history 2007-2011 -> OOS 2012
- history 2007-2012 -> OOS 2013
- history 2007-2013 -> OOS 2014
- ...
- history 2007-2024 -> OOS 2025

The historical window is reported for context only. It is not used to
choose or modify Strategy 0.

## Metrics

For every OOS block report:

- total return;
- annualized volatility;
- Sharpe ratio;
- maximum drawdown;
- Calmar ratio;
- average cash weight;
- annual turnover;
- transaction costs;
- number of rebalances.

For comparison, the expanding-history Sharpe ratio is also recorded.

## Stitched OOS series

All non-overlapping OOS blocks are concatenated into a single
out-of-sample return series.

The stitched series starts in 2012 and ends in 2025.

Its daily returns must exactly match the corresponding dates of the
frozen Strategy 0 backtest. This is a sanity check that the
walk-forward reporting layer does not alter the strategy or execution
logic.

## Interpretation

This test is intended to answer:

- Does Strategy 0 show acceptable behavior across many sequential
  future periods rather than only in one Train/Validation/Test split?
- Are results concentrated in a small number of years?
- Does the defensive profile persist across different market regimes?
- How unstable are annual Sharpe, drawdown, cash exposure and turnover?

This test does NOT establish that Strategy 0 has robust alpha and does
NOT create a new optimized strategy.

After walk-forward analysis is interpreted and documented, Strategy 0
research can be closed and Strategy 1 can be designed from the observed
strengths and weaknesses.
