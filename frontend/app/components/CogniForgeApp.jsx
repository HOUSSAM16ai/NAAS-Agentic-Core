"use client";

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { errorTracker } from '../utils/errorTracker';
import { useAgentSocket } from '../hooks/useAgentSocket';
import { ChatInterface } from './ChatInterface';
import { BUILD_VERSION } from '../buildVersion';
import { clientLog } from '../utils/clientLog';
import { markdownToPlainText } from '../utils/preprocessMath';
import { readApiError } from '../utils/apiError';
import { computeRefreshDelay, rotateSession } from '../utils/sessionRefresh';

const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL ?? '';
const apiUrl = (path) => `${API_ORIGIN}${path}`;

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false };
    }
    static getDerivedStateFromError(error) { return { hasError: true }; }
    componentDidCatch(error, errorInfo) { errorTracker.reportError(error, { errorInfo, source: "React ErrorBoundary" }); }
    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: '20px', color: 'var(--error-color)', textAlign: 'center' }}>
                    <h2>⚠️ Interface Error</h2>
                    <button onClick={() => window.location.reload()} style={{ padding: '10px 20px', marginTop: '10px', cursor: 'pointer' }}>إعادة تحميل</button>
                </div>
            );
        }
        return this.props.children;
    }
}

const LoginForm = ({ onLogin, onToggle }) => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await fetch(apiUrl('/api/security/login'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            if (res.ok) {
                const data = await res.json();
                onLogin(data.access_token, data.user, data.refresh_token);
            } else {
                setError(await readApiError(res, 'تعذّر تسجيل الدخول.'));
            }
        } catch (e) { setError('تعذّر الاتصال بالخادم. تحقّق من الشبكة وحاول مرّة أخرى.'); }
        finally { setLoading(false); }
    };

    return (
        <div className="login-form">
            <form onSubmit={handleSubmit}>
                <h2>تسجيل الدخول</h2>
                {error && <div className="error-message">{error}</div>}
                <div className="input-group"><input type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="البريد الإلكتروني" required /></div>
                <div className="input-group"><input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="كلمة المرور" required /></div>
                <button disabled={loading} style={{width: '100%', padding: '0.75rem', backgroundColor: 'var(--primary-color)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer'}}>{loading ? '...' : 'دخول'}</button>
            </form>
            <div className="toggle-form"><a onClick={onToggle}>إنشاء حساب جديد</a></div>
        </div>
    );
};

const RegisterForm = ({ onToggle, onLogin }) => {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await fetch(apiUrl('/api/security/register'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ full_name: name, email, password })
            });
            if (res.ok) {
                const loginRes = await fetch(apiUrl('/api/security/login'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });
                if (loginRes.ok) {
                    const data = await loginRes.json();
                    onLogin(data.access_token, data.user, data.refresh_token);
                } else {
                    onToggle();
                }
            } else {
                setError(await readApiError(res, 'فشل إنشاء الحساب.'));
            }
        } catch (e) { setError('تعذّر الاتصال بالخادم. تحقّق من الشبكة وحاول مرّة أخرى.'); }
        finally { setLoading(false); }
    };

    return (
        <div className="register-form">
            <form onSubmit={handleSubmit}>
                <h2>إنشاء حساب</h2>
                {error && <div className="error-message">{error}</div>}
                <div className="input-group"><input value={name} onChange={e=>setName(e.target.value)} placeholder="الاسم الكامل" required /></div>
                <div className="input-group"><input value={email} onChange={e=>setEmail(e.target.value)} placeholder="البريد الإلكتروني" required /></div>
                <div className="input-group"><input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="كلمة المرور" required /></div>
                <button disabled={loading} style={{width: '100%', padding: '0.75rem', backgroundColor: 'var(--primary-color)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer'}}>{loading ? '...' : 'تسجيل'}</button>
            </form>
            <div className="toggle-form"><a onClick={onToggle}>لديك حساب بالفعل؟ تسجيل الدخول</a></div>
        </div>
    );
};

const AuthScreen = ({ onLogin }) => {
    const [isLogin, setIsLogin] = useState(true);
    return (
        <div className="login-container">
            {isLogin ? <LoginForm onLogin={onLogin} onToggle={() => setIsLogin(false)} /> : <RegisterForm onToggle={() => setIsLogin(true)} onLogin={onLogin} />}
        </div>
    );
};

const DashboardLayout = ({ user, token, onLogout }) => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    // ISS-066 (D-058): lazy initializer يقرأ localStorage مباشرة عند أول render
    // لتجنب flash: لا نبدأ بـ 'dark' ثم نُحدِّث — نبدأ بالقيمة الصحيحة فوراً.
    const [theme, setTheme] = useState(() => {
        if (typeof window === 'undefined') return 'dark';
        return localStorage.getItem('theme') === 'light' ? 'light' : 'dark';
    });
    const [conversations, setConversations] = useState([]);
    const menuRef = useRef(null);

    const endpoint = user.is_admin ? '/admin/api/chat/ws' : '/api/chat/ws';
    const convEndpoint = user.is_admin ? '/admin/api/conversations' : '/api/chat/conversations';
    const historyEndpoint = user.is_admin ? (id) => `/admin/api/conversations/${id}` : (id) => `/api/chat/conversations/${id}`;
    // ISS-097 (D-WS-KICK-001): نقطة استرجاع آخر محادثة — تُستخدم لاستعادة
    // السياق عند التحميل بدل بدء "محادثة جديدة" فارغة في كل دخول.
    const latestEndpoint = user.is_admin ? '/admin/api/chat/latest' : '/api/chat/latest';
    const didRestoreRef = useRef(false);

    const fetchConversations = useCallback(async () => {
         try {
             const res = await fetch(apiUrl(`${convEndpoint}?limit=50`), {
                 headers: { 'Authorization': `Bearer ${token}` }
             });
             if (res.ok) {
                const rawItems = await res.json();
                const items = Array.isArray(rawItems) ? rawItems : [];
                const uniqueMap = new Map();
                items.forEach((item) => {
                    const key = String(item?.conversation_id ?? '');
                    if (!key) return;
                    if (!uniqueMap.has(key)) {
                        uniqueMap.set(key, item);
                    }
                });
                setConversations(Array.from(uniqueMap.values()).slice(0, 50));
             }
         } catch (e) { errorTracker.reportError(e); }
    }, [convEndpoint]);

    useEffect(() => {
        fetchConversations();
    }, [fetchConversations]);

    const { messages, sendMessage, status, conversationId, setConversationId, clearMessages, setMessages } = useAgentSocket(endpoint, token, fetchConversations);

    const loadConversation = async (id) => {
        setIsSidebarOpen(false);
        setConversationId(id);
        try {
            const res = await fetch(apiUrl(historyEndpoint(id)), {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setMessages(data.messages || []);
                setConversationId(data.conversation_id);
            }
        } catch (e) { errorTracker.reportError(e); }
    };

    const handleNewChat = () => {
        // ISS-097: المستخدم اختار محادثة جديدة صراحةً — علِّم didRestoreRef
        // حتى لا يُعيد effect الاسترجاع تحميل آخر محادثة فوق اختياره.
        didRestoreRef.current = true;
        clearMessages();
        setConversationId(null);
        setConversations([]);
        setIsSidebarOpen(false);
        setIsMenuOpen(false);
    };

    // ISS-097 (D-WS-KICK-001): استعادة آخر محادثة عند التحميل.
    // الكارثة: DashboardLayout كان يبدأ دائماً بـ conversationId=null + رسائل
    // فارغة، فبعد أي دخول (أول دخول أو إعادة دخول بعد طرد) يجد المستخدم نفسه
    // في "محادثة جديدة" فارغة — وهو نصف شكوى المستخدم الحرفية.
    // الحل: مرة واحدة عند التحميل، إن لم تكن هناك محادثة نشطة، نجلب آخر محادثة
    // (/latest) ونحمِّلها. غير حرج: عند الفشل أو غياب محادثة سابقة نبقى في
    // محادثة جديدة (مستخدم جديد). guard بـ didRestoreRef يمنع الكتابة فوق
    // اختيار المستخدم (محادثة جديدة / فتح محادثة من القائمة).
    useEffect(() => {
        if (didRestoreRef.current) return;
        didRestoreRef.current = true;
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch(apiUrl(latestEndpoint), {
                    headers: { 'Authorization': `Bearer ${token}` },
                });
                if (!res.ok || cancelled) return;
                const data = await res.json();
                if (cancelled || !data || data.conversation_id === undefined || data.conversation_id === null) {
                    return;
                }
                setMessages(data.messages || []);
                setConversationId(data.conversation_id);
            } catch (e) {
                // non-fatal — نبقى في محادثة جديدة فارغة
                errorTracker.reportError(e, { message: 'Failed to restore latest conversation' });
            }
        })();
        return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [latestEndpoint, token]);

    // ISS-066: localStorage قُرئ في useState lazy initializer — لا حاجة لـ useEffect هنا.

    useEffect(() => {
        if (typeof document === 'undefined') return;
        // ISS-066 (D-058): theme switching — triple application للموثوقية القصوى.
        // 1. html.dataset.theme — CSS selectors html[data-theme='light'] تعمل
        // 2. body.dataset.theme — fallback دفاعي لـ body[data-theme='light']
        // 3. colorScheme — يُخبر المتصفح بالـ theme لـ scrollbars + form controls
        // 4. localStorage — يحفظ الاختيار للـ anti-flash script عند التحميل التالي
        const root = document.documentElement;
        root.dataset.theme = theme;
        root.dir = 'rtl';
        root.style.colorScheme = theme;
        if (document.body) {
            document.body.dataset.theme = theme;
        }
        localStorage.setItem('theme', theme);
    }, [theme]);

    useEffect(() => {
        const handleOutsideClick = (event) => {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                setIsMenuOpen(false);
            }
        };
        document.addEventListener('mousedown', handleOutsideClick);
        return () => document.removeEventListener('mousedown', handleOutsideClick);
    }, []);

    // كارثة «نسخ كامل الواجهة يُظهر سلسلة طويلة من الأكواد البرمجية»:
    // تحديد الكل (Ctrl+A) ثم النسخ كان يجمع مصدر LaTeX/markup الخام عبر كل الرسائل.
    // طبقة أمان عامة: نعترض كل حدث `copy` على الوثيقة وننظّف التحديد عبر
    // markdownToPlainText (يزيل محدّدات الرياضيات وأوامر LaTeX ورموز markdown).
    // لا نتدخّل في حقول الإدخال، ولا نغيّر شيئاً إن كان التحديد نظيفاً أصلاً.
    useEffect(() => {
        const handleCopy = (event) => {
            const active = document.activeElement;
            const tag = active && active.tagName ? active.tagName.toLowerCase() : '';
            if (tag === 'input' || tag === 'textarea' || (active && active.isContentEditable)) {
                return;
            }
            const selected = window.getSelection ? String(window.getSelection() || '') : '';
            if (!selected) return;
            let cleaned;
            try {
                cleaned = markdownToPlainText(selected);
            } catch {
                return;
            }
            if (cleaned && cleaned !== selected && event.clipboardData) {
                event.clipboardData.setData('text/plain', cleaned);
                event.preventDefault();
            }
        };
        document.addEventListener('copy', handleCopy);
        return () => document.removeEventListener('copy', handleCopy);
    }, []);

    // ISS-067 (D-059): زر الـ theme مرئي دائماً في الـ header — لا يحتاج فتح القائمة.
    // الإصلاح الجذري: نقل الزر من القائمة المنسدلة إلى الـ header مباشرة.
    const handleToggleTheme = () => {
        setTheme((prevTheme) => (prevTheme === 'dark' ? 'light' : 'dark'));
        setIsMenuOpen(false);
    };

    // D-230: «متصل» و«تعافى» حالتان صحّيتان — لا تُعلَنان. ما عداهما يُعلَن.
    const isHealthyConnection = status === 'connected' || status === 'recovered';

    const getStatusText = (st) => {
        switch (st) {
            case 'connected':    return 'متصل';
            case 'recovered':    return 'متصل';
            case 'connecting':   return 'جاري الاتصال...';
            case 'reconnecting': return 'إعادة الاتصال...';
            case 'degraded':     return 'اتصال ضعيف';
            case 'offline':      return 'غير متصل';
            case 'auth_error':   return 'انتهت الجلسة';
            case 'disconnected': return 'غير متصل';
            case 'error':        return 'خطأ في الاتصال';
            default:             return st || 'غير متصل';
        }
    };

    return (
        <div className="app-container">
            <div className="header">
                <div className="header-title">
                    <h2>
                        {user.is_admin ? 'ETAALIM · CLI' : 'ETAALIM'}
                        {/* D-230: النجاح صامت. شارةُ «● متصل» الخضراء كانت تشغل انتباهاً
                            دائماً لتقول «لا شيء يحدث» — والانتباه أندر ما يملكه طالبٌ
                            قبل البكالوريا. يبقى الإعلان **عند العطل وحده**، فلا يُخفى
                            فشلٌ (§6.5: لا فشل صامت) ولا يُحتفى بالعادي. */}
                        {!isHealthyConnection && (
                            <span className="header-status" role="status">
                                <span className="status-offline">{getStatusText(status)}</span>
                            </span>
                        )}
                    </h2>
                </div>
                <div className="header-actions" ref={menuRef}>
                    {/* ISS-067: زر الـ theme مرئي دائماً — لا يحتاج فتح القائمة */}
                    <button
                        className="header-theme-btn"
                        onClick={handleToggleTheme}
                        title={theme === 'dark' ? 'الوضع النهاري' : 'الوضع المظلم'}
                        aria-label={theme === 'dark' ? 'تفعيل الوضع النهاري' : 'تفعيل الوضع المظلم'}
                    >
                        <i className={`fas ${theme === 'dark' ? 'fa-sun' : 'fa-moon'}`}></i>
                    </button>
                    <button
                        className="header-menu-btn"
                        onClick={() => setIsMenuOpen((prev) => !prev)}
                        aria-label="القائمة"
                    >
                        <i className="fas fa-ellipsis-v"></i>
                    </button>
                    {isMenuOpen && (
                        <div className="header-menu">
                            <button className="header-menu-item" onClick={handleNewChat}>
                                <i className="fas fa-plus"></i>
                                <span>محادثة جديدة</span>
                            </button>
                            <button className="header-menu-item" onClick={() => { fetchConversations(); setIsSidebarOpen(true); }}>
                                <i className="fas fa-history"></i>
                                <span>المحادثات السابقة</span>
                            </button>
                            <button className="header-menu-item" onClick={handleToggleTheme}>
                                <i className={`fas ${theme === 'dark' ? 'fa-sun' : 'fa-moon'}`}></i>
                                <span>{theme === 'dark' ? 'الوضع النهاري' : 'الوضع المظلم'}</span>
                            </button>
                            <button className="header-menu-item" onClick={onLogout}>
                                <i className="fas fa-sign-out-alt"></i>
                                <span>تسجيل الخروج</span>
                            </button>
                        </div>
                    )}
                </div>
            </div>

            <div className="dashboard-layout">
                {/* D-230: «فريق العملاء» (لوحة مراحل الوكلاء) حُذف بالكامل مع خطّافه
                    ومكوّنه — لا كود ميت (سابقة D-173 Stage 5: القدرة بلا مستهلكٍ حيّ
                    تُحذَف لا تُترَك stub). وهو داخليّ الطبيعة: الطالب يتعلّم الاحتمالات،
                    ولا يعنيه أيّ وكيلٍ يعمل الآن — عرضُه تسريبٌ لهندسة التعليم (D-117). */}

                <div className={`sidebar-overlay ${isSidebarOpen ? 'visible' : ''}`} onClick={() => setIsSidebarOpen(false)}></div>
                <div
                    className={`sidebar ${isSidebarOpen ? 'open' : ''}`}
                    inert={!isSidebarOpen || undefined}
                >
                     <div className="sidebar-header">
                        <h3>المحادثات</h3>
                        <button className="close-sidebar-btn" onClick={() => setIsSidebarOpen(false)} style={{background:'none', border:'none', fontSize:'1.2rem', cursor:'pointer'}}>
                            <i className="fas fa-times"></i>
                        </button>
                     </div>
                     <div className="conversation-list">
                         {conversations.map(conv => (
                             <div
                                 key={conv.conversation_id}
                                 className={`conversation-item ${conversationId === conv.conversation_id ? 'active' : ''}`}
                                 onClick={() => loadConversation(conv.conversation_id)}
                             >
                                 <i className="fas fa-comment-alt"></i>
                                 {conv.title || `محادثة ${String(conv.conversation_id).slice(0, 8)}...`}
                             </div>
                         ))}
                     </div>
                </div>

                <div className="chat-area">
                    <ChatInterface
                        messages={messages}
                        onSendMessage={sendMessage}
                        status={status}
                        user={user}
                    />
                </div>
            </div>
        </div>
    );
};

const App = () => {
    const [token, setToken] = useState(null);
    const [user, setUser] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    // ISS-101 (D-WS-PROXY-003): إعادة تحميل ذاتية عند قِدَم الـ bundle.
    //
    // الكارثة: تبويب متصفح حمّل JS قديماً (قبل الإصلاحات) يبقى يُشغّله ويُسبب
    // الطرد/التأرجح، حتى بعد تحديث الخادم. الحل: نقارن إصدار الـ bundle المُجمَّع
    // (BUILD_VERSION) مع build.json الذي يُقدّمه الخادم (يعكس الإصدار الحالي).
    // عند الاختلاف → التبويب قديم → إعادة تحميل واحدة (محروسة بـ sessionStorage
    // لمنع الحلقات) لجلب الكود الجديد. هذا يجعل أي تبويب قديم يُصلِح نفسه.
    useEffect(() => {
        let cancelled = false;
        const checkBuild = async () => {
            try {
                const res = await fetch(`/build.json?ts=${Date.now()}`, { cache: 'no-store' });
                if (!res.ok || cancelled) return;
                const data = await res.json();
                const serverBuild = data && data.build;
                if (serverBuild && serverBuild !== BUILD_VERSION) {
                    const key = `cf_reloaded_${serverBuild}`;
                    if (sessionStorage.getItem(key)) return; // سبق وأعدنا التحميل لهذا الإصدار
                    sessionStorage.setItem(key, '1');
                    console.warn(
                        `[App] stale bundle (loaded=${BUILD_VERSION}, server=${serverBuild}) — reloading once`
                    );
                    window.location.reload();
                }
            } catch (_e) {
                /* الشبكة/ملف غير متاح — تجاهل، لا نُعيد التحميل بلا داعٍ */
            }
        };
        checkBuild();
        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        const storedToken = localStorage.getItem('token');
        if (storedToken) setToken(storedToken);
        else setIsLoading(false);
    }, []);

    // D-WS-004 (rev. D-WS-SESSION-001 — 2026-05-26): استمع لـ auth_error من useRealtimeConnection.
    //
    // المستخدم اشتكى من نمط "kick → return" حيث يخرج إلى صفحة الدخول ثم يعود
    // وحده. السبب: 4401 يُطلق logout() الذي يستدعي window.location.reload() —
    // فالصفحة تُحمَّل، يفرغ localStorage، ويظهر AuthScreen.
    //
    // الإصلاح:
    // 1. JWT cap رُفع إلى 480 دقيقة (8 ساعات) في development (crypto.py).
    //    هذا يحل سبب 4401 الأكثر شيوعاً (انتهاء الـ token بعد 30 دقيقة).
    // 2. هنا، نُعطي المستخدم تنبيهاً واضحاً قبل reload — لا "kick صامت".
    //    رسالة Arabic واضحة + 2 ثانية تأخير ليرى المستخدم ما يحدث.
    useEffect(() => {
        const handleAuthError = (e) => {
            console.warn('[App] WS auth error received — session expired:', e.detail);
            clientLog('auth_error_received', { detail: JSON.stringify(e.detail || {}) });
            // أعلِم المستخدم بالحادث قبل reload — صدق في الـ UX
            try {
                window.dispatchEvent(new CustomEvent('agent:notification', {
                    detail: {
                        level: 'warning',
                        message: 'انتهت جلستك. يرجى تسجيل الدخول مرة أخرى.',
                    },
                }));
            } catch (_e) { /* notification non-fatal */ }
            // أعطِ المستخدم لحظتين ليرى الرسالة قبل reload
            setTimeout(() => logout(), 2000);
        };
        window.addEventListener('agent:auth_error', handleAuthError);
        return () => window.removeEventListener('agent:auth_error', handleAuthError);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (!token) {
            setIsLoading(false);
            return;
        }

        // ISS-099 (D-WS-KICK-002 — 2026-05-29): التحقق من المستخدم عبر HTTP /me
        // يجب أن يُسجِّل الخروج **فقط** عند 401/403 (token مؤكَّد البطلان) —
        // تماماً مثل بوابة الـ WebSocket (D-WS-KICK-001).
        //
        // الكارثة المُصلَحة: الكود القديم كان يستدعي logout() على **أي** فشل
        // (5xx، 404، timeout، خطأ شبكة). في بيئة Supabase، الـ backend يُعاد
        // تشغيله أحياناً (health-monitor بعد 3 إخفاقات)، أو يتأخر، أو يخطئ
        // proxy الـ Codespaces لحظياً → /me يُرجع 502/503/خطأ شبكة → logout()
        // → طرد إلى صفحة الدخول رغم أن الـ token صالح تماماً → دخول → محادثة
        // جديدة. الحل: 401/403 فقط تُسجِّل الخروج؛ أي فشل آخر = عابر → نُبقي
        // الجلسة، نعرض المستخدم المُخزَّن مؤقتاً، ونُعيد المحاولة بـ backoff.
        let cancelled = false;
        let attempt = 0;
        let retryTimer = null;

        // استرجاع المستخدم المُخزَّن مؤقتاً فوراً حتى لا نسقط إلى شاشة الدخول
        // أثناء فشل عابر لـ /me. وجود مستخدم مُخزَّن ⇒ نعرض التطبيق فوراً
        // ونتحقّق في الخلفية (لا شاشة تحميل أبدية لو كان /me متعثراً).
        try {
            const cachedRaw = localStorage.getItem('cogniforge_user');
            if (cachedRaw) {
                if (!user) setUser(JSON.parse(cachedRaw));
                setIsLoading(false);
            }
        } catch (_e) { /* cache غير صالح — تجاهل */ }

        const validate = async () => {
            try {
                const response = await fetch(apiUrl('/api/security/user/me'), {
                    headers: { 'Authorization': `Bearer ${token}` },
                });
                if (cancelled) return;
                if (response.ok) {
                    const u = await response.json();
                    setUser(u);
                    try {
                        localStorage.setItem('cogniforge_user', JSON.stringify(u));
                    } catch (_e) { /* تخزين غير متاح — غير قاتل */ }
                    setIsLoading(false);
                    return;
                }
                if (response.status === 401 || response.status === 403) {
                    // token مؤكَّد البطلان — هذا هو المسار الوحيد للخروج.
                    clientLog('fetchUser_logout', { me_status: response.status, attempt });
                    logout();
                    return;
                }
                // 5xx / 404 / غير ذلك → خلل backend عابر — لا تُسجِّل الخروج.
                clientLog('fetchUser_transient', { me_status: response.status, attempt });
                scheduleRetry();
            } catch (error) {
                if (cancelled) return;
                // خطأ شبكة → عابر — لا تُسجِّل الخروج.
                clientLog('fetchUser_network_error', { err: String(error).slice(0, 120), attempt });
                errorTracker.reportError(error, { message: 'Failed to fetch user (transient)' });
                scheduleRetry();
            }
        };

        const scheduleRetry = () => {
            // لا نحجب الواجهة: لو لدينا مستخدم (مُخزَّن مؤقتاً) نعرض التطبيق
            // ونُعيد المحاولة في الخلفية. لو لا مستخدم بعد، نبقى على شاشة
            // التحميل حتى نجاح /me أو 401/403.
            attempt += 1;
            if (attempt > 40) return; // توقّف صامت — تبقى الجلسة بالمستخدم المُخزَّن
            const delay = Math.min(1000 * 2 ** Math.min(attempt, 5), 30000);
            retryTimer = setTimeout(() => {
                if (!cancelled) validate();
            }, delay);
        };

        validate();
        return () => {
            cancelled = true;
            if (retryTimer) clearTimeout(retryTimer);
        };
    }, [token]);

    const handleLogin = (newToken, userData, newRefreshToken) => {
        localStorage.setItem('token', newToken);
        try {
            if (userData) localStorage.setItem('cogniforge_user', JSON.stringify(userData));
            // D-236: رمز التحديث كان يصل الواجهة ويُرمى. قاعدة الإنتاج قالت ذلك
            // بالأرقام: 135 رمزاً و135 عائلة — أي صفر تدوير.
            if (newRefreshToken) localStorage.setItem('refresh_token', newRefreshToken);
        } catch (_e) { /* غير قاتل */ }
        setToken(newToken);
        setUser(userData);
    };

    const logout = () => {
        // D-WS-AUTH-001 (2026-05-26): استخدام React state بدلاً من window.location.reload().
        // قبل: reload() كان يكسر React tree و يُسبب cycle مع auto-fill المتصفح.
        // بعد: setToken(null) + setUser(null) يُعيد render إلى AuthScreen بدون
        //      destructive page reload — يحفظ tab state ويمنع loop.
        clientLog('logout', { stack: (new Error().stack || '').split('\n').slice(1, 4).join(' | ').slice(0, 300) });
        localStorage.removeItem('token');
        try {
            localStorage.removeItem('cogniforge_user');
            localStorage.removeItem('refresh_token');
        } catch (_e) { /* غير قاتل */ }
        setToken(null);
        setUser(null);
        // لا reload — التغيير في state يكفي لإظهار AuthScreen.
    };

    // ── D-236 · التدوير الصامت ────────────────────────────────────────────────
    //
    // قبل هذا: عمرُ رمز الوصول **هو** عمر الجلسة. ينتهي فيُطرَد الطالب إلى صفحة
    // الدخول في منتصف تمرين، والعلاج المُطبَّق سابقاً كان **إطالة العمر** — وهو
    // علاجٌ يزيد المرض: رمزٌ مسروق يبقى صالحاً أطول. الصحيح رمزٌ قصير **يُجدَّد
    // قبل موته**، وهو ما يفعله `/api/v1/auth/refresh` بتدوير العائلة وكشف
    // إعادة الاستعمال (`TokenManager.revoke_family`).
    //
    // ⚠️ الفشل يُميَّز ولا يُعمَّم: 401/403 ⇒ الجلسة انتهت قطعاً ⇒ خروج. أمّا
    // الشبكة و5xx فعابرةٌ ⇒ إعادةُ محاولة — وطردُ طالبٍ بسبب انقطاعٍ لحظي هو
    // عطب D-WS-KICK-001 نفسه في ثوبٍ جديد.
    useEffect(() => {
        if (!token) return undefined;

        let cancelled = false;
        let timer = null;

        const schedule = (currentToken, attempt = 0) => {
            const base = computeRefreshDelay(currentToken);
            if (base === null) return; // بلا `exp` لا نُجدول — ولا نخمّن.
            // تراجعٌ أُسّي على الأعطاب العابرة، بسقفٍ يمنع الانتظار الأبدي.
            const delay = attempt === 0 ? base : Math.min(30000 * 2 ** (attempt - 1), 300000);
            timer = setTimeout(async () => {
                if (cancelled) return;
                const stored = localStorage.getItem('refresh_token');
                if (!stored) return; // جلسةٌ قديمة سبقت التدوير — تُترك لعمرها.
                const result = await rotateSession({ refreshToken: stored, apiUrl });
                if (cancelled) return;
                if (result.ok) {
                    clientLog('session_rotated', { status: 'ok' });
                    handleLogin(result.tokens.access_token, user, result.tokens.refresh_token);
                    return;
                }
                if (result.terminal) {
                    clientLog('session_rotation_terminal', { status: String(result.status) });
                    logout();
                    return;
                }
                clientLog('session_rotation_retry', { status: String(result.status), attempt });
                schedule(currentToken, attempt + 1);
            }, delay);
        };

        schedule(token);
        return () => {
            cancelled = true;
            if (timer) clearTimeout(timer);
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [token]);

    if (isLoading) return <div className="loading-screen"><i className="fas fa-circle-notch fa-spin"></i><h2>جاري تهيئة النظام...</h2></div>;
    if (!token || !user) return <AuthScreen onLogin={handleLogin} />;

    return <DashboardLayout user={user} token={token} onLogout={logout} />;
};

export default function CogniForgeApp() {
    return (
        <ErrorBoundary>
            <App />
        </ErrorBoundary>
    );
}
