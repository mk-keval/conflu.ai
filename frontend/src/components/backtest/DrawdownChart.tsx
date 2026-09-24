import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import type { EquityPoint } from '@/types/backtest';
import { formatDate, formatPct } from '@/lib/format';

interface DrawdownChartProps {
  data: EquityPoint[];
  initialCash: number;
}

function calcDrawdown(
  equityData: EquityPoint[]
): Array<{ timestamp: string; drawdown: number }> {
  if (!equityData.length) return [];
  let peak = equityData[0].equity;
  return equityData.map((p) => {
    if (p.equity > peak) peak = p.equity;
    return {
      timestamp: p.timestamp,
      drawdown: peak > 0 ? ((p.equity - peak) / peak) * 100 : 0,
    };
  });
}

interface TooltipPayloadEntry {
  value: number;
  payload: { timestamp: string; drawdown: number };
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="border-dark-500 bg-dark-800 rounded border px-3 py-2 text-xs shadow-lg">
      <p className="text-dark-300">{formatDate(p.timestamp)}</p>
      <p className="font-mono text-loss">{formatPct(p.drawdown)}</p>
    </div>
  );
}

export function DrawdownChart({ data }: DrawdownChartProps) {
  const ddData = calcDrawdown(data);

  if (!ddData.length) {
    return (
      <div className="border-dark-600 bg-dark-800 text-dark-400 flex h-48 items-center justify-center rounded border text-sm">
        No drawdown data available
      </div>
    );
  }

  const minDD = Math.min(...ddData.map((d) => d.drawdown)) * 1.05;

  return (
    <div className="border-dark-600 bg-dark-800 rounded border p-3">
      <h4 className="text-dark-200 mb-2 text-xs font-semibold">Drawdown</h4>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={ddData}>
          <defs>
            <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#EF4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#30363D" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatDate}
            stroke="#6E7681"
            tick={{ fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[minDD, 0]}
            tickFormatter={(v: number) => `${v.toFixed(1)}%`}
            stroke="#6E7681"
            tick={{ fontSize: 10 }}
            width={50}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="drawdown"
            stroke="#EF4444"
            strokeWidth={1.5}
            fill="url(#ddGrad)"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
