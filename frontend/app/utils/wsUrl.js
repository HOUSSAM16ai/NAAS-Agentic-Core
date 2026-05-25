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
 * يُعيد الـ host الصحيح لـ backend WebSocket في بيئة Gitpod/Ona/Codespaces.
 *
 * المشكلة (D-WS-002): في Gitpod/Ona، كل port له subdomain مختلف:
 *   - Frontend (5000): 5000-<id>.ws-eu.gitpod.io
 *   - Backend  (8000): 8000-<id>.ws-eu.gitpod.io
 * المتصفح يصل للـ frontend عبر port 5000 subdomain.
 * WebSocket يجب أن يصل للـ backend عبر port 8000 subdomain.
 *
 * @returns {string} host للـ backend WebSocket
 */
export const getCloudBackendHost = () => {
    if (!isBrowser) return null;
    const host = window.location.host; // مثل: 5000-abc123.ws-eu.gitpod.io

    // Gitpod / Ona: استبدل port prefix من 5000 إلى 8000
    if (host.match(/^5000-/)) {
        return host.replace(/^5000-/, '8000-');
    }
    // GitHub Codespaces: استبدل -5000. بـ -8000.
    if (host.match(/-5000\./)) {
        return host.replace(/-5000\./, '-8000.');
    }
    // Replit: نفس النمط
    if (host.match(/^5000-/)) {
        return host.replace(/^5000-/, '8000-');
    }
    return null;
};

/**
 * يبني WebSocket base URL بشكل ديناميكي وآمن.
 *
 * الأولوية:
 * 1. NEXT_PUBLIC_WS_URL (تهيئة صريحة — أعلى أولوية)
 * 2. NEXT_PUBLIC_API_URL (إذا كان HTTP URL)
 * 3. Cloud workspace port mapping (Gitpod/Ona/Codespaces)
 * 4. window.location.host (local dev — Next.js proxy يُمرِّر HTTP لكن ليس WS)
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

    const wsProtocol = httpToWsProtocol(window.location.protocol);

    // 3. D-WS-002: في Gitpod/Ona/Codespaces، كل port له subdomain مختلف.
    // Frontend على 5000-<id>.ws-eu.gitpod.io → Backend على 8000-<id>.ws-eu.gitpod.io
    if (isCloudWorkspace()) {
        const backendHost = getCloudBackendHost();
        if (backendHost) {
            console.info('[wsUrl] Cloud workspace detected — using backend host:', backendHost);
            return `${wsProtocol}//${backendHost}`;
        }
        // إذا لم يُمكن استخراج backend host → استخدم window.location.host
        // (يعمل إذا كان الـ proxy يُمرِّر WebSocket)
        return `${wsProtocol}//${window.location.host}`;
    }

    // 4. Local dev: ws://localhost:<BACKEND_PORT> مباشرة
    // Next.js proxy لا يُمرِّر WebSocket upgrade headers.
    // NEXT_PUBLIC_BACKEND_PORT يسمح بتغيير port بدون تعديل الكود.
    // الافتراضي 8000 — يتطابق مع uvicorn في supervisor.sh.
    const localBackendPort = process.env.NEXT_PUBLIC_BACKEND_PORT || '8000';
    const hostname = window.location.hostname; // localhost أو 127.0.0.1
    return `ws://${hostname}:${localBackendPort}`;
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
