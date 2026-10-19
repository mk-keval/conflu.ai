import { describe, it, expect } from 'vitest';
import type { JournalRow, ReplayTrade, WorkflowRun } from '@/api/workflow';
import {
  RUNS_STRIP_DAYS,
  buildRunsStrip,
  filterJournalRows,
  filterReplayRows,
  shiftDateKey,
} from '../JournalTab';

// ── Fixtures ──

function row(over: Partial<JournalRow> = {}): JournalRow {
  return {
    date_entered: '2026-10-14',
    symbol: 'AAPL',
    sector: null,
    action: 'BUY',
    entry_type: null,
    entry_price: '228.50',
    stop_loss: '220.00',
    target_1: '245.00',
    target_2: '255.00',
    position_size_pct: '4.0',
    account_value: null,
    shares: null,
    confluence_count: null,
    signal_at_entry: null,
    gate_verdict: 'PASS',
    gate_failed_step: null,
    entry_low: null,
    entry_high: null,
    risk_reward_planned: null,
    gate_version: null,
    notes: null,
    date_closed: null,
    exit_price: null,
    exit_reason: null,
    realized_r: null,
    pnl_usd: null,
    mfe_r: null,
    mae_r: null,
    plan_adherence: null,
    template: null,
    regime: null,
    entry_timing: 'eod',
    ...over,
  };
}

function run(over: Partial<WorkflowRun> = {}): WorkflowRun {
  return {
    id: 1,
    run_date: '2026-10-16',
    ran_at: '2026-10-16T20:05:00Z',
    mode: 'run_close',
    apply: true,
    accepted: 0,
    rejected: 0,
    updated: 0,
    skipped: 0,
    status: 'ok',
    message: 'ok',
    details: null,
    ...over,
  };
}

// ── filterJournalRows ──

describe('filterJournalRows', () => {
  const today = '2026-10-16';
  const enteredToday = row({ date_entered: '2026-10-16', symbol: 'AAA' });
  const closedToday = row({
    date_entered: '2026-10-02',
    date_closed: '2026-10-16',
    symbol: 'BBB',
  });
  const openOlder = row({ date_entered: '2026-10-01', symbol: 'CCC' });
  const closedOlder = row({
    date_entered: '2026-09-20',
    date_closed: '2026-09-30',
    symbol: 'DDD',
  });
  const rows = [enteredToday, closedToday, openOlder, closedOlder];

  it('today matches rows entered OR closed today (after-close exits included)', () => {
    const out = filterJournalRows(rows, 'today', today);
    expect(out.map((r) => r.symbol)).toEqual(['AAA', 'BBB']);
  });

  it('open matches rows without date_closed', () => {
    const out = filterJournalRows(rows, 'open', today);
    expect(out.map((r) => r.symbol)).toEqual(['AAA', 'CCC']);
  });

  it('closed matches rows with date_closed', () => {
    const out = filterJournalRows(rows, 'closed', today);
    expect(out.map((r) => r.symbol)).toEqual(['BBB', 'DDD']);
  });

  it('all returns every row', () => {
    expect(filterJournalRows(rows, 'all', today)).toHaveLength(4);
  });
});

// ── shiftDateKey ──

describe('shiftDateKey', () => {
  it('shifts within a month', () => {
    expect(shiftDateKey('2026-10-18', -1)).toBe('2026-10-17');
    expect(shiftDateKey('2026-10-18', 1)).toBe('2026-10-19');
  });

  it('crosses month boundaries', () => {
    expect(shiftDateKey('2026-03-01', -1)).toBe('2026-02-28');
    expect(shiftDateKey('2026-02-28', 1)).toBe('2026-03-01');
  });

  it('crosses year boundaries', () => {
    expect(shiftDateKey('2026-01-01', -1)).toBe('2025-12-31');
  });
});

// ── buildRunsStrip ──

describe('buildRunsStrip', () => {
  it('returns the last N days ending today', () => {
    const strip = buildRunsStrip([], '2026-10-16');
    expect(strip).toHaveLength(RUNS_STRIP_DAYS);
    expect(strip[strip.length - 1].date).toBe('2026-10-16');
    expect(strip[0].date).toBe(shiftDateKey('2026-10-16', -(RUNS_STRIP_DAYS - 1)));
  });

  it('classifies days as ok / error / missed', () => {
    const strip = buildRunsStrip(
      [
        run({ run_date: '2026-10-14', status: 'ok' }),
        run({ id: 2, run_date: '2026-10-15', status: 'error' }),
      ],
      '2026-10-16',
      5
    );
    expect(strip.map((c) => [c.date, c.status])).toEqual([
      ['2026-10-12', 'missed'],
      ['2026-10-13', 'missed'],
      ['2026-10-14', 'ok'],
      ['2026-10-15', 'error'],
      ['2026-10-16', 'missed'],
    ]);
  });

  it('treats partial runs as errors', () => {
    const strip = buildRunsStrip(
      [run({ run_date: '2026-10-16', status: 'partial' })],
      '2026-10-16',
      1
    );
    expect(strip[0].status).toBe('error');
  });

  it('any error on a day wins over the ok runs', () => {
    const strip = buildRunsStrip(
      [
        run({ run_date: '2026-10-16', status: 'ok' }),
        run({ id: 2, run_date: '2026-10-16', status: 'error' }),
      ],
      '2026-10-16',
      1
    );
    expect(strip[0].status).toBe('error');
    expect(strip[0].runs).toHaveLength(2);
  });

  it('marks run-less weekends as weekend, not missed', () => {
    // 2026-10-18 is a Sunday; 17 (Sat) and 18 (Sun) are the weekend.
    const strip = buildRunsStrip([], '2026-10-18', 3);
    expect(strip.map((c) => c.status)).toEqual(['missed', 'weekend', 'weekend']);
  });
});

// ── filterReplayRows ──

function replayRow(over: Partial<ReplayTrade> = {}): ReplayTrade {
  return {
    id: 1,
    run_id: 1,
    signal_date: '2026-10-01',
    date_entered: '2026-10-02',
    symbol: 'AAA',
    template: 'bull-flag-continuation',
    regime: 'Cautious',
    regime_key: 'choppy',
    screen_rank: 1,
    screen_weight: 85,
    direction: 'long',
    entry_price: 100,
    stop_loss: 95,
    target_1: 110,
    exit_date: '2026-10-06',
    exit_price: 110,
    exit_reason: 'target',
    realized_r: 2,
    pnl_usd: 1900,
    risk_pct: 1,
    position_size_pct: 5,
    shares: 50,
    account_value: 100000,
    hold_bars: 3,
    rvol: 1.2,
    also_signaled_by: null,
    notes: null,
    ...over,
  };
}

describe('filterReplayRows', () => {
  const rows = [
    replayRow({ id: 1, symbol: 'WIN', pnl_usd: 1900 }),
    replayRow({ id: 2, symbol: 'LOSS', pnl_usd: -1000, realized_r: -1 }),
    replayRow({ id: 3, symbol: 'FLAT', pnl_usd: 0, realized_r: 0 }),
  ];

  it('winners are net-positive P&L', () => {
    expect(filterReplayRows(rows, 'wins').map((r) => r.symbol)).toEqual(['WIN']);
  });

  it('losers include scratches (net <= 0)', () => {
    expect(filterReplayRows(rows, 'losses').map((r) => r.symbol)).toEqual([
      'LOSS',
      'FLAT',
    ]);
  });

  it('all returns every row', () => {
    expect(filterReplayRows(rows, 'all')).toHaveLength(3);
  });
});
