import { describe, it, expect } from 'vitest';
import {
  GATE_STEPS,
  evaluateLiquidity,
  evaluateStructure,
  evaluateRiskReward,
  evaluateEdge,
  computeGate,
  buildGateResults,
  LIQUIDITY_MIN_AVG_DAILY_USD,
  CONVICTION_HIGH,
  CONVICTION_LOW,
  type GateInput,
} from '../gate';
import type { GateStepResult } from '../../types/workflow';

const baseInput: GateInput = {
  symbol: 'AAPL',
  dailyTrend: 'bullish',
  weeklyTrend: 'bullish',
  entryLow: 100,
  entryHigh: 102,
  stopLoss: 96,
  targets: [112, 120],
  conviction: 8,
  catalystBias: 'bullish',
};

describe('GATE_STEPS', () => {
  it('defines the 5 steps in the elite order', () => {
    expect(GATE_STEPS.map((s) => s.name)).toEqual([
      'Liquidity',
      'Structure',
      'Risk/Reward',
      'Edge Check',
      'Conviction',
    ]);
  });
  it('keeps a plain-English question per step', () => {
    for (const s of GATE_STEPS) expect(s.question.length).toBeGreaterThan(15);
  });
});

describe('evaluateLiquidity', () => {
  it('passes when ADV is above the floor', () => {
    const r = evaluateLiquidity({ symbol: 'X', avgDailyVolumeUsd: 40_000_000 });
    expect(r.passed).toBe(true);
    expect(r.conditional).toBeUndefined();
  });
  it('passes exactly at the floor', () => {
    const r = evaluateLiquidity({ symbol: 'X', avgDailyVolumeUsd: LIQUIDITY_MIN_AVG_DAILY_USD });
    expect(r.passed).toBe(true);
  });
  it('is conditional between half and the floor', () => {
    const r = evaluateLiquidity({ symbol: 'X', avgDailyVolumeUsd: 7_000_000 });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBe(true);
  });
  it('fails below half the floor', () => {
    const r = evaluateLiquidity({ symbol: 'X', avgDailyVolumeUsd: 2_000_000 });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBeFalsy();
  });
  it('is conditional when no volume data is present (honest unknown)', () => {
    const r = evaluateLiquidity({ symbol: 'X' });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBe(true);
  });
  it('uses volume ratio as a secondary signal', () => {
    const r = evaluateLiquidity({ symbol: 'X', volumeRatio: 1.6 });
    expect(r.passed).toBe(true);
    expect(r.conditional).toBe(true);
  });
});

describe('evaluateStructure', () => {
  it('passes on aligned bullish weekly + daily', () => {
    const r = evaluateStructure(baseInput);
    expect(r.passed).toBe(true);
  });
  it('passes on aligned bearish weekly + daily', () => {
    const r = evaluateStructure({ ...baseInput, dailyTrend: 'bearish', weeklyTrend: 'bearish' });
    expect(r.passed).toBe(true);
  });
  it('is conditional on a counter-trend daily-vs-weekly', () => {
    const r = evaluateStructure({ ...baseInput, dailyTrend: 'bullish', weeklyTrend: 'bearish' });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBe(true);
  });
  it('is conditional when a timeframe trend is missing', () => {
    const r = evaluateStructure({ ...baseInput, weeklyTrend: null });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBe(true);
  });
  it('is conditional on mixed trends that are not clearly aligned', () => {
    const r = evaluateStructure({ ...baseInput, dailyTrend: 'mixed', weeklyTrend: 'bullish' });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBe(true);
  });
});

describe('evaluateRiskReward', () => {
  it('prefers the backend-computed R:R (pass at 2.5+)', () => {
    const r = evaluateRiskReward({ ...baseInput, riskReward: 3.0 });
    expect(r.passed).toBe(true);
  });
  it('is conditional between 2.0 and 2.5', () => {
    const r = evaluateRiskReward({ ...baseInput, riskReward: 2.2 });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBe(true);
  });
  it('fails below 2.0', () => {
    const r = evaluateRiskReward({ ...baseInput, riskReward: 1.4 });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBeFalsy();
  });
  it('derives R:R from raw entry/stop/target when not provided', () => {
    // entry 101, stop 96 => risk 5; target 112 => reward 11 => 2.2 : 1
    const r = evaluateRiskReward({ ...baseInput, riskReward: null });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBe(true);
  });
  it('is conditional when it cannot compute an R:R at all', () => {
    const r = evaluateRiskReward({ symbol: 'X' });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBe(true);
  });
});

describe('evaluateEdge', () => {
  it('passes on high conviction with a supportive catalyst', () => {
    const r = evaluateEdge({ ...baseInput, conviction: CONVICTION_HIGH });
    expect(r.passed).toBe(true);
  });
  it('is conditional when the catalyst signal is absent', () => {
    const r = evaluateEdge({ ...baseInput, catalystBias: null });
    expect(r.passed).toBe(true);
    expect(r.conditional).toBe(true);
  });
  it('is conditional on moderate conviction', () => {
    const r = evaluateEdge({ ...baseInput, conviction: 5 });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBe(true);
  });
  it('fails on weak conviction', () => {
    const r = evaluateEdge({ ...baseInput, conviction: CONVICTION_LOW - 1 });
    expect(r.passed).toBe(false);
    expect(r.conditional).toBeFalsy();
  });
  it('fails when the catalyst is explicitly against the trade', () => {
    const r = evaluateEdge({ ...baseInput, conviction: CONVICTION_HIGH, catalystBias: 'cautious' });
    expect(r.passed).toBe(false);
  });
});

describe('computeGate', () => {
  const passResult: GateStepResult[] = [
    { name: 'Liquidity', passed: true },
    { name: 'Structure', passed: true },
    { name: 'Risk/Reward', passed: true },
    { name: 'Edge Check', passed: true },
    { name: 'Conviction', passed: true },
  ];
  it('passes only when every step is a hard pass', () => {
    expect(computeGate(passResult).overall).toBe('PASS');
  });
  it('fails on any hard fail', () => {
    const r = computeGate([{ ...passResult[0], passed: false }]);
    expect(r.overall).toBe('FAIL');
  });
  it('is conditional when any step is conditional but none hard-fail', () => {
    const r = computeGate([{ ...passResult[0], passed: false, conditional: true }]);
    expect(r.overall).toBe('CONDITIONAL');
  });
});

describe('buildGateResults', () => {
  it('returns all 5 steps in order, ending with Conviction', () => {
    const results = buildGateResults({ ...baseInput, avgDailyVolumeUsd: 50_000_000 }, 8);
    expect(results.map((r) => r.name)).toEqual([
      'Liquidity',
      'Structure',
      'Risk/Reward',
      'Edge Check',
      'Conviction',
    ]);
  });
  it('maps a high conviction score to a passing Conviction step', () => {
    const results = buildGateResults(baseInput, CONVICTION_HIGH);
    expect(results[4].passed).toBe(true);
  });
  it('maps a low conviction score to a failing Conviction step', () => {
    const results = buildGateResults(baseInput, 3);
    expect(results[4].passed).toBe(false);
  });
  it('clamps conviction to 0-10', () => {
    const high = buildGateResults(baseInput, 99)[4];
    const low = buildGateResults(baseInput, -5)[4];
    expect(high.passed).toBe(true);
    expect(low.passed).toBe(false);
  });
});
