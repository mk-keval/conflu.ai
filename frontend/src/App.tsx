import { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { ScreenerPage } from './components/screener';
import { SharedScreenerView } from './components/screener/SharedScreenerView';
import { ChartsPage } from './components/charts';
import {
  BacktestPage,
  BacktestResultPage,
  ComparisonDashboard,
  FilterSweepPage,
} from './components/backtest';
import { RiskPage } from './components/risk';
import { SectorRotationPage } from './components/sector-rotation';
import { TickerAnalysisPage } from './components/ticker-analysis/TickerAnalysisPage';
import { WorkflowPage } from './components/workflow/WorkflowPage';
import { DashboardPage } from './components/dashboard/DashboardPage';
import { PortfolioPage } from './components/portfolio/PortfolioPage';
import {
  MorningBriefPage,
  SimpleVerdictPage,
  WatchlistBuilderPage,
  ProSettingsPage,
} from './components/professional';
import { LearnPage } from './components/learn/LearnPage';
import { useProModeStore } from './store/professional';
import { useWorkflowStore } from './store/workflowStore';

function HomeRedirect() {
  const proModeEnabled = useProModeStore((s) => s.enabled);
  return <Navigate to={proModeEnabled ? '/pro' : '/dashboard'} replace />;
}

export function App() {
  // Hydrate the paper-trade journal from the backend on mount + window focus
  // (D-68 P4 / R1): the dashboards (Expectancy, Open Positions, Skill Score)
  // read store.paperTrades, which was never hydrated from the SQLite journal.
  useEffect(() => {
    const hydrate = () => void useWorkflowStore.getState().hydrateFromJournal();
    hydrate();
    window.addEventListener('focus', hydrate);
    return () => window.removeEventListener('focus', hydrate);
  }, []);

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomeRedirect />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/screener" element={<ScreenerPage />} />
        <Route path="/sector-rotation" element={<SectorRotationPage />} />
        <Route path="/workflow" element={<WorkflowPage />} />
        <Route path="/charts" element={<ChartsPage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/backtest/filter-sweep" element={<FilterSweepPage />} />
        <Route
          path="/backtest/result/:runId"
          element={<BacktestResultPage />}
        />
        <Route path="/backtest/compare" element={<ComparisonDashboard />} />
        <Route path="/risk" element={<RiskPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/ticker/:symbol" element={<TickerAnalysisPage />} />
        <Route path="/ticker" element={<TickerAnalysisPage />} />
        <Route path="/learn" element={<LearnPage />} />
        <Route path="/shared/screen" element={<SharedScreenerView />} />
        <Route path="/shared/screen/:token" element={<SharedScreenerView />} />
        {/* Professional Mode routes */}
        <Route path="/pro" element={<MorningBriefPage />} />
        <Route path="/pro/ticker/:symbol" element={<SimpleVerdictPage />} />
        <Route path="/pro/watchlist" element={<WatchlistBuilderPage />} />
        <Route path="/pro/settings" element={<ProSettingsPage />} />
      </Route>
    </Routes>
  );
}
