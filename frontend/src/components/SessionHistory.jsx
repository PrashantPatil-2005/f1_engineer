/**
 * SessionHistory — Sidebar showing past query sessions
 *
 * Persisted via useSessionHistory hook (localStorage).
 * Clicking a session loads its question into the input.
 */

function formatTime(isoString) {
  try {
    const d = new Date(isoString);
    const now = new Date();
    const diffMs = now - d;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString();
  } catch {
    return '';
  }
}

function truncate(str, len = 55) {
  return str.length > len ? str.slice(0, len) + '...' : str;
}

export default function SessionHistory({ sessions, onSelect, onClear, onDelete }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: '16px 12px',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '16px',
          paddingBottom: '12px',
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        <h3
          style={{
            fontSize: '0.75rem',
            fontWeight: 700,
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '1.5px',
            fontFamily: 'var(--font-mono)',
          }}
        >
          History
        </h3>
        {sessions.length > 0 && (
          <button
            onClick={onClear}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.65rem',
              cursor: 'pointer',
              padding: '2px 6px',
              borderRadius: '4px',
              transition: 'color 0.2s',
            }}
            onMouseEnter={(e) => { e.target.style.color = 'var(--f1-red)'; }}
            onMouseLeave={(e) => { e.target.style.color = 'var(--text-muted)'; }}
          >
            Clear all
          </button>
        )}
      </div>

      {/* Session list */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}
      >
        {sessions.length === 0 ? (
          <p
            style={{
              color: 'var(--text-muted)',
              fontSize: '0.78rem',
              textAlign: 'center',
              marginTop: '32px',
              fontStyle: 'italic',
            }}
          >
            No queries yet.
            <br />
            Ask your first question!
          </p>
        ) : (
          sessions.map((session, i) => (
            <div
              key={session.id}
              onClick={() => onSelect(session.question)}
              style={{
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                background: 'transparent',
                borderLeft: '2px solid transparent',
                animation: `slideInLeft 0.3s ease-out ${i * 0.03}s both`,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-surface)';
                e.currentTarget.style.borderLeftColor = 'var(--accent-cyan)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.borderLeftColor = 'transparent';
              }}
            >
              <p
                style={{
                  fontSize: '0.8rem',
                  color: 'var(--text-primary)',
                  lineHeight: 1.4,
                  marginBottom: '4px',
                }}
              >
                {truncate(session.question)}
              </p>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.65rem',
                    color: 'var(--text-muted)',
                  }}
                >
                  {formatTime(session.timestamp)}
                </span>
                {session.metrics?.total_time && (
                  <span
                    className={`metric-pill ${session.metrics.total_time < 5 ? 'fast' : ''}`}
                    style={{ fontSize: '0.6rem', padding: '1px 5px' }}
                  >
                    {session.metrics.total_time}s
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
