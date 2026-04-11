/**
 * useSessionHistory — Persist chat sessions in localStorage
 *
 * Each session: { id, question, answer, chartData, metrics, timestamp }
 * Stores last 50 sessions max.
 */

import { useState, useCallback, useEffect } from 'react';

const STORAGE_KEY = 'f1_engineer_sessions';
const MAX_SESSIONS = 50;

function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveSessions(sessions) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // localStorage full or unavailable
  }
}

export function useSessionHistory() {
  const [sessions, setSessions] = useState(loadSessions);

  // Sync to localStorage on change
  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  const addSession = useCallback((session) => {
    setSessions((prev) => {
      const next = [
        {
          id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
          timestamp: new Date().toISOString(),
          ...session,
        },
        ...prev,
      ].slice(0, MAX_SESSIONS);
      return next;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setSessions([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  const deleteSession = useCallback((id) => {
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  return {
    sessions,
    addSession,
    clearHistory,
    deleteSession,
  };
}
