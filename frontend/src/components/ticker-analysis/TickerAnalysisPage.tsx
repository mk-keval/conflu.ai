import { useState } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { 
  fetchTickerAnalysis, 
  fetchOptionsChain, 
  fetchNews,
  type OptionsChainResponse,
  type NewsResponse,
} from '@/api/tickerAnalysis';
import type { TickerAnalysisResponse, TechnicalAnalysis } from '@/types/tickerAnalysis';
import { cn } from '@/lib/cn';
import { formatPrice, formatPct, formatLargeNumber } from '@/lib/format';
import {
  TrendingUp, Activity, DollarSign, AlertTriangle,
  Shield, Info, Brain, BookOpen,
  ArrowUp, ArrowDown, Minus, ChevronDown, ChevronUp, HelpCircle,
  FileText, Newspaper, BarChart2, Search,
  Loader2, ExternalLink,
} from 'lucide-react';
import type { MetricLesson, ModuleLesson } from './education';
import {
  TECHNICAL_LESSONS, FUNDAMENTAL_LESSONS, EARNINGS_LESSONS,
  SENTIMENT_LESSONS, RISK_LESSONS, MODULE_LESSONS,
  verdictWalkthrough, GLOSSARY,
} from './education';

// ── Helpers ──

type ScoreLabel = 'poor' | 'weak' | 'neutral' | 'good' | 'strong';
function scoreLabel(s: number): ScoreLabel {
  if (s < -0.4) return 'poor';
  if (s < -0.1) return 'weak';
  if (s < 0.3) return 'neutral';
  if (s < 0.6) return 'good';
  return 'strong';
}

const SCORE_COLORS: Record<ScoreLabel, string> = {
  poor: 'bg-loss text-white',
  weak: 'bg-loss/60 text-white',
  neutral: 'bg-text-muted text-white',
  good: 'bg-gain/70 text-white',
  strong: 'bg-gain text-white',
};

function ScoreBar({ score }: { score: number }) {
  const clamped = Math.max(-1, Math.min(1, score));
  const pct = ((clamped + 1) / 2) * 100;
  const color = clamped >= 0.3 ? 'bg-gain' : clamped >= -0.1 ? 'bg-text-muted' : 'bg-loss';
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 rounded-full bg-surface-hover overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono text-text-secondary w-10 text-right">
        {score >= 0 ? '+' : ''}{score.toFixed(2)}
      </span>
    </div>
  );
}

function FindingList({ items, max = 5 }: { items: string[]; max?: number }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? items : items.slice(0, max);
  return (
    <ul className="space-y-1">
      {visible.map((f, i) => (
        <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
          <span className="text-text-muted mt-0.5 shrink-0">&bull;</span>
          <span>{f}</span>
        </li>
      ))}
      {items.length > max && (
        <li>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-accent hover:text-accent/80 transition-colors cursor-pointer"
          >
            {expanded
              ? 'Show less'
              : `+${items.length - max} more findings`}
          </button>
        </li>
      )}
    </ul>
  );
}

// ── Verdict Banner ──

interface VerdictConfig {
  label: string;
  bg: string;
  border: string;
  text: string;
  icon: React.ReactNode;
}
const VERDICT_MAP: Record<string, VerdictConfig> = {
  STRONG_BUY: {
    label: 'STRONG BUY',
    bg: 'bg-gain/20',
    border: 'border-gain/50',
    text: 'text-gain',
    icon: <ArrowUp className="w-8 h-8" />,
  },
  BUY: {
    label: 'BUY',
    bg: 'bg-gain/10',
    border: 'border-gain',
    text: 'text-gain',
    icon: <ArrowUp className="w-8 h-8" />,
  },
  ACCUMULATE: {
    label: 'ACCUMULATE',
    bg: 'bg-gain/10',
    border: 'border-gain',
    text: 'text-gain',
    icon: <ArrowUp className="w-8 h-8" />,
  },
  WATCH: {
    label: 'WATCH',
    bg: 'bg-warning/10',
    border: 'border-warning',
    text: 'text-warning',
    icon: <Activity className="w-8 h-8" />,
  },
  HOLD: {
    label: 'HOLD',
    bg: 'bg-text-muted/10',
    border: 'border-text-muted',
    text: 'text-text-secondary',
    icon: <Minus className="w-8 h-8" />,
  },
  AVOID: {
    label: 'AVOID',
    bg: 'bg-loss/10',
    border: 'border-loss',
    text: 'text-loss',
    icon: <ArrowDown className="w-8 h-8" />,
  },
  SELL: {
    label: 'SELL',
    bg: 'bg-loss/10',
    border: 'border-loss',
    text: 'text-loss',
    icon: <ArrowDown className="w-8 h-8" />,
  },
};

function verdictConfig(action: string): VerdictConfig {
  // Handle "WATCH — positive bias" etc.
  const base = action.split('—')[0].trim();
  return VERDICT_MAP[base] ?? VERDICT_MAP.WATCH;
}

function ConvictionRing({ conviction, weightedScore }: { conviction: number; weightedScore?: number }) {
  const clamped = Math.max(1, Math.min(10, conviction));
  const pct = clamped / 10;
  const circumference = 2 * Math.PI * 16;
  const offset = circumference * (1 - pct);
  const color = conviction >= 7 ? '#22c55e' : conviction >= 4 ? '#eab308' : '#ef4444';
  const [open, setOpen] = useState(false);

  const getConvictionExplanation = () => {
    if (conviction >= 7) {
      return {
        title: "High Conviction (7-10)",
        meaning: "Strong alignment across multiple analysis modules. Technical, fundamental, earnings, sentiment, and risk signals all point in the same direction.",
        action: "Consider position sizing at upper end of risk limits. High conviction setups warrant larger positions.",
      };
    } else if (conviction >= 4) {
      return {
        title: "Moderate Conviction (4-6)",
        meaning: "Mixed signals — some modules bullish, others neutral or slightly bearish. Not a clear-cut setup but has merit.",
        action: "Size position conservatively. Wait for confirming price action or additional catalysts before committing full size.",
      };
    } else {
      return {
        title: "Low Conviction (1-3)",
        meaning: "Conflicting signals or weak overall score. Analysis modules disagree significantly, or most factors are neutral/negative.",
        action: "Avoid or position very small (≤1-2%). Treat as watchlist candidate only — wait for clearer setup.",
      };
    }
  };

  const explanation = getConvictionExplanation();

  return (
    <div className="flex items-center gap-1.5">
      <div className="relative" title="Click for conviction explanation" onClick={() => setOpen(!open)}>
        <svg width="40" height="40" viewBox="0 0 40 40" className="shrink-0 cursor-pointer">
          <circle cx="20" cy="20" r="16" fill="none" stroke="currentColor" strokeWidth="3" className="text-surface-hover" />
          <circle cx="20" cy="20" r="16" fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"
            strokeDasharray={circumference} strokeDashoffset={offset} transform="rotate(-90 20 20)"
            className="transition-all duration-500"
          />
          <text x="20" y="20" textAnchor="middle" dominantBaseline="central" fontSize="10" fontWeight="bold" fill="currentColor" className="text-text-primary">
            {conviction}
          </text>
        </svg>
      </div>
      {open && (
        <div className="absolute z-10 ml-2 bg-background border border-accent/20 rounded-lg p-3 text-xs min-w-[220px] animate-in slide-in-from-top-1 duration-150 shadow-lg">
          <div className="font-semibold text-accent mb-1.5">{explanation.title}</div>
          <div className="text-text-secondary mb-2 leading-relaxed">{explanation.meaning}</div>
          <div className="pt-2 border-t border-border/30">
            <div className="font-semibold text-text-primary mb-0.5">Action:</div>
            <div className="text-text-secondary leading-relaxed">{explanation.action}</div>
          </div>
          {weightedScore !== undefined && (
            <div className="mt-2 pt-2 border-t border-border/30">
              <div className="font-semibold text-text-primary mb-0.5">Weighted Score:</div>
              <div className="text-text-secondary font-mono">
                {weightedScore >= 0 ? '+' : ''}{weightedScore.toFixed(2)} (range: -1.0 to +1.0)
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function VerdictBanner({ data, weightedScore }: { data: TickerAnalysisResponse; weightedScore?: number }) {
  const v = data.verdict;
  const cfg = verdictConfig(v.action);
  const changeStr = data.change_pct != null ? formatPct(data.change_pct) : null;
  const isPositive = data.change_pct != null && data.change_pct >= 0;

  return (
    <div className={cn('border rounded-lg p-5', cfg.bg, cfg.border)}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div className={cn('p-2 rounded-full', cfg.bg)}>{cfg.icon}</div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-text-primary">{data.symbol}</h1>
              <span className={cn('text-xl font-semibold', isPositive ? 'text-gain' : 'text-loss')}>
                {data.price != null ? formatPrice(data.price) : '—'}
              </span>
              {changeStr && (
                <span className={cn('text-sm font-medium', isPositive ? 'text-gain' : 'text-loss')}>
                  {changeStr}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 mt-1">
              <span className={cn('text-lg font-bold', cfg.text)}>
                {cfg.label}
              </span>
              <div className="flex items-center gap-1.5 text-sm text-text-muted">
                <ConvictionRing conviction={v.conviction} weightedScore={weightedScore} />
              </div>
              {data.sector && (
                <span className="text-sm text-text-muted">{data.sector}</span>
              )}
            </div>
          </div>
        </div>
        <span className="text-xs text-text-muted">{data.execution_ms}ms</span>
        {data.data_age_hours != null && (
          <span className={cn(
            'text-xs ml-3',
            data.data_age_hours > 24 ? 'text-loss' : 'text-text-muted'
          )}>
            Data: {data.data_age_hours < 1 ? '<1h' : `${data.data_age_hours.toFixed(0)}h`} ago
            {data.data_age_hours > 24 && ' ⚠️ Stale'}
          </span>
        )}
      </div>

      {/* Thesis */}
      {v.thesis && (
        <p className="mt-4 text-sm text-text-secondary leading-relaxed">{v.thesis}</p>
      )}

      {/* Entry/Stop/Targets */}
      <div className="mt-4 grid grid-cols-4 gap-4">
        <KeyLevel label="Entry Zone" value={
          v.entry_zone_low != null && v.entry_zone_high != null
            ? `${formatPrice(v.entry_zone_low)} – ${formatPrice(v.entry_zone_high)}`
            : 'N/A'
        } note={v.entry_zone_low == null && v.entry_zone_high == null ? 'Binary outcome stock — no technical entry zones. Position on catalyst confirmation.' : undefined} />
        <KeyLevel label="Stop Loss" value={v.stop_loss != null ? formatPrice(v.stop_loss) : 'N/A'} note={v.stop_loss == null ? 'Binary outcome stock — stop set at portfolio risk limit.' : undefined} />
        <KeyLevel label="Targets" value={
          v.targets.length > 0 ? v.targets.map((t) => formatPrice(t)).join(', ') : 'N/A'
        } note={v.targets.length === 0 ? 'Binary outcome stock — targets depend on milestone outcomes.' : undefined} />
        <KeyLevel label="Risk/Reward" value={v.risk_reward != null ? `${v.risk_reward.toFixed(1)}:1` : 'N/A'} note={v.risk_reward == null ? 'Binary outcome stock — R:R varies by scenario.' : undefined} />
      </div>

      {/* Data Source Attribution */}
      <DataSourceAttribution data={data} />
    </div>
  );
}

function KeyLevel({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="bg-surface/50 rounded px-3 py-2">
      <div className="text-xs text-text-muted mb-0.5 flex items-center gap-1">
        {label}
        {note && (
          <span className="text-text-muted hover:text-text-primary cursor-help underline underline-dotted" title={note}>
            (?)
          </span>
        )}
      </div>
      <div className="text-sm font-mono font-semibold text-text-primary">{value}</div>
    </div>
  );
}

function DataSourceAttribution({ data }: { data: TickerAnalysisResponse }) {
  const sources = data.data_sources;
  if (!sources) return null;
  
  const ageHours = data.data_age_hours;
  const freshnessLabel = ageHours != null 
    ? (ageHours < 1 ? '<1h' : ageHours > 24 ? `${ageHours.toFixed(0)}h ⚠️ Stale` : `${ageHours.toFixed(0)}h`)
    : 'Unknown';
  
  const sourceItems = [
    { label: 'Technical (Daily)', value: sources.technical_daily, icon: <TrendingUp className="w-3 h-3" />, freshness: freshnessLabel },
    { label: 'Technical (Weekly)', value: sources.technical_weekly, icon: <TrendingUp className="w-3 h-3" />, freshness: freshnessLabel },
    { label: 'Fundamental', value: sources.fundamental, icon: <DollarSign className="w-3 h-3" />, freshness: freshnessLabel },
    { label: 'Earnings', value: sources.earnings, icon: <Activity className="w-3 h-3" />, freshness: freshnessLabel },
    { label: 'Sentiment', value: sources.sentiment, icon: <Activity className="w-3 h-3" />, freshness: freshnessLabel },
  ].filter(item => item.value);

  return (
    <div className="mt-4 p-3 bg-surface/30 border border-border/30 rounded-lg">
      <div className="text-xs font-semibold text-text-primary uppercase tracking-wider mb-2">Data Sources & Freshness</div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-2 text-xs">
        {sourceItems.map((item, i) => (
          <div key={i} className="flex flex-col gap-0.5 text-text-secondary">
            <div className="flex items-center gap-1.5">
              <span className="text-accent">{item.icon}</span>
              <span className="font-medium text-text-primary">{item.label}</span>
            </div>
            <div className="flex items-center gap-1.5 ml-5">
              <span className="font-mono text-text-secondary">{item.value}</span>
              <span className="text-text-muted">({item.freshness})</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Tab Panel ──

function TabButton({
  active, label, icon, onClick,
}: {
  active: boolean; label: string; icon: React.ReactNode; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors',
        active ? 'bg-accent/10 text-accent border border-accent/20' : 'text-text-muted hover:text-text-primary hover:bg-surface-hover',
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

// ── Module Cards ──

function VerdictTab({ data, explain }: { data: TickerAnalysisResponse; explain: boolean }) {
  const v = data.verdict;
  const [walkthroughOpen, setWalkthroughOpen] = useState(false);
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  // Handle both old format (TechnicalAnalysis) and new format (MultiTimeframeTechnical)
  const getTechnicalScore = (tech: any) => {
    if (!tech) return 0;
    return tech.daily?.score ?? tech.score ?? 0;
  };
  const moduleScores = [
    { label: 'Technical', score: getTechnicalScore(data.technical) },
    { label: 'Fundamentals', score: data.fundamental?.score ?? 0 },
    { label: 'Earnings', score: data.earnings?.score ?? 0 },
    { label: 'Sentiment', score: data.sentiment?.score ?? 0 },
    { label: 'Risk', score: data.risk?.score ?? 0 },
  ];
  const steps = explain ? verdictWalkthrough(v.action, v.conviction, moduleScores, v.key_red_flags) : [];

  const positiveCount = moduleScores.filter(m => m.score > 0).length;
  const negativeCount = moduleScores.filter(m => m.score < 0).length;

  return (
    <div className="space-y-5">
      {/* Module Scores Overview */}
      <div className="bg-surface/30 border border-border/30 rounded-lg p-4">
        <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wider mb-3">Module Scores</h3>
        <div className="grid grid-cols-5 gap-2">
          {moduleScores.map((m) => (
            <div key={m.label} className="text-center">
              <div className="text-[10px] text-text-muted uppercase tracking-wide truncate">{m.label}</div>
              <div className={cn(
                'text-sm font-mono font-semibold mt-0.5',
                m.score >= 0.3 ? 'text-gain' : m.score <= -0.3 ? 'text-loss' : 'text-text-muted',
              )}>
                {m.score >= 0 ? '+' : ''}{m.score.toFixed(2)}
              </div>
              <div className="mt-1 h-1.5 w-full bg-surface-hover rounded-full overflow-hidden">
                <div className={cn(
                  'h-full rounded-full transition-all',
                  m.score >= 0.3 ? 'bg-gain' : m.score >= -0.1 ? 'bg-text-muted' : 'bg-loss',
                )} style={{ width: `${((m.score + 1) / 2) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
        {explain && (
          <p className="text-xs text-text-muted mt-2">
            {positiveCount >= 4 ? 'Most modules are positive — strong overall alignment.' :
             positiveCount >= 3 ? 'More bullish signals than bearish, but mixed.' :
             negativeCount >= 3 ? 'More bearish signals — caution warranted.' :
             'Mixed signals across modules — look for confirming evidence.'}
          </p>
        )}
      </div>

      {/* Triggers */}
      {v.buy_triggers.length > 0 && (
        <div className="bg-surface/50 border border-gain/20 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gain mb-2 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" /> Buy Triggers
          </h3>
          <FindingList items={v.buy_triggers} />
        </div>
      )}
      {v.sell_triggers.length > 0 && (
        <div className="bg-surface/50 border border-loss/20 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-loss mb-2 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" /> Sell Triggers
          </h3>
          <FindingList items={v.sell_triggers} />
        </div>
      )}
      {/* Red Flags */}
      {v.key_red_flags.length > 0 && (
        <div className="bg-surface/50 border border-warning/20 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-warning mb-2 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> Red Flags
          </h3>
          <FindingList items={v.key_red_flags} />
        </div>
      )}
      {v.thesis && (
        <div className="bg-surface/50 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-2 flex items-center gap-2">
            <Info className="w-4 h-4" /> Detailed Analysis
          </h3>
          <p className="text-sm text-text-secondary leading-relaxed">{v.thesis}</p>
        </div>
      )}
      {v.position_size_pct > 0 && (
        <div className="bg-surface/50 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-2 flex items-center gap-2">
            <Shield className="w-4 h-4" /> Position Sizing
          </h3>
          <p className="text-sm text-text-secondary">
            Suggested position size: <span className="font-mono font-semibold text-text-primary">{v.position_size_pct}%</span> of portfolio
          </p>
        </div>
      )}

      {/* Trade Plan Panel */}
      {v.trade_plan && (
        <div className="bg-surface/50 rounded-lg p-4 border border-accent/20">
          <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
            <Shield className="w-4 h-4" /> Trade Plan
          </h3>
          <div className="space-y-4 text-sm">
            {/* Scale In */}
            {v.trade_plan.scale_in && v.trade_plan.scale_in.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-semibold text-text-primary flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-gain" /> Scale In
                </h4>
                <div className="space-y-1 ml-4">
                  {v.trade_plan.scale_in.map((step: any, i: number) => (
                    <div key={i} className="text-sm text-text-secondary flex items-center gap-2">
                      <span className="font-mono text-text-primary">{formatPrice(step.price)}</span>
                      <span className="text-text-muted">({step.size_pct}% of portfolio)</span>
                      <span className="text-text-muted">— {step.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Scale Out */}
            {v.trade_plan.scale_out && v.trade_plan.scale_out.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-semibold text-text-primary flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-gain" /> Scale Out (Partial Profits)
                </h4>
                <div className="space-y-1 ml-4">
                  {v.trade_plan.scale_out.map((step: any, i: number) => (
                    <div key={i} className="text-sm text-text-secondary flex items-center gap-2">
                      <span className="font-mono text-text-primary">{step.r_multiple}R</span>
                      <span className="text-text-muted">({step.size_pct}% of position)</span>
                      <span className="text-text-muted">— {step.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Trailing Stop */}
            {v.trade_plan.trail_type && (
              <div className="space-y-2">
                <h4 className="font-semibold text-text-primary flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-warning" /> Trailing Stop
                </h4>
                <div className="ml-4 space-y-1 text-sm">
                  <div className="text-text-secondary">
                    Type: <span className="font-mono text-text-primary capitalize">{v.trade_plan.trail_type}</span>
                    {v.trade_plan.trail_type === 'atr' && (
                      <span className="text-text-muted"> — {v.trade_plan.trail_value}x ATR</span>
                    )}
                    {v.trade_plan.trail_type === 'structure' && (
                      <span className="text-text-muted"> — trail below structure</span>
                    )}
                    {v.trade_plan.trail_type === 'percent' && (
                      <span className="text-text-muted"> — {v.trade_plan.trail_value}%</span>
                    )}
                  </div>
                  <div className="text-text-secondary">
                    Activate after: <span className="font-mono text-text-primary">{v.trade_plan.trail_activation_r}R</span>
                  </div>
                  <div className="text-text-secondary">
                    Move to breakeven at: <span className="font-mono text-text-primary">{v.trade_plan.move_to_breakeven_at_r}R</span>
                  </div>
                </div>
              </div>
            )}
            
            {/* Time Stop */}
            {v.trade_plan.max_hold_days && (
              <div className="space-y-2">
                <h4 className="font-semibold text-text-primary flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-warning" /> Time Stop
                </h4>
                <div className="ml-4 text-sm text-text-secondary">
                  Maximum hold: <span className="font-mono text-text-primary">{v.trade_plan.max_hold_days} days</span>
                </div>
              </div>
            )}
            
            {/* Risk Limits */}
            <div className="space-y-2 pt-2 border-t border-border/30">
              <h4 className="font-semibold text-text-primary flex items-center gap-2">
                <Shield className="w-4 h-4" /> Risk Limits
              </h4>
              <div className="ml-4 space-y-1 text-sm text-text-secondary">
                <div>Max position: <span className="font-mono text-text-primary">{v.trade_plan.max_position_pct}%</span></div>
                <div>Daily loss limit: <span className="font-mono text-text-primary">{v.trade_plan.daily_loss_limit_pct}%</span></div>
              </div>
            </div>
            
            {/* Notes */}
            {v.trade_plan.notes && v.trade_plan.notes.length > 0 && (
              <div className="space-y-1 pt-2 border-t border-border/30">
                <h4 className="font-semibold text-text-primary flex items-center gap-2">
                  <BookOpen className="w-4 h-4" /> Notes
                </h4>
                <ul className="ml-4 space-y-1 text-sm text-text-secondary list-disc">
                  {v.trade_plan.notes.map((note: string, i: number) => (
                    <li key={i}>{note}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Verdict Walkthrough */}
      {explain && steps.length > 0 && (
        <>
          <button
            onClick={() => setWalkthroughOpen(!walkthroughOpen)}
            className="flex items-center gap-2 text-sm text-accent hover:text-accent/80 transition-colors"
          >
            <BookOpen className="w-4 h-4" />
            <span>{walkthroughOpen ? 'Hide' : 'Show'} step-by-step reasoning</span>
            {walkthroughOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {walkthroughOpen && (
            <div className="space-y-3 animate-in slide-in-from-top-1 duration-150">
              {steps.map((step, i) => (
                <div key={i} className="bg-background/60 border border-border/30 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="flex items-center justify-center w-5 h-5 rounded-full bg-accent/20 text-accent text-xs font-bold">{i + 1}</span>
                    <span className="text-xs font-semibold text-text-primary">{step.module}</span>
                    <span className="text-xs text-text-muted">Score: {step.score}</span>
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed">{step.explanation}</p>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Glossary */}
      {explain && (
        <>
          <button
            onClick={() => setGlossaryOpen(!glossaryOpen)}
            className="flex items-center gap-2 text-sm text-accent hover:text-accent/80 transition-colors"
          >
            <BookOpen className="w-4 h-4" />
            <span>{glossaryOpen ? 'Hide' : 'View'} trading terms glossary</span>
            {glossaryOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {glossaryOpen && (
            <div className="grid gap-2 animate-in slide-in-from-top-1 duration-150">
              {GLOSSARY.map((entry, i) => (
                <div key={i} className="bg-background/60 border border-border/30 rounded-lg p-3">
                  <div className="text-xs font-semibold text-text-primary">{entry.term}</div>
                  <div className="text-xs text-text-secondary leading-relaxed mt-0.5">{entry.definition}</div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ScoreCard({
  title, icon, score, findings, lesson,
}: {
  title: string; icon: React.ReactNode; score: number; findings: string[]; lesson?: ModuleLesson;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-surface/50 border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
          {icon} {title}
        </h3>
        <span className={cn(
          'text-xs font-bold px-2 py-0.5 rounded-full',
          SCORE_COLORS[scoreLabel(score)],
        )}>
          {score >= 0 ? '+' : ''}{score.toFixed(2)}
        </span>
      </div>
      <ScoreBar score={score} />
      <div className="mt-3">
        <FindingList items={findings} />
      </div>
      {lesson && (
        <>
          <button
            onClick={() => setOpen(!open)}
            className="mt-3 flex items-center gap-1.5 text-xs text-accent hover:text-accent/80 transition-colors"
          >
            <Brain className="w-3.5 h-3.5" />
            <span>{open ? 'Hide' : 'How does this analysis work?'}</span>
            {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
          {open && (
            <div className="mt-2 bg-background/80 border border-accent/10 rounded-lg p-3 text-xs space-y-2.5 animate-in slide-in-from-top-1 duration-150">
              <div>
                <div className="font-semibold text-accent mb-0.5">What is {title} Analysis?</div>
                <p className="text-text-secondary leading-relaxed">{lesson.whatItIs}</p>
              </div>
              <div>
                <div className="font-semibold text-accent mb-0.5">Why does it matter?</div>
                <p className="text-text-secondary leading-relaxed">{lesson.whyItMatters}</p>
              </div>
              <div>
                <div className="font-semibold text-accent mb-0.5">How we calculated this score</div>
                <p className="text-text-secondary leading-relaxed">{lesson.howScoreWorks}</p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SectionCard({ title, icon, children, explain, description }: {
  title: string; icon: React.ReactNode; children: React.ReactNode; explain?: boolean; description?: string;
}) {
  return (
    <div className="bg-surface/10 border border-border/30 rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 bg-surface/20 border-b border-border/20">
        <span className="text-accent">{icon}</span>
        <span className="text-xs font-semibold text-text-primary uppercase tracking-wider">{title}</span>
      </div>
      {explain && description && (
        <div className="px-3 py-2 text-xs text-text-muted border-b border-border/10 leading-relaxed">
          {description}
        </div>
      )}
      <div className="p-3">
        {children}
      </div>
    </div>
  );
}

function TechnicalDetail({ data, explain }: { data: NonNullable<TickerAnalysisResponse['technical']>; explain: boolean }) {
  // Handle both old format (direct TechnicalAnalysis) and new format (MultiTimeframeTechnical)
  const isMulti = data && 'daily' in data;
  const daily = isMulti ? data.daily : data;
  const weekly = isMulti ? data.weekly : null;

  const renderTimeframe = (tf: TechnicalAnalysis, label: string) => (
    <div className="space-y-4 border-l-2 border-accent/20 pl-4">
      <h4 className="text-sm font-semibold text-text-primary flex items-center gap-2">
        <span className="px-2 py-0.5 bg-accent/10 rounded text-xs font-mono">{label}</span>
        <span className="text-xs text-text-muted">({tf.score >= 0.3 ? 'Bullish' : tf.score <= -0.3 ? 'Bearish' : 'Neutral'} • {tf.score >= 0 ? '+' : ''}{tf.score.toFixed(2)})</span>
      </h4>
      
      {/* Trend Section */}
      <SectionCard title="Trend" icon={<TrendingUp className="w-3.5 h-3.5" />} explain={explain}
        description="Moving Average alignment tells you the direction of the trend. ADX measures how strong that trend is — higher values = stronger trend."
      >
        <div className="grid grid-cols-2 gap-3">
          <MetricBox label="MA Alignment" value={tf.ma_alignment} explainer={explain ? { lesson: TECHNICAL_LESSONS.ma_alignment, rawValue: tf.ma_alignment } : undefined} />
          <MetricBox label="ADX" value={tf.adx != null ? `${tf.adx.toFixed(1)} (${tf.adx_verdict})` : '—'} explainer={explain ? { lesson: TECHNICAL_LESSONS.adx, rawValue: `${tf.adx?.toFixed(1) ?? ''} (${tf.adx_verdict})` } : undefined} />
        </div>
      </SectionCard>

      {/* Momentum Section */}
      <SectionCard title="Momentum" icon={<Activity className="w-3.5 h-3.5" />} explain={explain}
        description="Momentum measures the speed of price changes. RSI shows if the stock is overbought or oversold. MACD tracks whether buying or selling pressure is building."
      >
        <div className="grid grid-cols-2 gap-3">
          <MetricBox label="RSI" value={tf.rsi != null ? `${tf.rsi.toFixed(1)} (${tf.rsi_regime})` : '—'} explainer={explain ? { lesson: TECHNICAL_LESSONS.rsi, rawValue: `${tf.rsi?.toFixed(1) ?? ''} (${tf.rsi_regime})` } : undefined} />
          <MetricBox label="MACD" value={tf.macd_status ?? '—'} explainer={explain ? { lesson: TECHNICAL_LESSONS.macd_status, rawValue: tf.macd_status ?? '' } : undefined} />
        </div>
      </SectionCard>

      {/* Volume Section */}
      <SectionCard title="Volume" icon={<Activity className="w-3.5 h-3.5" />} explain={explain}
        description="Volume tells you how much interest there is in the stock. High volume confirms price moves are real. Low volume moves are unreliable — they can reverse quickly."
      >
        <div className="grid grid-cols-1 gap-3">
          <MetricBox label="Volume Ratio" value={tf.volume_ratio != null ? `${tf.volume_ratio.toFixed(2)}x` : '—'} explainer={explain ? { lesson: TECHNICAL_LESSONS.volume_ratio, rawValue: tf.volume_ratio?.toFixed(2) ?? '' } : undefined} />
        </div>
      </SectionCard>

      {/* Volatility Section */}
      <SectionCard title="Volatility" icon={<AlertTriangle className="w-3.5 h-3.5" />} explain={explain}
        description="Volatility measures how much the stock price swings. ATR tells you the average daily range. Bollinger Bands show if the price is at an extreme relative to recent movement."
      >
        <div className="grid grid-cols-2 gap-3">
          <MetricBox label="ATR" value={tf.atr_pct != null ? `${tf.atr_pct.toFixed(1)}% (${tf.volatility_regime})` : '—'} explainer={explain ? { lesson: TECHNICAL_LESSONS.atr_pct, rawValue: `${tf.atr_pct?.toFixed(1) ?? ''}% (${tf.volatility_regime})` } : undefined} />
          <MetricBox label="BB Position" value={tf.bb_position ?? '—'} explainer={explain ? { lesson: TECHNICAL_LESSONS.bb_position, rawValue: tf.bb_position ?? '' } : undefined} />
        </div>
      </SectionCard>
      
      {/* Key Findings */}
      <div className="mt-3">
        <FindingList items={tf.findings} max={5} />
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      {explain && (
        <div className="bg-accent/5 border border-accent/10 rounded-lg p-3 text-sm text-text-secondary leading-relaxed">
          <strong className="text-text-primary">Multi-Timeframe Analysis:</strong> Professional traders analyze multiple timeframes. 
          <strong>Weekly</strong> shows the primary trend and major support/resistance — the "big picture." 
          <strong>Daily</strong> shows entry timing, pullback structure, and volume confirmation. 
          Both should align for highest conviction setups. Weekly bullish + Daily pullback = ideal entry.
        </div>
      )}
      
      <ScoreCard title="Technical Analysis (Multi-Timeframe)" icon={<TrendingUp className="w-4 h-4" />} score={daily.score} findings={daily.findings} lesson={explain ? MODULE_LESSONS.technical : undefined} />
      
      <div className="grid md:grid-cols-2 gap-4">
        {renderTimeframe(daily, 'Daily')}
        {weekly && renderTimeframe(weekly, 'Weekly')}
      </div>
    </div>
  );
}

function FundamentalDetail({ data, explain }: { data: NonNullable<TickerAnalysisResponse['fundamental']>; explain: boolean }) {
  return (
    <div className="space-y-4">
      {explain && (
        <div className="bg-accent/5 border border-accent/10 rounded-lg p-3 text-sm text-text-secondary leading-relaxed">
          <strong className="text-text-primary">What to look for:</strong> A quality company grows revenue, earns strong profit margins, keeps debt manageable, and generates cash. Low P/E + high growth is the sweet spot. Consistent ROE above 15% signals competitive advantage.
        </div>
      )}
      <ScoreCard title="Fundamentals" icon={<DollarSign className="w-4 h-4" />} score={data.score} findings={data.findings} lesson={explain ? MODULE_LESSONS.fundamental : undefined} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricBox label="Market Cap" value={data.market_cap != null ? formatLargeNumber(data.market_cap) : '—'} explainer={explain ? { lesson: FUNDAMENTAL_LESSONS.market_cap, rawValue: formatLargeNumber(data.market_cap ?? 0) } : undefined} />
        <MetricBox label="P/E Ratio" value={data.pe_ratio != null ? data.pe_ratio.toFixed(2) : '—'} explainer={explain ? { lesson: FUNDAMENTAL_LESSONS.pe_ratio, rawValue: data.pe_ratio?.toFixed(2) ?? '—' } : undefined} />
        <MetricBox label="EPS" value={data.eps != null ? `$${data.eps.toFixed(2)}` : '—'} explainer={explain ? { lesson: FUNDAMENTAL_LESSONS.eps, rawValue: data.eps?.toFixed(2) ?? '—' } : undefined} />
        <MetricBox label="Profit Margin" value={data.profit_margin != null ? `${data.profit_margin.toFixed(1)}%` : '—'} explainer={explain ? { lesson: FUNDAMENTAL_LESSONS.profit_margin, rawValue: data.profit_margin?.toFixed(1) ?? '' } : undefined} />
        <MetricBox label="D/E Ratio" value={data.debt_to_equity != null ? data.debt_to_equity.toFixed(2) : '—'} explainer={explain ? { lesson: FUNDAMENTAL_LESSONS.debt_to_equity, rawValue: data.debt_to_equity?.toFixed(2) ?? '' } : undefined} />
        <MetricBox label="Revenue Growth" value={data.revenue_growth_yoy != null ? `${data.revenue_growth_yoy.toFixed(1)}%` : '—'} explainer={explain ? { lesson: FUNDAMENTAL_LESSONS.revenue_growth_yoy, rawValue: data.revenue_growth_yoy != null ? `${data.revenue_growth_yoy.toFixed(1)}%` : '' } : undefined} />
        <MetricBox label="FCF Yield" value={data.fcf_yield != null ? `${data.fcf_yield.toFixed(1)}%` : '—'} explainer={explain ? { lesson: FUNDAMENTAL_LESSONS.fcf_yield, rawValue: data.fcf_yield != null ? `${data.fcf_yield.toFixed(1)}%` : '' } : undefined} />
        <MetricBox label="Div Yield" value={data.dividend_yield != null ? `${data.dividend_yield.toFixed(2)}%` : '—'} explainer={explain ? { lesson: FUNDAMENTAL_LESSONS.dividend_yield, rawValue: data.dividend_yield != null ? `${data.dividend_yield.toFixed(2)}%` : '' } : undefined} />
        <MetricBox label="ROE" value={data.return_on_equity != null ? `${data.return_on_equity.toFixed(1)}%` : '—'} explainer={explain ? { lesson: FUNDAMENTAL_LESSONS.return_on_equity, rawValue: data.return_on_equity?.toFixed(1) ?? '' } : undefined} />
        <MetricBox label="P/B Ratio" value={data.price_to_book != null ? data.price_to_book.toFixed(2) : '—'} explainer={explain ? { lesson: FUNDAMENTAL_LESSONS.price_to_book, rawValue: data.price_to_book?.toFixed(2) ?? '' } : undefined} />
        <MetricBox label="Op. Margin" value={data.operating_margin != null ? `${data.operating_margin.toFixed(1)}%` : '—'} explainer={explain ? { lesson: FUNDAMENTAL_LESSONS.operating_margin, rawValue: data.operating_margin?.toFixed(1) ?? '' } : undefined} />
      </div>
    </div>
  );
}

function EarningsDetail({ data, explain }: { data: NonNullable<TickerAnalysisResponse['earnings']>; explain: boolean }) {
  return (
    <div className="space-y-4">
      {explain && (
        <div className="bg-accent/5 border border-accent/10 rounded-lg p-3 text-sm text-text-secondary leading-relaxed">
          <strong className="text-text-primary">What to look for:</strong> Consistent earnings beats (high beat rate) and double-digit surprise percentages signal a company that's outperforming expectations. Watch out for upcoming earnings dates within 2 weeks — stocks tend to drift before reports.
        </div>
      )}
      <ScoreCard title="Earnings" icon={<Activity className="w-4 h-4" />} score={data.score} findings={data.findings} lesson={explain ? MODULE_LESSONS.earnings : undefined} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricBox label="Last Surprise" value={data.last_surprise_pct != null ? `${data.last_surprise_pct.toFixed(1)}%` : '—'} explainer={explain ? { lesson: EARNINGS_LESSONS.last_surprise_pct, rawValue: data.last_surprise_pct?.toFixed(1) ?? '' } : undefined} />
        <MetricBox label="Beat Rate" value={data.beat_rate ?? '—'} explainer={explain ? { lesson: EARNINGS_LESSONS.beat_rate, rawValue: data.beat_rate ?? '' } : undefined} />
        <MetricBox label="Next Earnings" value={data.next_earnings_date ?? '—'} explainer={explain ? { lesson: EARNINGS_LESSONS.next_earnings_date, rawValue: data.next_earnings_date ?? '' } : undefined} />
      </div>
    </div>
  );
}

function SentimentDetail({ data, explain }: { data: NonNullable<TickerAnalysisResponse['sentiment']>; explain: boolean }) {
  return (
    <div className="space-y-4">
      {explain && (
        <div className="bg-accent/5 border border-accent/10 rounded-lg p-3 text-sm text-text-secondary leading-relaxed">
          <strong className="text-text-primary">What to look for:</strong> Strong analyst consensus (Buy/Strong Buy), insiders buying their own stock, high institutional ownership, and low short interest. Price targets above the current price suggest room to run. High days to cover + elevated short interest = squeeze potential.
        </div>
      )}
      <ScoreCard title="Sentiment" icon={<Activity className="w-4 h-4" />} score={data.score} findings={data.findings} lesson={explain ? MODULE_LESSONS.sentiment : undefined} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricBox label="Analyst Consensus" value={data.analyst_consensus} explainer={explain ? { lesson: SENTIMENT_LESSONS.analyst_consensus, rawValue: data.analyst_consensus } : undefined} />
        <MetricBox label="Insider Activity" value={data.insider_status} explainer={explain ? { lesson: SENTIMENT_LESSONS.insider_status, rawValue: data.insider_status } : undefined} />
        <MetricBox label="Short Interest" value={data.short_interest_pct != null ? `${data.short_interest_pct.toFixed(1)}%` : '—'} explainer={explain ? { lesson: SENTIMENT_LESSONS.short_interest_pct, rawValue: data.short_interest_pct?.toFixed(1) ?? '' } : undefined} />
        <MetricBox label="Days to Cover" value={data.days_to_cover != null ? `${data.days_to_cover.toFixed(1)}d` : '—'} explainer={explain ? { lesson: SENTIMENT_LESSONS.days_to_cover, rawValue: data.days_to_cover?.toFixed(1) ?? '' } : undefined} />
        <MetricBox label="Inst. Ownership" value={data.institutional_ownership != null ? `${data.institutional_ownership.toFixed(1)}%` : '—'} explainer={explain ? { lesson: SENTIMENT_LESSONS.institutional_ownership, rawValue: data.institutional_ownership?.toFixed(1) ?? '' } : undefined} />
        <MetricBox label="Beta" value={data.beta != null ? data.beta.toFixed(2) : '—'} explainer={explain ? { lesson: SENTIMENT_LESSONS.beta, rawValue: data.beta?.toFixed(2) ?? '' } : undefined} />
        <MetricBox label="Target Upside" value={data.target_upside_pct != null ? `${data.target_upside_pct.toFixed(1)}%` : data.target_price != null ? `$${data.target_price.toFixed(2)}` : '—'} explainer={explain ? { lesson: SENTIMENT_LESSONS.target_upside_pct, rawValue: data.target_upside_pct?.toFixed(1) ?? '' } : undefined} />
      </div>
    </div>
  );
}

function RiskDetail({ data, explain }: { data: NonNullable<TickerAnalysisResponse['risk']>; explain: boolean }) {
  return (
    <div className="space-y-4">
      {explain && (
        <div className="bg-accent/5 border border-accent/10 rounded-lg p-3 text-sm text-text-secondary leading-relaxed">
          <strong className="text-text-primary">What to look for:</strong> Normal volatility (1-3% ATR) is ideal for most traders. The suggested stop loss protects you from unexpected drops — use it. Position sizing ensures no single trade can wipe you out. High liquidity means easy entry/exit. Avoid stocks with extreme volatility or microscopic market caps.
        </div>
      )}
      <ScoreCard title="Risk" icon={<Shield className="w-4 h-4" />} score={data.score} findings={data.findings} lesson={explain ? MODULE_LESSONS.risk : undefined} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricBox label="Volatility" value={data.volatility_regime} explainer={explain ? { lesson: RISK_LESSONS.volatility_regime, rawValue: data.volatility_regime } : undefined} />
        <MetricBox label="Suggested Stop" value={`${data.suggested_stop_pct.toFixed(1)}%`} explainer={explain ? { lesson: RISK_LESSONS.suggested_stop_pct, rawValue: data.suggested_stop_pct.toFixed(1) } : undefined} />
        <MetricBox label="Position Size" value={`${data.suggested_position_size_pct.toFixed(1)}%`} explainer={explain ? { lesson: RISK_LESSONS.suggested_position_size_pct, rawValue: data.suggested_position_size_pct.toFixed(1) } : undefined} />
        <MetricBox label="Max Risk/Trade" value={`${data.max_risk_per_trade_pct.toFixed(1)}%`} explainer={explain ? { lesson: RISK_LESSONS.max_risk_per_trade_pct, rawValue: data.max_risk_per_trade_pct.toFixed(1) } : undefined} />
      </div>
    </div>
  );
}

function MetricBox({ label, value, explainer }: {
  label: string; value: string; explainer?: { lesson: MetricLesson; rawValue: string };
}) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <div className="bg-surface/30 border border-border/50 rounded px-3 py-2">
        <div className="text-xs text-text-muted mb-0.5 flex items-center gap-1">
          <span>{label}</span>
          {explainer && (
            <button
              onClick={() => setOpen(!open)}
              className={cn(
                'inline-flex items-center justify-center w-3.5 h-3.5 rounded-full transition-colors',
                open ? 'bg-accent text-white' : 'text-text-muted hover:text-accent',
              )}
              title="Explain this metric"
            >
              <HelpCircle className="w-3 h-3" />
            </button>
          )}
        </div>
        <div className="text-sm font-mono text-text-primary truncate" title={value}>{value}</div>
      </div>
      {explainer && open && (
        <div className="mt-1 bg-background border border-accent/10 rounded-lg p-3 text-xs space-y-2 animate-in slide-in-from-top-1 duration-150">
          <div>
            <div className="font-semibold text-accent mb-0.5">What is this?</div>
            <p className="text-text-secondary leading-relaxed">{explainer.lesson.what}</p>
          </div>
          <div>
            <div className="font-semibold text-accent mb-0.5">What does this value mean?</div>
            <p className="text-text-secondary leading-relaxed">{explainer.lesson.readValue(explainer.rawValue)}</p>
          </div>
          <div>
            <div className="font-semibold text-accent mb-0.5">How does it affect the score?</div>
            <p className="text-text-secondary leading-relaxed">{explainer.lesson.scoringImpact}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function OptionsDetail({ data }: { data: OptionsChainResponse; explain: boolean }) {
  const OPTIONS_EXPLANATION = "IV Rank >80 favors premium selling (credit spreads). IV Rank <20 favors buying (debit spreads/long options). Negative GEX = dealers short gamma (destabilizing, expect big moves). Positive GEX = stabilizing. Max Pain = magnetic price level at expiry. Put/Call Ratio >1.2 = excessive fear (contrarian bullish). <0.7 = complacency.";
  
  // Safeguard: if the response lacks calls/puts arrays (e.g. error shape or stale cache),
  // render a clean "no data" message instead of crashing on .sort()
  if (!data.calls || !data.puts) {
    return (
      <div className="bg-loss/10 border border-loss/20 rounded-lg p-6 text-center">
        <AlertTriangle className="w-10 h-10 text-loss mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-text-primary mb-1">Options Data Unavailable</h3>
        <p className="text-sm text-text-muted mb-4">Options chain data could not be loaded for this symbol.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-accent/5 border border-accent/10 rounded-lg p-3 text-sm text-text-secondary leading-relaxed">
        <strong className="text-text-primary">Options Signals:</strong>{' '}
        <span>{OPTIONS_EXPLANATION}</span>
      </div>
      
      <div className="bg-surface/30 border border-border/50 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3">Options Overview</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <MetricBox label="Spot Price" value={formatPrice(data.spot)} />
          <MetricBox label="Max Pain" value={formatPrice(data.maxPain)} />
          <MetricBox label="IV Rank" value={`${data.ivRank}%`} />
          <MetricBox label="Put/Call Ratio" value={data.putCallRatio.toFixed(2)} />
          <MetricBox label="Gamma Exposure" value={`${(data.gammaExposure / 1e6).toFixed(1)}M`} />
          <MetricBox label="Call OI" value={formatLargeNumber(data.totalCallOI)} />
          <MetricBox label="Put OI" value={formatLargeNumber(data.totalPutOI)} />
          <MetricBox label="Expiry" value={data.expiry} />
        </div>
      </div>

      <div className="bg-surface/30 border border-border/50 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3">Calls (Top 10 by OI)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-text-muted border-b border-border/30">
                <th className="pb-1 pr-3">Strike</th>
                <th className="pb-1 pr-3">Bid</th>
                <th className="pb-1 pr-3">Ask</th>
                <th className="pb-1 pr-3">IV</th>
                <th className="pb-1 pr-3">Vol</th>
                <th className="pb-1 pr-3">OI</th>
              </tr>
            </thead>
            <tbody>
              {data.calls
                .sort((a, b) => b.openInterest - a.openInterest)
                .slice(0, 10)
                .map((c) => (
                  <tr key={c.strike} className="border-b border-border/20">
                    <td className="py-1 pr-3 font-mono">{formatPrice(c.strike)}</td>
                    <td className="py-1 pr-3 font-mono">{c.bid > 0 ? formatPrice(c.bid) : '—'}</td>
                    <td className="py-1 pr-3 font-mono">{c.ask > 0 ? formatPrice(c.ask) : '—'}</td>
                    <td className="py-1 pr-3 font-mono">{(c.impliedVolatility * 100).toFixed(1)}%</td>
                    <td className="py-1 pr-3 font-mono">{formatLargeNumber(c.volume)}</td>
                    <td className="py-1 pr-3 font-mono">{formatLargeNumber(c.openInterest)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-surface/30 border border-border/50 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3">Puts (Top 10 by OI)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-text-muted border-b border-border/30">
                <th className="pb-1 pr-3">Strike</th>
                <th className="pb-1 pr-3">Bid</th>
                <th className="pb-1 pr-3">Ask</th>
                <th className="pb-1 pr-3">IV</th>
                <th className="pb-1 pr-3">Vol</th>
                <th className="pb-1 pr-3">OI</th>
              </tr>
            </thead>
            <tbody>
              {data.puts
                .sort((a, b) => b.openInterest - a.openInterest)
                .slice(0, 10)
                .map((p) => (
                  <tr key={p.strike} className="border-b border-border/20">
                    <td className="py-1 pr-3 font-mono">{formatPrice(p.strike)}</td>
                    <td className="py-1 pr-3 font-mono">{p.bid > 0 ? formatPrice(p.bid) : '—'}</td>
                    <td className="py-1 pr-3 font-mono">{p.ask > 0 ? formatPrice(p.ask) : '—'}</td>
                    <td className="py-1 pr-3 font-mono">{(p.impliedVolatility * 100).toFixed(1)}%</td>
                    <td className="py-1 pr-3 font-mono">{formatLargeNumber(p.volume)}</td>
                    <td className="py-1 pr-3 font-mono">{formatLargeNumber(p.openInterest)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-surface/30 border border-border/50 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3">Available Expiries</h3>
        <div className="flex flex-wrap gap-2">
          {data.availableExpiries.map((exp) => (
            <span
              key={exp}
              className={`px-2 py-1 rounded text-xs font-mono ${
                exp === data.expiry
                  ? 'bg-accent/20 text-accent border border-accent/30'
                  : 'bg-surface-hover text-text-secondary hover:bg-surface-hover/80'
              }`}
            >
              {exp}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function NewsDetail({ data }: { data: NewsResponse; explain: boolean }) {
  return (
    <div className="space-y-4">
      <div className="bg-accent/5 border border-accent/10 rounded-lg p-3 text-sm text-text-secondary leading-relaxed">
        <strong className="text-text-primary">News Feed:</strong> Green = positive catalysts (earnings beats, upgrades, partnerships). 
        Red = negative (misses, downgrades, investigations). Neutral = routine filings, dividends. 
        Click headlines to read full articles.
      </div>

      {data.items.length === 0 ? (
        <div className="text-center py-8 text-text-muted">
          No recent news found for {data.symbol}
        </div>
      ) : (
        <div className="space-y-2">
          {data.items.map((item, index) => (
            <div
              key={index}
              className={`bg-surface/30 border border-border/50 rounded-lg p-3 ${
                item.sentiment === 'positive' ? 'border-gain/30' :
                item.sentiment === 'negative' ? 'border-loss/30' : ''
              }`}
            >
              <div className="flex items-start gap-2">
                <span className={`flex-shrink-0 w-5 h-5 rounded-full mt-0.5 ${
                  item.sentiment === 'positive' ? 'bg-gain/20 text-gain' :
                  item.sentiment === 'negative' ? 'bg-loss/20 text-loss' : 'bg-text-muted/20 text-text-muted'
                } flex items-center justify-center`}>
                  {item.sentiment === 'positive' && <TrendingUp className="w-3 h-3" />}
                  {item.sentiment === 'negative' && <ArrowDown className="w-3 h-3" />}
                  {item.sentiment === 'neutral' && <Minus className="w-3 h-3" />}
                </span>
                <div className="flex-1 min-w-0">
                  <a
                    href={item.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-text-primary hover:text-accent font-medium block truncate"
                  >
                    {item.title}
                  </a>
                  <div className="flex items-center gap-2 mt-1 text-xs text-text-muted">
                    <span>{item.publisher}</span>
                    <span>•</span>
                    <span>{item.date ? new Date(item.date).toLocaleDateString() : 'Unknown date'}</span>
                    <ExternalLink className="w-3 h-3 opacity-50" />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Page ──

type TabKey = 'verdict' | 'technical' | 'fundamental' | 'earnings' | 'sentiment' | 'risk' | 'options' | 'news';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'verdict', label: 'Verdict', icon: <Info className="w-4 h-4" /> },
  { key: 'technical', label: 'Technical', icon: <TrendingUp className="w-4 h-4" /> },
  { key: 'fundamental', label: 'Fundamentals', icon: <DollarSign className="w-4 h-4" /> },
  { key: 'earnings', label: 'Earnings', icon: <Activity className="w-4 h-4" /> },
  { key: 'sentiment', label: 'Sentiment', icon: <Activity className="w-4 h-4" /> },
  { key: 'risk', label: 'Risk', icon: <Shield className="w-4 h-4" /> },
  { key: 'options', label: 'Options', icon: <FileText className="w-4 h-4" /> },
  { key: 'news', label: 'News', icon: <Newspaper className="w-4 h-4" /> },
];

export function TickerAnalysisPage() {
  const { symbol: routeSymbol } = useParams<{ symbol: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchInput, setSearchInput] = useState('');
  const [activeTab, setActiveTab] = useState<TabKey>('verdict');
  const [explain, setExplain] = useState(true);

  // If we have a route param, use it. Otherwise from search params.
  const symbol = routeSymbol ?? searchParams.get('symbol') ?? '';

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['ticker-analysis', symbol],
    queryFn: () => fetchTickerAnalysis(symbol),
    enabled: symbol.length > 0,
    staleTime: 30_000,
    retry: 1,
  });

  // Fetch options chain data
  const { data: optionsData, isLoading: optionsLoading, isError: optionsError } = useQuery({
    queryKey: ['ticker-options', symbol],
    queryFn: () => fetchOptionsChain(symbol),
    enabled: symbol.length > 0 && activeTab === 'options',
    staleTime: 60_000,
    retry: 1,
  });

  // Fetch news data
  const { data: newsData, isLoading: newsLoading } = useQuery({
    queryKey: ['ticker-news', symbol],
    queryFn: () => fetchNews(symbol),
    enabled: symbol.length > 0 && activeTab === 'news',
    staleTime: 300_000, // 5 minutes
    retry: 1,
  });

  const handleSearch = () => {
    const sym = searchInput.trim().toUpperCase();
    if (sym) {
      setSearchParams({ symbol: sym });
    }
  };

  // Landing / no symbol selected
  if (!symbol) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
          <Search className="w-16 h-16 text-text-muted mb-4" />
          <h1 className="text-xl font-semibold text-text-primary mb-2">Ticker Analysis</h1>
          <p className="text-text-muted mb-6 max-w-md">
            Enter a stock symbol to get an elite-trader-grade analysis with technical, fundamental, earnings,
            sentiment, and risk assessment — plus an actionable verdict.
          </p>
          <div className="flex gap-2 w-full max-w-sm">
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Enter symbol (e.g. QGEN)"
              className="flex-1 bg-surface border border-border rounded-lg px-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50"
            />
            <button
              onClick={handleSearch}
              className="bg-accent hover:bg-accent/90 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors"
            >
              Analyze
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Loading
  if (isLoading) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="flex items-center justify-center min-h-[40vh]">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
          <span className="ml-3 text-text-muted">Analyzing {symbol}...</span>
        </div>
      </div>
    );
  }

  // Error
  if (error || !data) {
    const errMsg = error instanceof Error ? error.message : 'Failed to fetch analysis';
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="bg-loss/10 border border-loss/20 rounded-lg p-6 text-center">
          <AlertTriangle className="w-10 h-10 text-loss mx-auto mb-3" />
          <h2 className="text-lg font-semibold text-text-primary mb-1">Analysis Failed</h2>
          <p className="text-sm text-text-muted mb-4">{errMsg}</p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => refetch()}
              className="bg-accent hover:bg-accent/90 text-white rounded-lg px-4 py-2 text-sm font-medium"
            >
              Retry
            </button>
            <Link
              to="/ticker"
              className="bg-surface-elevated hover:bg-surface-hover text-text-primary rounded-lg px-4 py-2 text-sm font-medium"
            >
              New Search
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Weighted score calculation for conviction tooltip
  const getTechnicalScore = (tech: any) => {
    if (!tech) return 0;
    return tech.daily?.score ?? tech.score ?? 0;
  };
  const moduleScores = [
    { label: 'Technical', score: getTechnicalScore(data.technical) },
    { label: 'Fundamentals', score: data.fundamental?.score ?? 0 },
    { label: 'Earnings', score: data.earnings?.score ?? 0 },
    { label: 'Sentiment', score: data.sentiment?.score ?? 0 },
    { label: 'Risk', score: data.risk?.score ?? 0 },
  ];
  // Default weights matching backend: [tech, fund, earn, sent, risk]
  const weights = [0.30, 0.22, 0.12, 0.20, 0.16];
  const available = moduleScores
    .map((m, i) => ({ score: m.score, weight: weights[i] }))
    .filter(m => m.score !== 0 || data.technical || data.fundamental || data.earnings || data.sentiment || data.risk);
  const totalWeight = available.reduce((sum, m) => sum + m.weight, 0);
  const weightedScore = totalWeight > 0
    ? available.reduce((sum, m) => sum + m.score * (m.weight / totalWeight), 0)
    : 0;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/ticker" className="text-text-muted hover:text-text-primary">
            <Search className="w-5 h-5" />
          </Link>
          <span className="text-text-muted text-sm">/</span>
          <span className="text-sm font-semibold text-text-primary">{symbol}</span>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to={`/charts?symbol=${symbol}&timeframe=1D`}
            className={cn(
              'flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-full border transition-colors',
              'bg-surface border-border/50 text-text-muted hover:text-text-primary hover:border-text-muted'
            )}
          >
            <BarChart2 className="w-3.5 h-3.5" />
            <span>View Chart</span>
          </Link>
          <button
            onClick={() => setExplain(!explain)}
            className={cn(
              'flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-full border transition-colors',
              explain
                ? 'bg-accent/10 border-accent/30 text-accent'
                : 'bg-surface border-border/50 text-text-muted hover:text-text-primary hover:border-text-muted',
            )}
          >
            <Brain className="w-3.5 h-3.5" />
            <span>{explain ? 'Explain On' : 'Explain'}</span>
          </button>
        </div>
      </div>

      {/* Verdict Banner */}
      <VerdictBanner data={data} weightedScore={weightedScore} />

      {/* Module Score Overview */}
      <div className="grid grid-cols-5 gap-3">
        <MiniScore label="Technical" score={getTechnicalScore(data.technical)} />
        <MiniScore label="Fundamentals" score={data.fundamental?.score ?? 0} />
        <MiniScore label="Earnings" score={data.earnings?.score ?? 0} />
        <MiniScore label="Sentiment" score={data.sentiment?.score ?? 0} />
        <MiniScore label="Risk" score={data.risk?.score ?? 0} />
      </div>

      {/* Tab Navigation */}
      <div className="flex flex-wrap gap-2 border-b border-border pb-3">
        {TABS.map((tab) => (
          <TabButton
            key={tab.key}
            active={activeTab === tab.key}
            label={tab.label}
            icon={tab.icon}
            onClick={() => setActiveTab(tab.key)}
          />
        ))}
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'verdict' && <VerdictTab data={data} explain={explain} />}
        {activeTab === 'technical' && data.technical && <TechnicalDetail data={data.technical} explain={explain} />}
        {activeTab === 'fundamental' && data.fundamental && <FundamentalDetail data={data.fundamental} explain={explain} />}
        {activeTab === 'earnings' && data.earnings && <EarningsDetail data={data.earnings} explain={explain} />}
        {activeTab === 'sentiment' && data.sentiment && <SentimentDetail data={data.sentiment} explain={explain} />}
        {activeTab === 'risk' && data.risk && <RiskDetail data={data.risk} explain={explain} />}
        {activeTab === 'options' && (
          optionsLoading ? (
            <div className="flex items-center justify-center min-h-[30vh]">
              <Loader2 className="w-8 h-8 text-accent animate-spin" />
              <span className="ml-3 text-text-muted">Loading options chain...</span>
            </div>
          ) : optionsError ? (
            <div className="bg-loss/10 border border-loss/20 rounded-lg p-6 text-center">
              <AlertTriangle className="w-10 h-10 text-loss mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-text-primary mb-1">Options Data Error</h3>
              <p className="text-sm text-text-muted mb-4">Failed to load options chain for {symbol}. The symbol may not have listed options.</p>
            </div>
          ) : optionsData ? (
            <OptionsDetail data={optionsData} explain={explain} />
          ) : (
            <div className="bg-loss/10 border border-loss/20 rounded-lg p-6 text-center">
              <AlertTriangle className="w-10 h-10 text-loss mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-text-primary mb-1">No Options Data</h3>
              <p className="text-sm text-text-muted mb-4">No options chain available for {symbol}</p>
            </div>
          )
        )}
        {activeTab === 'news' && (
          newsLoading ? (
            <div className="flex items-center justify-center min-h-[30vh]">
              <Loader2 className="w-8 h-8 text-accent animate-spin" />
              <span className="ml-3 text-text-muted">Loading news...</span>
            </div>
          ) : newsData ? (
            <NewsDetail data={newsData} explain={explain} />
          ) : (
            <div className="bg-loss/10 border border-loss/20 rounded-lg p-6 text-center">
              <AlertTriangle className="w-10 h-10 text-loss mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-text-primary mb-1">No News Data</h3>
              <p className="text-sm text-text-muted mb-4">No news available for {symbol}</p>
            </div>
          )
        )}
      </div>
    </div>
  );
}

function MiniScore({ label, score }: { label: string; score: number }) {
  const clamped = Math.max(-1, Math.min(1, score));
  const pct = ((clamped + 1) / 2) * 100;
  const color = score >= 0.3 ? 'bg-gain' : score >= -0.1 ? 'bg-text-muted' : 'bg-loss';
  return (
    <div className="bg-surface/30 border border-border/50 rounded-lg p-3">
      <div className="text-xs text-text-muted mb-2">{label}</div>
      <div className="h-1.5 rounded-full bg-surface-hover overflow-hidden mb-1.5">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
      <div className={cn(
        'text-sm font-bold font-mono',
        score >= 0.3 ? 'text-gain' : score >= -0.1 ? 'text-text-secondary' : 'text-loss',
      )}>
        {score >= 0 ? '+' : ''}{score.toFixed(2)}
      </div>
    </div>
  );
}
