import React, { useState, useRef, useEffect, useCallback, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

// ─── معالجة رموز LaTeX قبل التصيير ───────────────────────────────────────────
// ISS-057 (D-051): قاعدة المعرفة الرسمية تستخدم \\(...\\) و \\[...\\]
//   (شرطتان مائلتان خلفيتان) لإحاطة الرياضيات المضمَّنة. هذا اصطلاح ملف
//   knowledge_base/ التاريخي (192 موضعاً في bac2016 وحده).
//
//   قبل الإصلاح: `/\\\(([^]*?)\\\)/g` يطابق `\(` (واحد) فقط فيُبقي شرطة
//   فائضة → markdown يراها `\$` = دولار مُهرَّب → KaTeX لا يرسم → نص خام
//   مرئي للطالب (`$g$`, `$\mathbb{R}$`).
//
//   بعد الإصلاح: نُطبِّع أولاً `\\\\(` → `\\(`، ثم نحوِّل `\(...\)` → `$...$`.
//   نفعل نفس الشيء لـ `\\[...\\]` → `$$...$$` (display).
//   يدعم: \(g\) | \\(g\\) | \[...\] | \\[...\\] | $...$ | $$...$$
const preprocessMath = (content) => {
    if (!content) return '';
    let processed = content;
    // 1) قبل أي تحويل: استبدل كل `\\(...\\)` بـ `\(...\)` و `\\[...\\]` بـ `\[...\]`
    //    هذا يُطبِّع الـ double-backslash إلى single قبل أن نشتغل عليها.
    //    نستخدم regex بحذر لتجنب اللمس بـ `\\` خارج delimiters الرياضية.
    processed = processed.replace(/\\\\\(/g, '\\(');
    processed = processed.replace(/\\\\\)/g, '\\)');
    processed = processed.replace(/\\\\\[/g, '\\[');
    processed = processed.replace(/\\\\\]/g, '\\]');

    // 2) حوِّل `\[...\]` → `$$...$$` (display) و `\(...\)` → `$...$` (inline)
    processed = processed.replace(/\\\[([^]*?)\\\]/g, (_, inner) => `$$${inner}$$`);
    processed = processed.replace(/\\\(([^]*?)\\\)/g, (_, inner) => `$${inner}$`);
    return processed;
};

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
const Markdown = memo(({ content, isStreaming = false }) => {
    const safeContent = content || '';
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
            {isStreaming && <span className="streaming-cursor" aria-hidden="true" />}
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

    // ISS-056: للمساعد فقط — typewriter سلس يُجمِّل عرض الـ deltas المتقطعة.
    // المستخدم لا يحتاج typewriter لرسالته الخاصة.
    const displayedContent = useTypewriter(
        msg.role === 'assistant' ? (msg.content || '') : '',
        isStreaming
    );

    const handleCopy = useCallback(() => {
        // ننسخ النص الكامل، ليس النسخة المعروضة جزئياً
        navigator.clipboard.writeText(msg.content).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    }, [msg.content]);

    return (
        <div className={`message ${msg.role}`}>
            <div
                className={`message-bubble${isStreaming ? ' streaming' : ''}${msg.isError ? ' error' : ''}`}
                style={{ position: 'relative', paddingBottom: msg.role === 'assistant' ? '28px' : undefined }}
            >
                {msg.role === 'assistant' ? (
                    isEmpty && isStreaming
                        ? <TypingIndicator />
                        : <Markdown content={displayedContent} isStreaming={isStreaming} />
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
                    <span className={`connection-status ${isConnected ? 'online' : isConnecting ? 'connecting' : 'offline'}`}>
                        <span className="status-dot" />
                        {isConnected ? 'متصل' : isConnecting ? 'جاري الاتصال...' : 'غير متصل'}
                    </span>
                    <span className="input-hint">Enter للإرسال · Shift+Enter لسطر جديد</span>
                </div>
            </div>
        </div>
    );
};
