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
 * D-WS-GITPOD-001: Gitpod Flex يستخدم نطاق *.gitpod.dev (ليس *.gitpod.io)
 * مثال: 5000--019e6245-7448-7aac-964e-e9290606bc52.eu-central-1-01.gitpod.dev
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
        host.includes('.gitpod.') ||   // يشمل .gitpod.io و .gitpod.dev
        host.endsWith('.gitpod.dev') || // Gitpod Flex / Ona الجديد
        host.endsWith('.replit.dev') ||
        host.endsWith('.replit.app') ||
        host.endsWith('.janeway.replit.dev')
    );
};

/**
 * يُعيد الـ host الصحيح لـ backend WebSocket في بيئة Gitpod/Ona/Codespaces.
 *
 * المشكلة (D-WS-002): في Gitpod/Ona، كل port له subdomain مختلف:
 *   - Frontend (5000): 5000--<id>.<cluster>.gitpod.dev  (Gitpod Flex/Ona)
 *                   أو 5000-<id>.ws-eu.gitpod.io         (Gitpod Classic)
 *   - Backend  (8000): 8000--<id>.<cluster>.gitpod.dev
 *                   أو 8000-<id>.ws-eu.gitpod.io
 *
 * D-WS-GITPOD-001: Gitpod Flex يستخدم double-dash: <PORT>--<ENV_ID>.<cluster>.gitpod.dev
 * الـ regex /^5000-/ يُطابق كلا النمطين (5000- و 5000--) لأن 5000-- يبدأ بـ 5000-.
 *
 * D-WS-CODESPACES-001: GitHub Codespaces يستخدم نمط <name>-<port>.app.github.dev
 * لكن proxy الـ Codespaces لا يُمرِّر WebSocket upgrade headers بشكل موثوق لـ port 8000.
 * الحل: استخدام window.location.host (port 5000) — server.js يُمرِّر WS إلى localhost:8000.
 * لا نُعيد كتابة الـ port لـ *.app.github.dev.
 *
 * @returns {string | null} host للـ backend WebSocket، أو null للاستخدام window.location.host
 */
export const getCloudBackendHost = () => {
    if (!isBrowser) return null;
    const host = window.location.host;

    // D-WS-CODESPACES-001 / D-WS-GITPOD-002 (ISS-096 — 2026-05-28):
    //
    // GitHub Codespaces AND Gitpod Flex/Ona — لا نُعيد كتابة الـ port.
    // server.js على port 5000 يُمرِّر WebSocket إلى localhost:8000 داخلياً.
    //
    // السبب الجذري لـ ISS-096:
    //   - Gitpod Flex proxy يُغلق الـ WebSocket على port 8000 بعد ~10s idle
    //     (لا يوجد رسائل بين session_ready وأول سؤال).
    //   - الاتصال المباشر بـ 8000--<id>.gitpod.dev يمر عبر Gitpod edge proxy
    //     الذي له idle timeout قصير جداً على ports غير الأساسية.
    //   - port 5000 هو الـ "primary port" في Gitpod — proxy يتسامح معه أكثر.
    //   - server.js يُمرِّر WS upgrade إلى ws://127.0.0.1:8000 داخلياً —
    //     هذا اتصال localhost لا يمر عبر Gitpod proxy → لا idle timeout.
    //
    // القاعدة: كل بيئات cloud (Codespaces + Gitpod + Ona) تستخدم same-host proxy.
    // فقط Replit يحتاج port rewrite لأن server.js لا يعمل هناك.
    if (
        host.endsWith('.app.github.dev') ||
        host.endsWith('.preview.app.github.dev') ||
        host.includes('.gitpod.dev') ||
        host.includes('.gitpod.io')
    ) {
        console.info('[wsUrl] Cloud workspace (Codespaces/Gitpod/Ona) — using same-host proxy (server.js): %s', host);
        return null; // null → getWsBase يستخدم window.location.host (port 5000)
    }

    // Replit: 5000-<id>.replit.dev → 8000-<id>.replit.dev
    // server.js لا يعمل في Replit — الاتصال المباشر بـ port 8000 ضروري.
    if (host.match(/^5000-/) && (host.endsWith('.replit.dev') || host.endsWith('.replit.app') || host.endsWith('.janeway.replit.dev'))) {
        const backendHost = host.replace(/^5000-/, '8000-');
        console.info('[wsUrl] Replit port-prefix rewrite: frontend=%s → backend=%s', host, backendHost);
        return backendHost;
    }

    // Replit (نمط بديل): <name>-5000.<suffix>.replit.dev → <name>-8000.<suffix>.replit.dev
    if (host.match(/-5000\./) && (host.endsWith('.replit.dev') || host.endsWith('.replit.app'))) {
        const backendHost = host.replace(/-5000\./, '-8000.');
        console.info('[wsUrl] Replit port-suffix rewrite: frontend=%s → backend=%s', host, backendHost);
        return backendHost;
    }

    console.warn('[wsUrl] getCloudBackendHost: no port pattern matched for host=%s — falling back to window.location.host', host);
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

    // 3. D-WS-002 / D-WS-CODESPACES-001: Cloud workspace port routing.
    //
    // Gitpod/Ona: كل port له subdomain مختلف → نُعيد كتابة 5000→8000.
    //   Frontend: 5000--<id>.gitpod.dev → Backend: 8000--<id>.gitpod.dev
    //
    // GitHub Codespaces: getCloudBackendHost() يُعيد null عمداً.
    //   → نستخدم window.location.host (port 5000)
    //   → server.js يستقبل WebSocket upgrade ويُمرِّره إلى localhost:8000
    //   هذا أكثر موثوقية من الاتصال المباشر بـ *-8000.app.github.dev
    //   لأن Codespaces proxy لا يُمرِّر WS upgrade headers بشكل موثوق لـ ports غير الأساسية.
    if (isCloudWorkspace()) {
        const backendHost = getCloudBackendHost();
        if (backendHost) {
            console.info('[wsUrl] Cloud workspace — direct backend host:', backendHost);
            return `${wsProtocol}//${backendHost}`;
        }
        // null → استخدم window.location.host (Codespaces: server.js proxy على نفس الـ port)
        console.info('[wsUrl] Cloud workspace — same-host proxy path:', window.location.host);
        return `${wsProtocol}//${window.location.host}`;
    }

    // 4. Local dev: ws://localhost:<BACKEND_PORT> مباشرة
    // Next.js proxy لا يُمرِّر WebSocket upgrade headers.
    // NEXT_PUBLIC_BACKEND_PORT يسمح بتغيير port بدون تعديل الكود.
    // الافتراضي 8000 — يتطابق مع uvicorn في supervisor.sh.
    const localBackendPort = process.env.NEXT_PUBLIC_BACKEND_PORT || '8000';
    const hostname = window.location.hostname; // localhost أو 127.0.0.1
    const localBase = `ws://${hostname}:${localBackendPort}`;
    console.info('[wsUrl] Local dev mode — WS base:', localBase);
    return localBase;
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

        const finalUrl = url.toString();
        // Redact token value from log — show only that it is present
        const safeUrl = finalUrl.replace(/([?&]token=)[^&]+/, '$1[REDACTED]');
        console.info('[wsUrl] buildWsUrl → %s', safeUrl);
        return finalUrl;
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
