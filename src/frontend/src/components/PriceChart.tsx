import { useState } from 'react';
import { BarChart3, TrendingUp, TrendingDown } from 'lucide-react';
import { useMarketStore } from '../stores/marketStore';
import { usePriceHistory } from '../hooks/usePriceHistory';
import { formatCurrency } from '../utils/formatters';

function PriceChart() {
  const { selectedMarket } = useMarketStore();
  const [timeframe, setTimeframe] = useState<'24H' | '7D' | '1M' | 'ALL'>('24H');
  const { isLoading } = usePriceHistory(selectedMarket?.id || null, timeframe.toLowerCase());

  if (!selectedMarket) {
    return (
      <div className="ios-inner p-8 text-center">
        <BarChart3 className="w-12 h-12 text-surface-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">No Market Selected</h3>
        <p className="text-surface-400">Select a market from the sidebar to view price data</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-64 w-full rounded-lg"></div>
        <div className="flex justify-center gap-2">
          <div className="skeleton h-8 w-16 rounded-full"></div>
          <div className="skeleton h-8 w-16 rounded-full"></div>
          <div className="skeleton h-8 w-16 rounded-full"></div>
          <div className="skeleton h-8 w-16 rounded-full"></div>
        </div>
      </div>
    );
  }

  // Get yes percentage with fallbacks (similar to App.tsx logic)
  const yesPercentage =
    (selectedMarket.yes_percentage ?? 0) ||
    (selectedMarket.yes_price ? selectedMarket.yes_price * 100 : 0) ||
    (selectedMarket.outcomes?.[0]?.price ? selectedMarket.outcomes[0].price * 100 : 0);

  // Mock data for now since recharts isn't available
  const mockData = [
    { time: '00:00', price: yesPercentage - 5 },
    { time: '04:00', price: yesPercentage - 3 },
    { time: '08:00', price: yesPercentage - 1 },
    { time: '12:00', price: yesPercentage + 2 },
    { time: '16:00', price: yesPercentage + 4 },
    { time: '20:00', price: yesPercentage + 1 },
    { time: 'Now', price: yesPercentage },
  ];

  const latestPrice = mockData[mockData.length - 1]?.price ?? yesPercentage;
  const previousPrice = mockData[mockData.length - 2]?.price ?? yesPercentage;
  const priceChange = latestPrice - previousPrice;
  const priceChangePercent = previousPrice !== 0 ? (priceChange / previousPrice) * 100 : 0;

  return (
    <div className="space-y-4">
      {/* Price Display */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold text-white">{latestPrice.toFixed(1)}%</span>
            <div className="flex items-center gap-1">
              {priceChange >= 0 ? (
                <TrendingUp className="w-4 h-4 text-emerald-400" />
              ) : (
                <TrendingDown className="w-4 h-4 text-red-400" />
              )}
              <span
                className={`text-sm font-medium ${
                  priceChange >= 0 ? 'text-emerald-400' : 'text-red-400'
                }`}
              >
                {priceChange >= 0 ? '+' : ''}
                {priceChange.toFixed(1)}% ({priceChangePercent >= 0 ? '+' : ''}
                {priceChangePercent.toFixed(2)}%)
              </span>
            </div>
          </div>
          <p className="text-sm text-surface-400">Probability of Yes outcome</p>
        </div>

        {/* Timeframe Selector */}
        <div className="ios-segmented">
          <button
            onClick={() => setTimeframe('24H')}
            className={`ios-seg-item ${timeframe === '24H' ? 'active' : ''}`}
          >
            24H
          </button>
          <button
            onClick={() => setTimeframe('7D')}
            className={`ios-seg-item ${timeframe === '7D' ? 'active' : ''}`}
          >
            7D
          </button>
          <button
            onClick={() => setTimeframe('1M')}
            className={`ios-seg-item ${timeframe === '1M' ? 'active' : ''}`}
          >
            1M
          </button>
          <button
            onClick={() => setTimeframe('ALL')}
            className={`ios-seg-item ${timeframe === 'ALL' ? 'active' : ''}`}
          >
            ALL
          </button>
        </div>
      </div>

      {/* Chart Placeholder */}
      <div className="ios-inner p-4">
        <div className="h-64 bg-gradient-to-br from-surface-800 to-surface-900 rounded-lg flex items-center justify-center">
          <div className="text-center">
            <BarChart3 className="w-12 h-12 text-surface-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">Chart Coming Soon</h3>
            <p className="text-surface-400 text-sm">
              Advanced trading charts will be available with TradingView integration
            </p>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="ios-inner p-3 text-center">
          <div className="text-lg font-bold text-white">
            {formatCurrency(selectedMarket.volume_24h)}
          </div>
          <div className="text-xs text-surface-400">24h Volume</div>
        </div>
        <div className="ios-inner p-3 text-center">
          <div className="text-lg font-bold text-white">
            {selectedMarket.is_active ? 'Active' : 'Inactive'}
          </div>
          <div className="text-xs text-surface-400">Status</div>
        </div>
        <div className="ios-inner p-3 text-center">
          <div className="text-lg font-bold text-emerald-400">{yesPercentage.toFixed(1)}%</div>
          <div className="text-xs text-surface-400">Yes Probability</div>
        </div>
        <div className="ios-inner p-3 text-center">
          <div className="text-lg font-bold text-red-400">{(100 - yesPercentage).toFixed(1)}%</div>
          <div className="text-xs text-surface-400">No Probability</div>
        </div>
      </div>
    </div>
  );
}

export { PriceChart };
export default PriceChart;
