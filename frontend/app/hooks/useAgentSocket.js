import { useState, useRef, useCallback, useEffect } from 'react';
import { errorTracker } from '../utils/errorTracker';
import { useRealtimeConnection } from './useRealtimeConnection';

const isBrowser = typeof window !== 'undefined';
const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL ?? '';
const WS_ORIGIN = process.env.NEXT_PUBLIC_WS_URL ?? '';

const resolveWebSocketProtocol = (protocol) => {
    if (protocol === 'https:') return 'wss:';
    if (protocol === 'http:') return 'ws:';
    if (protocol === 'wss:' || protocol === 'ws:') return protocol;
    return 'ws:';
};

// ISS-MISC-VPN (2026-05-17, D-068): On cloud-forwarded environments (GitHub
// Codespaces, Gitpod, Ona) the frontend is served at one forwarded port
// (3000 or 5000) and the backend at another (8000). Two failure modes
// stack on top of each other:
//
//   (A) The browser may not be able to REACH the backend's cross-subdomain
//       URL at all — Codespaces sometimes leaves port 8000 with `private`
//       visibility on existing Codespaces, even when devcontainer.json
//       declares it public. Browsers get redirected to GitHub login →
//       WS handshake silently fails → status stuck on "غير متصل".
//
//   (B) Even when port 8000 is reachable, appending ":8000" to the
//       frontend hostname does NOT work (the cloud proxy doesn't accept
//       that syntax — every port gets its own subdomain).
//
// The ROBUST primary path: use SAME-ORIGIN WebSocket so the browser only
// ever talks to port 3000/5000. The Next.js custom server (frontend/server.js)
// proxies `/api/chat/ws` and `/admin/api/chat/ws` to uvicorn locally —
// internal-only, no Codespaces port visibility involved.
//
// The CROSS-SUBDOMAIN translation below is kept as a defensive fallback for
// users who run `next dev:next` (the legacy script) bypassing the custom
// server — in that case port 8000 MUST be public and reachable.
export const BACKEND_PORT = '8000';

const FRONTEND_FORWARDED_PORTS = new Set(['3000', '5000']);

// True iff window.location matches a cloud-forwarded hostname pattern
// (Codespaces / Gitpod). On those, same-origin is preferred because the
// custom Next.js server proxies WS to uvicorn internally.
const isCloudForwardedHostname = (hostname) => {
    if (!hostname || typeof hostname !== 'string') return false;
    return (
        /-\d+\.(?:preview\.)?app\.github\.dev$/.test(hostname) ||
        /^\d+-[\w.-]+\.gitpod\.io$/.test(hostname)
    );
};

export const translateCloudHostnameToBackend = (hostname) => {
    if (!hostname || typeof hostname !== 'string') return null;

    // GitHub Codespaces:
    //   <codespace-name>-<port>.app.github.dev
    //   <codespace-name>-<port>.preview.app.github.dev
    // (The `-<port>` suffix is the only thing the proxy uses to route — name
    // can itself contain hyphens, so we anchor the port-domain tail.)
    const codespaces = hostname.match(
        /^(.+)-(\d+)(\.(?:preview\.)?app\.github\.dev)$/
    );
    if (codespaces) {
        const [, name, , tail] = codespaces;
        return `${name}-${BACKEND_PORT}${tail}`;
    }

    // Gitpod / Ona: <port>-<workspace-id>.<region>.gitpod.io
    const gitpod = hostname.match(/^(\d+)-([\w.-]+\.gitpod\.io)$/);
    if (gitpod) {
        return `${BACKEND_PORT}-${gitpod[2]}`;
    }

    return null;
};

// Diagnostic helper — logs the chosen WS URL once per page load so users
// can verify in DevTools that the fix is active. Stays quiet in production.
let _wsUrlLogged = false;
const logWsResolution = (label, url) => {
    if (_wsUrlLogged || !isBrowser) return;
    _wsUrlLogged = true;
    try {
        // eslint-disable-next-line no-console
        console.info(`[CogniForge WS] ${label}: ${url}`);
    } catch (_e) { /* noop */ }
};

// Returns an ORDERED list of candidate WS bases. The reconnection loop in
// `useRealtimeConnection.js` rotates through these on failure, so the moment
// any one of them works the indicator flips to "متصل" — no manual
// configuration, no VPN, no Codespaces port-visibility flip required.
export const getWsBaseCandidates = () => {
    if (!isBrowser) return [];

    // 0. Explicit env override always wins (single candidate).
    const configuredOrigin = WS_ORIGIN || API_ORIGIN;
    if (configuredOrigin) {
        try {
            const parsed = new URL(configuredOrigin);
            const wsProtocol = resolveWebSocketProtocol(parsed.protocol);
            const url = `${wsProtocol}//${parsed.host}`;
            logWsResolution('using configured origin', url);
            return [url];
        } catch (error) {
            errorTracker.reportError(error, { message: 'Invalid WebSocket base configuration' });
            return [];
        }
    }

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const hostname = window.location.hostname;
    const port = window.location.port;
    const candidates = [];

    if (isCloudForwardedHostname(hostname)) {
        // Cloud (Codespaces / Gitpod). Try BOTH same-origin AND cross-port —
        // either one is enough. Order matters only for the FIRST connect.
        //   a) same-origin (goes through Next.js custom server proxy)
        //   b) cross-port (works if port 8000 is publicly forwarded)
        candidates.push(`${protocol}://${window.location.host}`);
        const cloudBackendHost = translateCloudHostnameToBackend(hostname);
        if (cloudBackendHost) {
            candidates.push(`${protocol}://${cloudBackendHost}`);
        }
    } else if (FRONTEND_FORWARDED_PORTS.has(port)) {
        // Local dev on standard Next.js port → backend on 8000 same host.
        candidates.push(`${protocol}://${hostname}:${BACKEND_PORT}`);
        // Also try same-origin in case the dev proxy is wired up.
        candidates.push(`${protocol}://${window.location.host}`);
    } else {
        // Same-origin fallback (reverse proxy / production).
        candidates.push(`${protocol}://${window.location.host}`);
    }

    logWsResolution(`candidates resolved (${candidates.length})`, candidates.join(' | '));
    return candidates;
};

const getWsBase = () => {
    if (!isBrowser) return '';

    // 1. Explicit env override always wins.
    const configuredOrigin = WS_ORIGIN || API_ORIGIN;
    if (configuredOrigin) {
        try {
            const parsed = new URL(configuredOrigin);
            const wsProtocol = resolveWebSocketProtocol(parsed.protocol);
            const url = `${wsProtocol}//${parsed.host}`;
            logWsResolution('using configured origin', url);
            return url;
        } catch (error) {
            errorTracker.reportError(error, { message: 'Invalid WebSocket base configuration' });
            return '';
        }
    }

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const hostname = window.location.hostname;
    const port = window.location.port;

    // 2. Cloud-forwarded environments: PREFER same-origin so the WS goes
    //    through the Next.js custom server's reverse proxy → uvicorn over
    //    localhost. This sidesteps port-8000 visibility, GitHub auth, and
    //    any browser cross-port quirks. Works even if port 8000 is private.
    if (isCloudForwardedHostname(hostname)) {
        const url = `${protocol}://${window.location.host}`;
        logWsResolution('cloud-forwarded → same-origin (via Next.js proxy)', url);
        return url;
    }

    // 3. Local dev on standard Next.js ports → backend on 8000 same host.
    if (FRONTEND_FORWARDED_PORTS.has(port)) {
        const url = `${protocol}://${hostname}:${BACKEND_PORT}`;
        logWsResolution('local dev → cross-port', url);
        return url;
    }

    // 4. Same-origin fallback (reverse proxy / production).
    const url = `${protocol}://${window.location.host}`;
    logWsResolution('default same-origin', url);
    return url;
};

const buildWebSocketUrlSafe = (baseUrl, endpoint, token) => {
    try {
        const wsUrl = new URL(endpoint, baseUrl);
        // Use a persistent session ID for the browser session
        let sessionId = '';
        if (typeof sessionStorage !== 'undefined') {
            sessionId = sessionStorage.getItem('agent_session_id');
            if (!sessionId) {
                sessionId = typeof crypto !== "undefined" && crypto.randomUUID
                    ? crypto.randomUUID()
                    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
                sessionStorage.setItem('agent_session_id', sessionId);
            }
        } else {
            // Fallback for SSR/non-browser
            sessionId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
        }

        wsUrl.searchParams.append("session_id", sessionId);
        return wsUrl.toString();
    } catch (error) {
        errorTracker.reportError(error, { message: 'Invalid WebSocket URL parts' });
        return '';
    }
};

const generateId = () => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
};

const parseNestedAssistantError = (value) => {
    if (typeof value !== 'string') return null;
    const trimmed = value.trim();
    if (!trimmed.startsWith('{')) return null;

    try {
        const parsed = JSON.parse(trimmed);
        if (parsed && parsed.type === 'assistant_error') {
            const content = parsed?.payload?.content;
            return typeof content === 'string' && content.trim() ? content : 'Unknown assistant error';
        }
    } catch (_error) {
        return null;
    }

    return null;
};

const notifyAgentError = (message) => {
    if (typeof window === 'undefined') return;
    window.dispatchEvent(
        new CustomEvent('agent:notification', {
            detail: {
                level: 'error',
                message,
            },
        })
    );
};

/**
 * دمج محتوى المساعد بشكل صحيح:
 * - إذا كان incoming هو delta حقيقي (قطعة صغيرة) → نُضيفه مباشرة
 * - إذا كان incoming يبدأ بـ current (نص تراكمي من الخادم) → نُرجع incoming
 * - نتجنب التكرار عبر كشف التداخل فقط عند الضرورة
 *
 * ISS-STREAM-001: الإصلاح الجراحي لمشكلة البث الكارثية.
 * السبب الجذري: بعض مسارات الـ fallback ترسل النص التراكمي الكامل
 * بدل delta صغير، مما يُسبب تكرار النص أو استبداله بشكل خاطئ.
 */
const mergeAssistantContent = (existingContent, incomingContent) => {
    const current = typeof existingContent === 'string' ? existingContent : '';
    const incoming = typeof incomingContent === 'string' ? incomingContent : '';

    if (!incoming) return current;
    if (!current) return incoming;

    // الحالة 1: incoming هو نص تراكمي يحتوي على current كاملاً في بدايته
    // → الخادم يُرسل النص الكامل حتى الآن، نُرجعه مباشرة
    if (incoming.startsWith(current)) {
        return incoming;
    }

    // الحالة 2: current يحتوي على incoming كاملاً (chunk قديم وصل متأخراً)
    // → نتجاهل الـ chunk القديم ونحتفظ بالحالي
    if (current.endsWith(incoming)) {
        return current;
    }

    // الحالة 3: delta حقيقي — نُضيفه مباشرة بدون حساب overlap معقد
    // هذا هو المسار الطبيعي لـ token-by-token streaming
    return `${current}${incoming}`;
};

const buildClientContextMessages = (messages, currentQuestion) => {
    const safeMessages = Array.isArray(messages) ? messages : [];
    const normalized = safeMessages
        .filter((item) => item && (item.role === 'user' || item.role === 'assistant'))
        .map((item) => ({
            role: item.role,
            content: typeof item.content === 'string' ? item.content.trim() : '',
        }))
        .filter((item) => item.content.length > 0);

    const questionText = typeof currentQuestion === 'string' ? currentQuestion.trim() : '';
    if (questionText) {
        normalized.push({ role: 'user', content: questionText });
    }

    return normalized.slice(-30);
};

export const useAgentSocket = (endpoint, token, onConversationUpdate) => {
    const [messages, setMessages] = useState([]);
    const [conversationId, setConversationId] = useState(null);
    const onConversationUpdateRef = useRef(onConversationUpdate);
    const activeConversationIdRef = useRef(null);
    const activeRequestIdRef = useRef(null);

    // Construct an ORDERED LIST of WS URLs. The realtime hook rotates
    // through them on connection failure (D-068 hardening 3 — frontend
    // resilience). The moment any one of them works, status flips to
    // "connected" → "متصل" — regardless of which Codespaces port is
    // actually reachable, regardless of whether the custom server is up.
    const [wsUrlCandidates, setWsUrlCandidates] = useState([]);
    useEffect(() => {
        if (!endpoint) {
            setWsUrlCandidates([]);
            return;
        }
        const bases = getWsBaseCandidates();
        const urls = bases
            .map((base) => buildWebSocketUrlSafe(base, endpoint, token))
            .filter(Boolean);
        setWsUrlCandidates(urls);
    }, [endpoint, token]);

    // Use the robust connection hook
    const eventNamespace = endpoint || 'default';
    const { state: status, sendMessage: sendSocketMessage } = useRealtimeConnection(wsUrlCandidates, token, eventNamespace);

    useEffect(() => {
        onConversationUpdateRef.current = onConversationUpdate;
    }, [onConversationUpdate]);

    useEffect(() => {
        activeConversationIdRef.current = conversationId;
    }, [conversationId]);

    const refreshConversationHistory = useCallback(() => {
        if (!onConversationUpdateRef.current) return;
        onConversationUpdateRef.current();
    }, []);

    const addMessage = useCallback((msg) => {
        setMessages(prev => [...prev, msg]);
    }, []);

    const isStreamLifecycleEvent = (eventType) => {
        return (
            eventType === 'delta' ||
            eventType === 'assistant_delta' ||
            eventType === 'assistant_final' ||
            eventType === 'assistant_fallback' ||
            eventType === 'persisted' ||
            eventType === 'complete' ||
            eventType === 'error' ||
            eventType === 'assistant_error'
        );
    };

    // Handle incoming events (decoupled from socket logic)
    useEffect(() => {
        const handler = (e) => {
            const { type, payload } = e.detail || {};
            const incomingConversationId = payload?.conversation_id;
            const incomingRequestId = payload?.request_id;
            const activeConversationId = activeConversationIdRef.current;
            const activeRequestId = activeRequestIdRef.current;
            const hasActiveConversation = activeConversationId !== null && activeConversationId !== undefined;
            const hasIncomingConversation = incomingConversationId !== null && incomingConversationId !== undefined;
            if (hasActiveConversation && hasIncomingConversation) {
                const normalizedActive = Number.parseInt(String(activeConversationId), 10);
                const normalizedIncoming = Number.parseInt(String(incomingConversationId), 10);
                if (
                    !Number.isNaN(normalizedActive) &&
                    !Number.isNaN(normalizedIncoming) &&
                    normalizedActive !== normalizedIncoming
                ) {
                    return;
                }
            }
            // Accept events without request_id for backward compatibility with older gateways.
            // Reject only when both sides have explicit IDs and they mismatch.
            if (
                activeRequestId &&
                incomingRequestId &&
                String(activeRequestId) !== String(incomingRequestId)
            ) {
                return;
            }
            // Defensive gate: if no active request, ignore stray stream events from
            // other conversations/tabs unless they explicitly initialize a conversation.
            if (!activeRequestId && type !== 'conversation_init' && isStreamLifecycleEvent(type)) {
                return;
            }

            if (type === 'conversation_init') {
                if (payload?.conversation_id) {
                    setConversationId(payload.conversation_id);
                }
                refreshConversationHistory();
            } else if (type === 'delta' || type === 'assistant_delta') {
                const content = payload?.content || '';
                if (!content) return;
                const nestedAssistantError = parseNestedAssistantError(content);
                if (nestedAssistantError) {
                    notifyAgentError(nestedAssistantError);
                    return;
                }

                setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last && last.role === 'assistant' && !last.isComplete && !last.isError) {
                        // ISS-STREAM-001: استخدام mergeAssistantContent للتعامل مع كلا المسارين:
                        // 1. delta حقيقي (token صغير) → يُضاف مباشرة
                        // 2. نص تراكمي (fallback يُرسل النص الكامل) → يُستبدل بشكل صحيح
                        const updated = {
                            ...last,
                            content: mergeAssistantContent(last.content, content),
                        };
                        return [...prev.slice(0, -1), updated];
                    } else {
                        // أول delta → ننشئ رسالة مساعد جديدة
                        return [...prev, { id: generateId(), role: 'assistant', content: content, isComplete: false }];
                    }
                });
            } else if (type === 'complete') {
                 activeRequestIdRef.current = null;
                 setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last && last.role === 'assistant') {
                        return [...prev.slice(0, -1), { ...last, isComplete: true }];
                    }
                    return prev;
                });
            } else if (type === 'assistant_final') {
                const content = payload?.content || '';
                const nestedAssistantError = parseNestedAssistantError(content);
                if (nestedAssistantError) {
                    notifyAgentError(nestedAssistantError);
                    return;
                }
                setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last && last.role === 'assistant' && !last.isComplete && !last.isError) {
                        // ISS-STREAM-001: إذا كان content فارغاً (streaming mode)
                        // → نُكمل الرسالة الحالية بدون تغيير المحتوى (الـ deltas كافية)
                        // إذا كان content غير فارغ (fallback mode) → ندمجه بشكل صحيح
                        const newContent = content ? mergeAssistantContent(last.content, content) : last.content;
                        return [...prev.slice(0, -1), { ...last, content: newContent, isComplete: true }];
                    } else if (content) {
                        // لا توجد رسالة مساعد جارية → ننشئ رسالة جديدة كاملة
                        return [...prev, { id: generateId(), role: 'assistant', content: content, isComplete: true }];
                    }
                    // streaming mode انتهى بدون assistant_final content → نُكمل آخر رسالة
                    if (last && last.role === 'assistant' && !last.isComplete) {
                        return [...prev.slice(0, -1), { ...last, isComplete: true }];
                    }
                    return prev;
                });
            } else if (type === 'persisted') {
                refreshConversationHistory();
            } else if (type === 'assistant_fallback') {
                 const content = payload?.content || '';
                 const nestedAssistantError = parseNestedAssistantError(content);
                 if (nestedAssistantError) {
                    notifyAgentError(nestedAssistantError);
                    return;
                 }
                 if (content) {
                    addMessage({ id: generateId(), role: 'assistant', content: content, isComplete: true });
                 }
                 refreshConversationHistory();
            } else if (type === 'error') {
                activeRequestIdRef.current = null;
                const details = payload?.details || 'Unknown error';
                notifyAgentError(String(details));
                refreshConversationHistory();
            } else if (type === 'assistant_error') {
                activeRequestIdRef.current = null;
                const content = payload?.content || 'Unknown assistant error';
                notifyAgentError(String(content));
                refreshConversationHistory();
            }
        };

        const eventName = `agent:event:${eventNamespace}`;
        window.addEventListener(eventName, handler);
        return () => window.removeEventListener(eventName, handler);
    }, [addMessage, refreshConversationHistory, eventNamespace]);

    const sendMessage = useCallback((text, metadata = {}) => {
        if (!text.trim()) return;

        // Optimistic UI update
        addMessage({ id: generateId(), role: 'user', content: text });

        const clientRequestId = generateId();
        activeRequestIdRef.current = clientRequestId;

        let sessionId = undefined;
        if (typeof sessionStorage !== 'undefined') {
            sessionId = sessionStorage.getItem('agent_session_id');
        }

        const payload = {
            question: text,
            client_request_id: clientRequestId,
            client_context_messages: buildClientContextMessages(messages, text),
            session_id: sessionId,
            ...metadata,
        };
        if (conversationId !== null && conversationId !== undefined) {
            const normalizedConversationId = Number.parseInt(String(conversationId), 10);
            payload.conversation_id = Number.isNaN(normalizedConversationId)
                ? conversationId
                : normalizedConversationId;
        }

        // Send via robust connection
        sendSocketMessage(payload);

    }, [conversationId, addMessage, sendSocketMessage, messages]);

    const clearMessages = () => {
        activeRequestIdRef.current = null;
        setMessages([]);
    };
    const setMessagesSafe = (msgs) => setMessages(msgs);

    return {
        messages,
        sendMessage,
        status, // 'idle' | 'connecting' | 'connected' | 'degraded' | 'offline'
        conversationId,
        setConversationId,
        clearMessages,
        setMessages: setMessagesSafe,
        agentStates: {} // Deprecated
    };
};
