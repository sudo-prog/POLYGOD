import { useState, useEffect, useRef } from 'react';
import { Zap, RefreshCw, Clock, TrendingUp, TrendingDown, Radio } from 'lucide-react';
import { useLiveTradesWS } from '../../hooks/useLiveTradesWS';
import { formatCurrency } from '../utils/formatters';

export function LiveTradesFeed() {
  const { isConnected, trades, lastError, clearTrades } = useLiveTradesWS();
  const [filter, setFilter] = useState<'all' | 'buy' | 'sell'>('all');
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const prevTradesLength = useRef(0);

  // Highlight new trades when they arrive
  useEffect(() => {
    if (trades.length > prevTradesLength.current && trades.length > 0) {
      const latestTrade = trades[0];
      setHighlightedId(latestTrade.fill_id);

      // Scroll to top when new trade arrives
      if (containerRef.current) {
        containerRef.current.scrollTop = 0;
      }

      // Remove highlight after animation
      setTimeout(() => {
        setHighlightedId(null);
      }, 2000);
    }
    prevTradesLength.current = trades.length;
  }, [trades]);

  const formatTime = (isoString: string | undefined): string => {
    if (!isoString) return '--:--:--';
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const filteredTrades = trades.filter((trade) => {
    if (filter === 'all') return true;
    return trade.side.toLowerCase() === filter;
  });

  // Calculate summary stats
  const buyVolume = trades.filter((t) => t.side === 'BUY').reduce((sum, t) => sum + t.value_usd, 0);
  const sellVolume = trades
    .filter((t) => t.side === 'SELL')
    .reduce((sum, t) => sum + t.value_usd, 0);
  const totalVolume = buyVolume + sellVolume;
  const buyPercent = totalVolume > 0 ? (buyVolume / totalVolume) * 100 : 50;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white flex items-center gap-2">
          <Radio
            className={`w-5 h-5 ${
              isConnected ? 'text-cyan-400 animate-pulse' : 'text-surface-400'
            }`}
          />
          Live Trades
          {isConnected && (
            <span className="text-xs bg-cyan-500/20 text-cyan-400 px-2 py-0.5 rounded-full">
              LIVE
            </span>
          )}
        </h3>
        <button onClick={clearTrades} className="ios-icon-btn">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Connection Status / Error */}
      {lastError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-400">
          {lastError}
        </div>
      )}

      {/* Stats Bar */}
      {trades.length > 0 && (
        <div className="ios-inner p-3 flex items-center justify-between">
          <div className="text-xs text-surface-400">
            <span className="text-emerald-400">{trades.length} trades</span>
            <span className="mx-2">•</span>
            <span>Total: {formatCurrency(totalVolume)}</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-emerald-400">{buyPercent.toFixed(0)}%</span>
            <div className="w-16 h-2 bg-surface-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-red-500"
                style={{ width: '100%' }}
              />
              <div
                className="h-full bg-emerald-500 absolute top-0 left-0"
                style={{ width: `${buyPercent}%`, height: '100%' }}
              />
            </div>
            <span className="text-red-400">{100 - buyPercent}%</span>
          </div>
        </div>
      )}

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

      {/* Live Trades Feed */}
      <div ref={containerRef} className="space-y-2 max-h-[400px] overflow-y-auto">
        {filteredTrades && filteredTrades.length > 0 ? (
          filteredTrades.slice(0, 30).map((trade, index) => {
            const isBuy = trade.side === 'BUY';
            const isHighlighted = highlightedId === trade.fill_id;
            const isLarge = trade.value_usd >= 5000;

            return (
              <div
                key={trade.fill_id || index}
                className={`ios-inner p-4 transition-all duration-500 ${
                  isHighlighted
                    ? 'bg-cyan-500/20 border-cyan-400/50 scale-[1.02]'
                    : isLarge
                      ? 'border-amber-400/30'
                      : ''
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {isBuy ? (
                      <TrendingUp className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-red-400" />
                    )}
                    <span className={`font-medium ${isBuy ? 'text-emerald-400' : 'text-red-400'}`}>
                      {trade.side.toUpperCase()}
                    </span>
                    {isLarge && (
                      <span className="text-[10px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded">
                        WHALE
                      </span>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-mono text-white">
                      {formatCurrency(trade.value_usd)}
                    </div>
                    <div className="text-xs text-surface-400 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatTime(trade.timestamp)}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs text-surface-500">
                  <span>
                    {trade.size.toLocaleString()} @ {trade.price.toFixed(2)}
                  </span>
                  <span className="font-mono text-surface-600">
                    {trade.market_id.slice(0, 12)}...
                  </span>
                </div>
              </div>
            );
          })
        ) : (
          <div className="ios-inner p-8 text-center">
            <Zap className="w-12 h-12 text-surface-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">Waiting for Trades</h3>
            <p className="text-surface-400 text-sm">
              {isConnected ? 'Listening for live trades...' : 'Connecting to trade feed...'}
            </p>
          </div>
        )}
      </div>

      {/* Auto-scroll hint */}
      {trades.length > 0 && (
        <div className="text-xs text-center text-surface-500">Newest trades appear at top</div>
      )}
    </div>
  );
}
