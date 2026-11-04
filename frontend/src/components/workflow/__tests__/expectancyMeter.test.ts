import { describe, expect, it } from 'vitest';
import type { PaperTrade } from '@/types/workflow';
import { calculateExpectancy } from '../ExpectancyMeter';

function trade(over: Partial<PaperTrade>): PaperTrade {
  return {
    id: 't',
    symbol: 'TEST',
    plan: {},
    fills: {},
    status: 'closed',
    outcome: 'target_hit',
    stepsFollowed: 0,
    stepsTotal: 13,
    adherencePct: 0,
    realizedR: 1,
    openedAt: '2026-10-01',
    closedAt: '2026-10-05',
    ...over,
  };
}

describe('calculateExpectancy', () => {
  it('skips out-of-sample rows (execution v0.1 legacy exclusion)', () => {
    const metrics = calculateExpectancy([
      trade({ id: 'keep', realizedR: 1 }),
      trade({ id: 'legacy', realizedR: -3, excludeFromStats: true }),
    ]);

    expect(metrics.tradeCount).toBe(1);
    expect(metrics.expectancy).toBe(1);
    expect(metrics.winRate).toBe(1);
  });
});
