import { NavLink } from 'react-router-dom';
import { useWS } from '@/ws/WebSocketProvider';
import { useProModeStore } from '@/store/professional';
import { cn } from '@/lib/cn';
import { BrandMark } from './BrandMark';
import {
  Home,
  LayoutDashboard,
  TrendingUp,
  BarChart2,
  Shield,
  RotateCcw,
  Search,
  Briefcase,
  Sun,
  BookOpen,
} from 'lucide-react';

interface NavItemProps {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItemProps[] = [
  { to: '/dashboard', label: 'Dashboard', icon: <Home className="h-5 w-5" /> },
  {
    to: '/screener',
    label: 'Screener',
    icon: <LayoutDashboard className="h-5 w-5" />,
  },
  {
    to: '/sector-rotation',
    label: 'Sector Rotation',
    icon: <RotateCcw className="h-5 w-5" />,
  },
  {
    to: '/ticker',
    label: 'Ticker Analysis',
    icon: <Search className="h-5 w-5" />,
  },
  { to: '/charts', label: 'Charts', icon: <TrendingUp className="h-5 w-5" /> },
  {
    to: '/backtest',
    label: 'Backtest',
    icon: <BarChart2 className="h-5 w-5" />,
  },
  { to: '/risk', label: 'Risk', icon: <Shield className="h-5 w-5" /> },
  {
    to: '/portfolio',
    label: 'Portfolio',
    icon: <Briefcase className="h-5 w-5" />,
  },
  {
    to: '/workflow',
    label: 'Swing Desk',
    icon: <Briefcase className="h-5 w-5" />,
  },
  { to: '/learn', label: 'Learn', icon: <BookOpen className="h-5 w-5" /> },
];

function NavItem({ to, label, icon }: NavItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150',
          isActive
            ? 'border-l-[3px] border-accent bg-accent/10 text-accent'
            : 'text-text-secondary hover:bg-white/[0.06] hover:text-text-primary'
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
  const label = isConnected
    ? 'Connected'
    : connectionState === 'disconnected'
      ? 'Disconnected'
      : connectionState === 'connecting'
        ? 'Connecting...'
        : 'Reconnecting...';
  const dotColor = isConnected ? 'bg-gain' : 'bg-loss';

  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <span className={cn('relative h-2 w-2 rounded-full', dotColor)}>
        {isConnected && (
          <span className="absolute inset-0 animate-ping rounded-full bg-gain opacity-40" />
        )}
      </span>
      <span className="text-xs text-text-muted">{label}</span>
    </div>
  );
}

export function Sidebar() {
  const proModeEnabled = useProModeStore((s) => s.enabled);

  return (
    <aside className="relative z-10 hidden w-64 flex-col border-r border-border bg-surface/60 backdrop-blur-xl lg:flex">
      {/* Top accent gradient bar */}
      <div className="h-[3px] bg-gradient-to-r from-accent via-accent/40 to-transparent" />

      <div className="flex items-center border-b border-border px-4 py-3">
        <BrandMark />
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}

        {/* Professional Mode section — visible when Guided mode is enabled */}
        {proModeEnabled && (
          <>
            <div className="px-3 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-widest text-text-muted/60">
              Guided Mode
            </div>
            <NavItem
              to="/pro"
              label="Morning Brief"
              icon={<Sun className="h-5 w-5" />}
            />
            <NavItem
              to="/pro/watchlist"
              label="Watchlist"
              icon={<Briefcase className="h-5 w-5" />}
            />
          </>
        )}
      </nav>

      <div className="border-t border-border/50 px-3 py-3">
        <ConnectionDot />
      </div>
    </aside>
  );
}
