// TickerBanner.tsx — Seamless LED-style scrolling ticker
// Uses JS-measured scroll width for pixel-perfect seamless loop
// position:fixed — NEVER shifts document layout
import { useState, useEffect, useRef, useCallback } from 'react';
import { Settings2, X } from 'lucide-react';
export interface TickerItem {
  id: string;
  label: string;
  value: string;
  change?: string;
  positive?: boolean;
}
export interface TickerSettings {
  height: number; // 24-56px
  speed: number; // px per second, 30-200
  bgColor: string;
  textColor: string; // positive values
  negColor: string;
  labelColor: string;
  sepColor: string;
  fontSize: number;
  fontFamily: string;
  ledEffect: boolean;
  ledOpacity: number;
  borderColor: string;
  borderWidth: number;
  glowEffect: boolean;
  letterSpacing: number;
}
const DEFAULTS: TickerSettings = {
  height: 32,
  speed: 80,
  bgColor: '#060400',
  textColor: '#ffb300',
  negColor: '#ff3b30',
  labelColor: '#ff9500',
  sepColor: '#3d2600',
  fontSize: 13,
  fontFamily: 'JetBrains Mono',
  ledEffect: true,
  ledOpacity: 0.15,
  borderColor: '#2d1f00',
  borderWidth: 1,
  glowEffect: true,
  letterSpacing: 0.06,
};
function load(): TickerSettings {
  try {
    const r = localStorage.getItem('pg-ticker');
    if (r) return { ...DEFAULTS, ...JSON.parse(r) };
  } catch {}
  return { ...DEFAULTS };
}
function save(s: TickerSettings) {
  try {
    localStorage.setItem('pg-ticker', JSON.stringify(s));
  } catch {}
}
interface Props {
  items: TickerItem[];
  onHeightChange?: (h: number) => void;
}
export function TickerBanner({ items, onHeightChange: _onHeightChange }: Props) {
  const [cfg, setCfg] = useState<TickerSettings>(load);
  const [showCfg, setShowCfg] = useState(false);
  const [paused, setPaused] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const posRef = useRef(0);
  const rafRef = useRef<number>(0);
  const lastRef = useRef(0);
  const halfWidthRef = useRef(0);
  const totalH = cfg.height + cfg.borderWidth;
  // Tell App.tsx the total height so header can offset correctly
  useEffect(() => {
    _onHeightChange?.(totalH);
  }, [totalH, _onHeightChange]);
  // Measure the FIRST HALF of the track (one copy of items) for seamless reset
  useEffect(() => {
    if (!trackRef.current) return;
    const children = Array.from(trackRef.current.children);
    const half = Math.floor(children.length / 2);
    let w = 0;
    for (let i = 0; i < half; i++) {
      w += (children[i] as HTMLElement).offsetWidth;
    }
    halfWidthRef.current = w;
    posRef.current = 0;
  }, [items, cfg.fontSize, cfg.fontFamily, cfg.letterSpacing]);
  // RAF scroll loop — resets seamlessly when pos reaches halfWidth
  useEffect(() => {
    const tick = (now: number) => {
      if (!paused && trackRef.current && halfWidthRef.current > 0) {
        const dt = lastRef.current ? (now - lastRef.current) / 1000 : 0;
        lastRef.current = now;
        posRef.current += cfg.speed * dt;
        if (posRef.current >= halfWidthRef.current) {
          posRef.current -= halfWidthRef.current; // seamless jump
        }
        trackRef.current.style.transform = `translateX(-${posRef.current}px)`;
      } else {
        lastRef.current = now;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [paused, cfg.speed]);
  const update = useCallback((p: Partial<TickerSettings>) => {
    setCfg((prev) => {
      const n = { ...prev, ...p };
      save(n);
      return n;
    });
  }, []);
  const fontStyle = `'${cfg.fontFamily}', 'JetBrains Mono', monospace`;
  const glow = cfg.glowEffect ? `0 0 8px ${cfg.textColor}88, 0 0 3px ${cfg.textColor}44` : 'none';
  if (!items.length) return null;
  // Build item set — rendered TWICE for seamless loop
  const ItemSet = () => (
    <>
      {items.map((item) => (
        <span
          key={item.id}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0,
            flexShrink: 0,
            whiteSpace: 'nowrap',
          }}
        >
          <span
            style={{
              fontFamily: fontStyle,
              fontSize: cfg.fontSize,
              letterSpacing: `${cfg.letterSpacing}em`,
              color: cfg.labelColor,
              fontWeight: 600,
              paddingRight: '0.5em',
              textShadow: cfg.glowEffect ? `0 0 8px ${cfg.labelColor}88` : 'none',
            }}
          >
            {item.label}
          </span>
          <span
            style={{
              fontFamily: fontStyle,
              fontSize: cfg.fontSize,
              letterSpacing: `${cfg.letterSpacing}em`,
              color: item.positive === false ? cfg.negColor : cfg.textColor,
              paddingRight: item.change ? '0.25em' : '0',
              textShadow: glow,
            }}
          >
            {item.value}
          </span>
          {item.change && (
            <span
              style={{
                fontFamily: fontStyle,
                fontSize: cfg.fontSize - 1,
                color: item.positive === false ? cfg.negColor : cfg.textColor,
                opacity: 0.85,
                letterSpacing: `${cfg.letterSpacing}em`,
              }}
            >
              {Number(item.change) >= 0 ? '+' : ''}
              {item.change}
            </span>
          )}
          <span
            style={{
              fontFamily: fontStyle,
              fontSize: cfg.fontSize,
              color: cfg.sepColor,
              padding: '0 1.2em',
            }}
          >
            ◆
          </span>
        </span>
      ))}
    </>
  );
  return (
    <>
      {/* Fixed ticker strip — zero layout impact */}
      <div
        ref={wrapRef}
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          height: cfg.height,
          zIndex: 1000,
          background: cfg.bgColor,
          borderBottom: `${cfg.borderWidth}px solid ${cfg.borderColor}`,
          overflow: 'hidden',
          userSelect: 'none',
        }}
        aria-label="Live market ticker"
      >
        {/* LED dot overlay */}
        {cfg.ledEffect && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              zIndex: 2,
              pointerEvents: 'none',
              backgroundImage: `radial-gradient(circle, rgba(0,0,0,${cfg.ledOpacity}) 1px, transparent 1px)`,
              backgroundSize: '3px 3px',
            }}
          />
        )}
        {/* Scrolling track — contains TWO copies for seamless loop */}
        <div
          ref={trackRef}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            height: '100%',
            willChange: 'transform',
            position: 'relative',
            zIndex: 3,
            paddingLeft: 8,
          }}
        >
          <ItemSet />
          <ItemSet />
        </div>
        {/* Left fade */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: 48,
            zIndex: 4,
            background: `linear-gradient(to right, ${cfg.bgColor}, transparent)`,
            pointerEvents: 'none',
          }}
        />
        {/* Right fade + gear */}
        <div
          style={{
            position: 'absolute',
            right: 0,
            top: 0,
            bottom: 0,
            width: 64,
            zIndex: 4,
            background: `linear-gradient(to left, ${cfg.bgColor} 32px, transparent)`,
            pointerEvents: 'none',
          }}
        />
        {/* Settings gear button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowCfg((v) => !v);
          }}
          aria-label="Ticker settings"
          style={{
            position: 'absolute',
            right: 8,
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 5,
            background: 'rgba(0,0,0,0.55)',
            border: `1px solid ${cfg.borderColor}`,
            borderRadius: 4,
            width: 22,
            height: 22,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: cfg.labelColor,
            pointerEvents: 'all',
          }}
        >
          <Settings2 style={{ width: 11, height: 11 }} />
        </button>
      </div>
      {/* Settings panel — drops BELOW ticker, fully visible, scrollable */}
      {showCfg && (
        <TickerSettingsPanel
          cfg={cfg}
          tickerTotalHeight={totalH}
          onChange={update}
          onClose={() => setShowCfg(false)}
          onReset={() => {
            setCfg({ ...DEFAULTS });
            save({ ...DEFAULTS });
          }}
        />
      )}
    </>
  );
}
// ■■ Settings Panel ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
function TickerSettingsPanel({
  cfg,
  tickerTotalHeight,
  onChange,
  onClose,
  onReset,
}: {
  cfg: TickerSettings;
  tickerTotalHeight: number;
  onChange: (p: Partial<TickerSettings>) => void;
  onClose: () => void;
  onReset: () => void;
}) {
  const FONTS = [
    'JetBrains Mono',
    'Courier New',
    'Share Tech Mono',
    'IBM Plex Mono',
    'Orbitron',
    'VT323',
  ];
  const row = (label: string, ctrl: React.ReactNode) => (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '5px 0',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: 'rgba(148,163,184,0.7)',
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
        }}
      >
        {label}
      </span>
      {ctrl}
    </div>
  );
  const sld = (
    key: keyof TickerSettings,
    min: number,
    max: number,
    step = 1,
    fmt?: (v: number) => string
  ) => (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={Number(cfg[key])}
        onChange={(e) => onChange({ [key]: parseFloat(e.target.value) })}
        style={{ width: 90 }}
        aria-label={key}
      />
      <span
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: 'rgba(255,255,255,0.6)',
          minWidth: 32,
          textAlign: 'right',
        }}
      >
        {fmt ? fmt(Number(cfg[key])) : Number(cfg[key])}
      </span>
    </div>
  );
  const col = (key: keyof TickerSettings) => (
    <input
      type="color"
      value={String(cfg[key])}
      onChange={(e) => onChange({ [key]: e.target.value })}
      aria-label={key}
      style={{
        width: 28,
        height: 22,
        padding: 2,
        border: '1px solid rgba(255,255,255,0.15)',
        borderRadius: 4,
        background: 'none',
        cursor: 'pointer',
      }}
    />
  );
  const tog = (key: keyof TickerSettings) => (
    <label
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        cursor: 'pointer',
      }}
    >
      <input
        type="checkbox"
        checked={Boolean(cfg[key])}
        onChange={(e) => onChange({ [key]: e.target.checked })}
        style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }}
      />
      <span
        style={{
          display: 'inline-block',
          width: 34,
          height: 18,
          borderRadius: 9,
          background: cfg[key] ? '#c9a84c' : 'rgba(255,255,255,0.15)',
          transition: 'background 200ms',
          position: 'relative',
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: 2,
            left: cfg[key] ? 16 : 2,
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: 'white',
            transition: 'left 200ms',
            boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
          }}
        />
      </span>
    </label>
  );
  return (
    <div
      style={{
        position: 'fixed',
        // Starts BELOW the ticker — never hidden behind it
        top: tickerTotalHeight,
        left: 0,
        right: 0,
        // Max height so it doesn't go off-screen; user can scroll inside
        maxHeight: 'calc(100vh - ' + tickerTotalHeight + 'px - 20px)',
        overflowY: 'auto',
        zIndex: 999,
        background: 'rgba(6,8,18,0.97)',
        backdropFilter: 'blur(24px)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        padding: '12px 20px 16px',
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 10,
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
            style={{
              padding: '3px 10px',
              fontSize: 9,
              fontFamily: 'var(--font-mono)',
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 999,
              color: 'rgba(255,255,255,0.7)',
              cursor: 'pointer',
            }}
          >
            RESET
          </button>
          <button
            onClick={onClose}
            aria-label="Close ticker settings"
            style={{
              width: 24,
              height: 24,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: '50%',
              color: 'rgba(255,255,255,0.7)',
              cursor: 'pointer',
            }}
          >
            <X style={{ width: 11, height: 11 }} />
          </button>
        </div>
      </div>
      {/* Grid of controls */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill,minmax(210px,1fr))',
          gap: '4px 24px',
        }}
      >
        <div>
          {row(
            'Height',
            sld('height', 24, 56, 2, (v) => `${v}px`)
          )}
          {row(
            'Speed',
            sld('speed', 30, 200, 5, (v) => `${v}px/s`)
          )}
          {row(
            'Font Size',
            sld('fontSize', 10, 20, 1, (v) => `${v}px`)
          )}
          {row(
            'Letter Spacing',
            sld('letterSpacing', 0, 0.25, 0.01, (v) => `${v.toFixed(2)}em`)
          )}
          {row(
            'Border',
            sld('borderWidth', 0, 3, 1, (v) => `${v}px`)
          )}
        </div>
        <div>
          {row('Background', col('bgColor'))}
          {row('Positive', col('textColor'))}
          {row('Negative', col('negColor'))}
          {row('Label', col('labelColor'))}
          {row('Separator', col('sepColor'))}
          {row('Border Colour', col('borderColor'))}
        </div>
        <div>
          {row('LED Dots', tog('ledEffect'))}
          {row(
            'LED Intensity',
            sld('ledOpacity', 0, 0.4, 0.01, (v) => `${Math.round(v * 100)}%`)
          )}
          {row('Glow', tog('glowEffect'))}
          {row(
            'Font Family',
            <select
              value={cfg.fontFamily}
              onChange={(e) => onChange({ fontFamily: e.target.value })}
              aria-label="Font family"
              style={{
                fontSize: 9,
                padding: '3px 8px',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: 6,
                color: 'white',
                fontFamily: 'var(--font-mono)',
                maxWidth: 140,
              }}
            >
              {FONTS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>
    </div>
  );
}
