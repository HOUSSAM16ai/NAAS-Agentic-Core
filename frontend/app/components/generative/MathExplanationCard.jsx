"use client";

/**
 * MathExplanationCard — بطاقة الشرح الرياضي العميق
 *
 * تُصيّر payload الشرح السردي القادم من math_pipeline:
 *   { math_type, label, intuition, steps[], hint, visual_metaphor }
 *
 * الفصل المعماري:
 *   - Backend  → يُحدد المنطق والحالة والمكوّن والتلميح
 *   - هذا الملف → يُحوِّل ذلك إلى قصة بصرية
 *   - LLM      → يكتب الشرح السردي (في solve_node)
 *
 * قانون D-074: لا رموز مجردة في labels — كل عنوان ملموس وقابل للقراءة.
 */

import React, { memo, useState } from 'react';
import { MathText } from './MathText';

// ── ألوان حسب نوع المسألة ────────────────────────────────────────────────────
const TYPE_COLORS = {
    derivative:      { bg: '#eff6ff', border: '#3b82f6', accent: '#1d4ed8', icon: '📐' },
    integral:        { bg: '#f0fdf4', border: '#22c55e', accent: '#15803d', icon: '∫'  },
    limit:           { bg: '#faf5ff', border: '#a855f7', accent: '#7e22ce', icon: '∞'  },
    equation:        { bg: '#fff7ed', border: '#f97316', accent: '#c2410c', icon: '⚖️' },
    function_study:  { bg: '#f0f9ff', border: '#0ea5e9', accent: '#0369a1', icon: '📊' },
    probability:     { bg: '#fdf4ff', border: '#d946ef', accent: '#a21caf', icon: '🎲' },
    complex:         { bg: '#fefce8', border: '#eab308', accent: '#a16207', icon: '🔢' },
    matrix:          { bg: '#f8fafc', border: '#64748b', accent: '#334155', icon: '🔲' },
    geometry:        { bg: '#fff1f2', border: '#f43f5e', accent: '#be123c', icon: '📐' },
    sequence:        { bg: '#ecfdf5', border: '#10b981', accent: '#065f46', icon: '🔢' },
    differential_eq: { bg: '#fef2f2', border: '#ef4444', accent: '#991b1b', icon: '📈' },
    general_math:    { bg: '#f9fafb', border: '#9ca3af', accent: '#374151', icon: '📚' },
};

const getColors = (mathType) =>
    TYPE_COLORS[mathType] || TYPE_COLORS.general_math;

// ── مكوّن خطوة واحدة ─────────────────────────────────────────────────────────
const StepCard = memo(({ step, index, accent }) => {
    const [expanded, setExpanded] = useState(true);

    return (
        <div
            className="math-step-card"
            style={{
                borderRight: `3px solid ${accent}`,
                background: '#ffffff',
                borderRadius: '8px',
                padding: '12px 16px',
                marginBottom: '10px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            }}
        >
            <button
                onClick={() => setExpanded(e => !e)}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    width: '100%',
                    textAlign: 'right',
                    padding: 0,
                }}
                aria-expanded={expanded}
            >
                <span
                    style={{
                        minWidth: '28px',
                        height: '28px',
                        borderRadius: '50%',
                        background: accent,
                        color: '#fff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '13px',
                        fontWeight: 700,
                        flexShrink: 0,
                    }}
                >
                    {index + 1}
                </span>
                <span
                    style={{
                        flex: 1,
                        fontWeight: 600,
                        fontSize: '14px',
                        color: '#1e293b',
                        textAlign: 'right',
                    }}
                >
                    {/* ISS-105: KaTeX للعناوين التي قد تحوي رموزاً رياضية */}
                    <MathText>{step.title || `الخطوة ${index + 1}`}</MathText>
                </span>
                <span style={{ color: '#94a3b8', fontSize: '12px' }}>
                    {expanded ? '▲' : '▼'}
                </span>
            </button>

            {expanded && step.content && (
                <div
                    style={{
                        marginTop: '10px',
                        paddingRight: '38px',
                        fontSize: '14px',
                        color: '#334155',
                        lineHeight: '1.7',
                        direction: 'rtl',
                    }}
                >
                    {/* ISS-105: محتوى الخطوة يحوي LaTeX (h(x), $$H(x)=…$$) → KaTeX */}
                    <MathText block>{step.content}</MathText>
                </div>
            )}
        </div>
    );
});
StepCard.displayName = 'StepCard';

// ── مكوّن الاستعارة البصرية ───────────────────────────────────────────────────
const VisualMetaphor = memo(({ metaphor, accent }) => {
    if (!metaphor) return null;
    return (
        <div
            style={{
                background: `${accent}12`,
                border: `1px dashed ${accent}`,
                borderRadius: '8px',
                padding: '12px 16px',
                marginBottom: '14px',
                display: 'flex',
                gap: '10px',
                alignItems: 'flex-start',
                direction: 'rtl',
            }}
            role="note"
            aria-label="صورة ذهنية"
        >
            <span style={{ fontSize: '20px', flexShrink: 0 }}>💡</span>
            <div>
                <div style={{ fontWeight: 600, fontSize: '13px', color: accent, marginBottom: '4px' }}>
                    الصورة الذهنية
                </div>
                <div style={{ fontSize: '14px', color: '#334155', lineHeight: '1.6' }}>
                    <MathText block>{metaphor}</MathText>
                </div>
            </div>
        </div>
    );
});
VisualMetaphor.displayName = 'VisualMetaphor';

// ── مكوّن التلميح ─────────────────────────────────────────────────────────────
const HintBadge = memo(({ hint, accent }) => {
    if (!hint) return null;
    return (
        <div
            style={{
                background: '#fffbeb',
                border: '1px solid #fbbf24',
                borderRadius: '6px',
                padding: '10px 14px',
                marginTop: '14px',
                display: 'flex',
                gap: '8px',
                alignItems: 'flex-start',
                direction: 'rtl',
            }}
        >
            <span style={{ fontSize: '16px', flexShrink: 0 }}>🔑</span>
            <div style={{ fontSize: '13px', color: '#92400e', lineHeight: '1.5' }}>
                <strong>تلميح: </strong><MathText>{hint}</MathText>
            </div>
        </div>
    );
});
HintBadge.displayName = 'HintBadge';

// ── المكوّن الرئيسي ───────────────────────────────────────────────────────────
export const MathExplanationCard = memo(({ props: payload }) => {
    const safe = payload && typeof payload === 'object' ? payload : {};
    const mathType = typeof safe.math_type === 'string' ? safe.math_type : 'general_math';
    const label = typeof safe.label === 'string' ? safe.label : '📚 رياضيات';
    const intuition = typeof safe.intuition === 'string' ? safe.intuition : '';
    const steps = Array.isArray(safe.steps) ? safe.steps : [];
    const hint = typeof safe.hint === 'string' ? safe.hint : '';
    const metaphor = typeof safe.visual_metaphor === 'string' ? safe.visual_metaphor : '';

    const colors = getColors(mathType);
    const [showSteps, setShowSteps] = useState(true);

    return (
        <div
            className="math-explanation-card"
            style={{
                background: colors.bg,
                border: `1px solid ${colors.border}`,
                borderRadius: '12px',
                padding: '18px 20px',
                marginTop: '12px',
                direction: 'rtl',
                fontFamily: 'inherit',
            }}
            role="region"
            aria-label={`شرح: ${label}`}
        >
            {/* ── رأس البطاقة ── */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    marginBottom: '14px',
                    paddingBottom: '12px',
                    borderBottom: `1px solid ${colors.border}40`,
                }}
            >
                <span style={{ fontSize: '22px' }}>{colors.icon}</span>
                <div>
                    <div
                        style={{
                            fontWeight: 700,
                            fontSize: '15px',
                            color: colors.accent,
                        }}
                    >
                        {label}
                    </div>
                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                        شرح تفاعلي خطوة بخطوة
                    </div>
                </div>
            </div>

            {/* ── الحدس والفهم الأولي ── */}
            {intuition && (
                <div
                    style={{
                        background: '#ffffff',
                        borderRadius: '8px',
                        padding: '12px 16px',
                        marginBottom: '14px',
                        fontSize: '14px',
                        color: '#1e293b',
                        lineHeight: '1.7',
                        borderRight: `4px solid ${colors.accent}`,
                    }}
                >
                    <div
                        style={{
                            fontWeight: 600,
                            fontSize: '12px',
                            color: colors.accent,
                            marginBottom: '6px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px',
                        }}
                    >
                        لماذا هذه الطريقة؟
                    </div>
                    {/* ISS-105: الحدس قد يحوي رموزاً رياضية → KaTeX */}
                    <MathText block>{intuition}</MathText>
                </div>
            )}

            {/* ── الصورة الذهنية ── */}
            <VisualMetaphor metaphor={metaphor} accent={colors.accent} />

            {/* ── الخطوات ── */}
            {steps.length > 0 && (
                <div>
                    <button
                        onClick={() => setShowSteps(s => !s)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '0 0 10px 0',
                            fontWeight: 600,
                            fontSize: '13px',
                            color: colors.accent,
                        }}
                        aria-expanded={showSteps}
                    >
                        <span>{showSteps ? '▼' : '▶'}</span>
                        <span>الخطوات ({steps.length})</span>
                    </button>

                    {showSteps && (
                        <div>
                            {steps.map((step, i) => (
                                <StepCard
                                    key={step.id || i}
                                    step={step}
                                    index={i}
                                    accent={colors.accent}
                                />
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ── التلميح ── */}
            <HintBadge hint={hint} accent={colors.accent} />
        </div>
    );
});
MathExplanationCard.displayName = 'MathExplanationCard';
