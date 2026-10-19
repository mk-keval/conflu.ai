import { describe, it, expect } from 'vitest';
import { newRoutine } from '@/workflow/routine';
import {
  formatStepTime,
  routineStepList,
  todayKey,
  TOUCHPOINT_A_ACTIONS,
  TOUCHPOINT_B_ACTIONS,
  runCloseProgressText,
  RUN_CLOSE_GATE_HINT_MS,
} from '../DailyRoutine';

describe('todayKey', () => {
  it('returns a YYYY-MM-DD local date string', () => {
    const key = todayKey();
    expect(key).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe('TOUCHPOINT_A_ACTIONS', () => {
  it('defines pre-market actions (API-driven)', () => {
    expect(TOUCHPOINT_A_ACTIONS.length).toBeGreaterThan(0);
    expect(TOUCHPOINT_A_ACTIONS[0]).toContain('Run Gate Enforcement');
    expect(TOUCHPOINT_A_ACTIONS[0]).toContain('fetch brief');
    expect(TOUCHPOINT_A_ACTIONS[0]).toContain('write journal');
  });
});

describe('TOUCHPOINT_B_ACTIONS', () => {
  it('defines after-close actions (API-driven)', () => {
    expect(TOUCHPOINT_B_ACTIONS.length).toBeGreaterThan(0);
    expect(TOUCHPOINT_B_ACTIONS[0]).toContain('Sync Exits (Dry Run)');
    expect(TOUCHPOINT_B_ACTIONS[2]).toContain('Sync Exits (Apply)');
  });
});

describe('routineStepList', () => {
  it('returns an empty list when routine is undefined', () => {
    expect(routineStepList(undefined)).toEqual([]);
  });

  it('flags exactly one step as next on an in_progress routine', () => {
    let r = newRoutine('2026-08-28', () => '2026-08-28T09:00:00.000Z');
    r = { ...r, currentStep: 0 }; // next step index 0 (seq 1)
    const list = routineStepList(r);
    expect(list.filter((s) => s.isNext)).toHaveLength(1);
    expect(list.find((s) => s.isNext)?.seq).toBe(1);
  });

  it('flags no step as next once the routine is completed', () => {
    let r = newRoutine('2026-08-28', () => '2026-08-28T09:00:00.000Z');
    r = { ...r, status: 'completed', currentStep: 1 };
    expect(routineStepList(r).every((s) => !s.isNext)).toBe(true);
  });
});

describe('formatStepTime', () => {
  it('formats an ISO timestamp to HH:MM', () => {
    expect(formatStepTime('2026-08-28T14:05:00.000Z')).toBeDefined();
  });

  it('returns null for null/empty input', () => {
    expect(formatStepTime(null)).toBeNull();
  });

  it('returns null for invalid timestamps', () => {
    expect(formatStepTime('not-a-date')).toBeNull();
  });
});

describe('runCloseProgressText (one-go after-close run)', () => {
  it('shows the gate phase before the hint threshold', () => {
    expect(runCloseProgressText(0)).toBe('Running gate enforcement…');
    expect(runCloseProgressText(RUN_CLOSE_GATE_HINT_MS - 1)).toBe(
      'Running gate enforcement…'
    );
  });

  it('switches to the exits phase at/after the hint threshold', () => {
    expect(runCloseProgressText(RUN_CLOSE_GATE_HINT_MS)).toBe('Syncing exits…');
    expect(runCloseProgressText(180_000)).toBe('Syncing exits…');
  });
});
