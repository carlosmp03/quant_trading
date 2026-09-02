# Strategy 0 — Research Results

Этот документ содержит результаты эмпирического исследования Strategy 0.

Предварительная спецификация стратегии была зафиксирована до проведения тестов в `STRATEGY_SPEC_v0.1.md`.

После просмотра Test параметры Strategy 0 считаются замороженными. Все последующие изменения параметров рассматриваются исключительно как robustness tests и не используются для выбора новой версии Strategy 0.

---

## 1. Baseline backtest

Периоды:

- Train: 2007-2015
- Validation: 2016-2020
- Test: 2021-2025

### Train

| Portfolio | CAGR | Volatility | Sharpe | Max Drawdown |
| --- | ---: | ---: | ---: | ---: |
| Strategy 0 | 4.60% | 7.63% | 0.628 | -8.54% |
| Inverse Vol | 5.08% | 11.87% | 0.477 | -30.41% |
| Equal Weight | 4.88% | 17.06% | 0.365 | -41.72% |
| SPY | 6.26% | 21.54% | 0.390 | -55.19% |

### Validation

| Portfolio | CAGR | Volatility | Sharpe | Max Drawdown |
| --- | ---: | ---: | ---: | ---: |
| Strategy 0 | 3.31% | 6.22% | 0.555 | -10.96% |
| Inverse Vol | 9.16% | 9.19% | 0.999 | -19.49% |
| Equal Weight | 12.01% | 13.19% | 0.926 | -24.53% |
| SPY | 15.13% | 18.87% | 0.841 | -33.72% |

### Test

| Portfolio | CAGR | Volatility | Sharpe | Max Drawdown | Calmar |
| --- | ---: | ---: | ---: | ---: | ---: |
| Strategy 0 | 6.83% | 7.67% | 0.901 | -10.30% | 0.663 |
| Inverse Vol | 7.97% | 10.36% | 0.793 | -19.23% | 0.414 |
| Equal Weight | 10.10% | 12.54% | 0.831 | -20.15% | 0.502 |
| SPY | 14.37% | 17.12% | 0.871 | -24.50% | 0.587 |

Strategy 0 не максимизирует абсолютную доходность. Её основное отличие от benchmarks — существенно меньшие volatility и drawdown.

На Validation Strategy 0 заметно уступает обычному inverse-volatility portfolio по Sharpe. Поэтому первоначальные результаты не позволяют утверждать, что trend filter устойчиво улучшает risk-adjusted performance.

---

## 2. Decomposition of Strategy 0

Для анализа механизма Strategy 0 были построены два дополнительных контрольных портфеля:

- Constant Exposure InvVol;
- Exposure Matched InvVol.

Декомпозиция:

\[
\text{Full Inverse Vol}
\rightarrow
\text{Constant Exposure InvVol}
\rightarrow
\text{Exposure Matched InvVol}
\rightarrow
\text{Strategy 0}.
\]

### 2.1. Reduced exposure effect

Constant Exposure InvVol использует постоянную risky exposure 66.99%, рассчитанную только по Train.

На Test:

| Portfolio | CAGR | Volatility | Sharpe | Max Drawdown |
| --- | ---: | ---: | ---: | ---: |
| Inverse Vol | 7.97% | 10.36% | 0.793 | -19.23% |
| Constant Exposure InvVol | 5.29% | 6.96% | 0.776 | -13.37% |

Значительная часть снижения волатильности Strategy 0 объясняется самим фактом меньшей средней risky exposure.

### 2.2. Dynamic exposure timing

Переход от Constant Exposure InvVol к Exposure Matched InvVol показывает эффект динамического изменения общей risky exposure.

Train:

\[
Sharpe: 0.490 \rightarrow 0.487,
\]

\[
MaxDD: -21.49\% \rightarrow -13.06\%.
\]

Validation:

\[
Sharpe: 1.040 \rightarrow 0.780.
\]

Test:

\[
Sharpe: 0.776 \rightarrow 0.942,
\]

\[
MaxDD: -13.37\% \rightarrow -8.27\%.
\]

Динамическое управление exposure способно существенно снижать drawdown в отдельных режимах, однако его эффект по Sharpe нестабилен между периодами.

### 2.3. Momentum-based ETF selection

Переход от Exposure Matched InvVol к Strategy 0 показывает дополнительный эффект выбора ETF с положительным momentum при той же общей risky exposure.

Train:

\[
Sharpe: 0.487 \rightarrow 0.628.
\]

Validation:

\[
Sharpe: 0.780 \rightarrow 0.555.
\]

Test:

\[
Sharpe: 0.942 \rightarrow 0.901.
\]

Momentum-based selection отдельных ETF не показывает устойчивого улучшения risk-adjusted performance.

### Decomposition conclusion

Strategy 0 лучше интерпретировать как defensive trend-allocation strategy.

Значительная часть её низкой волатильности объясняется меньшей средней risky exposure. Динамическое управление exposure может дополнительно уменьшать крупные просадки, однако этот эффект зависит от рыночного режима. Выбор отдельных ETF через momentum также не демонстрирует стабильного преимущества.

---

## 3. Robustness tests

Robustness tests не используются для повторной оптимизации Strategy 0.

Baseline остаётся неизменным:

- momentum lookback: 252 trading days;
- volatility window: 60 trading days;
- rebalance: weekly;
- transaction costs: 5 bps.

Цель robustness analysis — проверить, сохраняется ли общий характер стратегии при разумных изменениях исходных параметров.

### 3.1. Momentum lookback

Проверенные значения:

- 126 trading days;
- 189 trading days;
- 252 trading days — baseline;
- 378 trading days.

Все остальные параметры оставались неизменными.

Sanity check подтвердил, что вариант с lookback 252 полностью воспроизводит замороженный baseline Strategy 0.

#### Train

| Lookback | CAGR | Vol | Sharpe | MaxDD | Calmar | Cash | Turnover |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 126 | 4.22% | 7.60% | 0.582 | -12.69% | 0.333 | 36.23% | 5.229 |
| 189 | 5.00% | 7.24% | 0.710 | -8.54% | 0.585 | 35.70% | 4.472 |
| 252 | 4.60% | 7.63% | 0.628 | -8.54% | 0.539 | 33.01% | 3.675 |
| 378 | 4.25% | 7.71% | 0.579 | -11.28% | 0.377 | 31.90% | 2.623 |

#### Validation

| Lookback | CAGR | Vol | Sharpe | MaxDD | Calmar | Cash | Turnover |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 126 | 5.34% | 6.43% | 0.841 | -11.41% | 0.468 | 31.73% | 4.286 |
| 189 | 4.06% | 6.14% | 0.679 | -11.04% | 0.368 | 34.83% | 4.558 |
| 252 | 3.31% | 6.22% | 0.555 | -10.96% | 0.302 | 34.92% | 3.816 |
| 378 | 3.25% | 6.26% | 0.541 | -16.82% | 0.193 | 30.72% | 4.634 |

#### Test

| Lookback | CAGR | Vol | Sharpe | MaxDD | Calmar | Cash | Turnover |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 126 | 6.09% | 7.19% | 0.859 | -6.80% | 0.895 | 34.35% | 5.343 |
| 189 | 6.00% | 7.54% | 0.812 | -8.96% | 0.669 | 32.36% | 5.261 |
| 252 | 6.83% | 7.67% | 0.901 | -10.30% | 0.663 | 32.47% | 3.478 |
| 378 | 6.25% | 8.44% | 0.762 | -14.69% | 0.426 | 30.37% | 4.072 |

### Interpretation

Результаты не показывают существования одного momentum lookback, который доминирует на Train, Validation и Test.

На Train максимальный Sharpe среди проверенных вариантов имеет 189-дневный lookback.

На Validation наиболее высокий Sharpe имеет 126-дневный lookback.

На Test наиболее высокий Sharpe имеет замороженный baseline 252 дней, однако 126-дневный вариант имеет меньший Max Drawdown и более высокий Calmar.

Таким образом, Strategy 0 не выглядит критически зависимой от точного выбора 252-дневного momentum window в диапазоне примерно от 126 до 252 торговых дней.

Более короткие momentum windows приводят к более высокому turnover, что соответствует более частому изменению trend signals.

Вариант с 378-дневным lookback показывает более слабый результат по drawdown и Sharpe на Validation и Test, что может быть связано с более медленной реакцией на изменение рыночного режима. Этот результат рассматривается как наблюдение, а не как основание для оптимизации параметров.

Исходный 252-дневный momentum lookback остаётся неизменным.

---

## 4. Next robustness tests

Следующие проверки:

1. volatility window sensitivity;
2. rebalance-frequency sensitivity;
3. transaction-cost sensitivity;
4. leave-one-ETF-out analysis;
5. walk-forward analysis.

## 4. Walk-forward analysis

Для дополнительной проверки стабильности Strategy 0 был проведён fixed-parameter walk-forward analysis.

Параметры Strategy 0 не переоценивались и не оптимизировались. Использовались последовательные годовые out-of-sample блоки после пяти лет начальной истории:

* 2007-2011 → OOS 2012
* 2007-2012 → OOS 2013
* ...
* 2007-2024 → OOS 2025

Поскольку Strategy 0 не содержит обучаемой модели, данный тест не является walk-forward optimization. Его цель - оценить стабильность поведения стратегии по последовательным временным блокам.

Sanity check подтвердил, что stitched OOS returns в точности воспроизводят соответствующий участок замороженного backtest Strategy 0.

### Годовые OOS результаты

| Year | Return | Volatility | Sharpe | Max Drawdown | Average Cash |
| ---: | -----: | ---------: | -----: | -----------: | -----------: |
| 2012 |  3.80% |      4.56% |  0.847 |       -4.37% |       35.06% |
| 2013 |  9.81% |      6.72% |  1.426 |       -5.75% |       33.36% |
| 2014 |  0.05% |      5.59% |  0.036 |       -3.76% |       35.42% |
| 2015 |  0.79% |      5.02% |  0.181 |       -4.65% |       43.26% |
| 2016 | -0.77% |      4.05% | -0.171 |       -4.27% |       45.04% |
| 2017 | 16.11% |      5.25% |  2.882 |       -1.81% |       18.86% |
| 2018 | -6.48% |      8.98% | -0.703 |      -10.53% |       27.74% |
| 2019 |  9.88% |      2.97% |  3.193 |       -1.14% |       44.99% |
| 2020 | -0.62% |      7.72% | -0.041 |      -10.96% |       37.85% |
| 2021 | 10.88% |      9.58% |  1.126 |       -4.61% |       20.30% |
| 2022 | -5.80% |      5.21% | -1.124 |       -7.09% |       72.00% |
| 2023 |  5.31% |      6.24% |  0.867 |       -7.85% |       46.46% |
| 2024 |  9.83% |      8.47% |  1.150 |       -5.03% |       13.43% |
| 2025 | 15.09% |      8.03% |  1.805 |       -8.07% |       10.26% |

### Stitched OOS performance, 2012-2025

| Metric          |   Value |
| --------------- | ------: |
| CAGR            |   4.62% |
| Volatility      |   6.60% |
| Sharpe          |   0.718 |
| Max Drawdown    | -10.96% |
| Calmar          |   0.421 |
| Average Cash    |  34.58% |
| Annual Turnover |   3.860 |

Walk-forward results show substantial variation across market regimes.

Strategy 0 has several strong years, but also negative or nearly flat periods. The defensive mechanism is clearly regime-dependent: for example, average cash exposure reached 72% in 2022, while in other stress periods the strategy reduced risk less aggressively.

Because no parameters are re-estimated, the stitched walk-forward series is not an additional independent out-of-sample backtest. Its value is diagnostic: it shows that the behavior of Strategy 0 is not concentrated exclusively in one Train / Validation / Test split and highlights substantial year-to-year variation.

---

## 5. Final conclusion on Strategy 0

Strategy 0 can be characterized as a defensive systematic allocation strategy rather than a return-maximizing strategy.

The main findings are:

1. Strategy 0 produces substantially lower volatility and drawdowns than full-risk benchmarks, but also materially lower absolute returns.

2. A significant part of this defensive behavior is explained by lower average risky exposure and the resulting cash allocation.

3. Dynamic trend-based exposure management can reduce drawdowns in some market regimes, but does not consistently improve Sharpe ratio across Train, Validation and Test.

4. Momentum-based selection of individual ETFs also does not demonstrate a stable improvement in risk-adjusted returns.

5. The strategy is reasonably robust to changes in momentum lookback, volatility window, rebalance frequency and transaction-cost assumptions.

6. Leave-one-ETF-out tests show that the result is not driven entirely by one asset, although some assets, particularly IEF and GLD, materially affect the risk profile.

7. Sequential annual evaluation shows significant regime dependence: Strategy 0 performs strongly in some years and poorly in others.

Overall, Strategy 0 appears structurally and parametrically robust, but the current evidence does not establish robust alpha.

The Strategy 0 specification therefore remains frozen and is considered complete.

The next research stage is Strategy 1: a new strategy design based on the observed strengths and weaknesses of Strategy 0 rather than post-hoc optimization of its parameters.
