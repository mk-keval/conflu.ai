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
        symbols: symbols
          .split(',')
          .map((s) => s.trim().toUpperCase())
          .filter(Boolean),
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
      <form
        onSubmit={handleSubmit}
        className="border-dark-600 bg-dark-800 space-y-3 rounded border p-3"
      >
        <h3 className="text-dark-100 text-xs font-semibold">Position Sizing</h3>

        <div>
          <label className="text-dark-300 mb-1 block text-xs">Symbols</label>
          <input
            type="text"
            value={symbols}
            onChange={(e) => setSymbols(e.target.value)}
            className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-dark-300 mb-1 block text-xs">
              Total Cash
            </label>
            <input
              type="number"
              value={cash}
              onChange={(e) => setCash(Number(e.target.value))}
              min={1000}
              step={1000}
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="text-dark-300 mb-1 block text-xs">
              Risk/Trade (%)
            </label>
            <input
              type="number"
              value={riskPerTrade}
              onChange={(e) => setRiskPerTrade(Number(e.target.value))}
              min={0.1}
              max={10}
              step={0.1}
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            />
          </div>
        </div>

        <div>
          <label className="text-dark-300 mb-1 block text-xs">Method</label>
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
                    : 'border-dark-500 text-dark-200 hover:bg-dark-600 border'
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
              ? 'bg-dark-500 text-dark-300 cursor-not-allowed'
              : 'bg-accent text-white hover:bg-accent-dark'
          )}
        >
          {mutation.isPending ? 'Calculating...' : 'Calculate Position Size'}
        </button>

        {mutation.isError && (
          <p className="text-xs text-loss">
            Error: {(mutation.error as Error)?.message}
          </p>
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
      <div className="border-dark-600 bg-dark-800 text-dark-400 rounded border p-3 text-center text-xs">
        No position sizes calculated
      </div>
    );
  }

  return (
    <div className="border-dark-600 bg-dark-800 rounded border p-3">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-dark-200 text-xs font-semibold">Position Sizes</h4>
        <div className="text-dark-400 text-right text-[10px]">
          Method: {data.method}
          <br />
          Cash: {formatPrice(data.cash)}
        </div>
      </div>
      <div className="space-y-1">
        {entries.map(([symbol, size]) => (
          <div
            key={symbol}
            className="bg-dark-900 flex items-center justify-between rounded px-3 py-2"
          >
            <span className="text-dark-100 text-xs font-medium">{symbol}</span>
            <span className="text-dark-50 font-mono text-xs">
              {formatPrice(size)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
