import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { WorkflowBar } from './WorkflowBar';
import { ErrorBoundary } from './ErrorBoundary';
import { MobileNav } from './MobileNav';

export function AppShell() {
  return (
    <div className="relative flex h-screen overflow-hidden bg-background">
      {/* Ambient glow background — subtle atmosphere, never decoration */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute -top-40 -left-40 h-[600px] w-[600px] bg-[radial-gradient(ellipse_at_top_left,rgba(45,212,191,0.08),transparent_50%)]" />
        <div className="absolute -bottom-40 -right-40 h-[600px] w-[600px] bg-[radial-gradient(ellipse_at_bottom_right,rgba(99,102,241,0.07),transparent_50%)]" />
      </div>

      <Sidebar />

      <div className="relative z-10 flex flex-1 flex-col overflow-hidden">
        <Header />
        <WorkflowBar />
        <main className="flex-1 overflow-auto pb-16 lg:pb-0">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>

      <MobileNav />
    </div>
  );
}
