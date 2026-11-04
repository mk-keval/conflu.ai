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
import { formatDate, formatPrice } from '@/lib/format';

interface EquityCurveChartProps {
  data: EquityPoint[];
  initialCash?: number;
}

interface TooltipPayloadEntry {
  value: number;
  payload: EquityPoint;
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
      <p className="text-dark-50 font-mono">{formatPrice(p.equity)}</p>
    </div>
  );
}

export function EquityCurveChart({ data, initialCash }: EquityCurveChartProps) {
  if (!data.length) {
    return (
      <div className="border-dark-600 bg-dark-800 text-dark-400 flex h-64 items-center justify-center rounded border text-sm">
        No equity data available
      </div>
    );
  }

  const domainMin = Math.min(...data.map((d) => d.equity)) * 0.98;
  const domainMax = Math.max(...data.map((d) => d.equity)) * 1.02;

  return (
    <div className="border-dark-600 bg-dark-800 rounded border p-3">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-dark-200 text-xs font-semibold">Equity Curve</h4>
        {initialCash && (
          <span className="text-dark-400 text-[10px]">
            Initial: {formatPrice(initialCash)}
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22C55E" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#22C55E" stopOpacity={0} />
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
            domain={[domainMin, domainMax]}
            tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}K`}
            stroke="#6E7681"
            tick={{ fontSize: 10 }}
            width={60}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="equity"
            stroke="#22C55E"
            strokeWidth={1.5}
            fill="url(#equityGrad)"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
