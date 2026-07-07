import { useState } from 'react';
import { cn } from '@/lib/cn';
import { Info, ChevronDown } from 'lucide-react';
import type { ScreenTemplateDetail } from '@/types/screener';
import { formatFilterList } from './filterDescriptions';

interface TemplateInfoStripProps {
  template: ScreenTemplateDetail | null;
}

export function TemplateInfoStrip({ template }: TemplateInfoStripProps) {
  const [expanded, setExpanded] = useState(false);

  if (!template) return null;

  return (
    <div className="border-b border-border bg-surface/30 px-4 py-2">
      <div className="flex items-start gap-2">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
        <div className="flex-1 min-w-0">
          <p className="text-xs leading-relaxed text-text-secondary">
            {template.description}
          </p>
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-1 flex items-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors"
          >
            <span>{expanded ? 'Hide' : 'View'} filters</span>
            <ChevronDown className={cn(
              'h-3 w-3 transition-transform',
              expanded && 'rotate-180'
            )} />
          </button>
          {expanded && (
            <p className="mt-1 text-xs text-text-muted/70 leading-relaxed">
              {formatFilterList(template.filters)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={cn(
            'text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded',
            template.direction === 'short'
              ? 'bg-loss/10 text-loss'
              : 'bg-gain/10 text-gain'
          )}>
            {template.direction}
          </span>
          {template.timeframes.map((tf) => (
            <span key={tf} className="text-[10px] font-semibold text-text-muted bg-surface px-1.5 py-0.5 rounded">
              {tf}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
