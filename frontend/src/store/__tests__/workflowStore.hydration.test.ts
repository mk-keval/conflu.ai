/**
 * hydrateFromJournal (D-68 P4 / R1) — the store is hydrated from the backend
 * journal API, replacing the previously-dead code path that left every
 * dashboard (Expectancy, Open Positions, Skill Score) permanently empty.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

vi.mock('@/api/client', () => ({
  default: { get: vi.fn() },
}));

import api from '@/api/client';
import { useWorkflowStore } from '../workflowStore';
import type { PaperTrade } from '@/types/workflow';

const mockedGet = vi.mocked(api.get);

beforeEach(() => {
  // Shallow merge (NOT replace) — preserves the store's action functions.
  useWorkflowStore.setState({
    dailyRoutines: {},
    validationGates: [],
    paperTrades: [],
  });
  mockedGet.mockReset();
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('workflowStore — hydrateFromJournal', () => {
  it('maps open + closed journal rows into paperTrades', async () => {
    mockedGet
      .mockResolvedValueOnce({
        data: {
          positions: [
            {
              date_entered: '2026-10-16',
              symbol: 'AAPL',
              entry_price: '228.50',
              stop_loss: '220.00',
              gate_verdict: 'PASS',
              realized_r: null,
              plan_adherence: null,
            },
          ],
        },
      })
      .mockResolvedValueOnce({
        data: {
          trades: [
            {
              date_entered: '2026-10-10',
              date_closed: '2026-10-14',
              symbol: 'MSFT',
              entry_price: '410.00',
              stop_loss: '395.00',
              gate_verdict: 'CONDITIONAL',
              exit_reason: 'target_1',
              realized_r: 1.8,
              plan_adherence: 0.85,
            },
          ],
        },
      });

    await useWorkflowStore.getState().hydrateFromJournal();

    const trades = useWorkflowStore.getState().paperTrades;
    expect(trades).toHaveLength(2);

    const open = trades.find((t) => t.status === 'open')!;
    expect(open.id).toBe('2026-10-16-AAPL-open');
    expect(open.symbol).toBe('AAPL');
    expect(open.entryPrice).toBe('228.50');
    expect(open.gateVerdict).toBe('PASS');
    expect(open.openedAt).toBe('2026-10-16');
    expect(open.closedAt).toBeNull();

    const closed = trades.find((t) => t.status === 'closed')!;
    expect(closed.id).toBe('2026-10-10-MSFT-closed');
    expect(closed.outcome).toBe('target_1');
    expect(closed.realizedR).toBe(1.8);
    expect(closed.adherencePct).toBe(0.85);
    expect(closed.stepsFollowed).toBe(Math.round(0.85 * 13));
    expect(closed.closedAt).toBe('2026-10-14');

    expect(mockedGet).toHaveBeenCalledWith('/api/v1/workflow/journal/open');
    expect(mockedGet).toHaveBeenCalledWith('/api/v1/workflow/journal/closed');
  });

  it('keeps existing paperTrades when the backend is unreachable', async () => {
    const sentinel = [
      { id: 'sentinel', symbol: 'OLD' },
    ] as unknown as PaperTrade[];
    useWorkflowStore.setState({ paperTrades: sentinel });
    mockedGet.mockRejectedValueOnce(new Error('backend down'));

    await useWorkflowStore.getState().hydrateFromJournal();

    const trades = useWorkflowStore.getState().paperTrades;
    expect(trades).toHaveLength(1);
    expect(trades[0].symbol).toBe('OLD');
  });
});
