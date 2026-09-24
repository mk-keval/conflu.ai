import { cn } from '@/lib/cn';

interface ColumnDef {
  key: string;
  label: string;
}

interface ColumnHeaderProps {
  column: ColumnDef;
  sortKey: string | null;
  sortDir: 'asc' | 'desc' | null;
  onSort: (key: string) => void;
}

export function ColumnHeader({
  column,
  sortKey,
  sortDir,
  onSort,
}: ColumnHeaderProps) {
  const isSorted = sortKey === column.key;

  return (
    <th
      onClick={() => onSort(column.key)}
      className={cn(
        'cursor-pointer select-none px-3 py-2 text-left text-xs font-medium uppercase tracking-wider transition-colors',
        'border-b border-border text-text-muted hover:text-text-primary'
      )}
    >
      <div className="flex items-center gap-1">
        <span>{column.label}</span>
        <span className="text-[10px]">
          {isSorted && sortDir === 'asc' && '▲'}
          {isSorted && sortDir === 'desc' && '▼'}
        </span>
      </div>
    </th>
  );
}
