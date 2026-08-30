import { useState } from 'react';
import { cn } from '@/lib/cn';
import { Info, ChevronDown, Check } from 'lucide-react';
import type { ScreenTemplateDetail } from '@/types/screener';
import { formatFilterList, filtersByCategory, CATEGORY_HINTS, type FilterRuleDisplay } from './filterDescriptions';

interface TemplateInfoStripProps {
  template: ScreenTemplateDetail | null;
}

export function TemplateInfoStrip({ template }: TemplateInfoStripProps) {
  const [expanded, setExpanded] = useState(false);

  if (!template) return null;

  // Group rules by category so the expander reads as a structured checklist
  const grouped: { category: string; rules: string[] }[] =
    expanded && Array.isArray(template.filters)
      ? filtersByCategory(template.filters as unknown as FilterRuleDisplay[])
      : [];

  return (
    <div className="border-b border-border bg-surface/30 px-4 py-2">
      <div className="flex items-start gap-2">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
        <div className="flex-1 min-w-0">
          <p className="text-xs leading-relaxed text-text-secondary">
            {template.description}
          </p>
          {expanded && (
            <p className="mt-1 text-xs text-text-muted/70 leading-relaxed">
              A stock must pass <span className="text-text-primary font-semibold">every rule below</span> to appear in results:
            </p>
          )}
          {expanded && (
            <div className="mt-2 space-y-2.5">
              {grouped.map(({ category, rules }) => (
                <div key={category} className="rounded-md border border-border/40 bg-background/40 p-2.5">
                  <div className="flex items-baseline gap-2 mb-1.5">
                    <span className="text-xs font-semibold text-text-primary">{category}</span>
                    <span className="text-[10px] text-text-muted leading-tight">{rules.length} rule{rules.length > 1 ? 's' : ''}</span>
                  </div>
                  <ul className="space-y-1">
                    {rules.map((rule, i) => (
                      <li key={i} className="text-xs text-text-secondary flex items-start gap-2">
                        <Check className="h-3 w-3 mt-0.5 shrink-0 text-gain" />
                        <span>{rule}</span>
                      </li>
                    ))}
                  </ul>
                  {CATEGORY_HINTS[category.toLowerCase()] && (
                    <p className="text-[10px] text-text-muted/80 italic mt-1.5 pl-5">
                      Why it matters: {CATEGORY_HINTS[category.toLowerCase()]}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
          {!expanded && template.filters?.length > 0 && (
            <p className="mt-1 text-xs text-text-muted/70 truncate">{formatFilterList(template.filters)}</p>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-1 flex items-center gap-1 text-xs text-accent hover:text-accent/80 transition-colors"
          >
            <span>{expanded ? 'Hide' : 'View'} filters</span>
            <ChevronDown className={cn(
              'h-3 w-3 transition-transform',
              expanded && 'rotate-180'
            )} />
          </button>
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
