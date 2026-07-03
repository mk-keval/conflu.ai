import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchScreenTV,
  fetchTVTemplates,
} from '@/api/screener';
import type {
  TVScoredTicker,
  TVTemplate,
} from '@/types/screener';
import { useScreenStore } from '@/store/screen';
import { useWS } from '@/ws/WebSocketProvider';
import { screenerChannel } from '@/ws/channels';
import { STALE_TIMES } from '@/lib/constants';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { SkeletonTable } from '@/components/layout/LoadingSkeleton';
import { ScreenerTable } from './ScreenerTable';
import { DetailPanel } from './DetailPanel';
import { ExportButtons } from './ExportButtons';
import type { WSMessage } from '@/types/ws';
import { ChevronDown, Play, Loader2, RefreshCw, Columns } from 'lucide-react';
import { cn } from '@/lib/cn';
import { ALL_COLUMNS_META, DEFAULT_VISIBLE_COLUMNS } from './ScreenerTable';

function ScreenerContent() {
  const selectedConfig = useScreenStore((s) => s.selectedConfig);
  const timeframes = useScreenStore((s) => s.timeframes);
  const setConfig = useScreenStore((s) => s.setConfig);
  const { subscribe, unsubscribe, onMessage } = useWS();

  // State
  const [templates, setTemplates] = useState<TVTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<TVScoredTicker[]>([]);
  const [totalMatches, setTotalMatches] = useState(0);
  const [screenName, setScreenName] = useState('');
  const [executionTime, setExecutionTime] = useState(0);
  const [fetchedAt, setFetchedAt] = useState<string>('');
  const [selectedTicker, setSelectedTicker] = useState<TVScoredTicker | null>(null);
  const [sortState, setSortState] = useState<{ key: string | null; dir: 'asc' | 'desc' | null }>({ key: 'score', dir: 'desc' });
  const [currentPage, setCurrentPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

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
    staleTime: STALE_TIMES.screen,
    refetchInterval: 30_000,
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
    setSelectedTicker(ticker);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedTicker(null);
  }, []);

  const handleDeepAnalysis = useCallback((symbol: string) => {
    // Navigate to charts page with the symbol or trigger analysis
    console.log('Deep analysis for:', symbol);
    // Could navigate to charts page or open analysis modal
  }, []);

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

      <div className="flex-1 overflow-hidden relative">
        <ScreenerTable
          results={results}
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

        {/* Detail Panel */}
        <DetailPanel
          ticker={selectedTicker}
          onClose={handleCloseDetail}
          onAnalyze={handleDeepAnalysis}
        />
      </div>
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

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const toggleable = ALL_COLUMNS_META.filter((m) => !m.alwaysOn);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((p) => !p)}
        className="btn-ghost p-2 text-text-muted hover:text-text-primary"
        aria-label="Customize columns"
        title="Customize columns"
      >
        <Columns className="w-4 h-4" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 w-44 bg-dark-600 border border-border/50 rounded-lg shadow-xl py-1">
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
        </div>
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
          <div className="relative">
            <select
              value={selectedTemplate || templates[0]?.name || ''}
              onChange={(e) => onTemplateChange(e.target.value)}
              className="appearance-none cursor-pointer pl-3 pr-8 py-2 text-sm bg-surface border border-border rounded-lg
                         text-text-primary placeholder-text-muted
                         hover:border-text-muted/30 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent
                         transition-colors duration-150 min-w-[180px]"
            >
              {templates.length === 0 && (
                <option value="" disabled>Loading...</option>
              )}
              {templates.map((template) => (
                <option key={template.name} value={template.name} title={template.description}>
                  {template.name}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none" />
          </div>

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

export function ScreenerPage() {
  return (
    <ErrorBoundary>
      <ScreenerContent />
    </ErrorBoundary>
  );
}