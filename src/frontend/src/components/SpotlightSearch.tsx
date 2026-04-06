import { useState, useEffect, useRef } from 'react';
import { Search, X, TrendingUp, MessageSquare, Wallet } from 'lucide-react';
import { useMarkets } from '../hooks/useMarkets';
import { useNews } from '../hooks/useNews';
import { useWhales } from '../hooks/useWhales';
import { useMarketStore } from '../stores/marketStore';

interface SpotlightSearchProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SpotlightSearch({ isOpen, onClose }: SpotlightSearchProps) {
  const { data: markets } = useMarkets();
  const { data: news } = useNews(null);
  const { data: whales } = useWhales(null);
  const { setSelectedMarket } = useMarketStore();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);

  // Flatten all search results
  const searchResults = [
    ...(markets?.markets || []).map((market: any) => ({
      type: 'market' as const,
      icon: <TrendingUp className="w-4 h-4 text-emerald-400" />,
      title: market.title,
      subtitle: `${market.yes_percentage.toFixed(1)}% Yes • $${market.volume_24h.toLocaleString()}`,
      action: () => {
        setSelectedMarket(market);
        onClose();
      },
    })),
    ...(news?.articles || []).map((article: any) => ({
      type: 'news' as const,
      icon: <MessageSquare className="w-4 h-4 text-blue-400" />,
      title: article.title,
      subtitle: article.source || 'Unknown',
      action: () => {
        window.open(article.url, '_blank');
        onClose();
      },
    })),
    ...(whales || []).map((whale) => ({
      type: 'whale' as const,
      icon: <Wallet className="w-4 h-4 text-purple-400" />,
      title: `$${whale.volume.toLocaleString()} ${whale.side.toUpperCase()}`,
      subtitle: whale.timestamp,
      action: () => onClose(),
    })),
  ].filter(
    (item) =>
      item.title.toLowerCase().includes(query.toLowerCase()) ||
      item.subtitle.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
      setQuery('');
      setSelectedIndex(-1);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      switch (e.key) {
        case 'Escape':
          onClose();
          break;
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((prev) => Math.min(prev + 1, searchResults.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((prev) => Math.max(prev - 1, -1));
          break;
        case 'Enter':
          e.preventDefault();
          if (selectedIndex >= 0 && searchResults[selectedIndex]) {
            searchResults[selectedIndex].action();
          }
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, selectedIndex, searchResults, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-600 bg-black/50 backdrop-blur-sm flex items-start justify-center pt-20">
      <div className="w-full max-w-2xl mx-4">
        {/* Search Input */}
        <div className="ios-card p-4 mb-4">
          <div className="flex items-center gap-3">
            <Search className="w-5 h-5 text-surface-400" />
            <input
              ref={inputRef}
              type="text"
              placeholder="Search markets, news, and whale activity..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(-1);
              }}
              className="flex-1 bg-transparent border-none outline-none text-white placeholder-surface-400 text-lg"
            />
            <button onClick={onClose} className="ios-icon-btn">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Results */}
        {searchResults.length > 0 && (
          <div className="ios-card max-h-96 overflow-y-auto">
            <div className="divide-y divide-white/5">
              {searchResults.slice(0, 20).map((result, index) => (
                <button
                  key={index}
                  onClick={result.action}
                  className={`w-full px-4 py-3 text-left hover:bg-surface-800/50 transition-colors flex items-center gap-3 ${
                    index === selectedIndex ? 'bg-surface-800/70' : ''
                  }`}
                >
                  {result.icon}
                  <div className="flex-1 min-w-0">
                    <div className="text-white truncate">{result.title}</div>
                    <div className="text-surface-400 text-sm truncate">{result.subtitle}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {query && searchResults.length === 0 && (
          <div className="ios-card p-8 text-center">
            <Search className="w-12 h-12 text-surface-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">No results found</h3>
            <p className="text-surface-400">Try adjusting your search terms</p>
          </div>
        )}
      </div>
    </div>
  );
}
