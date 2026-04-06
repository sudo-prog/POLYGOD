import { useState } from 'react';
import { Trophy, User, RefreshCw } from 'lucide-react';
import { useMarketStore } from '../stores/marketStore';
import { formatCurrency, formatAddress } from '../utils/formatters';

export function TopHolders() {
  const { selectedMarket } = useMarketStore();
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Mock data for now
  const mockHolders = [
    { address: '0x1234567890abcdef1234567890abcdef12345678', amount: 150000, position: 'YES' },
    { address: '0xabcdef1234567890abcdef1234567890abcdef12', amount: 120000, position: 'NO' },
    { address: '0x7890abcdef1234567890abcdef1234567890abcd', amount: 98000, position: 'YES' },
    { address: '0x4567890abcdef1234567890abcdef1234567890ab', amount: 85000, position: 'NO' },
    { address: '0xcdef1234567890abcdef1234567890abcdef12345', amount: 72000, position: 'YES' },
  ];

  const handleRefresh = async () => {
    setIsRefreshing(true);
    // Simulate API call
    setTimeout(() => setIsRefreshing(false), 1000);
  };

  if (!selectedMarket) {
    return (
      <div className="ios-inner p-8 text-center">
        <Trophy className="w-12 h-12 text-surface-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">No Market Selected</h3>
        <p className="text-surface-400">Select a market to view top holders</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white flex items-center gap-2">
          <Trophy className="w-5 h-5 text-amber-400" />
          Top Holders
        </h3>
        <button onClick={handleRefresh} className="ios-icon-btn" disabled={isRefreshing}>
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Holders Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {mockHolders.map((holder, index) => (
          <div key={index} className="ios-card-sm p-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-600 rounded-full flex items-center justify-center text-white font-bold text-sm">
                {index + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <User className="w-4 h-4 text-surface-400" />
                  <span className="text-sm font-medium text-white truncate">
                    {formatAddress(holder.address)}
                  </span>
                </div>
                <div
                  className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
                    holder.position === 'YES'
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-red-500/20 text-red-400'
                  }`}
                >
                  {holder.position}
                </div>
              </div>
            </div>

            <div className="text-right">
              <div className="text-lg font-bold text-white">{formatCurrency(holder.amount)}</div>
              <div className="text-xs text-surface-400">Position Size</div>
            </div>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="ios-card-sm p-4">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-lg font-bold text-emerald-400">
              {mockHolders.filter((h) => h.position === 'YES').length}
            </div>
            <div className="text-xs text-surface-400">YES Positions</div>
          </div>
          <div>
            <div className="text-lg font-bold text-red-400">
              {mockHolders.filter((h) => h.position === 'NO').length}
            </div>
            <div className="text-xs text-surface-400">NO Positions</div>
          </div>
          <div>
            <div className="text-lg font-bold text-white">
              {formatCurrency(mockHolders.reduce((sum, h) => sum + h.amount, 0))}
            </div>
            <div className="text-xs text-surface-400">Total Volume</div>
          </div>
        </div>
      </div>
    </div>
  );
}
