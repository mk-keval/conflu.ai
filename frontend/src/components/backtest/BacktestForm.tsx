import { useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { runBacktest } from '@/api/backtest';
import { useBacktestStore } from '@/store/backtest';
import { cn } from '@/lib/cn';
import type { BacktestRequest } from '@/types/backtest';

const POSITION_SIZING_OPTIONS = [
  { value: 'fixed', label: 'Fixed' },
  { value: 'atr', label: 'ATR-based' },
  { value: 'kelly', label: 'Kelly' },
] as const;

interface FormState {
  symbols: string;
  start: string;
  end: string;
  initial_cash: number;
  fees_bps: number;
  slippage_bps: number;
  position_sizing: 'fixed' | 'atr' | 'kelly';
}

const defaults: FormState = {
  symbols: 'AAPL,MSFT',
  start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000)
    .toISOString()
    .split('T')[0],
  end: new Date().toISOString().split('T')[0],
  initial_cash: 100_000,
  fees_bps: 10,
  slippage_bps: 5,
  position_sizing: 'fixed',
};

export function BacktestForm() {
  const [form, setForm] = useState<FormState>(defaults);
  const navigate = useNavigate();
  const addRunId = useBacktestStore((s) => s.addRunId);

  const mutation = useMutation({
    mutationFn: (body: BacktestRequest) => runBacktest(body),
    onSuccess: (data) => {
      addRunId(data.run_id);
      navigate(`/backtest/result/${data.run_id}`);
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const symbols = form.symbols
      .split(',')
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    if (symbols.length === 0) return;

    const body: BacktestRequest = {
      symbols,
      start: form.start,
      end: form.end,
      initial_cash: form.initial_cash,
      fees_bps: form.fees_bps,
      slippage_bps: form.slippage_bps,
      position_sizing: form.position_sizing,
      sizing_params: {},
      signal_params: {},
    };

    mutation.mutate(body);
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border-dark-600 bg-dark-800 space-y-4 rounded border p-4"
    >
      <h3 className="text-dark-100 text-sm font-semibold">Run Backtest</h3>

      {/* Symbols */}
      <div>
        <label className="text-dark-300 mb-1 block text-xs">
          Symbols (comma-separated)
        </label>
        <input
          type="text"
          value={form.symbols}
          onChange={(e) => update('symbols', e.target.value)}
          placeholder="AAPL,MSFT,GOOGL"
          className="border-dark-500 bg-dark-700 text-dark-50 placeholder-dark-400 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
        />
      </div>

      {/* Date Range */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-dark-300 mb-1 block text-xs">Start</label>
          <input
            type="date"
            value={form.start}
            onChange={(e) => update('start', e.target.value)}
            className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="text-dark-300 mb-1 block text-xs">End</label>
          <input
            type="date"
            value={form.end}
            onChange={(e) => update('end', e.target.value)}
            className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
          />
        </div>
      </div>

      {/* Cash */}
      <div>
        <label className="text-dark-300 mb-1 block text-xs">Initial Cash</label>
        <input
          type="number"
          value={form.initial_cash}
          onChange={(e) => update('initial_cash', Number(e.target.value))}
          min={1000}
          step={1000}
          className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
        />
      </div>

      {/* Fees & Slippage */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-dark-300 mb-1 block text-xs">Fees (bps)</label>
          <input
            type="number"
            value={form.fees_bps}
            onChange={(e) => update('fees_bps', Number(e.target.value))}
            min={0}
            className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="text-dark-300 mb-1 block text-xs">
            Slippage (bps)
          </label>
          <input
            type="number"
            value={form.slippage_bps}
            onChange={(e) => update('slippage_bps', Number(e.target.value))}
            min={0}
            className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
          />
        </div>
      </div>

      {/* Position Sizing */}
      <div>
        <label className="text-dark-300 mb-1 block text-xs">
          Position Sizing
        </label>
        <div className="flex gap-2">
          {POSITION_SIZING_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => update('position_sizing', opt.value)}
              className={cn(
                'flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors',
                form.position_sizing === opt.value
                  ? 'bg-accent text-white'
                  : 'bg-dark-800 border-dark-500 text-dark-200 hover:bg-dark-600 border'
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={mutation.isPending}
        className={cn(
          'w-full rounded py-2 text-sm font-semibold transition-colors',
          mutation.isPending
            ? 'bg-dark-500 text-dark-300 cursor-not-allowed'
            : 'bg-accent text-white hover:bg-accent-dark'
        )}
      >
        {mutation.isPending ? 'Running...' : 'Run Backtest'}
      </button>

      {mutation.isError && (
        <p className="text-xs text-loss">
          Error: {(mutation.error as Error)?.message}
        </p>
      )}
    </form>
  );
}
