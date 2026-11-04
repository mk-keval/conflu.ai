import { describe, it, expect } from 'vitest';
import {
  GATE_STEPS,
  renderGateResult,
  gateSummary,
  LIQUIDITY_MIN_AVG_DAILY_USD,
  RISK_REWARD_PASS,
  RISK_REWARD_CONDITIONAL,
  CONVICTION_HIGH,
  CONVICTION_LOW,
} from '../gate';
import type { ValidationGate, GateStepResult } from '../../types/workflow';

describe('GATE_STEPS', () => {
  it('defines the 7 steps in the elite order (matches backend)', () => {
    expect(GATE_STEPS.map((s) => s.name)).toEqual([
      'Liquidity',
      'Structure',
      'Positioning',
      'Catalyst',
      'Risk/Reward',
      'Portfolio Fit',
      'Conviction',
    ]);
  });
  it('keeps a plain-English question per step', () => {
    for (const s of GATE_STEPS) expect(s.question.length).toBeGreaterThan(15);
  });
});

describe('renderGateResult', () => {
  const createMockGate = (
    overrides: Partial<ValidationGate> = {}
  ): ValidationGate => ({
    id: 'test-1',
    symbol: 'AAPL',
    overall: 'PASS',
    stepResults: [
      { name: 'Liquidity', passed: true, note: 'Liquidity OK' },
      { name: 'Structure', passed: true, note: 'Structure OK' },
      {
        name: 'Positioning',
        passed: true,
        conditional: true,
        note: 'Positioning conditional',
      },
      { name: 'Catalyst', passed: true, note: 'Catalyst OK' },
      { name: 'Risk/Reward', passed: true, note: 'R/R OK' },
      {
        name: 'Portfolio Fit',
        passed: true,
        conditional: true,
        note: 'Portfolio Fit conditional',
      },
      { name: 'Conviction', passed: true, note: 'Conviction OK' },
    ],
    convictionScore: 8,
    dataGaps: ['Positioning', 'Portfolio Fit'],
    evaluatedAt: '2026-09-22T12:00:00Z',
    createdAt: '2026-09-22T12:00:00Z',
    ...overrides,
  });

  it('renders all 7 steps with correct status mapping', () => {
    const gate = createMockGate();
    const rendered = renderGateResult(gate);

    expect(rendered.steps).toHaveLength(7);
    expect(rendered.steps[0].name).toBe('Liquidity');
    expect(rendered.steps[0].status).toBe('pass');
    expect(rendered.steps[2].name).toBe('Positioning');
    expect(rendered.steps[2].status).toBe('conditional');
    expect(rendered.steps[5].name).toBe('Portfolio Fit');
    expect(rendered.steps[5].status).toBe('conditional');
  });

  it('maps passed=true, conditional=false → pass', () => {
    const gate = createMockGate({
      stepResults: [
        { name: 'Liquidity', passed: true, note: 'OK' } as GateStepResult,
      ],
    });
    const rendered = renderGateResult(gate);
    expect(rendered.steps[0].status).toBe('pass');
  });

  it('maps passed=false, conditional=true → conditional', () => {
    const gate = createMockGate({
      stepResults: [
        {
          name: 'Liquidity',
          passed: false,
          conditional: true,
          note: 'OK',
        } as GateStepResult,
      ],
    });
    const rendered = renderGateResult(gate);
    expect(rendered.steps[0].status).toBe('conditional');
  });

  it('maps passed=false, conditional=false → fail', () => {
    const gate = createMockGate({
      stepResults: [
        {
          name: 'Liquidity',
          passed: false,
          conditional: false,
          note: 'OK',
        } as GateStepResult,
      ],
    });
    const rendered = renderGateResult(gate);
    expect(rendered.steps[0].status).toBe('fail');
  });

  it('includes question from GATE_STEPS', () => {
    const gate = createMockGate();
    const rendered = renderGateResult(gate);
    expect(rendered.steps[0].question).toBe(GATE_STEPS[0].question);
  });

  it('passes through convictionScore, dataGaps, evaluatedAt', () => {
    const gate = createMockGate({
      convictionScore: 7,
      dataGaps: ['Positioning'],
      evaluatedAt: '2026-09-22T15:30:00Z',
    });
    const rendered = renderGateResult(gate);
    expect(rendered.convictionScore).toBe(7);
    expect(rendered.dataGaps).toEqual(['Positioning']);
    expect(rendered.evaluatedAt).toBe('2026-09-22T15:30:00Z');
  });

  it('handles missing note gracefully', () => {
    const gate = createMockGate({
      stepResults: [{ name: 'Liquidity', passed: true } as GateStepResult],
    });
    const rendered = renderGateResult(gate);
    expect(rendered.steps[0].note).toBe('');
  });
});

describe('gateSummary', () => {
  const createMockGate = (
    overrides: Partial<ValidationGate> = {}
  ): ValidationGate => ({
    id: 'test-1',
    symbol: 'AAPL',
    overall: 'PASS',
    stepResults: [
      { name: 'Liquidity', passed: true, note: 'OK' },
      { name: 'Structure', passed: true, note: 'OK' },
      { name: 'Positioning', passed: true, note: 'OK' },
      { name: 'Catalyst', passed: true, note: 'OK' },
      { name: 'Risk/Reward', passed: true, note: 'OK' },
      { name: 'Portfolio Fit', passed: true, note: 'OK' },
      { name: 'Conviction', passed: true, note: 'OK' },
    ],
    convictionScore: 8,
    dataGaps: [],
    evaluatedAt: '2026-09-22T12:00:00Z',
    createdAt: '2026-09-22T12:00:00Z',
    ...overrides,
  });

  it('returns PASS summary with step count and conviction', () => {
    const gate = createMockGate({ overall: 'PASS', convictionScore: 8 });
    const summary = gateSummary(gate);
    expect(summary).toContain('PASS');
    expect(summary).toContain('7/7');
    expect(summary).toContain('8/10');
  });

  it('returns CONDITIONAL summary with half-size note', () => {
    const gate = createMockGate({
      overall: 'CONDITIONAL',
      convictionScore: 6,
      stepResults: [
        { name: 'Liquidity', passed: true, note: 'OK' },
        { name: 'Structure', passed: true, note: 'OK' },
        {
          name: 'Positioning',
          passed: false,
          conditional: true,
          note: 'Missing data',
        },
        { name: 'Catalyst', passed: true, note: 'OK' },
        { name: 'Risk/Reward', passed: true, note: 'OK' },
        {
          name: 'Portfolio Fit',
          passed: false,
          conditional: true,
          note: 'No journal',
        },
        { name: 'Conviction', passed: true, note: 'OK' },
      ],
    });
    const summary = gateSummary(gate);
    expect(summary).toContain('CONDITIONAL');
    expect(summary).toContain('half-size');
    expect(summary).toContain('5/7');
    expect(summary).toContain('2 conditional');
    expect(summary).toContain('6/10');
  });

  it('returns FAIL summary', () => {
    const gate = createMockGate({
      overall: 'FAIL',
      convictionScore: 3,
      stepResults: [
        { name: 'Liquidity', passed: true, note: 'OK' },
        {
          name: 'Structure',
          passed: false,
          conditional: false,
          note: 'Failed',
        },
        { name: 'Positioning', passed: true, note: 'OK' },
        { name: 'Catalyst', passed: true, note: 'OK' },
        { name: 'Risk/Reward', passed: true, note: 'OK' },
        { name: 'Portfolio Fit', passed: true, note: 'OK' },
        { name: 'Conviction', passed: true, note: 'OK' },
      ],
    });
    const summary = gateSummary(gate);
    expect(summary).toContain('FAIL');
    expect(summary).toContain('6/7');
    expect(summary).toContain('3/10');
  });
});

describe('Threshold constants (match backend)', () => {
  it('LIQUIDITY_MIN_AVG_DAILY_USD is 10M', () => {
    expect(LIQUIDITY_MIN_AVG_DAILY_USD).toBe(10_000_000);
  });
  it('RISK_REWARD_PASS is 2.5', () => {
    expect(RISK_REWARD_PASS).toBe(2.5);
  });
  it('RISK_REWARD_CONDITIONAL is 2.0 (D1 tier)', () => {
    expect(RISK_REWARD_CONDITIONAL).toBe(2.0);
  });
  it('CONVICTION_HIGH is 7', () => {
    expect(CONVICTION_HIGH).toBe(7);
  });
  it('CONVICTION_LOW is 4', () => {
    expect(CONVICTION_LOW).toBe(4);
  });
});
