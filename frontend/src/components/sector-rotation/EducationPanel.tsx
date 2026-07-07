import { useState } from 'react';
import { cn } from '@/lib/cn';
import { ChevronDown, BookOpen, TrendingUp, BarChart3, Lightbulb, ArrowRightLeft } from 'lucide-react';

interface EducationSection {
  id: string;
  title: string;
  icon: React.ReactNode;
  content: string[];
  subsections?: { title: string; text: string[] }[];
}

const SECTIONS: EducationSection[] = [
  {
    id: 'what-is',
    title: 'What is Sector Rotation?',
    icon: <Lightbulb className="h-4 w-4" />,
    content: [
      'Sector rotation is an investment strategy that involves moving capital between different stock market sectors based on where the economy is in the business cycle. The idea is simple: different sectors perform better at different stages of the economic cycle.',
      'By identifying which phase the economy is in, investors can position themselves in sectors that historically outperform during that phase — and avoid sectors that tend to underperform.',
    ],
    subsections: [
      {
        title: 'The Economic Cycle',
        text: [
          'Early Cycle: Economy is recovering from a recession. GDP growth accelerates from low levels. Central banks maintain accommodative policy.',
          'Mid Cycle: Economy grows at a sustainable pace. Corporate profits rise. Inflation is moderate. This is typically the longest phase.',
          'Late Cycle: Economy overheats. Growth peaks. Inflation rises. Central banks tighten policy. Yield curve may flatten.',
          'Recession: Economic contraction. Corporate profits decline. Central banks cut rates. Defensive sectors provide shelter.',
        ],
      },
    ],
  },
  {
    id: 'how-it-works',
    title: 'How Smart Money Rotates',
    icon: <ArrowRightLeft className="h-4 w-4" />,
    content: [
      'Institutional investors (pension funds, hedge funds, mutual funds) move capital between sectors systematically based on macroeconomic signals. This "smart money" flow can be tracked through sector ETF performance, volume patterns, and relative strength analysis.',
      'When smart money rotates OUT of a sector, you see persistent underperformance with above-average volume (distribution). When it rotates IN, you see outperformance with rising volume (accumulation).',
    ],
  },
  {
    id: 'classic-cycle',
    title: 'Classic Sector Rotation Cycle',
    icon: <TrendingUp className="h-4 w-4" />,
    content: [],
    subsections: [
      {
        title: 'Early Cycle — Cyclicals Lead',
        text: [
          'Consumer Discretionary (XLY): Rising consumer confidence drives spending on big-ticket items.',
          'Industrials (XLI): Manufacturing picks up as businesses restock inventories.',
          'Materials (XLB): Commodity demand increases, prices rise from depressed levels.',
          'Technology (XLK): Businesses invest in productivity-enhancing technology.',
        ],
      },
      {
        title: 'Mid Cycle — Growth Leads',
        text: [
          'Technology (XLK): Sustained growth as innovation cycles continue.',
          'Communication Services (XLC): Media and entertainment benefit from consumer spending.',
          'Health Care (XLV): Steady earnings growth with defensive characteristics.',
          'Consumer Cyclical (XLY): Continues to perform well in expansion.',
        ],
      },
      {
        title: 'Late Cycle — Value & Inflation Hedges',
        text: [
          'Energy (XLE): Rising inflation and commodity prices boost oil & gas profits.',
          'Financials (XLF): Banks benefit from steepening yield curve and higher interest rates.',
          'Materials (XLB): Commodity price momentum continues.',
          'Consumer Staples (XLP): Rotation begins toward defensives.',
        ],
      },
      {
        title: 'Recession — Defensives Shelter',
        text: [
          'Utilities (XLU): Stable earnings, high dividends, bond proxy.',
          'Consumer Staples (XLP): Recession-resistant demand for essentials.',
          'Health Care (XLV): Inelastic demand for medical services.',
          'Real Estate (XLRE): Income stability from long-term leases.',
        ],
      },
    ],
  },
  {
    id: 'key-metrics',
    title: 'How We Measure Rotation',
    icon: <BarChart3 className="h-4 w-4" />,
    content: [],
    subsections: [
      {
        title: 'Relative Strength (RS)',
        text: [
          'RS compares a sector\'s performance to the average of all sectors. A positive RS means the sector is outperforming; negative means underperforming.',
          'RS = (sector_return - mean_of_all_sectors) / standard_deviation',
          'We compute RS for 1-day and 1-week timeframes to capture both short-term momentum and emerging trends.',
        ],
      },
      {
        title: 'Smart Money Flow Signal',
        text: [
          'Our flow signal combines three factors to detect institutional accumulation/distribution:',
          '1. Price Change — Direction and magnitude of price movement.',
          '2. Volume Ratio — Current volume divided by 20-period average. Above 1.3x = significant.',
          '3. Relative Strength — Whether the sector is leading or lagging.',
          'When a sector shows positive price movement + above-average volume + positive RS → Inflow signal.',
          'When a sector shows negative price + high volume + negative RS → Outflow signal.',
        ],
      },
      {
        title: 'Momentum Score (0–100)',
        text: [
          'A composite score combining both 1-day and 1-week relative strength.',
          '1-week RS is weighted higher (25×) than 1-day RS (15×) to reduce noise.',
          'Score > 60 = strong momentum. Score < 40 = weak momentum. 40–60 = neutral.',
        ],
      },
    ],
  },
  {
    id: 'strategy',
    title: 'Using This Data',
    icon: <BookOpen className="h-4 w-4" />,
    content: [
      '1. Identify the current rotation phase using the phase indicator at the top of the page.',
      '2. Look for sectors with strong RS + high volume + bullish flow signals — these are where smart money is accumulating.',
      '3. Avoid sectors with weak RS + high volume + bearish flow signals — these are being distributed.',
      '4. Use the 1W view to filter out daily noise and identify genuine rotation trends.',
      '5. Remember: sector rotation is a medium-to-long-term strategy. Daily signals are useful for timing, but the real edge comes from identifying the macro phase.',
    ],
  },
];

export function EducationPanel() {
  const [openSection, setOpenSection] = useState<string | null>('what-is');

  const toggle = (id: string) => {
    setOpenSection(openSection === id ? null : id);
  };

  return (
    <div className="rounded-xl border border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border px-5 py-3">
        <BookOpen className="h-4 w-4 text-accent" />
        <h2 className="text-sm font-bold text-text-primary">Learn About Sector Rotation</h2>
      </div>

      <div className="divide-y divide-border">
        {SECTIONS.map((section) => {
          const isOpen = openSection === section.id;

          return (
            <div key={section.id}>
              <button
                onClick={() => toggle(section.id)}
                className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-surface-hover"
              >
                <span className="text-accent">{section.icon}</span>
                <span className="flex-1 text-sm font-semibold text-text-primary">{section.title}</span>
                <ChevronDown className={cn(
                  'h-4 w-4 text-text-muted transition-transform duration-200',
                  isOpen && 'rotate-180'
                )} />
              </button>

              {isOpen && (
                <div className="space-y-4 px-5 pb-5 pt-1">
                  {section.content.map((para, i) => (
                    <p key={i} className="text-sm leading-relaxed text-text-secondary">{para}</p>
                  ))}

                  {section.subsections?.map((sub, i) => (
                    <div key={i} className="space-y-1.5">
                      <h4 className="text-sm font-bold text-text-primary">{sub.title}</h4>
                      {sub.text.map((line, j) => (
                        <p key={j} className="text-sm leading-relaxed text-text-secondary">{line}</p>
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
