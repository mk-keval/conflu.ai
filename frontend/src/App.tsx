import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { ScreenerPage } from './components/screener';
import { SharedScreenerView } from './components/screener/SharedScreenerView';
import { ChartsPage } from './components/charts';
import { BacktestPage, BacktestResultPage, ComparisonDashboard } from './components/backtest';
import { RiskPage } from './components/risk';
import { SectorRotationPage } from './components/sector-rotation';
import { TickerAnalysisPage } from './components/ticker-analysis/TickerAnalysisPage';
import { WorkflowPage } from './components/workflow/WorkflowPage';
import { DashboardPage } from './components/dashboard/DashboardPage';

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/screener" element={<ScreenerPage />} />
        <Route path="/sector-rotation" element={<SectorRotationPage />} />
        <Route path="/workflow" element={<WorkflowPage />} />
        <Route path="/charts" element={<ChartsPage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/backtest/result/:runId" element={<BacktestResultPage />} />
        <Route path="/backtest/compare" element={<ComparisonDashboard />} />
        <Route path="/risk" element={<RiskPage />} />
        <Route path="/ticker" element={<TickerAnalysisPage />} />
        <Route path="/ticker/:symbol" element={<TickerAnalysisPage />} />
        <Route path="/shared/screen" element={<SharedScreenerView />} />
        <Route path="/shared/screen/:token" element={<SharedScreenerView />} />
      </Route>
    </Routes>
  );
}
