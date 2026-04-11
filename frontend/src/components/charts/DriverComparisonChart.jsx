/**
 * DriverComparisonChart — Line chart for lap time progression
 *
 * Renders when chart_data.type === "lap_times"
 * Shows lap-by-lap progression for one or more drivers.
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
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
        Lap {label}
      </p>
      {payload.map((entry, i) => (
        <p key={i} style={{ color: entry.color, margin: '2px 0' }}>
          {entry.name}: {formatLapTime(entry.value)}
        </p>
      ))}
    </div>
  );
}

export default function DriverComparisonChart({ data }) {
  if (!data) return null;

  // Handle single-driver format: { driver, laps, times }
  if (data.driver && data.laps && data.times) {
    const chartData = data.laps.map((lap, i) => ({
      lap,
      [data.driver]: data.times[i],
    }));

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
          📈 {data.title || 'Lap Time Progression'}
        </h4>

        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="lap"
              tick={{ fill: '#8888a0', fontSize: 10, fontFamily: "'JetBrains Mono'" }}
              axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
              tickLine={false}
              label={{
                value: 'Lap',
                position: 'insideBottomRight',
                offset: -5,
                style: { fill: '#555568', fontSize: 10, fontFamily: "'JetBrains Mono'" },
              }}
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
              }}
            />
            <Line
              type="monotone"
              dataKey={data.driver}
              stroke={DRIVER_COLORS[0]}
              strokeWidth={2}
              dot={{ fill: DRIVER_COLORS[0], r: 3 }}
              activeDot={{ r: 5, fill: DRIVER_COLORS[0] }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Multi-driver format: { drivers, laps, datasets }
  if (data.datasets && data.laps) {
    const chartData = data.laps.map((lap, i) => {
      const point = { lap };
      data.datasets.forEach((ds) => {
        point[ds.driver] = ds.values?.[i];
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
          📈 {data.title || 'Lap Time Progression'}
        </h4>

        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="lap"
              tick={{ fill: '#8888a0', fontSize: 10, fontFamily: "'JetBrains Mono'" }}
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
              }}
            />
            {drivers.map((driver, i) => (
              <Line
                key={driver}
                type="monotone"
                dataKey={driver}
                stroke={DRIVER_COLORS[i % DRIVER_COLORS.length]}
                strokeWidth={2}
                dot={{ fill: DRIVER_COLORS[i % DRIVER_COLORS.length], r: 3 }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return null;
}
