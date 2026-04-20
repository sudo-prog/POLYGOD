import { useCallback, useEffect, useRef, useState } from 'react';
import { useMarketStore } from '../stores/marketStore';

const WS_URL = `ws://${import.meta.env.VITE_WS_URL || 'localhost:8000'}/ws/polygod?token=${
  import.meta.env.VITE_WS_TOKEN
}`;
const RECONNECT_INTERVAL = 3000; // 3 seconds
const MAX_RECONNECT_ATTEMPTS = 10;

export function usePolyGodWS() {
  const [isConnected, setIsConnected] = useState(false);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [lastAlert, setLastAlert] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<string | null>(null);
  // FIX H1: useRef for reconnectAttempts to avoid stale closure
  const reconnectAttemptsRef = useRef(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    try {
      wsRef.current = new WebSocket(WS_URL);

      wsRef.current.onopen = () => {
        if (!isMountedRef.current) return;
        console.log('[PolyGodWS] Connected');
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
      };

      wsRef.current.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          setLastMessage(event.data); // Store raw message for Kronos hook
          const messageData = JSON.parse(event.data);
          setData(messageData);
          useMarketStore.getState().updatePolyGod(messageData);

          // Set last alert if the message contains alert information
          if (messageData.whale_alert) {
            setLastAlert(messageData.whale_alert);
            // Clear alert after 5 seconds
            setTimeout(() => setLastAlert(null), 5000);
          }
        } catch (parseError) {
          console.warn('[PolyGodWS] Failed to parse message:', parseError);
        }
      };

      wsRef.current.onclose = () => {
        if (!isMountedRef.current) return;
        console.log('[PolyGodWS] Disconnected');
        setIsConnected(false);
        wsRef.current = null;

        // FIX H1: Use ref for reconnectAttempts to get current value
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = RECONNECT_INTERVAL * Math.pow(1.5, reconnectAttemptsRef.current);
          console.log(
            `[PolyGodWS] Reconnecting in ${delay}ms (attempt ${
              reconnectAttemptsRef.current + 1
            }/${MAX_RECONNECT_ATTEMPTS})`
          );
          reconnectTimeoutRef.current = setTimeout(() => {
            if (!isMountedRef.current) return;
            reconnectAttemptsRef.current += 1;
            connect();
          }, delay);
        } else {
          console.warn('[PolyGodWS] Max reconnection attempts reached');
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('[PolyGodWS] Error:', error);
        setIsConnected(false);
      };
    } catch (error) {
      console.error('[PolyGodWS] Failed to create WebSocket:', error);
      setIsConnected(false);
    }
  }, []);

  // FIX H1: useCallback for connect with empty deps since we use refs
  const stableConnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect]);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    // FIX H2: Add visibilitychange listener for laptop lid open/close
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && !wsRef.current) {
        console.log('[PolyGodWS] Visibility restored, reconnecting...');
        stableConnect();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [connect, stableConnect]);

  return {
    isConnected,
    data,
    lastAlert,
    lastMessage,
    reconnectAttempts: reconnectAttemptsRef.current,
    maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS,
  };
}
