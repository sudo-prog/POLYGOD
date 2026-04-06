import { useState } from 'react';
import { Wallet, RefreshCw, Clock, TrendingUp, TrendingDown } from 'lucide-react';
import { useWhales } from '../hooks/useWhales';
import { useMarketStore } from '../stores/marketStore';
import { formatCurrency } from '../utils/formatters';

export function WhaleList() {
  const { selectedMarket } = useMarketStore();
  const { data: whales, isLoading, refetch } = useWhales(selectedMarket?.id || null);
  const [filter, setFilter] = useState<'all' | 'buy' | 'sell'>('all');

  const formatTimeAgo = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMinutes / 60);

    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMinutes > 0) return `${diffMinutes}m ago`;
    return 'Just now';
  };

  const filteredWhales =
    whales?.filter((whale) => {
      if (filter === 'all') return true;
      return whale.side.toLowerCase() === filter;
    }) || [];

  if (!selectedMarket) {
    return (
      <div className="ios-inner p-8 text-center">
        <Wallet className="w-12 h-12 text-surface-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">No Market Selected</h3>
        <p className="text-surface-400">Select a market to view large orders</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-8 w-32 mb-4"></div>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="ios-inner p-4">
            <div className="skeleton h-4 w-1/2 mb-2"></div>
            <div className="skeleton h-3 w-3/4"></div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white flex items-center gap-2">
          <Wallet className="w-5 h-5 text-emerald-400" />
          Recent Large Orders
        </h3>
        <button onClick={() => refetch()} className="ios-icon-btn" disabled={isLoading}>
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <button
          onClick={() => setFilter('all')}
          className={`ios-btn ${
            filter === 'all' ? 'bg-primary-500/20 border-primary-500/40 text-primary-400' : ''
          }`}
        >
          All
        </button>
        <button
          onClick={() => setFilter('buy')}
          className={`ios-btn ${
            filter === 'buy' ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400' : ''
          }`}
        >
          Buy
        </button>
        <button
          onClick={() => setFilter('sell')}
          className={`ios-btn ${
            filter === 'sell' ? 'bg-red-500/20 border-red-500/40 text-red-400' : ''
          }`}
        >
          Sell
        </button>
      </div>

      {/* Whale Trades */}
      <div className="space-y-3">
        {filteredWhales && filteredWhales.length > 0 ? (
          filteredWhales.slice(0, 20).map((trade, index) => (
            <div key={index} className="ios-inner p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {trade.side === 'BUY' ? (
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-red-400" />
                  )}
                  <span
                    className={`font-medium ${
                      trade.side === 'BUY' ? 'text-emerald-400' : 'text-red-400'
                    }`}
                  >
                    {trade.side.toUpperCase()}
                  </span>
                </div>
                <div className="text-right">
                  <div className="text-sm font-mono text-white">{formatCurrency(trade.volume)}</div>
                  <div className="text-xs text-surface-400 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatTimeAgo(trade.timestamp)}
                  </div>
                </div>
              </div>

              <div className="text-xs text-surface-400">
                Order size indicates significant market interest
              </div>
            </div>
          ))
        ) : (
          <div className="ios-inner p-8 text-center">
            <Wallet className="w-12 h-12 text-surface-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">No Large Orders</h3>
            <p className="text-surface-400">No significant orders detected for this market</p>
          </div>
        )}
      </div>
    </div>
  );
}
