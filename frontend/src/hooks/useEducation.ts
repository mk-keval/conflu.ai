import { useQuery } from '@tanstack/react-query';
import { explainMetric } from '@/api/professional';
import {
  getMetrics,
  getBacktestMetrics,
  findLesson,
  getModules,
  searchGlossary as searchGlossaryContent,
  getGlossary as getGlossaryContent,
  type Lesson,
} from '@/content/index';
import { METRIC_LESSON_ALIASES } from '@/components/ticker-analysis/education';

// ── Consolidated Lookup (delegates to canonical education.json) ──

/**
 * All metric lessons from education.json, plus legacy alias keys
 * (relative_volume → volume_ratio etc.) resolving to the same object.
 * Kept for backward compatibility with existing consumers.
 */
export const ALL_METRIC_LESSONS: Record<string, Lesson> = {
  ...getMetrics(),
  ...Object.fromEntries(
    Object.entries(METRIC_LESSON_ALIASES).map(([alias, canonical]) => [
      alias,
      getMetrics()[canonical],
    ])
  ),
};

/** Get the lesson for a metric name — searches ALL sections + aliases. */
export function getMetricLesson(metric: string): Lesson | undefined {
  return findLesson(metric) ?? ALL_METRIC_LESSONS[metric];
}

/** Get all known metric names grouped by category. */
export function getMetricCategories() {
  const groups: Record<string, string[]> = {};
  for (const [key, lesson] of Object.entries(getMetrics())) {
    const cat = lesson.category ?? 'technical';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(key);
  }
  // backtest metrics surface under their own group
  groups.backtest = Object.keys(getBacktestMetrics());
  return groups;
}

/** Search lessons by key/label (case-insensitive). */
export function searchMetrics(
  query: string
): Array<{ key: string; lesson: Lesson; category: string }> {
  const q = query.toLowerCase();
  const results: Array<{ key: string; lesson: Lesson; category: string }> = [];
  for (const [key, lesson] of Object.entries(getMetrics())) {
    const cat = lesson.category ?? 'technical';
    if (key.includes(q) || lesson.label.toLowerCase().includes(q))
      results.push({ key, lesson, category: cat });
  }
  for (const [key, lesson] of Object.entries(getBacktestMetrics())) {
    const cat = lesson.category ?? 'backtest';
    if (key.includes(q) || lesson.label.toLowerCase().includes(q))
      results.push({ key, lesson, category: cat });
  }
  return results;
}

/** Get module lesson by name. */
export function getModuleLesson(name: string) {
  return getModules()[name];
}

/** Get all module lessons. */
export function getAllModuleLessons() {
  return getModules();
}

/** Search glossary terms. */
export function searchGlossary(query: string) {
  return searchGlossaryContent(query);
}

/** Get the full glossary. */
export function getGlossary() {
  return getGlossaryContent();
}

// ── React Query Hooks ──

/**
 * Fetch the plain-English explanation for a metric from the backend.
 * Falls back to the local template if the API is unavailable.
 */
export function useMetricExplanation(metric: string, symbol?: string) {
  return useQuery({
    queryKey: ['professional', 'education', metric, symbol],
    queryFn: () => explainMetric(metric, symbol),
    staleTime: 1000 * 60 * 30, // 30 min — education content is fairly static
    gcTime: 1000 * 60 * 60 * 2, // 2 hr cache
    retry: 1,
  });
}

/**
 * Fetch explanations for multiple metrics at once.
 * Returns a map of metric → explanation.
 */
export function useBulkMetricExplanations(metrics: string[], symbol?: string) {
  return useQuery({
    queryKey: ['professional', 'education', 'bulk', ...metrics.sort(), symbol],
    queryFn: async () => {
      const results = await Promise.all(
        metrics.map((m) => explainMetric(m, symbol).catch(() => null))
      );
      const map: Record<string, string | null> = {};
      metrics.forEach((m, i) => {
        map[m] = results[i]?.plainEnglish ?? null;
      });
      return map;
    },
    enabled: metrics.length > 0,
    staleTime: 1000 * 60 * 30,
    gcTime: 1000 * 60 * 60 * 2,
    retry: 1,
  });
}
