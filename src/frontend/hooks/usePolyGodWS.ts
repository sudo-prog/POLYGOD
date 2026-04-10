// src/frontend/hooks/usePolyGodWS.ts
//
// SECURITY FIX H7: Token is no longer passed as a URL query parameter.
//
// Previous:  ws://host/ws/polygod?token=SECRET   ← in browser history, server logs
// Fixed:     ws://host/ws/polygod                ← clean URL
//            first message: {"type":"auth","token":"SECRET"}
//            server confirms: {"type":"auth_ok"}
//
// This is the standard first-message auth pattern used by Slack, Discord,
// and most production WebSocket APIs.
//
// VITE_WS_TOKEN is still read from the environment — it's just sent as
// application data instead of a URL parameter.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useMarketStore } from '../stores/marketStore';

// URL without token — protocol auto-detected from page protocol
const _proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const _host = import.meta.env.VITE_WS_URL || 'localhost:8000';
const WS_BASE_URL = `${_proto}//${_host}/ws/polygod`;

const WS_TOKEN: string = import.meta.env.VITE_WS_TOKEN ?? '';
const RECONNECT_BASE_MS = 3_000;
const MAX_RECONNECT_ATTEMPTS = 10;
const AUTH_TIMEOUT_MS = 10_000; // close if server doesn't respond to auth in 10s

export function usePolyGodWS() {
  const [isConnected, setIsConnected] = useState(false);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [lastAlert, setLastAlert] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const authTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);
  const isAuthenticatedRef = useRef(false);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    try {
      const ws = new WebSocket(WS_BASE_URL); // no token in URL
      wsRef.current = ws;
      isAuthenticatedRef.current = false;

      ws.onopen = () => {
        if (!isMountedRef.current) return;

        // Step 1: send auth frame as the first and only pre-auth message
        ws.send(JSON.stringify({ type: 'auth', token: WS_TOKEN }));

        // Close if server doesn't respond within AUTH_TIMEOUT_MS
        authTimeoutRef.current = setTimeout(() => {
          if (!isAuthenticatedRef.current) {
            console.warn('[PolyGodWS] Auth timed out — closing');
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
          console.warn('[PolyGodWS] Unparseable message:', event.data);
          return;
        }

        // Step 2: handle auth response before processing any data
        if (!isAuthenticatedRef.current) {
          if (frame.type === 'auth_ok') {
            isAuthenticatedRef.current = true;
            if (authTimeoutRef.current) clearTimeout(authTimeoutRef.current);
            setIsConnected(true);
            reconnectAttemptsRef.current = 0;
            console.log('[PolyGodWS] Authenticated ✓');
          } else {
            // Unexpected first frame (wrong token, server error, etc.)
            console.error('[PolyGodWS] Auth failed — server sent:', frame);
            ws.close(4001, 'auth_failed');
          }
          return;
        }

        // Step 3: normal data frames after authentication
        setData(frame);
        useMarketStore.getState().updatePolyGod(frame as any);

        if (frame.whale_alert) {
          setLastAlert(frame.whale_alert as string);
          setTimeout(() => setLastAlert(null), 5_000);
        }
      };

      ws.onclose = (event) => {
        if (!isMountedRef.current) return;
        if (authTimeoutRef.current) clearTimeout(authTimeoutRef.current);
        setIsConnected(false);
        isAuthenticatedRef.current = false;
        wsRef.current = null;
        console.log('[PolyGodWS] Disconnected (code=%d)', event.code);

        if (
          event.code === 4001 || // auth rejected — no point retrying with same token
          reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS
        ) {
          console.warn(
            '[PolyGodWS] Not reconnecting (code=%d, attempts=%d)',
            event.code,
            reconnectAttemptsRef.current
          );
          return;
        }

        const delay = RECONNECT_BASE_MS * Math.pow(1.5, reconnectAttemptsRef.current);
        console.log(
          `[PolyGodWS] Reconnecting in ${Math.round(delay)}ms ` +
            `(attempt ${reconnectAttemptsRef.current + 1}/${MAX_RECONNECT_ATTEMPTS})`
        );
        reconnectTimeoutRef.current = setTimeout(() => {
          if (!isMountedRef.current) return;
          reconnectAttemptsRef.current += 1;
          connect();
        }, delay);
      };

      ws.onerror = (err) => {
        console.error('[PolyGodWS] Error:', err);
        setIsConnected(false);
      };
    } catch (err) {
      console.error('[PolyGodWS] Failed to create WebSocket:', err);
      setIsConnected(false);
    }
  }, []);

  const stableConnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect]);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && !wsRef.current) {
        console.log('[PolyGodWS] Page visible again — reconnecting');
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
    data,
    lastAlert,
    reconnectAttempts: reconnectAttemptsRef.current,
    maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS,
  };
}
