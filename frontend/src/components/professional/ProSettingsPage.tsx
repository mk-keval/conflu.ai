import { useState } from 'react';
import {
  Settings,
  DollarSign,
  Bell,
  GraduationCap,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { useProModeStore } from '@/store/professional';
import { useProMode } from '@/hooks/useProMode';
import { GraduationProgress } from './GraduationProgress';
import type { RiskTolerance } from '@/types/professional';

const RISK_OPTIONS: {
  value: RiskTolerance;
  label: string;
  description: string;
  example: string;
}[] = [
  {
    value: 'conservative',
    label: 'Conservative',
    description: 'Lower risk, smaller positions',
    example: '$75K → $3,750 max per position (5%)',
  },
  {
    value: 'moderate',
    label: 'Moderate',
    description: 'Balanced risk-reward',
    example: '$75K → $5,000 max per position (6.7%)',
  },
  {
    value: 'aggressive',
    label: 'Aggressive',
    description: 'Higher risk, larger positions',
    example: '$75K → $7,500 max per position (10%)',
  },
];

const ALERT_LABELS: Record<string, string> = {
  morningBrief: 'Morning Brief Email',
  stopHitEmail: 'Stop Hit — Email',
  stopHitPush: 'Stop Hit — Push',
  targetHitPush: 'Target Hit — Push',
  earningsEmail: 'Earnings Alerts — Email',
  regimeChangeEmail: 'Regime Change — Email',
  regimeChangePush: 'Regime Change — Push',
  weeklyReview: 'Weekly Review Email (Sun)',
};

export function ProSettingsPage() {
  const {
    enabled,
    toggle,
    accountSize,
    setAccountSize,
    riskTolerance,
    setRiskTolerance,
    daysActive,
    isFeatureUnlocked,
    featureLockDays,
  } = useProMode();

  const alertPreferences = useProModeStore((s) => s.alertPreferences);
  const updateAlertPreferences = useProModeStore(
    (s) => s.updateAlertPreferences
  );
  const [accountInput, setAccountInput] = useState(String(accountSize));

  const handleAccountSave = () => {
    const value = parseInt(accountInput.replace(/[^0-9]/g, ''), 10);
    if (value >= 5000) {
      setAccountSize(value);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight text-text-primary">
          Professional Settings
        </h1>
        <p className="text-xs text-text-muted">
          Configure your Professional Mode experience
        </p>
      </div>

      {/* Section 1: Professional Mode toggle */}
      <section className="bg-surface-secondary overflow-hidden rounded-lg border border-border">
        <div className="flex items-center justify-between bg-surface-tertiary/30 px-4 py-3">
          <div className="flex items-center gap-2">
            <Settings className="h-4 w-4 text-accent" />
            <span className="text-sm font-semibold text-text-primary">
              Professional Mode
            </span>
          </div>
          <button
            data-testid="pro-mode-toggle"
            onClick={toggle}
            className={cn(
              'flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
              enabled
                ? 'bg-green-500/15 text-green-400'
                : 'bg-surface-tertiary text-text-muted'
            )}
          >
            {enabled ? (
              <ToggleRight className="h-4 w-4" />
            ) : (
              <ToggleLeft className="h-4 w-4" />
            )}
            {enabled ? 'Guided' : 'Explorer'}
          </button>
        </div>
        <div className="px-4 py-3">
          <p className="text-xs text-text-muted">
            {enabled
              ? 'Guided mode: Morning Brief, One-Click Verdict, position sizing, and education tooltips guide your workflow.'
              : 'Explorer mode: Full access to all screens, charts, backtesting, and deep analysis tools.'}
          </p>
        </div>
      </section>

      {/* Section 2: Account Settings */}
      <section className="bg-surface-secondary overflow-hidden rounded-lg border border-border">
        <div className="flex items-center gap-2 bg-surface-tertiary/30 px-4 py-3">
          <DollarSign className="h-4 w-4 text-accent" />
          <span className="text-sm font-semibold text-text-primary">
            Account Settings
          </span>
        </div>
        <div className="space-y-4 px-4 py-4">
          {/* Account size */}
          <div>
            <label className="mb-1.5 block text-xs text-text-muted">
              Account Size ($)
            </label>
            <div className="flex gap-2">
              <input
                data-testid="account-size-input"
                type="text"
                value={accountInput}
                onChange={(e) => setAccountInput(e.target.value)}
                onBlur={handleAccountSave}
                onKeyDown={(e) => e.key === 'Enter' && handleAccountSave()}
                placeholder="e.g., 100000"
                className="max-w-xs flex-1 rounded-lg border border-border/60 bg-background px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
              <button
                onClick={handleAccountSave}
                className="rounded-lg bg-accent/10 px-3 py-2 text-xs font-medium text-accent transition-colors hover:bg-accent/20"
              >
                Save
              </button>
            </div>
            <p className="text-2xs mt-1 text-text-muted">
              Used for position sizing. Minimum: $5,000. Current: $
              {accountSize.toLocaleString()}
            </p>
          </div>

          {/* Risk tolerance */}
          <div>
            <label className="mb-1.5 block text-xs text-text-muted">
              Risk Tolerance
            </label>
            <div className="grid grid-cols-3 gap-2">
              {RISK_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  data-testid={`risk-${opt.value}`}
                  onClick={() => setRiskTolerance(opt.value)}
                  className={cn(
                    'rounded-lg border p-3 text-left transition-colors',
                    riskTolerance === opt.value
                      ? 'border-accent bg-accent/10'
                      : 'border-border/60 bg-surface-tertiary/30 hover:border-accent/30'
                  )}
                >
                  <span
                    className={cn(
                      'block text-xs font-semibold',
                      riskTolerance === opt.value
                        ? 'text-accent'
                        : 'text-text-primary'
                    )}
                  >
                    {opt.label}
                  </span>
                  <span className="text-2xs mt-0.5 block text-text-muted">
                    {opt.description}
                  </span>
                  <span className="text-2xs mt-0.5 block font-mono text-text-muted">
                    {opt.example}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Section 3: Alert Preferences */}
      <section className="bg-surface-secondary overflow-hidden rounded-lg border border-border">
        <div className="flex items-center gap-2 bg-surface-tertiary/30 px-4 py-3">
          <Bell className="h-4 w-4 text-accent" />
          <span className="text-sm font-semibold text-text-primary">
            Alert Preferences
          </span>
        </div>
        <div className="space-y-1 px-4 py-3">
          {Object.entries(ALERT_LABELS).map(([key, label]) => (
            <div
              key={key}
              className="flex items-center justify-between border-b border-border/30 py-2 last:border-0"
            >
              <span className="text-xs text-text-primary">{label}</span>
              <button
                onClick={() =>
                  updateAlertPreferences({
                    [key]:
                      !alertPreferences[key as keyof typeof alertPreferences],
                  })
                }
                className={cn(
                  'relative h-5 w-9 rounded-full transition-colors',
                  alertPreferences[key as keyof typeof alertPreferences]
                    ? 'bg-accent'
                    : 'bg-surface-tertiary'
                )}
              >
                <span
                  className={cn(
                    'absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform',
                    alertPreferences[key as keyof typeof alertPreferences]
                      ? 'translate-x-4'
                      : 'translate-x-0.5'
                  )}
                />
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Section 4: Graduation Progress */}
      <section className="bg-surface-secondary overflow-hidden rounded-lg border border-border">
        <div className="flex items-center gap-2 bg-surface-tertiary/30 px-4 py-3">
          <GraduationCap className="h-4 w-4 text-accent" />
          <span className="text-sm font-semibold text-text-primary">
            Graduation Progress
          </span>
        </div>
        <div className="px-4 py-4">
          <GraduationProgress
            daysActive={daysActive}
            isFeatureUnlocked={isFeatureUnlocked}
            featureLockDays={featureLockDays}
          />
        </div>
      </section>
    </div>
  );
}
