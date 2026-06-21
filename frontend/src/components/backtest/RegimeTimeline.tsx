import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { detectRegimes, fetchBacktest } from '@/api/backtest';
import { cn } from '@/lib/cn';
import type { RegimeRequest, RegimeResult } from '@/types/backtest';

interface RegimeTimelineProps {
  runId: string;
  symbol: string;
}

const REGIME_COLORS = ['#ff5252', '#ffd740', '#00e676', '#40c4ff', '#e040fb'];
const REGIME_COLOR_CLASSES = [
  'bg-loss/20 border-loss/40',
  'bg-warning/20 border-warning/40',
  'bg-gain/20 border-gain/40',
  'bg-info/20 border-info/40',
  'bg-accent/20 border-accent/40',
];

function RegimeStats({ result }: { result: RegimeResult }) {
  if (!result.regime_names || result.regime_names.length === 0) return null;

  const counts: Record<number, number> = {};
  result.regime_labels.forEach((l) => {
    counts[l] = (counts[l] || 0) + 1;
  });

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {result.regime_names.map((name, i) => {
        const count = counts[i] || 0;
        const pct = ((count / result.regime_labels.length) * 100).toFixed(1);
        return (
          <div key={i} className={cn('rounded border px-3 py-2', REGIME_COLOR_CLASSES[i % REGIME_COLOR_CLASSES.length])}>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: REGIME_COLORS[i % REGIME_COLORS.length] }} />
              <span className="text-xs font-medium text-dark-200">{name}</span>
            </div>
            <p className="text-[11px] text-dark-400 mt-1">{count} bars ({pct}%)</p>
          </div>
        );
      })}
    </div>
  );
}

function RegimeBar({ result }: { result: RegimeResult }) {
  const maxBars = 200;
  const step = Math.max(1, Math.floor(result.regime_labels.length / maxBars));
  const sampled = result.regime_labels.filter((_, i) => i % step === 0).slice(0, maxBars);

  return (
    <div className="flex h-6 rounded overflow-hidden">
      {sampled.map((label, i) => (
        <div
          key={i}
          className="flex-1"
          style={{ backgroundColor: REGIME_COLORS[label % REGIME_COLORS.length] }}
          title={`${result.regime_names[label] || `Regime ${label}`}`}
        />
      ))}
    </div>
  );
}

export function RegimeTimeline({ runId, symbol }: RegimeTimelineProps) {
  const [showRegimes, setShowRegimes] = useState(false);
  const [regimeMethod, setRegimeMethod] = useState<'hmm' | 'volatility_quantile'>('hmm');
  const [nStates, setNStates] = useState(3);

  const { data: backtest } = useQuery({
    queryKey: ['backtest', runId],
    queryFn: () => fetchBacktest(runId),
    staleTime: Infinity,
  });

  const mutation = useMutation({
    mutationFn: (body: RegimeRequest) => detectRegimes(body),
    onSuccess: () => setShowRegimes(true),
  });

  function handleDetect() {
    if (!backtest) return;
    mutation.mutate({
      symbols: [symbol],
      start: backtest.timeframe, // placeholder - use actual dates
      end: new Date().toISOString(),
      method: regimeMethod,
      n_states: nStates,
      window_days: 252,
    });
  }

  return (
    <div className="space-y-3 rounded border border-dark-600 bg-dark-800 p-4">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-dark-200">Regime Detection</h4>
        {showRegimes && (
          <button onClick={() => setShowRegimes(false)}
            className="text-[10px] text-dark-400 hover:text-dark-200 transition-colors">
            Hide
          </button>
        )}
      </div>

      <div className="flex items-center gap-3">
        <select value={regimeMethod} onChange={(e) => setRegimeMethod(e.target.value as 'hmm' | 'volatility_quantile')}
          className="rounded border border-dark-500 bg-dark-700 px-2 py-1 text-xs text-dark-50 focus:border-accent focus:outline-none">
          <option value="hmm">HMM (3-4 states)</option>
          <option value="volatility_quantile">Volatility Quantile</option>
        </select>

        <label className="flex items-center gap-1.5">
          <span className="text-[10px] text-dark-400">States:</span>
          <input type="number" value={nStates} onChange={(e) => setNStates(Number(e.target.value))}
            min={2} max={4}
            className="w-12 rounded border border-dark-500 bg-dark-700 px-2 py-1 text-xs text-dark-50 text-center focus:border-accent focus:outline-none" />
        </label>

        <button onClick={handleDetect} disabled={mutation.isPending}
          className={cn('ml-auto rounded px-3 py-1.5 text-xs font-medium transition-colors',
            mutation.isPending ? 'cursor-not-allowed bg-dark-500 text-dark-300' : 'bg-accent text-white hover:bg-accent-dark'
          )}>
          {mutation.isPending ? 'Detecting...' : 'Detect Regimes'}
        </button>
      </div>

      {mutation.isError && (
        <p className="text-xs text-loss">Error: {(mutation.error as Error)?.message}</p>
      )}

      {mutation.data && (
        <div className="space-y-3">
          <RegimeBar result={mutation.data} />
          <RegimeStats result={mutation.data} />
        </div>
      )}
    </div>
  );
}
