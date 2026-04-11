/**
 * LapTimeChart — Grouped bar chart for lap time comparisons
 *
 * Renders when chart_data.type === "lap_time_comparison"
 * Shows lap time averages/bests for multiple drivers side-by-side.
 */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';

const DRIVER_COLORS = [
  '#00d2ff', // cyan
  '#e10600', // F1 red
  '#00ff87', // lime
  '#ffb800', // amber
  '#8b5cf6', // purple
  '#ff6b9d', // pink
];

function formatLapTime(seconds) {
  if (!seconds || seconds <= 0) return 'N/A';
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(3);
  return `${mins}:${secs.padStart(6, '0')}`;
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div
      style={{
        background: 'rgba(17, 17, 24, 0.95)',
        border: '1px solid rgba(0, 210, 255, 0.2)',
        borderRadius: '8px',
        padding: '10px 14px',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: '0.8rem',
      }}
    >
      <p style={{ color: '#8888a0', marginBottom: '6px', fontWeight: 600 }}>
        {label}
      </p>
      {payload.map((entry, i) => (
        <p key={i} style={{ color: entry.color, margin: '2px 0' }}>
          {entry.name}: {formatLapTime(entry.value)}
        </p>
      ))}
    </div>
  );
}

export default function LapTimeChart({ data }) {
  if (!data || !data.datasets || !data.labels) return null;

  // Transform data for Recharts
  const chartData = data.labels.map((label, i) => {
    const point = { name: label };
    data.datasets.forEach((ds) => {
      point[ds.driver] = ds.values[i];
    });
    return point;
  });

  const drivers = data.datasets.map((ds) => ds.driver);

  return (
    <div className="chart-container">
      <h4
        style={{
          color: 'var(--accent-cyan)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.8rem',
          fontWeight: 600,
          marginBottom: '12px',
          textTransform: 'uppercase',
          letterSpacing: '1px',
        }}
      >
        ⏱ {data.title || 'Lap Time Comparison'}
      </h4>

      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartData} barGap={4} barCategoryGap="20%">
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="name"
            tick={{ fill: '#8888a0', fontSize: 11, fontFamily: "'JetBrains Mono'" }}
            axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={formatLapTime}
            tick={{ fill: '#8888a0', fontSize: 10, fontFamily: "'JetBrains Mono'" }}
            axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
            tickLine={false}
            domain={['auto', 'auto']}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{
              fontFamily: "'JetBrains Mono'",
              fontSize: '0.75rem',
              color: '#8888a0',
            }}
          />
          {drivers.map((driver, i) => (
            <Bar
              key={driver}
              dataKey={driver}
              fill={DRIVER_COLORS[i % DRIVER_COLORS.length]}
              radius={[4, 4, 0, 0]}
              maxBarSize={40}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
