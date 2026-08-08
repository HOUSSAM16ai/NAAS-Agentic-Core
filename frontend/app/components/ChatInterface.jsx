import React, { useState, useRef, useEffect, useCallback, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { GenerativeUIRenderer } from './generative/GenerativeUIRenderer';
import { preprocessMath, markdownToPlainText } from '../utils/preprocessMath';

// ملاحظة (ISS-105 / D-WS-ORPHAN-001): `preprocessMath` انتقلت إلى وحدة مشتركة
// `app/utils/preprocessMath.js` لإعادة استخدامها في مكوّنات Generative UI عبر
// <MathText>. السلوك هنا بلا تغيير — نستوردها فقط.

// ─── ISS-056/057 (D-049/D-051): LaTeX-Aware Typewriter ─────────────────────
// المشكلة: WebSocket frames تصل في رشقات (machine-gun). حتى مع rAF batching،
// كل frame يعرض ~16ms من الحروف دفعة واحدة → تجربة مرئية مقطعة.
//
// مشكلة إضافية (ISS-057): الكشف حرفاً بحرف قد يكشف `$g` (بدون `$` إقفال)
// لفترة قصيرة → ReactMarkdown يعيد render مع LaTeX غير مكتمل → flicker.
//
// الحل المتقدم:
// 1. عند streaming → كشف بإيقاع ~60fps (~240 char/sec)
// 2. عند الوصول لبداية LaTeX block (`$`, `$$`, `\(`, `\[`) → كشف الـ block
//    كاملاً ذرياً (atomic) في نفس frame → لا flicker
// 3. عند backlog > 800 char → تسارع
// 4. عند `isStreaming=false` → كشف فوري للباقي
// ─────────────────────────────────────────────────────────────────────────────
const TYPEWRITER_CHARS_PER_FRAME = 4;
const TYPEWRITER_INSTANT_THRESHOLD = 800;

/**
 * يحدد طول الـ token الذرّي ابتداءً من index في النص.
 *
 * - LaTeX display `$$...$$` → يُكشف كاملاً
 * - LaTeX inline `$...$` → يُكشف كاملاً
 * - LaTeX delimiters `\(...\)` / `\[...\]` (و الـ double-backslash) → يُكشف كاملاً
 * - عادي → 1 char
 *
 * @param {string} text  النص الكامل
 * @param {number} start المؤشر الذي ينطلق منه
 * @returns {number}     عدد الحروف التي يجب كشفها معاً (>=1)
 */
const atomicTokenLength = (text, start) => {
    if (start >= text.length) return 0;
    const slice = text.slice(start);

    // $$...$$
    if (slice.startsWith('$$')) {
        const end = slice.indexOf('$$', 2);
        if (end !== -1) return end + 2;
    }
    // $...$  (سطر واحد — لا newlines داخله)
    if (slice.startsWith('$') && !slice.startsWith('$$')) {
        const newline = slice.indexOf('\n');
        const end = slice.indexOf('$', 1);
        if (end !== -1 && (newline === -1 || end < newline)) return end + 1;
    }
    // \[...\] أو \\[...\\] (display)
    if (slice.startsWith('\\[')) {
        const end = slice.indexOf('\\]', 2);
        if (end !== -1) return end + 2;
    }
    if (slice.startsWith('\\\\[')) {
        const end = slice.indexOf('\\\\]', 3);
        if (end !== -1) return end + 3;
    }
    // \(...\) أو \\(...\\) (inline)
    if (slice.startsWith('\\(')) {
        const end = slice.indexOf('\\)', 2);
        if (end !== -1) return end + 2;
    }
    if (slice.startsWith('\\\\(')) {
        const end = slice.indexOf('\\\\)', 3);
        if (end !== -1) return end + 3;
    }
    return 1;
};

const useTypewriter = (fullContent, isStreaming) => {
    const [displayed, setDisplayed] = useState(fullContent || '');
    const rafIdRef = useRef(null);

    useEffect(() => {
        const safeFull = fullContent || '';

        if (!isStreaming) {
            if (rafIdRef.current !== null) {
                cancelAnimationFrame(rafIdRef.current);
                rafIdRef.current = null;
            }
            setDisplayed(safeFull);
            return;
        }

        const tick = () => {
            setDisplayed((prev) => {
                if (prev.length >= safeFull.length) {
                    rafIdRef.current = null;
                    return prev;
                }
                const remaining = safeFull.length - prev.length;
                const accel = remaining > TYPEWRITER_INSTANT_THRESHOLD
                    ? Math.max(TYPEWRITER_CHARS_PER_FRAME * 3, Math.ceil(remaining / 30))
                    : TYPEWRITER_CHARS_PER_FRAME;

                // كشف ذرّي لـ LaTeX blocks بحيث لا يُعرض `$g` بدون `$` إقفال أبداً
                let cursor = prev.length;
                let revealed = 0;
                while (revealed < accel && cursor < safeFull.length) {
                    const tokenLen = atomicTokenLength(safeFull, cursor);
                    // إذا كان LaTeX block غير مكتمل بعد في الـ buffer (مثل `$g` فقط)،
                    // ننتظر القطعة التالية بدل كشف نصف delimiter
                    if (tokenLen === 0) break;
                    const nextCursor = cursor + tokenLen;
                    // إذا الـ token الذرّي طويل وفائض عن الـ buffer الفعلي → توقَّف
                    if (nextCursor > safeFull.length) break;
                    cursor = nextCursor;
                    revealed += tokenLen;
                }

                // ضمان تقدم 1 حرف على الأقل (نص عادي) لتجنب التجمد
                if (cursor === prev.length && cursor < safeFull.length) {
                    cursor = prev.length + 1;
                }

                const next = safeFull.slice(0, cursor);
                if (next.length < safeFull.length) {
                    rafIdRef.current = requestAnimationFrame(tick);
                } else {
                    rafIdRef.current = null;
                }
                return next;
            });
        };

        if (rafIdRef.current === null) {
            rafIdRef.current = requestAnimationFrame(tick);
        }

        return () => {
            if (rafIdRef.current !== null) {
                cancelAnimationFrame(rafIdRef.current);
                rafIdRef.current = null;
            }
        };
    }, [fullContent, isStreaming]);

    return displayed;
};

// ─── شارة بطاقة الامتحان ─────────────────────────────────────────────────────
const ExamBadge = memo(() => (
    <div className="exam-badge">
        <i className="fas fa-scroll exam-badge-icon" />
        <span>ورقة امتحان رسمية — بكالوريا الجزائر</span>
    </div>
));
ExamBadge.displayName = 'ExamBadge';

// ─── مكوّن Markdown مع KaTeX فائق الجودة ─────────────────────────────────────
// ISS-073 (2026-05-15): فصل streaming عن rendering لمنع الـ flicker الكارثي.
// المشكلة: ReactMarkdown + rehypeKatex يُعيدان بناء DOM كاملاً عند كل حرف →
//   خطوط تظهر وتختفي + layout يتغير + KaTeX يُعيد رسم المعادلات من الصفر.
// الحل: أثناء streaming → نص خام بسيط (لا Markdown، لا KaTeX).
//        عند الاكتمال → ReactMarkdown + KaTeX مرة واحدة فقط.
const Markdown = memo(({ content, isStreaming = false }) => {
    const safeContent = content || '';

    // أثناء الـ streaming: نص خام بسيط — لا re-render مكلف، لا flicker
    if (isStreaming) {
        return (
            <div className="markdown-content streaming-raw" dir="rtl">
                <span className="streaming-text">{safeContent}</span>
                <span className="streaming-cursor" aria-hidden="true" />
            </div>
        );
    }

    // بعد الاكتمال: ReactMarkdown + KaTeX مرة واحدة فقط
    const processedContent = preprocessMath(safeContent);
    const isExamContent = (
        safeContent.includes('التمرين') &&
        safeContent.includes('بكالوريا') &&
        (safeContent.includes('$$') || safeContent.includes('\\(') || safeContent.includes('\\['))
    );

    return (
        <div className={`markdown-content${isExamContent ? ' exam-content' : ''}`}>
            {isExamContent && <ExamBadge />}
            <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[[rehypeKatex, {
                    throwOnError: false,
                    strict: false,
                    trust: true,
                    macros: {
                        '\\R': '\\mathbb{R}',
                        '\\N': '\\mathbb{N}',
                        '\\Z': '\\mathbb{Z}',
                        '\\C': '\\mathbb{C}',
                    },
                }]]}
                components={{
                    table: ({ children }) => (
                        <div className="math-table-wrapper">
                            <table className="math-table">{children}</table>
                        </div>
                    ),
                    blockquote: ({ children }) => (
                        <blockquote className="md-blockquote">{children}</blockquote>
                    ),
                    hr: () => <hr className="md-hr" />,
                }}
            >
                {processedContent}
            </ReactMarkdown>
        </div>
    );
});
Markdown.displayName = 'Markdown';

// ─── مؤشر الكتابة المتحرك ────────────────────────────────────────────────────
const TypingIndicator = memo(() => (
    <div className="typing-indicator" aria-label="جاري الكتابة...">
        <span /><span /><span />
    </div>
));
TypingIndicator.displayName = 'TypingIndicator';

// ─── مكوّن رسالة واحدة ───────────────────────────────────────────────────────
const MessageBubble = memo(({ msg, idx }) => {
    const [copied, setCopied] = useState(false);

    const isStreaming = msg.role === 'assistant' && !msg.isComplete;
    const isEmpty = !msg.content || msg.content.trim() === '';

    // ISS-078 D-066: حماية ضد فقاعة user فارغة (سبب blue-bar flicker).
    // لو رسالة المستخدم فارغة (race condition قبل send)، تُعرَض كشريط أزرق ضخم.
    // الحل: لا تعرض bubble للـ user الفارغة.
    if (msg.role === 'user' && isEmpty) {
        return null;
    }

    // ISS-076 (2026-05-15) D-064: تجاوز useTypewriter بالكامل لمنع flicker.
    //
    // السبب: عند انتقال `isStreaming` من true → false، useTypewriter كان
    // يبدأ بـ displayed='' (initial state) ثم يستدعي setDisplayed(full)
    // في useEffect → 2 render cycles → الـ DOM يعرض "" ثم "full content"
    // → الواجهة "ترمش" + "خطوط تظهر وتختفي".
    //
    // الحل: عرض المحتوى الكامل مباشرة بعد streaming. لا typewriter effect
    // إضافي (الـ streaming نفسه يُولِّد typewriter طبيعي).
    //
    // ISS-073 (سابق): أثناء streaming → الـ Markdown يعرض raw text (لا ReactMarkdown
    // re-render مكلف، لا KaTeX flicker).
    const contentToShow = msg.role === 'assistant' ? (msg.content || '') : '';

    const handleCopy = useCallback(() => {
        // ننسخ النص الكامل كنصّ نظيف قابل للقراءة — لا markdown/LaTeX خام.
        // (كارثة «النسخ يُظهر أكواد برمجية»: كان ينسخ msg.content الخام.)
        navigator.clipboard.writeText(markdownToPlainText(msg.content)).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    }, [msg.content]);

    // ─────────────────────────────────────────────────────────────────
    // D-230: الكائن سطحٌ أوّل، لا ذيلٌ في فقاعة
    // ─────────────────────────────────────────────────────────────────
    // ‏CLAUDE.md §0.6 المرحلة ١: «الطالب **يتفاعل مع كائنات** لا يقرأ جداراً نصّياً»،
    // والدردشة «سطح تسليم فقط». وكان الكود يقول العكس بنيوياً: الكائن يُصيَّر **داخل**
    // فقاعة الدردشة **بعد** النصّ، فيقرأ الطالب الجدار ثمّ يرى البطاقة إن بقي انتباه.
    // فحصٌ حيّ على الإنتاج قال إن ٩٫٧٪ فقط من الردود تحمل كائناً أصلاً.
    //
    // القلب: حين يحمل الدور كائناً فالكائن **هو** الردّ، والنصّ يصير تعليقاً مساعداً
    // تحته. وحين لا يحمل، يبقى النصّ كما هو تماماً — بلا انحدار لأيّ دورٍ نصّي.
    const hasObject = msg.role === 'assistant' && msg.isComplete && Boolean(msg.uiComponent);

    return (
        <div className={`message ${msg.role}`}>
            <div
                className={`message-bubble${isStreaming ? ' streaming' : ''}${msg.isError ? ' error' : ''}${hasObject ? ' object-first' : ''}`}
                style={{ position: 'relative', paddingBottom: msg.role === 'assistant' ? '28px' : undefined }}
            >
                {/* الكائن أوّلاً حين يوجد — هو الردّ لا زينتُه. */}
                {hasObject && <GenerativeUIRenderer uiComponent={msg.uiComponent} />}

                {msg.role === 'assistant' ? (
                    isEmpty && isStreaming
                        ? <TypingIndicator />
                        : !isEmpty && (
                            <div className={hasObject ? 'message-aside' : undefined}>
                                <Markdown content={contentToShow} isStreaming={isStreaming} />
                            </div>
                        )
                ) : (
                    <span className="user-message-text">{msg.content}</span>
                )}

                {msg.role === 'assistant' && msg.isComplete && !isEmpty && (
                    <button
                        className={`copy-button${copied ? ' copied' : ''}`}
                        onClick={handleCopy}
                        title={copied ? 'تم النسخ!' : 'نسخ النص'}
                        aria-label={copied ? 'تم النسخ' : 'نسخ'}
                    >
                        <i className={copied ? 'fas fa-check' : 'far fa-copy'} />
                    </button>
                )}
            </div>
        </div>
    );
});
MessageBubble.displayName = 'MessageBubble';

// ─── المكوّن الرئيسي ──────────────────────────────────────────────────────────
export const ChatInterface = ({ messages, onSendMessage, status, user }) => {
    const [input, setInput] = useState('');
    const messagesContainerRef = useRef(null);
    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);
    const [autoScroll, setAutoScroll] = useState(true);

    useEffect(() => {
        if (!autoScroll) return;
        const container = messagesContainerRef.current;
        if (!container) return;
        const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 200;
        if (isNearBottom) container.scrollTop = container.scrollHeight;
    }, [messages, autoScroll]);

    const handleScroll = useCallback(() => {
        const container = messagesContainerRef.current;
        if (!container) return;
        const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
        setAutoScroll(isNearBottom);
    }, []);

    useEffect(() => {
        const ta = textareaRef.current;
        if (!ta) return;
        ta.style.height = 'auto';
        ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
    }, [input]);

    const handleSend = useCallback(() => {
        const trimmed = input.trim();
        if (!trimmed) return;
        setAutoScroll(true);
        onSendMessage(trimmed, {});
        setInput('');
        if (textareaRef.current) textareaRef.current.style.height = 'auto';
    }, [input, onSendMessage]);

    const handleKeyDown = useCallback((e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }, [handleSend]);

    const isConnected = status === 'connected';
    const isConnecting = status === 'connecting';
    const hasStreamingMessage = messages.some(m => m.role === 'assistant' && !m.isComplete);

    const QUICK_PROMPTS = [
        'تمرين 2016 الدورة الأولى الموضوع الثاني التمرين الرابع',
        'اعطني تمرين الدوال العددية',
        'اعطني تمرين الاحتمالات 2024',
    ];

    return (
        <div className="chat-container">
            <div className="messages" ref={messagesContainerRef} onScroll={handleScroll}>
                {messages.length === 0 ? (
                    <div className="welcome-screen">
                        <div className="welcome-icon-wrapper">
                            <i className={`fas ${user?.is_admin ? 'fa-brain' : 'fa-graduation-cap'} welcome-icon`} />
                        </div>
                        <h3 className="welcome-title">
                            {user?.is_admin ? 'System Ready' : 'مرحباً بك في CogniForge'}
                        </h3>
                        <p className="welcome-subtitle">
                            {user?.is_admin
                                ? 'The Overmind is listening.'
                                : 'اسألني أي شيء يخص دراستك — رياضيات، فيزياء، علوم.'}
                        </p>
                        {!user?.is_admin && (
                            <div className="quick-prompts">
                                {QUICK_PROMPTS.map((prompt) => (
                                    <button
                                        key={prompt}
                                        className="quick-prompt-btn"
                                        onClick={() => {
                                            setInput(prompt);
                                            textareaRef.current?.focus();
                                        }}
                                    >
                                        <i className="fas fa-bolt" />
                                        {prompt}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                ) : (
                    messages.map((msg, idx) => (
                        <MessageBubble key={msg.id || idx} msg={msg} idx={idx} />
                    ))
                )}
                <div ref={messagesEndRef} />
            </div>

            {!autoScroll && (
                <button
                    className="scroll-to-bottom-btn"
                    onClick={() => {
                        setAutoScroll(true);
                        messagesContainerRef.current?.scrollTo({
                            top: messagesContainerRef.current.scrollHeight,
                            behavior: 'smooth',
                        });
                    }}
                    aria-label="العودة للأسفل"
                >
                    <i className="fas fa-chevron-down" />
                </button>
            )}

            <div className="input-area-wrapper">
                <div className={`input-area${isConnecting ? ' connecting' : ''}`}>
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={isConnecting ? 'جاري الاتصال...' : 'اكتب سؤالك أو اطلب تمريناً...'}
                        rows={1}
                        disabled={isConnecting}
                        aria-label="حقل الإدخال"
                    />
                    <button
                        onClick={handleSend}
                        disabled={!input.trim() || isConnecting}
                        aria-label="إرسال"
                    >
                        {hasStreamingMessage
                            ? <i className="fas fa-circle-notch fa-spin" />
                            : <i className="fas fa-arrow-up" />
                        }
                    </button>
                </div>
                <div className="input-footer">
                    {/* D-230: النجاح صامت. شارة «● متصل» كانت تُعلَن دائماً لتقول «لا
                        شيء يحدث» — وهي النسخة **الثانية** من نفس الشارة (الأولى كانت في
                        الترويسة). يبقى الإعلان عند العطل وحده: لا فشلٌ صامت (§6.5)،
                        ولا احتفاءٌ بالعادي. */}
                    {!isConnected && (
                        <span
                            className={`connection-status ${isConnecting ? 'connecting' : 'offline'}`}
                            role="status"
                        >
                            <span className="status-dot" />
                            {isConnecting ? 'جاري الاتصال...' : 'غير متصل'}
                        </span>
                    )}
                    <span className="input-hint">Enter للإرسال · Shift+Enter لسطر جديد</span>
                </div>
            </div>
        </div>
    );
};
