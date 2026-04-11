/**
 * useSSE — Custom hook for Server-Sent Events via POST fetch
 *
 * Native EventSource only supports GET, but our /api/ask uses POST.
 * This hook uses fetch() + ReadableStream to parse SSE events.
 *
 * SSE format from backend:
 *   data: {"type": "token", "content": "Max"}
 *   data: {"type": "done", "answer": "...", "chart_data": {...}, "metrics": {...}}
 *   data: {"type": "error", "content": "..."}
 */

import { useState, useCallback, useRef } from 'react';

export function useSSE() {
  const [tokens, setTokens] = useState('');
  const [answer, setAnswer] = useState('');
  const [chartData, setChartData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const reset = useCallback(() => {
    setTokens('');
    setAnswer('');
    setChartData(null);
    setMetrics(null);
    setError(null);
  }, []);

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const sendQuestion = useCallback(async (question) => {
    // Reset state
    reset();
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || `Server error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulated = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE lines: "data: {...}\n\n"
        const lines = buffer.split('\n');
        // Keep the last potentially incomplete line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;

          const jsonStr = trimmed.slice(6); // Remove "data: " prefix
          try {
            const event = JSON.parse(jsonStr);

            switch (event.type) {
              case 'token':
                accumulated += event.content;
                setTokens(accumulated);
                break;

              case 'done':
                setAnswer(event.answer || accumulated);
                setChartData(event.chart_data || null);
                setMetrics(event.metrics || null);
                setIsStreaming(false);
                break;

              case 'error':
                setError(event.content || 'Unknown streaming error');
                setIsStreaming(false);
                break;

              default:
                break;
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        // Cancelled by user
        setIsStreaming(false);
        return;
      }
      setError(err.message || 'Failed to connect to server');
      setIsStreaming(false);
    }
  }, [reset]);

  return {
    tokens,
    answer,
    chartData,
    metrics,
    isStreaming,
    error,
    sendQuestion,
    cancel,
    reset,
  };
}
