import { useRef, useState, useMemo, useCallback, type ReactNode } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ChevronUp, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatPrice, formatLargeNumber, changePct } from '@/lib/format';
import type { TVScoredTicker, TVDataFields } from '@/types/screener';

// ── Column metadata — defines ALL available columns and their defaults ───────

export interface ColumnMeta {
  key: string;
  label: string;
  /** Relative width weight — normalised to sum to 100% at render time. */
  weight: number;
  /** Columns the user cannot hide. */
  alwaysOn: boolean;
}

export const ALL_COLUMNS_META: ColumnMeta[] = [
  { key: 'symbol',      label: 'Symbol',      weight: 8,  alwaysOn: true  },
  { key: 'price',       label: 'Price',       weight: 10, alwaysOn: true  },
  { key: 'score',       label: 'Scr',         weight: 6,  alwaysOn: true  },
  { key: 'change',      label: 'Change',      weight: 13, alwaysOn: true  },
  { key: 'entry',       label: 'Entry/SL',    weight: 12, alwaysOn: true  },
  { key: 'confluence',  label: 'Confluence',  weight: 14, alwaysOn: true  },
  { key: 'volume',      label: 'Volume',      weight: 10, alwaysOn: true  },
  { key: 'rs_rating',   label: 'RS Rtg',      weight: 6,  alwaysOn: false },
  { key: 'inst_qual',   label: 'Inst Q',      weight: 6,  alwaysOn: false },
  { key: 'conviction',  label: 'Conv',        weight: 6,  alwaysOn: false },
  { key: 'market_cap',  label: 'Mkt Cap',     weight: 8,  alwaysOn: false },
  { key: 'pe_ratio',    label: 'P/E',         weight: 6,  alwaysOn: false },
  { key: 'eps',         label: 'EPS',         weight: 6,  alwaysOn: false },
  { key: 'div_yield',   label: 'Div %',       weight: 6,  alwaysOn: false },
  { key: 'rel_vol',     label: 'Rel Vol',     weight: 6,  alwaysOn: false },
  { key: 'rsi',         label: 'RSI',         weight: 5,  alwaysOn: false },
  { key: 'adx',         label: 'ADX',         weight: 5,  alwaysOn: false },
  { key: 'vol_change',  label: 'Vol %',       weight: 6,  alwaysOn: false },
  { key: 'atr_pct',     label: 'ATR%',        weight: 6,  alwaysOn: false },
  { key: 'sector',      label: 'Sector',      weight: 7,  alwaysOn: false },
  { key: 'rating',      label: 'Rtg',         weight: 8,  alwaysOn: true  },
];

/** Default set of visible column keys — everything except Div %, Rel Vol, and Vol %. */
export const DEFAULT_VISIBLE_COLUMNS: string[] = ALL_COLUMNS_META
  .filter((m) => m.key !== 'div_yield' && m.key !== 'rel_vol' && m.key !== 'vol_change')
  .map((m) => m.key);

// ── Helpers ──────────────────────────────────────────────────────────────────

// ── Cell renderers ───────────────────────────────────────────────────────────

function CellSymbol({ symbol, ticker, convergenceCount }: {
  symbol: string;
  ticker?: TVScoredTicker;
  convergenceCount?: number;
}) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="font-semibold text-text-primary text-sm tracking-tight">{symbol}</span>
      {ticker?.probable_fund && (
        <span className="inline-flex items-center justify-center h-[14px] px-[4px] rounded bg-warning/20 text-warning text-[9px] font-bold leading-none uppercase" title={ticker.probable_fund_reason ?? 'Probable fund'}>
          Fund
        </span>
      )}
      {convergenceCount != null && convergenceCount > 1 && (
        <span className="inline-flex items-center justify-center min-w-[14px] h-[14px] px-[3px] rounded bg-accent/20 text-accent text-[10px] font-bold leading-none" title={`Matched ${convergenceCount} templates`}>
          {convergenceCount}x
        </span>
      )}
    </span>
  );
}

function CellPrice({ value }: { value: number }) {
  return <span className="font-mono text-sm tabular-nums text-text-primary">{formatPrice(value)}</span>;
}

function CellScore({ score }: { score: number }) {
  const color =
    score >= 70 ? 'bg-accent/15 text-accent' :
    score >= 40 ? 'bg-warning/15 text-warning' :
    'bg-loss/15 text-loss';
  return (
    <span className={cn('inline-flex items-center justify-center w-8 h-[18px] rounded-[3px] text-[11px] font-bold leading-none', color)}>
      {score}
    </span>
  );
}

function CellChange({ change, price }: { change: number; price: number }) {
  const pct = changePct(price, change);
  const isGain = change >= 0;
  return (
    <span className={cn('font-mono text-sm tabular-nums', isGain ? 'text-gain' : 'text-loss')}>
      <span>{isGain ? '+' : ''}{change.toFixed(2)}</span>
      {pct != null && (
        <span className={cn('ml-1.5 text-xs', isGain ? 'text-gain/70' : 'text-loss/70')}>
          {isGain ? '+' : ''}{pct.toFixed(2)}%
        </span>
      )}
    </span>
  );
}

function CellEntry({ ticker }: { ticker: TVScoredTicker }) {
  return (
    <span className="font-mono text-sm tabular-nums text-text-primary">
      {formatPrice(ticker.entry)}
      <span className="text-text-muted ml-1 text-xs">/ {formatPrice(ticker.stop_loss)}</span>
    </span>
  );
}

function CellConfluence({ breakdown }: { breakdown: Record<string, number> }) {
  return (
    <span className="text-xs tabular-nums leading-none">
      <span className="text-info">T{breakdown.trend ?? 0}</span>
      <span className="text-text-muted mx-1">·</span>
      <span className="text-accent">M{breakdown.momentum ?? 0}</span>
      <span className="text-text-muted mx-1">·</span>
      <span className="text-warning">V{breakdown.volume ?? 0}</span>
      <span className="text-text-muted mx-1">·</span>
      <span className="text-purple-400">Q{breakdown.quality ?? 0}</span>
      <span className="text-text-muted mx-1">·</span>
      <span className="text-cyan-400">F{breakdown.fundamental ?? 0}</span>
    </span>
  );
}

function CellSector({ sector }: { sector?: string }) {
  if (!sector) return <span className="text-xs text-text-muted">—</span>;
  return (
    <span className="text-xs text-text-secondary truncate max-w-[120px] block" title={sector}>
      {sector}
    </span>
  );
}

function CellVolume({ data }: { data: TVDataFields }) {
  return (
    <span className="font-mono text-sm tabular-nums text-volume">
      {formatLargeNumber(data.volume ?? 0)}
      {data.relative_volume_10d_calc != null && (
        <span className="ml-1 text-xs text-text-muted">
          ×{data.relative_volume_10d_calc.toFixed(1)}
        </span>
      )}
    </span>
  );
}

function CellRating({ rating }: { rating: string }) {
  const text = rating.toLowerCase();
  const isBuy = text.includes('buy');
  const isSell = text.includes('sell');
  const isStrong = text.includes('strong');
  const color = isBuy
    ? 'bg-accent/15 text-accent'
    : isSell
    ? 'bg-loss/15 text-loss'
    : 'bg-surface-hover/50 text-text-muted';
  const display = isStrong
    ? (isBuy ? 'SB' : 'SS')
    : isBuy ? 'B' : isSell ? 'S' : rating.charAt(0).toUpperCase();
  return (
    <span className={cn('inline-flex items-center justify-center w-6 h-[18px] rounded-[3px] text-[11px] font-bold leading-none', color)}>
      {display}
    </span>
  );
}

function CellMarketCap({ data }: { data: TVDataFields }) {
  if (data.market_cap_basic == null) return <span className="text-xs text-text-muted">—</span>;
  return (
    <span className="font-mono text-xs tabular-nums text-text-secondary">
      {formatLargeNumber(data.market_cap_basic)}
    </span>
  );
}

function CellPERatio({ data }: { data: TVDataFields }) {
  if (data.price_earnings_ttm == null) return <span className="text-xs text-text-muted">—</span>;
  return (
    <span className="font-mono text-xs tabular-nums text-text-secondary">
      {data.price_earnings_ttm.toFixed(1)}
    </span>
  );
}

function CellDivYield({ data }: { data: TVDataFields }) {
  if (data.dividends_yield_current == null) return <span className="text-xs text-text-muted">—</span>;
  return (
    <span className="font-mono text-xs tabular-nums text-text-secondary">
      {data.dividends_yield_current.toFixed(2)}%
    </span>
  );
}

function CellEPS({ data }: { data: TVDataFields }) {
  if (data.earnings_per_share_diluted_ttm == null) return <span className="text-xs text-text-muted">—</span>;
  return (
    <span className="font-mono text-xs tabular-nums text-text-secondary">
      {data.earnings_per_share_diluted_ttm.toFixed(2)}
    </span>
  );
}

function CellRelVol({ data }: { data: TVDataFields }) {
  if (data.relative_volume_10d_calc == null) return <span className="text-xs text-text-muted">—</span>;
  return (
    <span className="font-mono text-xs tabular-nums text-text-secondary">
      ×{data.relative_volume_10d_calc.toFixed(1)}
    </span>
  );
}

function CellRSI({ data }: { data: TVDataFields }) {
  if (data.RSI == null) return <span className="text-xs text-text-muted">—</span>;
  const color =
    data.RSI > 70 ? 'text-loss' :
    data.RSI < 30 ? 'text-accent' :
    'text-text-primary';
  return (
    <span className={cn('font-mono text-xs tabular-nums', color)}>
      {Math.round(data.RSI)}
    </span>
  );
}

function CellADX({ data }: { data: TVDataFields }) {
  if (data.ADX == null) return <span className="text-xs text-text-muted">—</span>;
  const color =
    data.ADX > 50 ? 'text-loss' :
    data.ADX > 40 ? 'text-orange-400' :
    data.ADX > 25 ? 'text-accent' :
    data.ADX > 20 ? 'text-warning' :
    'text-text-muted';
  return (
    <span className={cn('font-mono text-xs tabular-nums', color)}>
      {Math.round(data.ADX)}
    </span>
  );
}

function CellVolChange({ data }: { data: TVDataFields }) {
  if (data.volume_change == null) return <span className="text-xs text-text-muted">—</span>;
  const isGain = data.volume_change > 0;
  return (
    <span className={cn('font-mono text-xs tabular-nums', isGain ? 'text-gain' : 'text-loss')}>
      {isGain ? '+' : ''}{Math.round(data.volume_change)}%
    </span>
  );
}

function CellRSRating({ rating }: { rating?: number }) {
  if (rating == null) return <span className="text-xs text-text-muted">—</span>;
  const color =
    rating >= 80 ? 'text-accent' :
    rating >= 60 ? 'text-info' :
    rating >= 40 ? 'text-warning' :
    'text-loss';
  return (
    <span className={cn('font-mono text-xs tabular-nums font-bold', color)}>
      {rating}
    </span>
  );
}

function CellInstQuality({ quality }: { quality?: number }) {
  if (quality == null) return <span className="text-xs text-text-muted">—</span>;
  const color =
    quality >= 80 ? 'text-accent' :
    quality >= 60 ? 'text-info' :
    quality >= 40 ? 'text-warning' :
    'text-loss';
  return (
    <span className={cn('font-mono text-xs tabular-nums', color)}>
      {quality}
    </span>
  );
}

function CellConviction({ ticker }: { ticker: TVScoredTicker }) {
  const verdict = ticker.elite?.signal_conviction;
  if (!verdict) return <span className="text-xs text-text-muted">—</span>;
  const dotColor =
    verdict === 'high' ? 'bg-accent' :
    verdict === 'medium' ? 'bg-warning' :
    'bg-loss';
  return (
    <span className="flex items-center gap-1">
      <span className={cn('w-1.5 h-1.5 rounded-full', dotColor)} />
      <span className="text-xs font-medium text-text-secondary capitalize">{verdict}</span>
    </span>
  );
}

function CellATRPct({ data }: { data: TVDataFields }) {
  if (data.ATR == null || data.close == null) return <span className="text-xs text-text-muted">—</span>;
  const atrPct = (data.ATR / data.close) * 100;
  const color =
    atrPct > 5 ? 'text-loss' :
    atrPct > 3 ? 'text-orange-400' :
    atrPct > 1 ? 'text-text-primary' :
    'text-text-muted';
  return (
    <span className={cn('font-mono text-xs tabular-nums', color)}>
      {atrPct.toFixed(1)}%
    </span>
  );
}

// ── Column definition ────────────────────────────────────────────────────────

interface ColumnDef {
  key: string;
  label: string;
  align: 'left' | 'right' | 'center';
  render: (ticker: TVScoredTicker, data: TVDataFields, onClick?: () => void) => ReactNode;
  noSort?: boolean;
}

/** Lookup: column key → render function. */
const COL_RENDERERS: Record<string, (t: TVScoredTicker, d: TVDataFields, onClick?: () => void) => ReactNode> = {
  symbol:     (t) => <CellSymbol symbol={t.symbol} ticker={t} />,
  price:      (_t, d) => <CellPrice value={d.close} />,
  score:      (t, _d) => <CellScore score={t.score} />,
  change:     (_t, d) => <CellChange change={d.change} price={d.close} />,
  entry:      (t, _d) => <CellEntry ticker={t} />,
  confluence: (t, _d) => <CellConfluence breakdown={t.breakdown} />,
  volume:     (_t, d) => <CellVolume data={d} />,
  rs_rating:  (t, _d) => <CellRSRating rating={t.elite?.rs_rating} />,
  inst_qual:  (t, _d) => <CellInstQuality quality={t.elite?.inst_quality} />,
  conviction: (t, _d) => <CellConviction ticker={t} />,
  market_cap: (_t, d) => <CellMarketCap data={d} />,
  pe_ratio:   (_t, d) => <CellPERatio data={d} />,
  eps:        (_t, d) => <CellEPS data={d} />,
  div_yield:  (_t, d) => <CellDivYield data={d} />,
  rel_vol:    (_t, d) => <CellRelVol data={d} />,
  rsi:        (_t, d) => <CellRSI data={d} />,
  adx:        (_t, d) => <CellADX data={d} />,
  vol_change: (_t, d) => <CellVolChange data={d} />,
  atr_pct:    (_t, d) => <CellATRPct data={d} />,
  sector:     (_t, d) => <CellSector sector={d.sector} />,
  rating:     (t, _d) => <CellRating rating={t.rating} />,
};

/** Build sorted ColumnDef[] for visible columns, with normalised widths. */
function buildColumns(
  convergenceMap: ReadonlyMap<string, number> | null,
  visibleKeys: ReadonlySet<string>,
): { columns: ColumnDef[]; colPct: Record<string, number> } {
  // Filter + sort by ALL_COLUMNS_META order
  const visible = ALL_COLUMNS_META.filter((m) => visibleKeys.has(m.key));
  const totalWeight = visible.reduce((s, m) => s + m.weight, 0);

  const colPct: Record<string, number> = {};
  const columns: ColumnDef[] = visible.map((meta) => {
    const pct = (meta.weight / totalWeight) * 100;
    colPct[meta.key] = pct;

    const base = COL_RENDERERS[meta.key];
    const render = meta.key === 'symbol' && convergenceMap
      ? (t: TVScoredTicker) =>
          <CellSymbol symbol={t.symbol} ticker={t} convergenceCount={convergenceMap.get(t.symbol)} />
      : base;

    const align: 'left' | 'right' | 'center' =
      meta.key === 'symbol' || meta.key === 'sector' ? 'left' :
      meta.key === 'score' || meta.key === 'confluence' || meta.key === 'rating' ? 'center' :
      'right';

    return {
      key: meta.key,
      label: meta.label,
      align,
      render,
      noSort: meta.key === 'sector' || meta.key === 'rating',
    };
  });

  return { columns, colPct };
}

// ── Header (flex-based) ──────────────────────────────────────────────────────

function SortIcon({ active, dir }: { active: boolean; dir: 'asc' | 'desc' }) {
  if (!active) return <ChevronUp className="w-3 h-3 text-text-muted/15" />;
  return dir === 'asc'
    ? <ChevronUp className="w-3 h-3 text-accent" />
    : <ChevronDown className="w-3 h-3 text-accent" />;
}

function ColumnHeader({ column, colPct, sortKey, sortDir, onSort }: {
  column: ColumnDef;
  colPct: Record<string, number>;
  sortKey: string | null;
  sortDir: 'asc' | 'desc' | null;
  onSort: (key: string) => void;
}) {
  const isActive = sortKey === column.key;
  return (
    <div
      className={cn(
        'flex items-center h-10 px-3 text-[11px] font-semibold uppercase select-none border-r border-border/10 last:border-r-0',
        column.align === 'right' && 'justify-end',
        column.align === 'center' && 'justify-center',
        'tracking-wider text-text-muted cursor-pointer hover:text-text-primary/80 transition-colors',
        isActive && 'text-accent',
      )}
      style={{ flex: `0 0 ${colPct[column.key]}%` }}
      onClick={() => !column.noSort && onSort(column.key)}
    >
      {column.label && <span className="truncate">{column.label}</span>}
      {!column.noSort && <SortIcon active={isActive} dir={isActive && sortDir ? sortDir : 'asc'} />}
    </div>
  );
}

// ── Empty state ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center p-8">
        <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-surface border border-border flex items-center justify-center">
          <svg className="w-7 h-7 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <h3 className="text-base font-medium text-text-primary mb-1">No Results</h3>
        <p className="text-sm text-text-muted max-w-xs mx-auto">
          Configure your filters and run a screen to discover trading opportunities
        </p>
      </div>
    </div>
  );
}

// ── Props ────────────────────────────────────────────────────────────────────

interface ScreenerTableProps {
  results: TVScoredTicker[];
  onRowClick: (ticker: TVScoredTicker) => void;
  sortState: { key: string | null; dir: 'asc' | 'desc' | null };
  onSort: (key: string) => void;
  currentPage: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  convergenceMap?: ReadonlyMap<string, number> | null;
  /** Set of visible column keys. Defaults to ALL_COLUMNS_META filterable keys. */
  visibleColumns?: ReadonlySet<string>;
}

const ROW_H = 40;

// ── Data row ─────────────────────────────────────────────────────────────────

function DataRow({
  ticker,
  data,
  isEven,
  columns,
  colPct,
  onRowClick,
}: {
  ticker: TVScoredTicker;
  data: TVDataFields;
  isEven: boolean;
  columns: ColumnDef[];
  colPct: Record<string, number>;
  onRowClick: (t: TVScoredTicker) => void;
}) {
  return (
    <div
      className={cn(
        'group flex items-center w-full border-b border-border/20 transition-all duration-100 cursor-pointer',
        isEven ? 'bg-background' : 'bg-surface',
        'hover:bg-accent/[0.03]',
      )}
      style={{ height: ROW_H }}
      onClick={() => onRowClick(ticker)}
    >
      {columns.map((col) => {
        const isSticky = col.key === 'symbol';
        return (
          <div
            key={col.key}
            className={cn(
              'flex items-center h-full px-3 text-sm whitespace-nowrap border-r border-border/10 last:border-r-0 overflow-hidden',
              isSticky && 'sticky left-0 z-10',
              isSticky && (isEven ? 'bg-background' : 'bg-surface'),
              isSticky && 'group-hover:bg-accent/[0.03]',
              col.align === 'right' && 'justify-end',
              col.align === 'center' && 'justify-center',
            )}
            style={{ flex: `0 0 ${colPct[col.key]}%` }}
          >
            {col.render(ticker, data, () => onRowClick(ticker))}
          </div>
        );
      })}
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────────────────────

export function ScreenerTable({
  results,
  onRowClick,
  sortState,
  onSort,
  currentPage,
  pageSize,
  onPageChange,
  onPageSizeChange,
  convergenceMap = null,
  visibleColumns,
}: ScreenerTableProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const [sortKey, setSortKey] = useState<string | null>(sortState.key);
  const [sortDir, setSortDir] = useState<'asc' | 'desc' | null>(sortState.dir);

  // Resolve which columns to show
  const defaultVisible = useMemo(
    () => new Set(DEFAULT_VISIBLE_COLUMNS),
    [],
  );
  const vKeys = visibleColumns ?? defaultVisible;

  const { columns, colPct } = useMemo(
    () => buildColumns(convergenceMap, vKeys),
    [convergenceMap, vKeys],
  );

  if (sortState.key !== sortKey || sortState.dir !== sortDir) {
    setSortKey(sortState.key);
    setSortDir(sortState.dir);
  }

  const sortedData = useMemo(() => {
    if (!sortKey || !sortDir) return results;
    return [...results].sort((a, b) => {
      const da = a.tv_data;
      const db = b.tv_data;
      let aVal: number | string = 0;
      let bVal: number | string = 0;
      switch (sortKey) {
        case 'symbol':   aVal = a.symbol; bVal = b.symbol; break;
        case 'price':    aVal = da.close ?? 0; bVal = db.close ?? 0; break;
        case 'score':    aVal = a.score; bVal = b.score; break;
        case 'change':   aVal = da.change ?? 0; bVal = db.change ?? 0; break;
        case 'entry':    aVal = a.entry; bVal = b.entry; break;
        case 'confluence': aVal = a.score; bVal = b.score; break;
        case 'volume':   aVal = da.volume ?? 0; bVal = db.volume ?? 0; break;
        case 'market_cap': aVal = da.market_cap_basic ?? 0; bVal = db.market_cap_basic ?? 0; break;
        case 'pe_ratio': aVal = da.price_earnings_ttm ?? 0; bVal = db.price_earnings_ttm ?? 0; break;
        case 'eps': aVal = da.earnings_per_share_diluted_ttm ?? 0; bVal = db.earnings_per_share_diluted_ttm ?? 0; break;
        case 'div_yield': aVal = da.dividends_yield_current ?? 0; bVal = db.dividends_yield_current ?? 0; break;
        case 'rel_vol':  aVal = da.relative_volume_10d_calc ?? 0; bVal = db.relative_volume_10d_calc ?? 0; break;
        case 'rsi':      aVal = da.RSI ?? 0; bVal = db.RSI ?? 0; break;
        case 'adx':      aVal = da.ADX ?? 0; bVal = db.ADX ?? 0; break;
        case 'vol_change': aVal = da.volume_change ?? 0; bVal = db.volume_change ?? 0; break;
        case 'atr_pct':  aVal = da.ATR != null && da.close != null ? (da.ATR / da.close) * 100 : 0; bVal = db.ATR != null && db.close != null ? (db.ATR / db.close) * 100 : 0; break;
        case 'rating':   aVal = a.rating; bVal = b.rating; break;
        case 'rs_rating': aVal = a.elite?.rs_rating ?? 0; bVal = b.elite?.rs_rating ?? 0; break;
        case 'inst_qual': aVal = a.elite?.inst_quality ?? 0; bVal = b.elite?.inst_quality ?? 0; break;
        default:         aVal = 0; bVal = 0;
      }
      if (typeof aVal === 'string') {
        return sortDir === 'asc'
          ? aVal.localeCompare(bVal as string)
          : (bVal as string).localeCompare(aVal);
      }
      return sortDir === 'asc'
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });
  }, [results, sortKey, sortDir]);

  const handleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        if (sortDir === null) setSortDir('asc');
        else if (sortDir === 'asc') setSortDir('desc');
        else { setSortKey(null); setSortDir(null); }
      } else {
        setSortKey(key);
        setSortDir('asc');
      }
      onSort(key);
    },
    [sortKey, sortDir, onSort]
  );

  const totalPages = Math.ceil(sortedData.length / pageSize);
  const paginatedData = sortedData.slice(
    currentPage * pageSize,
    (currentPage + 1) * pageSize
  );

  const virtualizer = useVirtualizer({
    count: paginatedData.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_H,
    overscan: 5,
  });

  if (results.length === 0) return <EmptyState />;

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();
  const paddingTop = virtualItems.length > 0 ? virtualItems[0].start : 0;
  const paddingBottom = virtualItems.length > 0
    ? totalSize - virtualItems[virtualItems.length - 1].end
    : 0;

  return (
    <div className="flex flex-col h-full">
      <div ref={parentRef} className="flex-1 overflow-auto">
        {/* Header — sticky at top */}
        <div className="sticky top-0 z-20 flex w-full bg-background/90 backdrop-blur-sm border-b border-border/50 shadow-[0_1px_8px_rgba(0,0,0,0.2)] min-w-[900px]">
          {columns.map((col) => (
            <ColumnHeader
              key={col.key}
              column={col}
              colPct={colPct}
              sortKey={sortKey}
              sortDir={sortDir}
              onSort={handleSort}
            />
          ))}
        </div>

        {/* Virtual list body */}
        <div className="w-full min-w-[900px]" style={{ height: totalSize }}>
          {/* Top spacer */}
          {paddingTop > 0 && <div style={{ height: paddingTop }} />}

          {/* Visible rows */}
          {virtualItems.map((virtualRow) => {
            const ticker = paginatedData[virtualRow.index];
            const data = ticker.tv_data ?? {} as TVDataFields;
            const rowIndex = currentPage * pageSize + virtualRow.index;

            return (
              <DataRow
                key={ticker.symbol}
                ticker={ticker}
                data={data}
                isEven={rowIndex % 2 === 0}
                columns={columns}
                colPct={colPct}
                onRowClick={onRowClick}
              />
            );
          })}

          {/* Bottom spacer */}
          {paddingBottom > 0 && <div style={{ height: paddingBottom }} />}
        </div>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between border-t border-border px-4 py-2.5 bg-background">
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span>Showing</span>
          <span className="font-mono text-text-primary tabular-nums">
            {sortedData.length > 0 ? currentPage * pageSize + 1 : 0}
          </span>
          <span>–</span>
          <span className="font-mono text-text-primary tabular-nums">
            {Math.min((currentPage + 1) * pageSize, sortedData.length)}
          </span>
          <span>of</span>
          <span className="font-mono text-text-primary tabular-nums">{sortedData.length}</span>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="select w-auto px-2 py-1 text-xs min-w-0"
            aria-label="Results per page"
          >
            {[10, 25, 50, 100].map((size) => (
              <option key={size} value={size}>{size} / page</option>
            ))}
          </select>

          <div className="flex items-center gap-0.5 ml-2">
            <button
              onClick={() => onPageChange(0)}
              disabled={currentPage === 0}
              className="btn-ghost p-1 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="First page"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <ChevronLeft className="w-3.5 h-3.5 -ml-2.5" />
            </button>
            <button
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage === 0}
              className="btn-ghost p-1 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>

            <div className="flex items-center gap-0.5 mx-1.5">
              {(() => {
                const buttons: number[] = [];
                const total = totalPages;
                const cur = currentPage;
                if (total <= 5) {
                  for (let i = 0; i < total; i++) buttons.push(i);
                } else if (cur <= 1) {
                  for (let i = 0; i < 5; i++) buttons.push(i);
                } else if (cur >= total - 2) {
                  for (let i = total - 5; i < total; i++) buttons.push(i);
                } else {
                  for (let i = cur - 2; i <= cur + 2; i++) buttons.push(i);
                }
                return buttons.map((pageNum) => (
                  <button
                    key={pageNum}
                    onClick={() => onPageChange(pageNum)}
                    className={cn(
                      'w-7 h-7 rounded text-xs font-medium transition-all',
                      pageNum === currentPage
                        ? 'bg-accent text-white'
                        : 'text-text-muted hover:bg-surface-hover hover:text-text-primary'
                    )}
                    aria-label={`Page ${pageNum + 1}`}
                    aria-current={pageNum === currentPage ? 'page' : undefined}
                  >
                    {pageNum + 1}
                  </button>
                ));
              })()}
            </div>

            <button
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage >= totalPages - 1}
              className="btn-ghost p-1 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Next page"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => onPageChange(totalPages - 1)}
              disabled={currentPage >= totalPages - 1}
              className="btn-ghost p-1 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Last page"
            >
              <ChevronRight className="w-3.5 h-3.5" />
              <ChevronRight className="w-3.5 h-3.5 -ml-2.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
