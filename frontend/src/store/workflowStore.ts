/**
 * Guided-workflow state store (Phase 1, gap #4) — persisted to localStorage.
 *
 * This is the THIN, ABSTRACTED persistence layer for Daily Routine, Validation
 * Gates, and Paper Trades + adherence. Design constraints (D-A v2.1):
 *   - Persists via Zustand `persist` → localStorage under a versioned key.
 *   - Exposes only plain read/write actions — NO HTTP / API coupling. A future
 *     backend or offline/sync layer can hydrate the same shape without touching
 *     the components that consume this store (Sprints 2-8).
 *   - Domain logic (routine advance rules, adherence math) lives in the pure
 *     modules `workflow/routine.ts` and `workflow/adherence.ts`; the store just
 *     holds state and delegates, keeping it testable with zero DOM.
 */

import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { useMemo } from 'react';
import {
  adherencePct,
  selectAdherence,
  type RollingAdherence,
} from '../workflow/adherence';
import {
  completeRoutineStep as advanceRoutine,
  newRoutine,
} from '../workflow/routine';
import type {
  DailyRoutine,
  GateStepResult,
  GateVerdict,
  PaperTrade,
  PaperTradeOutcome,
  RoutineStepSeq,
  ValidationGate,
} from '../types/workflow';

/** localStorage key — bump the `-vN` suffix on any breaking shape change. */
const STORAGE_KEY = 'conflu-workflow-v1';

/**
 * In-memory storage used only when `localStorage` is unavailable (e.g. the
 * vitest Node environment). Keeps the store importable/testable without a DOM
 * while persisting normally in the browser.
 */
function memoryStorage(): Storage {
  const map = new Map<string, string>();
  return {
    getItem: (k) => map.get(k) ?? null,
    setItem: (k, v) => void map.set(k, v),
    removeItem: (k) => void map.delete(k),
    clear: () => void map.clear(),
    key: (_i) => null,
    get length() {
      return map.size;
    },
  };
}

/** Default rolling window for the 20-trade adherence metric. */
export const ADHERENCE_WINDOW = 20;

interface WorkflowState {
  // persisted
  dailyRoutines: Record<string, DailyRoutine>;
  validationGates: ValidationGate[];
  paperTrades: PaperTrade[];
}

interface WorkflowActions {
  // Daily Routine
  getRoutine: (date: string) => DailyRoutine | undefined;
  getOrCreateRoutine: (date: string) => DailyRoutine;
  completeRoutineStep: (date: string, seq: RoutineStepSeq, data?: Record<string, unknown>) => void;
  // Validation Gate
  recordGate: (gate: Omit<ValidationGate, 'id' | 'createdAt'>) => ValidationGate;
  // Paper Trades
  openPaperTrade: (trade: Omit<PaperTrade, 'id' | 'status' | 'outcome' | 'adherencePct' | 'openedAt' | 'closedAt'>) => PaperTrade;
  closePaperTrade: (
    id: string,
    outcome: Exclude<PaperTradeOutcome, 'open'>,
    stepsFollowed: number,
    stepsTotal: number
  ) => void;
  // Reset (admin/debug)
  resetWorkflow: () => void;
}

export type WorkflowStore = WorkflowState & WorkflowActions;

function newId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function emptyState(): WorkflowState {
  return { dailyRoutines: {}, validationGates: [], paperTrades: [] };
}

export const useWorkflowStore = create<WorkflowStore>()(
  persist(
    (set, get) => ({
      ...emptyState(),

      // ── Daily Routine ──

      getRoutine: (date) => get().dailyRoutines[date],

      getOrCreateRoutine: (date) => {
        const existing = get().dailyRoutines[date];
        if (existing) return existing;
        const routine = newRoutine(date);
        set((state) => ({
          dailyRoutines: { ...state.dailyRoutines, [date]: routine },
        }));
        return routine;
      },

      completeRoutineStep: (date, seq, data) => {
        const routine = get().dailyRoutines[date];
        if (!routine) return;
        const advanced = advanceRoutine(routine, seq, data);
        if (advanced === routine) return; // out-of-order / no-op
        set((state) => ({
          dailyRoutines: { ...state.dailyRoutines, [date]: advanced },
        }));
      },

      // ── Validation Gate ──

      recordGate: (gate) => {
        const created: ValidationGate = {
          ...gate,
          id: newId(),
          createdAt: new Date().toISOString(),
        };
        set((state) => ({ validationGates: [...state.validationGates, created] }));
        return created;
      },

      // ── Paper Trades + adherence ──

      openPaperTrade: (trade) => {
        const created: PaperTrade = {
          ...trade,
          id: newId(),
          status: 'open',
          outcome: 'open',
          adherencePct: 0,
          openedAt: new Date().toISOString(),
          closedAt: null,
        };
        set((state) => ({ paperTrades: [...state.paperTrades, created] }));
        return created;
      },

      closePaperTrade: (id, outcome, stepsFollowed, stepsTotal) => {
        const now = new Date().toISOString();
        set((state) => ({
          paperTrades: state.paperTrades.map((t) =>
            t.id === id
              ? {
                  ...t,
                  status: 'closed',
                  outcome,
                  stepsFollowed,
                  stepsTotal,
                  adherencePct: adherencePct(stepsFollowed, stepsTotal),
                  closedAt: now,
                }
              : t
          ),
        }));
      },

      // ── Reset ──

      resetWorkflow: () => set(emptyState()),
    }),
    {
      name: STORAGE_KEY,
      // Fall back to in-memory storage outside the browser (vitest/SSR) so the
      // store imports cleanly; persists to localStorage normally in the browser.
      storage: createJSONStorage(() =>
        typeof window !== 'undefined' && typeof localStorage !== 'undefined'
          ? localStorage
          : memoryStorage()
      ),
    }
  )
);

// ── Derived selectors (pure helpers over store state) ──

/**
 * Rolling 20-trade adherence + streak over all stored closed trades.
 * Stable selector: subscribes to the `paperTrades` array reference and
 * memoizes the derived `{ rolling, streak }` so the object identity is stable
 * between renders (selectAdherence creates a fresh object each call — returning
 * it directly from the selector would re-render React 18 subscribers forever).
 */
export function useAdherence(): { rolling: RollingAdherence; streak: number } {
  const paperTrades = useWorkflowStore((s) => s.paperTrades);
  return useMemo(() => selectAdherence(paperTrades, ADHERENCE_WINDOW), [paperTrades]);
}

/** Latest validation gate for a symbol (most recent attempt), if any. */
export function latestGateForSymbol(symbol: string): ValidationGate | undefined {
  const gates = useWorkflowStore.getState().validationGates;
  for (let i = gates.length - 1; i >= 0; i--) {
    if (gates[i].symbol === symbol) return gates[i];
  }
  return undefined;
}

// Re-export the gate-step helper types for callers that build a ValidationGate.
export type { GateStepResult, GateVerdict };
