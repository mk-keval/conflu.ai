import type { WSChannelType } from '@/types/ws';

export function priceChannel(symbol: string): string {
  return `price:${symbol}`;
}

export function indicatorChannel(symbol: string, name: string): string {
  return `indicator:${symbol}:${name}`;
}

export function signalChannel(symbol: string): string {
  return `signal:${symbol}`;
}

export function screenerChannel(name: string): string {
  return `screener:${name}`;
}

export function riskChannel(portfolioId: string): string {
  return `risk:${portfolioId}`;
}

export function backtestChannel(runId: string): string {
  return `backtest:${runId}`;
}

// Phase 8: Alert channels
export function alertUserChannel(userId: string): string {
  return `alert:user:${userId}`;
}

export function alertChannel(alertId: string): string {
  return `alert:${alertId}`;
}

// Phase 8: Replay channels
export function replayChannel(screenConfigId: string): string {
  return `replay:${screenConfigId}`;
}

// Phase 8: Shared screen channels
export function sharedScreenChannel(token: string): string {
  return `shared:${token}`;
}

export function parseChannel(channel: string): {
  type: WSChannelType;
  params: string[];
} {
  const parts = channel.split(':');
  const type = parts[0] as WSChannelType;
  const params = parts.slice(1);
  return { type, params };
}

const SEQUENCE_STORAGE_KEY = 'ws_sequences';

export function getStoredSequences(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(SEQUENCE_STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

export function storeSequence(channel: string, seq: number): void {
  const sequences = getStoredSequences();
  sequences[channel] = seq;
  localStorage.setItem(SEQUENCE_STORAGE_KEY, JSON.stringify(sequences));
}
