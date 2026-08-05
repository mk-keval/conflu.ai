import { useState } from 'react';
import { cn } from '@/lib/cn';
import { ChevronDown, BookOpen, BarChart3, Lightbulb, ArrowRightLeft, AlertTriangle, Zap, Eye } from 'lucide-react';

interface EducationSection {
  id: string;
  title: string;
  icon: React.ReactNode;
  content: string[];
  subsections?: { title: string; text: string[]; highlight?: string }[];
  tip?: string;
}

const SECTIONS: EducationSection[] = [
  {
    id: 'what-is',
    title: 'What is Sector Rotation?',
    icon: <Lightbulb className="h-4 w-4" />,
    content: [
      'Sector rotation is the constant movement of money between different parts of the stock market. Think of it like a party: early on, everyone piles into one room (tech). Later, the crowd moves to another room (energy). By watching where the crowd is going, you can position yourself ahead of the move.',
      'The core insight: NOT all sectors perform well at the same time. Money flows in cycles. Your job isn\'t to predict the future — it\'s to identify which sector has the strongest tailwind RIGHT NOW and ride it.',
    ],
    subsections: [
      {
        title: 'The Economic Cycle — Quick Reference',
        text: [
          '📈 Early Cycle: Economy recovering. Cyclicals lead — Industrials, Consumer Disc., Financials, Tech. Think "rebound mode."',
          '➡️ Mid Cycle: Steady growth. Tech and Comms lead. This is the longest phase — "cruising mode."',
          '⚠️ Late Cycle: Inflation rising, rates going up. Energy and Materials lead. Time to protect gains — "tighten up mode."',
          '🛡️ Recession: Economy shrinking. Defensives win — Utilities, Staples, Health Care. "Survival mode."',
        ],
      },
    ],
    tip: 'The phase label at the top tells you where we are in this cycle. But today\'s price action may differ — the phase uses trailing data to avoid false signals.',
  },
  {
    id: 'how-it-works',
    title: 'Smart Money Flow — Following the Institutions',
    icon: <Eye className="h-4 w-4" />,
    content: [
      'Big money (pension funds, hedge funds) can\'t move in and out of positions overnight. When institutions decide a sector is the place to be, they accumulate over days or weeks — and you can see their footprints in price, volume, and relative strength.',
      'The key tells: When a sector rises on ABOVE-average volume while most other sectors are flat or down, that\'s institutional buying. When it falls on heavy volume while lagging peers, that\'s institutional selling.',
      'Retail noise looks different: low volume, random price moves, no follow-through.',
    ],
    tip: 'Volume is your lie detector. A sector up 3% on normal volume = noise. A sector up 3% on 1.6x average volume = institutions loading up.',
  },
  {
    id: 'key-metrics',
    title: 'Reading the Dashboard — What Each Number Means',
    icon: <BarChart3 className="h-4 w-4" />,
    content: [
      'The heatmap and flows tab give you three key signals. Here\'s how to read them without a finance degree.',
    ],
    subsections: [
      {
        title: 'Relative Strength (RS) — "Who\'s Winning Right Now"',
        text: [
          'RS answers: "Is this sector running faster or slower than everyone else?"',
          '• RS = 0 → moving at average speed (nothing special)',
          '• RS = +1 to +2 → clearly outperforming, worth attention',
          '• RS = +2 or higher → extreme outlier, something BIG is happening',
          '• RS negative → lagging, money is leaving',
          '',
          'Think of it like lap times on a track. If the average sector runs a 60-second lap and XLK runs a 52-second lap, its RS is high — it\'s lapping the field.',
        ],
        highlight: 'RS > 2 on high volume = institutions piling in aggressively. That\'s your signal to pay attention, not to chase blindly.',
      },
      {
        title: 'Volume Ratio — "Is This Real or Just Noise?"',
        text: [
          'Volume tells you if a move has conviction:',
          '• 1.0x = average volume — normal trading day',
          '• 1.3x+ = above average — move has institutional backing',
          '• 1.5x+ = high conviction — significant capital rotating in/out',
          '• Below 0.7x = quiet — retail noise, no follow-through expected',
          '',
          'A sector up 5% on 1.6x volume (like XLK today) is institutions buying. Same 5% move on 0.5x volume would mean nothing — just a thin-market spike.',
        ],
      },
      {
        title: 'Flow Signal — "Is It Inflow or Outflow?"',
        text: [
          'The green/red arrows combine price, volume, and RS into one signal:',
          '',
          '🟢 Inflow (green up arrow): Price up + above-average volume + positive RS = accumulation. Smart money is buying.',
          '🔴 Outflow (red down arrow): Price down + above-average volume + negative RS = distribution. Smart money is selling.',
          '⚪ Neutral: No clear signal. Move is likely noise.',
          '',
          'The pulsing dot means "strong" signal — the conviction is higher.',
        ],
      },
    ],
  },
  {
    id: 'phase-guide',
    title: 'Rotation Phases — What To Do',
    icon: <Zap className="h-4 w-4" />,
    content: [
      'Each phase tells you where we are in the cycle and what historically works. But "works" doesn\'t mean "buy everything in this group" — use it as a filter, not a mandate.',
    ],
    subsections: [
      {
        title: '🟢 Early Cycle — "Bet on Recovery"',
        text: [
          'Leaders: XLF (Financials), XLI (Industrials), XLY (Consumer Disc.), XLK (Tech)',
          'Strategy: Look for breakouts in cyclicals. Reduce defensive positions. The economy is healing and risk-taking is rewarded.',
          'Risk: Don\'t buy everything — only sectors showing RS > 0.5 with rising volume.',
        ],
      },
      {
        title: '🔵 Growth Leading — "Let Winners Run"',
        text: [
          'Leaders: XLK (Tech), XLC (Comms)',
          'Strategy: Ride momentum with trailing stops. The trend is your friend. Use pullbacks to the EMA as entry points.',
          'Risk: Don\'t get greedy — growth phases don\'t last forever. Have an exit plan before you enter.',
        ],
      },
      {
        title: '🟠 Late Cycle — "Protect and Hedge"',
        text: [
          'Leaders: XLE (Energy), XLB (Materials)',
          'Strategy: Add inflation-resistant sectors. Tighten all stops. Start trimming extended positions in growth/tech.',
          'Risk: The hardest phase to trade — rallies fail faster. Consider taking partial profits.',
        ],
      },
      {
        title: '🔴 Defensive Flight — "Survival First"',
        text: [
          'Leaders: XLP (Staples), XLU (Utilities), XLV (Health Care), XLRE (Real Estate)',
          'Strategy: Reduce position sizes. Avoid beaten-down cyclicals. Cash is a valid position.',
          'Risk: Don\'t try to catch falling knives. If tech is getting crushed, don\'t buy the dip — wait for the rotation to exhaust.',
          '',
          '⚠️ IMPORTANT: The app detects this phase using 1-week trailing data. A single strong day (like today\'s tech rally) won\'t immediately flip the label. Switch to 1D view to see today\'s action, and watch for the phase to update in coming days if the rally sustains.',
        ],
      },
    ],
  },
  {
    id: '1d-vs-1w',
    title: '1D vs 1W — Why Both Matter',
    icon: <ArrowRightLeft className="h-4 w-4" />,
    content: [
      'The 1D/1W toggle changes what you see in the heatmap and flows tab, but NOT the rotation phase label.',
    ],
    subsections: [
      {
        title: '1D (Today) — "What\'s Happening Right Now"',
        text: [
          'Best for: Timing entries and exits. Seeing today\'s money flow. Catching intraday shifts.',
          'Use it when: You want to see which sector is hot TODAY. It\'s reactive — captures the current session.',
          'Limitation: One day is noise. A single news event (like MSFT earnings) can distort it.',
        ],
      },
      {
        title: '1W (This Week) — "What\'s Actually Trending"',
        text: [
          'Best for: Confirming real rotations. Filtering out daily noise. Seeing the big picture.',
          'Use it when: You want to know where money has been flowing all week, not just since this morning.',
          'Limitation: Lags behind sudden reversals. A Friday rally won\'t show up until Monday.',
        ],
      },
      {
        title: 'How To Use Both Together',
        text: [
          '1. Check 1W view to see the established trend — this is your "truth."',
          '2. Check 1D view to see if today is confirming or contradicting the trend.',
          '3. If both align (e.g., 1W says tech, 1D says tech) → strong signal. Go with it.',
          '4. If they conflict (e.g., 1W says defensives, 1D says tech) → possible shift. Watch for 2-3 more days of confirmation before acting.',
          '',
          'This is exactly what\'s happening today: 1W says defensives, 1D says tech. A conflict = a potential shift. Watch the next few days.',
        ],
      },
    ],
  },
  {
    id: 'common-pitfalls',
    title: 'Common Mistakes',
    icon: <AlertTriangle className="h-4 w-4" />,
    content: [
      'Learning to read sector flows takes practice. Here are the mistakes almost everyone makes:',
    ],
    subsections: [
      {
        title: '❌ Mistake 1: Buying the First Big Day',
        text: [
          'Today tech is up 5.5%. FOMO kicks in. Slow down.',
          'One day doesn\'t make a trend. Wait for confirmation — a pullback that holds, or a second leg up on volume.',
        ],
      },
      {
        title: '❌ Mistake 2: Ignoring the Timeframe Conflict',
        text: [
          'If 1W says one thing and 1D says another, don\'t pick a side yet. The market is deciding. Wait.',
        ],
      },
      {
        title: '❌ Mistake 3: Fighting the Phase',
        text: [
          'If the phase says "defensive flight" and you keep buying tech dips, you\'re fighting the macro trend. Sometimes you\'ll win (like today), but over time it\'s a losing game.',
          'Better approach: Wait for the phase label itself to change. That\'s your macro buy signal.',
        ],
      },
      {
        title: '❌ Mistake 4: Treating All Inflows Equally',
        text: [
          'RS of 0.3 with 1.1x volume = mild interest. RS of 2.6 with 1.6x volume = institutions going all-in.',
          'The strength matters. Not all green arrows are equal.',
        ],
      },
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
                        line === '' ? <br key={j} /> :
                        <p key={j} className="text-sm leading-relaxed text-text-secondary">{line}</p>
                      ))}
                      {sub.highlight && (
                        <div className="mt-2 rounded-md border border-accent/20 bg-accent/5 px-3 py-2">
                          <p className="text-xs leading-relaxed text-accent">{sub.highlight}</p>
                        </div>
                      )}
                    </div>
                  ))}

                  {section.tip && (
                    <div className="flex items-start gap-2 rounded-md border border-border bg-surface-tertiary/50 px-3 py-2">
                      <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
                      <p className="text-xs leading-relaxed text-text-secondary">{section.tip}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
