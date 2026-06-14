// ─── معالجة رموز LaTeX قبل التصيير (وحدة مشتركة) ─────────────────────────────
// ISS-105 (D-WS-ORPHAN-001 — 2026-06-01): استُخرجت من ChatInterface.jsx لإعادة
//   استخدامها في مكوّنات Generative UI (MathExplanationCard / FullExerciseStory…)
//   عبر <MathText>. كانت معرّفة محلياً وغير مُصدَّرة، فكانت تلك المكوّنات تعرض
//   LaTeX خاماً (`h(x)=x+f(x)`, `$$H(x)=…$$`, `\\(\\mathbb{R}\\)`) في بطاقاتها.
//
// ISS-057 (D-051): قاعدة المعرفة الرسمية تستخدم \\(...\\) و \\[...\\]
//   (شرطتان مائلتان خلفيتان) لإحاطة الرياضيات المضمَّنة. هذا اصطلاح ملف
//   knowledge_base/ التاريخي (192 موضعاً في bac2016 وحده).
//
// ISS-060 (D-054): قاعدة المعرفة تستخدم أيضاً `\\command` (مثل `\\lambda`,
//   `\\int`, `\\displaystyle`) داخل الرياضيات. KaTeX يفسِّر `\\` كـ newline
//   (\newline) ويرى `lambda` كنص حر فيرسم الحروف منفصلة `l a m b d a`.
//   لذا نُطبِّع `\\command` → `\command` بعد تطبيع الحدود.
//
//   قبل الإصلاح: `/\\\(([^]*?)\\\)/g` يطابق `\(` (واحد) فقط فيُبقي شرطة
//   فائضة → markdown يراها `\$` = دولار مُهرَّب → KaTeX لا يرسم → نص خام
//   مرئي للطالب (`$g$`, `$\mathbb{R}$`).
//
//   بعد الإصلاح: نُطبِّع أولاً `\\\\(` → `\\(`، ثم نحوِّل `\(...\)` → `$...$`.
//   نفعل نفس الشيء لـ `\\[...\\]` → `$$...$$` (display).
//   يدعم: \(g\) | \\(g\\) | \[...\] | \\[...\\] | $...$ | $$...$$
export const preprocessMath = (content) => {
    if (!content) return '';
    let processed = content;

    // 1) قبل أي تحويل: استبدل كل `\\(...\\)` بـ `\(...\)` و `\\[...\\]` بـ `\[...\]`
    //    هذا يُطبِّع الـ double-backslash إلى single قبل أن نشتغل عليها.
    //    نستخدم regex بحذر لتجنب اللمس بـ `\\` خارج delimiters الرياضية.
    processed = processed.replace(/\\\\\(/g, '\\(');
    processed = processed.replace(/\\\\\)/g, '\\)');
    processed = processed.replace(/\\\\\[/g, '\\[');
    processed = processed.replace(/\\\\\]/g, '\\]');

    // 2) (ISS-060) طبِّع `\\command` → `\command` لكل أوامر LaTeX داخل الرياضيات.
    //    knowledge_base يستخدم double-backslash لكل شيء (`\\lambda`, `\\int`,
    //    `\\displaystyle`, `\\to`, `\\infty`, `\\,`, `\\mathbb{R}`).
    //    KaTeX يفسِّر `\\` كـ `\newline` ويرى `lambda` كنص فيرسم `l a m b d a`.
    //    الـ regex يطابق `\\` متبوعاً بحرف لاتيني (واحد أو أكثر) أو punctuation
    //    LaTeX خاصة (`,;!{}`). لا يلمس `\\\\` (4 backslashes = newline حقيقي).
    processed = processed.replace(/\\\\([a-zA-Z]+|[,;!{}])/g, '\\$1');

    // 3) حوِّل `\[...\]` → `$$...$$` (display) و `\(...\)` → `$...$` (inline)
    processed = processed.replace(/\\\[([^]*?)\\\]/g, (_, inner) => `$$${inner}$$`);
    processed = processed.replace(/\\\(([^]*?)\\\)/g, (_, inner) => `$${inner}$`);

    // 4) (ISS-108 / D-097) حوِّل جداول Markdown إلى أسطر قابلة للقراءة.
    //    المشروع لا يستخدم remark-gfm، فجداول `| ... |` تُعرض خاماً (رموز أنابيب
    //    مكسورة — جزء من «النصوص الغبية» التي اشتكى منها المستخدم). نكتشف كتلة
    //    جدول (صف عناوين متبوع بصف فاصل `|---|`) ونحوّلها إلى عنوان عريض + نقاط،
    //    فتُعرض نظيفة بدل رموز الأنابيب. النص العادي والرياضيات لا يتأثران.
    processed = convertMarkdownTables(processed);
    return processed;
};

// يكشف صف الفاصل في جدول GFM (`|---|:--:|` — أنابيب وشرطات ونقطتان ومسافات فقط).
const _isTableSeparator = (line) =>
    /^\s*\|?[\s:|-]+\|?\s*$/.test(line) && line.includes('-') && line.includes('|');

// يفصل خلايا صف جدول ويُزيل الأنابيب الطرفية.
const _tableCells = (line) =>
    line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());

const convertMarkdownTables = (text) => {
    if (!text || !text.includes('|')) return text;
    const lines = text.split('\n');
    const out = [];
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const next = lines[i + 1];
        if (line.trim().startsWith('|') && next !== undefined && _isTableSeparator(next)) {
            const header = _tableCells(line).filter(Boolean);
            if (header.length) out.push(`**${header.join(' — ')}**`);
            i++; // تخطَّ صف الفاصل
            while (i + 1 < lines.length && lines[i + 1].trim().startsWith('|')) {
                i++;
                const row = _tableCells(lines[i]).filter((c) => c !== '');
                if (row.length) out.push(`- ${row.join(' — ')}`);
            }
        } else {
            out.push(line);
        }
    }
    return out.join('\n');
};

// ─── نسخ نظيف: markdown + LaTeX → نص قابل للقراءة ────────────────────────────
// كارثة «النسخ يُظهر أكواد برمجية»: زرّ النسخ كان ينسخ `msg.content` الخام
// (`$$...$$`, `\frac{}{}`, `\boxed{}`, عناوين `##`, جداول `|...|`, تشديد `**`).
// هذه الدالة تحوّله إلى نص عربي نظيف للطالب. حتمية نقية — قابلة للاختبار بـ node.

const _GREEK = {
    alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', epsilon: 'ε', zeta: 'ζ',
    eta: 'η', theta: 'θ', lambda: 'λ', mu: 'μ', nu: 'ν', xi: 'ξ', pi: 'π',
    rho: 'ρ', sigma: 'σ', tau: 'τ', phi: 'φ', chi: 'χ', psi: 'ψ', omega: 'ω',
    Gamma: 'Γ', Delta: 'Δ', Theta: 'Θ', Lambda: 'Λ', Pi: 'Π', Sigma: 'Σ',
    Phi: 'Φ', Psi: 'Ψ', Omega: 'Ω',
};

const _SYM = {
    times: '×', cdot: '·', div: '÷', pm: '±', mp: '∓', ast: '*',
    leq: '≤', le: '≤', geq: '≥', ge: '≥', neq: '≠', ne: '≠', approx: '≈',
    equiv: '≡', to: '→', rightarrow: '→', Rightarrow: '⇒', leftarrow: '←',
    infty: '∞', sum: '∑', int: '∫', prod: '∏', partial: '∂', nabla: '∇',
    in: '∈', notin: '∉', forall: '∀', exists: '∃', cup: '∪', cap: '∩',
    subset: '⊂', supset: '⊃', emptyset: '∅', angle: '∠', perp: '⊥',
    lim: 'lim', ln: 'ln', log: 'log', sin: 'sin', cos: 'cos', tan: 'tan',
    exp: 'exp', max: 'max', min: 'min', dots: '…', ldots: '…', cdots: '…',
    quad: ' ', qquad: '  ', displaystyle: '', limits: '', left: '', right: '',
};

const _stripLatexCommands = (s) => {
    let t = s;
    t = t.replace(/\\\\/g, ' '); // فاصل السطر في TeX → مسافة
    t = t.replace(/\\left\s*([([{|.])/g, '$1').replace(/\\right\s*([)\]}|.])/g, '$1');
    t = t.replace(/\\[,;:!]/g, ' ').replace(/\\ /g, ' '); // أوامر التباعد
    // \frac{a}{b} → a/b  (يدعم \dfrac/\tfrac)
    t = t.replace(/\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, (_, a, b) => `${a}/${b}`);
    t = t.replace(/\\sqrt\s*\{([^{}]*)\}/g, (_, x) => `√(${x})`);
    t = t.replace(/\\(?:boxed|text|mathrm|operatorname|mathbf|mathit)\s*\{([^{}]*)\}/g, (_, x) => x);
    const _BB = { R: 'ℝ', N: 'ℕ', Z: 'ℤ', Q: 'ℚ', C: 'ℂ' };
    t = t.replace(/\\mathbb\s*\{([RNZQC])\}/g, (_, x) => _BB[x] || x);
    // أمر LaTeX عام → رمز/يوناني/الاسم (الأطول-أولاً يضمنه محرّك الـ regex بالطول)
    t = t.replace(/\\([a-zA-Z]+)/g, (_, name) => {
        if (_SYM[name] !== undefined) return _SYM[name];
        if (_GREEK[name] !== undefined) return _GREEK[name];
        return name; // غير مُعيَّن → احذف الـ backslash، أبقِ الاسم مقروءاً
    });
    t = t.replace(/\^\{([^{}]*)\}/g, (_, x) => `^(${x})`);
    t = t.replace(/_\{([^{}]*)\}/g, (_, x) => `_(${x})`);
    t = t.replace(/[{}]/g, ''); // أقواس الأوامر المتبقية
    return t;
};

export const markdownToPlainText = (content) => {
    if (!content) return '';
    let t = content;
    // 1) طبِّع double-backslash (مثل preprocessMath)
    t = t.replace(/\\\\\(/g, '\\(').replace(/\\\\\)/g, '\\)');
    t = t.replace(/\\\\\[/g, '\\[').replace(/\\\\\]/g, '\\]');
    t = t.replace(/\\\\([a-zA-Z]+|[,;!{}])/g, '\\$1');
    // 2) جداول markdown → أسطر مقروءة
    t = convertMarkdownTables(t);
    // 3) أسوار/شيفرة inline (أبقِ المحتوى)
    t = t.replace(/```[a-zA-Z]*\n?/g, '').replace(/`([^`]*)`/g, '$1');
    // 4) أزل محدّدات الرياضيات (أبقِ المحتوى)
    t = t.replace(/\$\$([^]*?)\$\$/g, (_, x) => x);
    t = t.replace(/\$([^$\n]*?)\$/g, (_, x) => x);
    t = t.replace(/\\\[([^]*?)\\\]/g, (_, x) => x);
    t = t.replace(/\\\(([^]*?)\\\)/g, (_, x) => x);
    // 5) بسّط أوامر LaTeX → Unicode/نص
    t = _stripLatexCommands(t);
    // 6) أزل تنسيق markdown
    t = t.replace(/^\s{0,3}#{1,6}\s+/gm, '');
    t = t.replace(/\*\*([^*]+)\*\*/g, '$1').replace(/__([^_]+)__/g, '$1');
    t = t.replace(/\*([^*\n]+)\*/g, '$1');
    t = t.replace(/^\s*>\s?/gm, '');
    t = t.replace(/^\s*[-*+]\s+/gm, '• ');
    t = t.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1'); // روابط
    t = t.replace(/^\s*[-—_]{3,}\s*$/gm, ''); // hr
    // 7) تنظيف المسافات
    t = t.replace(/[ \t]{2,}/g, ' ').replace(/\n{3,}/g, '\n\n');
    return t.trim();
};

// خيارات KaTeX الموحَّدة عبر التطبيق — مصدر حقيقة واحد.
export const KATEX_OPTIONS = {
    throwOnError: false,
    strict: false,
    trust: true,
    macros: {
        '\\R': '\\mathbb{R}',
        '\\N': '\\mathbb{N}',
        '\\Z': '\\mathbb{Z}',
        '\\C': '\\mathbb{C}',
    },
};
