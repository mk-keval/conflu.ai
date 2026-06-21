import { NavLink } from 'react-router-dom';
import { useWS } from '@/ws/WebSocketProvider';
import { cn } from '@/lib/cn';

interface NavItemProps {
  to: string;
  label: string;
  icon: string;
}

const navItems: NavItemProps[] = [
  { to: '/screener', label: 'Screener', icon: '▦' },
  { to: '/charts', label: 'Charts', icon: '⬡' },
  { to: '/backtest', label: 'Backtest', icon: '↗' },
  { to: '/risk', label: 'Risk', icon: '◈' },
];

function NavItem({ to, label, icon }: NavItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-2 rounded p-2 text-sm transition-colors',
          isActive
            ? 'bg-dark-500 text-accent-light'
            : 'text-dark-200 hover:bg-dark-500 hover:text-dark-50'
        )
      }
    >
      <span className="w-5 text-center">{icon}</span>
      <span>{label}</span>
    </NavLink>
  );
}

function ConnectionDot() {
  const { connectionState } = useWS();
  const dotColors: Record<string, string> = {
    connected: 'bg-gain',
    disconnected: 'bg-loss',
    connecting: 'bg-yellow-400',
    reconnecting: 'bg-yellow-400',
  };

  return (
    <div className="flex items-center gap-2 px-2 py-3">
      <span
        className={cn('h-2 w-2 rounded-full', dotColors[connectionState] || 'bg-dark-400')}
      />
      <span className="text-xs text-dark-300 capitalize">{connectionState}</span>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="flex w-56 flex-col border-r border-dark-600 bg-dark-900">
      <div className="flex items-center gap-2 border-b border-dark-600 px-4 py-3">
        <span className="text-lg font-bold text-accent">conflu.ai</span>
      </div>

      <nav className="flex-1 space-y-1 px-2 py-4">
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>

      <div className="border-t border-dark-600 px-3 py-2">
        <ConnectionDot />
      </div>
    </aside>
  );
}
