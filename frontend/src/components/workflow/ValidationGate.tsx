/**
 * Validation Gate modal (Phase 1, Sprint 3 — gap #4, in-flow guided learning).
 *
 * Launched from a ticker's Verdict banner ("Validate Setup"), this 7-step modal
 * teaches the working-professional beginner the questions behind a trade before
 * they size/execute it. Each step asks a plain-English question, shows the
 * backend's auto-answer (computed from live verdict + trade-plan data via the
 * API), and exposes a "Why this matters" education note. The final step is the
 * user's own 0-10 conviction; the result is persisted through
 * `useWorkflowStore.recordGate` (localStorage).
 *
 * The gate is **backend-decided, frontend-rendered**. This component receives
 * a pre-computed `ValidationGate` from the API and displays it.
 */

import { useMemo, useState } from 'react';
import {
  CheckCircle2,
  HelpCircle,
  ShieldCheck,
  X,
  AlertTriangle,
  MinusCircle,
  PlayCircle,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { useWorkflowStore } from '@/store/workflowStore';
import {
  renderGateResult,
  gateSummary,
  type ValidationGate,
} from '@/workflow/gate';
import type { GateVerdict } from '@/types/workflow';
import { TermLink } from '@/components/learn/TermLink';

/** Plain-English "why this matters" for each gate step (Sprint 6 formalizes glossing). */
export const GATE_WHY: Record<string, string> = {
  Liquidity:
    'Institutions only trade names they can get into and out of without moving the price. If volume is too thin, your stop can gap and your fill can be terrible.',
  Structure:
    'Institutions check weekly > daily alignment. If the higher timeframe contradicts your daily setup, you are fighting the bigger money — your invalidation (where you are wrong) is a structure break.',
  Positioning:
    'High short interest or heavy institutional ownership can create crowded trades. When everyone is on the same side, a small reversal becomes a stampede.',
  Catalyst:
    'A setup with no edge is just a guess. A near-term catalyst (earnings, FDA, M&A, macro) is the fuel that makes the move start now instead of later.',
  'Risk/Reward':
    'You do not need to be right often if your winners pay for your losers. A 2.5:1 floor means one win covers two and a half losses — the math of surviving a losing streak. D1 tier: 2.0:1 with first target ≥ 1R earns half-size.',
  'Portfolio Fit':
    'Risk is not per-trade — it is portfolio-level. 8-position cap, 30% sector ceiling, and no pyramiding at unchanged stops keep the book balanced.',
  Conviction:
    'This is your honest, 0-10 score after weighing everything above. Below ~4 there is no edge; 4-6 trade small; 7+ is a full-size signal.',
};

function VerdictChip({ verdict }: { verdict: GateVerdict }) {
  const cfg =
    verdict === 'PASS'
      ? {
          label: 'PASS',
          cls: 'text-green-500 bg-green-500/10 border-green-500/30',
        }
      : verdict === 'CONDITIONAL'
        ? {
            label: 'CONDITIONAL',
            cls: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
          }
        : { label: 'FAIL', cls: 'text-loss bg-loss/10 border-loss/30' };
  return (
    <span
      className={cn(
        'rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        cfg.cls
      )}
    >
      {cfg.label}
    </span>
  );
}

export interface ValidationGateProps {
  open: boolean;
  onClose: () => void;
  /** Ticker symbol for the gate + recordGate. */
  symbol: string;
  /** Pre-computed gate result from the backend API (ticker analysis verdict). */
  gateResult: ValidationGate | null;
  /** Optional — when provided, a "Proceed to Execute" action appears after a
   *  PASS/CONDITIONAL save so the user can size the trade (Sprint 4). */
  onProceed?: () => void;
}

export function ValidationGate({
  open,
  onClose,
  symbol,
  gateResult,
  onProceed,
}: ValidationGateProps) {
  const recordGate = useWorkflowStore((s) => s.recordGate);
  const [saved, setSaved] = useState(false);

  // Render the backend gate result for display
  const rendered = useMemo(
    () => (gateResult ? renderGateResult(gateResult) : null),
    [gateResult]
  );

  if (!open) return null;
  if (!gateResult || !rendered) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
        <div className="w-full max-w-2xl rounded-xl border border-border/50 bg-surface-elevated p-6 text-center shadow-2xl">
          <ShieldCheck className="mx-auto mb-3 h-10 w-10 text-text-muted" />
          <h2 className="mb-1 text-base font-semibold text-text-primary">
            No Gate Result
          </h2>
          <p className="text-xs text-text-muted">
            Run analysis on a ticker first to see the validation gate.
          </p>
          <button onClick={onClose} className="btn-secondary mt-4">
            Close
          </button>
        </div>
      </div>
    );
  }

  const { overall, steps, convictionScore, dataGaps, evaluatedAt } = rendered;

  const handleSave = () => {
    recordGate({
      symbol,
      stepResults: gateResult.stepResults,
      overall,
      convictionScore,
      dataGaps,
      evaluatedAt,
    });
    setSaved(true);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-border/50 bg-surface-elevated p-6 shadow-2xl">
        {/* Header */}
        <div className="mb-1 flex items-start justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-accent" />
            <h2 className="text-base font-semibold text-text-primary">
              Validate Setup — {symbol}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted transition-colors hover:text-text-primary"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="mb-4 text-xs text-text-muted">
          Seven checks before you risk a dollar. The backend evaluates each step
          from live data; conditional means data was missing, not a soft pass.
        </p>

        {/* Data gaps warning */}
        {dataGaps.length > 0 && (
          <div className="mb-3 rounded border border-yellow-400/30 bg-yellow-400/10 p-2 text-xs text-yellow-400">
            <strong>Data gaps:</strong> {dataGaps.join(', ')} — these steps
            could not be fully verified.
          </div>
        )}

        {/* Steps */}
        <ol className="space-y-3">
          {steps.map((step, i) => (
            <li
              key={step.name}
              className={cn(
                'rounded-lg border p-3',
                step.status === 'pass'
                  ? 'border-green-500/30 bg-green-500/5'
                  : step.status === 'conditional'
                    ? 'border-yellow-400/30 bg-yellow-400/5'
                    : 'border-loss/30 bg-loss/5'
              )}
            >
              <div className="flex items-start gap-3">
                <span className="mt-0.5">
                  {step.status === 'pass' && (
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                  )}
                  {step.status === 'conditional' && (
                    <AlertTriangle className="h-5 w-5 text-yellow-400" />
                  )}
                  {step.status === 'fail' && (
                    <MinusCircle className="h-5 w-5 text-loss" />
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-text-primary">
                      {i + 1}. {step.name}
                    </span>
                    {step.status === 'pass' && (
                      <span className="text-[10px] font-medium uppercase tracking-wide text-green-500">
                        ok
                      </span>
                    )}
                    {step.status === 'conditional' && (
                      <span className="text-[10px] font-medium uppercase tracking-wide text-yellow-400">
                        conditional
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs italic text-text-muted">
                    {step.question}
                  </p>

                  {/* Backend note */}
                  {step.note && (
                    <p className="mt-2 text-xs leading-relaxed text-text-secondary">
                      <TermLink text={step.note} />
                    </p>
                  )}

                  {/* Why this matters (expandable) */}
                  <WhyMatters text={GATE_WHY[step.name]} />
                </div>
              </div>
            </li>
          ))}
        </ol>

        {/* Overall verdict */}
        <div className="mt-4 flex items-center justify-between rounded-lg border border-border/40 bg-surface/20 p-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-accent" />
            <span className="text-sm font-semibold text-text-primary">
              Overall verdict
            </span>
            <VerdictChip verdict={overall} />
          </div>
          <span className="text-[11px] text-text-muted">
            {gateSummary(gateResult)}
          </span>
        </div>

        {/* "No qualifying setups" message for FAIL verdicts (Slice 3, Sec.7) */}
        {overall === 'FAIL' && (
          <div className="mt-3 p-3 rounded-lg border border-text-muted/20 bg-surface/10">
            <p className="text-sm font-semibold text-text-primary">
              No qualifying setups today.
            </p>
            <p className="mt-1 text-xs text-text-muted">
              This is the system working — the gate rejected this setup because it
              did not meet the 7-step criteria. A quiet day reads as <strong>success</strong>,
              not failure.
            </p>
          </div>
        )}

        {/* Evaluated timestamp */}
        <p className="mt-2 text-right text-[10px] text-text-muted">
          Evaluated: {new Date(evaluatedAt).toLocaleString()}
        </p>

        {/* Actions */}
        <div className="mt-4 flex items-center gap-3">
          {saved ? (
            <span className="flex items-center gap-1.5 text-sm font-medium text-green-500">
              <CheckCircle2 className="h-4 w-4" /> Saved to this device
            </span>
          ) : (
            <button
              onClick={handleSave}
              className="btn-primary gap-1.5 px-4 py-2 text-sm"
            >
              <ShieldCheck className="h-4 w-4" />
              Save Validation
            </button>
          )}
          {saved &&
            onProceed &&
            (overall === 'PASS' || overall === 'CONDITIONAL') && (
              <button
                onClick={onProceed}
                className="btn-primary gap-1.5 px-4 py-2 text-sm"
              >
                <PlayCircle className="h-4 w-4" />
                Proceed to Execute
              </button>
            )}
          <button
            onClick={onClose}
            className="px-3 py-2 text-sm text-text-muted transition-colors hover:text-text-primary"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function WhyMatters({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[11px] text-accent transition-colors hover:text-accent/80"
      >
        <HelpCircle className="h-3 w-3" />
        {open ? 'Hide' : 'Why'} this matters
      </button>
      {open && (
        <p className="mt-1.5 rounded-md bg-background/50 px-3 py-2 text-xs leading-relaxed text-text-secondary">
          <TermLink text={text} />
        </p>
      )}
    </div>
  );
}
