import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';

const WS_URL = 'ws://localhost:8000/ws/polygod';
const RECONNECT_INTERVAL = 3000; // 3 seconds
const MAX_RECONNECT_ATTEMPTS = 10;

export function usePolyGodWS() {
  const [isConnected, setIsConnected] = useState(false);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [lastAlert, setLastAlert] = useState<string | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = () => {
    try {
      wsRef.current = new WebSocket(WS_URL);

      wsRef.current.onopen = () => {
        console.log('[PolyGodWS] Connected');
        setIsConnected(true);
        setReconnectAttempts(0);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const messageData = JSON.parse(event.data);
          setData(messageData);
          useStore.getState().updatePolyGod?.(messageData);

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
        console.log('[PolyGodWS] Disconnected');
        setIsConnected(false);
        wsRef.current = null;

        // Attempt reconnection with exponential backoff
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          const delay = RECONNECT_INTERVAL * Math.pow(1.5, reconnectAttempts);
          console.log(`[PolyGodWS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})`);
          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectAttempts(prev => prev + 1);
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
  };

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    isConnected,
    data,
    lastAlert,
    reconnectAttempts,
    maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS
  };
}
