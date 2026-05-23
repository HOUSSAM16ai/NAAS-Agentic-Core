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

const getWsBase = () => {
    if (!isBrowser) return '';
    const configuredOrigin = WS_ORIGIN || API_ORIGIN;
    if (configuredOrigin) {
        try {
            const parsed = new URL(configuredOrigin);
            const wsProtocol = resolveWebSocketProtocol(parsed.protocol);
            return `${wsProtocol}//${parsed.host}`;
        } catch (error) {
            errorTracker.reportError(error, { message: 'Invalid WebSocket base configuration' });
            return '';
        }
    }

    // Warn if falling back in production
    if (process.env.NODE_ENV === 'production') {
        console.warn('CRITICAL: NEXT_PUBLIC_WS_URL or NEXT_PUBLIC_API_URL is missing in production. Falling back to window.location, which may cause connection failures.');
    }

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const hostname = window.location.hostname;
    const port = window.location.port;

    // Smart fallback: if we are on port 3000 (standard Next.js), assume backend is on port 8000
    // This fixes local production builds or direct access bypassing Nginx where backend is on default port
    if (port === '3000') {
         return `${protocol}://${hostname}:8000`;
    }

    const host = window.location.host;
    return `${protocol}://${host}`;
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

    // Construct WebSocket URL only on the client to avoid SSR/client mismatch
    const [wsUrl, setWsUrl] = useState(null);
    useEffect(() => {
        const wsBase = getWsBase();
        const url = wsBase && endpoint ? buildWebSocketUrlSafe(wsBase, endpoint, token) : null;
        setWsUrl(url);
    }, [endpoint, token]);

    // Use the robust connection hook
    const eventNamespace = endpoint || 'default';
    const { state: status, sendMessage: sendSocketMessage } = useRealtimeConnection(wsUrl, token, eventNamespace);

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
            } else if (type === 'ui_component') {
                // Generative UI: حدث مكوّن React تفاعلي يُبثّ بالتوازي مع النص.
                // نُنشئ رسالة مساعد مستقلة تحمل وصف المكوّن (component/props/fallbackText).
                // isComplete:true → تُصيَّر فوراً ولا تحجب زر الإرسال، وأول delta
                // نصّي لاحق يُنشئ رسالة نصية منفصلة (لا يندمج مع فقاعة المكوّن).
                const component = payload?.component;
                const props = payload?.props;
                const fallbackText = payload?.fallback_text || 'تعذّر عرض المكوّن.';
                if (typeof component === 'string' && component) {
                    setMessages(prev => [
                        ...prev,
                        {
                            id: generateId(),
                            role: 'assistant',
                            content: '',
                            isComplete: true,
                            uiComponent: {
                                component,
                                props: props && typeof props === 'object' ? props : {},
                                fallbackText: String(fallbackText),
                            },
                        },
                    ]);
                }
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
                // ui_component: payload بصري من Math Pipeline — يُرفق بالرسالة المكتملة
                const uiComponent = payload?.ui_component || null;
                setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last && last.role === 'assistant' && !last.isComplete && !last.isError) {
                        // ISS-STREAM-001: إذا كان content فارغاً (streaming mode)
                        // → نُكمل الرسالة الحالية بدون تغيير المحتوى (الـ deltas كافية)
                        // إذا كان content غير فارغ (fallback mode) → ندمجه بشكل صحيح
                        const newContent = content ? mergeAssistantContent(last.content, content) : last.content;
                        return [...prev.slice(0, -1), { ...last, content: newContent, isComplete: true, uiComponent }];
                    } else if (content) {
                        // لا توجد رسالة مساعد جارية → ننشئ رسالة جديدة كاملة
                        return [...prev, { id: generateId(), role: 'assistant', content: content, isComplete: true, uiComponent }];
                    }
                    // streaming mode انتهى بدون assistant_final content → نُكمل آخر رسالة
                    if (last && last.role === 'assistant' && !last.isComplete) {
                        return [...prev.slice(0, -1), { ...last, isComplete: true, uiComponent }];
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

    // ISS-080 (D-068, 2026-05-18): تطبيع رسائل التاريخ القادمة من الـ backend.
    // الكارثة: عند فتح محادثة قديمة، `CustomerMessageOut`/`MessageResponse` لا
    // يحويان حقل `isComplete`. النتيجة في `ChatInterface.jsx`:
    //   - `hasStreamingMessage = messages.some(m => m.role==='assistant' && !m.isComplete)`
    //     يُرجع true (لأن `!undefined === true`) → زر الإرسال يبقى دائرة تدور
    //     بدل سهم الإرسال → المستخدم لا يستطيع إرسال أي رسالة.
    //   - `isStreaming = msg.role==='assistant' && !msg.isComplete` يصبح true →
    //     `Markdown` يدخل الفرع streaming-raw → LaTeX يظهر كنص خام (`\[ x^{2} \]`
    //     بدل المعادلة المُصيَّرة).
    //
    // الحل: عند `setMessages` للتاريخ، نضمن لكل رسالة assistant أن
    // `isComplete: true` (هي تاريخية → مكتملة بالتعريف)، و نولِّد `id` لو ناقص.
    const setMessagesSafe = useCallback((msgs) => {
        if (!Array.isArray(msgs)) {
            setMessages([]);
            return;
        }
        const normalized = msgs.map((msg) => {
            if (!msg || typeof msg !== 'object') return msg;
            const next = { ...msg };
            if (next.id === undefined || next.id === null) {
                next.id = generateId();
            }
            // كل رسالة قادمة من التاريخ مكتملة بالتعريف. علِّمها صراحةً
            // فقط لرسائل المساعد (assistant) — رسائل المستخدم لا تحتاج العلم.
            if (next.role === 'assistant' && next.isComplete !== true) {
                next.isComplete = true;
            }
            return next;
        });
        setMessages(normalized);
    }, []);

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
