---
name: backtest
description: Run backtesting for trading strategies using historical data. Use when users ask to backtest a strategy, analyze trading performance, optimize strategy parameters, or integrate with poly_data for historical market data.
---

# Backtest Skill

An expert agent for running backtesting simulations on trading strategies with historical data.

## Capabilities

- **Strategy Backtesting**: Test trading strategies against historical price data
- **Performance Analysis**: Calculate returns, Sharpe ratio, max drawdown, win rate
- **Parameter Optimization**: Find optimal strategy parameters through grid/random search
- **poly_data Integration**: Fetch historical market data from poly_data API
- **Multi-Timeframe Analysis**: Run backtests across different timeframes (1m, 5m, 1h, 1d)
- **Portfolio Simulation**: Simulate portfolio with position sizing and risk management

## Workflow

### Step 1: Define Strategy & Parameters

1. Identify the trading strategy to backtest
2. Define entry/exit conditions
3. Set parameters (timeframe, initial capital, position size)

### Step 2: Fetch Historical Data

Use poly_data integration for market data:
- Fetch OHLCV data for specified symbols and timeframes
- Handle missing data and backfill gaps
- Normalize data format for backtesting engine

### Step 3: Run Backtest

1. Initialize backtesting engine with parameters
2. Iterate through historical data points
3. Apply strategy signals to generate trades
4. Track positions, P&L, and equity curve

### Step 4: Analyze Results

| Metric | Description |
|--------|-------------|
| Total Return | Overall percentage return |
| Sharpe Ratio | Risk-adjusted return |
| Max Drawdown | Largest peak-to-trough decline |
| Win Rate | Percentage of profitable trades |
| Avg Win/Loss | Average profit/loss per trade |
| Profit Factor | Gross profit / gross loss |

### Step 5: Optimize (Optional)

1. Define parameter ranges for optimization
2. Run grid search or Bayesian optimization
3. Select best parameters based on target metric

## poly_data Integration

```python
# Fetch historical data from poly_data
from poly_data import get_bars

# Get daily bars for AAPL
bars = get_bars(
    symbol="AAPL",
    timeframe="1D",
    start_date="2020-01-01",
    end_date="2024-12-31"
)
```

## Output Format

Provide:
1. Summary of strategy and parameters used
2. Data source and timeframe
3. Performance metrics table
4. Equity curve visualization
5. Trade log (optional)
6. Optimization results (if applicable)
