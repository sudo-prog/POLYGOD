/**
 * useKronosWS — reads Kronos forecast data from the existing /ws/polygod stream.
 * No new WebSocket connection — piggybacks on the existing authenticated WS.
 *
 * Usage:
 *   const { forecast, isLoading } = useKronosWS(marketId)
 */

import { useState, useEffect } from 'react';
import { usePolyGodWS } from './usePolyGodWS'; // existing hook

export interface KronosForecastData {
  market_id: string;
  title: string;
  forecast: number; // percentage, e.g. 67.4
  lower_80: number;
  upper_80: number;
  signal: 'bullish' | 'bearish' | 'neutral' | 'insufficient_data' | 'model_error';
  trend: 'up' | 'down';
  delta_pct: number;
  horizon_candles: number;
  timeframe: string;
  updated_at: string;
}

export function useKronosWS(marketId: string | undefined): {
  forecast: KronosForecastData | null;
  isLoading: boolean;
  lastUpdated: Date | null;
} {
  const { lastMessage } = usePolyGodWS();
  const [forecast, setForecast] = useState<KronosForecastData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    if (!lastMessage || !marketId) return;

    try {
      const data = JSON.parse(lastMessage);
      if (data.type === 'state' && data.kronos_forecasts) {
        const marketForecast = data.kronos_forecasts[marketId];
        if (marketForecast) {
          setForecast(marketForecast as KronosForecastData);
          setLastUpdated(new Date());
          setIsLoading(false);
        }
      }
    } catch {
      // malformed message — ignore
    }
  }, [lastMessage, marketId]);

  // If we've received at least one WS message but no Kronos data for this market,
  // stop showing the loading spinner after 5 seconds
  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 5000);
    return () => clearTimeout(timer);
  }, []);

  return { forecast, isLoading, lastUpdated };
}
