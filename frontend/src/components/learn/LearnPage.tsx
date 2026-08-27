import { useMemo, useState } from 'react';
import {
  Search, BookOpen, LineChart, BarChart3, DollarSign, Brain,
  TrendingUp, Shield, FlaskConical, ListChecks, ChevronRight, X,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  getMetrics,
  getBacktestMetrics,
  getTradePlan,
  getModules,
  getConcepts,
  getGlossary,
  searchGlossary,
  getContentMeta,
  type Lesson,
} from '@/content/index';

/**
 * Learn Hub — the central, always-accessible education page.
 * Promotes the glossary + concept browser out of Professional Mode gating.
 * Sections: search across everything → guided paths → metric categories →
 * backtest metrics → trade plan → modules → concepts → full glossary.
 */

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  technical: <LineChart className="h-3.5 w-3.5" />,
  fundamental: <BarChart3 className="h-3.5 w-3.5" />,
  growth: <TrendingUp className="h-3.5 w-3.5" />,
  earnings: <DollarSign className="h-3.5 w-3.5" />,
  sentiment: <Brain className="h-3.5 w-3.5" />,
  risk: <Shield className="h-3.5 w-3.5" />,
  market: <LineChart className="h-3.5 w-3.5" />,
};

const GUIDED_PATHS: Array<{ title: string; blurb: string; keys: string[] }> = [
  {
    title: 'Your first screen',
    blurb: 'Run the screener and understand every number it shows.',
    keys: ['screener-score', 'confluence', 'volume_ratio', 'rsi'],
  },
  {
    title: 'Reading a verdict',
    blurb: 'What BUY/WATCH/AVOID mean and how the score got there.',
    keys: ['conviction_score', 'market_regime', 'ma_alignment', 'pe_ratio'],
  },
  {
    title: 'Protect your capital',
    blurb: 'Risk management — the difference between surviving and blowing up.',
    keys: ['r_multiple', 'trailing_stop', 'risk_limits', 'max_risk_per_trade_pct'],
  },
];

export function LearnPage() {
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const metrics = getMetrics();
  const bt = getBacktestMetrics();
  const tp = getTradePlan();
  const modules = getModules();
  const concepts = getConcepts();
  const glossary = getGlossary();
  const meta = getContentMeta();

  const q = query.trim().toLowerCase();

  // Group metrics by category
  const byCategory = useMemo(() => {
    const groups: Record<string, Array<[string, Lesson]>> = {};
    for (const [k, l] of Object.entries(metrics)) {
      if (q && !(k.includes(q) || l.label.toLowerCase().includes(q))) continue;
      (groups[l.category ?? 'technical'] ??= []).push([k, l]);
    }
    return groups;
  }, [metrics, q]);

  const filteredBt = useMemo(
    () => Object.entries(bt).filter(([k, l]) => !q || k.includes(q) || l.label.toLowerCase().includes(q)),
    [bt, q]
  );
  const filteredTp = useMemo(
    () => Object.entries(tp).filter(([k, l]) => !q || k.includes(q) || l.label.toLowerCase().includes(q)),
    [tp, q]
  );
  const filteredGlossary = useMemo(() => (q ? searchGlossary(q) : glossary), [glossary, q]);
  const filteredConcepts = useMemo(
    () => Object.entries(concepts).filter(([k, l]) => !q || k.includes(q) || l.label.toLowerCase().includes(q)),
    [concepts, q]
  );

  const totalEntries =
    Object.keys(metrics).length +
    Object.keys(bt).length +
    Object.keys(tp).length +
    Object.keys(concepts).length +
    Object.keys(modules).length +
    glossary.length;

  const toggle = (key: string) => setExpanded((prev) => (prev === key ? null : key));

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 lg:p-6">
      {/* Header */}
      <div>
        <h1 className="flex items-center gap-2 text-xl font-bold text-text-primary">
          <BookOpen className="h-5 w-5 text-accent" /> Learn
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Every metric, score, and term this platform uses — explained in plain English.
          {totalEntries} entries · content v{meta.version}
        </p>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search any concept… (rsi, drawdown, conviction, squeeze…)"
          className="w-full rounded-lg border border-border bg-surface py-2.5 pl-9 pr-9 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
        />
        {query && (
          <button
            onClick={() => setQuery('')}
            aria-label="Clear search"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Guided paths (only when not searching) */}
      {!q && (
        <section>
          <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
            <ListChecks className="h-3.5 w-3.5" /> Start here
          </h2>
          <div className="grid gap-2 sm:grid-cols-3">
            {GUIDED_PATHS.map((p) => (
              <div key={p.title} className="rounded-lg border border-border bg-surface p-3">
                <p className="text-sm font-semibold text-text-primary">{p.title}</p>
                <p className="mt-0.5 text-xs text-text-muted">{p.blurb}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {p.keys.map((k) => (
                    <PathChip key={k} k={k} onPick={(key) => { setQuery(''); toggle(key); }} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Metric categories */}
      {(['technical', 'fundamental', 'growth', 'earnings', 'sentiment', 'market'] as const).map((cat) => {
        const entries = byCategory[cat];
        if (!entries?.length) return null;
        return (
          <Section key={cat} icon={CATEGORY_ICONS[cat]} title={`${cat[0].toUpperCase()}${cat.slice(1)} Metrics`} count={entries.length}>
            {entries.map(([k, l]) => (
              <LessonRow key={k} entryKey={k} lesson={l} expanded={expanded === k} onToggle={() => toggle(k)} />
            ))}
          </Section>
        );
      })}
      {byCategory.risk && (
        <Section icon={<Shield className="h-3.5 w-3.5" />} title="Risk" count={byCategory.risk.length}>
          {byCategory.risk.map(([k, l]) => (
            <LessonRow key={k} entryKey={k} lesson={l} expanded={expanded === k} onToggle={() => toggle(k)} />
          ))}
        </Section>
      )}

      {/* Backtest metrics */}
      {filteredBt.length > 0 && (
        <Section icon={<FlaskConical className="h-3.5 w-3.5" />} title="Backtest Metrics" count={filteredBt.length}>
          {filteredBt.map(([k, l]) => (
            <LessonRow key={k} entryKey={k} lesson={l} expanded={expanded === k} onToggle={() => toggle(k)} />
          ))}
        </Section>
      )}

      {/* Trade plan */}
      {filteredTp.length > 0 && (
        <Section icon={<ListChecks className="h-3.5 w-3.5" />} title="Trade Plan Concepts" count={filteredTp.length}>
          {filteredTp.map(([k, l]) => (
            <LessonRow key={k} entryKey={k} lesson={l} expanded={expanded === k} onToggle={() => toggle(k)} />
          ))}
        </Section>
      )}

      {/* Modules + Concepts */}
      {!q && (
        <>
          <Section icon={<BarChart3 className="h-3.5 w-3.5" />} title="Analysis Modules" count={Object.keys(modules).length}>
            {Object.entries(modules).map(([k, m]) => (
              <div key={k} className="rounded-lg border border-border/50 px-3 py-2">
                <p className="text-sm font-medium text-text-primary">{m.title}</p>
                <p className="mt-0.5 text-xs text-text-muted">{m.whatItIs}</p>
                <p className="mt-1 text-xs text-text-muted italic">{m.howScoreWorks}</p>
              </div>
            ))}
          </Section>
          <Section icon={<BookOpen className="h-3.5 w-3.5" />} title="Core Concepts" count={Object.keys(concepts).length}>
            {Object.entries(concepts).map(([k, c]) => (
              <LessonRow key={k} entryKey={k} lesson={c} expanded={expanded === k} onToggle={() => toggle(k)} simple />
            ))}
          </Section>
        </>
      )}
      {q && filteredConcepts.length > 0 && (
        <Section icon={<BookOpen className="h-3.5 w-3.5" />} title="Concepts" count={filteredConcepts.length}>
          {filteredConcepts.map(([k, c]) => (
            <LessonRow key={k} entryKey={k} lesson={c} expanded={expanded === k} onToggle={() => toggle(k)} simple />
          ))}
        </Section>
      )}

      {/* Glossary */}
      {(filteredGlossary.length > 0 || q === '') && (
        <Section icon={<BookOpen className="h-3.5 w-3.5" />} title="Glossary" count={filteredGlossary.length}>
          <div className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
            {filteredGlossary.map((g) => (
              <div key={g.term} className="px-1 py-1">
                <span className="text-sm font-medium text-text-primary">{g.term}</span>
                <span className="ml-1.5 text-xs text-text-muted">{g.definition}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {q && totalEmpty(byCategory, filteredBt, filteredTp, filteredGlossary, filteredConcepts) && (
        <p className="py-12 text-center text-sm text-text-muted">
          Nothing matches “{query}”. Try a shorter term.
        </p>
      )}
    </div>
  );
}

function totalEmpty(
  byCategory: Record<string, unknown[]>,
  bt: unknown[],
  tp: unknown[],
  gl: unknown[],
  con: unknown[]
): boolean {
  return (
    Object.values(byCategory).every((a) => a.length === 0) &&
    bt.length === 0 && tp.length === 0 && gl.length === 0 && con.length === 0
  );
}

function PathChip({ k, onPick }: { k: string; onPick: (key: string) => void }) {
  const label = findLabel(k);
  if (!label) return null;
  return (
    <button
      onClick={() => onPick(k)}
      className="inline-flex items-center gap-0.5 rounded-full bg-bg-muted px-2 py-0.5 text-[10px] font-medium text-text-secondary hover:bg-accent/10 hover:text-accent"
    >
      {label} <ChevronRight className="h-2.5 w-2.5" />
    </button>
  );
}

function findLabel(key: string): string | null {
  const all = { ...getMetrics(), ...getBacktestMetrics(), ...getTradePlan(), ...getConcepts() } as Record<string, Lesson>;
  return all[key]?.label ?? null;
}

function Section({
  icon,
  title,
  count,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
        {icon} {title} <span className="font-normal normal-case">({count})</span>
      </h2>
      <div className="space-y-1">{children}</div>
    </section>
  );
}

function LessonRow({
  entryKey,
  lesson,
  expanded,
  onToggle,
  simple = false,
}: {
  entryKey: string;
  lesson: Lesson;
  expanded: boolean;
  onToggle: () => void;
  simple?: boolean;
}) {
  return (
    <div className={cn('rounded-lg border transition-colors', expanded ? 'border-accent/40 bg-surface' : 'border-border/50 bg-surface hover:border-border')}>
      <button onClick={onToggle} className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left" aria-expanded={expanded}>
        <span className="min-w-0">
          <span className="text-sm font-medium text-text-primary">{lesson.label}</span>
          {lesson.oneLiner && (
            <span className={cn('block truncate text-xs text-text-muted', expanded && 'hidden')}>{lesson.oneLiner}</span>
          )}
        </span>
        <ChevronRight className={cn('h-4 w-4 shrink-0 text-text-muted transition-transform', expanded && 'rotate-90')} />
      </button>
      {expanded && (
        <div className="space-y-2 border-t border-border/50 px-3 py-3 text-sm text-text-secondary">
          {!simple && lesson.what && <Block title="What it is" body={lesson.what} />}
          {!simple && lesson.howCalculated && <Block title="How it's calculated" body={lesson.howCalculated} />}
          {!simple && lesson.whyMatters && <Block title="Why it matters" body={lesson.whyMatters} />}
          {!simple && lesson.scoringImpact && <Block title="How our score uses it" body={lesson.scoringImpact} />}
          {!simple && lesson.commonMistakes && lesson.commonMistakes.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">Common mistakes</p>
              <ul className="mt-0.5 list-disc pl-4 space-y-0.5 text-xs">
                {lesson.commonMistakes.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          )}
          {!simple && lesson.example && <Block title="Example" body={lesson.example} />}
          {simple && lesson.what && <p>{lesson.what}</p>}
          {lesson.related && lesson.related.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-0.5">
              {lesson.related.map((r) => (
                <span key={r} className="rounded bg-bg-muted px-1.5 py-0.5 text-2xs text-text-muted">
                  {r.replaceAll('_', ' ')}
                </span>
              ))}
            </div>
          )}
          <p className="pt-0.5 font-mono text-2xs text-text-muted">key: {entryKey}</p>
        </div>
      )}
    </div>
  );
}

function Block({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">{title}</p>
      <p className="mt-0.5 text-xs leading-relaxed">{body}</p>
    </div>
  );
}

export default LearnPage;
