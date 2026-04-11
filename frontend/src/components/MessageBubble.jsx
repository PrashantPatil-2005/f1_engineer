/**
 * MessageBubble — Single chat message with markdown rendering + inline charts
 *
 * Renders user questions and AI responses differently.
 * If chart_data is present, renders the appropriate chart below the answer.
 */

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import MetricsBar from './MetricsBar';
import LapTimeChart from './charts/LapTimeChart';
import TyreStrategyChart from './charts/TyreStrategyChart';
import DriverComparisonChart from './charts/DriverComparisonChart';

function RenderChart({ chartData }) {
  if (!chartData || !chartData.type) return null;

  switch (chartData.type) {
    case 'lap_time_comparison':
      return <LapTimeChart data={chartData} />;
    case 'tyre_strategy':
      return <TyreStrategyChart data={chartData} />;
    case 'lap_times':
      return <DriverComparisonChart data={chartData} />;
    default:
      return null;
  }
}

function TypingIndicator() {
  return (
    <div className="typing-indicator">
      <span></span>
      <span></span>
      <span></span>
    </div>
  );
}

export default function MessageBubble({ message }) {
  const { role, content, chartData, metrics, isStreaming } = message;
  const isUser = role === 'user';

  return (
    <div
      className="animate-fade-in-up"
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: '16px',
        padding: '0 8px',
      }}
    >
      <div
        style={{
          maxWidth: isUser ? '70%' : '85%',
          minWidth: '60px',
        }}
      >
        {/* Role label */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginBottom: '6px',
            justifyContent: isUser ? 'flex-end' : 'flex-start',
          }}
        >
          {!isUser && (
            <span
              style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, var(--f1-red), #ff4444)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.6rem',
                flexShrink: 0,
              }}
            >
              🏎
            </span>
          )}
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.65rem',
              fontWeight: 600,
              color: isUser ? 'var(--text-muted)' : 'var(--accent-cyan)',
              textTransform: 'uppercase',
              letterSpacing: '1px',
            }}
          >
            {isUser ? 'You' : 'Race Engineer'}
          </span>
        </div>

        {/* Message body */}
        <div
          className={isUser ? '' : 'racing-stripe'}
          style={{
            padding: isUser ? '12px 16px' : '12px 16px 12px 20px',
            borderRadius: isUser
              ? 'var(--radius-md) var(--radius-md) 4px var(--radius-md)'
              : 'var(--radius-md) var(--radius-md) var(--radius-md) 4px',
            background: isUser
              ? 'linear-gradient(135deg, rgba(0, 210, 255, 0.12), rgba(0, 210, 255, 0.06))'
              : 'var(--bg-card)',
            border: isUser
              ? '1px solid rgba(0, 210, 255, 0.15)'
              : '1px solid var(--border-subtle)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
          }}
        >
          {isUser ? (
            <p
              style={{
                fontSize: '0.9rem',
                color: 'var(--text-primary)',
                lineHeight: 1.5,
              }}
            >
              {content}
            </p>
          ) : (
            <>
              {content ? (
                <div className="markdown-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {content}
                  </ReactMarkdown>
                </div>
              ) : isStreaming ? (
                <TypingIndicator />
              ) : null}

              {/* Inline chart */}
              {chartData && <RenderChart chartData={chartData} />}

              {/* Metrics bar */}
              {metrics && <MetricsBar metrics={metrics} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
