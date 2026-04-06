import { Activity, TrendingUp } from 'lucide-react';
import { useMarketStore } from '../stores/marketStore';
import { formatCurrency } from '../utils/formatters';

export function PriceMovement() {
  const { selectedMarket } = useMarketStore();

  // Mock analysis data
  const analysis = {
    volatility: 'Medium',
    trend: 'Bullish',
    support: 45.2,
    resistance: 68.9,
    volume24h: 1250000,
    change24h: 3.2,
  };

  if (!selectedMarket) {
    return (
      <div className="ios-inner p-8 text-center">
        <Activity className="w-12 h-12 text-surface-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">No Market Selected</h3>
        <p className="text-surface-400">Select a market to view price analysis</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <h3 className="font-semibold text-white flex items-center gap-2">
        <Activity className="w-5 h-5 text-purple-400" />
        Price Analysis
      </h3>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="ios-card-sm p-4 text-center">
          <div className="text-lg font-bold text-white mb-1">{analysis.volatility}</div>
          <div className="text-xs text-surface-400">Volatility</div>
        </div>
        <div className="ios-card-sm p-4 text-center">
          <div className="flex items-center justify-center gap-1 mb-1">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <span className="text-lg font-bold text-emerald-400">{analysis.trend}</span>
          </div>
          <div className="text-xs text-surface-400">Trend</div>
        </div>
        <div className="ios-card-sm p-4 text-center">
          <div className="text-lg font-bold text-emerald-400 mb-1">
            {analysis.support.toFixed(1)}%
          </div>
          <div className="text-xs text-surface-400">Support</div>
        </div>
        <div className="ios-card-sm p-4 text-center">
          <div className="text-lg font-bold text-red-400 mb-1">
            {analysis.resistance.toFixed(1)}%
          </div>
          <div className="text-xs text-surface-400">Resistance</div>
        </div>
      </div>

      {/* Technical Signals */}
      <div className="ios-card-sm p-4">
        <h4 className="font-medium text-white mb-3">Technical Signals</h4>
        <div className="space-y-3">
          <div className="flex items-center justify-between p-2 bg-surface-800/50 rounded-lg">
            <span className="text-sm text-white">RSI (14)</span>
            <span className="text-sm font-mono text-emerald-400">62.4</span>
          </div>
          <div className="flex items-center justify-between p-2 bg-surface-800/50 rounded-lg">
            <span className="text-sm text-white">MACD</span>
            <span className="text-sm font-mono text-emerald-400">+0.8</span>
          </div>
          <div className="flex items-center justify-between p-2 bg-surface-800/50 rounded-lg">
            <span className="text-sm text-white">Moving Average (50)</span>
            <span className="text-sm font-mono text-white">
              {selectedMarket.yes_percentage.toFixed(1)}%
            </span>
          </div>
        </div>
      </div>

      {/* Volume Analysis */}
      <div className="ios-card-sm p-4">
        <h4 className="font-medium text-white mb-3">Volume Analysis</h4>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-surface-400">24h Volume</span>
            <span className="text-sm font-medium text-white">
              {formatCurrency(analysis.volume24h)}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-surface-400">Price Change</span>
            <span className="text-sm font-medium text-emerald-400">+{analysis.change24h}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
