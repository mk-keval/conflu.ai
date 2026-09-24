import { useState } from 'react';
import { ChevronDown, Scale } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * ScoreLegendCard — reconciles the three coexisting score systems:
 *  1. Module scores (-1..+1), weighted 30/22/12/20/16% (default) → ticker verdict
 *  2. Screener pillar score (0-100 → A+/A/B/B+/C/D), five pillars T/M/V/Q/F
 *  3. Conviction (1-10) — confidence derived from the weighted score
 * Facts verified against synthesis.py + confluence_scorer.py (W1.4 appendix).
 */

const MODULE_WEIGHTS = [
  { name: 'Technical', pct: 30 },
  { name: 'Fundamental', pct: 22 },
  { name: 'Earnings', pct: 12 },
  { name: 'Sentiment', pct: 20 },
  { name: 'Risk', pct: 16 },
];

const PILLARS = [
  { code: 'T', name: 'Trend', max: 30 },
  { code: 'M', name: 'Momentum', max: 25 },
  { code: 'V', name: 'Volume', max: 20 },
  { code: 'Q', name: 'Quality', max: 15 },
  { code: 'F', name: 'Fundamental', max: 10 },
];

export function ScoreLegendCard({
  defaultOpen = false,
}: {
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-border bg-surface/50">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2 text-left"
        aria-expanded={open}
      >
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-secondary">
          <Scale className="h-3.5 w-3.5 text-text-muted" />
          How our scores relate
        </span>
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 text-text-muted transition-transform',
            open && 'rotate-180'
          )}
        />
      </button>

      {open && (
        <div className="space-y-3 border-t border-border px-3 py-3 text-xs text-text-muted">
          {/* 1 — module scores */}
          <div>
            <p className="mb-1 text-[11px] font-semibold text-text-primary">
              1 · Module scores{' '}
              <span className="font-normal text-text-muted">
                (−1.0 to +1.0)
              </span>
            </p>
            <div className="mb-1 flex flex-wrap gap-x-3 gap-y-0.5">
              {MODULE_WEIGHTS.map((m) => (
                <span key={m.name} className="whitespace-nowrap">
                  {m.name} <span className="font-mono">{m.pct}%</span>
                </span>
              ))}
            </div>
            <MiniBars
              items={MODULE_WEIGHTS.map((m) => ({
                label: m.name.slice(0, 4),
                pct: m.pct,
              }))}
            />
            <p className="mt-1">
              Weighted average of these five drives the verdict
              (BUY/WATCH/AVOID…). Weights shift with market regime.
            </p>
          </div>

          {/* 2 — screener pillars */}
          <div>
            <p className="mb-1 text-[11px] font-semibold text-text-primary">
              2 · Screener score{' '}
              <span className="font-normal text-text-muted">
                (0–100 → A+ / A / B / C / D)
              </span>
            </p>
            <div className="mb-1 flex flex-wrap gap-x-3 gap-y-0.5">
              {PILLARS.map((p) => (
                <span key={p.code} className="whitespace-nowrap">
                  {p.code} {p.name} <span className="font-mono">/{p.max}</span>
                </span>
              ))}
            </div>
            <MiniBars
              items={PILLARS.map((p) => ({
                label: p.code,
                pct: (p.max / 100) * 100,
              }))}
            />
            <p className="mt-1">
              Five pillars sum to 100 and power the screener table ranking
              ("Scr" column).
            </p>
          </div>

          {/* 3 — conviction */}
          <div>
            <p className="mb-1 text-[11px] font-semibold text-text-primary">
              3 · Conviction{' '}
              <span className="font-normal text-text-muted">(1–10)</span>
            </p>
            <p>
              Confidence in the final call: ≥8 strong alignment, 6–7 solid, 4–5
              mixed, ≤3 weak or conflicting signals. Low conviction
              automatically shrinks suggested position size.
            </p>
          </div>

          <p className="border-t border-border pt-2 text-[11px] italic">
            Module scores power this Ticker Analysis verdict; screener pillars
            rank the table; conviction expresses confidence in both.
          </p>
        </div>
      )}
    </div>
  );
}

function MiniBars({ items }: { items: Array<{ label: string; pct: number }> }) {
  return (
    <div className="bg-bg-muted flex h-1.5 w-full overflow-hidden rounded">
      {items.map((it) => (
        <div
          key={it.label}
          style={{ width: `${it.pct}%` }}
          className={cn(
            'h-full',
            items.indexOf(it) % 3 === 0
              ? 'bg-accent/70'
              : items.indexOf(it) % 3 === 1
                ? 'bg-accent/45'
                : 'bg-accent/60'
          )}
          title={`${it.label} ${Math.round(it.pct)}%`}
        />
      ))}
    </div>
  );
}
