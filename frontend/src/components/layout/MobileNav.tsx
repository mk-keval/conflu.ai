import { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useProModeStore } from '@/store/professional';
import { useKeyboard } from '@/hooks/useKeyboard';
import { cn } from '@/lib/cn';
import {
  Home,
  LayoutDashboard,
  RotateCcw,
  TrendingUp,
  BarChart2,
  Menu,
  Search,
  Shield,
  Briefcase,
  Sun,
  X,
} from 'lucide-react';

interface MobileNavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const primaryItems: MobileNavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: <Home className="h-5 w-5" /> },
  { to: '/screener', label: 'Screener', icon: <LayoutDashboard className="h-5 w-5" /> },
  { to: '/sector-rotation', label: 'Sectors', icon: <RotateCcw className="h-5 w-5" /> },
  { to: '/charts', label: 'Charts', icon: <TrendingUp className="h-5 w-5" /> },
  { to: '/backtest', label: 'Backtest', icon: <BarChart2 className="h-5 w-5" /> },
];

const moreItems: MobileNavItem[] = [
  { to: '/ticker', label: 'Ticker Analysis', icon: <Search className="h-5 w-5" /> },
  { to: '/risk', label: 'Risk', icon: <Shield className="h-5 w-5" /> },
  { to: '/portfolio', label: 'Portfolio', icon: <Briefcase className="h-5 w-5" /> },
  { to: '/workflow', label: 'Swing Desk', icon: <Briefcase className="h-5 w-5" /> },
];

interface DrawerItemProps extends MobileNavItem {
  onNavigate: () => void;
}

function DrawerItem({ to, label, icon, onNavigate }: DrawerItemProps) {
  return (
    <NavLink
      to={to}
      onClick={onNavigate}
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

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const proModeEnabled = useProModeStore((s) => s.enabled);

  // Close the drawer on any route change
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  useKeyboard({ Escape: () => setOpen(false) });

  const isMoreActive = moreItems.some(
    (item) => location.pathname === item.to || location.pathname.startsWith(item.to + '/')
  );

  return (
    <>
      {/* Slide-up "More" drawer */}
      <div
        aria-hidden={!open}
        className={cn(
          'fixed inset-0 z-50 lg:hidden transition-opacity duration-200',
          open ? 'opacity-100' : 'pointer-events-none opacity-0'
        )}
      >
        <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />

        <div
          className={cn(
            'absolute inset-x-0 bottom-0 max-h-[80vh] overflow-y-auto rounded-t-2xl border-t border-white/10 bg-surface/95 backdrop-blur-xl transition-transform duration-300',
            open ? 'translate-y-0' : 'translate-y-full'
          )}
        >
          <div className="flex items-center justify-between border-b border-border/50 px-4 py-3">
            <span className="text-sm font-semibold text-text-primary">More</span>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close menu"
              className="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-white/[0.06] hover:text-text-primary"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <nav className="space-y-1 p-3 pb-[env(safe-area-inset-bottom)]">
            {moreItems.map((item) => (
              <DrawerItem key={item.to} {...item} onNavigate={() => setOpen(false)} />
            ))}

            {proModeEnabled && (
              <>
                <div className="px-3 pt-4 pb-1 text-[10px] font-semibold uppercase tracking-widest text-text-muted/60">
                  Guided Mode
                </div>
                <DrawerItem to="/pro" label="Morning Brief" icon={<Sun className="h-5 w-5" />} onNavigate={() => setOpen(false)} />
                <DrawerItem to="/pro/watchlist" label="Watchlist" icon={<Briefcase className="h-5 w-5" />} onNavigate={() => setOpen(false)} />
              </>
            )}
          </nav>
        </div>
      </div>

      {/* Bottom navigation bar — mobile only */}
      <nav
        aria-label="Primary"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-surface/80 backdrop-blur-xl pb-[env(safe-area-inset-bottom)] lg:hidden"
      >
        <div className="flex">
          {primaryItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex flex-1 flex-col items-center gap-1 py-2.5 text-[10px] font-medium transition-colors',
                  isActive ? 'text-accent' : 'text-text-muted hover:text-text-primary'
                )
              }
            >
              <span className="flex h-5 w-5 items-center justify-center">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}

          <button
            onClick={() => setOpen(true)}
            aria-expanded={open}
            aria-label="More menu"
            className={cn(
              'flex flex-1 flex-col items-center gap-1 py-2.5 text-[10px] font-medium transition-colors',
              isMoreActive ? 'text-accent' : 'text-text-muted hover:text-text-primary'
            )}
          >
            <span className="flex h-5 w-5 items-center justify-center">
              <Menu className="h-5 w-5" />
            </span>
            <span>More</span>
          </button>
        </div>
      </nav>
    </>
  );
}
