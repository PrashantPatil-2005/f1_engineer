/**
 * ChatWindow — Main chat thread with message list + input
 *
 * Manages the conversation state, SSE streaming, and message history.
 * Auto-scrolls to latest message during streaming.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import MessageBubble from './MessageBubble';
import SuggestedQueries from './SuggestedQueries';
import { useSSE } from '../hooks/useSSE';

export default function ChatWindow({ onSessionComplete }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const currentStreamRef = useRef(null);

  const {
    tokens,
    answer,
    chartData,
    metrics,
    isStreaming,
    error,
    sendQuestion,
    cancel,
  } = useSSE();

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(scrollToBottom, [messages, tokens, scrollToBottom]);

  // Update the streaming message in real-time
  useEffect(() => {
    if (isStreaming && tokens && currentStreamRef.current !== null) {
      setMessages((prev) => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
          updated[lastIdx] = {
            ...updated[lastIdx],
            content: tokens,
            isStreaming: true,
          };
        }
        return updated;
      });
    }
  }, [tokens, isStreaming]);

  // Handle stream completion
  useEffect(() => {
    if (!isStreaming && answer && currentStreamRef.current !== null) {
      setMessages((prev) => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
          updated[lastIdx] = {
            ...updated[lastIdx],
            content: answer,
            chartData: chartData,
            metrics: metrics,
            isStreaming: false,
          };
        }
        return updated;
      });

      // Save to session history
      if (onSessionComplete && currentStreamRef.current) {
        onSessionComplete({
          question: currentStreamRef.current,
          answer: answer,
          chartData: chartData,
          metrics: metrics,
        });
      }

      currentStreamRef.current = null;
    }
  }, [isStreaming, answer, chartData, metrics, onSessionComplete]);

  // Handle error
  useEffect(() => {
    if (error && currentStreamRef.current !== null) {
      setMessages((prev) => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
          updated[lastIdx] = {
            ...updated[lastIdx],
            content: `⚠️ **Error:** ${error}`,
            isStreaming: false,
          };
        }
        return updated;
      });
      currentStreamRef.current = null;
    }
  }, [error]);

  const handleSend = useCallback(
    (question) => {
      const q = (question || input).trim();
      if (!q || isStreaming) return;

      // Add user message
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: q },
        { role: 'assistant', content: '', isStreaming: true },
      ]);

      currentStreamRef.current = q;
      setInput('');
      sendQuestion(q);
    },
    [input, isStreaming, sendQuestion]
  );

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestionSelect = (text) => {
    handleSend(text);
  };

  // Set question from sidebar
  const setQuestion = (q) => {
    setInput(q);
    inputRef.current?.focus();
  };

  // Expose setQuestion for parent
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current._setQuestion = setQuestion;
    }
  });

  const isEmpty = messages.length === 0;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        position: 'relative',
      }}
    >
      {/* Messages area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '24px 16px',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {isEmpty ? (
          /* Empty state */
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '32px',
              paddingBottom: '60px',
            }}
          >
            {/* Logo / Title */}
            <div style={{ textAlign: 'center' }} className="animate-fade-in-up">
              <div
                style={{
                  fontSize: '3rem',
                  marginBottom: '12px',
                  filter: 'drop-shadow(0 0 20px rgba(225, 6, 0, 0.3))',
                }}
              >
                🏎
              </div>
              <h2
                style={{
                  fontSize: '1.5rem',
                  fontWeight: 800,
                  background: 'linear-gradient(135deg, var(--text-primary), var(--accent-cyan))',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  marginBottom: '8px',
                }}
              >
                F1 AI Race Engineer
              </h2>
              <p
                style={{
                  color: 'var(--text-secondary)',
                  fontSize: '0.85rem',
                  maxWidth: '400px',
                  lineHeight: 1.5,
                }}
              >
                Ask me anything about Formula 1 races from 2018–2024.
                I analyze real data from FastF1.
              </p>
            </div>

            {/* Suggested queries */}
            <SuggestedQueries onSelect={handleSuggestionSelect} disabled={isStreaming} />
          </div>
        ) : (
          /* Message list */
          <>
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div
        style={{
          padding: '16px 20px',
          borderTop: '1px solid var(--border-subtle)',
          background: 'var(--bg-secondary)',
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: '10px',
            maxWidth: '800px',
            margin: '0 auto',
          }}
        >
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about any F1 race..."
            disabled={isStreaming}
            id="query-input"
            style={{
              flex: 1,
              padding: '12px 16px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              background: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-body)',
              fontSize: '0.9rem',
              outline: 'none',
              transition: 'border-color 0.2s',
            }}
            onFocus={(e) => {
              e.target.style.borderColor = 'var(--accent-cyan)';
            }}
            onBlur={(e) => {
              e.target.style.borderColor = 'var(--border-subtle)';
            }}
          />

          {isStreaming ? (
            <button
              onClick={cancel}
              id="cancel-btn"
              style={{
                padding: '12px 20px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--f1-red)',
                background: 'rgba(225, 6, 0, 0.1)',
                color: 'var(--f1-red)',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s',
                whiteSpace: 'nowrap',
              }}
              onMouseEnter={(e) => {
                e.target.style.background = 'rgba(225, 6, 0, 0.2)';
              }}
              onMouseLeave={(e) => {
                e.target.style.background = 'rgba(225, 6, 0, 0.1)';
              }}
            >
              ■ Stop
            </button>
          ) : (
            <button
              onClick={() => handleSend()}
              disabled={!input.trim()}
              id="send-btn"
              style={{
                padding: '12px 20px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                background: input.trim()
                  ? 'linear-gradient(135deg, var(--f1-red), #ff2222)'
                  : 'var(--bg-surface)',
                color: input.trim() ? '#fff' : 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: input.trim() ? 'pointer' : 'not-allowed',
                transition: 'all 0.2s',
                boxShadow: input.trim() ? 'var(--shadow-glow-red)' : 'none',
                whiteSpace: 'nowrap',
              }}
              onMouseEnter={(e) => {
                if (input.trim()) {
                  e.target.style.transform = 'translateY(-1px)';
                }
              }}
              onMouseLeave={(e) => {
                e.target.style.transform = 'translateY(0)';
              }}
            >
              Send ➜
            </button>
          )}
        </div>

        {/* Powered by line */}
        <p
          style={{
            textAlign: 'center',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.6rem',
            color: 'var(--text-muted)',
            marginTop: '8px',
            letterSpacing: '0.5px',
          }}
        >
          Powered by FastF1 • FAISS
        </p>
      </div>
    </div>
  );
}
