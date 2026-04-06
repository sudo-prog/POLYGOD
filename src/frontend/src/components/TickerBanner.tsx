// POLYGOD — TickerBanner.tsx
// LED-style scrolling ticker — position:fixed, never shifts layout
// Settings persisted to localStorage key 'pg-ticker-settings'

import { useState, useEffect, useRef, useCallback } from 'react';
import { Settings2, X } from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────
export interface TickerItem {
  id: string;
  label: string; // e.g. "S&P 100"
  value: string; // e.g. "1547.90"
  change?: string; // e.g. "-3.31"
  changePct?: string; // e.g. "-0.21%"
  positive?: boolean; // drives colour
  type?: 'market' | 'whale' | 'alert' | 'info';
}

export interface TickerSettings {
  height: number; // px, 24–60
  speed: number; // px/s, 20–200
  bgColor: string; // hex
  textColor: string; // hex  (positive values)
  negColor: string; // hex  (negative values)
  labelColor: string; // hex
  separatorColor: string; // hex
  fontSize: number; // px, 10–22
  fontFamily: string; // CSS font name
  ledEffect: boolean; // dot-matrix overlay
  ledOpacity: number; // 0–0.4
  borderColor: string; // hex
  borderWidth: number; // px 0–3
  scanlineEffect: boolean; // CRT scanline overlay
  letterSpacing: number; // em, 0–0.3
}

const DEFAULT_SETTINGS: TickerSettings = {
  height: 32,
  speed: 60,
  bgColor: '#0a0500',
  textColor: '#ffb300',
  negColor: '#ff3b30',
  labelColor: '#ff9500',
  separatorColor: '#664400',
  fontSize: 13,
  fontFamily: 'JetBrains Mono',
  ledEffect: true,
  ledOpacity: 0.18,
  borderColor: '#3a2800',
  borderWidth: 1,
  scanlineEffect: true,
  letterSpacing: 0.06,
};

function loadSettings(): TickerSettings {
  try {
    const raw = localStorage.getItem('pg-ticker-settings');
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    /* ignore */
  }
  return { ...DEFAULT_SETTINGS };
}

function saveSettings(s: TickerSettings) {
  try {
    localStorage.setItem('pg-ticker-settings', JSON.stringify(s));
  } catch {
    /* ignore */
  }
}

// ── LED dot-matrix SVG pattern ─────────────────────────────────────────
function LedOverlay({ height, opacity }: { height: number; opacity: number }) {
  return (
    <svg
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 3,
      }}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <pattern id="led-dots" x="0" y="0" width="3" height="3" patternUnits="userSpaceOnUse">
          <circle cx="1.5" cy="1.5" r="1" fill={`rgba(0,0,0,${opacity})`} />
        </pattern>
      </defs>
      <rect width="100%" height={height} fill="url(#led-dots)" />
    </svg>
  );
}

// ── Scanline overlay ──────────────────────────────────────────────────
function ScanlineOverlay({ height }: { height: number }) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        height,
        background:
          'repeating-linear-gradient(0deg, rgba(0,0,0,0.08) 0px, rgba(0,0,0,0.08) 1px, transparent 1px, transparent 3px)',
        pointerEvents: 'none',
        zIndex: 2,
      }}
    />
  );
}

// ── Settings panel ────────────────────────────────────────────────────
function TickerSettingsPanel({
  settings,
  onChange,
  onClose,
  onReset,
}: {
  settings: TickerSettings;
  onChange: (partial: Partial<TickerSettings>) => void;
  onClose: () => void;
  onReset: () => void;
}) {
  const fonts = [
    'JetBrains Mono',
    'Courier New',
    'Share Tech Mono',
    'VT323',
    'Press Start 2P',
    'Orbitron',
    'IBM Plex Mono',
  ];

  const row = (label: string, children: React.ReactNode) => (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '4px 0',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: 'rgba(148,163,184,0.7)',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </span>
      {children}
    </div>
  );

  const colorInput = (key: keyof TickerSettings) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <input
        type="color"
        value={String(settings[key])}
        aria-label={key}
        onChange={(e) => onChange({ [key]: e.target.value })}
        style={{
          width: 28,
          height: 22,
          padding: 1,
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 4,
          background: 'none',
          cursor: 'pointer',
        }}
      />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.5)' }}>
        {String(settings[key])}
      </span>
    </div>
  );

  const slider = (
    key: keyof TickerSettings,
    min: number,
    max: number,
    step = 1,
    fmt?: (v: number) => string
  ) => {
    const val = Number(settings[key]);
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={val}
          aria-label={key}
          onChange={(e) => onChange({ [key]: parseFloat(e.target.value) })}
          style={{ width: 100 }}
        />
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            color: 'rgba(255,255,255,0.6)',
            minWidth: 30,
            textAlign: 'right',
          }}
        >
          {fmt ? fmt(val) : val}
        </span>
      </div>
    );
  };

  const toggle = (key: keyof TickerSettings) => (
    <label
      className="ios-toggle"
      style={{ width: 36, height: 20, position: 'relative', display: 'inline-block' }}
    >
      <input
        type="checkbox"
        checked={Boolean(settings[key])}
        onChange={(e) => onChange({ [key]: e.target.checked })}
        style={{ opacity: 0, width: 0, height: 0, position: 'absolute' }}
      />
      <span
        className="ios-toggle-track"
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: 999,
          cursor: 'pointer',
          background: settings[key] ? '#c9a84c' : 'rgba(255,255,255,0.15)',
          border: '1px solid rgba(255,255,255,0.12)',
          transition: 'background 200ms',
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: 2,
            left: settings[key] ? 16 : 2,
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: 'white',
            boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
            transition: 'left 200ms',
          }}
        />
      </span>
    </label>
  );

  return (
    <div
      style={{
        position: 'fixed',
        left: 0,
        right: 0,
        top: settings.height + settings.borderWidth,
        zIndex: 199,
        background: 'rgba(7,8,14,0.97)',
        backdropFilter: 'blur(24px)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        padding: '12px 20px',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
        gap: '8px 24px',
      }}
    >
      {/* Header */}
      <div
        style={{
          gridColumn: '1 / -1',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 6,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            color: '#c9a84c',
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
          }}
        >
          ✦ TICKER SETTINGS
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={onReset}
            className="ios-btn"
            style={{ padding: '3px 10px', fontSize: 9, borderRadius: 999 }}
          >
            RESET
          </button>
          <button
            onClick={onClose}
            className="ios-icon-btn"
            style={{ width: 24, height: 24 }}
            aria-label="Close ticker settings"
          >
            <X style={{ width: 11, height: 11 }} />
          </button>
        </div>
      </div>

      {/* Column 1 — Dimensions */}
      <div>
        {row(
          'Height (px)',
          slider('height', 24, 60, 2, (v) => `${v}px`)
        )}
        {row(
          'Scroll Speed',
          slider('speed', 20, 200, 5, (v) => `${v}px/s`)
        )}
        {row(
          'Font Size',
          slider('fontSize', 10, 22, 1, (v) => `${v}px`)
        )}
        {row(
          'Letter Spacing',
          slider('letterSpacing', 0, 0.3, 0.01, (v) => `${v.toFixed(2)}em`)
        )}
        {row(
          'Border Width',
          slider('borderWidth', 0, 3, 1, (v) => `${v}px`)
        )}
      </div>

      {/* Column 2 — Colours */}
      <div>
        {row('Background', colorInput('bgColor'))}
        {row('Positive / Value', colorInput('textColor'))}
        {row('Negative', colorInput('negColor'))}
        {row('Label', colorInput('labelColor'))}
        {row('Separator', colorInput('separatorColor'))}
        {row('Border', colorInput('borderColor'))}
      </div>

      {/* Column 3 — Effects + Font */}
      <div>
        {row('LED Dot Effect', toggle('ledEffect'))}
        {row(
          'LED Intensity',
          slider('ledOpacity', 0, 0.4, 0.02, (v) => `${Math.round(v * 100)}%`)
        )}
        {row('Scanlines', toggle('scanlineEffect'))}
        {row(
          'Font Family',
          <select
            value={settings.fontFamily}
            aria-label="Font family"
            onChange={(e) => onChange({ fontFamily: e.target.value })}
            className="ios-select"
            style={{ fontSize: 10, padding: '3px 26px 3px 8px', maxWidth: 140 }}
          >
            {fonts.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  );
}

// ── Main TickerBanner ─────────────────────────────────────────────────
interface TickerBannerProps {
  items: TickerItem[];
  /** Callback so App.tsx can offset its sticky header top value */
  onHeightChange?: (height: number) => void;
}

export function TickerBanner({ items, onHeightChange }: TickerBannerProps) {
  const [settings, setSettings] = useState<TickerSettings>(loadSettings);
  const [showSettings, setShowSettings] = useState(false);
  const [paused, setPaused] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);

  const totalHeight = settings.height + settings.borderWidth;

  // Notify parent of height so header top can be offset correctly
  useEffect(() => {
    onHeightChange?.(totalHeight);
  }, [totalHeight, onHeightChange]);

  const handleChange = useCallback((partial: Partial<TickerSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...partial };
      saveSettings(next);
      return next;
    });
  }, []);

  const handleReset = useCallback(() => {
    setSettings({ ...DEFAULT_SETTINGS });
    saveSettings({ ...DEFAULT_SETTINGS });
  }, []);

  // CSS animation approach — use a fixed base duration to prevent animation restarts
  // when items change (e.g., when whale alert appears/disappears)
  const baseDuration = 30; // base seconds for one complete cycle

  // Only calculate extra time for additional items, don't recalculate on every change
  const duration = Math.max(baseDuration, baseDuration + (items.length - 5) * 3);

  if (!items.length) return null;

  return (
    <>
      {/* ── Fixed ticker strip ── */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          height: settings.height,
          zIndex: 200,
          background: settings.bgColor,
          borderBottom: `${settings.borderWidth}px solid ${settings.borderColor}`,
          overflow: 'hidden',
          cursor: paused ? 'default' : 'pointer',
          userSelect: 'none',
        }}
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        role="marquee"
        aria-label="Live market ticker"
      >
        {/* Scanlines */}
        {settings.scanlineEffect && <ScanlineOverlay height={settings.height} />}

        {/* LED dots */}
        {settings.ledEffect && (
          <LedOverlay height={settings.height} opacity={settings.ledOpacity} />
        )}

        {/* Scrolling track */}
        <div
          ref={trackRef}
          style={{
            display: 'flex',
            alignItems: 'center',
            height: '100%',
            whiteSpace: 'nowrap',
            animation: `ticker-scroll ${duration}s linear infinite`,
            animationPlayState: paused ? 'paused' : 'running',
            position: 'relative',
            zIndex: 4,
          }}
        >
          {/* Render twice so it loops seamlessly */}
          {[0, 1].map((pass) => (
            <span key={pass} style={{ display: 'inline-flex', alignItems: 'center' }}>
              {items.map((item) => (
                <span
                  key={`${pass}-${item.id}`}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 0 }}
                >
                  {/* Label */}
                  <span
                    style={{
                      fontFamily: `'${settings.fontFamily}', monospace`,
                      fontSize: settings.fontSize,
                      letterSpacing: `${settings.letterSpacing}em`,
                      color: settings.labelColor,
                      paddingRight: '0.5em',
                      fontWeight: 600,
                      textShadow: `0 0 8px ${settings.labelColor}88`,
                    }}
                  >
                    {item.label}
                  </span>
                  {/* Value */}
                  <span
                    style={{
                      fontFamily: `'${settings.fontFamily}', monospace`,
                      fontSize: settings.fontSize,
                      letterSpacing: `${settings.letterSpacing}em`,
                      color: item.positive === false ? settings.negColor : settings.textColor,
                      paddingRight: '0.3em',
                      textShadow: `0 0 10px ${
                        item.positive === false ? settings.negColor : settings.textColor
                      }99`,
                    }}
                  >
                    {item.value}
                  </span>
                  {/* Change */}
                  {item.change && (
                    <span
                      style={{
                        fontFamily: `'${settings.fontFamily}', monospace`,
                        fontSize: settings.fontSize - 1,
                        letterSpacing: `${settings.letterSpacing}em`,
                        color: item.positive === false ? settings.negColor : settings.textColor,
                        paddingRight: '0.2em',
                        opacity: 0.9,
                      }}
                    >
                      {Number(item.change) >= 0 ? '+' : ''}
                      {item.change}
                    </span>
                  )}
                  {/* Pct */}
                  {item.changePct && (
                    <span
                      style={{
                        fontFamily: `'${settings.fontFamily}', monospace`,
                        fontSize: settings.fontSize - 1,
                        letterSpacing: `${settings.letterSpacing}em`,
                        color: item.positive === false ? settings.negColor : settings.textColor,
                        opacity: 0.85,
                      }}
                    >
                      {item.changePct}
                    </span>
                  )}
                  {/* Separator */}
                  <span
                    style={{
                      fontFamily: `'${settings.fontFamily}', monospace`,
                      fontSize: settings.fontSize,
                      color: settings.separatorColor,
                      padding: '0 1em',
                      textShadow: `0 0 6px ${settings.separatorColor}66`,
                    }}
                  >
                    ◆
                  </span>
                </span>
              ))}
            </span>
          ))}
        </div>

        {/* Settings gear — right edge */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowSettings((s) => !s);
          }}
          aria-label="Ticker settings"
          style={{
            position: 'absolute',
            right: 8,
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 10,
            background: 'rgba(0,0,0,0.5)',
            border: `1px solid ${settings.borderColor}`,
            borderRadius: 4,
            width: 22,
            height: 22,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: settings.labelColor,
          }}
        >
          <Settings2 style={{ width: 11, height: 11 }} />
        </button>

        {/* Left fade */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: 40,
            zIndex: 5,
            background: `linear-gradient(to right, ${settings.bgColor}, transparent)`,
            pointerEvents: 'none',
          }}
        />
        {/* Right fade (leaves space for gear) */}
        <div
          style={{
            position: 'absolute',
            right: 0,
            top: 0,
            bottom: 0,
            width: 60,
            zIndex: 5,
            background: `linear-gradient(to left, ${settings.bgColor}, transparent)`,
            pointerEvents: 'none',
          }}
        />
      </div>

      {/* Settings panel (drops below the ticker) */}
      {showSettings && (
        <TickerSettingsPanel
          settings={settings}
          onChange={handleChange}
          onClose={() => setShowSettings(false)}
          onReset={handleReset}
        />
      )}

      {/* CSS keyframe injected once */}
      <style>{`
        @keyframes ticker-scroll {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </>
  );
}
