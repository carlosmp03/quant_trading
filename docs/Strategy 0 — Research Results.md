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