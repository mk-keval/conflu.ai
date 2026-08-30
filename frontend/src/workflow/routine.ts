/**
 * Daily Routine domain logic (Phase 1, gap #4).
 *
 * Pure functions for constructing and advancing a 4-step Daily Routine, so the
 * ordering/advance rules are unit-testable without touching the Zustand store
 * or localStorage. The store in `store/workflowStore.ts` delegates here.
 */

import type {
  DailyRoutine,
  RoutineStep,
  RoutineStepLabel,
  RoutineStepSeq,
} from '../types/workflow';

/** The four steps, in order, that make up a working-professional routine. */
export const ROUTINE_STEPS: readonly { seq: RoutineStepSeq; label: RoutineStepLabel }[] = [
  { seq: 1, label: 'Pre-Market' },
  { seq: 2, label: 'Market Open' },
  { seq: 3, label: 'Mid-Day' },
  { seq: 4, label: 'After-Close Journal' },
];

/** Build a fresh, all-pending routine for the given local date key. */
export function newRoutine(date: string, now: () => string = () => new Date().toISOString()): DailyRoutine {
  const steps: RoutineStep[] = ROUTINE_STEPS.map(({ seq, label }) => ({
    seq,
    step: label,
    status: 'pending',
    completedAt: null,
    data: undefined,
  }));
  return {
    date,
    currentStep: 0,
    status: 'in_progress',
    steps,
    updatedAt: now(),
  };
}

/**
 * Complete the given step (1-based seq) and return a NEW routine.
 * Steps must be completed in order (seq === currentStep + 1); anything else is
 * a no-op returning the input unchanged. Completing step 4 marks the routine
 * complete.
 */
export function completeRoutineStep(
  routine: DailyRoutine,
  seq: RoutineStepSeq,
  data?: Record<string, unknown>,
  now: () => string = () => new Date().toISOString()
): DailyRoutine {
  const index = seq - 1;
  // Ignore out-of-order / already-completed / out-of-range steps.
  if (index < 0 || index >= routine.steps.length) return routine;
  if (index !== routine.currentStep) return routine;
  if (routine.steps[index].status === 'completed') return routine;

  const steps = routine.steps.map((s, i) =>
    i === index ? { ...s, status: 'completed' as const, completedAt: now(), ...(data ? { data } : {}) } : s
  );
  const nextStep = index + 1;
  const isComplete = nextStep >= routine.steps.length;
  return {
    ...routine,
    steps,
    currentStep: isComplete ? routine.steps.length - 1 : nextStep,
    status: isComplete ? 'completed' : routine.status,
    updatedAt: now(),
  };
}
