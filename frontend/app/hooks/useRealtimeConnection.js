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
 * @param {string} wsUrl - The WebSocket URL.
 * @param {string} token - The authentication token.
 * @returns {{ state: string, sendMessage: (data: any) => void }}
 */
export function useRealtimeConnection(wsUrl, token, eventNamespace = "default") {
  const wsRef = useRef(null);
  const retries = useRef(0);
  const [state, setState] = useState("idle");
  const mountedRef = useRef(true);
  const reconnectTimeoutRef = useRef(null);
  const pendingQueue = useRef([]);
  const connectionIdRef = useRef(null);
  if (connectionIdRef.current === null) {
    connectionIdRef.current =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  const connect = useCallback(() => {
    if (!wsUrl || !token) return;
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) return;

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

          // Bug A fix: detect HTML error pages (Next.js DevTools 500 bleed).
          // When the backend crashes, Next.js dev server may intercept the 500
          // and stream back a raw HTML page containing <nextjs-portal> or
          // <!DOCTYPE html>. Guard here before JSON.parse so the HTML never
          // reaches the chat renderer as text content.
          if (typeof event.data === "string") {
            const trimmed = event.data.trimStart();
            if (trimmed.startsWith("<") || trimmed.startsWith("<!DOCTYPE")) {
              console.error("[WS] Received HTML instead of JSON — backend 500 error page intercepted by Next.js DevTools. Suppressing HTML bleed.", event.data.slice(0, 200));
              window.dispatchEvent(
                new CustomEvent("agent:notification", {
                  detail: { level: "error", message: "حدث خطأ في الخادم. يرجى المحاولة مرة أخرى." },
                })
              );
              window.dispatchEvent(
                new CustomEvent("agent:event", {
                  detail: {
                    type: "assistant_final",
                    payload: { content: "" },
                    _connection_id: connectionIdRef.current,
                    _event_namespace: eventNamespace,
                  },
                })
              );
              return;
            }
          }

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

             const delay = Math.min(
               2 ** retries.current * 500,
               MAX_BACKOFF
             );

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
  }, [wsUrl, token, eventNamespace]);

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
