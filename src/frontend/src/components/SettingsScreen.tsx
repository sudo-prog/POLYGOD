import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { useEditModeStore } from '../stores/editModeStore';

interface ThemePreset {
  name: string;
  colors: Record<string, string>;
  background: string;
  typography: Record<string, string>;
}

const themePresets: ThemePreset[] = [
  {
    name: 'DEFAULT',
    colors: {
      accent: '#c9a84c',
      background: '#07080e',
      surface: '#0c1223',
      gold: '#c9a84c',
      green: '#22c55e',
      red: '#ef4444',
      ice: '#7dd3fc',
      purple: '#a78bfa',
    },
    background: 'mesh-gradient',
    typography: {
      title: 'Work Sans',
      body: 'Work Sans',
      mono: 'JetBrains Mono',
    },
  },
];

export function SettingsScreen() {
  const { toggleSettings, settingsOpen } = useEditModeStore();
  const [themeConfig, setThemeConfig] = useState({
    colors: {
      accent: '#c9a84c',
      background: '#07080e',
      surface: '#0c1223',
      gold: '#c9a84c',
      green: '#22c55e',
      red: '#ef4444',
      ice: '#7dd3fc',
      purple: '#a78bfa',
    },
    background: 'mesh-gradient' as 'mesh-gradient' | 'solid' | 'custom-gradient',
    transparency: {
      panel: 0.72,
      button: 0.08,
      border: 0.1,
    },
    typography: {
      title: 'Work Sans',
      body: 'Work Sans',
      mono: 'JetBrains Mono',
      labels: 'Work Sans',
      titleSize: '16px',
      bodySize: '14px',
      labelSize: '12px',
      lineHeight: '1.5',
      letterSpacing: '0',
    },
    layout: {
      gridRowHeight: 30,
    },
    accessibility: {
      reduceMotion: false,
      highContrast: false,
      boldText: false,
      textScale: '100%' as '80%' | '90%' | '100%' | '110%' | '125%',
      colorBlind: 'None' as 'None' | 'Deuteranopia' | 'Protanopia' | 'Tritanopia',
    },
    alerts: {
      whaleAlertMin: 100,
      autoReconnect: true,
      defaultRefresh: '15s' as '15s' | '30s' | '1m' | '5m',
      newsAutoRefresh: true,
    },
  });

  const [savedThemes, setSavedThemes] = useState<ThemePreset[]>([]);
  const [showResetConfirmation, setShowResetConfirmation] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem('pg-saved-themes');
    if (saved) {
      setSavedThemes(JSON.parse(saved));
    }
  }, []);

  const applyThemeVars = (theme: ThemePreset) => {
    Object.entries(theme.colors).forEach(([key, value]) => {
      document.documentElement.style.setProperty(`--pg-${key}`, value);
    });
    if (theme.background === 'mesh-gradient') {
      document.documentElement.style.setProperty('--pg-bg', theme.colors.background);
    } else if (theme.background === 'solid') {
      document.documentElement.style.setProperty('--pg-bg', theme.colors.background);
    }
    Object.entries(theme.typography).forEach(([key, value]) => {
      document.documentElement.style.setProperty(`--font-${key}`, `'${value}', sans-serif`);
    });
  };

  const handleApplyAll = () => {
    Object.entries(themeConfig.colors).forEach(([key, value]) => {
      document.documentElement.style.setProperty(`--pg-${key}`, value);
    });
    if (themeConfig.background === 'mesh-gradient') {
      document.documentElement.style.setProperty('--pg-bg', themeConfig.colors.background);
    } else if (themeConfig.background === 'solid') {
      document.documentElement.style.setProperty('--pg-bg', themeConfig.colors.background);
    }
    document.documentElement.style.setProperty(
      '--pg-panel',
      `rgba(12,18,35,${themeConfig.transparency.panel})`
    );
    document.documentElement.style.setProperty(
      '--pg-glass',
      `rgba(0,0,0,${themeConfig.transparency.button})`
    );
    document.documentElement.style.setProperty(
      '--pg-glass-border',
      `rgba(0,0,0,${themeConfig.transparency.border})`
    );
    Object.entries(themeConfig.typography).forEach(([key, value]) => {
      document.documentElement.style.setProperty(`--font-${key}`, `'${value}', sans-serif`);
    });
    document.documentElement.style.setProperty(
      '--grid-row-height',
      `${themeConfig.layout.gridRowHeight}px`
    );
  };

  const handleResetAll = () => {
    if (showResetConfirmation) {
      setThemeConfig({
        colors: {
          accent: '#c9a84c',
          background: '#07080e',
          surface: '#0c1223',
          gold: '#c9a84c',
          green: '#22c55e',
          red: '#ef4444',
          ice: '#7dd3fc',
          purple: '#a78bfa',
        },
        background: 'mesh-gradient' as 'mesh-gradient' | 'solid' | 'custom-gradient',
        transparency: {
          panel: 0.72,
          button: 0.08,
          border: 0.1,
        },
        typography: {
          title: 'Work Sans',
          body: 'Work Sans',
          mono: 'JetBrains Mono',
          labels: 'Work Sans',
          titleSize: '16px',
          bodySize: '14px',
          labelSize: '12px',
          lineHeight: '1.5',
          letterSpacing: '0',
        },
        layout: {
          gridRowHeight: 30,
        },
        accessibility: {
          reduceMotion: false,
          highContrast: false,
          boldText: false,
          textScale: '100%' as '80%' | '90%' | '100%' | '110%' | '125%',
          colorBlind: 'None' as 'None' | 'Deuteranopia' | 'Protanopia' | 'Tritanopia',
        },
        alerts: {
          whaleAlertMin: 100,
          autoReconnect: true,
          defaultRefresh: '15s' as '15s' | '30s' | '1m' | '5m',
          newsAutoRefresh: true,
        },
      });
      setShowResetConfirmation(false);
    } else {
      setShowResetConfirmation(true);
    }
  };

  if (!settingsOpen) return null;

  return (
    <div
      className="fixed inset-0 z-200 overflow-y-auto"
      style={{
        background: 'rgba(7, 8, 14, 0.96)',
        backdropFilter: 'blur(32px)',
      }}
    >
      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="bg-surface-900/50 border border-white/10 rounded-2xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-white/10">
            <h1 className="text-xl font-bold text-white">SETTINGS</h1>
            <button onClick={toggleSettings} className="ios-icon-btn">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-6">
            {/* APPEARANCE */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white">APPEARANCE</h3>
              <div className="space-y-3">
                {/* Theme presets */}
                <div>
                  <label className="block text-sm font-medium text-surface-200 mb-2">
                    Theme Presets
                  </label>
                  <div className="flex gap-2">
                    {themePresets.map((preset) => (
                      <button
                        key={preset.name}
                        onClick={() => applyThemeVars(preset)}
                        className="px-4 py-2 bg-surface-800/50 border border-white/10 rounded-lg text-sm font-medium text-white hover:bg-surface-700/50 transition-colors"
                      >
                        {preset.name}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Color mode */}
                <div>
                  <label className="block text-sm font-medium text-surface-200 mb-2">
                    Color Mode
                  </label>
                  <div className="ios-segmented">
                    <button className="ios-seg-item active">Dark</button>
                    <button className="ios-seg-item">System</button>
                    <button className="ios-seg-item">Light</button>
                  </div>
                </div>

                {/* Saved themes */}
                <div>
                  <label className="block text-sm font-medium text-surface-200 mb-2">
                    Saved Themes
                  </label>
                  <div className="space-y-2">
                    {savedThemes.map((theme) => (
                      <div
                        key={theme.name}
                        className="flex items-center justify-between p-3 bg-surface-800/50 rounded-lg"
                      >
                        <span className="text-sm text-white">{theme.name}</span>
                        <div className="flex gap-2">
                          <button className="ios-btn text-xs">Load</button>
                          <button className="ios-btn-red text-xs">Delete</button>
                        </div>
                      </div>
                    ))}
                  </div>
                  <button className="ios-btn-gold mt-2">Save Current Theme</button>
                </div>
              </div>
            </div>

            {/* COLOURS */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white">COLOURS</h3>
              <div className="grid grid-cols-2 gap-4">
                {Object.entries(themeConfig.colors).map(([key, value]) => (
                  <div key={key} className="flex items-center gap-3">
                    <label className="text-sm font-medium text-surface-200 capitalize min-w-[60px]">
                      {key}
                    </label>
                    <input
                      type="color"
                      value={value}
                      onChange={(e) =>
                        setThemeConfig((prev) => ({
                          ...prev,
                          colors: { ...prev.colors, [key]: e.target.value },
                        }))
                      }
                      className="w-8 h-8 rounded border border-white/10"
                    />
                    <input
                      type="text"
                      value={value}
                      onChange={(e) =>
                        setThemeConfig((prev) => ({
                          ...prev,
                          colors: { ...prev.colors, [key]: e.target.value },
                        }))
                      }
                      className="ios-input flex-1"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* BACKGROUND */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white">BACKGROUND</h3>
              <div className="ios-segmented">
                <button className="ios-seg-item active">Mesh Gradient</button>
                <button className="ios-seg-item">Solid</button>
                <button className="ios-seg-item">Custom Gradient</button>
              </div>
              <div className="w-full h-16 bg-gradient-to-br from-surface-800 to-surface-900 rounded-lg border border-white/10"></div>
            </div>

            {/* TRANSPARENCY */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white">TRANSPARENCY</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-surface-200 mb-2">
                    Panel Background Opacity: {Math.round(themeConfig.transparency.panel * 100)}%
                  </label>
                  <input
                    type="range"
                    min="0.4"
                    max="0.95"
                    step="0.05"
                    value={themeConfig.transparency.panel}
                    onChange={(e) =>
                      setThemeConfig((prev) => ({
                        ...prev,
                        transparency: { ...prev.transparency, panel: parseFloat(e.target.value) },
                      }))
                    }
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-200 mb-2">
                    Button Background Opacity: {Math.round(themeConfig.transparency.button * 100)}%
                  </label>
                  <input
                    type="range"
                    min="0.04"
                    max="0.25"
                    step="0.01"
                    value={themeConfig.transparency.button}
                    onChange={(e) =>
                      setThemeConfig((prev) => ({
                        ...prev,
                        transparency: { ...prev.transparency, button: parseFloat(e.target.value) },
                      }))
                    }
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-200 mb-2">
                    Border Opacity: {Math.round(themeConfig.transparency.border * 100)}%
                  </label>
                  <input
                    type="range"
                    min="0.04"
                    max="0.30"
                    step="0.01"
                    value={themeConfig.transparency.border}
                    onChange={(e) =>
                      setThemeConfig((prev) => ({
                        ...prev,
                        transparency: { ...prev.transparency, border: parseFloat(e.target.value) },
                      }))
                    }
                    className="w-full"
                  />
                </div>
              </div>
            </div>

            {/* TYPOGRAPHY */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white">TYPOGRAPHY</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-surface-200 mb-2">
                    Global Line Height: {themeConfig.typography.lineHeight}
                  </label>
                  <input
                    type="range"
                    min="1.2"
                    max="2.0"
                    step="0.1"
                    value={themeConfig.typography.lineHeight}
                    onChange={(e) =>
                      setThemeConfig((prev) => ({
                        ...prev,
                        typography: {
                          ...prev.typography,
                          lineHeight: parseFloat(e.target.value).toString(),
                        },
                      }))
                    }
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-200 mb-2">
                    Text Scale
                  </label>
                  <div className="ios-segmented">
                    <button className="ios-seg-item">80%</button>
                    <button className="ios-seg-item">90%</button>
                    <button className="ios-seg-item active">100%</button>
                    <button className="ios-seg-item">110%</button>
                    <button className="ios-seg-item">125%</button>
                  </div>
                </div>
              </div>
            </div>

            {/* LAYOUT */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white">LAYOUT</h3>
              <div>
                <label className="block text-sm font-medium text-surface-200 mb-2">
                  Grid Row Height: {themeConfig.layout.gridRowHeight}px
                </label>
                <input
                  type="range"
                  min="30"
                  max="60"
                  step="5"
                  value={themeConfig.layout.gridRowHeight}
                  onChange={(e) =>
                    setThemeConfig((prev) => ({
                      ...prev,
                      layout: { ...prev.layout, gridRowHeight: parseInt(e.target.value) },
                    }))
                  }
                  className="w-full"
                />
              </div>
              <button className="ios-btn-red">Reset All Widget Sizes</button>
            </div>

            {/* ACCESSIBILITY */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white">ACCESSIBILITY</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-surface-200">Reduce Motion</span>
                  <button
                    onClick={() =>
                      setThemeConfig((prev) => ({
                        ...prev,
                        accessibility: {
                          ...prev.accessibility,
                          reduceMotion: !prev.accessibility.reduceMotion,
                        },
                      }))
                    }
                    className={`ios-toggle ${
                      themeConfig.accessibility.reduceMotion ? 'active' : ''
                    }`}
                  >
                    <span />
                  </button>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-surface-200">High Contrast</span>
                  <button
                    onClick={() =>
                      setThemeConfig((prev) => ({
                        ...prev,
                        accessibility: {
                          ...prev.accessibility,
                          highContrast: !prev.accessibility.highContrast,
                        },
                      }))
                    }
                    className={`ios-toggle ${
                      themeConfig.accessibility.highContrast ? 'active' : ''
                    }`}
                  >
                    <span />
                  </button>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-surface-200">Bold Text</span>
                  <button
                    onClick={() =>
                      setThemeConfig((prev) => ({
                        ...prev,
                        accessibility: {
                          ...prev.accessibility,
                          boldText: !prev.accessibility.boldText,
                        },
                      }))
                    }
                    className={`ios-toggle ${themeConfig.accessibility.boldText ? 'active' : ''}`}
                  >
                    <span />
                  </button>
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-200 mb-2">
                    Text Scale
                  </label>
                  <div className="ios-segmented">
                    <button className="ios-seg-item">A-</button>
                    <button className="ios-seg-item active">A</button>
                    <button className="ios-seg-item">A+</button>
                    <button className="ios-seg-item">A++</button>
                  </div>
                </div>
              </div>
            </div>

            {/* ALERTS & DATA */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white">ALERTS & DATA</h3>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <label className="text-sm font-medium text-surface-200">
                    Whale Alert Minimum:
                  </label>
                  <input
                    type="number"
                    value={themeConfig.alerts.whaleAlertMin}
                    onChange={(e) =>
                      setThemeConfig((prev) => ({
                        ...prev,
                        alerts: { ...prev.alerts, whaleAlertMin: parseInt(e.target.value) },
                      }))
                    }
                    className="ios-input w-20"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-surface-200">WebSocket Auto-Reconnect</span>
                  <button
                    onClick={() =>
                      setThemeConfig((prev) => ({
                        ...prev,
                        alerts: { ...prev.alerts, autoReconnect: !prev.alerts.autoReconnect },
                      }))
                    }
                    className={`ios-toggle ${themeConfig.alerts.autoReconnect ? 'active' : ''}`}
                  >
                    <span />
                  </button>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-surface-200">News Auto-Refresh</span>
                  <button
                    onClick={() =>
                      setThemeConfig((prev) => ({
                        ...prev,
                        alerts: { ...prev.alerts, newsAutoRefresh: !prev.alerts.newsAutoRefresh },
                      }))
                    }
                    className={`ios-toggle ${themeConfig.alerts.newsAutoRefresh ? 'active' : ''}`}
                  >
                    <span />
                  </button>
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-200 mb-2">
                    Default Refresh Interval
                  </label>
                  <div className="ios-segmented">
                    <button className="ios-seg-item active">15s</button>
                    <button className="ios-seg-item">30s</button>
                    <button className="ios-seg-item">1m</button>
                    <button className="ios-seg-item">5m</button>
                  </div>
                </div>
              </div>
            </div>

            {/* THOUGHT STREAM AI - MCP PACKAGES */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-white">THOUGHT STREAM AI - MCP PACKAGES</h3>
              <p className="text-sm text-surface-400">
                Install and manage Model Context Protocol (MCP) packages for Thought Stream AI.
              </p>
              <div className="space-y-3">
                <div className="p-4 bg-surface-800/50 rounded-lg border border-white/10">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <div className="font-medium text-white">Playwright MCP</div>
                      <div className="text-sm text-surface-400">
                        Browser automation for web research
                      </div>
                    </div>
                    <span className="text-xs px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded">
                      Installed
                    </span>
                  </div>
                </div>
                <div className="p-4 bg-surface-800/50 rounded-lg border border-white/10">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <div className="font-medium text-white">Filesystem MCP</div>
                      <div className="text-sm text-surface-400">Local file system access</div>
                    </div>
                    <span className="text-xs px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded">
                      Installed
                    </span>
                  </div>
                </div>
                <div className="p-4 bg-surface-800/50 rounded-lg border border-white/10">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <div className="font-medium text-white">Postgres MCP</div>
                      <div className="text-sm text-surface-400">
                        Database queries and operations
                      </div>
                    </div>
                    <span className="text-xs px-2 py-1 bg-surface-600/50 text-surface-300 rounded">
                      Available
                    </span>
                  </div>
                  <button className="text-xs text-primary-400 hover:text-primary-300">
                    Install
                  </button>
                </div>
                {/* Package installer input */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-surface-200">
                    Install Custom MCP Package
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="npm install @org/mcp-package"
                      className="ios-input flex-1"
                    />
                    <button className="ios-btn">Install</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Action Bar */}
          <div
            className="sticky bottom-0 flex items-center justify-end gap-3 p-6 border-t border-white/10"
            style={{
              background: 'rgba(7, 8, 14, 0.95)',
              backdropFilter: 'blur(16px)',
              borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <button className="ios-btn">Cancel</button>
            <button onClick={handleResetAll} className="ios-btn-red">
              {showResetConfirmation ? 'Confirm Reset' : 'Reset All'}
            </button>
            <button onClick={handleApplyAll} className="ios-btn">
              Apply All
            </button>
            <button className="ios-btn-gold">Save</button>
          </div>
        </div>
      </div>
    </div>
  );
}
