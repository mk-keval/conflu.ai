/**
 * Typed accessors over the canonical education content (education.json).
 *
 * SINGLE SOURCE OF TRUTH: every consumer (EducationTooltip, ConceptExplorer,
 * useEducation hooks, glossary panels, Learn hub) reads through this module.
 * The backend loads the same file at startup (see
 * backend/app/infrastructure/professional/education.py).
 */
import raw from './education.json';
import { evaluateBands } from './evaluateBands';

// ── Types ──

export interface BandsInterpretation {
  type: 'bands';
  transform?: string | null;
  bands: Array<{ if: string; text: string }>;
}

export interface Lesson {
  label: string;
  category?: string;
  oneLiner?: string;
  what?: string;
  howCalculated?: string;
  valueInterpretation?: BandsInterpretation;
  whyMatters?: string;
  scoringImpact?: string;
  commonMistakes?: string[];
  example?: string;
  related?: string[];
}

export interface GlossaryEntry {
  term: string;
  definition: string;
  related?: string[];
}

interface EducationDoc {
  meta: { version: string; updatedAt: string };
  thresholds: Record<string, number>;
  metrics: Record<string, Lesson>;
  backtestMetrics: Record<string, Lesson>;
  tradePlan: Record<string, Lesson>;
  modules: Record<
    string,
    {
      title: string;
      whatItIs: string;
      whyItMatters: string;
      howScoreWorks: string;
    }
  >;
  concepts: Record<string, Lesson>;
  glossary: GlossaryEntry[];
}

const doc = raw as unknown as EducationDoc;

// ── Section accessors ──

/** All metric lessons keyed by metric key (48 entries). */
export function getMetrics(): Record<string, Lesson> {
  return doc.metrics;
}

/** Backtest performance-metric lessons (10 entries). */
export function getBacktestMetrics(): Record<string, Lesson> {
  return doc.backtestMetrics;
}

/** Trade-plan concept lessons (entry_zone, r_multiple, ...). */
export function getTradePlan(): Record<string, Lesson> {
  return doc.tradePlan;
}

/** Analysis-module intros (technical, fundamental, earnings, sentiment, risk). */
export function getModules(): EducationDoc['modules'] {
  return doc.modules;
}

/** Standalone concepts (conviction_score, var, regime_states, ...). */
export function getConcepts(): Record<string, Lesson> {
  return doc.concepts;
}

/** Full glossary (~78 terms). */
export function getGlossary(): GlossaryEntry[] {
  return doc.glossary;
}

export function getContentMeta() {
  return doc.meta;
}

/** Central numeric thresholds (single source for copy + logic). */
export function getThresholds(): Record<string, number> {
  return doc.thresholds;
}

// ── Cross-section lookup ──

const LESSON_INDEX: Record<
  string,
  {
    lesson: Lesson;
    section: 'metrics' | 'backtestMetrics' | 'tradePlan' | 'concepts';
  }
> = (() => {
  const idx: Record<
    string,
    {
      lesson: Lesson;
      section: 'metrics' | 'backtestMetrics' | 'tradePlan' | 'concepts';
    }
  > = {};
  for (const [k, v] of Object.entries(doc.metrics))
    idx[k] = { lesson: v, section: 'metrics' };
  for (const [k, v] of Object.entries(doc.backtestMetrics))
    idx[k] = { lesson: v, section: 'backtestMetrics' };
  for (const [k, v] of Object.entries(doc.tradePlan))
    idx[k] = { lesson: v, section: 'tradePlan' };
  for (const [k, v] of Object.entries(doc.concepts))
    idx[k] = { lesson: v, section: 'concepts' };
  return idx;
})();

/**
 * Resolve a lesson by key across all sections.
 * Falls back through alias map for legacy keys.
 */
const LEGACY_ALIASES: Record<string, string> = {
  relative_volume: 'volume_ratio',
  days_to_cover: 'short_ratio',
  macd: 'macd_status',
  atr: 'atr_pct',
};

export function findLesson(key: string): Lesson | undefined {
  const direct = LESSON_INDEX[key];
  if (direct) return direct.lesson;
  const aliased = LEGACY_ALIASES[key];
  return aliased ? LESSON_INDEX[aliased]?.lesson : undefined;
}

// ── Value-aware rendering ──

/** Render the valueInterpretation band text for a concrete value. */
export function renderValueText(key: string, value: string): string | null {
  const lesson = findLesson(key);
  if (!lesson?.valueInterpretation) return null;
  const out = evaluateBands(
    lesson.valueInterpretation as Parameters<typeof evaluateBands>[0],
    value
  );
  return out || null;
}

/** Tooltip-grade summary: oneLiner (+ dynamic band line when a value is given). */
export function tooltipSummary(
  key: string,
  value?: string
): { label: string; oneLiner: string; readLine?: string } | null {
  const lesson = findLesson(key);
  if (!lesson) return null;
  return {
    label: lesson.label,
    oneLiner: lesson.oneLiner ?? '',
    readLine:
      value != null ? (renderValueText(key, value) ?? undefined) : undefined,
  };
}

// ── Glossary search (used by Learn hub + ConceptExplorer) ──

export function searchGlossary(query: string): GlossaryEntry[] {
  const q = query.toLowerCase();
  return doc.glossary.filter(
    (e) =>
      e.term.toLowerCase().includes(q) || e.definition.toLowerCase().includes(q)
  );
}
