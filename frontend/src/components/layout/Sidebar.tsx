import { NavLink } from 'react-router-dom';
import { useWS } from '@/ws/WebSocketProvider';
import { cn } from '@/lib/cn';
import { LayoutDashboard, TrendingUp, BarChart2, Shield } from 'lucide-react';

interface NavItemProps {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItemProps[] = [
  { to: '/screener', label: 'Screener', icon: <LayoutDashboard className="w-5 h-5" /> },
  { to: '/charts', label: 'Charts', icon: <TrendingUp className="w-5 h-5" /> },
  { to: '/backtest', label: 'Backtest', icon: <BarChart2 className="w-5 h-5" /> },
  { to: '/risk', label: 'Risk', icon: <Shield className="w-5 h-5" /> },
];

function NavItem({ to, label, icon }: NavItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150',
          isActive
            ? 'bg-surface-hover text-accent border-l-2 border-accent'
            : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
        )
      }
    >
      <span className="flex-shrink-0">{icon}</span>
      <span>{label}</span>
    </NavLink>
  );
}

function ConnectionDot() {
  const { connectionState } = useWS();
  const dotColors: Record<string, string> = {
    connected: 'bg-gain',
    disconnected: 'bg-loss',
    connecting: 'bg-warning',
    reconnecting: 'bg-warning',
  };

  const labels: Record<string, string> = {
    connected: 'Connected',
    disconnected: 'Disconnected',
    connecting: 'Connecting...',
    reconnecting: 'Reconnecting...',
  };

  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <span
        className={cn('h-2 w-2 rounded-full', dotColors[connectionState] || 'bg-text-muted')}
      />
      <span className="text-xs text-text-muted capitalize">
        {labels[connectionState] || connectionState}
      </span>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="flex w-64 flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border px-4 py-4">
        <span className="text-lg font-bold text-accent">conflu.ai</span>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>

      <div className="border-t border-border px-3 py-3">
        <ConnectionDot />
      </div>
    </aside>
  );
}