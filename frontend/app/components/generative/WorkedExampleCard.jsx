"use client";

import React, { memo, useState } from 'react';
import { MathText } from './MathText';

/**
 * WorkedExampleCard — بطاقة المثال المحلول المُتدرّج (D-114).
 * ────────────────────────────────────────────────────────────────
 * تُصيّر مخرَج WorkedExampleSkill (للمبتدئ المطلق، support_level==1):
 *   props = { concept_id, title, steps[{title, subgoal_label, subgoal_color,
 *             self_explanation_prompt}], mastery, bridge_text }
 *
 * الخريطة المنهجية المُتحوِّلة («كيف أحلّ أي تمرين مهما تغيّر يوم الامتحان» —
 * سؤال الطالب الحرفي). المثال الملموس بالأرقام يصل في السرد (مكشوف، على مسألة
 * مماثلة). هنا: كشف تدريجي تفاعلي يُجبر التفكير قبل الانتقال (active recall) +
 * مقياس إتقان يمتلئ فقط بالنجاح المستقل + جسر «جرّب تمرينك».
 *
 * props مشوّهة ⇒ fallbackText آمن. يُصيَّر بعد isComplete فقط.
 */

const CONCEPT_LABELS = {
    probability: 'الاحتمالات',
    conditional_probability: 'الاحتمال الشرطي',
    complex_numbers: 'الأعداد المركبة',
    numerical_functions: 'الدوال العددية',
    integration: 'التكامل',
    derivatives: 'الاشتقاق',
    limits: 'النهايات',
    sequences: 'المتتاليات',
    trigonometry: 'المثلثات',
    logarithm: 'اللوغاريتم',
    exponential: 'الدالة الأسية',
    general: 'عام',
};

const label = (id) => CONCEPT_LABELS[id] || id || 'المفهوم';

export const WorkedExampleCard = memo(({ props, fallbackText }) => {
    const data = props && typeof props === 'object' ? props : {};
    const steps = Array.isArray(data.steps) ? data.steps : [];
    const title = typeof data.title === 'string' && data.title ? data.title : 'مثال محلول كامل';
    const bridge = typeof data.bridge_text === 'string' ? data.bridge_text : '';
    const masteryRaw = typeof data.mastery === 'number' ? data.mastery : null;
    const masteryPct = masteryRaw != null ? Math.max(0, Math.min(100, Math.round(masteryRaw * 100))) : 0;

    // كشف تدريجي: يبدأ بخطوة واحدة، الطالب يكشف التالية بعد التفكير (active recall).
    const [revealed, setRevealed] = useState(1);

    if (steps.length === 0) {
        return (
            <div className="genui-bkt-stub" role="note">
                <i className="fas fa-lightbulb genui-bkt-icon" aria-hidden="true" />
                <span>{fallbackText || 'مثال محلول لبناء المنهجية.'}</span>
            </div>
        );
    }

    const allRevealed = revealed >= steps.length;
    const shown = steps.slice(0, revealed);

    return (
        <div className="genui-we-card" role="region" aria-label="مثال محلول متدرّج">
            <div className="genui-we-head">
                <i className="fas fa-lightbulb genui-we-icon" aria-hidden="true" />
                <span className="genui-we-title">{title}</span>
                <span className="genui-we-concept">{label(data.concept_id)}</span>
            </div>

            {/* مقياس الإتقان — يمتلئ فقط بالنجاح المستقل (لا بقراءة المثال) */}
            <div className="genui-we-mastery" aria-label={`مستوى الإتقان ${masteryPct}%`}>
                <div className="genui-we-mastery-bar">
                    <div className="genui-we-mastery-fill" style={{ width: `${masteryPct}%` }} />
                </div>
                <span className="genui-we-mastery-label">
                    الإتقان {masteryPct}% — يرتفع عند حلّك المستقل
                </span>
            </div>

            <ol className="genui-we-steps">
                {shown.map((step, idx) => {
                    const s = step && typeof step === 'object' ? step : {};
                    const color = typeof s.subgoal_color === 'string' ? s.subgoal_color : '#6366f1';
                    return (
                        <li className="genui-we-step" key={idx} style={{ '--we-accent': color }}>
                            <div className="genui-we-step-head">
                                <span className="genui-we-step-num" style={{ backgroundColor: color }}>
                                    {idx + 1}
                                </span>
                                <span className="genui-we-step-badge" style={{ color }}>
                                    {typeof s.subgoal_label === 'string' ? s.subgoal_label : ''}
                                </span>
                            </div>
                            {typeof s.self_explanation_prompt === 'string' && s.self_explanation_prompt && (
                                <p className="genui-we-step-why">
                                    <i className="fas fa-circle-question" aria-hidden="true" />{' '}
                                    <MathText>{s.self_explanation_prompt}</MathText>
                                </p>
                            )}
                        </li>
                    );
                })}
            </ol>

            {!allRevealed ? (
                <button
                    type="button"
                    className="genui-we-next"
                    onClick={() => setRevealed((r) => Math.min(steps.length, r + 1))}
                >
                    <i className="fas fa-arrow-left" aria-hidden="true" /> الخطوة التالية
                    <span className="genui-we-progress">{revealed}/{steps.length}</span>
                </button>
            ) : (
                bridge && (
                    <div className="genui-we-bridge">
                        <i className="fas fa-graduation-cap" aria-hidden="true" />
                        <MathText>{bridge}</MathText>
                    </div>
                )
            )}
        </div>
    );
});
WorkedExampleCard.displayName = 'WorkedExampleCard';
