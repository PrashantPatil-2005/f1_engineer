/**
 * App — Root layout: sidebar + chat window
 *
 * F1 AI Race Engineer — Phase 2 Frontend
 */

import { useState, useCallback, useEffect } from 'react';
import ChatWindow from './components/ChatWindow';
import SessionHistory from './components/SessionHistory';
import { useSessionHistory } from './hooks/useSessionHistory';

export default function App() {
  const { sessions, addSession, clearHistory, deleteSession } = useSessionHistory();
  const getIsMobile = () => (typeof window !== 'undefined' ? window.innerWidth <= 900 : false);
  const [isMobile, setIsMobile] = useState(getIsMobile);
  const [sidebarOpen, setSidebarOpen] = useState(!getIsMobile());
  const [chatKey, setChatKey] = useState(0);

  useEffect(() => {
    const onResize = () => {
      const mobile = getIsMobile();
      setIsMobile(mobile);
      setSidebarOpen((prev) => (mobile ? prev : true));
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  useEffect(() => {
    const keepAliveUrl =
      import.meta.env.VITE_KEEP_ALIVE_URL ||
      `${window.location.origin}/api/health`;

    const ping = () => {
      fetch(keepAliveUrl, { cache: 'no-store' })
        .then(() => console.log('keep-alive pinged'))
        .catch((err) => {
          console.error('keep-alive ping failed:', err);
        });
    };
    ping();
    const interval = window.setInterval(ping, 45000);
    return () => window.clearInterval(interval);
  }, []);

  const handleSessionComplete = useCallback(
    (session) => {
      addSession(session);
    },
    [addSession]
  );

  const handleSelectHistory = useCallback((question) => {
    // Focus chat input and set question
    const input = document.getElementById('query-input');
    if (input) {
      // Use native setter to trigger React onChange
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value'
      ).set;
      nativeInputValueSetter.call(input, question);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.focus();
    }
  }, []);

  const handleNewChat = useCallback(() => {
    setChatKey((k) => k + 1);
  }, []);

  return (
    <div
      className="grid-bg"
      style={{
        display: 'flex',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
      }}
    >
      {/* Sidebar */}
      <aside
        style={{
          width: isMobile ? '280px' : sidebarOpen ? '280px' : '0px',
          minWidth: isMobile ? '280px' : sidebarOpen ? '280px' : '0px',
          background: 'var(--bg-secondary)',
          borderRight: sidebarOpen || !isMobile ? '1px solid var(--border-subtle)' : 'none',
          transition: 'all 0.3s ease',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          position: isMobile ? 'fixed' : 'relative',
          left: 0,
          top: 0,
          bottom: 0,
          transform: isMobile ? (sidebarOpen ? 'translateX(0)' : 'translateX(-100%)') : 'none',
          zIndex: isMobile ? 40 : 'auto',
        }}
      >
        {/* Sidebar header */}
        <div
          style={{
            padding: '16px 12px',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          {/* Brand */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '12px',
            }}
          >
            <span
              style={{
                fontSize: '1.3rem',
                filter: 'drop-shadow(0 0 8px rgba(225, 6, 0, 0.4))',
              }}
            >
              🏎
            </span>
            <div>
              <h1
                style={{
                  fontSize: '0.85rem',
                  fontWeight: 800,
                  background: 'linear-gradient(135deg, var(--f1-red), #ff4444)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  lineHeight: 1.2,
                }}
              >
                F1 RACE
              </h1>
              <h1
                style={{
                  fontSize: '0.85rem',
                  fontWeight: 800,
                  color: 'var(--text-primary)',
                  lineHeight: 1.2,
                }}
              >
                ENGINEER
              </h1>
            </div>
          </div>

          {/* Red line accent */}
          <div className="redline" style={{ marginBottom: '12px' }} />

          {/* New chat button */}
          <button
            onClick={handleNewChat}
            id="new-chat-btn"
            style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-accent)',
              background: 'rgba(0, 210, 255, 0.05)',
              color: 'var(--accent-cyan)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
            onMouseEnter={(e) => {
              e.target.style.background = 'rgba(0, 210, 255, 0.1)';
            }}
            onMouseLeave={(e) => {
              e.target.style.background = 'rgba(0, 210, 255, 0.05)';
            }}
          >
            + New Query
          </button>
        </div>

        {/* Session history */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <SessionHistory
            sessions={sessions}
            onSelect={handleSelectHistory}
            onClear={clearHistory}
            onDelete={deleteSession}
          />
        </div>

        {/* Sidebar footer */}
        <div
          style={{
            padding: '12px',
            borderTop: '1px solid var(--border-subtle)',
            textAlign: 'center',
          }}
        >
          <p
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--text-muted)',
              letterSpacing: '0.5px',
            }}
          >
            v2.0 • 2018–2024 Seasons
          </p>
        </div>
      </aside>

      {/* Main content */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          position: 'relative',
        }}
      >
        {/* Top bar */}
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: isMobile ? '10px 12px' : '10px 20px',
            borderBottom: '1px solid var(--border-subtle)',
            background: 'rgba(17, 17, 24, 0.8)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            zIndex: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Sidebar toggle */}
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              id="sidebar-toggle"
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: '1.1rem',
                padding: '4px',
                borderRadius: '4px',
                transition: 'color 0.2s',
                display: 'flex',
                alignItems: 'center',
              }}
              onMouseEnter={(e) => { e.target.style.color = 'var(--text-primary)'; }}
              onMouseLeave={(e) => { e.target.style.color = 'var(--text-secondary)'; }}
              title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
            >
              {sidebarOpen ? '◁' : '▷'}
            </button>

            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: isMobile ? '0.62rem' : '0.7rem',
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '1.5px',
              }}
            >
              Race Analysis Console
            </span>
          </div>

          {/* Status indicator */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <div
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: 'var(--accent-lime)',
                boxShadow: '0 0 6px var(--accent-lime)',
              }}
            />
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.65rem',
                color: 'var(--text-muted)',
                display: isMobile ? 'none' : 'inline',
              }}
            >
              CONNECTED
            </span>
          </div>
        </header>

        {/* Chat window */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <ChatWindow
            key={chatKey}
            onSessionComplete={handleSessionComplete}
          />
        </div>
      </main>

      {isMobile && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.35)',
            zIndex: 30,
          }}
        />
      )}
    </div>
  );
}
