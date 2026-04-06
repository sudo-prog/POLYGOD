import { ExternalLink, Newspaper, RefreshCw, Clock } from 'lucide-react';
import { useNews } from '../hooks/useNews';
import { useMarketStore } from '../stores/marketStore';

export function NewsFeed() {
  const { selectedMarket } = useMarketStore();
  const { data: news, isLoading, refetch } = useNews(selectedMarket?.id || null);

  const formatTimeAgo = (dateString: string | null | undefined): string => {
    if (!dateString) return '';

    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    return 'Just now';
  };

  if (!selectedMarket) {
    return (
      <div className="ios-inner p-8 text-center">
        <Newspaper className="w-12 h-12 text-surface-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">No Market Selected</h3>
        <p className="text-surface-400">Select a market to view related news</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="ios-inner p-4">
            <div className="skeleton h-4 w-3/4 mb-2"></div>
            <div className="skeleton h-3 w-1/2 mb-2"></div>
            <div className="skeleton h-3 w-1/4"></div>
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
          <Newspaper className="w-5 h-5 text-primary-400" />
          Related News
        </h3>
        <button onClick={() => refetch()} className="ios-icon-btn" disabled={isLoading}>
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* News Articles */}
      <div className="space-y-3">
        {news?.articles && news.articles.length > 0 ? (
          news.articles.slice(0, 10).map((article: any, index: number) => (
            <a
              key={index}
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ios-inner p-4 block hover:bg-surface-800/50 transition-all group"
            >
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <h4 className="font-medium text-white group-hover:text-primary-300 transition-colors line-clamp-2 mb-1">
                    {article.title}
                  </h4>
                  <div className="flex items-center gap-3 text-xs text-surface-400">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatTimeAgo(article.published_at)}
                    </span>
                    {article.source && (
                      <>
                        <span>•</span>
                        <span>{article.source}</span>
                      </>
                    )}
                  </div>
                </div>
                <ExternalLink className="w-4 h-4 text-surface-400 group-hover:text-primary-300 transition-colors flex-shrink-0 mt-1" />
              </div>

              {/* Sentiment Indicator */}
              {article.sentiment_score !== null && article.sentiment_score !== undefined && (
                <div className="mt-2 flex items-center gap-2">
                  <div
                    className={`px-2 py-1 rounded-full text-xs font-medium ${
                      article.sentiment_score > 0.1
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : article.sentiment_score < -0.1
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-surface-500/20 text-surface-400'
                    }`}
                  >
                    {article.sentiment_score > 0.1
                      ? 'Bullish'
                      : article.sentiment_score < -0.1
                        ? 'Bearish'
                        : 'Neutral'}
                  </div>
                </div>
              )}
            </a>
          ))
        ) : (
          <div className="ios-inner p-8 text-center">
            <Newspaper className="w-12 h-12 text-surface-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">No News Available</h3>
            <p className="text-surface-400">No recent news articles found for this market</p>
          </div>
        )}
      </div>
    </div>
  );
}
