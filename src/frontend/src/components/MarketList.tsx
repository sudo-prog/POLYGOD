import { useState } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useMarkets } from '../hooks/useMarkets';
import { useMarketStore } from '../stores/marketStore';
import { formatCurrency, formatPercent } from '../utils/formatters';

export function MarketList() {
  const { data: marketsResponse, isLoading } = useMarkets();
  const { selectedMarket, setSelectedMarket } = useMarketStore();
  const [searchQuery, setSearchQuery] = useState('');

  const filteredMarkets =
    marketsResponse?.markets?.filter(
      (market: any) =>
        market.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        market.slug.toLowerCase().includes(searchQuery.toLowerCase())
    ) || [];

  const getChangeIcon = (change: number) => {
    if (change > 0) return <TrendingUp className="w-3 h-3 text-emerald-400" />;
    if (change < 0) return <TrendingDown className="w-3 h-3 text-red-400" />;
    return <Minus className="w-3 h-3 text-surface-400" />;
  };

  const getChangeColor = (change: number) => {
    if (change > 0) return 'text-emerald-400';
    if (change < 0) return 'text-red-400';
    return 'text-surface-400';
  };

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="ios-inner p-3">
            <div className="skeleton h-4 w-3/4 mb-2"></div>
            <div className="skeleton h-3 w-1/2"></div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Search */}
      <div className="ios-input mb-4">
        <input
          type="text"
          placeholder="Search markets..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-transparent border-none outline-none text-white placeholder-surface-400"
        />
      </div>

      {/* Market List */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {filteredMarkets.slice(0, 50).map((market: any) => (
          <div
            key={market.id}
            onClick={() => setSelectedMarket(market)}
            className={`ios-inner p-3 cursor-pointer transition-all hover:bg-surface-800/50 ${
              selectedMarket?.id === market.id ? 'bg-primary-500/10 border-primary-500/30' : ''
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-white text-sm truncate mb-1">{market.title}</h3>
                <div className="flex items-center gap-3 text-xs text-surface-300">
                  <span className="text-emerald-400 font-mono">
                    {market.yes_percentage.toFixed(1)}% Yes
                  </span>
                  <span>•</span>
                  <span>{formatCurrency(market.volume_24h)}</span>
                </div>
              </div>

              <div className="flex flex-col items-end gap-1">
                <div className="flex items-center gap-1">
                  {getChangeIcon(market.change_24h)}
                  <span className={`text-xs font-medium ${getChangeColor(market.change_24h)}`}>
                    {formatPercent(Math.abs(market.change_24h))}
                  </span>
                </div>
                <div className="text-xs text-surface-400">24h</div>
              </div>
            </div>

            {/* Probability Bar */}
            <div className="mt-2 w-full bg-surface-800 rounded-full h-1.5 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-300"
                style={{ width: `${market.yes_percentage}%` }}
              />
            </div>
          </div>
        ))}

        {filteredMarkets.length === 0 && !isLoading && (
          <div className="ios-inner p-4 text-center">
            <p className="text-surface-400 text-sm">No markets found</p>
          </div>
        )}
      </div>
    </div>
  );
}
