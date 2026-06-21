import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { generateReport } from '@/api/backtest';
import { cn } from '@/lib/cn';
import type { ReportRequest } from '@/types/backtest';

interface ReportDownloadProps {
  runId: string;
}

const FORMATS = ['html', 'pdf', 'json'] as const;

export function ReportDownload({ runId }: ReportDownloadProps) {
  const [formats, setFormats] = useState<('html' | 'pdf' | 'json')[]>(['html']);
  const [includeEquity, setIncludeEquity] = useState(true);
  const [includeDrawdown, setIncludeDrawdown] = useState(true);
  const [includeTrades, setIncludeTrades] = useState(true);
  const [includeRegimes, setIncludeRegimes] = useState(false);
  const [includeParams, setIncludeParams] = useState(true);
  const [showOptions, setShowOptions] = useState(false);

  const mutation = useMutation({
    mutationFn: (body: ReportRequest) => generateReport(runId, body),
  });

  function handleGenerate() {
    const body: ReportRequest = {
      formats,
      template: 'backtest_report.html',
      include_equity_curve: includeEquity,
      include_drawdown: includeDrawdown,
      include_trade_analysis: includeTrades,
      include_regime_analysis: includeRegimes,
      include_parameter_sensitivity: includeParams,
    };
    mutation.mutate(body);
  }

  function toggleFormat(fmt: 'html' | 'pdf' | 'json') {
    setFormats((prev) => prev.includes(fmt) ? prev.filter((f) => f !== fmt) : [...prev, fmt]);
  }

  const result = mutation.data;

  return (
    <div className="space-y-3 rounded border border-dark-600 bg-dark-800 p-4">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-dark-200">Report Generation</h4>
        <button onClick={() => setShowOptions(!showOptions)}
          className="text-[10px] text-dark-400 hover:text-dark-200 transition-colors">
          {showOptions ? 'Hide options' : 'Options'}
        </button>
      </div>

      {showOptions && (
        <div className="space-y-2">
          <div>
            <label className="mb-1 block text-[10px] text-dark-400">Formats</label>
            <div className="flex gap-2">
              {FORMATS.map((fmt) => (
                <button key={fmt} type="button" onClick={() => toggleFormat(fmt)}
                  className={cn('rounded px-2.5 py-1 text-[10px] font-medium uppercase transition-colors',
                    formats.includes(fmt) ? 'bg-accent text-white' : 'border border-dark-500 text-dark-300 hover:bg-dark-600'
                  )}>
                  {fmt}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1">
            {([
              [includeEquity, setIncludeEquity, 'Equity Curve'] as const,
              [includeDrawdown, setIncludeDrawdown, 'Drawdown'] as const,
              [includeTrades, setIncludeTrades, 'Trade Analysis'] as const,
              [includeRegimes, setIncludeRegimes, 'Regime Analysis'] as const,
              [includeParams, setIncludeParams, 'Parameter Sensitivity'] as const,
            ]).map(([value, setter, label]) => (
              <label key={label} className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={value}
                  onChange={(e) => setter(e.target.checked)}
                  className="rounded border-dark-500 bg-dark-700 text-accent focus:ring-accent" />
                <span className="text-[11px] text-dark-300">{label}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      <button onClick={handleGenerate} disabled={mutation.isPending || formats.length === 0}
        className={cn('w-full rounded py-2 text-xs font-semibold transition-colors',
          mutation.isPending || formats.length === 0
            ? 'cursor-not-allowed bg-dark-500 text-dark-300'
            : 'bg-accent text-white hover:bg-accent-dark'
        )}>
        {mutation.isPending ? 'Generating...' : 'Generate Report'}
      </button>

      {mutation.isError && (
        <p className="text-xs text-loss">Error: {(mutation.error as Error)?.message}</p>
      )}

      {result && result.formats.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] text-dark-400">Download:</p>
          {result.formats.map((f) => (
            <a key={f.format} href={f.download_url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 rounded bg-dark-700 px-3 py-1.5 text-xs text-accent hover:text-accent-light hover:bg-dark-600 transition-colors">
              <span className="uppercase text-[10px] font-medium">{f.format}</span>
              <span className="text-dark-400 truncate">{f.download_url}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
