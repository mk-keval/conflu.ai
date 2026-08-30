import { describe, it, expect } from 'vitest';
import {
  adherencePct,
  rollingAdherence,
  adherenceStreak,
  selectAdherence,
} from '../adherence';
import {
  ADHERENCE_MAX_STEPS,
  type PaperTrade,
} from '../../types/workflow';

function trade(overrides: Partial<PaperTrade> & { id: string }): PaperTrade {
  return {
    symbol: 'AAPL',
    plan: {},
    fills: {},
    status: 'closed',
    outcome: 'target_hit',
    stepsFollowed: 13,
    stepsTotal: 13,
    adherencePct: 100,
    openedAt: '2026-08-01T00:00:00.000Z',
    closedAt: '2026-08-01T20:00:00.000Z',
    ...overrides,
  };
}

describe('adherencePct', () => {
  it('returns 100 for a fully adhered trade', () => {
    expect(adherencePct(13, 13)).toBe(100);
  });

  it('computes a rounded percentage', () => {
    // 10/13 = 76.923... → 76.92
    expect(adherencePct(10, 13)).toBe(76.92);
  });

  it('clamps adherence to [0, 100]', () => {
    expect(adherencePct(0, 13)).toBe(0);
    expect(adherencePct(30, 13)).toBe(100); // impossible numerator
  });

  it('caps the denominator at ADHERENCE_MAX_STEPS (13)', () => {
    expect(adherencePct(13, 99)).toBe(100); // 99 clamped to 13
    expect(ADHERENCE_MAX_STEPS).toBe(13);
  });

  it('guards against a zero denominator', () => {
    expect(adherencePct(0, 0)).toBe(0);
  });
});

describe('rollingAdherence', () => {
  it('returns an empty result when there are no closed trades', () => {
    expect(rollingAdherence([])).toEqual({ pct: 0, count: 0, full: false });
  });

  it('averages over the most recent `window` trades', () => {
    const trades = [
      trade({ id: '1', stepsFollowed: 13, stepsTotal: 13, adherencePct: 100 }),
      trade({ id: '2', stepsFollowed: 10, stepsTotal: 13, adherencePct: 76.92 }),
      trade({ id: '3', stepsFollowed: 7, stepsTotal: 13, adherencePct: 53.85 }),
    ];
    const res = rollingAdherence(trades, 2);
    expect(res.count).toBe(2);
    // (76.92 + 53.85) / 2 = 65.385 → 65.39
    expect(res.pct).toBe(65.39);
    expect(res.full).toBe(true);
  });

  it('reports not-full when fewer than window trades exist', () => {
    const trades = [trade({ id: '1', adherencePct: 100 })];
    const res = rollingAdherence(trades, 20);
    expect(res.count).toBe(1);
    expect(res.full).toBe(false);
    expect(res.pct).toBe(100);
  });

  it('ignores open trades (not yet closed)', () => {
    const open = trade({ id: 'OPEN', status: 'open', outcome: 'open', closedAt: null });
    const closed1 = trade({ id: '1', adherencePct: 50 });
    const res = rollingAdherence([open, closed1], 20);
    expect(res.count).toBe(1);
    expect(res.pct).toBe(50);
  });
});

describe('adherenceStreak', () => {
  it('counts consecutive most-recent trades at or above the benchmark', () => {
    const trades = [
      trade({ id: '1', adherencePct: 100 }),
      trade({ id: '2', adherencePct: 90 }),
      trade({ id: '3', adherencePct: 100 }),
      trade({ id: '4', adherencePct: 40 }), // breaks the streak
      trade({ id: '5', adherencePct: 100 }), // most recent
    ];
    expect(adherenceStreak(trades)).toBe(1);
  });

  it('returns 0 on an empty set', () => {
    expect(adherenceStreak([])).toBe(0);
  });

  it('counts a long unbroken run', () => {
    const trades = [1, 2, 3].map((n) =>
      trade({ id: String(n), adherencePct: 100 })
    );
    expect(adherenceStreak(trades)).toBe(3);
  });
});

describe('selectAdherence', () => {
  it('combines rolling + streak', () => {
    const trades = [
      trade({ id: '1', adherencePct: 100 }),
      trade({ id: '2', adherencePct: 100 }),
    ];
    const res = selectAdherence(trades, 20);
    expect(res.rolling.pct).toBe(100);
    expect(res.rolling.count).toBe(2);
    expect(res.streak).toBe(2);
  });
});
