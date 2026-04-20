/**
 * KronosForecastCard — Live AI Forecast widget for market detail view.
 *
 * Design: dark terminal/quant aesthetic to match POLYGOD's existing ios-* classes.
 * Shows Chronos-T5 probability forecast with confidence band, signal badge,
 * and a mini sparkline of the forecast direction.
 */

import { useKronosWS } from '../hooks/useKronosWS';

interface Props {
  marketId: string;
  currentPrice: number; // yes_percentage from market data
}

const SIGNAL_CONFIG = {
  bullish: { label: 'BULLISH', color: '#00ff9f', bg: 'rgba(0,255,159,0.08)', icon: '▲' },
  bearish: { label: 'BEARISH', color: '#ff4d6d', bg: 'rgba(255,77,109,0.08)', icon: '▼' },
  neutral: { label: 'NEUTRAL', color: '#a0a0b0', bg: 'rgba(160,160,176,0.08)', icon: '◆' },
  insufficient_data: { label: 'NO DATA', color: '#555570', bg: 'rgba(85,85,112,0.08)', icon: '?' },
  model_error: { label: 'ERROR', color: '#ff6b00', bg: 'rgba(255,107,0,0.08)', icon: '!' },
};

export function KronosForecastCard({ marketId, currentPrice }: Props) {
  const { forecast, isLoading, lastUpdated } = useKronosWS(marketId);

  const signal = forecast?.signal ?? 'neutral';
  const cfg = SIGNAL_CONFIG[signal] ?? SIGNAL_CONFIG.neutral;

  // Confidence band width as percentage of the card (for visual bar)
  const bandWidth = forecast
    ? Math.min(100, Math.abs(forecast.upper_80 - forecast.lower_80) * 1.5)
    : 0;

  const forecastDelta = forecast ? forecast.forecast - currentPrice : null;

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, rgba(10,10,20,0.95) 0%, rgba(15,15,30,0.98) 100%)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: '12px',
        padding: '16px 20px',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background grid texture */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          opacity: 0.03,
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)',
          backgroundSize: '20px 20px',
          pointerEvents: 'none',
        }}
      />

      {/* Header row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontSize: '9px',
              letterSpacing: '0.15em',
              color: '#666680',
              textTransform: 'uppercase',
              fontWeight: 600,
            }}
          >
            ◈ Kronos AI Forecast
          </span>
          {/* Live pulse dot */}
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: forecast ? '#00ff9f' : '#555',
              boxShadow: forecast ? '0 0 6px #00ff9f' : 'none',
              display: 'inline-block',
              animation: forecast ? 'pulse 2s infinite' : 'none',
            }}
          />
        </div>
        {lastUpdated && (
          <span style={{ fontSize: '9px', color: '#44445a' }}>
            {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>

      {isLoading && !forecast ? (
        // Loading state
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {[80, 55, 65].map((w, i) => (
            <div
              key={i}
              style={{
                height: '10px',
                width: `${w}%`,
                background: 'rgba(255,255,255,0.04)',
                borderRadius: '4px',
                animation: 'shimmer 1.5s infinite',
              }}
            />
          ))}
          <span style={{ fontSize: '10px', color: '#44445a', marginTop: '4px' }}>
            Streaming historical data...
          </span>
        </div>
      ) : forecast &&
        forecast.signal !== 'insufficient_data' &&
        forecast.signal !== 'model_error' ? (
        <>
          {/* Main forecast value */}
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginBottom: '10px' }}
          >
            <span style={{ fontSize: '32px', fontWeight: 700, color: cfg.color, lineHeight: 1 }}>
              {forecast.forecast.toFixed(1)}%
            </span>
            {forecastDelta !== null && (
              <span
                style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: forecastDelta > 0 ? '#00ff9f' : '#ff4d6d',
                }}
              >
                {forecastDelta > 0 ? '+' : ''}
                {forecastDelta.toFixed(1)}%
              </span>
            )}
            <div
              style={{
                marginLeft: 'auto',
                padding: '3px 10px',
                borderRadius: '20px',
                background: cfg.bg,
                border: `1px solid ${cfg.color}33`,
                fontSize: '10px',
                fontWeight: 700,
                color: cfg.color,
                letterSpacing: '0.1em',
              }}
            >
              {cfg.icon} {cfg.label}
            </div>
          </div>

          {/* Confidence band */}
          <div style={{ marginBottom: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span style={{ fontSize: '9px', color: '#44445a' }}>80% Confidence Band</span>
              <span style={{ fontSize: '9px', color: '#66667a' }}>
                {forecast.lower_80.toFixed(1)}% — {forecast.upper_80.toFixed(1)}%
              </span>
            </div>
            <div
              style={{
                height: '4px',
                background: 'rgba(255,255,255,0.05)',
                borderRadius: '2px',
                position: 'relative',
              }}
            >
              {/* Current price marker */}
              <div
                style={{
                  position: 'absolute',
                  left: `${Math.min(95, Math.max(5, currentPrice))}%`,
                  top: '-2px',
                  width: '2px',
                  height: '8px',
                  background: '#666680',
                  transform: 'translateX(-50%)',
                }}
              />
              {/* Confidence band fill */}
              <div
                style={{
                  position: 'absolute',
                  left: `${Math.min(95, Math.max(5, forecast.lower_80))}%`,
                  width: `${bandWidth}%`,
                  height: '100%',
                  background: `linear-gradient(90deg, ${cfg.color}40, ${cfg.color}80, ${cfg.color}40)`,
                  borderRadius: '2px',
                }}
              />
              {/* Forecast point */}
              <div
                style={{
                  position: 'absolute',
                  left: `${Math.min(95, Math.max(5, forecast.forecast))}%`,
                  top: '-3px',
                  width: '4px',
                  height: '10px',
                  background: cfg.color,
                  borderRadius: '2px',
                  transform: 'translateX(-50%)',
                  boxShadow: `0 0 8px ${cfg.color}`,
                }}
              />
            </div>
          </div>

          {/* Meta row */}
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            {[
              { label: 'Horizon', value: `${forecast.horizon_candles} × ${forecast.timeframe}` },
              { label: 'Trend', value: forecast.trend === 'up' ? '↑ Up' : '↓ Down' },
              {
                label: 'Δ',
                value: `${forecast.delta_pct > 0 ? '+' : ''}${forecast.delta_pct.toFixed(1)}%`,
              },
            ].map(({ label, value }) => (
              <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <span
                  style={{
                    fontSize: '8px',
                    color: '#44445a',
                    textTransform: 'uppercase',
                    letterSpacing: '0.12em',
                  }}
                >
                  {label}
                </span>
                <span style={{ fontSize: '11px', color: '#a0a0c0', fontWeight: 600 }}>{value}</span>
              </div>
            ))}
          </div>

          {/* Model attribution */}
          <div
            style={{
              marginTop: '12px',
              paddingTop: '10px',
              borderTop: '1px solid rgba(255,255,255,0.04)',
            }}
          >
            <span style={{ fontSize: '8px', color: '#33334a', letterSpacing: '0.08em' }}>
              CHRONOS-T5 · 418M+ TRADES · SII-WANGZJ/POLYMARKET_DATA
            </span>
          </div>
        </>
      ) : (
        // No data / error state
        <div style={{ padding: '8px 0' }}>
          <span style={{ fontSize: '11px', color: '#44445a' }}>
            {forecast?.signal === 'model_error'
              ? '⚠ Forecast model error — check logs'
              : 'No historical data for this market yet'}
          </span>
          <div style={{ marginTop: '6px', fontSize: '9px', color: '#33334a' }}>
            Kronos enriches top-10 markets by volume every 15 min
          </div>
        </div>
      )}

      {/* CSS animations injected inline */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        @keyframes shimmer {
          0% { opacity: 0.04; }
          50% { opacity: 0.10; }
          100% { opacity: 0.04; }
        }
      `}</style>
    </div>
  );
}
