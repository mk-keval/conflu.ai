import { createContext, useContext, type ReactNode } from 'react';
import { useWebSocket } from './useWebSocket';
import type { ConnectionState, WSMessage } from '@/types/ws';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:5173/ws/stream';

interface WebSocketContextType {
  connectionState: ConnectionState;
  subscribe: (channel: string) => void;
  unsubscribe: (channel: string) => void;
  send: (data: unknown) => void;
  onMessage: (handler: (message: WSMessage) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const ws = useWebSocket(WS_URL);

  return (
    <WebSocketContext.Provider value={ws}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWS(): WebSocketContextType {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error('useWS must be used within a WebSocketProvider');
  }
  return ctx;
}
