import { useState, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { cn } from '@/lib/cn';
import {
  Loader2,
  ChevronDown,
  ChevronUp,
  Zap,
  Calendar,
  DollarSign,
  AlertTriangle,
} from 'lucide-react';
import {
  runSimpleBacktest,
  fetchBacktestTemplates,
  type SimpleBacktestRequest,
  type SimpleBacktestResponse,
} from '@/api/backtest';
import type { TVTemplate } from '@/types/screener';

const TIMEFRAME_OPTIONS = [
  { value: '1D', label: '1 Day' },
  { value: '4h', label: '4 Hours' },
  { value: '1h', label: '1 Hour' },
  { value: '1W', label: '1 Week' },
] as const;

const POSITION_SIZING_OPTIONS = [
  { value: 'fixed', label: 'Fixed' },
  { value: 'atr', label: 'ATR-based' },
  { value: 'kelly', label: 'Kelly' },
] as const;

interface SimpleBacktestFormState {
  template: string;
  symbols: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  initial_cash: number;
  fees_bps: number;
  slippage_bps: number;
  position_sizing: 'fixed' | 'atr' | 'kelly';
}

const defaults: SimpleBacktestFormState = {
  template: '',
  symbols: 'AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AVGO,ORCL,CRM',
  timeframe: '1D',
  start_date: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
  end_date: new Date().toISOString().split('T')[0],
  initial_cash: 100_000,
  fees_bps: 10,
  slippage_bps: 5,
  position_sizing: 'fixed',
};

interface SimpleBacktestFormProps {
  onBacktestComplete?: (data: SimpleBacktestResponse) => void;
}

export function SimpleBacktestForm({ onBacktestComplete }: SimpleBacktestFormProps) {
  const [form, setForm] = useState<SimpleBacktestFormState>(defaults);
  const [templates, setTemplates] = useState<TVTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Load templates on mount
  useEffect(() => {
    let cancelled = false;
    fetchBacktestTemplates()
      .then((t) => {
        if (!cancelled) {
          setTemplates(t);
          setTemplatesLoading(false);
          if (t.length > 0 && !form.template) {
            setForm((prev) => ({ ...prev, template: t[0].name }));
          }
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setTemplatesError(e.message);
          setTemplatesLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, []);

  const mutation = useMutation({
    mutationFn: (request: SimpleBacktestRequest) => runSimpleBacktest(request),
    onSuccess: (data) => {
      onBacktestComplete?.(data);
    },
    onError: (error) => {
      console.error('Backtest failed:', error);
    },
  });

  function update<K extends keyof SimpleBacktestFormState>(key: K, value: SimpleBacktestFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const symbols = form.symbols
      .split(',')
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    if (symbols.length === 0) return;
    if (!form.template) return;

    const request: SimpleBacktestRequest = {
      template: form.template,
      symbols,
      timeframe: form.timeframe,
      start: form.start_date,
      end: form.end_date,
      initial_cash: form.initial_cash,
      fees_bps: form.fees_bps,
      slippage_bps: form.slippage_bps,
      position_sizing: form.position_sizing,
      sizing_params: {},
    };

    mutation.mutate(request);
  }

  return (
    <div className="border-border/20 bg-surface/50 space-y-4 rounded border p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg font-semibold tracking-tight text-text-primary flex items-center gap-2">
          <Zap className="h-5 w-5 text-accent" />
          Simple Backtest
        </h3>
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1 bg-surface-elevated hover:bg-surface-hover text-text-secondary text-xs px-2 py-1 rounded transition-colors"
        >
          {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          {showAdvanced ? 'Hide Advanced' : 'Advanced'}
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Template Selector */}
        <div>
          <label className="text-text-muted mb-1 block text-xs">Template</label>
          {templatesLoading ? (
            <div className="flex items-center gap-2 text-text-muted text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading templates...
            </div>
          ) : templatesError ? (
            <div className="text-loss text-sm">Failed to load templates: {templatesError}</div>
          ) : (
            <select
              value={form.template}
              onChange={(e) => update('template', e.target.value)}
              disabled={mutation.isPending}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 disabled:opacity-50"
            >
              {templates.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name} {t.direction ? `(${t.direction})` : ''}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Symbols Input */}
        <div>
          <label className="text-text-muted mb-1 block text-xs">Symbols (comma-separated)</label>
          <input
            type="text"
            value={form.symbols}
            onChange={(e) => update('symbols', e.target.value)}
            placeholder="AAPL,MSFT,GOOGL"
            disabled={mutation.isPending}
            className="input disabled:opacity-50"
          />
          <p className="text-[10px] text-text-muted mt-1">Enter comma-separated tickers. Results will be aggregated across all symbols.</p>
        </div>

        {/* Date Range */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="flex items-center gap-1 text-text-muted mb-1 text-xs">
              <Calendar className="h-3 w-3" />
              Start Date
            </label>
            <input
              type="date"
              value={form.start_date}
              onChange={(e) => update('start_date', e.target.value)}
              disabled={mutation.isPending}
              max={new Date().toISOString().split('T')[0]}
              className="input disabled:opacity-50"
            />
          </div>
          <div>
            <label className="flex items-center gap-1 text-text-muted mb-1 text-xs">
              <Calendar className="h-3 w-3" />
              End Date
            </label>
            <input
              type="date"
              value={form.end_date}
              onChange={(e) => update('end_date', e.target.value)}
              disabled={mutation.isPending}
              max={new Date().toISOString().split('T')[0]}
              className="input disabled:opacity-50"
            />
          </div>
        </div>

        {/* Timeframe */}
        <div>
          <label className="text-text-muted mb-1 block text-xs">Timeframe</label>
          <select
            value={form.timeframe}
            onChange={(e) => update('timeframe', e.target.value)}
            disabled={mutation.isPending}
            className="select disabled:opacity-50"
          >
            {TIMEFRAME_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {showAdvanced && (
          <div className="border-t border-border/30 pt-4 space-y-3">
            <h4 className="text-text-secondary text-xs font-semibold flex items-center gap-2">
              <DollarSign className="h-3 w-3" />
              Advanced Settings
            </h4>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="text-text-muted mb-1 block text-xs">Initial Cash</label>
                <input
                  type="number"
                  value={form.initial_cash}
                  onChange={(e) => update('initial_cash', Number(e.target.value))}
                  min={1000}
                  step={1000}
                  disabled={mutation.isPending}
                  className="input disabled:opacity-50"
                />
              </div>

              <div>
                <label className="text-text-muted mb-1 block text-xs">Fees (bps)</label>
                <input
                  type="number"
                  value={form.fees_bps}
                  onChange={(e) => update('fees_bps', Number(e.target.value))}
                  min={0}
                  disabled={mutation.isPending}
                  className="input disabled:opacity-50"
                />
              </div>

              <div>
                <label className="text-text-muted mb-1 block text-xs">Slippage (bps)</label>
                <input
                  type="number"
                  value={form.slippage_bps}
                  onChange={(e) => update('slippage_bps', Number(e.target.value))}
                  min={0}
                  disabled={mutation.isPending}
                  className="input disabled:opacity-50"
                />
              </div>

              <div>
                <label className="text-text-muted mb-1 block text-xs">Position Sizing</label>
                <div className="flex gap-2">
                  {POSITION_SIZING_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => update('position_sizing', opt.value)}
                      disabled={mutation.isPending}
                      className={cn(
                        'flex-1 rounded px-3 py-2 text-xs font-medium transition-colors',
                        form.position_sizing === opt.value
                          ? 'bg-accent text-white'
                          : 'border-border bg-surface text-text-secondary hover:bg-surface-hover border'
                      )}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={mutation.isPending || !form.template || templatesLoading}
          className={cn(
            'w-full rounded-lg py-3 text-sm font-semibold transition-colors',
            mutation.isPending || !form.template || templatesLoading
              ? 'bg-surface-elevated text-text-muted cursor-not-allowed'
              : 'bg-accent text-white hover:bg-accent-dark'
          )}
        >
          {mutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Running Backtest...
            </>
          ) : (
            <>
              <Zap className="h-4 w-4 mr-2" />
              Run Backtest
            </>
          )}
        </button>

        {mutation.isError && (
          <div className="flex items-center gap-2 text-xs text-loss bg-loss-bg rounded p-3">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            Error: {(mutation.error as Error)?.message || 'Backtest failed'}
          </div>
        )}
      </form>
    </div>
  );
}