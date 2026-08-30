import { describe, it, expect } from 'vitest';
import {
  TRANCHES,
  convictionToLevel,
  splitShares,
  targetPriceAtRMul,
  scaleOutTargets,
  buildTranches,
  buildOcoBracket,
  buildExecutionPlan,
} from '../execution';
import type { ExecutionSetup } from '../../types/workflow';

const baseSetup: ExecutionSetup = {
  symbol: 'AAPL',
  conviction: 8,
  accountEquity: 25_000,
  entryLow: 200,
  entryHigh: 204,
  entryMid: 202,
  stopLoss: 196,
  targets: [214, 226],
  scaleOut: [
    { r_multiple: 2, size_pct: 50 },
    { r_multiple: 3, size_pct: 50 },
  ],
  timeStopDays: 5,
  triggerPrices: [202, 203, 204],
};

describe('TRANCHES', () => {
  it('is the 40/30/30 ladder', () => {
    expect([...TRANCHES]).toEqual([0.4, 0.3, 0.3]);
  });
});

describe('convictionToLevel', () => {
  it('maps >= 8 to high', () => {
    expect(convictionToLevel(8)).toBe('high');
    expect(convictionToLevel(10)).toBe('high');
  });
  it('maps 5-7 to medium', () => {
    expect(convictionToLevel(5)).toBe('medium');
    expect(convictionToLevel(7)).toBe('medium');
  });
  it('maps < 5 to low', () => {
    expect(convictionToLevel(4)).toBe('low');
    expect(convictionToLevel(0)).toBe('low');
  });
});

describe('splitShares', () => {
  it('splits 100 into 40/30/30', () => {
    expect(splitShares(100)).toEqual([40, 30, 30]);
  });
  it('floors each tranche and gives remainder to the first', () => {
    // 33 -> 13 / 9 / 11 (floor 13.2, floor 9.9, remainder 33-13-9=11)
    expect(splitShares(33)).toEqual([13, 9, 11]);
  });
  it('always totals the input for positive shares', () => {
    const total = 137;
    expect(splitShares(total).reduce((a, b) => a + b, 0)).toBe(total);
  });
  it('returns zeros for non-positive input', () => {
    expect(splitShares(0)).toEqual([0, 0, 0]);
    expect(splitShares(-5)).toEqual([0, 0, 0]);
  });
});

describe('targetPriceAtRMul', () => {
  it('computes price at r-multiple above long entry', () => {
    // risk = |202-196| = 6; 2R -> 202 + 12 = 214
    expect(targetPriceAtRMul(202, 196, 2)).toBeCloseTo(214);
  });
  it('handles a short (entry below stop) direction', () => {
    // risk = |198-204| = 6; short target at 1R below entry = 198 - 6 = 192
    expect(targetPriceAtRMul(198, 204, 1)).toBeCloseTo(192);
  });
  it('returns the entry price when risk is zero', () => {
    expect(targetPriceAtRMul(100, 100, 3)).toBe(100);
  });
});

describe('scaleOutTargets', () => {
  it('maps the plan scale-out with r-multiples and prices', () => {
    const targets = scaleOutTargets(baseSetup);
    expect(targets.map((t) => t.rMultiple)).toEqual([2, 3]);
    // Prefers the verdict's explicit price targets when present.
    expect(targets[0].targetPrice).toBeCloseTo(214);
    expect(targets[1].targetPrice).toBeCloseTo(226);
    expect(targets.map((t) => t.sizePct)).toEqual([50, 50]);
  });
  it('falls back to a single full-exit target when no plan', () => {
    const t = scaleOutTargets({ ...baseSetup, scaleOut: [] });
    expect(t).toHaveLength(1);
    expect(t[0].sizePct).toBe(100);
    expect(t[0].targetPrice).toBeCloseTo(214); // nearest target above entry
  });
});

describe('buildTranches', () => {
  it('assigns trigger prices from the plan scale-in', () => {
    const tranches = buildTranches(100, baseSetup);
    expect(tranches.map((t) => t.triggerPrice)).toEqual([202, 203, 204]);
  });
  it('first tranche stops at the structure stop, later at break-even', () => {
    const tranches = buildTranches(100, baseSetup);
    expect(tranches[0].stopPrice).toBe(196);
    expect(tranches[1].stopPrice).toBe(202);
    expect(tranches[2].stopPrice).toBe(202);
  });
  it('quantities sum to the total shares', () => {
    const tranches = buildTranches(137, baseSetup);
    expect(tranches.reduce((a, t) => a + t.qty, 0)).toBe(137);
  });
  it('falls back to entry-zone prices when no scale-in given', () => {
    const tranches = buildTranches(100, { ...baseSetup, triggerPrices: [] });
    expect(tranches[0].triggerPrice).toBe(202);
    expect(tranches[2].triggerPrice).toBe(204);
  });
});

describe('buildOcoBracket', () => {
  it('builds a broker-ready bracket', () => {
    const oco = buildOcoBracket(100, baseSetup);
    expect(oco.symbol).toBe('AAPL');
    expect(oco.stop_loss).toBe(196);
    expect(oco.time_stop_days).toBe(5);
    expect(oco.tranches).toHaveLength(3);
    expect(oco.tranches.reduce((a, t) => a + t.qty, 0)).toBe(100);
    expect(oco.targets).toHaveLength(2);
  });
});

describe('buildExecutionPlan', () => {
  it('assembles everything with the conviction level', () => {
    const plan = buildExecutionPlan(100, baseSetup);
    expect(plan.totalShares).toBe(100);
    expect(plan.convictionLevel).toBe('high');
    expect(plan.tranches).toHaveLength(3);
    expect(plan.oco.stop_loss).toBe(196);
    expect(plan.timeStopDays).toBe(5);
  });
});
