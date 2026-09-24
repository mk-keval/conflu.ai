import { describe, it, expect, beforeEach } from 'vitest';
import { useWorkflowStore } from '../workflowStore';

const { getState, setState } = useWorkflowStore;

beforeEach(() => {
  // Shallow merge (NOT replace) — preserves the store's action functions.
  setState({
    dailyRoutines: {},
    validationGates: [],
    paperTrades: [],
  });
});

describe('workflowStore — Daily Routine', () => {
  it('creates a routine on first access and returns it on subsequent access', () => {
    const first = getState().getOrCreateRoutine('2026-08-28');
    expect(first.steps).toHaveLength(2); // 2 touchpoints (Slice 3)
    const again = getState().getOrCreateRoutine('2026-08-28');
    expect(again).toBe(first); // same reference → idempotent
  });

  it('completes touchpoints in order', () => {
    getState().getOrCreateRoutine('2026-08-28');
    getState().completeRoutineStep('2026-08-28', 1);
    let r = getState().dailyRoutines['2026-08-28'];
    expect(r.steps[0].status).toBe('completed');
    expect(r.currentStep).toBe(1);

    // Complete touchpoint 2 (now the next step) - should succeed
    getState().completeRoutineStep('2026-08-28', 2);
    r = getState().dailyRoutines['2026-08-28'];
    expect(r.steps[1].status).toBe('completed');
    expect(r.status).toBe('completed');
  });
});

describe('workflowStore — Validation Gate', () => {
  it('records a gate with generated id + timestamp + dataGaps + evaluatedAt', () => {
    const created = getState().recordGate({
      symbol: 'AAPL',
      stepResults: [
        { name: 'Liquidity', passed: true },
        { name: 'Structure', passed: false, conditional: true },
      ],
      overall: 'CONDITIONAL',
      convictionScore: 6,
      dataGaps: ['Structure'],
      evaluatedAt: '2026-09-22T12:00:00Z',
    });
    expect(created.id).toBeTruthy();
    expect(created.createdAt).toBeTruthy();
    expect(created.dataGaps).toEqual(['Structure']);
    expect(created.evaluatedAt).toBe('2026-09-22T12:00:00Z');
    expect(getState().validationGates).toHaveLength(1);
    expect(getState().validationGates[0].overall).toBe('CONDITIONAL');
  });
});

describe('workflowStore — Paper Trades + adherence', () => {
  it('opens a trade then closes it computing adherence', () => {
    const opened = getState().openPaperTrade({
      symbol: 'AAPL',
      plan: {},
      fills: {},
      stepsFollowed: 0,
      stepsTotal: 13,
    });
    expect(opened.status).toBe('open');
    expect(opened.adherencePct).toBe(0);

    getState().closePaperTrade(opened.id, 'target_hit', 10, 13);
    const closed = getState().paperTrades.find((t) => t.id === opened.id)!;
    expect(closed.status).toBe('closed');
    expect(closed.outcome).toBe('target_hit');
    expect(closed.adherencePct).toBe(76.92);
    expect(closed.closedAt).toBeTruthy();
  });

  it('rolls up adherence across multiple closed trades', () => {
    const t1 = getState().openPaperTrade({
      symbol: 'A',
      plan: {},
      fills: {},
      stepsFollowed: 0,
      stepsTotal: 13,
    });
    const t2 = getState().openPaperTrade({
      symbol: 'B',
      plan: {},
      fills: {},
      stepsFollowed: 0,
      stepsTotal: 13,
    });
    getState().closePaperTrade(t1.id, 'target_hit', 13, 13);
    getState().closePaperTrade(t2.id, 'target_hit', 7, 13);
    const trades = getState().paperTrades;
    expect(trades).toHaveLength(2);
    expect(trades[0].adherencePct).toBe(100);
    expect(trades[1].adherencePct).toBe(53.85);
  });
});

describe('workflowStore — reset', () => {
  it('clears all workflow state', () => {
    getState().getOrCreateRoutine('2026-08-28');
    getState().recordGate({
      symbol: 'A',
      stepResults: [],
      overall: 'PASS',
      convictionScore: 8,
      dataGaps: [],
      evaluatedAt: '2026-09-22T12:00:00Z',
    });
    expect(getState().dailyRoutines['2026-08-28']).toBeTruthy();
    getState().resetWorkflow();
    expect(getState().dailyRoutines).toEqual({});
    expect(getState().validationGates).toEqual([]);
    expect(getState().paperTrades).toEqual([]);
  });
});
