"use client";

/**
 * MathText — تصيير نص قصير يحوي LaTeX داخل مكوّنات Generative UI.
 *
 * ISS-105 (D-WS-ORPHAN-001 — 2026-06-01): مكوّنات Generative UI
 * (MathExplanationCard / FullExerciseStory…) كانت تُصيّر حقولها النصية
 * (step.content / intuition / hint / pedagogical_message) كـ `{text}` خام بلا
 * أي معالجة LaTeX، فيرى الطالب `h(x)=x+f(x)`, `$$H(x)=…$$`, `\\(\\mathbb{R}\\)`
 * كرموز خام داخل البطاقات. هذا المكوّن يمرّر النص عبر نفس خط أنابيب
 * ChatInterface (`preprocessMath` → ReactMarkdown + remark-math + rehype-katex)
 * فتُرسَم الرياضيات عبر KaTeX. النص العادي (تسميات عربية ملموسة) يمرّ كما هو.
 *
 * الفصل المعماري محفوظ: الخلفية تُخرج نصاً/Pydantic فقط — التصيير هنا.
 */

import React, { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { preprocessMath, KATEX_OPTIONS } from '../../utils/preprocessMath';

// إلغاء غلاف <p> الذي يضيفه ReactMarkdown كي يبقى النص inline داخل العناوين/التسميات.
const INLINE_COMPONENTS = {
    p: ({ children }) => <>{children}</>,
};

/**
 * @param {object}  props
 * @param {string}  props.children  النص الخام (قد يحوي LaTeX)
 * @param {string=} props.className صنف CSS اختياري للحاوية
 * @param {boolean=} props.block    true → حاوية <div> (فقرات)؛ false → <span> inline
 */
export const MathText = memo(({ children, className, block = false }) => {
    const raw = typeof children === 'string' ? children : '';
    if (!raw) return null;

    // لا LaTeX ولا markdown → أرجِع النص مباشرة (تجنّب كلفة ReactMarkdown للتسميات).
    const hasMathOrMarkdown = /[$\\*_`#[\]]|\\\(|\\\[/.test(raw);
    if (!hasMathOrMarkdown) {
        return <span className={className}>{raw}</span>;
    }

    const processed = preprocessMath(raw);
    const Wrapper = block ? 'div' : 'span';
    const wrapperClass = `genui-mathtext${block ? ' genui-mathtext-block' : ''}${
        className ? ` ${className}` : ''
    }`;

    return (
        <Wrapper className={wrapperClass}>
            <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}
                components={INLINE_COMPONENTS}
            >
                {processed}
            </ReactMarkdown>
        </Wrapper>
    );
});
MathText.displayName = 'MathText';
