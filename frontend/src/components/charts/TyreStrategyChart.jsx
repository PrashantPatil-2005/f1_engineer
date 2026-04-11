/**
 * TyreStrategyChart — Horizontal stacked bar chart for tyre strategy timeline
 *
 * Renders when chart_data.type === "tyre_strategy"
 * Shows each driver's stint segments colored by tyre compound.
 */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from 'recharts';

const COMPOUND_COLORS = {
  SOFT: '#ff3333',
  MEDIUM: '#ffd700',
  HARD: '#e0e0e0',
  INTERMEDIATE: '#4caf50',
  WET: '#2196f3',
  UNKNOWN: '#888888',
};

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;

  const data = payload[0]?.payload;
  if (!data) return null;

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
      <p style={{ color: '#f0f0f5', fontWeight: 600, marginBottom: '4px' }}>
        {data.driver}
      </p>
      {data.stints?.map((stint, i) => (
        <p key={i} style={{ color: COMPOUND_COLORS[stint.compound] || '#888', margin: '2px 0' }}>
          Stint {i + 1}: {stint.compound} (Laps {stint.lap_start}–{stint.lap_end})
        </p>
      ))}
    </div>
  );
}

export default function TyreStrategyChart({ data }) {
  if (!data || !data.drivers || data.drivers.length === 0) return null;

  // Find max lap for x-axis
  let maxLap = 0;
  data.drivers.forEach((d) => {
    d.stints?.forEach((s) => {
      if (s.lap_end > maxLap) maxLap = s.lap_end;
    });
  });

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
        🏎 {data.title || 'Tyre Strategy Timeline'}
      </h4>

      {/* Compound Legend */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '12px', flexWrap: 'wrap' }}>
        {Object.entries(COMPOUND_COLORS).filter(([k]) => k !== 'UNKNOWN').map(([compound, color]) => (
          <div key={compound} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <div
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: color,
              }}
            />
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.7rem',
                color: 'var(--text-secondary)',
                textTransform: 'capitalize',
              }}
            >
              {compound.toLowerCase()}
            </span>
          </div>
        ))}
      </div>

      {/* Strategy bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {data.drivers.map((driverData) => (
          <div key={driverData.driver} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {/* Driver label */}
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: 'var(--text-primary)',
                minWidth: '36px',
                textAlign: 'right',
              }}
            >
              {driverData.driver}
            </span>

            {/* Stint bars */}
            <div
              style={{
                flex: 1,
                display: 'flex',
                height: '28px',
                borderRadius: '4px',
                overflow: 'hidden',
                background: 'var(--bg-primary)',
              }}
            >
              {driverData.stints?.map((stint, i) => {
                const width = ((stint.lap_end - stint.lap_start + 1) / maxLap) * 100;
                const compound = stint.compound?.toUpperCase() || 'UNKNOWN';
                return (
                  <div
                    key={i}
                    title={`${compound} — Laps ${stint.lap_start}–${stint.lap_end}`}
                    style={{
                      width: `${width}%`,
                      background: COMPOUND_COLORS[compound] || COMPOUND_COLORS.UNKNOWN,
                      opacity: 0.85,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'opacity 0.2s',
                      cursor: 'pointer',
                      borderRight: i < driverData.stints.length - 1 ? '2px solid var(--bg-primary)' : 'none',
                    }}
                    onMouseEnter={(e) => { e.target.style.opacity = '1'; }}
                    onMouseLeave={(e) => { e.target.style.opacity = '0.85'; }}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        color: compound === 'HARD' ? '#222' : '#fff',
                        textShadow: compound === 'HARD' ? 'none' : '0 1px 2px rgba(0,0,0,0.5)',
                      }}
                    >
                      {width > 8 ? `L${stint.lap_start}-${stint.lap_end}` : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Lap axis */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: '6px',
          marginLeft: '46px',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.65rem',
          color: 'var(--text-muted)',
        }}
      >
        <span>Lap 1</span>
        <span>Lap {Math.round(maxLap / 2)}</span>
        <span>Lap {maxLap}</span>
      </div>
    </div>
  );
}
