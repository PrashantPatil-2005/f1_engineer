/**
 * MetricsBar — Pipeline timing breakdown display
 *
 * Shows classify, data, retrieval, LLM timing + cache hit status
 * in a compact, mono-font bar below the answer.
 */

export default function MetricsBar({ metrics }) {
  if (!metrics) return null;

  const items = [
    {
      label: 'Total',
      value: `${metrics.total_time}s`,
      highlight: metrics.total_time < 5,
    },
    {
      label: 'Classify',
      value: `${metrics.classify_time}s`,
    },
    {
      label: 'Data',
      value: `${metrics.data_time}s`,
      highlight: metrics.cache_hit,
    },
    {
      label: 'FAISS',
      value: `${metrics.retrieval_time}s`,
    },
    {
      label: 'LLM',
      value: `${metrics.llm_time}s`,
    },
    {
      label: 'Cache',
      value: metrics.cache_hit ? 'HIT' : 'MISS',
      highlight: metrics.cache_hit,
    },
    {
      label: 'Chunks',
      value: metrics.chunks_retrieved,
    },
  ];

  return (
    <div
      className="animate-fade-in"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '6px',
        marginTop: '10px',
        paddingTop: '10px',
        borderTop: '1px solid var(--border-subtle)',
      }}
    >
      {items.map((item, i) => (
        <div
          key={i}
          className={`metric-pill ${item.highlight ? 'fast' : ''}`}
        >
          <span style={{ color: 'var(--text-muted)', marginRight: '4px' }}>
            {item.label}
          </span>
          {item.value}
        </div>
      ))}

      {/* Session info */}
      {metrics.year && metrics.race && (
        <div className="metric-pill" style={{ marginLeft: 'auto' }}>
          <span style={{ color: 'var(--text-muted)', marginRight: '4px' }}>
            📍
          </span>
          {metrics.year} {metrics.race} ({metrics.session || 'R'})
        </div>
      )}
    </div>
  );
}
