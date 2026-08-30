/**
 * Validation Gate modal (Phase 1, Sprint 3 — gap #4, in-flow guided learning).
 *
 * Launched from a ticker's Verdict banner ("Validate Setup"), this 5-step modal
 * teaches the working-professional beginner the questions behind a trade before
 * they size/execute it. Each step asks a plain-English question, shows the app's
 * auto-answer (computed from live verdict + trade-plan data via
 * `workflow/gate.ts`), and exposes a "Why this matters" education note. The final
 * step is the user's own 0-10 conviction; the result is persisted through
 * `useWorkflowStore.recordGate` (localStorage).
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
  GATE_STEPS,
  buildGateResults,
  computeGate,
  type GateInput,
} from '@/workflow/gate';
import type { GateVerdict } from '@/types/workflow';
import { TermLink } from '@/components/learn/TermLink';

/** Plain-English "why this matters" for each gate step (Sprint 6 formalizes glossing). */
export const GATE_WHY: Record<string, string> = {
  Liquidity:
    'Institutions only trade names they can get into and out of without moving the price. If volume is too thin, your stop can gap and your fill can be terrible.',
  Structure:
    'Institutions check weekly > daily alignment. If the higher timeframe contradicts your daily setup, you are fighting the bigger money — your invalidation (where you are wrong) is a structure break.',
  'Risk/Reward':
    'You do not need to be right often if your winners pay for your losers. A 2.5:1 floor means one win covers two and a half losses — the math of surviving a losing streak.',
  'Edge Check':
    'A setup with no edge is just a guess. Conviction comes from many signals agreeing; a real catalyst is the fuel that makes the move start.',
  Conviction:
    'This is your honest, 0-10 score after weighing everything above. Below ~4 there is no edge; 4-6 trade small; 7+ is a full-size signal.',
};

function VerdictChip({ verdict }: { verdict: GateVerdict }) {
  const cfg =
    verdict === 'PASS'
      ? { label: 'PASS', cls: 'text-green-500 bg-green-500/10 border-green-500/30' }
      : verdict === 'CONDITIONAL'
        ? { label: 'CONDITIONAL', cls: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30' }
        : { label: 'FAIL', cls: 'text-loss bg-loss/10 border-loss/30' };
  return (
    <span className={cn('text-xs font-semibold px-2.5 py-0.5 rounded-full border', cfg.cls)}>
      {cfg.label}
    </span>
  );
}

function StepStatusIcon({ passed, conditional }: { passed: boolean; conditional?: boolean }) {
  if (passed) return <CheckCircle2 className="h-5 w-5 text-green-500" />;
  if (conditional) return <AlertTriangle className="h-5 w-5 text-yellow-400" />;
  return <MinusCircle className="h-5 w-5 text-loss" />;
}

export interface ValidationGateProps {
  open: boolean;
  onClose: () => void;
  /** Ticker symbol for the gate + recordGate. */
  symbol: string;
  /** Raw gate inputs derived from the ticker page's verdict/trade-plan/technical. */
  input: GateInput;
  /** Optional — when provided, a "Proceed to Execute" action appears after a
   *  PASS/CONDITIONAL save so the user can size the trade (Sprint 4). */
  onProceed?: () => void;
}

export function ValidationGate({ open, onClose, symbol, input, onProceed }: ValidationGateProps) {
  const recordGate = useWorkflowStore((s) => s.recordGate);
  // Seed the conviction from the verdict's own conviction (0-10) if we have it.
  const [conviction, setConviction] = useState(
    input.conviction != null ? Math.max(0, Math.min(10, Math.round(input.conviction))) : 5
  );

  const results = useMemo(() => buildGateResults(input, conviction), [input, conviction]);
  const { overall } = useMemo(
      () => computeGate(results),
    [input, results, conviction]
  );

  const [saved, setSaved] = useState(false);

  if (!open) return null;

  const handleSave = () => {
    recordGate({ symbol, stepResults: results, overall, convictionScore: conviction });
    setSaved(true);
  };

  const convictionConfig = GATE_STEPS.find((s) => s.name === 'Conviction')!;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border border-border/50 bg-surface-elevated p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between mb-1">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-accent" />
            <h2 className="text-base font-semibold text-text-primary">
              Validate Setup — {symbol}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="text-xs text-text-muted mb-4">
          Five checks before you risk a dollar. Each shows the question, the app
          reads your setup to answer it, and why it matters.
        </p>

        {/* Steps */}
        <ol className="space-y-3">
          {GATE_STEPS.map((step, i) => {
            const result = results[i];
            const isConviction = step.name === 'Conviction';
            return (
              <li
                key={step.name}
                className={cn(
                  'rounded-lg border p-3',
                  result?.passed
                    ? 'border-green-500/30 bg-green-500/5'
                    : result?.conditional
                      ? 'border-yellow-400/30 bg-yellow-400/5'
                      : 'border-loss/30 bg-loss/5'
                )}
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5">
                    <StepStatusIcon passed={!!result?.passed} conditional={result?.conditional} />
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-text-primary">
                        {i + 1}. {step.name}
                      </span>
                      {result?.passed && !result?.conditional && (
                        <span className="text-[10px] font-medium text-green-500 uppercase tracking-wide">
                          ok
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-text-muted mt-0.5 italic">{step.question}</p>

                    {/* Auto-answer */}
                    {result?.note && (
                      <p className="text-xs text-text-secondary leading-relaxed mt-2">
                        <TermLink text={result.note} />
                      </p>
                    )}

                    {/* Conviction slider only on the final step */}
                    {isConviction && (
                      <div className="mt-3">
                        <input
                          type="range"
                          min={0}
                          max={10}
                          step={1}
                          value={conviction}
                          onChange={(e) => setConviction(Number(e.target.value))}
                          className="w-full accent-accent"
                          aria-label={convictionConfig.question}
                        />
                        <div className="flex items-center justify-between text-[10px] text-text-muted mt-1">
                          <span>0 — no edge</span>
                          <span className="font-mono font-semibold text-text-primary text-xs">
                            {conviction}/10
                          </span>
                          <span>10 — full conviction</span>
                        </div>
                      </div>
                    )}

                    {/* Why this matters (expandable) */}
                    <WhyMatters text={GATE_WHY[step.name]} />
                  </div>
                </div>
              </li>
            );
          })}
        </ol>

        {/* Overall verdict */}
        <div className="mt-4 flex items-center justify-between rounded-lg border border-border/40 bg-surface/20 p-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-accent" />
            <span className="text-sm font-semibold text-text-primary">Overall verdict</span>
            <VerdictChip verdict={overall} />
          </div>
          <span className="text-[11px] text-text-muted">
            PASS requires every check green; any caution = CONDITIONAL; any hard no = FAIL.
          </span>
        </div>

        {/* Actions */}
        <div className="mt-4 flex items-center gap-3">
          {saved ? (
            <span className="text-sm font-medium text-green-500 flex items-center gap-1.5">
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
          {saved && onProceed && (overall === 'PASS' || overall === 'CONDITIONAL') && (
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
            className="px-3 py-2 text-sm text-text-muted hover:text-text-primary transition-colors"
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
        className="flex items-center gap-1 text-[11px] text-accent hover:text-accent/80 transition-colors"
      >
        <HelpCircle className="h-3 w-3" />
        {open ? 'Hide' : 'Why'} this matters
      </button>
      {open && (
        <p className="mt-1.5 text-xs text-text-secondary leading-relaxed bg-background/50 rounded-md px-3 py-2">
          <TermLink text={text} />
        </p>
      )}
    </div>
  );
}
