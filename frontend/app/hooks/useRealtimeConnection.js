/**
 * useRealtimeConnection — WebSocket connection manager
 *
 * ## State Machine
 *
 *   idle → connecting → connected → degraded → reconnecting → offline
 *                                                           ↘ recovered (→ connected)
 *
 * ## Offline Declaration Rules (D-WS-002)
 *   لا يُعلَن عن Offline إلا بعد:
 *   1. WebSocket failure
 *   2. reconnect exhaustion (MAX_RETRIES محاولات)
 *   قبل ذلك: الحالة هي "reconnecting" وليس "offline"
 *
 * ## Heartbeat
 *   ping/pong كل HEARTBEAT_INTERVAL ms للكشف عن stale connections.
 *   إذا لم يصل pong خلال HEARTBEAT_TIMEOUT ms → إعادة الاتصال.
 */

import { useEffect, useRef, useState, useCallback } from "react";

const MAX_BACKOFF = 30000;          // أقصى تأخير بين المحاولات (30 ثانية)
const MAX_RETRIES = 10;             // عدد المحاولات قبل إعلان offline
const FATAL_CODES = new Set([4401, 4403]);
const HEARTBEAT_INTERVAL = 25000;  // ping كل 25 ثانية
const HEARTBEAT_TIMEOUT = 10000;   // انتظر pong لمدة 10 ثوانٍ

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
  const heartbeatIntervalRef = useRef(null);
  const heartbeatTimeoutRef = useRef(null);

  if (connectionIdRef.current === null) {
    connectionIdRef.current =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  // إيقاف heartbeat
  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current);
      heartbeatTimeoutRef.current = null;
    }
  }, []);

  // بدء heartbeat — ping/pong للكشف عن stale connections
  const startHeartbeat = useCallback((ws) => {
    stopHeartbeat();
    heartbeatIntervalRef.current = setInterval(() => {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        stopHeartbeat();
        return;
      }
      try {
        ws.send(JSON.stringify({ type: "ping" }));
      } catch {
        stopHeartbeat();
        return;
      }
      // إذا لم يصل pong خلال HEARTBEAT_TIMEOUT → stale connection
      heartbeatTimeoutRef.current = setTimeout(() => {
        console.warn("[WS] heartbeat timeout — stale connection, forcing reconnect");
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.close(1001, "heartbeat_timeout");
        }
      }, HEARTBEAT_TIMEOUT);
    }, HEARTBEAT_INTERVAL);
  }, [stopHeartbeat]);

  const connect = useCallback(() => {
    if (!wsUrl || !token) return;
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) return;

    // D-WS-002: "reconnecting" بدلاً من "offline" أثناء المحاولات
    setState(retries.current > 0 ? "reconnecting" : "connecting");

    try {
        const wsUrlObj = new URL(wsUrl);

        // ISS-WS-001: token يُرسَل عبر query param فقط.
        // الكود القديم كان يُرسله في ["jwt", token] subprotocol —
        // Codespaces edge proxy وcarrier-NAT وBrave Mobile تحذفه → 4401.
        // query param يعمل عبر كل الشبكات لأنه جزء من URL وليس header.
        if (token) {
            wsUrlObj.searchParams.set("token", token);
        }
        if (!wsUrlObj.searchParams.has("session_id")) {
            wsUrlObj.searchParams.set("session_id", connectionIdRef.current);
        }

        // Log auth transport mode بدون تسريب token value
        const authMode = token ? "query_param" : "none";
        const safeUrl = wsUrlObj.toString().replace(/token=[^&]+/, "token=[REDACTED]");
        console.info(
            `[WS] connecting auth_mode=${authMode} attempt=${retries.current + 1}/${MAX_RETRIES} url=${safeUrl}`
        );

        // لا subprotocols — يُبسِّط الـ handshake ويتجنب رفض proxies
        const ws = new WebSocket(wsUrlObj.toString());
        wsRef.current = ws;

        ws.onopen = () => {
          if (mountedRef.current) {
            const wasReconnect = retries.current > 0;
            retries.current = 0;
            setState(wasReconnect ? "recovered" : "connected");

            // بعد recovery → انتقل إلى connected بعد لحظة قصيرة للـ UI feedback
            if (wasReconnect) {
              setTimeout(() => {
                if (mountedRef.current) setState("connected");
              }, 500);
            }

            // بدء heartbeat للكشف عن stale connections
            startHeartbeat(ws);

            // Flush pending messages
            if (pendingQueue.current.length > 0) {
                console.log(`[WS] Flushing ${pendingQueue.current.length} pending messages`);
                while (pendingQueue.current.length > 0) {
                    const msg = pendingQueue.current.shift();
                    try { ws.send(JSON.stringify(msg)); } catch { /* ignore */ }
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

          // معالجة pong من heartbeat — إلغاء timeout
          if (typeof event.data === "string" && event.data.includes('"type":"pong"')) {
            if (heartbeatTimeoutRef.current) {
              clearTimeout(heartbeatTimeoutRef.current);
              heartbeatTimeoutRef.current = null;
            }
            return;
          }

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

        ws.onerror = (err) => {
          if (mountedRef.current) {
              // degraded وليس offline — onclose سيُقرِّر ما إذا كان يجب إعادة الاتصال
              setState("degraded");
          }
          console.warn("[WS] error", {
            url: ws.url,
            readyState: ws.readyState,
            error: err?.message || "unknown",
          });
        };

        ws.onclose = (e) => {
          if (mountedRef.current) {
             wsRef.current = null;
             stopHeartbeat();

             console.warn("[WS] closed", {
               url: ws.url,
               code: e.code,
               reason: e.reason,
               wasClean: e.wasClean,
             });

             // Fatal auth errors — لا إعادة اتصال
             // D-WS-004: 4401 = token منتهي أو مفقود → يجب إعادة تسجيل الدخول
             //           4403 = صلاحيات غير كافية (admin يحاول customer endpoint)
             if (FATAL_CODES.has(e.code)) {
                 console.warn("[WS] Fatal auth error, stopping reconnection:", e.code, e.reason);
                 setState("auth_error");
                 // أُطلق حدث عالمي ليتمكن الـ UI من إعادة توجيه المستخدم لتسجيل الدخول
                 if (typeof window !== 'undefined') {
                     window.dispatchEvent(new CustomEvent('agent:auth_error', {
                         detail: { code: e.code, reason: e.reason || 'session_expired' }
                     }));
                 }
                 return;
             }

             retries.current += 1;

             // D-WS-002: لا يُعلَن عن Offline إلا بعد استنفاد جميع المحاولات
             if (retries.current >= MAX_RETRIES) {
               console.error(
                 `[WS] Exhausted ${MAX_RETRIES} reconnect attempts — declaring offline. ` +
                 `last_close_code=${e.code} auth_mode=${token ? "query_param" : "none"}`
               );
               setState("offline");
               return; // لا إعادة اتصال تلقائية — المستخدم يحتاج reload
             }

             // أثناء المحاولات: حالة "reconnecting" وليس "offline"
             setState("reconnecting");

             // Exponential backoff مع jitter
             const delay = Math.min(
               Math.pow(2, retries.current - 1) * 500,
               MAX_BACKOFF
             );
             const jitter = Math.floor(Math.random() * 500);

             console.info(`[WS] Reconnecting in ${delay + jitter}ms (attempt ${retries.current}/${MAX_RETRIES})`);
             clearTimeout(reconnectTimeoutRef.current);
             reconnectTimeoutRef.current = setTimeout(connect, delay + jitter);
          }
        };
    } catch (err) {
        console.warn("[WS] Connection failed:", err);
        retries.current += 1;

        if (!mountedRef.current) return;

        // D-WS-002: لا offline إلا بعد exhaustion
        if (retries.current >= MAX_RETRIES) {
            setState("offline");
            return;
        }

        setState("reconnecting");
        const delay = Math.min(Math.pow(2, retries.current - 1) * 500, MAX_BACKOFF);
        const jitter = Math.floor(Math.random() * 500);
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(connect, delay + jitter);
    }
  }, [wsUrl, token, eventNamespace, startHeartbeat, stopHeartbeat]);

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
      stopHeartbeat();
      if (wsRef.current) {
        wsRef.current.close(1000, "component_unmount");
        wsRef.current = null;
      }
      clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect, stopHeartbeat]);

  return { state, sendMessage };
}
