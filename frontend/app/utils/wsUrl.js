/**
 * wsUrl.js — WebSocket URL generation utility
 *
 * ## لماذا هذا الملف موجود؟
 *
 * المشكلة الجذرية (ISS-OFFLINE-001):
 *   - Frontend كان يستخدم `localhost` ثابتاً داخل browser runtime
 *   - Next.js rewrites لا تُمرِّر WebSocket upgrade headers
 *   - في Codespaces/Gitpod: المتصفح يضرب wss://[workspace]/api/chat/ws
 *     → يصل Next.js → يفشل لأن Next.js لا يُمرِّر WS
 *   - VPN غيَّر network path وسمح بالاتصال المباشر → وهم أن المشكلة حُلَّت
 *
 * الحل:
 *   - دائماً استخدم window.location.host (ليس localhost)
 *   - اكتشاف بيئة Codespaces/Gitpod تلقائياً
 *   - ws:// في http، wss:// في https
 *   - دعم NEXT_PUBLIC_WS_URL للتهيئة الصريحة
 *
 * ## قانون معماري (D-WS-001):
 *   ممنوع استخدام localhost داخل browser runtime.
 *   ممنوع hardcode أي port داخل browser runtime.
 *   يجب استخدام window.location.host دائماً.
 */

const isBrowser = typeof window !== 'undefined';

/**
 * يحوِّل بروتوكول HTTP إلى WebSocket المقابل.
 * @param {string} protocol - window.location.protocol
 * @returns {'wss:' | 'ws:'}
 */
export const httpToWsProtocol = (protocol) => {
    if (protocol === 'https:') return 'wss:';
    if (protocol === 'http:') return 'ws:';
    // إذا كان البروتوكول مجهولاً → افترض wss للأمان
    return 'wss:';
};

/**
 * يكتشف ما إذا كانت البيئة Codespaces أو Gitpod.
 * في هذه البيئات، المتصفح يصل عبر proxy خارجي → يجب استخدام
 * window.location.host بدلاً من localhost.
 *
 * @returns {boolean}
 */
export const isCloudWorkspace = () => {
    if (!isBrowser) return false;
    const host = window.location.hostname;
    return (
        host.endsWith('.app.github.dev') ||
        host.endsWith('.preview.app.github.dev') ||
        host.endsWith('.gitpod.io') ||
        host.endsWith('.ws-eu.gitpod.io') ||
        host.includes('.gitpod.') ||
        host.endsWith('.replit.dev') ||
        host.endsWith('.replit.app') ||
        host.endsWith('.janeway.replit.dev')
    );
};

/**
 * يبني WebSocket base URL بشكل ديناميكي وآمن.
 *
 * الأولوية:
 * 1. NEXT_PUBLIC_WS_URL (تهيئة صريحة — أعلى أولوية)
 * 2. NEXT_PUBLIC_API_URL (إذا كان HTTP URL)
 * 3. window.location.host (الافتراضي الآمن)
 *
 * @returns {string} WebSocket base URL (مثل: wss://host أو ws://host:8000)
 */
export const getWsBase = () => {
    if (!isBrowser) return '';

    // 1. تهيئة صريحة عبر env var
    const explicitWsUrl = process.env.NEXT_PUBLIC_WS_URL;
    if (explicitWsUrl) {
        try {
            const parsed = new URL(explicitWsUrl);
            const wsProtocol = httpToWsProtocol(parsed.protocol);
            return `${wsProtocol}//${parsed.host}`;
        } catch {
            console.warn('[wsUrl] Invalid NEXT_PUBLIC_WS_URL:', explicitWsUrl);
        }
    }

    // 2. استخدام NEXT_PUBLIC_API_URL إذا كان HTTP URL
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (apiUrl) {
        try {
            const parsed = new URL(apiUrl);
            const wsProtocol = httpToWsProtocol(parsed.protocol);
            return `${wsProtocol}//${parsed.host}`;
        } catch {
            console.warn('[wsUrl] Invalid NEXT_PUBLIC_API_URL:', apiUrl);
        }
    }

    // 3. الافتراضي الآمن: window.location.host
    // هذا يعمل في جميع البيئات:
    //   - Local dev (localhost:3000 → ws://localhost:3000 → Next.js proxy → 8000)
    //   - Codespaces (xxx.app.github.dev → wss://xxx.app.github.dev)
    //   - Gitpod (xxx.gitpod.io → wss://xxx.gitpod.io)
    //   - Production (example.com → wss://example.com)
    const wsProtocol = httpToWsProtocol(window.location.protocol);
    const host = window.location.host;

    // تحذير في production إذا لم تكن env vars مُعيَّنة
    if (process.env.NODE_ENV === 'production' && !isCloudWorkspace()) {
        console.warn(
            '[wsUrl] NEXT_PUBLIC_WS_URL not set in production. ' +
            'Falling back to window.location.host. ' +
            'Set NEXT_PUBLIC_WS_URL for explicit configuration.'
        );
    }

    return `${wsProtocol}//${host}`;
};

/**
 * يبني WebSocket URL كامل لـ endpoint معين.
 *
 * ISS-WS-001: token يُضاف كـ query param هنا إذا مُرِّر.
 * هذا يضمن وصوله حتى عندما يحذف proxy الـ sec-websocket-protocol header.
 *
 * @param {string} endpoint - المسار النسبي (مثل /api/chat/ws)
 * @param {string} [sessionId] - معرف الجلسة للـ session affinity
 * @param {string} [token] - JWT token للمصادقة (اختياري — يُضاف كـ ?token=)
 * @returns {string} WebSocket URL كامل
 */
export const buildWsUrl = (endpoint, sessionId, token) => {
    if (!isBrowser || !endpoint) return '';

    const base = getWsBase();
    if (!base) return '';

    try {
        const url = new URL(endpoint, base.replace(/^(wss?):\/\//, 'https://'));
        // استبدل البروتوكول بـ ws/wss
        const wsProtocol = httpToWsProtocol(window.location.protocol);
        url.protocol = wsProtocol;

        // أضف session_id للـ session affinity
        if (sessionId) {
            url.searchParams.set('session_id', sessionId);
        }

        // ISS-WS-001: token كـ query param — يعمل عبر كل proxies وشبكات الهاتف.
        // sec-websocket-protocol يُحذف من Codespaces/carrier-NAT/Brave Mobile.
        if (token) {
            url.searchParams.set('token', token);
        }

        return url.toString();
    } catch (err) {
        console.error('[wsUrl] Failed to build WebSocket URL:', { endpoint, base, err });
        return '';
    }
};

/**
 * يُعيد أو يُنشئ session ID ثابت للمتصفح.
 * يُستخدم لـ session affinity في WebSocket connections.
 *
 * @returns {string}
 */
export const getOrCreateSessionId = () => {
    if (!isBrowser) return `ssr-${Date.now()}`;

    try {
        let sessionId = sessionStorage.getItem('cogniforge_ws_session_id');
        if (!sessionId) {
            sessionId =
                typeof crypto !== 'undefined' && crypto.randomUUID
                    ? crypto.randomUUID()
                    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
            sessionStorage.setItem('cogniforge_ws_session_id', sessionId);
        }
        return sessionId;
    } catch {
        // sessionStorage غير متاح (private browsing في بعض المتصفحات)
        return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    }
};
