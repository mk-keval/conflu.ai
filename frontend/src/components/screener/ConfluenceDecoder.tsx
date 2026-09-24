import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { BarChart3, X } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * ConfluenceDecoder — explains the screener's pillar codes "T30 · M19 · V7 · Q10 · F8".
 *
 * Engine facts (verified against backend confluence_scorer.py):
 *   Trend 0-30 · Momentum 0-25 · Volume 0-20 · Quality 0-15 · Fundamental 0-10
 *   → total 0-100 mapped to letter rating (A+ ≥80 … D).
 *   Pillar importance is re-weighted by market regime.
 */

const PILLARS: Array<{
  code: string;
  name: string;
  max: number;
  meaning: string;
}> = [
  {
    code: 'T',
    name: 'Trend',
    max: 30,
    meaning: 'Is the stock in a clear direction?',
  },
  {
    code: 'M',
    name: 'Momentum',
    max: 25,
    meaning: 'Is buying pressure building?',
  },
  {
    code: 'V',
    name: 'Volume',
    max: 20,
    meaning: 'Are real traders behind the move?',
  },
  { code: 'Q', name: 'Quality', max: 15, meaning: 'Low-risk price behavior?' },
  {
    code: 'F',
    name: 'Fundamental',
    max: 10,
    meaning: 'Does the business back the trade?',
  },
];

interface Props {
  /** Raw code string like "T30 · M19 · V7 · Q10 · F8" (or undefined → render nothing). */
  value?: string | null;
  className?: string;
}

export function ConfluenceDecoder({ value, className }: Props) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useEffect(() => {
    if (!open) return;
    const update = () => {
      const el = btnRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      setPos({
        left: Math.min(r.left, window.innerWidth - 340),
        top: r.bottom + 6,
      });
    };
    update();
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const path = e.composedPath() as Node[];
      if (
        (!popRef.current || !path.includes(popRef.current)) &&
        (!btnRef.current || !path.includes(btnRef.current))
      ) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown, true);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown, true);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!value) return null;

  // Parse "T30 · M19 · V7 · Q10 · F8" into {code, score}
  const parts = value
    .split('·')
    .map((s) => s.trim())
    .map((s) => ({ code: s.charAt(0), score: parseInt(s.slice(1), 10) }))
    .filter((p) => !Number.isNaN(p.score));

  if (parts.length === 0) {
    // Not a parseable pillar string — render as plain text
    return <span className={className}>{value}</span>;
  }

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        className={cn(
          'text-dark-200 inline-flex items-center gap-1 font-mono transition-colors hover:text-accent',
          className
        )}
        title="Break down this confluence score"
      >
        <span>{value}</span>
        <BarChart3 className="h-3 w-3 shrink-0 opacity-60" />
      </button>

      {open &&
        pos &&
        createPortal(
          <div
            ref={popRef}
            style={{ left: pos.left, top: pos.top }}
            className="fixed z-[9999] w-80 rounded-lg border border-border bg-surface p-3 text-xs shadow-xl"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                Confluence breakdown
              </span>
              <button
                onClick={() => setOpen(false)}
                aria-label="Close"
                className="text-text-muted hover:text-text-primary"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
            <div className="space-y-2">
              {PILLARS.map((p) => {
                const found = parts.find((x) => x.code === p.code);
                const score = found?.score ?? 0;
                const pct = Math.max(0, Math.min(100, (score / p.max) * 100));
                return (
                  <div key={p.code}>
                    <div className="mb-0.5 flex items-baseline justify-between gap-2">
                      <span className="text-text-primary">
                        <span className="font-mono text-text-muted">
                          {p.code}
                        </span>{' '}
                        {p.name}
                        <span className="ml-1.5 normal-case text-text-muted">
                          — {p.meaning}
                        </span>
                      </span>
                      <span className="shrink-0 font-mono text-text-muted">
                        {found ? `${score}/${p.max}` : `–/${p.max}`}
                      </span>
                    </div>
                    <div className="bg-bg-muted h-1 w-full overflow-hidden rounded">
                      <div
                        className={cn(
                          'h-full rounded transition-all',
                          pct >= 70
                            ? 'bg-gain'
                            : pct >= 40
                              ? 'bg-amber-400'
                              : 'bg-loss'
                        )}
                        style={{ width: `${found ? pct : 0}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-2.5 border-t border-border pt-2 text-[10px] leading-relaxed text-text-muted">
              Pillars are weighted by market regime — trend matters most in
              strong trends; volume and quality lead in choppy markets. Total
              maps to the letter rating.
            </p>
          </div>,
          document.body
        )}
    </>
  );
}
