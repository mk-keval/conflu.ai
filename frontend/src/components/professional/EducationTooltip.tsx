import { useState, useRef, useCallback, useEffect, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
import { HelpCircle, BookOpen, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/cn';
import { findLesson, renderValueText } from '@/content/index';

interface EducationTooltipProps {
  metricKey: string;
  metricLabel?: string;
  metricValue?: string;
  symbol?: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
  compact?: boolean;
  children?: React.ReactNode;
}

/** "rsi" → "Rsi", "pe_ratio" → "Pe Ratio" — display-safe fallback for raw keys. */
function toTitleCase(key: string): string {
  return key
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

/**
 * Education tooltip rendered through a PORTAL.
 *
 * Why a portal: tooltips rendered inline were trapped inside ancestor
 * stacking contexts (cards with blur/transform classes), letting the page's
 * scroll container intercept clicks on buttons INSIDE the tooltip — closing
 * it instead of activating "Deep dive". Portal + fixed positioning escapes
 * every ancestor stacking context.
 */
export function EducationTooltip({
  metricKey,
  metricLabel,
  metricValue,
  position = 'top',
  compact = false,
  children,
}: EducationTooltipProps) {
  const [open, setOpen] = useState(false);
  const [deepDive, setDeepDive] = useState(false);
  const [coords, setCoords] = useState<{ left: number; top: number } | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);

  // Canonical lesson from education.json (single source of truth).
  const lesson = findLesson(metricKey);

  const updateCoords = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const pad = 8;
    let left = r.left + r.width / 2;
    let top = r.top - pad;
    if (position === 'bottom') top = r.bottom + pad;
    else if (position === 'left') { left = r.left - pad; top = r.top + r.height / 2; }
    else if (position === 'right') { left = r.right + pad; top = r.top + r.height / 2; }
    setCoords({ left, top });
  }, [position]);

  useLayoutEffect(() => {
    if (!open) return;
    updateCoords();
    const reposition = () => updateCoords();
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    return () => {
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('resize', reposition);
    };
  }, [open, updateCoords]);

  const handleToggle = useCallback(() => {
    setOpen((prev) => !prev);
    setDeepDive(false);
  }, []);

  // Close on outside click / Escape (portal-safe: checks composed path)
  useEffect(() => {
    if (!open) return;
    const handlePointer = (e: Event) => {
      const path = e.composedPath() as Node[];
      const tip = tooltipRef.current;
      const trigger = triggerRef.current;
      if (!tip || !trigger || (!path.includes(tip) && !path.includes(trigger))) {
        setOpen(false);
        setDeepDive(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        setDeepDive(false);
      }
    };
    document.addEventListener('mousedown', handlePointer, true);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handlePointer, true);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  const translateClasses: Record<string, string> = {
    top: '-translate-x-1/2 -translate-y-full',
    bottom: '-translate-x-1/2',
    left: '-translate-x-full -translate-y-1/2',
    right: '-translate-y-1/2',
  };

  const tooltipNode =
    open &&
    coords &&
    createPortal(
      <div
        ref={tooltipRef}
        role="tooltip"
        style={{ left: coords.left, top: coords.top }}
        className={cn(
          'fixed z-[9999] p-3 rounded-lg border border-border bg-surface shadow-xl backdrop-blur-sm',
          deepDive
            ? 'w-96 max-h-96 overflow-y-auto text-sm text-text-primary'
            : 'w-72 text-sm text-text-primary',
          'animate-in fade-in duration-100',
          translateClasses[position]
        )}
      >
        {/* Metric label */}
        <div className="font-semibold text-xs text-accent uppercase tracking-wider mb-1">
          {metricLabel || lesson?.label || toTitleCase(metricKey)}
          {metricValue && (
            <span className="text-text-primary ml-1 normal-case font-mono">= {metricValue}</span>
          )}
        </div>

        {!lesson ? (
          <p className="text-text-muted text-xs">
            Explanation coming soon — this metric isn't in our education library yet.
          </p>
        ) : !deepDive ? (
          <>
            {lesson.oneLiner && <p className="text-text-primary mb-1">{lesson.oneLiner}</p>}
            {metricValue != null && lesson.valueInterpretation && (
              <p className="text-text-muted text-xs mb-1">{renderValueText(metricKey, metricValue)}</p>
            )}
            <button
              onClick={() => setDeepDive(true)}
              className="mt-2 inline-flex items-center gap-1 text-xs text-accent hover:text-accent-light transition-colors"
            >
              <BookOpen className="h-3 w-3" />
              Deep dive
              <ChevronDown className="h-3 w-3" />
            </button>
          </>
        ) : (
          <>
            {lesson.what && (
              <Section title="What it is">
                <p>{lesson.what}</p>
              </Section>
            )}
            {lesson.howCalculated && (
              <Section title="How it's calculated">
                <p>{lesson.howCalculated}</p>
              </Section>
            )}
            {lesson.whyMatters && (
              <Section title="Why it matters">
                <p>{lesson.whyMatters}</p>
              </Section>
            )}
            {lesson.scoringImpact && (
              <Section title="How our score uses it">
                <p>{lesson.scoringImpact}</p>
              </Section>
            )}
            {lesson.commonMistakes && lesson.commonMistakes.length > 0 && (
              <Section title="Common mistakes">
                <ul className="list-disc pl-4 space-y-0.5">
                  {lesson.commonMistakes.map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              </Section>
            )}
            {lesson.example && (
              <Section title="Example">
                <p className="italic">{lesson.example}</p>
              </Section>
            )}
            {lesson.related && lesson.related.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {lesson.related.map((r) => (
                  <span key={r} className="px-1.5 py-0.5 rounded bg-bg-muted text-2xs text-text-muted">
                    {toTitleCase(r)}
                  </span>
                ))}
              </div>
            )}
            <button
              onClick={() => setDeepDive(false)}
              className="mt-2 text-xs text-text-muted hover:text-accent transition-colors"
            >
              Show less
            </button>
          </>
        )}
      </div>,
      document.body
    );

  return (
    <span className="relative inline-flex items-center">
      {children ? (
        <span ref={triggerRef} onClick={handleToggle} className="cursor-pointer">
          {children}
        </span>
      ) : (
        <button
          ref={triggerRef as React.Ref<HTMLButtonElement>}
          onClick={handleToggle}
          className={cn(
            'inline-flex items-center justify-center rounded-full transition-colors',
            compact ? 'h-3.5 w-3.5' : 'h-4 w-4',
            'text-text-muted hover:text-accent hover:bg-accent/10'
          )}
          aria-label={`Learn about ${metricLabel || lesson?.label || toTitleCase(metricKey)}`}
        >
          <HelpCircle className={compact ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
        </button>
      )}
      {tooltipNode}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-2.5 last:mb-0">
      <div className="text-2xs font-semibold text-text-muted uppercase tracking-wider mb-0.5">{title}</div>
      {children}
    </div>
  );
}
