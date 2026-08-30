import { describe, it, expect } from 'vitest';
import { newRoutine } from '@/workflow/routine';
import {
  buildJournalData,
  formatStepTime,
  routineStepList,
  todayKey,
  JOURNAL_QUESTIONS,
} from '../DailyRoutine';

describe('JOURNAL_QUESTIONS', () => {
  it('defines the 3 thesis-vs-reality journal questions', () => {
    expect(JOURNAL_QUESTIONS).toHaveLength(3);
    expect(JOURNAL_QUESTIONS.map((q) => q.key)).toEqual(['q1', 'q2', 'q3']);
  });
});

describe('buildJournalData', () => {
  it('merges answers and stamps the journaledAt timestamp', () => {
    const data = buildJournalData({ q1: 'thesis', q2: 'reality', q3: 'do differently' });
    expect(data.q1).toBe('thesis');
    expect(data.q2).toBe('reality');
    expect(data.q3).toBe('do differently');
    expect(typeof data.journaledAt).toBe('string');
    expect(new Date(data.journaledAt as string).getTime()).not.toBeNaN();
  });
});

describe('todayKey', () => {
  it('returns a YYYY-MM-DD local date string', () => {
    const key = todayKey();
    expect(key).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe('routineStepList', () => {
  it('returns an empty list when routine is undefined', () => {
    expect(routineStepList(undefined)).toEqual([]);
  });

  it('flags exactly one step as next on an in_progress routine', () => {
    let r = newRoutine('2026-08-28', () => '2026-08-28T09:00:00.000Z');
    r = { ...r, currentStep: 2 }; // next step index 2 (seq 3)
    const list = routineStepList(r);
    expect(list.filter((s) => s.isNext)).toHaveLength(1);
    expect(list.find((s) => s.isNext)?.seq).toBe(3);
  });

  it('flags no step as next once the routine is completed', () => {
    let r = newRoutine('2026-08-28', () => '2026-08-28T09:00:00.000Z');
    r = { ...r, status: 'completed', currentStep: 3 };
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
