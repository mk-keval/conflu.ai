import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRiskStore } from '@/store/risk';
import { useWS } from '@/ws/WebSocketProvider';
import { riskChannel, signalChannel } from '@/ws/channels';
import { fetchBeta, fetchCorrelation, fetchVaR, fetchRiskSummary } from '@/api/risk';
import { STALE_TIMES } from '@/lib/constants';
import { cn } from '@/lib/cn';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { CorrelationHeatmap } from './CorrelationHeatmap';
import { PositionSizer } from './PositionSizer';
import { BetaCards } from './BetaCards';
import { VarGauge } from './VarGauge';
import { KellyResult } from './KellyResult';

const TABS = [
  { id: 'correlation', label: 'Correlation' },
  { id: 'position-size', label: 'Position Size' },
  { id: 'beta', label: 'Beta' },
  { id: 'var', label: 'VaR / CVaR' },
] as const;

function SymbolInput({ symbols, onChange }: { symbols: string[]; onChange: (s: string[]) => void }) {
  const [value, setValue] = useState(symbols.join(','));

  useEffect(() => {
    const timer = setTimeout(() => {
      const parsed = value.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean);
      if (JSON.stringify(parsed) !== JSON.stringify(symbols)) {
        onChange(parsed);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [value]);

  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-dark-300 whitespace-nowrap">Symbols:</label>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="AAPL,MSFT,GOOGL"
        className="flex-1 rounded border border-dark-500 bg-dark-700 px-3 py-1.5 text-sm text-dark-50 placeholder-dark-400 focus:border-accent focus:outline-none"
      />
    </div>
  );
}

function RiskContent() {
  const {
    selectedSymbols,
    activeView,
    varConfidence,
    varMethod,
    setSymbols,
    setActiveView,
    setVarConfidence,
    setVarMethod,
  } = useRiskStore();

  const { subscribe, unsubscribe } = useWS();

  // WS subscriptions for risk and signals
  useEffect(() => {
    const riskCh = riskChannel('default');
    subscribe(riskCh);
    const signalChs = selectedSymbols.map((sym) => signalChannel(sym));
    signalChs.forEach((ch) => subscribe(ch));

    return () => {
      unsubscribe(riskCh);
      signalChs.forEach((ch) => unsubscribe(ch));
    };
  }, [selectedSymbols, subscribe, unsubscribe]);

  // Correlation query
  const corrQuery = useQuery({
    queryKey: ['risk', 'correlation', selectedSymbols],
    queryFn: () => fetchCorrelation(selectedSymbols),
    staleTime: STALE_TIMES.risk,
    enabled: selectedSymbols.length >= 2 && activeView === 'correlation',
  });

  // Beta query
  const betaQuery = useQuery({
    queryKey: ['risk', 'beta', selectedSymbols],
    queryFn: () => fetchBeta(selectedSymbols),
    staleTime: STALE_TIMES.risk,
    enabled: selectedSymbols.length >= 1 && activeView === 'beta',
  });

  // VaR query
  const varQuery = useQuery({
    queryKey: ['risk', 'var', selectedSymbols, varConfidence, varMethod],
    queryFn: () => fetchVaR(selectedSymbols, varConfidence, varMethod),
    staleTime: STALE_TIMES.risk,
    enabled: selectedSymbols.length >= 1 && activeView === 'var',
  });

  // Risk summary query
  const summaryQuery = useQuery({
    queryKey: ['risk', 'summary', selectedSymbols],
    queryFn: () => fetchRiskSummary(undefined, selectedSymbols),
    staleTime: STALE_TIMES.risk,
    enabled: selectedSymbols.length >= 1,
  });

  return (
    <div className="flex h-full flex-col">
      {/* Header toolbar */}
      <div className="flex items-center gap-3 border-b border-dark-600 px-4 py-3">
        <SymbolInput symbols={selectedSymbols} onChange={setSymbols} />
        <div className="flex-1" />
        {/* Risk summary badge */}
        {summaryQuery.data && (
          <div className="flex items-center gap-3 text-[10px] text-dark-400">
            <span>Exposure: {summaryQuery.data.total_exposure?.toLocaleString() ?? '—'}</span>
            <span>β: {summaryQuery.data.beta_weighted?.toFixed(2) ?? '—'}</span>
            <span>Div: {summaryQuery.data.diversification_score?.toFixed(2) ?? '—'}</span>
          </div>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-dark-600 px-4">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveView(tab.id as typeof activeView)}
            className={cn(
              'border-b-2 px-4 py-2.5 text-xs font-medium transition-colors',
              activeView === tab.id
                ? 'border-accent text-accent-light'
                : 'border-transparent text-dark-300 hover:text-dark-100'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-auto p-4">
        {activeView === 'correlation' && (
          <CorrelationHeatmap
            data={corrQuery.data ?? null}
            isLoading={corrQuery.isLoading}
            error={corrQuery.error?.message ?? null}
          />
        )}

        {activeView === 'position-size' && (
          <div className="max-w-lg">
            <PositionSizer />
            <div className="mt-4">
              <KellyResult
                data={null}
              />
            </div>
          </div>
        )}

        {activeView === 'beta' && (
          <BetaCards
            data={betaQuery.data ?? []}
            isLoading={betaQuery.isLoading}
            error={betaQuery.error?.message ?? null}
          />
        )}

        {activeView === 'var' && (
          <div className="max-w-lg">
            <div className="mb-4 flex items-center gap-3">
              <div>
                <label className="mb-1 block text-[10px] text-dark-400">Confidence</label>
                <select
                  value={varConfidence}
                  onChange={(e) => setVarConfidence(Number(e.target.value))}
                  className="rounded border border-dark-500 bg-dark-700 px-2 py-1 text-xs text-dark-50 focus:border-accent focus:outline-none"
                >
                  <option value={0.90}>90%</option>
                  <option value={0.95}>95%</option>
                  <option value={0.99}>99%</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[10px] text-dark-400">Method</label>
                <select
                  value={varMethod}
                  onChange={(e) => setVarMethod(e.target.value as 'historical' | 'parametric' | 'monte_carlo')}
                  className="rounded border border-dark-500 bg-dark-700 px-2 py-1 text-xs text-dark-50 focus:border-accent focus:outline-none"
                >
                  <option value="historical">Historical</option>
                  <option value="parametric">Parametric</option>
                  <option value="monte_carlo">Monte Carlo</option>
                </select>
              </div>
            </div>
            <VarGauge
              data={varQuery.data ?? null}
              isLoading={varQuery.isLoading}
              error={varQuery.error?.message ?? null}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export function RiskPage() {
  return (
    <ErrorBoundary>
      <RiskContent />
    </ErrorBoundary>
  );
}
