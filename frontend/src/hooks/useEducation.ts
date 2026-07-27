import { useQuery } from '@tanstack/react-query';
import { explainMetric } from '@/api/professional';
import {
  TECHNICAL_LESSONS,
  FUNDAMENTAL_LESSONS,
  EARNINGS_LESSONS,
  SENTIMENT_LESSONS,
  GROWTH_LESSONS,
  MODULE_LESSONS,
  GLOSSARY,
  type MetricLesson,
  type ModuleLesson,
} from '@/components/ticker-analysis/education';

// ── Consolidated Lookup ──

const ALL_METRIC_LESSONS: Record<string, MetricLesson> = {
  ...TECHNICAL_LESSONS,
  ...FUNDAMENTAL_LESSONS,
  ...EARNINGS_LESSONS,
  ...SENTIMENT_LESSONS,
  ...GROWTH_LESSONS,
};

/** Get the local lesson template for a metric name. */
export function getMetricLesson(metric: string): MetricLesson | undefined {
  return ALL_METRIC_LESSONS[metric];
}

/** Get all known metric names grouped by category. */
export function getMetricCategories() {
  return {
    technical: Object.keys(TECHNICAL_LESSONS),
    fundamental: Object.keys(FUNDAMENTAL_LESSONS),
    earnings: Object.keys(EARNINGS_LESSONS),
    sentiment: Object.keys(SENTIMENT_LESSONS),
    growth: Object.keys(GROWTH_LESSONS),
  };
}

/** Search metrics by name/label (case-insensitive). */
export function searchMetrics(query: string): Array<{ key: string; lesson: MetricLesson; category: string }> {
  const q = query.toLowerCase();
  const results: Array<{ key: string; lesson: MetricLesson; category: string }> = [];
  for (const [key, lesson] of Object.entries(TECHNICAL_LESSONS)) {
    if (key.includes(q) || lesson.label.toLowerCase().includes(q)) results.push({ key, lesson, category: 'technical' });
  }
  for (const [key, lesson] of Object.entries(FUNDAMENTAL_LESSONS)) {
    if (key.includes(q) || lesson.label.toLowerCase().includes(q)) results.push({ key, lesson, category: 'fundamental' });
  }
  for (const [key, lesson] of Object.entries(EARNINGS_LESSONS)) {
    if (key.includes(q) || lesson.label.toLowerCase().includes(q)) results.push({ key, lesson, category: 'earnings' });
  }
  for (const [key, lesson] of Object.entries(SENTIMENT_LESSONS)) {
    if (key.includes(q) || lesson.label.toLowerCase().includes(q)) results.push({ key, lesson, category: 'sentiment' });
  }
  for (const [key, lesson] of Object.entries(GROWTH_LESSONS)) {
    if (key.includes(q) || lesson.label.toLowerCase().includes(q)) results.push({ key, lesson, category: 'growth' });
  }
  return results;
}

/** Get module lesson by name. */
export function getModuleLesson(name: string): ModuleLesson | undefined {
  return MODULE_LESSONS[name];
}

/** Get all module lessons. */
export function getAllModuleLessons(): Record<string, ModuleLesson> {
  return MODULE_LESSONS;
}

/** Search glossary terms. */
export function searchGlossary(query: string): typeof GLOSSARY {
  const q = query.toLowerCase();
  return GLOSSARY.filter(
    (entry) => entry.term.toLowerCase().includes(q) || entry.definition.toLowerCase().includes(q)
  );
}

/** Get the full glossary. */
export function getGlossary(): typeof GLOSSARY {
  return GLOSSARY;
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
