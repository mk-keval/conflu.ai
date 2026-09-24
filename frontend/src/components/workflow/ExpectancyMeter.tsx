/**
 * Expectancy Meter (Slice 3 — Mission Surface)
 *
 * Displays rolling expectancy and profit factor over closed paper trades.
 * This is the north-star metric: positive expectancy = edge; negative = bleed.
 *
 * Metrics (plan Sec.2E / Slice 3):
 *   - Expectancy (R/trade) = avg(R) over closed trades
 *   - Profit Factor = gross wins / gross losses
 *   - Win Rate = % of trades with realized_r > 0
 *   - Avg Win (R) / Avg Loss (R)
 *
 * Rolling window defaults to 20 trades (ADHERENCE_WINDOW) for statistical meaning.
 */

import { useMemo } from 'react';
import { TrendingUp, TrendingDown, Target, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useWorkflowStore } from '@/store/workflowStore';
import type { PaperTrade } from '@/types/workflow';

const EXPECTANCY_WINDOW = 20;

export interface ExpectancyMetrics {
  expectancy: number; // avg R per trade
  profitFactor: number | '∞'; // gross wins / gross losses
  winRate: number; // % of trades with R > 0
  avgWinR: number;
  avgLossR: number;
  tradeCount: number;
  isMeaningful: boolean; // true when >= EXPECTANCY_WINDOW trades
}

/** Pure calculation — no React deps, fully testable. */
export function calculateExpectancy(
  trades: PaperTrade[],
  window: number = EXPECTANCY_WINDOW
): ExpectancyMetrics {
  const closed = trades
    .filter(
      (t): t is PaperTrade & { realizedR: number } =>
        t.status === 'closed' &&
        typeof t.realizedR === 'number' &&
        isFinite(t.realizedR)
    )
    .sort((a, b) => (a.closedAt ?? '').localeCompare(b.closedAt ?? ''))
    .slice(-window); // most recent N

  if (closed.length === 0) {
    return {
      expectancy: 0,
      profitFactor: 0,
      winRate: 0,
      avgWinR: 0,
      avgLossR: 0,
      tradeCount: 0,
      isMeaningful: false,
    };
  }

  const rs = closed.map((t) => t.realizedR);
  const wins = rs.filter((r) => r > 0);
  const losses = rs.filter((r) => r < 0);

  const grossWin = wins.reduce((sum, r) => sum + r, 0);
  const grossLoss = Math.abs(losses.reduce((sum, r) => sum + r, 0));

  const expectancy = rs.reduce((sum, r) => sum + r, 0) / rs.length;
  const profitFactor: number | '∞' = grossLoss > 0 ? grossWin / grossLoss : '∞';
  const winRate = wins.length / rs.length;
  const avgWinR = wins.length > 0 ? grossWin / wins.length : 0;
  const avgLossR = losses.length > 0 ? grossLoss / losses.length : 0;

  return {
    expectancy,
    profitFactor,
    winRate,
    avgWinR,
    avgLossR,
    tradeCount: closed.length,
    isMeaningful: closed.length >= window,
  };
}

/** Color helpers for expectancy meter. */
function expectancyColor(exp: number): string {
  if (exp > 0.2) return 'text-green-500 bg-green-500/10 border-green-500/30';
  if (exp > 0) return 'text-green-400 bg-green-400/10 border-green-400/30';
  if (exp > -0.2)
    return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30';
  return 'text-red-500 bg-red-500/10 border-red-500/30';
}

function pfColor(pf: number | '∞'): string {
  if (pf === '∞') return 'text-green-500';
  if (pf >= 1.5) return 'text-green-500';
  if (pf >= 1.0) return 'text-yellow-400';
  return 'text-red-500';
}

/** Big circular meter for expectancy (like the adherence meter). */
export function ExpectancyMeter() {
  const paperTrades = useWorkflowStore((s) => s.paperTrades);
  const metrics = useMemo(
    () => calculateExpectancy(paperTrades),
    [paperTrades]
  );

  const hasTrades = paperTrades.length > 0;
  const pfDisplay =
    metrics.profitFactor === '∞'
      ? '∞'
      : (metrics.profitFactor as number).toFixed(2);
  const pfCls = pfColor(metrics.profitFactor);
  const expCls = expectancyColor(metrics.expectancy);

  if (!hasTrades) {
    return (
      <div className="rounded-xl border border-border/50 bg-surface/20 p-8 text-center">
        <BarChart3 className="mx-auto h-10 w-10 text-text-muted" />
        <h3 className="mt-3 text-sm font-semibold text-text-primary">
          Expectancy Meter
        </h3>
        <p className="mx-auto mt-2 max-w-md text-xs text-text-muted">
          Log and close paper trades to see your expectancy. Positive expectancy
          = edge; negative expectancy = bleed. The math of survival.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Big meter */}
      <div className="rounded-xl border border-border/50 bg-surface/20 p-4 text-center">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
          <BarChart3 className="mr-1 inline h-3 w-3" />
          Rolling {EXPECTANCY_WINDOW}-trade expectancy
        </div>
        <div
          className={cn(
            'relative mx-auto flex h-32 w-32 items-center justify-center rounded-full border-4',
            expCls
          )}
        >
          <div className="text-center">
            <div className="text-3xl font-bold">
              {metrics.expectancy >= 0 ? '+' : ''}
              {metrics.expectancy.toFixed(2)}R
            </div>
            <div className="mt-1 text-[10px] text-text-muted">
              {metrics.tradeCount} trade{metrics.tradeCount === 1 ? '' : 's'}
            </div>
          </div>
        </div>
        <p className="mt-2 text-[11px] text-text-muted">
          {metrics.isMeaningful
            ? `Statistically meaningful (${EXPECTANCY_WINDOW} trades logged).`
            : `${EXPECTANCY_WINDOW - metrics.tradeCount} more closed trade${EXPECTANCY_WINDOW - metrics.tradeCount === 1 ? '' : 's'} until this number is battle-tested.`}
        </p>
      </div>

      {/* Supporting metrics grid */}
      <div className="grid grid-cols-2 gap-3">
        <MetricCard
          icon={Target}
          label="Profit Factor"
          value={pfDisplay}
          valueClass={pfCls}
          help="Gross wins / gross losses. > 1.0 = profitable edge."
        />
        <MetricCard
          icon={TrendingUp}
          label="Win Rate"
          value={`${(metrics.winRate * 100).toFixed(1)}%`}
          valueClass="text-text-primary"
          help="% of closed trades that made money."
        />
        <MetricCard
          icon={TrendingUp}
          label="Avg Win"
          value={`+${metrics.avgWinR.toFixed(2)}R`}
          valueClass="text-green-500"
          help="Average R on winning trades."
        />
        <MetricCard
          icon={TrendingDown}
          label="Avg Loss"
          value={`${metrics.avgLossR.toFixed(2)}R`}
          valueClass="text-red-500"
          help="Average R on losing trades (absolute value)."
        />
      </div>

      {/* Interpretation */}
      <div className="rounded-lg border border-border/30 bg-surface/10 px-3 py-2 text-xs text-text-secondary">
        <strong>Interpretation:</strong> Expectancy = (Win Rate × Avg Win) −
        (Loss Rate × Avg Loss). Positive expectancy means your system makes
        money per trade on average — this is the only number that matters for
        long-term survival. Profit Factor &gt; 1.0 confirms the same.
        {metrics.tradeCount < EXPECTANCY_WINDOW &&
          ' (Sample too small — treat as directional only.)'}
      </div>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  valueClass,
  help,
}: {
  icon: typeof Target;
  label: string;
  value: string;
  valueClass: string;
  help: string;
}) {
  return (
    <div className="rounded-xl border border-border/50 bg-surface/20 p-3">
      <div className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
        <Icon className="h-3 w-3" />
        {label}
      </div>
      <div className={cn('text-2xl font-bold', valueClass)}>{value}</div>
      <p className="mt-1 text-[10px] text-text-muted">{help}</p>
    </div>
  );
}
