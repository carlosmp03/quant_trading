# Strategy 0 — Robustness Test Plan

This document fixes the robustness-test design before reviewing the
results of the remaining robustness experiments.

Strategy 0 itself remains frozen.

## Frozen baseline

- Universe: SPY, QQQ, IWM, EFA, EEM, IEF, GLD, DBC
- Momentum lookback: 252 trading days
- Volatility window: 60 trading days
- Rebalance frequency: weekly
- Transaction costs: 5 bps
- Maximum ETF weight: 25%
- Long-only
- No leverage
- No derivatives

Train / Validation / Test remain:

- Train: 2007-2015
- Validation: 2016-2020
- Test: 2021-2025

Robustness variants are diagnostic only. They are not used to replace
the frozen Strategy 0 parameters.

---

## 1. Momentum lookback sensitivity

Change only the momentum lookback:

- 126 trading days
- 189 trading days
- 252 trading days — baseline
- 378 trading days

All other parameters remain fixed.

This test has already been run. The 252-day variant must reproduce the
frozen Strategy 0 backtest.

---

## 2. Volatility-window sensitivity

Change only the rolling volatility-estimation window:

- 40 trading days
- 60 trading days — baseline
- 90 trading days

Momentum remains 252 trading days.

Rebalancing remains weekly.

Transaction costs remain 5 bps.

---

## 3. Rebalance-frequency sensitivity

Change only the rebalance frequency:

- weekly — baseline
- biweekly
- monthly

Weekly decision dates are the last actual trading day of each
Monday-Friday trading week.

Biweekly rebalancing is defined as every second weekly decision date,
anchored at the first weekly decision date of the backtest.

Monthly decision dates are the last actual trading day of each calendar
month.

In every case, the signal is observed after the decision-date Close and
the rebalance is executed at the Open of the next trading day.

---

## 4. Transaction-cost sensitivity

Change only total transaction costs:

- 0 bps
- 5 bps — baseline
- 10 bps
- 20 bps

Costs are applied to realized turnover at each rebalance.

---

## 5. Leave-one-ETF-out robustness

Run the frozen Strategy 0 once for the full universe and then eight
additional times, excluding one ETF at a time:

- without SPY
- without QQQ
- without IWM
- without EFA
- without EEM
- without IEF
- without GLD
- without DBC

For each reduced universe, the Strategy 0 exposure rule is applied to
the remaining universe:

\[
G_t = \frac{N_t}{|\mathcal U|}.
\]

Thus, with one ETF removed, the denominator becomes 7.

The omitted ETF receives zero weight throughout the backtest.

---

## Evaluation

For every variant, report separately for Train, Validation and Test:

- CAGR
- annualized volatility
- Sharpe ratio
- maximum drawdown
- Calmar ratio
- average cash weight
- annual turnover
- number of rebalances

No single best parameter value will be selected from these experiments.

The objective is to determine whether the qualitative behavior of
Strategy 0 survives reasonable perturbations of its design choices.

After these robustness tests are completed, the next planned stage is
walk-forward analysis.
