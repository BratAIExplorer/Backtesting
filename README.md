# Centralized Quant Lab (Backtesting)

This directory serves as the centralized quantitative research and backtesting environment for all Antigravity trading projects (e.g., `FinFlow`, `TradingBot`, `Deepaks-Bots`). 

By unifying research scripts here, we ensure that our data caching, statistical harness, and backtesting methodologies remain consistent across all applications, preventing duplicate work and scattered findings.

## Structure

*   **`harness/`**: The core quantitative engine.
    *   `data.py`: Centralized caching layer for Yahoo Finance daily bars, earnings dates/surprises, and GDELT historical news.
    *   `stats.py`: Statistical validation tools (HAC t-stats, deflated Sharpe ratios, block bootstrapping).
    *   `walkforward.py`: Purged and embargoed K-fold cross-validation.
    *   `signals.py`: Event-building and calendar-time portfolio logic.
*   **`strategies/`**: The actual trading strategies being tested, grouped by category.
    *   `pead/`: Post-Earnings Announcement Drift and News Sentiment models (migrated from `TradingBot`).
    *   `trend/`: Lagging indicator tests, 200-DMA filters, and Piotroski screens (migrated from `FinFlow`).
*   **`tests/`**: Unit tests for the strategies and harness.
*   **`FINDINGS.md`**: The single source of truth for all backtest results and strategy verdicts.

## Usage

Scripts should be executed as modules from the root of this `Backtesting` directory. For example:

```bash
# Run the PEAD + News Sentiment study
python -m strategies.pead.run_news

# Run the RSI/MACD trend backtests
python -m strategies.trend.backtest_trend
```

*Note: Crypto backtesting (`Kyro_Crypto_WealthGenerator`) remains intentionally isolated in its own repository due to the unique mechanics of 24/7 markets and funding rates.*
