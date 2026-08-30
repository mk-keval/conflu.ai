/**
 * Execution Engine modal (Phase 1, Sprint 4 — gap #4, in-flow guided learning).
 *
 * Opened from the Validation Gate ("Proceed to Execute") or a ticker's Verdict
 * banner. It sizes the trade via the existing `/professional/position-size`
 * endpoint (backend math, no new backend code) and renders the teachable
 * execution plan: a 40/30/30 tranche ladder with trigger/limit/stop prices,
 * scale-out targets as r-multiples, a time-stop note, and a broker-ready OCO
 * bracket JSON the user can copy straight into their broker.
 */

import { useMemo, useState } from 'react';
import { Copy, Check, Loader2, PlayCircle, X, AlertTriangle, ClipboardList } from 'lucide-react';
import { calculatePositionSize } from '@/api/professional';
import { buildExecutionPlan, convictionToLevel, type ExecutionPlan } from '@/workflow/execution';
import type { ExecutionSetup } from '@/types/workflow';
import { TermLink } from '@/components/learn/TermLink';

export interface ExecutionEngineProps {
  open: boolean;
  onClose: () => void;
  /** Pre-filled from the ticker verdict/trade-plan (derived on the ticker page). */
  setup: ExecutionSetup;
  /** Optional — when provided, a "Log Paper Trade" action appears once a plan is
   *  sized so the user can record + score it (Sprint 5). */
  onLogPaperTrade?: (plan: ExecutionPlan) => void;
}

const DEFAULT_ACCOUNT_EQUITY = 25_000;

export function ExecutionEngine({ open, onClose, setup, onLogPaperTrade }: ExecutionEngineProps) {
  const [accountEquity, setAccountEquity] = useState(
    setup.accountEquity > 0 ? setup.accountEquity : DEFAULT_ACCOUNT_EQUITY
  );
  const [result, setResult] = useState<Awaited<ReturnType<typeof calculatePositionSize>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Rebuild the plan whenever the setup changes (new symbol) — discard stale sizing.
  const resetKey = setup.symbol;
  const [lastSymbol, setLastSymbol] = useState(resetKey);
  if (lastSymbol !== resetKey) {
    setLastSymbol(resetKey);
    setResult(null);
    setError(null);
    setCopied(false);
  }

  const size = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await calculatePositionSize({
        symbol: setup.symbol,
        accountEquity,
        entry: setup.entryMid,
        stopLoss: setup.stopLoss,
        conviction: convictionToLevel(setup.conviction),
      });
      setResult(res);
      setCopied(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to size position');
    } finally {
      setLoading(false);
    }
  };

  const plan = useMemo(
    () => (result ? buildExecutionPlan(result.shares, setup) : null),
    [result, setup]
  );

  const copyOco = async () => {
    if (!plan) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(plan.oco, null, 2));
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border border-border/50 bg-surface-elevated p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between mb-1">
          <div className="flex items-center gap-2">
            <PlayCircle className="h-5 w-5 text-accent" />
            <h2 className="text-base font-semibold text-text-primary">
              Execution Engine — {setup.symbol}
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
          Size the position, then take it in three pieces so a bad entry never
          gets your full size. Copy the bracket into your broker.
        </p>

        {/* Inputs */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <label className="text-xs text-text-muted block">
            Account equity (USD)
            <input
              type="number"
              min={0}
              value={accountEquity}
              onChange={(e) => setAccountEquity(Number(e.target.value))}
              className="mt-1 w-full rounded-md border border-border/50 bg-background px-3 py-2 text-sm text-text-primary"
            />
          </label>
          <div className="text-xs text-text-muted flex flex-col justify-end pb-1">
            Conviction:
            <span className="text-sm font-semibold text-text-primary">
              {setup.conviction}/10 →{' '}
              <span className="text-accent uppercase">{convictionToLevel(setup.conviction)}</span>
            </span>
          </div>
        </div>

        <button
          onClick={size}
          disabled={loading}
          className="btn-primary gap-1.5 px-4 py-2 text-sm disabled:opacity-60"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
          {loading ? 'Sizing…' : result ? 'Re-run sizing' : 'Size position'}
        </button>

        {error && (
          <p className="mt-3 flex items-center gap-1.5 text-xs text-loss">
            <AlertTriangle className="h-3.5 w-3.5" /> {error}
          </p>
        )}

        {/* Results */}
        {plan && result && (
          <div className="mt-5 space-y-5">
            {/* Summary */}
            <div className="rounded-lg border border-border/40 bg-surface/20 p-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <div className="text-xs text-text-muted">Position size</div>
              <div className="text-right font-semibold text-text-primary">
                ${result.positionSize.toLocaleString()}
              </div>
              <div className="text-xs text-text-muted">Shares</div>
              <div className="text-right font-semibold text-text-primary">{result.shares}</div>
              <div className="text-xs text-text-muted">Risk at stop</div>
              <div className="text-right font-semibold text-text-primary">
                ${result.riskAmount.toLocaleString()} ({result.riskPct.toFixed(1)}%)
              </div>
              <div className="text-xs text-text-muted">Conviction multiplier</div>
              <div className="text-right font-semibold text-text-primary">
                {result.convictionMultiplier.toFixed(2)}×
              </div>
              <div className="text-xs text-text-muted">Capped by</div>
              <div className="text-right font-medium text-text-secondary capitalize">
                {result.cappedBy}
              </div>
            </div>

            {/* Tranche ladder */}
            <div>
              <h3 className="text-sm font-semibold text-text-primary mb-2">
                Entry ladder (40 / 30 / 30)
              </h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wide text-text-muted border-b border-border/40">
                    <th className="py-1.5 pr-2">#</th>
                    <th className="py-1.5 pr-2">Shares</th>
                    <th className="py-1.5 pr-2">Trigger</th>
                    <th className="py-1.5 pr-2">Limit</th>
                    <th className="py-1.5 pr-2">Stop</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.tranches.map((t) => (
                    <tr key={t.seq} className="border-b border-border/20">
                      <td className="py-1.5 pr-2 text-text-secondary">
                        {t.seq} · {(t.weight * 100).toFixed(0)}%
                      </td>
                      <td className="py-1.5 pr-2 font-mono text-text-primary">{t.qty}</td>
                      <td className="py-1.5 pr-2 font-mono text-text-primary">
                        ${t.triggerPrice.toFixed(2)}
                      </td>
                      <td className="py-1.5 pr-2 font-mono text-text-primary">
                        ${t.limitPrice.toFixed(2)}
                      </td>
                      <td className="py-1.5 pr-2 font-mono text-text-secondary">
                        ${t.stopPrice.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Scale-out targets */}
            <div>
              <h3 className="text-sm font-semibold text-text-primary mb-2">
                Scale-out targets
              </h3>
              <ul className="space-y-1.5 text-sm">
                {plan.targets.map((t, i) => (
                  <li key={i} className="flex items-center justify-between rounded-md border border-border/20 bg-border/5 px-3 py-1.5">
                    <span className="text-text-secondary">
                      {t.rMultiple}R · take {t.sizePct}% off
                    </span>
                    <span className="font-mono font-semibold text-text-primary">
                      ${t.targetPrice.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[11px] text-text-muted">
                <TermLink text="r-multiple" /> = how many times your risk is made. Three
                targets means you bank wins in pieces instead of one all-or-nothing exit.
              </p>
            </div>

            {/* Time stop */}
            {plan.timeStopDays > 0 && (
              <div className="rounded-md border border-border/30 bg-surface/10 px-3 py-2 text-xs text-text-secondary">
                <TermLink text="Time stop" />: if neither stop nor target has hit in{' '}
                <span className="font-semibold text-text-primary">{plan.timeStopDays} days</span>,
                close the trade — the thesis has had its chance.
              </div>
            )}

            {/* OCO bracket */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-text-primary">
                  Broker-ready OCO bracket
                </h3>
                <button
                  onClick={copyOco}
                  className="flex items-center gap-1 text-[11px] font-medium text-accent hover:text-accent/80 transition-colors"
                >
                  {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  {copied ? 'Copied' : 'Copy JSON'}
                </button>
              </div>
              <pre className="rounded-lg border border-border/30 bg-background p-3 text-[11px] leading-relaxed text-text-secondary overflow-x-auto">
                {JSON.stringify(plan.oco, null, 2)}
              </pre>
              <p className="mt-1.5 text-[11px] text-text-muted">
                <TermLink text="OCO" /> = one-cancels-other: when one leg fills, the others cancel.
              </p>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="mt-4 flex items-center gap-3">
          {plan && onLogPaperTrade && (
            <button
              onClick={() => onLogPaperTrade(plan)}
              className="btn-primary gap-1.5 px-4 py-2 text-sm"
            >
              <ClipboardList className="h-4 w-4" />
              Log Paper Trade
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
