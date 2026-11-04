import { describe, it, expect } from 'vitest';
import {
  PLAN_STEP_DEFS,
  PLAN_STEP_COUNT,
  scorePlanSteps,
  planStepGroups,
} from '../planSteps';
import {
  ADHERENCE_MAX_STEPS,
  PAPER_TRADE_PLAN_STEPS,
} from '../../types/workflow';

describe('PLAN_STEP_DEFS', () => {
  it('has exactly the 13-step taxonomy (== ADHERENCE_MAX_STEPS)', () => {
    expect(PLAN_STEP_COUNT).toBe(ADHERENCE_MAX_STEPS);
    expect(PLAN_STEP_DEFS).toHaveLength(13);
  });

  it('matches the PAPER_TRADE_PLAN_STEPS category counts', () => {
    const count = (k: keyof typeof PAPER_TRADE_PLAN_STEPS) =>
      PLAN_STEP_DEFS.filter((s) => s.key === k).length;
    expect(count('validation_gate')).toBe(
      PAPER_TRADE_PLAN_STEPS.validation_gate
    ); // 5
    expect(count('entry_tranches')).toBe(PAPER_TRADE_PLAN_STEPS.entry_tranches); // 3
    expect(count('stop_respected')).toBe(PAPER_TRADE_PLAN_STEPS.stop_respected); // 1
    expect(count('target_hits')).toBe(PAPER_TRADE_PLAN_STEPS.target_hits); // 3
    expect(count('time_stop_honored')).toBe(
      PAPER_TRADE_PLAN_STEPS.time_stop_honored
    ); // 1
  });

  it('every def has a key, label, and group', () => {
    for (const s of PLAN_STEP_DEFS) {
      expect(s.key).toBeTruthy();
      expect(s.label.length).toBeGreaterThan(0);
      expect(s.group).toBeTruthy();
    }
  });
});

describe('scorePlanSteps', () => {
  it('scores all-13 checked as 13/13', () => {
    const res = scorePlanSteps(PLAN_STEP_DEFS.map(() => true));
    expect(res).toEqual({ stepsFollowed: 13, stepsTotal: 13 });
  });

  it('scores none checked as 0/13', () => {
    const res = scorePlanSteps(PLAN_STEP_DEFS.map(() => false));
    expect(res).toEqual({ stepsFollowed: 0, stepsTotal: 13 });
  });

  it('counts only the checked steps', () => {
    const checked = PLAN_STEP_DEFS.map((_, i) => i % 2 === 0);
    const res = scorePlanSteps(checked);
    expect(res.stepsFollowed).toBe(7); // indices 0,2,4,6,8,10,12
    expect(res.stepsTotal).toBe(13);
  });

  it('treats a short array (missing entries) as not followed but keeps 13 total', () => {
    const res = scorePlanSteps([true, true, true]);
    expect(res.stepsFollowed).toBe(3);
    expect(res.stepsTotal).toBe(13);
  });

  it('handles an empty array as 0/13', () => {
    const res = scorePlanSteps([]);
    expect(res).toEqual({ stepsFollowed: 0, stepsTotal: 13 });
  });
});

describe('planStepGroups', () => {
  it('returns the three groups in order with correct totals', () => {
    const groups = planStepGroups();
    expect(groups.map((g) => g.group)).toEqual([
      'Validation Gate',
      'Entry',
      'Execution Discipline',
    ]);
    expect(groups[0].steps).toHaveLength(5);
    expect(groups[1].steps).toHaveLength(3);
    expect(groups[2].steps).toHaveLength(5); // stop(1) + targets(3) + time stop(1)
  });

  it('groups cover every def exactly once', () => {
    const all = planStepGroups().flatMap((g) => g.steps);
    expect(all).toHaveLength(PLAN_STEP_DEFS.length);
    expect(new Set(all.map((s) => s.label)).size).toBe(PLAN_STEP_DEFS.length);
  });
});
