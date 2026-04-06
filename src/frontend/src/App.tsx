import { useState, useEffect } from 'react';
import {
  TrendingUp,
  Newspaper,
  BarChart3,
  Wallet,
  Trophy,
  Activity,
  MessageSquare,
  Zap,
  Brain,
  DollarSign,
  Bell,
} from 'lucide-react';
import { MarketList } from './components/MarketList';
import { TickerBanner } from './components/TickerBanner';
import { useMarkets } from './hooks/useMarkets';
import PriceChart from './components/PriceChart';
import { NewsFeed } from './components/NewsFeed';
import { WhaleList } from './components/WhaleList';
import { TopHolders } from './components/TopHolders';
import { PriceMovement } from './components/PriceMovement';
import { TimeframeSelector } from './components/TimeframeSelector';
import { SearchBar } from './components/SearchBar';
import { DebateFloor } from './components/DebateFloor';
import { UserDashboard } from './components/UserDashboard';
import LLMHub from './components/LLMHub';
import { useMarketStore } from './stores/marketStore';
import { usePolyGodWS } from './hooks/usePolyGodWS';
import { useEditModeStore } from './stores/editModeStore';
import { SettingsButton } from './components/SettingsButton';
import { HamburgerMenu } from './components/HamburgerMenu';
import { SettingsScreen } from './components/SettingsScreen';
import { SpotlightSearch } from './components/SpotlightSearch';
import { NotificationCentre } from './components/NotificationCentre';

interface PolyGodData {
  mode?: number;
  mode_name?: string;
  paper_pnl?: number;
}

function App() {
  const { selectedMarket } = useMarketStore();
  const { isConnected, data: rawPolyGodData, lastAlert } = usePolyGodWS();
  const {
    isEditMode,
    setEditMode,
    toggleSettings,
    setHamburgerOpen,
    settingsOpen,
    setSpotlightOpen,
    spotlightOpen,
    setNotificationOpen,
    notificationOpen,
  } = useEditModeStore();
  const [activeTab, setActiveTab] = useState<'news' | 'whales' | 'holders' | 'stats' | 'debate'>(
    'news'
  );
  const [activeView, setActiveView] = useState<'markets' | 'user' | 'llm'>('markets');
  const [tickerHeight, setTickerHeight] = useState(33); // Dynamic ticker height
  const { data: marketsData } = useMarkets();

  // Safely parse polyGodData with proper type checking
  const polyGodData: PolyGodData | null = (() => {
    if (!rawPolyGodData) return null;

    try {
      // If it's already an object, use it directly
      if (typeof rawPolyGodData === 'object' && rawPolyGodData !== null) {
        return rawPolyGodData as PolyGodData;
      }

      // If it's a string, try to parse it
      if (typeof rawPolyGodData === 'string') {
        const parsed = JSON.parse(rawPolyGodData);
        if (typeof parsed === 'object' && parsed !== null) {
          return parsed as PolyGodData;
        }
      }
    } catch (error) {
      console.warn('Failed to parse polyGodData:', error);
    }

    return null;
  })();

  // Mode color mapping
  const getModeColor = (mode: number) => {
    switch (mode) {
      case 0:
        return 'bg-gray-500/30 text-gray-300';
      case 1:
        return 'bg-blue-500/30 text-blue-300';
      case 2:
        return 'bg-yellow-500/30 text-yellow-300';
      case 3:
        return 'bg-red-500/30 text-red-300 animate-pulse';
      default:
        return 'bg-gray-500/30 text-gray-300';
    }
  };

  // Check if polyGodData has the expected properties
  const hasValidPolyGodData = (data: PolyGodData | null): data is PolyGodData => {
    return (
      data !== null &&
      typeof data === 'object' &&
      ('mode' in data || 'mode_name' in data || 'paper_pnl' in data)
    );
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Ctrl + E: Toggle Edit Mode
      if (event.ctrlKey && event.key === 'e') {
        event.preventDefault();
        setEditMode(!isEditMode);
      }
      // Ctrl + ,: Open Settings Screen
      else if (event.ctrlKey && event.key === ',') {
        event.preventDefault();
        toggleSettings();
      }
      // Ctrl + \: Toggle Hamburger Menu
      else if (event.ctrlKey && event.key === '\\') {
        event.preventDefault();
        setHamburgerOpen(true);
      }
      // Cmd+K / Ctrl+K: Open Spotlight Search
      else if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
        event.preventDefault();
        setSpotlightOpen(true);
      }
      // Escape: Close panels in priority order (spotlight > settings > hamburger > editMode)
      else if (event.key === 'Escape') {
        if (spotlightOpen) {
          setSpotlightOpen(false);
        } else if (settingsOpen) {
          toggleSettings();
        } else if (document.querySelector('.hamburger-menu')) {
          setHamburgerOpen(false);
        } else if (isEditMode) {
          setEditMode(false);
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [
    isEditMode,
    settingsOpen,
    spotlightOpen,
    setEditMode,
    toggleSettings,
    setHamburgerOpen,
    setSpotlightOpen,
  ]);

  return (
    <div className="min-h-screen bg-surface-950 pg-mesh-bg" style={{ paddingTop: tickerHeight }}>
      <TickerBanner
        items={[
          ...(lastAlert
            ? [
                {
                  id: 'whale-alert',
                  label: 'WHALE ALERT',
                  value: lastAlert.slice(0, 40),
                  positive: true,
                },
              ]
            : []),
          ...(marketsData?.markets?.slice(0, 10).map((market: any, idx: number) => {
            const yesPercentage =
              (market.yes_percentage ?? 0) ||
              (market.yes_price ? market.yes_price * 100 : 0) ||
              (market.outcomes?.[0]?.price ? market.outcomes[0].price * 100 : 0);
            return {
              id: `market-${idx}`,
              label: market.title.slice(0, 22).toUpperCase(),
              value: `${yesPercentage.toFixed(1)}%`,
              positive: yesPercentage > 50,
            };
          }) || []),
        ]}
        onHeightChange={setTickerHeight}
      />

      {/* Header */}
      <header className="glass border-b border-white/10 sticky z-50" style={{ top: tickerHeight }}>
        <div className="max-w-[1920px] mx-auto px-4 py-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <HamburgerMenu setActiveView={setActiveView} />
            <div className="p-2 rounded-xl bg-primary-600 shadow-lg shadow-primary-900/20">
              <TrendingUp className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">POLYGOD</h1>
              <p className="text-sm text-surface-200">AI-Powered Market Intelligence</p>
            </div>
          </div>

          <div className="flex-1 flex flex-col md:flex-row items-center justify-end gap-3 w-full">
            {/* GOD TIER POLYGOD STATUS */}
            <div className="flex items-center gap-2 bg-surface-900/70 border border-white/10 rounded-xl px-3 py-2">
              <Brain className={`w-4 h-4 ${isConnected ? 'text-emerald-400' : 'text-red-400'}`} />
              <span className="text-xs font-semibold text-surface-200">POLYGOD</span>
              {polyGodData && hasValidPolyGodData(polyGodData) && (
                <>
                  {/* Mode + PnL (original) */}
                  <div
                    className={`text-xs px-2 py-0.5 rounded-lg font-medium ${getModeColor(
                      polyGodData.mode || 0
                    )}`}
                  >
                    MODE {polyGodData.mode || 0}
                  </div>
                  <div className="flex items-center gap-1">
                    <DollarSign
                      className={`w-3 h-3 ${
                        (polyGodData.paper_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                      }`}
                    />
                    <span
                      className={`text-xs font-mono font-bold ${
                        (polyGodData.paper_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                      }`}
                    >
                      {(polyGodData.paper_pnl ?? 0).toFixed(2)}
                    </span>
                  </div>
                  {/* NEW: Confidence Gauge */}
                  <div className="w-24 h-2 bg-surface-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-emerald-400 to-cyan-400 transition-all"
                      style={{ width: `${Math.min(100, (polyGodData.paper_pnl ?? 0) * 20)}%` }}
                    ></div>
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        const marketId = selectedMarket?.id || 'default';
                        const response = await fetch(
                          `/api/polygod/simulate?market_id=${marketId}&order_size=1000`,
                          {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                          }
                        );
                        const data = await response.json();
                        alert(
                          `Monte-Carlo: ${data.recommendation}\nWin Prob: ${(
                            data.simulation.win_prob * 100
                          ).toFixed(1)}%\nExpected PnL: $${data.simulation.expected_pnl.toFixed(2)}`
                        );
                      } catch (err) {
                        alert('Monte-Carlo simulation failed — check backend logs');
                      }
                    }}
                    className="text-[10px] px-2 py-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 rounded-lg flex items-center gap-1"
                  >
                    <Zap className="w-3 h-3" /> SIM
                  </button>
                </>
              )}
              {!isConnected && <Zap className="w-3 h-3 text-yellow-400 animate-pulse" />}
            </div>

            <div className="ios-segmented">
              <button
                onClick={() => setActiveView('markets')}
                className={`ios-seg-item ${activeView === 'markets' ? 'active' : ''}`}
              >
                Markets
              </button>
              <button
                onClick={() => setActiveView('user')}
                className={`ios-seg-item ${activeView === 'user' ? 'active' : ''}`}
              >
                User Lab
              </button>
              <button
                onClick={() => setActiveView('llm')}
                className={`ios-seg-item ${activeView === 'llm' ? 'active' : ''}`}
              >
                LLM Hub
              </button>
            </div>

            {/* Notification Bell */}
            <button
              onClick={() => setNotificationOpen(!notificationOpen)}
              className="ios-icon-btn relative"
            >
              <Bell className="w-5 h-5" />
              {/* Unread count badge */}
              <div className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-xs font-bold text-white">
                2
              </div>
            </button>

            {activeView === 'markets' && <SearchBar />}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1920px] mx-auto p-4">
        {activeView === 'markets' ? (
          <div className="grid grid-cols-12 gap-4 lg:gap-6">
            {/* Sidebar - Market List */}
            <aside className="col-span-12 lg:col-span-3 xl:col-span-3">
              <div className="ios-card rounded-2xl p-4 sticky top-24">
                <div className="flex items-center gap-2 mb-4">
                  <BarChart3 className="w-5 h-5 text-primary-400" />
                  <h2 className="font-semibold text-white">Top 100 Markets</h2>
                </div>
                <MarketList />
              </div>
            </aside>

            {/* Main Content Area */}
            <div className="col-span-12 lg:col-span-9 xl:col-span-9 space-y-4 lg:space-y-6">
              {/* Chart Section */}
              <section className="ios-card rounded-2xl p-4 lg:p-6">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
                  <div className="flex-1 min-w-0">
                    <h2 className="font-semibold text-white truncate">
                      {selectedMarket?.title || 'Select a market'}
                    </h2>
                    {selectedMarket && (
                      <div className="flex items-center gap-3 text-sm text-surface-200">
                        <p>
                          Current:{' '}
                          <span className="text-white font-medium">
                            {(
                              (selectedMarket.yes_percentage ?? 0) ||
                              (selectedMarket.yes_price ? selectedMarket.yes_price * 100 : 0) ||
                              (selectedMarket.outcomes?.[0]?.price
                                ? selectedMarket.outcomes[0].price * 100
                                : 0)
                            ).toFixed(2)}
                            %
                          </span>{' '}
                          Yes
                        </p>
                        <span className="text-surface-600">•</span>
                        <p>
                          Vol:{' '}
                          <span className="text-white font-medium">
                            {new Intl.NumberFormat('en-US', {
                              style: 'currency',
                              currency: 'USD',
                              maximumFractionDigits: 0,
                            }).format(selectedMarket.volume_24h)}
                          </span>
                        </p>
                      </div>
                    )}
                  </div>
                  <TimeframeSelector />
                </div>
                <PriceChart />
              </section>

              {/* News & Whales Section */}
              <section className="ios-card rounded-2xl p-4 lg:p-6">
                <div className="flex items-center gap-4 mb-4 border-b border-white/5 pb-2 overflow-x-auto">
                  <button
                    onClick={() => setActiveTab('news')}
                    className={`flex items-center gap-2 px-2 py-1 relative transition-colors whitespace-nowrap ${
                      activeTab === 'news'
                        ? 'text-white'
                        : 'text-surface-400 hover:text-surface-200'
                    }`}
                  >
                    <Newspaper
                      className={`w-5 h-5 ${
                        activeTab === 'news' ? 'text-accent-400' : 'opacity-70'
                      }`}
                    />
                    <span className="font-semibold">Related News</span>
                    {activeTab === 'news' && (
                      <div className="absolute -bottom-[9px] left-0 right-0 h-0.5 bg-accent-400 rounded-full" />
                    )}
                  </button>

                  <div className="w-px h-4 bg-white/10 shrink-0" />

                  <button
                    onClick={() => setActiveTab('whales')}
                    className={`flex items-center gap-2 px-2 py-1 relative transition-colors whitespace-nowrap ${
                      activeTab === 'whales'
                        ? 'text-white'
                        : 'text-surface-400 hover:text-surface-200'
                    }`}
                  >
                    <Wallet
                      className={`w-5 h-5 ${
                        activeTab === 'whales' ? 'text-emerald-400' : 'opacity-70'
                      }`}
                    />
                    <span className="font-semibold">Recent Large Orders</span>
                    {activeTab === 'whales' && (
                      <div className="absolute -bottom-[9px] left-0 right-0 h-0.5 bg-emerald-400 rounded-full" />
                    )}
                  </button>

                  <div className="w-px h-4 bg-white/10 shrink-0" />

                  <button
                    onClick={() => setActiveTab('holders')}
                    className={`flex items-center gap-2 px-2 py-1 relative transition-colors whitespace-nowrap ${
                      activeTab === 'holders'
                        ? 'text-white'
                        : 'text-surface-400 hover:text-surface-200'
                    }`}
                  >
                    <Trophy
                      className={`w-5 h-5 ${
                        activeTab === 'holders' ? 'text-amber-400' : 'opacity-70'
                      }`}
                    />
                    <span className="font-semibold">Top Holders</span>
                    {activeTab === 'holders' && (
                      <div className="absolute -bottom-[9px] left-0 right-0 h-0.5 bg-amber-400 rounded-full" />
                    )}
                  </button>

                  <div className="w-px h-4 bg-white/10 shrink-0" />

                  <button
                    onClick={() => setActiveTab('stats')}
                    className={`flex items-center gap-2 px-2 py-1 relative transition-colors whitespace-nowrap ${
                      activeTab === 'stats'
                        ? 'text-white'
                        : 'text-surface-400 hover:text-surface-200'
                    }`}
                  >
                    <Activity
                      className={`w-5 h-5 ${
                        activeTab === 'stats' ? 'text-purple-400' : 'opacity-70'
                      }`}
                    />
                    <span className="font-semibold">Price Analysis</span>
                    {activeTab === 'stats' && (
                      <div className="absolute -bottom-[9px] left-0 right-0 h-0.5 bg-purple-400 rounded-full" />
                    )}
                  </button>

                  <div className="w-px h-4 bg-white/10 shrink-0" />

                  <button
                    onClick={() => setActiveTab('debate')}
                    className={`flex items-center gap-2 px-2 py-1 relative transition-colors whitespace-nowrap ${
                      activeTab === 'debate'
                        ? 'text-white'
                        : 'text-surface-400 hover:text-surface-200'
                    }`}
                  >
                    <MessageSquare
                      className={`w-5 h-5 ${
                        activeTab === 'debate' ? 'text-blue-400' : 'opacity-70'
                      }`}
                    />
                    <span className="font-semibold">Debate Floor</span>
                    {activeTab === 'debate' && (
                      <div className="absolute -bottom-[9px] left-0 right-0 h-0.5 bg-blue-400 rounded-full" />
                    )}
                  </button>
                </div>

                {activeTab === 'news' && <NewsFeed />}
                {activeTab === 'whales' && <WhaleList />}
                {activeTab === 'holders' && <TopHolders />}
                {activeTab === 'stats' && <PriceMovement />}
                {activeTab === 'debate' && <DebateFloor marketId={selectedMarket?.id || null} />}
              </section>
            </div>
          </div>
        ) : activeView === 'llm' ? (
          <LLMHub />
        ) : (
          <UserDashboard />
        )}
      </main>

      {/* Settings Screen */}
      <SettingsScreen />

      {/* Spotlight Search */}
      <SpotlightSearch isOpen={spotlightOpen} onClose={() => setSpotlightOpen(false)} />

      {/* Notification Centre */}
      <NotificationCentre
        isOpen={notificationOpen}
        onClose={() => setNotificationOpen(false)}
        tickerHeight={tickerHeight}
      />

      {/* Settings Button */}
      <SettingsButton />

      {/* Footer */}
      <footer className="glass border-t border-white/10 mt-8">
        <div className="max-w-[1920px] mx-auto px-4 py-4 text-center text-sm text-surface-200">
          <p>
            Data from{' '}
            <a
              href="https://polymarket.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary-400 hover:text-primary-300 transition-colors"
            >
              Polymarket
            </a>{' '}
            • News from NewsAPI
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
