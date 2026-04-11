/**
 * SuggestedQueries — Clickable query chips shown on empty state
 *
 * Curated F1 questions covering different query types.
 */

const SUGGESTIONS = [
  {
    text: 'Compare Hamilton vs Leclerc in Bahrain 2024',
    icon: '⚔️',
    type: 'comparison',
  },
  {
    text: "What was Verstappen's tyre strategy at Monza 2024?",
    icon: '🛞',
    type: 'strategy',
  },
  {
    text: 'Who won the 2024 British Grand Prix?',
    icon: '🏆',
    type: 'result',
  },
  {
    text: "How were Norris's lap times at Silverstone 2024?",
    icon: '⏱',
    type: 'lap_time',
  },
  {
    text: 'Compare Verstappen vs Norris in Japanese GP 2024',
    icon: '⚔️',
    type: 'comparison',
  },
  {
    text: "Explain Piastri's race strategy at Hungarian GP 2024",
    icon: '🛞',
    type: 'strategy',
  },
  {
    text: 'Who had the fastest lap at Spa 2024?',
    icon: '⏱',
    type: 'lap_time',
  },
  {
    text: 'How did Alonso perform at Monaco 2024?',
    icon: '🏎',
    type: 'general',
  },
];

const typeColors = {
  comparison: 'var(--accent-cyan)',
  strategy: 'var(--accent-amber)',
  result: 'var(--accent-lime)',
  lap_time: 'var(--accent-purple)',
  general: 'var(--text-secondary)',
};

export default function SuggestedQueries({ onSelect, disabled }) {
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '8px',
        justifyContent: 'center',
        maxWidth: '640px',
        margin: '0 auto',
      }}
    >
      {SUGGESTIONS.map((s, i) => (
        <button
          key={i}
          onClick={() => onSelect(s.text)}
          disabled={disabled}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 14px',
            borderRadius: '999px',
            border: '1px solid var(--border-subtle)',
            background: 'var(--bg-surface)',
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font-body)',
            fontSize: '0.8rem',
            cursor: disabled ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s ease',
            opacity: disabled ? 0.5 : 1,
            animation: `fadeInUp 0.4s ease-out ${i * 0.05}s both`,
          }}
          onMouseEnter={(e) => {
            if (!disabled) {
              e.target.style.borderColor = typeColors[s.type] || 'var(--border-accent)';
              e.target.style.color = 'var(--text-primary)';
              e.target.style.background = 'var(--bg-surface-hover)';
              e.target.style.transform = 'translateY(-1px)';
            }
          }}
          onMouseLeave={(e) => {
            e.target.style.borderColor = 'var(--border-subtle)';
            e.target.style.color = 'var(--text-secondary)';
            e.target.style.background = 'var(--bg-surface)';
            e.target.style.transform = 'translateY(0)';
          }}
        >
          <span style={{ fontSize: '0.9rem' }}>{s.icon}</span>
          {s.text}
        </button>
      ))}
    </div>
  );
}
