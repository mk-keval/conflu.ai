import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { cn } from '@/lib/cn';
import {
  Plus,
  Loader2,
  ChevronDown,
  ChevronUp,
  Settings,
  Zap,
  Trash2Icon,
} from 'lucide-react';
import {
  runFilterSweep,
  type FilterSweepConfig,
} from '@/api/backtest';

const OBJECTIVE_OPTIONS = [
  'sharpe',
  'sortino',
  'calmar',
  'win_rate',
  'profit_factor',
  'expectancy',
] as const;

type OptimizationMetric = typeof OBJECTIVE_OPTIONS[number];

interface ParamRow {
  key: string;
  type: 'int' | 'float' | 'categorical';
  low: string;
  high: string;
  step: string;
  choices: string;
}

interface FormState {
  name: string;
  description: string;
  screen_name: string;
  symbols: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  initial_cash: number;
  fees_bps: number;
  slippage_bps: number;
  position_sizing: 'fixed' | 'atr' | 'kelly';
  sizing_params: Record<string, unknown>;
  optimization_metric: OptimizationMetric;
  max_combinations: number;
  parallel_jobs: number;
  params: ParamRow[];
}

const POSITION_SIZING_OPTIONS = [
  { value: 'fixed', label: 'Fixed' },
  { value: 'atr', label: 'ATR-based' },
  { value: 'kelly', label: 'Kelly' },
] as const;

const TIMEFRAME_OPTIONS = [
  { value: '1D', label: '1 Day' },
  { value: '4h', label: '4 Hours' },
  { value: '1h', label: '1 Hour' },
  { value: '1W', label: '1 Week' },
] as const;

const SCREEN_OPTIONS = [
  { value: 'trend-follower', label: 'Trend Follower' },
  { value: 'high-conviction-stack', label: 'High Conviction Stack' },
  { value: 'bull-flag-continuation', label: 'Bull Flag Continuation' },
  { value: 'statistical-mean-reversion', label: 'Statistical Mean Reversion' },
  { value: 'institutional-swing-quality', label: 'Institutional Swing Quality' },
  { value: 'trend-leader', label: 'Trend Leader' },
  { value: 'quality-trend-fundamentals', label: 'Quality Trend Fundamentals' },
  { value: 'volatility-expansion', label: 'Volatility Expansion' },
  { value: '52week-breakout', label: '52-Week Breakout' },
  { value: 'breakdown', label: 'Breakdown' },
  { value: 'mean-reversion', label: 'Mean Reversion' },
  { value: 'short-squeeze', label: 'Short Squeeze' },
  { value: 'volume-trend-accumulation', label: 'Volume Trend Accumulation' },
] as const;

const DEFAULT_PARAM_ROW: ParamRow = {
  key: '',
  type: 'float',
  low: '0',
  high: '1',
  step: '1',
  choices: '',
};

const defaults: FormState = {
  name: 'Custom Sweep',
  description: 'Custom filter parameter sweep',
  screen_name: 'trend-follower',
  symbols: 'AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AVGO,ORCL,CRM',
  timeframe: '1D',
  start_date: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000)
    .toISOString()
    .split('T')[0],
  end_date: new Date().toISOString().split('T')[0],
  initial_cash: 100_000,
  fees_bps: 10,
  slippage_bps: 5,
  position_sizing: 'fixed',
  sizing_params: {},
  optimization_metric: 'expectancy',
  max_combinations: 2000,
  parallel_jobs: 1,
  params: [DEFAULT_PARAM_ROW],
};

const PRESET_OPTIONS = [
  {
    name: 'Trend Follower Optimization',
    description: 'Optimize trend follower screen parameters for max expectancy',
    screen_name: 'trend-follower',
    symbols: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'ORCL', 'CRM'],
    timeframe: '1D',
    start_date: '2022-01-01',
    end_date: '2024-01-01',
    optimization_metric: 'expectancy',
    max_combinations: 2000,
    params: {},
  },
  {
    name: 'High Conviction Stack Optimization',
    description: 'Optimize high conviction stack parameters',
    screen_name: 'high-conviction-stack',
    symbols: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'ORCL', 'CRM'],
    timeframe: '1D',
    start_date: '2022-01-01',
    end_date: '2024-01-01',
    optimization_metric: 'expectancy',
    max_combinations: 2000,
    params: {},
  },
  {
    name: 'Breakout Optimization',
    description: 'Optimize breakout screen parameters',
    screen_name: 'bull-flag-continuation',
    symbols: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'ORCL', 'CRM'],
    timeframe: '1D',
    start_date: '2022-01-01',
    end_date: '2024-01-01',
    optimization_metric: 'expectancy',
    max_combinations: 2000,
    params: {},
  },
  {
    name: 'Pullback Optimization',
    description: 'Optimize pullback/mean reversion screen parameters',
    screen_name: 'statistical-mean-reversion',
    symbols: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'ORCL', 'CRM'],
    timeframe: '1D',
    start_date: '2022-01-01',
    end_date: '2024-01-01',
    optimization_metric: 'expectancy',
    max_combinations: 2000,
    params: {},
  },
  {
    name: 'Institutional Quality Optimization',
    description: 'Optimize institutional quality screen parameters',
    screen_name: 'institutional-swing-quality',
    symbols: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'ORCL', 'CRM'],
    timeframe: '1D',
    start_date: '2022-01-01',
    end_date: '2024-01-01',
    optimization_metric: 'expectancy',
    max_combinations: 2000,
    params: {},
  },
];

interface FilterSweepFormProps {
  onSweepStarted?: (data: { sweep_id: string; status: string }) => void;
}

export function FilterSweepForm({ onSweepStarted }: FilterSweepFormProps) {
  const [form, setForm] = useState<FormState>(defaults);
  const [showPresets, setShowPresets] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const mutation = useMutation({
    mutationFn: (config: FilterSweepConfig) => runFilterSweep(config),
    onSuccess: (data) => {
      console.log('Sweep started:', data);
      onSweepStarted?.(data);
    },
    onError: (error) => {
      console.error('Sweep failed:', error);
    },
  });

  

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev: FormState) => ({ ...prev, [key]: value } as FormState));
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
      params: [...prev.params, DEFAULT_PARAM_ROW],
    }));
  }

  function removeParamRow(index: number) {
    setForm((prev) => ({
      ...prev,
      params: prev.params.filter((_, i) => i !== index),
    }));
  }

  function loadPreset(preset: typeof PRESET_OPTIONS[0]) {
    setForm((prev) => ({
      ...prev,
      name: preset.name,
      description: preset.description,
      screen_name: preset.screen_name,
      symbols: preset.symbols.join(','),
      timeframe: preset.timeframe,
      start_date: preset.start_date,
      end_date: preset.end_date,
      optimization_metric: preset.optimization_metric as OptimizationMetric,
      max_combinations: preset.max_combinations,
    }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const symbols = form.symbols
      .split(',')
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    if (symbols.length === 0) return;

    const param_grid: Record<string, any> = {};
    form.params.forEach((p) => {
      if (!p.key) return;
      if (p.type === 'categorical') {
        param_grid[p.key] = {
          name: p.key,
          display_name: p.key,
          param_type: 'categorical',
          choices: p.choices.split(',').map((c) => c.trim()),
          description: `Categorical parameter: ${p.key}`,
        };
      } else {
        param_grid[p.key] = {
          name: p.key,
          display_name: p.key,
          param_type: p.type,
          low: p.low ? Number(p.low) : undefined,
          high: p.high ? Number(p.high) : undefined,
          step: p.step ? Number(p.step) : undefined,
          description: `Parameter: ${p.key}`,
        };
      }
    });

    const config: FilterSweepConfig = {
      name: form.name,
      description: form.description,
      screen_name: form.screen_name,
      param_grid: Object.fromEntries(
        Object.entries(param_grid).map(([k, v]) => [
          k,
          {
            name: k,
            display_name: v.display_name,
            param_type: v.param_type,
            low: v.low,
            high: v.high,
            step: v.step,
            choices: v.choices,
            description: v.description,
          },
        ]),
      ),
      symbols: symbols,
      timeframe: form.timeframe,
      start_date: form.start_date,
      end_date: form.end_date,
      initial_cash: form.initial_cash,
      fees_bps: form.fees_bps,
      slippage_bps: form.slippage_bps,
      position_sizing: form.position_sizing,
      sizing_params: form.sizing_params,
      optimization_metric: form.optimization_metric as OptimizationMetric,
      max_combinations: form.max_combinations,
      parallel_jobs: form.parallel_jobs,
    };

    mutation.mutate(config);
  }

  return (
    <div className="border-dark-600 bg-dark-800 space-y-4 rounded border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-dark-100 text-sm font-semibold flex items-center gap-2">
          <Zap className="h-4 w-4 text-accent" />
          Filter Sweep Configuration
        </h3>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowPresets(!showPresets)}
            className="bg-dark-600 text-dark-200 hover:bg-dark-500 rounded px-2 py-1 text-xs transition-colors"
          >
            {showPresets ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            Presets
          </button>
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="bg-dark-600 text-dark-200 hover:bg-dark-500 rounded px-2 py-1 text-xs transition-colors"
          >
            {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            Advanced
          </button>
        </div>
      </div>

      {showPresets && (
        <div className="border-t border-border/30 pt-4">
          <p className="text-xs text-text-muted mb-2">Select a preset to auto-fill configuration</p>
          <div className="flex flex-wrap gap-2">
            {PRESET_OPTIONS.map((preset) => (
              <button
                key={preset.name}
                type="button"
                onClick={() => loadPreset(preset)}
                className={cn(
                  'rounded-lg border px-3 py-2 text-xs transition-colors text-left',
                  form.screen_name === preset.screen_name
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-dark-500 bg-dark-800 text-text-secondary hover:bg-dark-600'
                )}
              >
                <div className="font-medium">{preset.name}</div>
                <div className="text-[10px] text-text-muted mt-0.5">{preset.description}</div>
                <div className="text-[10px] text-text-muted">
                  {preset.screen_name} · {preset.symbols.length} symbols · {preset.max_combinations} combos
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-dark-300 mb-1 block text-xs">Sweep Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => update('name', e.target.value)}
              placeholder="My Custom Sweep"
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            />
          </div>

          <div>
            <label className="text-dark-300 mb-1 block text-xs">Screen Template</label>
            <select
              value={form.screen_name}
              onChange={(e) => update('screen_name', e.target.value)}
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            >
              {SCREEN_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-dark-300 mb-1 block text-xs">Timeframe</label>
            <select
              value={form.timeframe}
              onChange={(e) => update('timeframe', e.target.value)}
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            >
              {TIMEFRAME_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-dark-300 mb-1 block text-xs">Optimization Metric</label>
            <select
              value={form.optimization_metric}
              onChange={(e) => setForm(prev => ({ ...prev, optimization_metric: e.target.value as OptimizationMetric }))}
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            >
              {OBJECTIVE_OPTIONS.map((obj) => (
                <option key={obj} value={obj}>
                  {obj}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-dark-300 mb-1 block text-xs">Start Date</label>
            <input
              type="date"
              value={form.start_date}
              onChange={(e) => update('start_date', e.target.value)}
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            />
          </div>

          <div>
            <label className="text-dark-300 mb-1 block text-xs">End Date</label>
            <input
              type="date"
              value={form.end_date}
              onChange={(e) => update('end_date', e.target.value)}
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            />
          </div>

          <div>
            <label className="text-dark-300 mb-1 block text-xs">Symbols (comma-separated)</label>
            <input
              type="text"
              value={form.symbols}
              onChange={(e) => update('symbols', e.target.value)}
              placeholder="AAPL,MSFT,GOOGL"
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            />
          </div>

          <div>
            <label className="text-dark-300 mb-1 block text-xs">Timeframe</label>
            <select
              value={form.timeframe}
              onChange={(e) => update('timeframe', e.target.value)}
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            >
              {TIMEFRAME_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-dark-300 mb-1 block text-xs">Optimization Metric</label>
            <select
              value={form.optimization_metric}
              onChange={(e) => setForm(prev => ({ ...prev, optimization_metric: e.target.value as OptimizationMetric }))}
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            >
              {OBJECTIVE_OPTIONS.map((obj) => (
                <option key={obj} value={obj}>
                  {obj}
                </option>
              ))}
            </select>
          </div>
        </div>

        {showAdvanced && (
          <div className="border-t border-border/30 pt-4 space-y-3">
            <h4 className="text-dark-300 text-xs font-semibold flex items-center gap-2">
              <Settings className="h-3 w-3" />
              Advanced Settings
            </h4>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
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
                <label className="text-dark-300 mb-1 block text-xs">Slippage (bps)</label>
                <input
                  type="number"
                  value={form.slippage_bps}
                  onChange={(e) => update('slippage_bps', Number(e.target.value))}
                  min={0}
                  className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
                />
              </div>

              <div>
                <label className="text-dark-300 mb-1 block text-xs">Position Sizing</label>
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
                          : 'border-dark-500 text-dark-200 hover:bg-dark-600 border'
                      )}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-dark-300 mb-1 block text-xs">Max Combinations</label>
                <input
                  type="number"
                  value={form.max_combinations}
                  onChange={(e) => update('max_combinations', Number(e.target.value))}
                  min={1}
                  max={10000}
                  className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
                />
              </div>

              <div>
                <label className="text-dark-300 mb-1 block text-xs">Parallel Jobs</label>
                <input
                  type="number"
                  value={form.parallel_jobs}
                  onChange={(e) => update('parallel_jobs', Number(e.target.value))}
                  min={1}
                  max={8}
                  className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
                />
              </div>

<div>
            <label className="text-dark-300 mb-1 block text-xs">Optimization Metric</label>
            <select
              value={form.optimization_metric}
              onChange={(e) => setForm(prev => ({ ...prev, optimization_metric: e.target.value as OptimizationMetric }))}
              className="border-dark-500 bg-dark-700 text-dark-50 w-full rounded border px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            >
              {OBJECTIVE_OPTIONS.map((obj) => (
                <option key={obj} value={obj}>
                  {obj}
                </option>
              ))}
            </select>
              </div>
            </div>
          </div>
        )}

        <div className="border-t border-border/30 pt-4">
          <div className="mb-2 flex items-center justify-between">
            <label className="text-dark-300 text-xs">Parameter Space</label>
            <button
              type="button"
              onClick={addParamRow}
              className="bg-dark-600 text-dark-200 hover:bg-dark-500 rounded px-2 py-0.5 text-[10px] transition-colors"
            >
              <Plus className="h-3 w-3 mr-1" />
              Add Param
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
                  onChange={(e) => updateParam(i, 'type', e.target.value as 'int' | 'float' | 'categorical')}
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
                  <Trash2Icon className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        </div>

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
          {mutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Starting Sweep...
            </>
          ) : (
            <>
              <Zap className="h-4 w-4 mr-2" />
              Start Sweep
            </>
          )}
        </button>

        {mutation.isError && (
          <p className="text-xs text-loss text-center">
            Error: {(mutation.error as Error)?.message}
          </p>
        )}
      </form>
    </div>
  );
}