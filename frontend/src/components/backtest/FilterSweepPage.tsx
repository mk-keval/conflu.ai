import { useState, useCallback } from 'react';
import { cn } from '@/lib/cn';
import { FilterSweepForm } from './FilterSweepForm';
import { FilterSweepResults } from './FilterSweepResults';
import { SimpleBacktestForm } from './SimpleBacktestForm';
import { SimpleBacktestResults } from './SimpleBacktestResults';
import { getFilterSweepResults } from '@/api/backtest';
import type { FilterSweepSummary } from '@/types/backtest';
import type { SimpleBacktestResponse } from '@/api/backtest';
import { Zap, TrendingUp } from 'lucide-react';

export function FilterSweepPage() {
  const [mode, setMode] = useState<'sweep' | 'simple'>('sweep');
  const [view, setView] = useState<'form' | 'results'>('form');
  const [summary, setSummary] = useState<FilterSweepSummary | null>(null);
  const [simpleResult, setSimpleResult] = useState<SimpleBacktestResponse | null>(null);

  const handleSweepStarted = useCallback((data: { sweep_id: string; status: string }) => {
    // Poll for results
    const pollForResults = async () => {
      try {
        const result = await getFilterSweepResults(data.sweep_id);
        setSummary(result);
        setView('results');
      } catch (error) {
        // Sweep might still be running, keep polling
        console.log('Sweep not ready yet, will retry...');
      }
    };

    const interval = setInterval(pollForResults, 2000);
    pollForResults(); // Initial check

    // Stop polling after 5 minutes or when results arrive
    const timeout = setTimeout(() => {
      clearInterval(interval);
    }, 5 * 60 * 1000);

    // Cleanup function
    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, []);

  const handleSimpleBacktestComplete = useCallback((data: SimpleBacktestResponse) => {
    setSimpleResult(data);
    setView('results');
  }, []);

  const handleRunNewSweep = useCallback(() => {
    setSummary(null);
    setView('form');
  }, []);

  const handleRunNewSimpleBacktest = useCallback(() => {
    setSimpleResult(null);
    setView('form');
  }, []);

  return (
    <div className="min-h-[calc(100vh-4.5rem)]">
      <div className="border-b border-border/20 bg-surface/50 px-4 py-3">
        <div className="mx-auto max-w-7xl flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div className="flex items-center gap-2">
            <h1 className="font-display text-xl font-semibold tracking-tight text-text-primary">
              Filter Sweep Backtest
            </h1>
            <span className="rounded-full border border-accent/30 bg-accent/10 px-2.5 py-0.5 text-xs font-medium text-accent">
              Beta
            </span>
          </div>
          <p className="text-sm text-text-muted">
            Run parameter sweeps or simple backtests on screen templates
          </p>
        </div>
      </div>

      {/* Mode Toggle */}
      <div className="mx-auto max-w-7xl px-4 py-3">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-1 py-1">
          <button
            onClick={() => { setMode('sweep'); setView('form'); }}
            className={cn(
              'flex-1 rounded px-3 py-2 text-sm font-medium transition-colors',
              mode === 'sweep'
                ? 'bg-accent text-white shadow-sm'
                : 'text-text-secondary hover:bg-surface-hover'
            )}
          >
            <Zap className="h-4 w-4 mr-2 inline" />
            Parameter Sweep
          </button>
          <button
            onClick={() => { setMode('simple'); setView('form'); }}
            className={cn(
              'flex-1 rounded px-3 py-2 text-sm font-medium transition-colors',
              mode === 'simple'
                ? 'bg-accent text-white shadow-sm'
                : 'text-text-secondary hover:bg-surface-hover'
            )}
          >
            <TrendingUp className="h-4 w-4 mr-2 inline" />
            Simple Backtest
          </button>
        </div>
      </div>

      <div className="mx-auto max-w-7xl flex-1 p-4">
        {mode === 'sweep' ? (
          view === 'form' ? (
            <FilterSweepForm onSweepStarted={handleSweepStarted} />
          ) : (
            <FilterSweepResults
              summary={summary}
              onRunNewSweep={handleRunNewSweep}
            />
          )
        ) : (
          view === 'form' ? (
            <SimpleBacktestForm onBacktestComplete={handleSimpleBacktestComplete} />
          ) : (
            <SimpleBacktestResults
              data={simpleResult}
              onRunNewBacktest={handleRunNewSimpleBacktest}
            />
          )
        )}
      </div>
    </div>
  );
}

export { FilterSweepForm } from './FilterSweepForm';
export { FilterSweepResults } from './FilterSweepResults';