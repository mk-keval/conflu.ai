import { useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { postPositionSize } from '@/api/risk';
import { cn } from '@/lib/cn';
import { formatPrice } from '@/lib/format';
import type { PositionSizeResult } from '@/types/risk';

const METHOD_OPTIONS = [
  { value: 'fixed', label: 'Fixed' },
  { value: 'atr', label: 'ATR' },
  { value: 'kelly', label: 'Kelly' },
] as const;

export function PositionSizer() {
  const [symbols, setSymbols] = useState('AAPL,MSFT,GOOGL');
  const [cash, setCash] = useState(100_000);
  const [method, setMethod] = useState<'atr' | 'kelly' | 'fixed'>('fixed');
  const [riskPerTrade, setRiskPerTrade] = useState(1.0);

  const mutation = useMutation({
    mutationFn: () =>
      postPositionSize({
        symbols: symbols.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean),
        method,
        cash,
        params: { risk_per_trade: riskPerTrade },
      }),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="space-y-3 rounded border border-dark-600 bg-dark-800 p-3">
        <h3 className="text-xs font-semibold text-dark-100">Position Sizing</h3>

        <div>
          <label className="mb-1 block text-xs text-dark-300">Symbols</label>
          <input
            type="text"
            value={symbols}
            onChange={(e) => setSymbols(e.target.value)}
            className="w-full rounded border border-dark-500 bg-dark-700 px-3 py-1.5 text-sm text-dark-50 focus:border-accent focus:outline-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs text-dark-300">Total Cash</label>
            <input
              type="number"
              value={cash}
              onChange={(e) => setCash(Number(e.target.value))}
              min={1000}
              step={1000}
              className="w-full rounded border border-dark-500 bg-dark-700 px-3 py-1.5 text-sm text-dark-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-dark-300">Risk/Trade (%)</label>
            <input
              type="number"
              value={riskPerTrade}
              onChange={(e) => setRiskPerTrade(Number(e.target.value))}
              min={0.1}
              max={10}
              step={0.1}
              className="w-full rounded border border-dark-500 bg-dark-700 px-3 py-1.5 text-sm text-dark-50 focus:border-accent focus:outline-none"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs text-dark-300">Method</label>
          <div className="flex gap-2">
            {METHOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setMethod(opt.value)}
                className={cn(
                  'flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors',
                  method === opt.value
                    ? 'bg-accent text-white'
                    : 'border border-dark-500 text-dark-200 hover:bg-dark-600'
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <button
          type="submit"
          disabled={mutation.isPending}
          className={cn(
            'w-full rounded py-2 text-xs font-semibold transition-colors',
            mutation.isPending
              ? 'cursor-not-allowed bg-dark-500 text-dark-300'
              : 'bg-accent text-white hover:bg-accent-dark'
          )}
        >
          {mutation.isPending ? 'Calculating...' : 'Calculate Position Size'}
        </button>

        {mutation.isError && (
          <p className="text-xs text-loss">Error: {(mutation.error as Error)?.message}</p>
        )}
      </form>

      {/* Results */}
      {mutation.data && <PositionSizerResult data={mutation.data} />}
    </div>
  );
}

function PositionSizerResult({ data }: { data: PositionSizeResult }) {
  const entries = Object.entries(data.sizes);

  if (!entries.length) {
    return (
      <div className="rounded border border-dark-600 bg-dark-800 p-3 text-center text-xs text-dark-400">
        No position sizes calculated
      </div>
    );
  }

  return (
    <div className="rounded border border-dark-600 bg-dark-800 p-3">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-xs font-semibold text-dark-200">Position Sizes</h4>
        <div className="text-right text-[10px] text-dark-400">
          Method: {data.method}
          <br />
          Cash: {formatPrice(data.cash)}
        </div>
      </div>
      <div className="space-y-1">
        {entries.map(([symbol, size]) => (
          <div
            key={symbol}
            className="flex items-center justify-between rounded bg-dark-900 px-3 py-2"
          >
            <span className="text-xs font-medium text-dark-100">{symbol}</span>
            <span className="font-mono text-xs text-dark-50">{formatPrice(size)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
