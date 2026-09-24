import { useState } from 'react';
import { cn } from '@/lib/cn';
import {
  ChevronDown,
  BookOpen,
  Search,
  Filter,
  BarChart3,
  TrendingUp,
} from 'lucide-react';
import type { ScreenTemplateDetail } from '@/types/screener';
import { filtersByCategory } from './filterDescriptions';

interface ScreenerEducationProps {
  template: ScreenTemplateDetail | null;
}

export function ScreenerEducation({ template }: ScreenerEducationProps) {
  const [openSection, setOpenSection] = useState<string | null>('what-is');

  const toggle = (id: string) => {
    setOpenSection(openSection === id ? null : id);
  };

  if (!template) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-border bg-surface/50">
        <p className="text-sm text-text-muted">
          Select a screener template to learn about it
        </p>
      </div>
    );
  }

  const direction =
    template.direction === 'short' ? 'Short / Bearish' : 'Long / Bullish';
  const marketLabel = template.asset_classes
    .join(', ')
    .replace('equities', 'Stocks')
    .replace('crypto', 'Crypto');
  const byCategory = filtersByCategory(template.filters);

  const sections = [
    {
      id: 'what-is',
      title: 'What This Screener Finds',
      icon: <Search className="h-4 w-4" />,
      content: [template.description],
    },
    {
      id: 'how-filters',
      title: 'How The Filters Work',
      icon: <Filter className="h-4 w-4" />,
      content: [],
      subsections: byCategory.map((g) => ({
        title: g.category,
        text: g.rules.map((r, i) => `${i + 1}. ${r}`),
      })),
    },
    {
      id: 'conditions',
      title: 'Best Use & Market Conditions',
      icon: <BarChart3 className="h-4 w-4" />,
      content: [],
      subsections: [
        {
          title: 'Direction',
          text: [direction],
        },
        {
          title: 'Asset Classes',
          text: [marketLabel],
        },
        {
          title: 'Timeframes Considered',
          text:
            template.timeframes.length > 0
              ? [
                  'Primary: ' +
                    template.timeframes.join(', ') +
                    (template.timeframes.includes('1W') ? '' : ''),
                ]
              : ['Daily (default)'],
        },
        {
          title: 'Universe',
          text: [template.universe?.markets?.join(', ') ?? 'America'],
        },
      ],
    },
    {
      id: 'how-to-use',
      title: 'How To Use The Results',
      icon: <TrendingUp className="h-4 w-4" />,
      content: getUsageGuidance(template),
    },
  ];

  return (
    <div className="rounded-xl border border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border px-5 py-3">
        <BookOpen className="h-4 w-4 text-accent" />
        <h2 className="text-sm font-bold text-text-primary">
          Learn: {template.name}
        </h2>
      </div>

      <div className="divide-y divide-border">
        {sections.map((section) => {
          const isOpen = openSection === section.id;

          return (
            <div key={section.id}>
              <button
                onClick={() => toggle(section.id)}
                className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-surface-hover"
              >
                <span className="text-accent">{section.icon}</span>
                <span className="flex-1 text-sm font-semibold text-text-primary">
                  {section.title}
                </span>
                <ChevronDown
                  className={cn(
                    'h-4 w-4 text-text-muted transition-transform duration-200',
                    isOpen && 'rotate-180'
                  )}
                />
              </button>

              {isOpen && (
                <div className="space-y-4 px-5 pb-5 pt-1">
                  {section.content.map((para, i) => (
                    <p
                      key={i}
                      className="text-sm leading-relaxed text-text-secondary"
                    >
                      {para}
                    </p>
                  ))}

                  {section.subsections?.map((sub, i) => (
                    <div key={i} className="space-y-1.5">
                      <h4 className="text-sm font-bold text-text-primary">
                        {sub.title}
                      </h4>
                      {sub.text.map((line, j) => (
                        <p
                          key={j}
                          className="text-sm leading-relaxed text-text-secondary"
                        >
                          {line}
                        </p>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Generate usage guidance text based on template properties. */
function getUsageGuidance(template: ScreenTemplateDetail): string[] {
  const n = template.name.toLowerCase();
  const d = template.direction;

  const tips: string[] = [
    '1. Scan the results table for stocks with the highest scores — these match the most criteria.',
    '2. Click any ticker to open the detail panel for deeper analysis (entry, stop-loss, targets).',
    '3. Sort by Score, Change, or Volume to find the strongest setups.',
  ];

  if (n.includes('breakout') || n.includes('momentum')) {
    tips.push(
      '4. Look for stocks sustaining above the breakout level — failed breakouts retrace quickly.'
    );
    tips.push(
      '5. Use the 4h timeframe results to confirm the momentum is holding intraday.'
    );
  }
  if (n.includes('trend')) {
    tips.push(
      '4. Pullbacks to the moving average within an uptrend are often re-entry opportunities.'
    );
    tips.push(
      '5. Multi-timeframe confirmation (daily + 4h) increases probability of trend continuation.'
    );
  }
  if (
    n.includes('oversold') ||
    n.includes('reversion') ||
    n.includes('bounce')
  ) {
    tips.push(
      '4. Wait for a bullish confirmation candle before entering — catching a falling knife is risky.'
    );
    tips.push(
      '5. Set tight stop-losses below the recent swing low; reversal trades are higher risk.'
    );
  }
  if (n.includes('surge') || n.includes('volume')) {
    tips.push(
      '4. Heavy volume confirms institutional interest — low-volume breakouts often fail.'
    );
    tips.push(
      '5. Check if the volume surge aligns with a catalyst (earnings, news, sector rotation).'
    );
  }
  if (n.includes('low-vol') || n.includes('setup')) {
    tips.push(
      '4. Low-vol setups precede expansion — the squeeze can break either direction. Wait for confirmation.'
    );
  }
  if (d === 'short' || n.includes('distribution') || n.includes('breakdown')) {
    tips.push(
      '4. Short trades require extra caution — use tight stops and consider longer timeframes for confirmation.'
    );
    tips.push(
      '5. Look for below-average volume on any bounce attempt — dead cat bounces trap new shorts.'
    );
  }
  if (n.includes('52') || n.includes('52week') || n.includes('52-week')) {
    tips.push(
      '4. 52-week breakouts to new highs have no overhead resistance — strong momentum can continue.'
    );
    tips.push(
      '5. Use a volatility stop (ATR-based) to let winners run without giving back gains.'
    );
  }

  return tips;
}
