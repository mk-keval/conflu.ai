import { describe, it, expect } from 'vitest';
import { buildAdherenceCsv, csvClosedDate } from '../adherenceExport';
import type { PaperTrade } from '../../types/workflow';

function makeTrade(overrides: Partial<PaperTrade> = {}): PaperTrade {
  return {
    id: 't1',
    symbol: 'NVDA',
    plan: {},
    fills: {},
    status: 'closed',
    outcome: 'target_hit',
    stepsFollowed: 11,
    stepsTotal: 13,
    adherencePct: 84.62,
    openedAt: '2026-08-20T10:00:00.000Z',
    closedAt: '2026-08-24T15:00:00.000Z',
    ...overrides,
  };
}

describe('buildAdherenceCsv', () => {
  it('emits a header row then one row per trade', () => {
    const csv = buildAdherenceCsv([makeTrade()]);
    const lines = csv.split('\n');
    expect(lines[0]).toBe(
      'symbol,opened,closed,outcome,steps_followed,steps_total,adherence_pct'
    );
    expect(lines).toHaveLength(2);
    expect(lines[1]).toContain('NVDA');
    expect(lines[1]).toContain('target_hit');
    expect(lines[1]).toContain('11,13,84.62');
  });

  it('quotes and escapes a symbol containing a comma', () => {
    const trade = makeTrade({ symbol: 'BRK,B' });
    const csv = buildAdherenceCsv([trade]);
    expect(csv.split('\n')[1]).toMatch(/^"BRK,B"/);
  });

  it('escapes embedded quotes in a field', () => {
    const trade = makeTrade({ symbol: 'A"B' });
    const csv = buildAdherenceCsv([trade]);
    expect(csv.split('\n')[1]).toMatch(/^"A""B"/);
  });

  it('leaves closedAt blank for open trades', () => {
    const trade = makeTrade({ outcome: 'open', status: 'open', closedAt: null });
    const csv = buildAdherenceCsv([trade]);
    const cols = csv.split('\n')[1].split(',');
    // symbol,opened,closed,... — closed is the 3rd column
    expect(cols[2]).toBe('');
  });

  it('produces a valid total row count for multiple trades', () => {
    const trades = [makeTrade(), makeTrade({ id: 't2', symbol: 'AAPL' })];
    expect(buildAdherenceCsv(trades).split('\n')).toHaveLength(3);
  });
});

describe('csvClosedDate', () => {
  it('formats the closed date or returns empty for open trades', () => {
    expect(csvClosedDate(makeTrade())).not.toBe('');
    expect(csvClosedDate(makeTrade({ closedAt: null }))).toBe('');
  });
});
