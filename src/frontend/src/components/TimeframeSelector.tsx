import { useMarketStore } from '../stores/marketStore';

export function TimeframeSelector() {
  const { selectedTimeframe, setSelectedTimeframe } = useMarketStore();

  return (
    <div className="ios-segmented">
      <button
        onClick={() => setSelectedTimeframe('24H')}
        className={`ios-seg-item ${selectedTimeframe === '24H' ? 'active' : ''}`}
      >
        24H
      </button>
      <button
        onClick={() => setSelectedTimeframe('7D')}
        className={`ios-seg-item ${selectedTimeframe === '7D' ? 'active' : ''}`}
      >
        7D
      </button>
      <button
        onClick={() => setSelectedTimeframe('1M')}
        className={`ios-seg-item ${selectedTimeframe === '1M' ? 'active' : ''}`}
      >
        1M
      </button>
      <button
        onClick={() => setSelectedTimeframe('ALL')}
        className={`ios-seg-item ${selectedTimeframe === 'ALL' ? 'active' : ''}`}
      >
        ALL
      </button>
    </div>
  );
}
