/**
 * Adherence CSV export (Phase 1, Sprint 7).
 *
 * Pure, browser-free CSV generation for the Adherence Dashboard so it can be
 * unit-tested without a DOM or the store. Mirrors the paper-trade fields a
 * beginner cares about pulling into a spreadsheet to review their own workflow
 * adherence.
 */

import { formatDate } from '../lib/format';
import type { PaperTrade } from '../types/workflow';

/** RFC-4180-ish field escaping: quote when a field contains a comma, quote, or newline. */
function escapeCsv(field: string): string {
  if (/[",\n\r]/.test(field)) {
    return `"${field.replace(/"/g, '""')}"`;
  }
  return field;
}

/** Human-friendly close-outcome label, matching the logger UI. */
const OUTCOME_LABEL: Record<string, string> = {
  target_hit: 'target_hit',
  stop_hit: 'stop_hit',
  time_stop: 'time_stop',
  flat: 'flat',
  open: 'open',
};

/**
 * Build a CSV document from paper trades (any order; caller passes what they
 * want — the dashboard passes closed trades newest-first).
 */
export function buildAdherenceCsv(trades: PaperTrade[]): string {
  const header = 'symbol,opened,closed,outcome,steps_followed,steps_total,adherence_pct';
  const rows = trades.map((t) =>
    [
      escapeCsv(t.symbol),
      escapeCsv(t.openedAt),
      escapeCsv(t.closedAt ?? ''),
      escapeCsv(OUTCOME_LABEL[t.outcome] ?? t.outcome),
      String(t.stepsFollowed),
      String(t.stepsTotal),
      String(t.adherencePct),
    ].join(',')
  );
  return [header, ...rows].join('\n');
}

/** Convenience: the human-readable closed date column for a summary row. */
export function csvClosedDate(trade: PaperTrade): string {
  return trade.closedAt ? formatDate(trade.closedAt) : '';
}
