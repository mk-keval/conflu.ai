import { useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { optimizeBacktest } from '@/api/backtest';
import { cn } from '@/lib/cn';
import type { OptimizeRequest } from '@/types/backtest';

const METHODS = ['grid', 'random', 'bayesian'] as const;
const OBJECTIVE_OPTIONS = [
  'sharpe',
  'sortino',
  'calmar',
  'max_dd',
  'win_rate',
  'profit_factor',
  'sqn',
  'cagr',
];

interface ParamRow {
  key: string;
  type: 'int' | 'float' | 'categorical';
  low: string;
  high: string;
  step: string;
  choices: string;
}

interface FormState {
  symbols: string;
  start: string;
  end: string;
  initial_cash: number;
  fees_bps: number;
  slippage_bps: number;
  position_sizing: 'fixed' | 'atr' | 'kelly';
  method: 'grid' | 'random' | 'bayesian';
  objectives: string[];
  max_trials: number;
  timeout_s: number;
  n_jobs: number;
  early_stopping: boolean;
  params: ParamRow[];
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
  method: 'bayesian',
  objectives: ['sharpe'],
  max_trials: 100,
  timeout_s: 300,
  n_jobs: 1,
  early_stopping: true,
  params: [
    { key: '', type: 'float', low: '0', high: '1', step: '1', choices: '' },
  ],
};

export function OptimizationForm() {
  const [form, setForm] = useState<FormState>(defaults);
  const navigate = useNavigate();

  const mutation = useMutation({
    mutationFn: (body: OptimizeRequest) => optimizeBacktest(body),
    onSuccess: (data) => {
      navigate(`/backtest/result/${data.study_id}`);
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const symbols = form.symbols
      .split(',')
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    if (symbols.length === 0) return;

    const param_distributions: Record<string, Record<string, unknown>> = {};
    form.params.forEach((p) => {
      if (!p.key) return;
      param_distributions[p.key] = {
        type: p.type,
        low: p.low ? Number(p.low) : undefined,
        high: p.high ? Number(p.high) : undefined,
        step: p.step ? Number(p.step) : undefined,
        choices: p.choices ? p.choices.split(',').map((c) => c.trim()) : [],
      };
    });

    const body: OptimizeRequest = {
      symbols,
      start: form.start,
      end: form.end,
      initial_cash: form.initial_cash,
      fees_bps: form.fees_bps,
      slippage_bps: form.slippage_bps,
      position_sizing: form.position_sizing,
      sizing_params: {},
      signal_params: {},
      method: form.method,
      grid_params: {},
      param_distributions,
      objectives: form.objectives,
      max_trials: form.max_trials,
      timeout_s: form.timeout_s,
      n_jobs: form.n_jobs,
      early_stopping: form.early_stopping,
    };

    mutation.mutate(body);
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toggleObjective(obj: string) {
    setForm((prev) => ({
      ...prev,
      objectives: prev.objectives.includes(obj)
        ? prev.objectives.filter((o) => o !== obj)
        : [...prev.objectives, obj],
    }));
  }

  function updateParam(index: number, field: keyof ParamRow, value: string) {
    setForm((prev) => {
      const params = [...prev.params];
      params[index] = { ...params[index], [field]: value };
      return { ...prev, params };
    });
  }

  function addParamRow() {
    setForm((prev) => ({
      ...prev,
      params: [
        ...prev.params,
        { key: '', type: 'float', low: '0', high: '1', step: '1', choices: '' },
      ],
    }));
  }

  function removeParamRow(index: number) {
    setForm((prev) => ({
      ...prev,
      params: prev.params.filter((_, i) => i !== index),
    }));
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border-dark-600 bg-dark-800 space-y-4 rounded border p-4"
    >
      <h3 className="text-dark-100 text-sm font-semibold">
        Parameter Optimization
      </h3>

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

      {/* Method */}
      <div>
        <label className="text-dark-300 mb-1 block text-xs">Method</label>
        <div className="flex gap-2">
          {METHODS.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => update('method', m)}
              className={cn(
                'flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors',
                form.method === m
                  ? 'bg-accent text-white'
                  : 'bg-dark-800 border-dark-500 text-dark-200 hover:bg-dark-600 border'
              )}
            >
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Objectives */}
      <div>
        <label className="text-dark-300 mb-1 block text-xs">Objectives</label>
        <div className="flex flex-wrap gap-1.5">
          {OBJECTIVE_OPTIONS.map((obj) => (
            <button
              key={obj}
              type="button"
              onClick={() => toggleObjective(obj)}
              className={cn(
                'rounded px-2 py-1 text-[10px] font-medium transition-colors',
                form.objectives.includes(obj)
                  ? 'bg-accent text-white'
                  : 'bg-dark-800 border-dark-500 text-dark-300 hover:bg-dark-600 border'
              )}
            >
              {obj}
            </button>
          ))}
        </div>
      </div>

      {/* Numeric Params */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-dark-300 mb-1 block text-xs">Max Trials</label>
          <input
            type="number"
            value={form.max_trials}
            onChange={(e) => update('max_trials', Number(e.target.value))}
            min={1}
            max={100000}
            className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="text-dark-300 mb-1 block text-xs">
            Timeout (s)
          </label>
          <input
            type="number"
            value={form.timeout_s}
            onChange={(e) => update('timeout_s', Number(e.target.value))}
            min={10}
            className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-dark-300 mb-1 block text-xs">
            Parallel Jobs
          </label>
          <input
            type="number"
            value={form.n_jobs}
            onChange={(e) => update('n_jobs', Number(e.target.value))}
            min={1}
            max={32}
            className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
          />
        </div>
        <div className="flex items-end pb-2">
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={form.early_stopping}
              onChange={(e) => update('early_stopping', e.target.checked)}
              className="border-dark-500 bg-dark-700 rounded text-accent focus:ring-accent"
            />
            <span className="text-dark-300 text-xs">Early Stopping</span>
          </label>
        </div>
      </div>

      {/* Parameter Space Builder */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <label className="text-dark-300 text-xs">Parameter Space</label>
          <button
            type="button"
            onClick={addParamRow}
            className="bg-dark-600 text-dark-200 hover:bg-dark-500 rounded px-2 py-0.5 text-[10px] transition-colors"
          >
            + Add Param
          </button>
        </div>
        <div className="space-y-2">
          {form.params.map((p, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <input
                type="text"
                value={p.key}
                onChange={(e) => updateParam(i, 'key', e.target.value)}
                placeholder="param_name"
                className="border-dark-500 bg-dark-700 text-dark-50 placeholder-dark-400 w-24 rounded border px-2 py-1 text-[11px] focus:border-accent focus:outline-none"
              />
              <select
                value={p.type}
                onChange={(e) => updateParam(i, 'type', e.target.value)}
                className="border-dark-500 bg-dark-700 text-dark-50 rounded border px-1 py-1 text-[11px] focus:border-accent focus:outline-none"
              >
                <option value="int">int</option>
                <option value="float">float</option>
                <option value="categorical">cat</option>
              </select>
              {p.type === 'categorical' ? (
                <input
                  type="text"
                  value={p.choices}
                  onChange={(e) => updateParam(i, 'choices', e.target.value)}
                  placeholder="val1,val2"
                  className="border-dark-500 bg-dark-700 text-dark-50 placeholder-dark-400 flex-1 rounded border px-2 py-1 text-[11px] focus:border-accent focus:outline-none"
                />
              ) : (
                <>
                  <input
                    type="text"
                    value={p.low}
                    onChange={(e) => updateParam(i, 'low', e.target.value)}
                    placeholder="low"
                    className="border-dark-500 bg-dark-700 text-dark-50 placeholder-dark-400 w-14 rounded border px-2 py-1 text-[11px] focus:border-accent focus:outline-none"
                  />
                  <input
                    type="text"
                    value={p.high}
                    onChange={(e) => updateParam(i, 'high', e.target.value)}
                    placeholder="high"
                    className="border-dark-500 bg-dark-700 text-dark-50 placeholder-dark-400 w-14 rounded border px-2 py-1 text-[11px] focus:border-accent focus:outline-none"
                  />
                  {p.type === 'int' && (
                    <input
                      type="text"
                      value={p.step}
                      onChange={(e) => updateParam(i, 'step', e.target.value)}
                      placeholder="step"
                      className="border-dark-500 bg-dark-700 text-dark-50 placeholder-dark-400 w-12 rounded border px-2 py-1 text-[11px] focus:border-accent focus:outline-none"
                    />
                  )}
                </>
              )}
              <button
                type="button"
                onClick={() => removeParamRow(i)}
                className="text-dark-400 text-xs transition-colors hover:text-loss"
              >
                ✕
              </button>
            </div>
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
        {mutation.isPending ? 'Optimizing...' : 'Start Optimization'}
      </button>

      {mutation.isError && (
        <p className="text-xs text-loss">
          Error: {(mutation.error as Error)?.message}
        </p>
      )}
    </form>
  );
}
