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
    return processed;
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
