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
import api from '@/api/client';
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
  PaperTradeStatus,
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
  completeRoutineStep: (
    date: string,
    seq: RoutineStepSeq,
    data?: Record<string, unknown>
  ) => void;
  // Validation Gate
  recordGate: (
    gate: Omit<ValidationGate, 'id' | 'createdAt'>
  ) => ValidationGate;
  // Paper Trades (read-only, hydrated from backend journal)
  // Paper trades are now sourced from the CSV journal via the backend API.
  // Local mutations (openPaperTrade/closePaperTrade) are deprecated —
  // the backend paper_trade_from_brief.py script writes to the CSV ledger.
  // This store only reads/hydrates from the backend.
  hydrateFromJournal: () => Promise<void>;
  // Deprecated: kept for backward compatibility with existing components
  // The backend paper_trade_from_brief.py is now the single writer.
  openPaperTrade: (
    trade: Omit<
      PaperTrade,
      'id' | 'status' | 'outcome' | 'adherencePct' | 'openedAt' | 'closedAt'
    >
  ) => PaperTrade;
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
        set((state) => ({
          validationGates: [...state.validationGates, created],
        }));
        return created;
      },

      // Hydrate paperTrades from CSV journal via backend API
      // The backend paper_trade_from_brief.py is the single writer; this store only reads.
      hydrateFromJournal: async () => {
        try {
          // Fetch open positions from the backend journal API
          const response = await api.get('/api/v1/workflow/journal/open');
          const openPositions = response.data.positions || [];

          // Fetch closed trades for adherence/expectancy calculations
          const closedResponse = await api.get('/api/v1/workflow/journal/closed');
          const closedTrades = closedResponse.data.trades || [];

          // Convert journal rows to PaperTrade format for UI components
          const paperTrades: PaperTrade[] = [
            ...openPositions.map((row: any) => ({
              id: `${row.date_entered}-${row.symbol}-open`,
              symbol: row.symbol,
              plan: {},
              fills: {},
              status: 'open' as PaperTradeStatus,
              outcome: 'open' as PaperTradeOutcome,
              stepsFollowed: 0,
              stepsTotal: 13,
              adherencePct: 0,
              realizedR: row.realized_r ?? undefined,
              entryPrice: row.entry_price ?? undefined,
              stopLoss: row.stop_loss ?? undefined,
              gateVerdict: row.gate_verdict as 'PASS' | 'FAIL' | 'CONDITIONAL' | undefined,
              planAdherence: row.plan_adherence ?? undefined,
              excludeFromStats:
                row.exclude_from_stats === '1' ||
                row.exclude_from_stats === 1 ||
                row.exclude_from_stats === true,
              openedAt: row.date_entered ?? new Date().toISOString(),
              closedAt: null,
            })),
            ...closedTrades.map((row: any) => ({
              id: `${row.date_entered}-${row.symbol}-closed`,
              symbol: row.symbol,
              plan: {},
              fills: {},
              status: 'closed' as PaperTradeStatus,
              outcome: row.exit_reason as PaperTradeOutcome || 'flat',
              stepsFollowed: Math.round((row.plan_adherence ?? 0) * 13),
              stepsTotal: 13,
              adherencePct: row.plan_adherence ?? 0,
              realizedR: row.realized_r ?? undefined,
              entryPrice: row.entry_price ?? undefined,
              stopLoss: row.stop_loss ?? undefined,
              gateVerdict: row.gate_verdict as 'PASS' | 'FAIL' | 'CONDITIONAL' | undefined,
              planAdherence: row.plan_adherence ?? undefined,
              excludeFromStats:
                row.exclude_from_stats === '1' ||
                row.exclude_from_stats === 1 ||
                row.exclude_from_stats === true,
              openedAt: row.date_entered ?? new Date().toISOString(),
              closedAt: row.date_closed ?? new Date().toISOString(),
            })),
          ];

          set({ paperTrades });
        } catch (error) {
          console.warn('Failed to hydrate from journal, using localStorage fallback:', error);
          // Fallback: keep existing localStorage paperTrades
        }
      },

      // ── Deprecated: Local paper trade mutations (backend is the source of truth) ──

      openPaperTrade: (trade: Omit<PaperTrade, 'id' | 'status' | 'outcome' | 'adherencePct' | 'openedAt' | 'closedAt'>) => {
        console.warn('openPaperTrade is deprecated — paper trades are now managed by the backend journal');
        const created: PaperTrade = {
          ...trade,
          id: newId(),
          status: 'open' as PaperTradeStatus,
          outcome: 'open' as PaperTradeOutcome,
          adherencePct: 0,
          openedAt: new Date().toISOString(),
          closedAt: null,
        };
        set((state) => ({ paperTrades: [...state.paperTrades, created] }));
        return created;
      },

      closePaperTrade: (id: string, outcome: Exclude<PaperTradeOutcome, 'open'>, stepsFollowed: number, stepsTotal: number) => {
        console.warn('closePaperTrade is deprecated — paper trades are now managed by the backend journal');
        const now = new Date().toISOString();
        set((state) => ({
          paperTrades: state.paperTrades.map((t) =>
            t.id === id
              ? {
                  ...t,
                  status: 'closed' as PaperTradeStatus,
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
      // Only persist dailyRoutines and validationGates to localStorage.
      // paperTrades are hydrated from the backend journal on each session.
      partialize: (state) => ({
        dailyRoutines: state.dailyRoutines,
        validationGates: state.validationGates,
        // paperTrades intentionally excluded — sourced from backend journal
      }),
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
  return useMemo(
    () => selectAdherence(paperTrades, ADHERENCE_WINDOW),
    [paperTrades]
  );
}

/** Latest validation gate for a symbol (most recent attempt), if any. */
export function latestGateForSymbol(
  symbol: string
): ValidationGate | undefined {
  const gates = useWorkflowStore.getState().validationGates;
  for (let i = gates.length - 1; i >= 0; i--) {
    if (gates[i].symbol === symbol) return gates[i];
  }
  return undefined;
}

// Re-export the gate-step helper types for callers that build a ValidationGate.
export type { GateStepResult, GateVerdict };
