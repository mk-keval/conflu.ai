import { useEffect, useState, useCallback } from 'react';
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
import { ChevronDown, Play, Loader2, RefreshCw } from 'lucide-react';

function ScreenerContent() {
  const selectedConfig = useScreenStore((s) => s.selectedConfig);
  const timeframes = useScreenStore((s) => s.timeframes);
  const setConfig = useScreenStore((s) => s.setConfig);
  const { subscribe, unsubscribe, onMessage } = useWS();

  // State
  const [templates, setTemplates] = useState<TVTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('trend-follower');
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<TVScoredTicker[]>([]);
  const [totalMatches, setTotalMatches] = useState(0);
  const [screenName, setScreenName] = useState('Trend Follower');
  const [executionTime, setExecutionTime] = useState(0);
  const [selectedTicker, setSelectedTicker] = useState<TVScoredTicker | null>(null);
  const [sortState, setSortState] = useState<{ key: string | null; dir: 'asc' | 'desc' | null }>({ key: 'score', dir: 'desc' });
  const [currentPage, setCurrentPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  // Fetch templates on mount
  useEffect(() => {
    fetchTVTemplates()
      .then(setTemplates)
      .catch(console.error);
  }, []);

  // Update selected template when config changes
  useEffect(() => {
    const template = templates.find((t) => t.name === selectedConfig);
    if (template) {
      setSelectedTemplate(template.name);
      setScreenName(template.name.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));
    }
  }, [selectedConfig, templates]);

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
      setScreenName(data.screen_name.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));
      setCurrentPage(0); // Reset to first page on new results
    }
  }, [data]);

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

function ScreenerHeader({
  screenName,
  totalMatches,
  templates,
  selectedTemplate,
  onTemplateChange,
  isRunning,
  onRunScreen,
  executionTime,
}: {
  screenName: string;
  totalMatches: number;
  templates: TVTemplate[];
  selectedTemplate: string;
  onTemplateChange: (name: string) => void;
  isRunning: boolean;
  onRunScreen: () => void;
  executionTime: number;
}) {
  return (
    <div className="border-b border-border bg-surface/50 backdrop-blur-sm">
      <div className="px-4 py-3 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4 flex-1 min-w-0">
          <div>
            <h1 className="text-xl font-bold text-text-primary">{screenName}</h1>
            <p className="text-sm text-text-muted">
              {totalMatches.toLocaleString()} matches {executionTime > 0 && `• ${executionTime}ms`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Template Selector */}
          <div className="relative">
            <select
              value={selectedTemplate}
              onChange={(e) => onTemplateChange(e.target.value)}
              className="select pr-10 min-w-[200px] bg-surface border-border"
            >
              {templates.map((template) => (
                <option key={template.name} value={template.name}>
                  {template.name.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none" />
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