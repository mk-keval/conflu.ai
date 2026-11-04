import { useState, useCallback, useRef, useEffect } from 'react';
import type { ConnectionState, WSMessage } from '@/types/ws';
import { getStoredSequences, storeSequence } from './channels';

const MAX_RECONNECT_DELAY = 30_000;

interface UseWebSocketReturn {
  connectionState: ConnectionState;
  subscribe: (channel: string) => void;
  unsubscribe: (channel: string) => void;
  send: (data: unknown) => void;
  onMessage: (handler: (message: WSMessage) => void) => () => void;
}

export function useWebSocket(url: string): UseWebSocketReturn {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const subscriptionsRef = useRef<Set<string>>(new Set());
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );
  const handlersRef = useRef<Set<(message: WSMessage) => void>>(new Set());
  const mountedRef = useRef(true);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data) as WSMessage;
      if (
        'channel' in message &&
        'sequence' in message &&
        typeof message.sequence === 'number'
      ) {
        storeSequence(message.channel as string, message.sequence as number);
      }
      handlersRef.current.forEach((handler) => {
        try {
          handler(message);
        } catch {
          // Handler error - ignore to keep other handlers working
        }
      });
    } catch {
      // Parse error - ignore malformed messages
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    const delay = Math.min(
      1000 * Math.pow(2, reconnectAttemptRef.current),
      MAX_RECONNECT_DELAY
    );
    reconnectAttemptRef.current++;
    setConnectionState('reconnecting');
    reconnectTimeoutRef.current = setTimeout(() => {
      if (mountedRef.current) {
        connect();
      }
    }, delay);
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setConnectionState('connecting');
    const ws = new WebSocket(url);

    ws.onopen = () => {
      if (!mountedRef.current) {
        ws.close();
        return;
      }
      setConnectionState('connected');
      reconnectAttemptRef.current = 0;

      // Resubscribe to all channels
      subscriptionsRef.current.forEach((ch) => {
        ws.send(JSON.stringify({ type: 'subscribe', channels: [ch] }));
      });

      // Send resync with stored sequences
      const sequences = getStoredSequences();
      const maxSeq = Math.max(0, ...Object.values(sequences));
      if (maxSeq > 0) {
        ws.send(JSON.stringify({ type: 'resync', last_sequence: maxSeq }));
      }
    };

    ws.onmessage = handleMessage;

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setConnectionState('disconnected');
      scheduleReconnect();
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [url, handleMessage, scheduleReconnect]);

  const subscribe = useCallback((channel: string) => {
    subscriptionsRef.current.add(channel);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: 'subscribe', channels: [channel] })
      );
    }
  }, []);

  const unsubscribe = useCallback((channel: string) => {
    subscriptionsRef.current.delete(channel);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: 'unsubscribe', channels: [channel] })
      );
    }
  }, []);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const onMessage = useCallback((handler: (message: WSMessage) => void) => {
    handlersRef.current.add(handler);
    return () => {
      handlersRef.current.delete(handler);
    };
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    connectionState,
    subscribe,
    unsubscribe,
    send,
    onMessage,
  };
}
