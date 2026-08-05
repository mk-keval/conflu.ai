import { useMemo } from 'react';
import { GraduationCap, Lock, Unlock } from 'lucide-react';
import { cn } from '@/lib/cn';
import { UNLOCK_SCHEDULE } from '@/types/professional';

interface GraduationProgressProps {
  daysActive: number;
  isFeatureUnlocked: (feature: string) => boolean;
  featureLockDays: (feature: string) => number;
}

interface ScheduleItem {
  feature: string;
  label: string;
  unlockDay: number;
  unlocked: boolean;
  daysRemaining: number;
}

const FEATURE_LABELS: Record<string, string> = {
  'morning-brief': 'Morning Brief',
  'one-click-verdict': 'One-Click Verdict',
  'watchlist-builder': 'Watchlist Builder',
  'screen-selector': 'All 21 Screen Templates',
  'deep-analysis': 'Deep Analysis (8 Tabs)',
  'backtest-engine': 'Backtest Engine',
  'portfolio-analytics': 'Portfolio Analytics',
  'charts-full': 'Full Charts',
};

export function GraduationProgress({
  daysActive,
  isFeatureUnlocked,
  featureLockDays,
}: GraduationProgressProps) {
  const schedule: ScheduleItem[] = useMemo(
    () =>
      Object.entries(UNLOCK_SCHEDULE)
        .map(([feature, unlockDay]) => ({
          feature,
          label: FEATURE_LABELS[feature] || feature,
          unlockDay,
          unlocked: isFeatureUnlocked(feature),
          daysRemaining: featureLockDays(feature),
        }))
        .sort((a, b) => a.unlockDay - b.unlockDay),
    [daysActive, isFeatureUnlocked, featureLockDays]
  );

  const nextUnlock = schedule.find((s) => !s.unlocked);
  const progressPct = Math.min(
    100,
    (daysActive / 90) * 100
  );

  return (
    <div data-testid="graduation-progress" className="space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <GraduationCap className="h-4 w-4 text-accent" />
        <span className="text-sm font-semibold text-text-primary">Graduation Path</span>
      </div>

      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-text-muted">
          <span>Day {daysActive}</span>
          <span>{Math.min(90, daysActive)} / 90 days</span>
        </div>
        <div className="h-2 rounded-full bg-surface-tertiary overflow-hidden">
          <div
            className="h-full rounded-full bg-accent transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Next unlock */}
      {nextUnlock && (
        <div className="rounded-md bg-accent/10 border border-accent/20 p-2">
          <span className="text-xs text-text-muted block">
            Next unlock in {nextUnlock.daysRemaining} day{nextUnlock.daysRemaining !== 1 ? 's' : ''}:
          </span>
          <span className="text-sm font-medium text-accent">
            {nextUnlock.label}
          </span>
        </div>
      )}

      {/* Full schedule */}
      <div className="space-y-1">
        {schedule.map((item) => (
          <div
            key={item.feature}
            className={cn(
              'flex items-center justify-between py-1 px-2 rounded',
              item.unlocked ? 'bg-green-500/5' : 'opacity-60'
            )}
          >
            <div className="flex items-center gap-2">
              {item.unlocked ? (
                <Unlock className="h-3 w-3 text-green-400" />
              ) : (
                <Lock className="h-3 w-3 text-text-muted" />
              )}
              <span
                className={cn(
                  'text-xs',
                  item.unlocked ? 'text-text-primary' : 'text-text-muted'
                )}
              >
                {item.label}
              </span>
            </div>
            <span className="text-2xs text-text-muted">
              {item.unlocked ? 'Unlocked' : `Day ${item.unlockDay}`}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
