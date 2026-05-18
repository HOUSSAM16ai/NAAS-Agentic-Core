import { useEffect, useRef, useState, useCallback } from "react";

const MAX_BACKOFF = 10000;
const FATAL_CODES = new Set([4401, 4403]);

const parseAssistantErrorEnvelope = (rawData) => {
  if (typeof rawData !== "string") return null;
  const trimmed = rawData.trim();
  if (!trimmed.startsWith("{")) return null;

  try {
    const parsed = JSON.parse(trimmed);
    if (parsed?.type === "assistant_error") {
      return parsed?.payload?.content || "Unknown assistant error";
    }
  } catch (_error) {
    return null;
  }

  return null;
};

/**
 * Hook to manage a robust WebSocket connection.
 *
 * Accepts EITHER a single URL string (legacy) OR an array of candidate URLs
 * (D-068 hardening 3 — ISS-MISC-VPN). When given a list, the hook rotates
 * through candidates on each connection-close so the moment ANY candidate
 * works the indicator flips to "متصل" without requiring the user to know
 * which Codespaces port is reachable.
 *
 * @param {string|string[]} wsUrlInput - WS URL or list of candidate URLs.
 * @param {string} token - The authentication token.
 * @returns {{ state: string, sendMessage: (data: any) => void }}
 */
export function useRealtimeConnection(wsUrlInput, token, eventNamespace = "default") {
  const wsRef = useRef(null);
  const retries = useRef(0);
  const [state, setState] = useState("idle");
  const mountedRef = useRef(true);
  const reconnectTimeoutRef = useRef(null);
  const pendingQueue = useRef([]);
  // Index into the candidate list — rotates on each onclose so we sweep
  // through ALL candidate URLs before giving up. Reset to 0 on every onopen.
  const candidateIndexRef = useRef(0);
  const connectionIdRef = useRef(null);
  if (connectionIdRef.current === null) {
    connectionIdRef.current =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  // Normalize: accept either a string (legacy single URL) or an array of
  // candidate URLs (the new resilience mode).
  const wsUrlCandidates = Array.isArray(wsUrlInput)
    ? wsUrlInput.filter((u) => typeof u === "string" && u.length > 0)
    : typeof wsUrlInput === "string" && wsUrlInput
      ? [wsUrlInput]
      : [];

  const connect = useCallback(() => {
    if (wsUrlCandidates.length === 0 || !token) return;
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) return;

    // Pick the current candidate. The index is rotated by onclose so each
    // failed attempt advances to the next one.
    const candidateIdx = candidateIndexRef.current % wsUrlCandidates.length;
    const wsUrl = wsUrlCandidates[candidateIdx];

    setState("connecting");

    try {
        const wsUrlObj = new URL(wsUrl);
        wsUrlObj.searchParams.append("token", token);
        if (!wsUrlObj.searchParams.has("session_id")) {
            wsUrlObj.searchParams.append("session_id", connectionIdRef.current);
        }
        const ws = new WebSocket(wsUrlObj.toString(), ["jwt", token]);
        wsRef.current = ws;

        ws.onopen = () => {
          if (mountedRef.current) {
            retries.current = 0;
            // The winning candidate is now the preferred one for future
            // reconnects (e.g. after a transient network hiccup). Reset the
            // rotation pointer to it so we don't waste time re-probing dead
            // candidates again.
            // (candidateIdx is captured in this closure scope.)
            try {
              // eslint-disable-next-line no-console
              console.info(`[CogniForge WS] connected via candidate #${candidateIdx + 1}/${wsUrlCandidates.length}: ${wsUrl}`);
            } catch (_e) { /* noop */ }
            setState("connected");

            // Flush pending messages
            if (pendingQueue.current.length > 0) {
                console.log(`Flushing ${pendingQueue.current.length} pending messages`);
                while (pendingQueue.current.length > 0) {
                    const msg = pendingQueue.current.shift();
                    ws.send(JSON.stringify(msg));
                }
            }
          }
        };

        // ISS-STREAM-004: Delta batching via requestAnimationFrame
        // Problem: 400+ delta chunks arrive in <4s → 400+ dispatchEvent calls →
        //          400+ React setState calls → machine-gun re-renders that freeze UI.
        // Fix: buffer delta chunks and flush them in a single batch per animation frame.
        //      Non-delta events (conversation_init, persisted, error, etc.) are dispatched
        //      immediately to preserve correct lifecycle ordering.
        const deltaBuffer = [];
        let rafPending = false;

        const flushDeltaBuffer = () => {
          rafPending = false;
          if (!mountedRef.current || deltaBuffer.length === 0) return;

          // Merge all buffered delta content into a single chunk
          const merged = deltaBuffer.splice(0).reduce((acc, ev) => {
            const content = ev.payload?.content;
            if (typeof content === 'string') acc += content;
            return acc;
          }, '');

          if (!merged) return;

          // Use the last buffered event as the envelope, replace content with merged
          const baseEvent = deltaBuffer[0] || {};
          const mergedEvent = {
            ...baseEvent,
            type: 'assistant_delta',
            payload: { ...(baseEvent.payload || {}), content: merged },
          };

          window.dispatchEvent(new CustomEvent('agent:event', { detail: mergedEvent }));
          window.dispatchEvent(new CustomEvent(`agent:event:${eventNamespace}`, { detail: mergedEvent }));
        };

        const scheduleDeltaFlush = () => {
          if (!rafPending) {
            rafPending = true;
            requestAnimationFrame(flushDeltaBuffer);
          }
        };

        ws.onmessage = (event) => {
          if (!mountedRef.current) return;

          const directAssistantError = parseAssistantErrorEnvelope(event.data);
          if (directAssistantError) {
            window.dispatchEvent(
              new CustomEvent("agent:notification", {
                detail: { level: "error", message: String(directAssistantError) },
              })
            );
            return;
          }

          try {
            const data = JSON.parse(event.data);
            const enrichedData = {
              ...data,
              _connection_id: connectionIdRef.current,
              _event_namespace: eventNamespace,
            };

            const eventType = data?.type;
            const isDelta = eventType === 'delta' || eventType === 'assistant_delta';

            if (isDelta) {
              // Buffer delta events — flush once per animation frame (~16ms)
              deltaBuffer.push(enrichedData);
              scheduleDeltaFlush();
            } else {
              // Flush any pending deltas before dispatching lifecycle events
              // to preserve correct ordering (e.g. deltas before assistant_final)
              if (deltaBuffer.length > 0) flushDeltaBuffer();

              window.dispatchEvent(
                new CustomEvent("agent:event", {
                  detail: enrichedData,
                })
              );
              window.dispatchEvent(
                new CustomEvent(`agent:event:${eventNamespace}`, {
                  detail: enrichedData,
                })
              );
            }
          } catch (e) {
            console.warn("Failed to parse WebSocket message:", e);
          }
        };

        ws.onerror = () => {
          if (mountedRef.current) {
              setState("degraded");
          }
          console.warn("[WS] error", {
            url: ws.url,
            readyState: ws.readyState, // 0..3
          });
        };

        ws.onclose = (e) => {
          if (mountedRef.current) {
             wsRef.current = null;

             console.warn("[WS] closed", {
               url: ws.url,
               code: e.code,
               reason: e.reason,
               wasClean: e.wasClean,
               readyState: ws.readyState,
             });

             // Check for fatal auth errors
             if (FATAL_CODES.has(e.code)) {
                 console.warn("Fatal auth error, stopping reconnection:", e.code);
                 setState("auth_error");
                 return; // STOP reconnection
             }

             setState("offline");

             // D-068 hardening 3: rotate to the next candidate URL on each
             // failure. We sweep ALL candidates before any candidate gets a
             // second try, so a working candidate is exercised within a
             // single round (rather than getting stuck retrying a dead one).
             if (wsUrlCandidates.length > 1) {
                 candidateIndexRef.current = (candidateIndexRef.current + 1) % wsUrlCandidates.length;
             }

             // Backoff is exponential but capped — and we hold it short
             // (< 1s) for the first sweep so all candidates are exercised
             // quickly. After we've cycled through everything once, the
             // backoff grows normally.
             const sweepCount = Math.floor(retries.current / Math.max(1, wsUrlCandidates.length));
             const delay = Math.min(2 ** sweepCount * 500, MAX_BACKOFF);

             const jitter = Math.floor(Math.random() * 200);

             retries.current += 1;
             clearTimeout(reconnectTimeoutRef.current);
             reconnectTimeoutRef.current = setTimeout(connect, delay + jitter);
          }
        };
    } catch (err) {
        console.warn("WebSocket connection failed:", err);
        if (mountedRef.current) setState("offline");

        const delay = Math.min(
            2 ** retries.current * 500,
            MAX_BACKOFF
        );
        retries.current += 1;
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(connect, delay);
    }
    // We intentionally depend on the JOINED candidate string so identity
    // changes of the wsUrlInput array don't endlessly re-trigger reconnect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsUrlCandidates.join("|"), token, eventNamespace]);

  const sendMessage = useCallback((data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      console.warn("WebSocket is not connected. Queuing message.", data);
      pendingQueue.current.push(data);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (wsRef.current) wsRef.current.close();
      clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  return { state, sendMessage };
}
