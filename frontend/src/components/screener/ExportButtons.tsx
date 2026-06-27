import { useState } from 'react';
import { fetchScreenTV } from '@/api/screener';
import { useScreenStore } from '@/store/screen';
import type { TVScoredTicker } from '@/types/screener';
import { FileText, FileSpreadsheet } from 'lucide-react';

export function ExportButtons() {
  const [loading, setLoading] = useState<'csv' | 'json' | null>(null);
  const { selectedConfig } = useScreenStore();

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      setLoading(format);
      const response = await fetchScreenTV(selectedConfig, 500);
      const data = response.results;

      const blob = new Blob(
        [format === 'json' ? JSON.stringify(data, null, 2) : convertToCsv(data)],
        { type: format === 'json' ? 'application/json' : 'text/csv' }
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `screener-${selectedConfig}-${Date.now()}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => handleExport('csv')}
        disabled={loading !== null}
        className="btn-secondary gap-1.5"
        title="Export CSV"
      >
        <FileSpreadsheet className="w-4 h-4" />
        <span className="hidden sm:inline">CSV</span>
      </button>
      <button
        onClick={() => handleExport('json')}
        disabled={loading !== null}
        className="btn-secondary gap-1.5"
        title="Export JSON"
      >
        <FileText className="w-4 h-4" />
        <span className="hidden sm:inline">JSON</span>
      </button>
    </div>
  );
}

function convertToCsv(data: TVScoredTicker[]): string {
  if (data.length === 0) return '';
  const headers = ['symbol', 'score', 'rating', 'entry', 'stop_loss', 'targets', 'risk_reward', 'breakdown'];
  const csvRows = [headers.join(',')];
  for (const row of data) {
    const values = headers.map((h) => {
      const val = (row as unknown as Record<string, unknown>)[h];
      if (typeof val === 'object') return JSON.stringify(val);
      return String(val ?? '');
    });
    csvRows.push(values.join(','));
  }
  return csvRows.join('\n');
}
