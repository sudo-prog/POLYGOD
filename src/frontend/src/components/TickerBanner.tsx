// TickerBanner.tsx — Seamless LED-style scrolling ticker
// BUG FIXES vs previous version:
//   1. ItemSet extracted to module-level memoized component — was defined inside
//      render(), causing React to unmount/remount DOM nodes every render, which
//      made the measurement useEffect see stale/empty children → halfWidth = 0 → glitch.
//   2. paddingLeft removed from trackRef div — the 8px offset wasn't counted in
//      child offsetWidth sums, causing early loop reset every cycle (visible seam).
//   3. posRef no longer resets to 0 on remeasure — instead it clamps to new width,
//      preventing the flash-to-start on data refresh.
//   4. lastRef resets on pause/unpause to prevent a giant dt spike on resume.
import { useState, useEffect, useRef, useCallback, memo } from 'react';
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

// ─── Item renderer — module-level so React never unmounts/remounts DOM nodes ──
// THE CORE BUG: previously defined as `const ItemSet = () => (...)` INSIDE the
// TickerBanner function body. React sees a brand new component type on every
// render → unmounts + remounts all DOM nodes → offsetWidth returns 0 on measure
// → halfWidthRef stays 0 → scroll guard fails → ticker glitches/restarts.
interface ItemSetProps {
  items: TickerItem[];
  cfg: TickerSettings;
  glow: string;
  fontStyle: string;
}

const ItemSet = memo(({ items, cfg, glow, fontStyle }: ItemSetProps) => (
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
));
ItemSet.displayName = 'TickerItemSet';

// ─── Main banner ──────────────────────────────────────────────────────────────

interface Props {
  items: TickerItem[];
  onHeightChange?: (h: number) => void;
}

export function TickerBanner({ items, onHeightChange }: Props) {
  const [cfg, setCfg] = useState<TickerSettings>(load);
  const [showCfg, setShowCfg] = useState(false);
  const [paused, setPaused] = useState(false);

  const trackRef = useRef<HTMLDivElement>(null);
  const posRef = useRef(0);
  const rafRef = useRef<number>(0);
  const lastRef = useRef<number>(0);
  const halfWidthRef = useRef(0);

  const totalH = cfg.height + cfg.borderWidth;

  useEffect(() => {
    onHeightChange?.(totalH);
  }, [totalH, onHeightChange]);

  // ── Measure the first copy's width after DOM paint ────────────────────────
  // Uses ResizeObserver + delayed measurement to guarantee proper calculation.
  // Clamps posRef instead of resetting to 0 — no flash-to-start on data refresh.
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // Force re-render when items change to ensure we measure the new items
  const [itemVersion, setItemVersion] = useState(0);

  useEffect(() => {
    setItemVersion((v) => v + 1);
  }, [items.map((i) => i.id).join(',')]); // Track item IDs

  useEffect(() => {
    // Wait for DOM update after itemVersion changes
    const setupTimeout = setTimeout(() => {
      if (!trackRef.current) return;

      const measure = () => {
        if (!trackRef.current) return;

        const container = trackRef.current;
        const children = Array.from(container.children) as HTMLElement[];

        if (children.length === 0) {
          console.warn('[Ticker] No children found during measurement');
          return;
        }

        // Get total width of first copy (half the children)
        const half = Math.floor(children.length / 2);
        let w = 0;

        // Sum widths - exclude the separator (◆) spans which are in the middle
        // We need the width of the actual content, not including separators between copies
        for (let i = 0; i < children.length; i++) {
          const childWidth = children[i].getBoundingClientRect().width;
          if (childWidth > 0) w += childWidth;
        }

        // Divide by 2 to get single copy width
        w = Math.floor(w / 2);

        console.log('[Ticker] Measured width:', w, 'children:', children.length, 'half:', half);

        // Ensure we have valid width before updating
        if (w > 100) {
          // Minimum width threshold
          halfWidthRef.current = w;

          // Only clamp if we're currently scrolling past the new width
          if (posRef.current > w) {
            posRef.current = Math.max(0, posRef.current % w);
          }
        }
      };

      // Set up ResizeObserver to watch for size changes
      if (!resizeObserverRef.current) {
        resizeObserverRef.current = new ResizeObserver(() => {
          measure();
        });
      }

      // Disconnect previous observer if any
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
      }

      resizeObserverRef.current.observe(trackRef.current);

      // Initial measure after DOM is fully ready
      // Use multiple delays to handle different rendering scenarios
      setTimeout(measure, 50);
      setTimeout(measure, 200);
      setTimeout(measure, 500);
    }, 0);

    return () => {
      clearTimeout(setupTimeout);
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
      }
    };
  }, [itemVersion, cfg.fontSize, cfg.fontFamily, cfg.letterSpacing]);

  // ── RAF scroll loop ───────────────────────────────────────────────────────
  // lastRef = 0 signals "first frame" — skip delta to avoid spike on resume.
  useEffect(() => {
    const tick = (now: number) => {
      if (!paused && trackRef.current && halfWidthRef.current > 0) {
        if (lastRef.current === 0) {
          lastRef.current = now; // skip first frame delta
        } else {
          const dt = (now - lastRef.current) / 1000;
          lastRef.current = now;
          posRef.current += cfg.speed * dt;
          if (posRef.current >= halfWidthRef.current) {
            posRef.current -= halfWidthRef.current; // seamless wrap
          }
          trackRef.current.style.transform = `translateX(-${posRef.current}px)`;
        }
      } else if (paused) {
        lastRef.current = 0; // reset so resume starts clean
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

  return (
    <>
      {/* Fixed ticker strip — zero layout impact */}
      <div
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

        {/* Scrolling track — TWO copies for seamless loop */}
        {/* NOTE: no paddingLeft — it offset measurements, causing early reset */}
        <div
          ref={trackRef}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            height: '100%',
            willChange: 'transform',
            position: 'relative',
            zIndex: 3,
          }}
        >
          <ItemSet items={items} cfg={cfg} glow={glow} fontStyle={fontStyle} />
          <ItemSet items={items} cfg={cfg} glow={glow} fontStyle={fontStyle} />
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

        {/* Right fade */}
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

        {/* Settings gear */}
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

// ─── Settings panel ───────────────────────────────────────────────────────────
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
          background: cfg[key] ? '#c9a84c' : 'rgba(255, 255, 255, 0.1)',
        }}
      />
    </label>
  );

  return (
    <div
      style={{
        position: 'fixed',
        top: tickerTotalHeight,
        right: 8,
        width: 320,
        background: '#0d0d0f',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: 8,
        padding: 16,
        zIndex: 1001,
        boxShadow: '0 8px 32px rgba(0,0,0,0.8)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 12,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            fontWeight: 600,
            color: '#ffb300',
          }}
        >
          TICKER SETTINGS
        </span>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: 'rgba(255,255,255,0.5)',
            cursor: 'pointer',
          }}
        >
          <X style={{ width: 14, height: 14 }} />
        </button>
      </div>

      {row(
        'Height',
        sld('height', 24, 56, 1, (v) => `${v}px`)
      )}
      {row(
        'Speed',
        sld('speed', 30, 200, 5, (v) => `${v} px/s`)
      )}
      {row(
        'Font Size',
        sld('fontSize', 10, 18, 1, (v) => `${v}px`)
      )}
      {row(
        'Letter Spacing',
        sld('letterSpacing', 0, 0.2, 0.01, (v) => `${(v * 100).toFixed(0)}%`)
      )}
      {row('LED Effect', tog('ledEffect'))}
      {row(
        'LED Opacity',
        sld('ledOpacity', 0, 0.3, 0.01, (v) => `${(v * 100).toFixed(0)}%`)
      )}
      {row('Glow Effect', tog('glowEffect'))}
      {row('Background', col('bgColor'))}
      {row('Text Color', col('textColor'))}
      {row('Negative Color', col('negColor'))}
      {row('Label Color', col('labelColor'))}
      {row('Border Color', col('borderColor'))}

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button
          onClick={onReset}
          style={{
            flex: 1,
            padding: '8px 12px',
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 4,
            color: 'rgba(255, 255, 255, 0.7)',
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            cursor: 'pointer',
          }}
        >
          RESET DEFAULTS
        </button>
        <button
          onClick={onClose}
          style={{
            flex: 1,
            padding: '8px 12px',
            background: '#c9a84c',
            border: 'none',
            borderRadius: 4,
            color: '#000',
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          DONE
        </button>
      </div>
    </div>
  );
}
