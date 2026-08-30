import { describe, it, expect } from 'vitest';
import { newRoutine, completeRoutineStep, ROUTINE_STEPS } from '../routine';

const NOW = '2026-08-28T09:00:00.000Z';

describe('newRoutine', () => {
  it('creates four pending steps in the correct order', () => {
    const r = newRoutine('2026-08-28', () => NOW);
    expect(r.date).toBe('2026-08-28');
    expect(r.currentStep).toBe(0);
    expect(r.status).toBe('in_progress');
    expect(r.steps).toHaveLength(4);
    expect(r.steps.every((s) => s.status === 'pending')).toBe(true);
    expect(ROUTINE_STEPS.map((s) => s.label)).toEqual([
      'Pre-Market',
      'Market Open',
      'Mid-Day',
      'After-Close Journal',
    ]);
  });
});

describe('completeRoutineStep', () => {
  it('completes steps in order, advancing currentStep', () => {
    let r = newRoutine('2026-08-28', () => NOW);
    r = completeRoutineStep(r, 1, undefined, () => NOW);
    expect(r.steps[0].status).toBe('completed');
    expect(r.currentStep).toBe(1);
    r = completeRoutineStep(r, 2, undefined, () => NOW);
    expect(r.currentStep).toBe(2);
  });

  it('leaves state unchanged on out-of-order steps', () => {
    let r = newRoutine('2026-08-28', () => NOW);
    const before = r;
    r = completeRoutineStep(r, 2); // skipping step 1 is not allowed
    expect(r).toBe(before);
  });

  it('ignores already-completed steps', () => {
    let r = newRoutine('2026-08-28', () => NOW);
    r = completeRoutineStep(r, 1);
    const before = r;
    r = completeRoutineStep(r, 1); // re-completing step 1 is a no-op
    expect(r).toBe(before);
  });

  it('marks the routine complete when step 4 finishes', () => {
    let r = newRoutine('2026-08-28', () => NOW);
    r = completeRoutineStep(r, 1);
    r = completeRoutineStep(r, 2);
    r = completeRoutineStep(r, 3);
    r = completeRoutineStep(r, 4);
    expect(r.status).toBe('completed');
    expect(r.steps.every((s) => s.status === 'completed')).toBe(true);
  });

  it('stores optional per-step data', () => {
    let r = newRoutine('2026-08-28', () => NOW);
    r = completeRoutineStep(r, 1);
    r = completeRoutineStep(r, 2);
    r = completeRoutineStep(r, 3);
    r = completeRoutineStep(r, 4, { journal: 'thesis still valid' });
    expect(r.steps[3].data).toEqual({ journal: 'thesis still valid' });
  });
});
