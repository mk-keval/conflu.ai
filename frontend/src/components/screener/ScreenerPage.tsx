import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  fetchScreenTV,
  fetchTVTemplates,
  fetchTVTemplate,
} from '@/api/screener';
import type {
  TVScoredTicker,
  TVTemplate,
  ScreenTemplateDetail,
} from '@/types/screener';
import { useScreenStore } from '@/store/screen';
import { useMarketStore } from '@/store/market';
import { useSectorRotationStore } from '@/store/sectorRotation';
import { fetchSectorRotation } from '@/api/sectorRotation';
import { useWS } from '@/ws/WebSocketProvider';
import { screenerChannel } from '@/ws/channels';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { SkeletonTable } from '@/components/layout/LoadingSkeleton';
import { ScreenerTable } from './ScreenerTable';
import { ExportButtons } from './ExportButtons';
import { TemplateInfoStrip } from './TemplateInfoStrip';
import { ScreenerEducation } from './ScreenerEducation';
import type { WSMessage } from '@/types/ws';
import type { SectorRotationResponse } from '@/types/sector';
import { ChevronDown, Play, Loader2, RefreshCw, Columns, List, BookOpen, TrendingUp, TrendingDown, Activity, AlertTriangle, Gauge } from 'lucide-react';
import { cn } from '@/lib/cn';
import { ALL_COLUMNS_META, DEFAULT_VISIBLE_COLUMNS } from './ScreenerTable';

// ── Regime-to-screener recommendation mapping ──
// Maps market regime labels to recommended / avoid screener configs.
// Used by TemplateDropdown to show badges (✅ Recommended / ⚠️ Caution).
const REGIME_SCREENER_MAP: Record<string, { recommended: string[]; avoid: string[] }> = {
  Exuberance: {
    recommended: ['trend-follower', 'momentum-breakout', '52week-breakout', 'bull-flag-continuation', 'volatility-expansion', 'volume-surge-breakout'],
    avoid: ['mean-reversion', 'oversold-bounce', 'low-vol-setup'],
  },
  'Risk-On': {
    recommended: ['trend-follower', 'trend-follower-mtf', 'momentum-breakout', '52week-breakout', 'bull-flag-continuation', 'high-conviction-stack'],
    avoid: ['distribution', 'breakdown', 'oversold-bounce'],
  },
  Neutral: {
    recommended: ['high-conviction-stack', 'quality-trend-fundamentals', 'institutional-swing-quality', 'trend-follower-mtf', 'volume-trend-accumulation'],
    avoid: ['momentum-breakout', 'breakdown'],
  },
  Cautious: {
    recommended: ['low-vol-setup', 'mean-reversion', 'oversold-bounce', 'volume-trend-accumulation', 'quality-trend-fundamentals'],
    avoid: ['momentum-breakout', '52week-breakout', 'volatility-expansion'],
  },
  'Risk-Off': {
    recommended: ['oversold-bounce', 'distribution', 'low-vol-setup', 'mean-reversion'],
    avoid: ['trend-follower', 'momentum-breakout', '52week-breakout', 'bull-flag-continuation'],
  },
  Crisis: {
    recommended: [],
    avoid: [],  // All screeners are risky — show warning instead
  },
};

const DEFAULT_REGIME_RECOMMENDATION = { recommended: [], avoid: [] };

function getScreenerRecommendation(templateName: string, regimeLabel: string | null): 'recommended' | 'avoid' | null {
  if (!regimeLabel) return null;
  const mapping = REGIME_SCREENER_MAP[regimeLabel] ?? DEFAULT_REGIME_RECOMMENDATION;
  if (mapping.recommended.some((r) => templateName.toLowerCase().includes(r))) return 'recommended';
  if (mapping.avoid.some((r) => templateName.toLowerCase().includes(r))) return 'avoid';
  return null;
}

function RegimeBadge({ recommendation }: { recommendation: 'recommended' | 'avoid' | null }) {
  if (recommendation === 'recommended') {
    return (
      <span className="ml-auto text-[10px] font-semibold text-green-500 bg-green-500/10 px-1.5 py-0.5 rounded shrink-0 flex items-center gap-1">
        <span>Best for today</span>
      </span>
    );
  }
  if (recommendation === 'avoid') {
    return (
      <span className="ml-auto text-[10px] font-medium text-red-400 bg-red-400/10 px-1.5 py-0.5 rounded shrink-0">
        ⚠️
      </span>
    );
  }
  return null;
}

function ScreenerContent() {
  const selectedConfig = useScreenStore((s) => s.selectedConfig);
  const timeframes = useScreenStore((s) => s.timeframes);
  const setConfig = useScreenStore((s) => s.setConfig);
  const { subscribe, unsubscribe, onMessage } = useWS();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // State
  const [templates, setTemplates] = useState<TVTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<TVScoredTicker[]>([]);
  const [totalMatches, setTotalMatches] = useState(0);
  const [screenName, setScreenName] = useState('');
  const [executionTime, setExecutionTime] = useState(0);
  const [fetchedAt, setFetchedAt] = useState<string>('');
  // Sector filter: initialized from URL ?sector= param, cleared when results change
  const [sectorFilter, setSectorFilter] = useState<string>(() => searchParams.get('sector') || '');
  const [sortState, setSortState] = useState<{ key: string | null; dir: 'asc' | 'desc' | null }>({ key: 'score', dir: 'desc' });
  const [currentPage, setCurrentPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [activeTab, setActiveTab] = useState<'results' | 'learn'>('results');
  const [templateDetails, setTemplateDetails] = useState<ScreenTemplateDetail | null>(null);

  // Column visibility — persisted in localStorage
  const COL_KEY = 'screener:visible-columns';
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(COL_KEY);
      if (saved) return new Set(JSON.parse(saved));
    } catch {}
    return new Set(DEFAULT_VISIBLE_COLUMNS);
  });

  const toggleColumn = useCallback((key: string) => {
    setVisibleColumns((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      localStorage.setItem(COL_KEY, JSON.stringify([...next]));
      return next;
    });
  }, []);

  // Multi-template convergence tracking: ticker → set of template names
  const MAX_CONVERGENCE_RUNS = 5;
  const [templateRuns, setTemplateRuns] = useState<{ template: string; tickers: string[] }[]>([]);
  const convergenceMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const run of templateRuns) {
      for (const ticker of run.tickers) {
        map.set(ticker, (map.get(ticker) ?? 0) + 1);
      }
    }
    return map;
  }, [templateRuns]);

  // Fetch templates on mount
  useEffect(() => {
    fetchTVTemplates()
      .then(setTemplates)
      .catch(console.error);
  }, []);

  // Update selected template when config or templates change
  useEffect(() => {
    if (templates.length === 0) return;

    // Normalise both sides for fuzzy matching (handles old hyphenated store values)
    const norm = (s: string) => s.toLowerCase().replace(/[-\s]+/g, '');

    const exact = templates.find((t) => t.name === selectedConfig);
    if (exact) {
      setSelectedTemplate(exact.name);
      setScreenName(exact.name);
      return;
    }

    const fuzzy = templates.find((t) => norm(t.name) === norm(selectedConfig));
    if (fuzzy) {
      setSelectedTemplate(fuzzy.name);
      setScreenName(fuzzy.name);
      setConfig(fuzzy.name);
      return;
    }

    // Fall back to first template
    setSelectedTemplate(templates[0].name);
    setScreenName(templates[0].name);
    setConfig(templates[0].name);
  }, [selectedConfig, templates, setConfig]);

  // Fetch template details for the info strip + learn tab
  useEffect(() => {
    if (!selectedTemplate) return;
    fetchTVTemplate(selectedTemplate)
      .then((data) => setTemplateDetails(data as unknown as ScreenTemplateDetail))
      .catch(() => setTemplateDetails(null));
  }, [selectedTemplate]);

  // Fetch screen data
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['screen-tv', selectedConfig, timeframes],
    queryFn: async () => {
      setIsRunning(true);
      try {
        const response = await fetchScreenTV(selectedConfig, 500);
        return response;
      } finally {
        setIsRunning(false);
      }
    },
    staleTime: Infinity,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    enabled: !!selectedConfig,
  });

  // Update results when data changes
  useEffect(() => {
    if (data) {
      setResults(data.results);
      setTotalMatches(data.total_matches);
      setExecutionTime(data.execution_ms);
      setFetchedAt(data.fetched_at);
      setScreenName(data.screen_name.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));
      setCurrentPage(0); // Reset to first page on new results

      // Update convergence tracking (keep last N runs)
      const tickers = data.results.map((r) => r.symbol);
      setTemplateRuns((prev) => {
        const next = [...prev, { template: selectedTemplate, tickers }];
        if (next.length > MAX_CONVERGENCE_RUNS) next.shift();
        return next;
      });
    }
  }, [data, selectedTemplate]);

  // WS subscription for real-time updates
  useEffect(() => {
    const channel = screenerChannel(selectedConfig);
    subscribe(channel);
    return () => unsubscribe(channel);
  }, [selectedConfig, subscribe, unsubscribe]);

  // Handle WS messages
  useEffect(() => {
    const unsub = onMessage((message: WSMessage) => {
      if (message.type === 'screen_update') {
        // Note: WS uses legacy ScreenSymbolResult type, TV screener uses TVScoredTicker
        // For now, we rely on refetch interval for TV screener updates
        // TODO: Update WS to use TVScoredTicker type
      }
    });
    return unsub;
  }, [onMessage]);

  const handleRunScreen = useCallback(async () => {
    await refetch();
  }, [refetch]);

  const handleTemplateChange = useCallback((templateName: string) => {
    setSelectedTemplate(templateName);
    const template = templates.find((t) => t.name === templateName);
    if (template) {
      setConfig(templateName);
      setScreenName(template.name.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));
    }
  }, [templates, setConfig]);

  const handleSort = useCallback((key: string) => {
    setSortState(prev => {
      if (prev.key === key) {
        if (prev.dir === null) return { key, dir: 'asc' };
        if (prev.dir === 'asc') return { key, dir: 'desc' };
        return { key: null, dir: null };
      }
      return { key, dir: 'asc' };
    });
    setCurrentPage(0);
  }, []);

  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  const handlePageSizeChange = useCallback((size: number) => {
    setPageSize(size);
    setCurrentPage(0);
  }, []);

  const handleRowClick = useCallback((ticker: TVScoredTicker) => {
    navigate(`/ticker/${ticker.symbol}`);
  }, [navigate]);

  // ── Sector filter logic ──
  // Extract unique sectors from results for the filter pills
  // Also reset sector filter when results change to a different sector set
  const uniqueSectors = useMemo(() => {
    const sectors = new Set<string>();
    for (const r of results) {
      const s = r.tv_data?.sector;
      if (s) sectors.add(s);
    }
    return [...sectors].sort();
  }, [results]);

  // Clear sector filter when it no longer matches any result sector
  useEffect(() => {
    if (sectorFilter && !uniqueSectors.includes(sectorFilter)) {
      setSectorFilter('');
    }
  }, [uniqueSectors, sectorFilter]);

  // Filtered results driven by the active sector pill
  const filteredResults = useMemo(() => {
    if (!sectorFilter) return results;
    return results.filter((r) => r.tv_data?.sector === sectorFilter);
  }, [results, sectorFilter]);

  if (isLoading && results.length === 0) {
    return (
      <div className="flex h-full flex-col">
        <ScreenerHeader
          screenName={screenName}
          totalMatches={0}
          templates={templates}
          selectedTemplate={selectedTemplate}
          onTemplateChange={handleTemplateChange}
          isRunning={true}
          onRunScreen={handleRunScreen}
          executionTime={0}
          fetchedAt=""
          visibleColumns={visibleColumns}
          onToggleColumn={toggleColumn}
        />
        <div className="flex-1 overflow-auto">
          <SkeletonTable rows={8} className="p-4" />
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex h-full flex-col">
        <ScreenerHeader
          screenName={screenName}
          totalMatches={0}
          templates={templates}
          selectedTemplate={selectedTemplate}
          onTemplateChange={handleTemplateChange}
          isRunning={false}
          onRunScreen={handleRunScreen}
          executionTime={0}
          fetchedAt=""
          visibleColumns={visibleColumns}
          onToggleColumn={toggleColumn}
        />
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-loss-bg flex items-center justify-center">
              <svg className="w-8 h-8 text-loss" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-text-primary mb-1">Error Loading Data</h3>
            <p className="text-text-muted mb-4">{(error as Error)?.message || 'Unknown error occurred'}</p>
            <button onClick={handleRunScreen} className="btn-primary">
              <RefreshCw className="w-4 h-4 mr-2" />
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <ScreenerHeader
        screenName={screenName}
        totalMatches={totalMatches}
        templates={templates}
        selectedTemplate={selectedTemplate}
        onTemplateChange={handleTemplateChange}
        isRunning={isRunning}
        onRunScreen={handleRunScreen}
        executionTime={executionTime}
        fetchedAt={fetchedAt}
        visibleColumns={visibleColumns}
        onToggleColumn={toggleColumn}
      />

      {/* Market overview panel — collapsible context hint */}
      <MarketOverviewPanel />

      {/* Sector focus banner — top sectors from rotation, clickable to filter */}
      <SectorFocusBanner onSelectSector={(sector) => setSectorFilter(sector)} />

      {/* Template info strip — always visible */}
      <TemplateInfoStrip template={templateDetails} />

      {/* Tab navigation */}
      <div className="flex border-b border-border bg-surface/20 px-4">
        {([
          { key: 'results' as const, label: 'Results', icon: <List className="h-4 w-4" /> },
          { key: 'learn' as const, label: 'Learn', icon: <BookOpen className="h-4 w-4" /> },
        ]).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'flex items-center gap-2 border-b-2 px-5 py-3 text-sm font-semibold transition-colors',
              activeTab === tab.key
                ? 'border-accent text-accent'
                : 'border-transparent text-text-muted hover:text-text-primary hover:border-border'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'results' ? (
        <div className="flex-1 overflow-hidden relative flex flex-col">
          {/* Sector filter pills */}
          {uniqueSectors.length > 0 && (
            <div className="flex items-center gap-1.5 px-4 py-2 border-b border-border/30 shrink-0 overflow-x-auto">
              <button
                onClick={() => setSectorFilter('')}
                className={`text-xs px-2.5 py-1 rounded-full border transition-colors whitespace-nowrap ${
                  !sectorFilter
                    ? 'bg-accent/10 border-accent/30 text-accent font-medium'
                    : 'border-border/50 text-text-muted hover:text-text-primary hover:border-text-muted/30'
                }`}
              >
                All ({results.length})
              </button>
              {uniqueSectors.map((sector) => {
                const count = results.filter((r) => r.tv_data?.sector === sector).length;
                const isActive = sectorFilter === sector;
                return (
                  <button
                    key={sector}
                    onClick={() => setSectorFilter(isActive ? '' : sector)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors whitespace-nowrap ${
                      isActive
                        ? 'bg-accent/10 border-accent/30 text-accent font-medium'
                        : 'border-border/50 text-text-muted hover:text-text-primary hover:border-text-muted/30'
                    }`}
                  >
                    {sector} ({count})
                  </button>
                );
              })}
            </div>
          )}
          <div className="flex-1 overflow-hidden">
            <ScreenerTable
              results={filteredResults}
              onRowClick={handleRowClick}
              sortState={sortState}
              onSort={handleSort}
              currentPage={currentPage}
              pageSize={pageSize}
              onPageChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
              convergenceMap={convergenceMap}
              visibleColumns={visibleColumns}
            />
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4">
          <ScreenerEducation template={templateDetails} />
        </div>
      )}
    </div>
  );
}

function formatElapsed(isoString: string): string {
  const elapsed = Date.now() - new Date(isoString).getTime();
  if (elapsed < 1000) return 'just now';
  if (elapsed < 60_000) return `${Math.floor(elapsed / 1000)}s ago`;
  if (elapsed < 3_600_000) return `${Math.floor(elapsed / 60_000)}m ago`;
  return `${Math.floor(elapsed / 3_600_000)}h ago`;
}

function FreshnessBadge({ fetchedAt }: { fetchedAt: string }) {
  const [label, setLabel] = useState(() => formatElapsed(fetchedAt));

  useEffect(() => {
    setLabel(formatElapsed(fetchedAt));
    const interval = setInterval(() => setLabel(formatElapsed(fetchedAt)), 10_000);
    return () => clearInterval(interval);
  }, [fetchedAt]);

  if (!fetchedAt) return null;

  const color = label === 'just now' || label.endsWith('s ago')
    ? 'text-accent'
    : label.endsWith('m ago')
    ? 'text-warning'
    : 'text-loss';

  return (
    <span className={cn('inline-flex items-center gap-1 text-xs', color)} title={fetchedAt}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}

function ColumnCustomizer({
  visibleColumns,
  onToggle,
}: {
  visibleColumns: Set<string>;
  onToggle: (key: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close on outside click — check BOTH the parent wrapper AND the portal dropdown
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      const isOutsideParent = ref.current && !ref.current.contains(target);
      const isOutsideDropdown = dropdownRef.current && !dropdownRef.current.contains(target);
      if (isOutsideParent && isOutsideDropdown) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const toggleable = ALL_COLUMNS_META.filter((m) => !m.alwaysOn);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});

  useEffect(() => {
    if (!open || !btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setDropdownStyle({
      position: 'fixed',
      right: document.documentElement.clientWidth - rect.right,
      top: rect.bottom + 4,
      zIndex: 9999,
    });
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        ref={btnRef}
        onClick={() => setOpen((p) => !p)}
        className="btn-ghost p-2 text-text-muted hover:text-text-primary"
        aria-label="Customize columns"
        title="Customize columns"
      >
        <Columns className="w-4 h-4" />
      </button>
      {open && createPortal(
        <div
          ref={dropdownRef}
          style={dropdownStyle}
          className="w-44 bg-surface-elevated border border-border/50 rounded-lg shadow-xl py-1"
        >
          {toggleable.map((meta) => (
            <label
              key={meta.key}
              className="flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:bg-surface-hover/40 cursor-pointer select-none"
            >
              <input
                type="checkbox"
                checked={visibleColumns.has(meta.key)}
                onChange={() => onToggle(meta.key)}
                className="accent-accent"
              />
              {meta.label}
            </label>
          ))}
        </div>,
        document.body
      )}
    </div>
  );
}

function ScreenerHeader({
  screenName,
  totalMatches,
  templates,
  selectedTemplate,
  onTemplateChange,
  isRunning,
  onRunScreen,
  executionTime,
  fetchedAt,
  visibleColumns,
  onToggleColumn,
}: {
  screenName: string;
  totalMatches: number;
  templates: TVTemplate[];
  selectedTemplate: string;
  onTemplateChange: (name: string) => void;
  isRunning: boolean;
  onRunScreen: () => void;
  executionTime: number;
  fetchedAt: string;
  visibleColumns: Set<string>;
  onToggleColumn: (key: string) => void;
}) {
  return (
    <div className="border-b border-border bg-surface/50 backdrop-blur-sm">
      <div className="px-4 py-3 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4 flex-1 min-w-0">
          <div>
            <h1 className="text-xl font-bold text-text-primary">{screenName}</h1>
            <p className="text-sm text-text-muted flex items-center gap-2">
              <span>{totalMatches.toLocaleString()} matches</span>
              {executionTime > 0 && <span>• {executionTime}ms</span>}
              <FreshnessBadge fetchedAt={fetchedAt} />
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Template Selector */}
          <TemplateDropdown
            templates={templates}
            selected={selectedTemplate || templates[0]?.name || ''}
            onChange={onTemplateChange}
          />

          {/* Run Screen Button */}
          <button
            onClick={onRunScreen}
            disabled={isRunning}
            className="btn-primary gap-2"
          >
            {isRunning ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Running...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                <span>Run Screen</span>
              </>
            )}
          </button>

          {/* Column Customizer */}
          <ColumnCustomizer visibleColumns={visibleColumns} onToggle={onToggleColumn} />

          {/* Export Buttons */}
          <ExportButtons />
        </div>
      </div>
    </div>
  );
}

function TemplateDropdown({
  templates,
  selected,
  onChange,
}: {
  templates: TVTemplate[];
  selected: string;
  onChange: (name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});
  const regimeLabel = useMarketStore((s) => s.regime?.regime_label ?? null);

  // Close on outside click — check BOTH the parent wrapper AND the portal dropdown
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      const isOutsideParent = ref.current && !ref.current.contains(target);
      const isOutsideDropdown = dropdownRef.current && !dropdownRef.current.contains(target);
      if (isOutsideParent && isOutsideDropdown) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Position dropdown below button when opened
  useEffect(() => {
    if (!open || !btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setDropdownStyle({
      position: 'fixed',
      left: rect.left,
      top: rect.bottom + 4,
      minWidth: rect.width,
      zIndex: 9999,
    });
  }, [open]);

  const selectedTemplate = templates.find((t) => t.name === selected);
  const direction = selectedTemplate?.direction;
  const isLong = direction === 'long';
  const isShort = direction === 'short';

  return (
    <div className="relative" ref={ref}>
      <button
        ref={btnRef}
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 cursor-pointer pl-3 pr-8 py-2 text-sm bg-surface border border-border rounded-lg
                   text-text-primary
                   hover:border-text-muted/30 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent
                   transition-colors duration-150 min-w-[180px] w-full text-left"
      >
        {direction && (
          <span
            className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${
              isLong ? 'bg-green-500' : isShort ? 'bg-red-500' : 'bg-gray-500'
            }`}
          />
        )}
        <span className="flex-1 truncate">{selectedTemplate?.name || selected || 'Select template'}</span>
        <ChevronDown className={`absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && createPortal(
        <div
          ref={dropdownRef}
          style={dropdownStyle}
          className="bg-surface border border-border rounded-lg shadow-xl max-h-[320px] overflow-y-auto"
        >
          {templates.map((t) => {
            const tLong = t.direction === 'long';
            const tShort = t.direction === 'short';
            return (
              <button
                key={t.name}
                onClick={() => { onChange(t.name); setOpen(false); }}
                className={`flex items-center gap-2 w-full text-left px-3 py-2 text-sm transition-colors hover:bg-border/30 ${
                  t.name === selected ? 'bg-accent/10 text-accent' : 'text-text-primary'
                }`}
                title={t.description}
              >
                {t.direction ? (
                  <span
                    className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${
                      tLong ? 'bg-green-500' : tShort ? 'bg-red-500' : 'bg-gray-500'
                    }`}
                  />
                ) : (
                  <span className="inline-block w-2 h-2 flex-shrink-0" />
                )}
                <span className="flex-1 truncate">{t.name}</span>
                <RegimeBadge recommendation={getScreenerRecommendation(t.name, regimeLabel)} />
              </button>
            );
          })}
        </div>,
        document.body
      )}
    </div>
  );
}

/**
 * Market Overview Panel — shows current regime + sector rotation context.
 * Collapsible panel at the top of the screener page giving users
 * a quick market pulse before they pick a screener config.
 */
function MarketOverviewPanel() {
  const regime = useMarketStore((s) => s.regime);
  const [sectorData, setSectorData] = useState<SectorRotationResponse | null>(null);
  const [expanded, setExpanded] = useState(true);

  // Fetch sector rotation for the leaders/laggards list
  useEffect(() => {
    fetchSectorRotation()
      .then(setSectorData)
      .catch(() => { /* silent — non-critical data */ });
  }, []);

  if (!regime) return null;

  const comp = regime.composite_score;
  const label = regime.regime_label;
  const colorClass = comp >= 65 ? 'text-green-400' : comp >= 50 ? 'text-yellow-400' : comp >= 35 ? 'text-orange-400' : 'text-red-400';
  const barColor = comp >= 65 ? 'bg-green-500' : comp >= 50 ? 'bg-yellow-400' : comp >= 35 ? 'bg-orange-400' : 'bg-red-500';
  const leaders = sectorData?.leaders.slice(0, 3) ?? [];
  const laggards = sectorData?.laggards.slice(0, 3) ?? [];
  const sectorLookup = new Map((sectorData?.sectors ?? []).map((s) => [s.symbol, s]));

  // Determine suggested strategy
  const getStrategyHint = (lbl: string): string => {
    if (lbl === 'Exuberance' || lbl === 'Risk-On') return 'Trend/momentum screeners recommended';
    if (lbl === 'Neutral') return 'Quality/value screeners preferred';
    if (lbl === 'Cautious') return 'Defensive/mean-reversion screeners suggested';
    if (lbl === 'Risk-Off') return 'Oversold bounce & distribution screeners';
    if (lbl === 'Crisis') return 'Avoid new positions — capital preservation';
    return '';
  };

  return (
    <div className="border-b border-border/50">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-4 py-1.5 text-[11px] text-text-muted hover:text-text-primary transition-colors"
      >
        <Gauge className="h-3 w-3" />
        <span>Market Pulse</span>
        <ChevronDown className={`h-3 w-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>
      {expanded && (
        <div className="px-4 pb-3 pt-1 grid grid-cols-[1fr_auto] gap-4 text-xs">
          {/* Left: Regime + Score Bar */}
          <div className="space-y-1.5 min-w-0">
            <div className="flex items-center gap-2">
              <span className={`font-semibold ${colorClass}`}>{label}</span>
              <span className="text-text-muted">{comp.toFixed(0)}/100</span>
              <div className="flex-1 h-1.5 rounded-full bg-border max-w-[120px]">
                <div className={`h-full rounded-full ${barColor}`} style={{ width: `${comp}%` }} />
              </div>
            </div>
            <p className="text-text-muted">{getStrategyHint(label)}</p>
          </div>

          {/* Right: Sector Leaders / Laggards */}
          <div className="flex gap-6">
            {leaders.length > 0 && (
              <div className="space-y-0.5">
                <p className="text-[10px] font-medium text-green-500 uppercase tracking-wider">Leading</p>
                {leaders.map((sym) => {
                  const s = sectorLookup.get(sym);
                  return (
                    <div key={sym} className="flex items-center gap-1.5">
                      <TrendingUp className="h-3 w-3 text-green-500 shrink-0" />
                      <span className="text-text-primary">{s?.name || sym}</span>
                      {s?.change_1d != null && (
                        <span className="text-green-500 font-mono">+{s.change_1d.toFixed(1)}%</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            {laggards.length > 0 && (
              <div className="space-y-0.5">
                <p className="text-[10px] font-medium text-red-400 uppercase tracking-wider">Lagging</p>
                {laggards.map((sym) => {
                  const s = sectorLookup.get(sym);
                  return (
                    <div key={sym} className="flex items-center gap-1.5">
                      <TrendingDown className="h-3 w-3 text-red-400 shrink-0" />
                      <span className="text-text-primary">{s?.name || sym}</span>
                      {s?.change_1d != null && (
                        <span className="text-red-400 font-mono">{s.change_1d.toFixed(1)}%</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Sector Focus Banner — shows recommended sectors from rotation data.
 * Clicking a sector focuses the screener results to that sector.
 */
function SectorFocusBanner({ onSelectSector }: { onSelectSector: (sector: string) => void }) {
  const [sectorData, setSectorData] = useState<SectorRotationResponse | null>(null);

  useEffect(() => {
    fetchSectorRotation()
      .then(setSectorData)
      .catch(() => { /* non-critical */ });
  }, []);

  const sectors = sectorData?.sectors ?? [];
  const rotationPhase = sectorData?.rotation_phase ?? '';

  // Sort by 1d change descending, take top 4
  const topSectors = useMemo(
    () => [...sectors].sort((a, b) => (b.change_1d ?? 0) - (a.change_1d ?? 0)).slice(0, 4),
    [sectors]
  );

  if (topSectors.length === 0) return null;

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b border-border/30 bg-surface/10">
      <span className="text-[10px] font-semibold uppercase text-text-muted tracking-wider shrink-0">
        Focus{rotationPhase ? ` · ${rotationPhase}` : ''}
      </span>
      <div className="flex gap-1.5 overflow-x-auto">
        {topSectors.map((s) => {
          const change = s.change_1d ?? 0;
          const isPos = change >= 0;
          return (
            <button
              key={s.symbol}
              onClick={() => onSelectSector(s.name)}
              className="flex items-center gap-1.5 text-xs bg-surface/30 border border-border/40 hover:border-accent/30 rounded-full px-2.5 py-1 transition-colors shrink-0"
              title={`Click to filter by ${s.name}`}
            >
              <span className="text-text-primary font-medium">{s.name}</span>
              <span className={cn('font-mono', isPos ? 'text-green-500' : 'text-red-400')}>
                {isPos ? '+' : ''}{change.toFixed(1)}%
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function ScreenerPage() {
  return (
    <ErrorBoundary>
      <ScreenerContent />
    </ErrorBoundary>
  );
}