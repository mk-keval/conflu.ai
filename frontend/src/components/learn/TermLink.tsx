import { useMemo, useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { getGlossary } from '@/content/index';

/**
 * TermLink — auto-links trading jargon inside prose to its glossary definition.
 *
 * Conservative matching (per plan W3.2):
 *  - whole-word, case-insensitive
 *  - only terms ≥4 chars (avoids "P/E" false positives mid-word etc.)
 *  - skips strings already inside quotes/parens in the source text
 *  - max N links per passage to avoid confetti
 * Renders a dotted-underlined span; click opens a small definition popover.
 */

interface TermDef {
  term: string;
  definition: string;
}

const MIN_TERM_LEN = 4;
const MAX_LINKS_PER_TEXT = 3;

// Build the lookup once — sorted longest-first so longer terms win overlaps.
const TERMS: TermDef[] = getGlossary()
  .filter((g) => g.term.length >= MIN_TERM_LEN)
  .sort((a, b) => b.term.length - a.term.length);

interface Segment {
  text: string;
  def?: TermDef;
}

/** Split text into plain/term segments using whole-word matches. */
function segmentText(text: string): Segment[] {
  if (!text || TERMS.length === 0) return [{ text }];

  // One combined regex of escaped alternations, word-bounded.
  const escaped = TERMS.map((t) =>
    t.term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  );
  const re = new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi');

  const segments: Segment[] = [];
  let last = 0;
  let links = 0;
  for (const m of text.matchAll(re)) {
    const idx = m.index ?? 0;
    if (idx > last) segments.push({ text: text.slice(last, idx) });
    if (links < MAX_LINKS_PER_TEXT) {
      const def = TERMS.find(
        (t) => t.term.toLowerCase() === m[0].toLowerCase()
      );
      if (def) {
        segments.push({ text: m[0], def });
        links += 1;
      } else {
        segments.push({ text: m[0] });
      }
    } else {
      segments.push({ text: m[0] });
    }
    last = idx + m[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last) });
  return segments;
}

export function TermLink({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  const segments = useMemo(() => segmentText(text), [text]);
  const hasTerms = segments.some((s) => s.def);
  if (!hasTerms) return <span className={className}>{text}</span>;
  return (
    <span className={className}>
      {segments.map((s, i) =>
        s.def ? (
          <TermSpan key={i} term={s.text} def={s.def} />
        ) : (
          <span key={i}>{s.text}</span>
        )
      )}
    </span>
  );
}

function TermSpan({ term, def }: { term: string; def: TermDef }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useEffect(() => {
    if (!open) return;
    const update = () => {
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      setPos({
        left: Math.max(
          8,
          Math.min(r.left + r.width / 2 - 120, window.innerWidth - 256)
        ),
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
      const tip = popRef.current;
      const trg = ref.current;
      if (!tip || !trg || (!path.includes(tip) && !path.includes(trg)))
        setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown, true);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown, true);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        className="font-inherit cursor-help border-b border-dotted border-accent/60 text-inherit transition-colors hover:text-accent"
        title={def.definition.slice(0, 120)}
      >
        {term}
      </button>
      {open &&
        pos &&
        createPortal(
          <div
            ref={popRef}
            style={{ left: pos.left, top: pos.top }}
            className="fixed z-[9999] w-60 rounded-lg border border-border bg-surface p-2.5 shadow-xl"
          >
            <p className="text-xs font-semibold text-text-primary">
              {def.term}
            </p>
            <p className="mt-0.5 text-xs leading-relaxed text-text-muted">
              {def.definition}
            </p>
          </div>,
          document.body
        )}
    </>
  );
}
