import { useState, useEffect } from 'react';
import {
  Menu,
  X,
  Grid,
  Layers,
  Palette,
  Save,
  Settings,
  User,
  Cpu,
  Activity,
  MessageSquare,
  Wallet,
  TrendingUp,
  Trophy,
  BarChart3,
} from 'lucide-react';
import { useEditModeStore } from '../stores/editModeStore';

interface MenuItem {
  icon: React.ReactNode;
  label: string;
  action?: () => void;
  href?: string;
  id?: string;
  danger?: boolean;
  disabled?: boolean;
}

interface HamburgerMenuProps {
  setActiveView: (view: 'markets' | 'user' | 'llm') => void;
}

export function HamburgerMenu({ setActiveView }: HamburgerMenuProps) {
  const { setEditMode, toggleSettings, setHamburgerOpen, widgetHidden, setWidgetHidden } =
    useEditModeStore();
  const [isOpen, setIsOpen] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (isOpen && event.target) {
        const target = event.target as Element;
        const menu = document.getElementById('hamburger-menu');
        if (menu && !menu.contains(target)) {
          setIsOpen(false);
        }
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (isOpen && event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  const menuItems: MenuItem[][] = [
    // NAVIGATE
    [
      {
        icon: <Grid className="w-4 h-4" />,
        label: 'Markets',
        action: () => {
          setActiveView('markets');
          setHamburgerOpen(false);
        },
      },
      {
        icon: <User className="w-4 h-4" />,
        label: 'User Lab',
        action: () => {
          setActiveView('user');
          setHamburgerOpen(false);
        },
      },
      {
        icon: <Cpu className="w-4 h-4" />,
        label: 'LLM Hub',
        action: () => {
          setActiveView('llm');
          setHamburgerOpen(false);
        },
      },
    ],
    // WIDGETS
    [
      {
        icon: <TrendingUp className="w-4 h-4" />,
        label: 'Market List',
        id: 'market-list',
        action: () => setWidgetHidden('market-list', !widgetHidden['market-list']),
      },
      {
        icon: <BarChart3 className="w-4 h-4" />,
        label: 'Price Chart',
        id: 'price-chart',
        action: () => setWidgetHidden('price-chart', !widgetHidden['price-chart']),
      },
      {
        icon: <MessageSquare className="w-4 h-4" />,
        label: 'Intel Feed',
        id: 'news-feed',
        action: () => setWidgetHidden('news-feed', !widgetHidden['news-feed']),
      },
      {
        icon: <Wallet className="w-4 h-4" />,
        label: 'Large Orders',
        id: 'whale-list',
        action: () => setWidgetHidden('whale-list', !widgetHidden['whale-list']),
      },
      {
        icon: <Trophy className="w-4 h-4" />,
        label: 'Top Holders',
        id: 'top-holders',
        action: () => setWidgetHidden('top-holders', !widgetHidden['top-holders']),
      },
      {
        icon: <Activity className="w-4 h-4" />,
        label: 'Price Analysis',
        id: 'price-movement',
        action: () => setWidgetHidden('price-movement', !widgetHidden['price-movement']),
      },
      {
        icon: <Layers className="w-4 h-4" />,
        label: 'Debate Floor',
        id: 'debate-floor',
        action: () => setWidgetHidden('debate-floor', !widgetHidden['debate-floor']),
      },
    ],
    // TOOLS
    [
      {
        icon: <Palette className="w-4 h-4" />,
        label: 'Style Editor',
        action: () => {
          toggleSettings();
          setHamburgerOpen(false);
        },
      },
      {
        icon: <Grid className="w-4 h-4" />,
        label: 'Edit Layout',
        action: () => {
          setEditMode(true);
          setHamburgerOpen(false);
        },
      },
      {
        icon: <Settings className="w-4 h-4" />,
        label: 'Keyboard Shortcuts',
        action: () => setShowShortcuts(true),
      },
    ],
    // SYSTEM
    [
      {
        icon: <Activity className="w-4 h-4" />,
        label: 'Connection',
        action: () => {},
      },
      {
        icon: <Layers className="w-4 h-4" />,
        label: 'Data Sources',
        action: () => {},
      },
      {
        icon: <Settings className="w-4 h-4" />,
        label: 'About POLYGOD v0.1.0',
        action: () => {},
      },
      {
        icon: <Save className="w-4 h-4" />,
        label: 'Report Bug',
        href: 'https://github.com/sudo-prog/POLYGOD/issues',
      },
    ],
  ];

  const shortcuts = [
    { key: 'Ctrl + E', action: 'Toggle Edit Mode' },
    { key: 'Ctrl + ,', action: 'Open Settings Screen' },
    { key: 'Ctrl + \\', action: 'Toggle Hamburger Menu' },
    { key: 'Cmd + K', action: 'Spotlight Search' },
    { key: 'Escape', action: 'Close panel / Exit edit mode' },
    { key: 'Double-click widget title', action: 'Rename widget' },
  ];

  return (
    <div className="fixed left-6 top-16 z-50">
      <button onClick={() => setIsOpen(!isOpen)} className="ios-icon-btn">
        {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {isOpen && (
        <div
          id="hamburger-menu"
          className="mt-3 space-y-2"
          style={{
            background: 'rgba(8, 12, 24, 0.92)',
            backdropFilter: 'blur(28px) saturate(200%)',
            border: '1px solid rgba(255, 255, 255, 0.10)',
            borderRadius: '20px',
            minWidth: '260px',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)',
            animation: 'float-up 200ms cubic-bezier(0.34, 1.2, 0.64, 1)',
            position: 'absolute',
            top: '50px',
            left: '0',
            zIndex: 200,
          }}
        >
          {menuItems.map((section, sectionIndex) => (
            <div key={sectionIndex}>
              {section.map((item, index) => {
                const isWidgetSection = sectionIndex === 1; // WIDGETS section
                return (
                  <div
                    key={index}
                    className="flex items-center gap-3 px-4 py-3 rounded-lg transition-all hover:bg-surface-950/50"
                    style={{
                      padding: '10px 14px',
                      borderRadius: '12px',
                      color: 'var(--pg-text)',
                      fontFamily: 'var(--font-body)',
                      fontSize: '13px',
                    }}
                  >
                    {item.href ? (
                      <a
                        href={item.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-3 flex-1"
                      >
                        {item.icon}
                        <span>{item.label}</span>
                        <svg
                          className="w-4 h-4 ml-auto"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                          />
                        </svg>
                      </a>
                    ) : (
                      <>
                        <button
                          onClick={() => {
                            if (item.action) {
                              item.action();
                            }
                            if (!isWidgetSection) {
                              setHamburgerOpen(false);
                            }
                          }}
                          className="flex items-center gap-3 flex-1"
                        >
                          {item.icon}
                          <span>{item.label}</span>
                        </button>
                        {isWidgetSection && item.id && (
                          <button
                            onClick={() => {
                              if (item.action) {
                                item.action();
                              }
                            }}
                            className={`ios-toggle ${widgetHidden[item.id] ? '' : 'active'}`}
                          >
                            <span />
                          </button>
                        )}
                      </>
                    )}
                  </div>
                );
              })}
              {sectionIndex < menuItems.length - 1 && (
                <div
                  style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', margin: '8px 0' }}
                />
              )}
            </div>
          ))}
        </div>
      )}

      {showShortcuts && (
        <div
          className="fixed inset-0 z-500 flex items-center justify-center p-4"
          style={{
            background: 'rgba(7, 8, 14, 0.96)',
            backdropFilter: 'blur(32px)',
          }}
        >
          <div
            className="bg-surface-900/50 border border-white/10 rounded-2xl max-w-md w-full p-6"
            style={{
              background: 'rgba(30, 41, 59, 0.6)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
            }}
          >
            <h3 className="font-semibold text-white mb-4">Keyboard Shortcuts</h3>
            <div className="space-y-2">
              {shortcuts.map((shortcut, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between py-2 border-b border-white/5 last:border-b-0"
                >
                  <span className="text-sm text-surface-200">{shortcut.key}</span>
                  <span className="text-sm font-medium text-white">{shortcut.action}</span>
                </div>
              ))}
            </div>
            <button onClick={() => setShowShortcuts(false)} className="mt-4 ios-btn text-sm w-full">
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
