import { useState, useRef } from 'react';
import { useEditModeStore } from '../stores/editModeStore';
import { useLongPress } from '../hooks/useLongPress';
import { MarketList } from './MarketList';
import PriceChart from './PriceChart';
import { NewsFeed } from './NewsFeed';
import { WhaleList } from './WhaleList';
import { TopHolders } from './TopHolders';
import { PriceMovement } from './PriceMovement';
import { DebateFloor } from './DebateFloor';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

import { TimeframeSelector } from './TimeframeSelector';
import { SettingsButton } from './SettingsButton';
import { X, RefreshCw, Edit, Copy, Scissors, EyeOff, Target, RotateCcw } from 'lucide-react';
import { useMarketStore } from '../stores/marketStore';

export function EditableLayout() {
  const {
    isEditMode,
    jiggleMode,
    setEditMode,
    renameWidget,
    setSelectedComponent,
    setFocusMode,
    focusMode,
    setWidgetHidden,
    resetWidgetStyle,
  } = useEditModeStore();
  const { selectedMarket } = useMarketStore();
  const [renamingWidget, setRenamingWidget] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; widgetId: string } | null>(
    null
  );
  const [copiedStyle, setCopiedStyle] = useState<any>(null);
  const lastTapTime = useRef<Record<string, number>>({});

  const handleLongPress = useLongPress(() => {
    if (!isEditMode) {
      setEditMode(true);
    }
  });

  const handleWidgetClick = (widgetId: string) => {
    const now = Date.now();
    const lastTap = lastTapTime.current[widgetId] || 0;
    if (now - lastTap < 300) {
      // Double tap detected
      setRenamingWidget(widgetId);
    }
    lastTapTime.current[widgetId] = now;
  };

  const handleRename = (widgetId: string, newName: string) => {
    renameWidget(widgetId, newName);
    setRenamingWidget(null);
  };

  const handleCancelRename = (_widgetId: string) => {
    setRenamingWidget(null);
  };

  const handleContextMenu = (e: React.MouseEvent, widgetId: string) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, widgetId });
  };

  const closeContextMenu = () => {
    setContextMenu(null);
  };

  const handleCopyStyle = async () => {
    if (!contextMenu) return;
    const style = useEditModeStore.getState().widgetStyles[contextMenu.widgetId];
    if (style) {
      await navigator.clipboard.writeText(JSON.stringify(style));
      setCopiedStyle(style);
    }
    closeContextMenu();
  };

  const handlePasteStyle = () => {
    if (!contextMenu || !copiedStyle) return;
    setSelectedComponent(contextMenu.widgetId);
    setEditMode(true);
    // The paste will happen in the StyleSidebar
    closeContextMenu();
  };

  const handleHideWidget = () => {
    if (!contextMenu) return;
    setWidgetHidden(contextMenu.widgetId, true);
    closeContextMenu();
  };

  const handleResetWidget = () => {
    if (!contextMenu) return;
    resetWidgetStyle(contextMenu.widgetId);
    closeContextMenu();
  };

  const handleFocusWidget = () => {
    if (!contextMenu) return;
    setSelectedComponent(contextMenu.widgetId);
    setFocusMode(true);
    closeContextMenu();
  };

  const components = [
    { id: 'marketList', title: 'Market List' },
    { id: 'priceChart', title: 'Price Chart' },
    { id: 'newsFeed', title: 'News Feed' },
    { id: 'whaleList', title: 'Whale List' },
    { id: 'topHolders', title: 'Top Holders' },
    { id: 'priceMovement', title: 'Price Movement' },
    { id: 'debateFloor', title: 'Debate Floor' },
  ];

  const renderComponent = (componentId: string) => {
    switch (componentId) {
      case 'marketList':
        return <MarketList />;
      case 'priceChart':
        return <PriceChart />;
      case 'newsFeed':
        return <NewsFeed />;
      case 'whaleList':
        return <WhaleList />;
      case 'topHolders':
        return <TopHolders />;
      case 'priceMovement':
        return <PriceMovement />;
      case 'debateFloor':
        return <DebateFloor marketId={selectedMarket?.id || null} />;
      default:
        return null;
    }
  };

  if (!isEditMode) {
    return (
      <>
        <SettingsButton />
        <div className="max-w-[1920px] mx-auto p-4">
          <div className="grid grid-cols-12 gap-4 lg:gap-6">
            <div className="col-span-12 lg:col-span-3 xl:col-span-3">
              <div className="ios-card rounded-2xl p-4 sticky top-24">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-5 h-5 bg-primary-400 rounded"></div>
                  <h2 className="font-semibold text-white">Top 100 Markets</h2>
                </div>
                <MarketList />
              </div>
            </div>
            <div className="col-span-12 lg:col-span-9 xl:col-span-9 space-y-4 lg:space-y-6">
              <section className="ios-card rounded-2xl p-4 lg:p-6">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
                  <div className="flex-1 min-w-0">
                    <h2 className="font-semibold text-white truncate">
                      {selectedMarket?.title || 'Select a market'}
                    </h2>
                  </div>
                  <TimeframeSelector />
                </div>
                <PriceChart />
              </section>

              <section className="ios-card rounded-2xl p-4 lg:p-6">
                <div className="flex items-center gap-4 mb-4">
                  <button className="ios-btn active">News</button>
                  <button className="ios-btn">Orders</button>
                  <button className="ios-btn">Holders</button>
                  <button className="ios-btn">Analysis</button>
                  <button className="ios-btn">Debate</button>
                </div>
                <NewsFeed />
              </section>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <div className="pg-mesh-bg">
      <div className="max-w-[1920px] mx-auto p-4">
        <div className="grid grid-cols-12 gap-4 lg:gap-6">
          <div className="col-span-12 lg:col-span-3 xl:col-span-3">
            <div className="ios-card rounded-2xl p-4 sticky top-24">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-5 h-5 bg-primary-400 rounded"></div>
                <h2 className="font-semibold text-white">Top 100 Markets</h2>
              </div>
              <MarketList />
            </div>
          </div>
          <div className="col-span-12 lg:col-span-9 xl:col-span-9 space-y-4 lg:space-y-6">
            {components.map((component) => (
              <section
                key={component.id}
                className={`ios-card rounded-2xl p-4 lg:p-6 relative ${jiggleMode ? 'jiggle' : ''}`}
                {...handleLongPress}
                onContextMenu={(e) => handleContextMenu(e, component.id)}
              >
                {/* Hold progress ring */}
                {handleLongPress.isHolding && (
                  <svg
                    className="absolute inset-0 w-full h-full pointer-events-none"
                    style={{ zIndex: 20 }}
                    viewBox="0 0 100 100"
                  >
                    <circle
                      cx="50"
                      cy="50"
                      r="45"
                      fill="none"
                      stroke="var(--pg-gold)"
                      strokeWidth="2"
                      strokeDasharray="282.743"
                      strokeDashoffset={282.743 * (1 - handleLongPress.holdProgress)}
                    />
                  </svg>
                )}

                {/* Corner resize handles */}
                {isEditMode && (
                  <>
                    <div
                      className="absolute top-0 left-0 w-2.5 h-2.5 bg-white rounded-full pointer-events-none"
                      style={{
                        border: '1.5px solid var(--pg-gold)',
                        transform: 'translate(-50%, -50%)',
                        zIndex: 20,
                      }}
                    />
                    <div
                      className="absolute top-0 right-0 w-2.5 h-2.5 bg-white rounded-full pointer-events-none"
                      style={{
                        border: '1.5px solid var(--pg-gold)',
                        transform: 'translate(50%, -50%)',
                        zIndex: 20,
                      }}
                    />
                    <div
                      className="absolute bottom-0 left-0 w-2.5 h-2.5 bg-white rounded-full pointer-events-none"
                      style={{
                        border: '1.5px solid var(--pg-gold)',
                        transform: 'translate(-50%, 50%)',
                        zIndex: 20,
                      }}
                    />
                    <div
                      className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-white rounded-full pointer-events-none"
                      style={{
                        border: '1.5px solid var(--pg-gold)',
                        transform: 'translate(50%, 50%)',
                        zIndex: 20,
                      }}
                    />
                  </>
                )}

                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
                  <div className="flex-1 min-w-0">
                    {renamingWidget === component.id ? (
                      <input
                        type="text"
                        defaultValue={component.title}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            handleRename(component.id, e.currentTarget.value);
                          } else if (e.key === 'Escape') {
                            handleCancelRename(component.id);
                          }
                        }}
                        onBlur={(e) => handleRename(component.id, e.currentTarget.value)}
                        className="bg-transparent border-none border-b border-yellow-500 text-white font-semibold outline-none w-full"
                        autoFocus
                      />
                    ) : (
                      <h2
                        className="font-semibold text-white truncate cursor-pointer"
                        onClick={() => handleWidgetClick(component.id)}
                      >
                        {component.title}
                      </h2>
                    )}
                  </div>
                  {isEditMode && (
                    <div className="flex items-center gap-2">
                      <button className="ios-icon-btn" onClick={() => {}}>
                        <RefreshCw className="w-4 h-4" />
                      </button>
                      <button className="ios-icon-btn" onClick={() => {}}>
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
                {renderComponent(component.id)}
              </section>
            ))}
          </div>
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div
          className="pg-context-menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={closeContextMenu}
        >
          <button
            className="pg-context-item"
            onClick={() => {
              setSelectedComponent(contextMenu.widgetId);
              setEditMode(true);
            }}
          >
            <Edit className="w-4 h-4" />
            Edit Style
          </button>
          <button className="pg-context-item" onClick={handleCopyStyle}>
            <Copy className="w-4 h-4" />
            Copy Style
          </button>
          <button className="pg-context-item" onClick={handlePasteStyle} disabled={!copiedStyle}>
            <Scissors className="w-4 h-4" />
            Paste Style
          </button>
          <hr className="border-white/10 my-1" />
          <button className="pg-context-item" onClick={handleFocusWidget}>
            <Target className="w-4 h-4" />
            Focus Mode
          </button>
          <button className="pg-context-item" onClick={handleHideWidget}>
            <EyeOff className="w-4 h-4" />
            Hide Widget
          </button>
          <button className="pg-context-item" onClick={handleResetWidget}>
            <RotateCcw className="w-4 h-4" />
            Reset Widget
          </button>
        </div>
      )}

      {/* Focus Mode Exit Button */}
      {focusMode && (
        <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-50">
          <button
            onClick={() => setFocusMode(false)}
            className="ios-btn-gold px-6 py-3 text-sm font-medium"
          >
            Exit Focus Mode
          </button>
        </div>
      )}
    </div>
  );
}
