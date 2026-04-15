// src/frontend/hooks/useLiveTradesWS.ts
//
// Hook for connecting to the /ws/live-trades WebSocket endpoint
// Receives real-time whale trades broadcast by the backend

import { useCallback, useEffect, useRef, useState } from 'react';

export interface LiveTrade {
  fill_id: string;
  market_id: string;
  size: number;
  price: number;
  side: 'BUY' | 'SELL' | 'unknown';
  value_usd: number;
  timestamp?: string;
}

export interface LiveTradesMessage {
  type: 'whale_trade';
  data: LiveTrade;
  timestamp: string;
}

const _proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const _host = import.meta.env.VITE_WS_URL || 'localhost:8000';
const WS_LIVE_TRADES_URL = `${_proto}//${_host}/ws/live-trades`;

const WS_TOKEN: string = import.meta.env.VITE_WS_TOKEN ?? '';
const RECONNECT_BASE_MS = 3_000;
const MAX_RECONNECT_ATTEMPTS = 10;
const AUTH_TIMEOUT_MS = 10_000;

export function useLiveTradesWS() {
  const [isConnected, setIsConnected] = useState(false);
  const [trades, setTrades] = useState<LiveTrade[]>([]);
  const [lastError, setLastError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const authTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);
  const isAuthenticatedRef = useRef(false);

  const addTrade = useCallback((trade: LiveTrade) => {
    setTrades((prev) => {
      // Keep last 50 trades max
      const updated = [trade, ...prev].slice(0, 50);
      return updated;
    });
  }, []);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    try {
      const ws = new WebSocket(WS_LIVE_TRADES_URL);
      wsRef.current = ws;
      isAuthenticatedRef.current = false;

      ws.onopen = () => {
        if (!isMountedRef.current) return;

        // Send auth as first message
        ws.send(JSON.stringify({ type: 'auth', token: WS_TOKEN }));

        // Auth timeout
        authTimeoutRef.current = setTimeout(() => {
          if (!isAuthenticatedRef.current) {
            console.warn('[LiveTradesWS] Auth timed out — closing');
            ws.close();
          }
        }, AUTH_TIMEOUT_MS);
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        if (!isMountedRef.current) return;

        let frame: Record<string, unknown>;
        try {
          frame = JSON.parse(event.data);
        } catch {
          console.warn('[LiveTradesWS] Unparseable message:', event.data);
          return;
        }

        // Handle auth response
        if (!isAuthenticatedRef.current) {
          if (frame.type === 'auth_ok') {
            isAuthenticatedRef.current = true;
            if (authTimeoutRef.current) clearTimeout(authTimeoutRef.current);
            setIsConnected(true);
            reconnectAttemptsRef.current = 0;
            console.log('[LiveTradesWS] Authenticated ✓');
          } else {
            console.error('[LiveTradesWS] Auth failed — server sent:', frame);
            ws.close(4001, 'auth_failed');
          }
          return;
        }

        // Handle whale_trade messages
        if (frame.type === 'whale_trade' && frame.data) {
          const tradeData = frame.data as LiveTrade;
          addTrade(tradeData);
        }
      };

      ws.onclose = (event) => {
        if (!isMountedRef.current) return;
        if (authTimeoutRef.current) clearTimeout(authTimeoutRef.current);
        setIsConnected(false);
        isAuthenticatedRef.current = false;
        wsRef.current = null;
        console.log('[LiveTradesWS] Disconnected (code=%d)', event.code);

        if (event.code === 4001 || reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          console.warn(
            '[LiveTradesWS] Not reconnecting (code=%d, attempts=%d)',
            event.code,
            reconnectAttemptsRef.current
          );
          setLastError('Authentication failed or max attempts reached');
          return;
        }

        const delay = RECONNECT_BASE_MS * Math.pow(1.5, reconnectAttemptsRef.current);
        console.log(
          `[LiveTradesWS] Reconnecting in ${Math.round(delay)}ms ` +
            `(attempt ${reconnectAttemptsRef.current + 1}/${MAX_RECONNECT_ATTEMPTS})`
        );
        reconnectTimeoutRef.current = setTimeout(() => {
          if (!isMountedRef.current) return;
          reconnectAttemptsRef.current += 1;
          connect();
        }, delay);
      };

      ws.onerror = (err) => {
        console.error('[LiveTradesWS] Error:', err);
        setLastError('WebSocket connection error');
      };
    } catch (err) {
      console.error('[LiveTradesWS] Failed to create WebSocket:', err);
      setLastError('Failed to connect to live trades');
      setIsConnected(false);
    }
  }, [addTrade]);

  const stableConnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect]);

  const clearTrades = useCallback(() => {
    setTrades([]);
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && !wsRef.current) {
        console.log('[LiveTradesWS] Page visible again — reconnecting');
        stableConnect();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (authTimeoutRef.current) clearTimeout(authTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [connect, stableConnect]);

  return {
    isConnected,
    trades,
    lastError,
    clearTrades,
    reconnectAttempts: reconnectAttemptsRef.current,
    maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS,
  };
}
