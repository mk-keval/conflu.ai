import { useState, useEffect } from 'react';
import { cn } from '@/lib/cn';
import type { ScreenTemplateConfig, FilterRuleConfig, FilterParam } from '@/lib/constants';
import { TIMEFRAMES } from '@/lib/constants';

interface FilterParamInputProps {
  param: FilterParam;
  value: string | number | boolean;
  onChange: (value: string | number | boolean) => void;
}

// Multi-timeframe filters that support compareTimeframe
const MULTI_TF_FILTERS = new Set([
  'ema_compare',
  'rsi_compare',
  'indicator_compare',
  'price_vs_ema',
]);

function FilterParamInput({ param, value, onChange }: FilterParamInputProps) {
  const { type, options, min, max, step } = param;

  if (type === 'select' && options) {
    return (
      <select
        value={String(value)}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-dark-400 bg-dark-600 px-2 py-1 text-sm text-dark-50 focus:border-accent focus:outline-none"
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt.charAt(0).toUpperCase() + opt.slice(1)}
          </option>
        ))}
      </select>
    );
  }

  if (type === 'boolean') {
    const checked = value === true;
    return (
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="rounded border-dark-400 bg-dark-600 text-accent focus:ring-accent"
        />
        <span className="text-sm text-dark-300">Enabled</span>
      </label>
    );
  }

  // Number input
  const numValue = typeof value === 'number' ? value : 0;
  return (
    <input
      type="number"
      value={numValue}
      onChange={(e) => onChange(Number(e.target.value))}
      min={min}
      max={max}
      step={step}
      className="w-20 rounded border border-dark-400 bg-dark-600 px-2 py-1 text-sm text-dark-50 focus:border-accent focus:outline-none"
    />
  );
}

interface FilterRowProps {
  filter: FilterRuleConfig;
  index: number;
  values: Record<string, string | number | boolean>;
  onParamChange: (filterIndex: number, paramKey: string, value: string | number | boolean) => void;
  onToggleNegate: (filterIndex: number) => void;
  onToggleOperator: (filterIndex: number) => void;
  onToggleCompareTimeframe: (filterIndex: number) => void;
  onRemove: (filterIndex: number) => void;
  isExpanded: boolean;
  onToggleExpand: () => void;
}

function FilterRow({ filter, index, values, onParamChange, onToggleNegate, onToggleOperator, onToggleCompareTimeframe, onRemove, isExpanded, onToggleExpand }: FilterRowProps) {
  const isMultiTF = MULTI_TF_FILTERS.has(filter.indicator);
  const currentCompareTF = filter.compareTimeframe || '';

  return (
    <div className={cn('rounded border border-dark-600 bg-dark-800 overflow-hidden', isExpanded && 'border-accent')}>
      {/* Filter header */}
      <div
        onClick={onToggleExpand}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggleExpand(); }}}
        role="button"
        tabIndex={0}
        className={cn('w-full flex items-center justify-between gap-2 p-3 text-left cursor-pointer', isExpanded && 'bg-dark-700')}
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="text-xs font-mono text-dark-400 w-8 text-right">{index + 1}.</span>
          <span className="text-xs text-dark-400 uppercase tracking-wider">{filter.category}</span>
          <span className="font-medium text-dark-100 truncate">{filter.label}</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-dark-600 text-dark-300">{filter.timeframe}</span>
          {isMultiTF && currentCompareTF && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-accent/20 text-accent border border-accent/30">
              vs {currentCompareTF}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={filter.negate}
              onChange={(e) => { e.stopPropagation(); onToggleNegate(index); }}
              className="rounded border-dark-400 bg-dark-600 text-accent focus:ring-accent"
              title="Negate filter"
            />
            <span className="text-[10px] text-dark-400">NOT</span>
          </label>
          <select
            value={filter.operator}
            onChange={(e) => { e.stopPropagation(); onToggleOperator(index); }}
            className="rounded border border-dark-400 bg-dark-600 px-2 py-0.5 text-xs text-dark-50 focus:border-accent focus:outline-none"
            title="Operator"
          >
            <option value="gt">&gt;</option>
            <option value="lt">&lt;</option>
            <option value="eq">=</option>
            <option value="crosses_above">Crosses ↑</option>
            <option value="crosses_below">Crosses ↓</option>
          </select>
          {isMultiTF && (
            <select
              value={currentCompareTF}
              onChange={(e) => { e.stopPropagation(); onToggleCompareTimeframe(index); }}
              className="rounded border border-dark-400 bg-dark-600 px-2 py-0.5 text-xs text-dark-50 focus:border-accent focus:outline-none"
              title="Compare Timeframe"
            >
              <option value="">-- Compare TF --</option>
              {TIMEFRAMES.map((tf) => (
                <option key={tf} value={tf}>{tf}</option>
              ))}
            </select>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onRemove(index); }}
            className="p-1 text-dark-400 hover:text-loss hover:bg-dark-600 rounded"
            title="Remove filter"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>

      {/* Expanded params */}
      {isExpanded && Object.keys(filter.params).length > 0 && (
        <div className="p-3 border-t border-dark-600 space-y-2 bg-dark-900">
          {Object.entries(filter.params).map(([paramKey, param]) => (
            <div key={paramKey} className="flex items-center gap-2">
              <label className="text-xs text-dark-300 w-32">{param.label}:</label>
              <FilterParamInput
                param={param}
                value={values[paramKey] ?? param.defaultValue}
                onChange={(v) => onParamChange(index, paramKey, v)}
              />
              {param.type === 'number' && param.min !== undefined && (
                <span className="text-[10px] text-dark-400">({param.min}–{param.max})</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* No params message */}
      {isExpanded && Object.keys(filter.params).length === 0 && (
        <div className="p-3 border-t border-dark-600 text-center text-xs text-dark-400 bg-dark-900">
          No configurable parameters
        </div>
      )}
    </div>
  );
}

interface ScreenTemplateEditorProps {
  config: ScreenTemplateConfig;
  defaultConfig: ScreenTemplateConfig;
  onConfigChange: (config: ScreenTemplateConfig) => void;
  onReset: () => void;
  isDirty: boolean;
}

export function ScreenTemplateEditor({
  config,
  defaultConfig,
  onConfigChange,
  onReset,
  isDirty,
}: ScreenTemplateEditorProps) {
  const [configState, setConfigState] = useState<ScreenTemplateConfig>(config);
  const [expandedFilters, setExpandedFilters] = useState<Record<number, boolean>>({});

  // Sync with config prop changes
  useEffect(() => {
    setConfigState(config);
    setExpandedFilters({});
  }, [config]);
  // useEffect(() => {
  //   setConfig(defaultConfig);
  //   setExpandedFilters({});
  // }, [defaultConfig]);

  // Notify parent of changes
  // useEffect(() => {
  //   onConfigChange(config);
  // }, [config, onConfigChange]);

  const handleParamChange = (filterIndex: number, paramKey: string, value: string | number | boolean) => {
    const newConfig = {
      ...configState,
      filters: configState.filters.map((f, i) =>
        i === filterIndex && f.params[paramKey]
          ? { ...f, params: { ...f.params, [paramKey]: { ...f.params[paramKey], defaultValue: value } } }
          : f
      ),
    };
    setConfigState(newConfig);
    onConfigChange(newConfig);
  };

  const handleToggleNegate = (filterIndex: number) => {
    const newConfig = {
      ...configState,
      filters: configState.filters.map((f, i) =>
        i === filterIndex ? { ...f, negate: !f.negate } : f
      ),
    };
    setConfigState(newConfig);
    onConfigChange(newConfig);
  };

  const handleToggleOperator = (filterIndex: number) => {
    const operators = ['gt', 'lt', 'eq', 'crosses_above', 'crosses_below'] as const;
    const newConfig = {
      ...configState,
      filters: configState.filters.map((f, i) => {
        if (i !== filterIndex) return f;
        const currentIndex = operators.indexOf(f.operator as typeof operators[number]);
        const nextIndex = (currentIndex + 1) % operators.length;
        return { ...f, operator: operators[nextIndex] };
      }),
    };
    setConfigState(newConfig);
    onConfigChange(newConfig);
  };

  const handleToggleCompareTimeframe = (filterIndex: number) => {
    const timeframes = ['', ...TIMEFRAMES];
    const currentTF = configState.filters[filterIndex].compareTimeframe || '';
    const currentIndex = timeframes.indexOf(currentTF);
    const nextIndex = (currentIndex + 1) % timeframes.length;
    const newTF = timeframes[nextIndex];
    
    const newConfig = {
      ...configState,
      filters: configState.filters.map((f, i) =>
        i === filterIndex ? { ...f, compareTimeframe: newTF || undefined } : f
      ),
    };
    setConfigState(newConfig);
    onConfigChange(newConfig);
  };

  const handleRemoveFilter = (filterIndex: number) => {
    const newConfig = {
      ...configState,
      filters: configState.filters.filter((_, i) => i !== filterIndex),
    };
    setConfigState(newConfig);
    onConfigChange(newConfig);
  };

  const handleToggleExpand = (filterIndex: number) => {
    setExpandedFilters((prev) => ({ ...prev, [filterIndex]: !prev[filterIndex] }));
  };

  return (
    <div className="space-y-3">
      {/* Template header */}
      <div className="flex items-start justify-between gap-3 p-3 rounded border border-dark-600 bg-dark-800">
        <div>
          <h3 className="font-semibold text-dark-50">{defaultConfig.name}</h3>
          <p className="text-xs text-dark-400 mt-0.5">{defaultConfig.description}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-[10px] text-dark-400">Asset Classes:</span>
            <span className="text-xs text-dark-200">{defaultConfig.assetClasses.join(', ')}</span>
            <span className="text-[10px] text-dark-400">Timeframes:</span>
            <span className="text-xs text-dark-200">{defaultConfig.timeframes.join(', ')}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isDirty && (
            <button
              onClick={onReset}
              className="px-3 py-1.5 text-xs font-medium text-dark-300 hover:text-dark-50 hover:bg-dark-600 rounded border border-dark-400 transition-colors"
            >
              Reset to Defaults
            </button>
          )}
        </div>
      </div>

      {/* Filters list */}
      <div className="space-y-2">
        {configState.filters.map((filter, index) => (
          <FilterRow
            key={index}
            filter={filter}
            index={index}
            values={Object.fromEntries(
              Object.entries(filter.params).map(([k, p]) => [k, p.defaultValue])
            )}
            onParamChange={handleParamChange}
            onToggleNegate={handleToggleNegate}
            onToggleOperator={handleToggleOperator}
            onToggleCompareTimeframe={handleToggleCompareTimeframe}
            onRemove={handleRemoveFilter}
            isExpanded={expandedFilters[index] ?? false}
            onToggleExpand={() => handleToggleExpand(index)}
          />
        ))}

        {configState.filters.length === 0 && (
          <div className="text-center py-8 text-dark-400">
            No filters in this template
          </div>
        )}
      </div>
    </div>
  );
}