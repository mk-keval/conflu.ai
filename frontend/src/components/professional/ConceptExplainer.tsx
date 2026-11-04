import { useState } from 'react';
import {
  Lightbulb,
  TrendingUp,
  Shield,
  BarChart3,
  Brain,
  Clock,
  DollarSign,
  PieChart,
  Target,
  GraduationCap,
  Layers,
} from 'lucide-react';
import { cn } from '@/lib/cn';

// ── Concept Definitions ──

interface ConceptDef {
  label: string;
  icon: React.ReactNode;
  explanation: string;
  example?: string;
}

const CONCEPT_MAP: Record<string, ConceptDef> = {
  'sector-rotation': {
    label: 'Sector Rotation',
    icon: <Layers className="h-4 w-4" />,
    explanation:
      "Sector rotation shows which industries are leading and lagging. Leading sectors tend to continue outperforming. Think of it like fashion trends — what's in style changes over time as money flows between sectors.",
    example:
      "When tech is leading and utilities are lagging, investors are bullish (risk-on). When utilities lead, they're defensive (risk-off).",
  },
  'risk-on': {
    label: 'Risk-On vs Risk-Off',
    icon: <TrendingUp className="h-4 w-4" />,
    explanation:
      "Risk-on means investors are optimistic and buying growth stocks, tech, and small companies. Risk-off means they're scared and buying utilities, bonds, and gold.",
    example:
      'Risk-on: Bitcoin up, tech stocks surging. Risk-off: Gold up, utilities outperforming.',
  },
  'conviction-score': {
    label: 'Conviction Score',
    icon: <Brain className="h-4 w-4" />,
    explanation:
      'Conviction score (1-10) measures how confident the system is in this trade. 7+ = Strong signals aligned. 4-6 = Mixed signals. 1-3 = Weak or conflicting.',
    example:
      'AAPL at conviction 8/10 means technical, fundamental, and sentiment all agree — rare and reliable.',
  },
  regime: {
    label: 'Market Regime',
    icon: <BarChart3 className="h-4 w-4" />,
    explanation:
      'Market regime is the current "personality" of the market — strong uptrend, choppy/ranging, or high volatility. Different strategies work in different regimes.',
    example:
      'In a "strong trend" regime, momentum strategies work. In a "ranging" regime, mean reversion works better.',
  },
  'stop-loss': {
    label: 'Stop Loss',
    icon: <Shield className="h-4 w-4" />,
    explanation:
      'A stop loss is your "emergency exit." If the stock drops below this price, you sell automatically to prevent bigger losses. Essential for protecting your money.',
    example:
      'Buy at $100, set stop at $90. If stock drops to $90, you sell and limit loss to 10%. Without it, you might hold as it drops to $50.',
  },
  'position-sizing': {
    label: 'Position Sizing',
    icon: <DollarSign className="h-4 w-4" />,
    explanation:
      'Position sizing decides how much of your money goes into each stock. The goal: no single loss should hurt your account significantly. 1-2% risk per trade is standard.',
    example:
      'With a $100K account, risking 1.5% per trade means max loss of $1,500 on any single position.',
  },
  diversification: {
    label: 'Diversification',
    icon: <PieChart className="h-4 w-4" />,
    explanation:
      "Don't put all your eggs in one basket. Spread across sectors. If tech crashes, healthcare might be fine. Max 15-20% per sector.",
    example:
      'Instead of buying 5 tech stocks, buy 1 tech + 1 healthcare + 1 energy + 1 finance + 1 consumer.',
  },
  'pre-market': {
    label: 'Pre-Market Trading',
    icon: <Clock className="h-4 w-4" />,
    explanation:
      'Pre-market prices show where a stock trades BEFORE the market opens (4-9:30 AM ET). Big pre-market moves often set the tone for the day.',
    example:
      'If AAPL pre-market is +2% after strong earnings, the stock will likely open higher. If -3%, something is wrong.',
  },
  verdict: {
    label: 'Verdict',
    icon: <Target className="h-4 w-4" />,
    explanation:
      "The verdict is the system's overall opinion: Strong Buy (exceptional setup), Buy (good setup), Watch (wait for confirmation), Avoid (problems found).",
    example:
      'STRONG BUY: All signals aligned, high conviction, clear entry and targets.',
  },
  graduation: {
    label: 'Graduation Path',
    icon: <GraduationCap className="h-4 w-4" />,
    explanation:
      'Professional Mode unlocks features gradually over 90 days. This prevents overwhelm. You start with the basics and progressively access advanced tools.',
    example:
      'Day 1: Morning Brief + Verdict. Day 14: All 21 screens. Day 30: Deep analysis tabs.',
  },
};

function getConcept(concept: string): ConceptDef | undefined {
  return CONCEPT_MAP[concept];
}

function getAllConcepts(): Record<string, ConceptDef> {
  return CONCEPT_MAP;
}

function searchConcepts(
  query: string
): Array<{ key: string; def: ConceptDef }> {
  const q = query.toLowerCase();
  return Object.entries(CONCEPT_MAP)
    .filter(
      ([key, def]) =>
        key.includes(q) ||
        def.label.toLowerCase().includes(q) ||
        def.explanation.toLowerCase().includes(q)
    )
    .map(([key, def]) => ({ key, def }));
}

// ── Component ──

interface ConceptExplainerProps {
  concept: string;
  compact?: boolean;
  className?: string;
}

export function ConceptExplainer({
  concept,
  compact = false,
  className,
}: ConceptExplainerProps) {
  const [open, setOpen] = useState(false);
  const def = getConcept(concept);

  if (!def) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 text-xs text-text-muted',
          className
        )}
      >
        <Lightbulb className="h-3 w-3" />
        Learn more about {concept.replace(/-/g, ' ')}
      </span>
    );
  }

  if (compact) {
    return (
      <span className="relative inline-flex items-center">
        <button
          onClick={() => setOpen(!open)}
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
          className={cn(
            'inline-flex items-center gap-1 text-xs transition-colors',
            'text-text-muted hover:text-accent',
            className
          )}
          aria-label={`Learn about ${def.label}`}
        >
          {def.icon}
          <span>{def.label}</span>
        </button>
        {open && (
          <div
            className={cn(
              'absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2',
              'w-64 rounded-lg border border-border bg-surface p-3 shadow-xl',
              'text-sm text-text-primary backdrop-blur-sm',
              'animate-in fade-in slide-in-from-bottom-1 duration-100'
            )}
          >
            <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-accent">
              {def.label}
            </div>
            <p className="mb-1 text-xs leading-relaxed text-text-primary">
              {def.explanation}
            </p>
            {def.example && (
              <p className="text-2xs mt-1 italic text-text-muted">
                💡 {def.example}
              </p>
            )}
          </div>
        )}
      </span>
    );
  }

  return (
    <div
      className={cn(
        'bg-bg-muted/30 rounded-lg border border-border/50 p-3',
        'animate-in fade-in duration-200',
        className
      )}
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 shrink-0 text-accent">{def.icon}</span>
        <div>
          <div className="mb-0.5 text-xs font-semibold uppercase tracking-wider text-accent">
            {def.label}
          </div>
          <p className="text-sm leading-relaxed text-text-primary">
            {def.explanation}
          </p>
          {def.example && (
            <p className="mt-1.5 text-xs italic text-text-muted">
              💡 {def.example}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Re-export utilities for use by the hook ──
export { getConcept, getAllConcepts, searchConcepts };
export type { ConceptDef };
