"use client";

import React, { memo } from 'react';

/**
 * BktMasteryCard — بطاقة تتبّع الإتقان المعرفي (D-106 · ISS-114).
 * ────────────────────────────────────────────────────────────────
 * يستبدل BktHintStub بمكوّن بصري حقيقي يقرأ مخرَج محرّك BKT (D-074):
 *   props = { concept_id, cognitive_load_estimate, student_mastery_probability }
 *
 * - حلقة تقدّم SVG (stroke-dashoffset) متدرّجة اللون حسب الإتقان.
 * - تسمية المفهوم بالعربية + شارة الحِمل المعرفي.
 * - يُصيَّر بعد isComplete فقط ⇒ أنيميشن الحلقة قانوني (قوانين الثيم D-055→D-059).
 * - props مشوّهة ⇒ يعرض fallbackText كملاحظة آمنة (لا انهيار).
 */

// تسميات المفاهيم — مرآة لـ bkt_engine._CONCEPT_PATTERNS ids.
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

const LOAD_LABELS = {
    low: { text: 'حِمل خفيف', cls: 'low' },
    medium: { text: 'حِمل متوسط', cls: 'medium' },
    high: { text: 'حِمل مرتفع', cls: 'high' },
};

const RADIUS = 32;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function band(mastery) {
    if (mastery >= 0.7) return 'high';
    if (mastery >= 0.35) return 'mid';
    return 'low';
}

export const BktMasteryCard = memo(({ props, fallbackText }) => {
    const data = props && typeof props === 'object' ? props : {};
    const mastery = Number(data.student_mastery_probability);

    // props مشوّهة → ملاحظة آمنة (نفس سلوك الـ stub القديم).
    if (!Number.isFinite(mastery)) {
        return (
            <div className="genui-bkt-stub" role="note">
                <i className="fas fa-lightbulb genui-bkt-icon" aria-hidden="true" />
                <span>{fallbackText || 'مؤشر إتقان المهارة.'}</span>
            </div>
        );
    }

    const clamped = Math.max(0, Math.min(1, mastery));
    const pct = Math.round(clamped * 100);
    const conceptLabel = CONCEPT_LABELS[data.concept_id] || data.concept_id || 'المفهوم';
    const load = LOAD_LABELS[data.cognitive_load_estimate] || null;
    const grade = band(clamped);
    const dashOffset = CIRCUMFERENCE * (1 - clamped);

    return (
        <div
            className={`genui-bkt-card genui-bkt-${grade}`}
            role="region"
            aria-label={`تتبّع إتقان ${conceptLabel}: ${pct}%`}
        >
            <div className="genui-bkt-ring" aria-hidden="true">
                <svg viewBox="0 0 80 80" width="80" height="80">
                    <circle
                        className="genui-bkt-ring-track"
                        cx="40"
                        cy="40"
                        r={RADIUS}
                        fill="none"
                        strokeWidth="7"
                    />
                    <circle
                        className="genui-bkt-ring-fill"
                        cx="40"
                        cy="40"
                        r={RADIUS}
                        fill="none"
                        strokeWidth="7"
                        strokeLinecap="round"
                        strokeDasharray={CIRCUMFERENCE}
                        strokeDashoffset={dashOffset}
                        transform="rotate(-90 40 40)"
                    />
                </svg>
                <span className="genui-bkt-pct">{pct}%</span>
            </div>
            <div className="genui-bkt-body">
                <div className="genui-bkt-title">
                    <i className="fas fa-brain genui-bkt-icon" aria-hidden="true" />
                    <span>تتبّع المعرفة — {conceptLabel}</span>
                </div>
                {load && (
                    <span className={`genui-bkt-load genui-bkt-load-${load.cls}`}>{load.text}</span>
                )}
            </div>
        </div>
    );
});
BktMasteryCard.displayName = 'BktMasteryCard';
