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
            ? 'bg-accent/10 text-accent border-l-[3px] border-accent'
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

  const isConnected = connectionState === 'connected';
  const label = isConnected ? 'Connected' : connectionState === 'disconnected' ? 'Disconnected' : connectionState === 'connecting' ? 'Connecting...' : 'Reconnecting...';
  const dotColor = isConnected ? 'bg-gain' : 'bg-loss';

  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <span className={cn('relative h-2 w-2 rounded-full', dotColor)}>
        {isConnected && (
          <span className="absolute inset-0 rounded-full bg-gain animate-ping opacity-40" />
        )}
      </span>
      <span className="text-xs text-text-muted">{label}</span>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="flex w-64 flex-col border-r border-border bg-surface">
      {/* Top accent gradient bar */}
      <div className="h-[3px] bg-gradient-to-r from-accent via-accent/40 to-transparent" />

      <div className="flex items-center gap-2.5 border-b border-border px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15">
          <span className="text-sm font-bold text-accent">C</span>
        </div>
        <span className="text-base font-bold tracking-tight text-text-primary">conflu</span>
        <span className="text-base font-light text-text-muted">.ai</span>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>

      <div className="border-t border-border/50 px-3 py-3">
        <ConnectionDot />
      </div>
    </aside>
  );
}