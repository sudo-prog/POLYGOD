import { useEffect, useState } from 'react';
import { useStore } from '../store';

export function usePolyGodWS() {
  const [isConnected, setIsConnected] = useState(false);
  const [data, setData] = useState(null);
  const [lastAlert, setLastAlert] = useState<string | null>(null);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/rag-god');

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const messageData = JSON.parse(event.data);
      setData(messageData);
      useStore.getState().updateRAGGod?.(messageData);

      // Set last alert if the message contains alert information
      if (messageData.alert) {
        setLastAlert(messageData.alert);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    ws.onerror = () => {
      setIsConnected(false);
    };

    return () => ws.close();
  }, []);

  return {
    isConnected,
    data,
    lastAlert
  };
}
