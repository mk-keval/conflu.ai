import { useLocation, useNavigate } from 'react-router-dom';
import { useProModeStore } from '@/store/professional';
import { cn } from '@/lib/cn';
import { Check } from 'lucide-react';

export function WorkflowBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const proModeEnabled = useProModeStore((s) => s.enabled);
  const path = location.pathname;

  // In Guided mode the workflow starts at the Morning Brief (/pro); otherwise at Dashboard
  const STEPS = [
    { label: 'Market', path: proModeEnabled ? '/pro' : '/dashboard' },
    { label: 'Screen', path: '/screener' },
    { label: 'Analyze', path: '/ticker' },
    { label: 'Portfolio', path: '/portfolio' },
  ];

  // Determine current step — check specific paths first so /pro/ticker/:sym maps to Analyze, not Market
  let currentIdx = -1;
  for (let i = 0; i < STEPS.length; i++) {
    const stepPath = STEPS[i].path;
    if (path === stepPath || path.startsWith(stepPath + '/')) {
      // /pro/ticker/:symbol is the Analyze step even though it starts with /pro
      if (stepPath === '/pro' && path.startsWith('/pro/ticker')) {
        currentIdx = 2; // Analyze
        break;
      }
      currentIdx = i;
      break;
    }
  }

  // Only show on workflow-relevant pages
  if (currentIdx === -1) return null;

  return (
    <div className="flex items-center gap-0.5 px-4 py-1.5 border-b border-border/30 bg-surface/5">
      {STEPS.map((step, i) => {
        const isComplete = i < currentIdx;
        const isCurrent = i === currentIdx;
        const isFuture = i > currentIdx;

        return (
          <div key={step.label} className="flex items-center gap-0.5">
            {/* Step dot + label */}
            <button
              onClick={() => navigate(step.path)}
              disabled={isFuture}
              className={cn(
                'flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded transition-colors',
                isCurrent && 'text-accent bg-accent/10',
                isComplete && 'text-green-500 hover:text-green-400',
                isFuture && 'text-text-muted/40 cursor-default',
              )}
            >
              <span className={cn(
                'flex items-center justify-center w-4 h-4 rounded-full text-[9px] font-bold',
                isCurrent && 'bg-accent/20 text-accent',
                isComplete && 'bg-green-500/20 text-green-500',
                isFuture && 'bg-border/30 text-text-muted/40',
              )}>
                {isComplete ? <Check className="h-2.5 w-2.5" /> : i + 1}
              </span>
              {step.label}
            </button>

            {/* Connector */}
            {i < STEPS.length - 1 && (
              <span className={cn(
                'w-4 h-px mx-0.5',
                i < currentIdx ? 'bg-green-500/40' : 'bg-border/30'
              )} />
            )}
          </div>
        );
      })}
    </div>
  );
}
