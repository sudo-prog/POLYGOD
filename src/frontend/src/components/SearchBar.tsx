import { useState } from 'react';
import { Search, X } from 'lucide-react';
import { useMarketStore } from '../stores/marketStore';
import { useMarkets } from '../hooks/useMarkets';

export function SearchBar() {
  const { setSelectedMarket } = useMarketStore();
  const { data: marketsResponse } = useMarkets();
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  const filteredMarkets =
    marketsResponse?.markets
      ?.filter(
        (market: any) =>
          market.title.toLowerCase().includes(query.toLowerCase()) ||
          market.slug.toLowerCase().includes(query.toLowerCase())
      )
      .slice(0, 5) || [];

  const handleSelect = (market: any) => {
    setSelectedMarket(market);
    setQuery('');
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <div className="ios-input flex items-center gap-2">
        <Search className="w-4 h-4 text-surface-400" />
        <input
          type="text"
          placeholder="Search markets..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(e.target.value.length > 0);
          }}
          onFocus={() => setIsOpen(query.length > 0)}
          onBlur={() => setTimeout(() => setIsOpen(false), 200)}
          className="flex-1 bg-transparent border-none outline-none text-white placeholder-surface-400"
        />
        {query && (
          <button
            onClick={() => {
              setQuery('');
              setIsOpen(false);
            }}
            className="text-surface-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Search Results */}
      {isOpen && filteredMarkets.length > 0 && (
        <div className="absolute top-full left-0 right-0 z-50 mt-2 bg-surface-900/95 border border-white/10 rounded-2xl backdrop-blur-xl max-h-64 overflow-y-auto">
          {filteredMarkets.map((market: any) => (
            <button
              key={market.id}
              onClick={() => handleSelect(market)}
              className="w-full px-4 py-3 text-left hover:bg-surface-800/50 transition-colors first:rounded-t-2xl last:rounded-b-2xl"
            >
              <div className="font-medium text-white truncate">{market.title}</div>
              <div className="text-sm text-surface-400">
                {market.yes_percentage.toFixed(1)}% Yes • ${market.volume_24h.toLocaleString()}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
