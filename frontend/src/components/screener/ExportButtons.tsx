import { useState } from 'react';
import { fetchScreen } from '@/api/screener';
import { useScreenStore } from '@/store/screen';

export function ExportButtons() {
  const [loading, setLoading] = useState<'csv' | 'json' | null>(null);
  const { selectedConfig, timeframes } = useScreenStore();

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      setLoading(format);
      const data = await fetchScreen(selectedConfig, undefined, timeframes, format);

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
    <div className="flex gap-2">
      <button
        onClick={() => handleExport('csv')}
        disabled={loading !== null}
        className="rounded bg-dark-600 px-3 py-1.5 text-sm text-dark-200 hover:bg-dark-500 disabled:opacity-50"
      >
        {loading === 'csv' ? 'Exporting...' : 'Export CSV'}
      </button>
      <button
        onClick={() => handleExport('json')}
        disabled={loading !== null}
        className="rounded bg-dark-600 px-3 py-1.5 text-sm text-dark-200 hover:bg-dark-500 disabled:opacity-50"
      >
        {loading === 'json' ? 'Exporting...' : 'Export JSON'}
      </button>
    </div>
  );
}

function convertToCsv(data: unknown[]): string {
  if (data.length === 0) return '';
  const headers = Object.keys(data[0] as Record<string, unknown>);
  const csvRows = [headers.join(',')];
  for (const row of data) {
    const values = headers.map((h) => {
      const val = (row as Record<string, unknown>)[h];
      if (typeof val === 'object') return JSON.stringify(val);
      return String(val ?? '');
    });
    csvRows.push(values.join(','));
  }
  return csvRows.join('\n');
}
