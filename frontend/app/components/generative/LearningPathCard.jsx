"use client";

import React, { memo } from 'react';

/**
 * LearningPathCard — بطاقة المسار التعلّمي التكيفي (D-111).
 * ────────────────────────────────────────────────────────────────
 * يقرأ مخرَج LearningPathSkill (فوق BKT):
 *   props = { current_concept, next_concept, advanced, target_difficulty,
 *             recommendation_text, rationale }
 *
 * يعرض الخطوة التالية المقترحة + صعوبة متكيفة. يُصيَّر بعد isComplete فقط.
 * props مشوّهة ⇒ fallbackText آمن.
 */

const CONCEPT_LABELS = {
    probability: 'الاحتمالات',
    conditional_probability: 'الاحتمال الشرطي',
    statistics: 'الإحصاء',
    complex_numbers: 'الأعداد المركبة',
    numerical_functions: 'الدوال العددية',
    integration: 'التكامل',
    differential_equations: 'المعادلات التفاضلية',
    derivatives: 'الاشتقاق',
    limits: 'النهايات',
    sequences: 'المتتاليات',
    trigonometry: 'المثلثات',
    logarithm: 'اللوغاريتم',
    exponential: 'الدالة الأسية',
    geometry: 'الهندسة',
    general: 'عام',
};

const DIFFICULTY = {
    easy: { text: 'سهل', cls: 'easy', icon: 'fa-seedling' },
    medium: { text: 'متوسط', cls: 'medium', icon: 'fa-layer-group' },
    hard: { text: 'متقدّم', cls: 'hard', icon: 'fa-fire' },
};

const label = (id) => CONCEPT_LABELS[id] || id || 'المفهوم';

export const LearningPathCard = memo(({ props, fallbackText }) => {
    const data = props && typeof props === 'object' ? props : {};
    const rec = typeof data.recommendation_text === 'string' ? data.recommendation_text : '';

    if (!rec) {
        return (
            <div className="genui-bkt-stub" role="note">
                <i className="fas fa-route genui-bkt-icon" aria-hidden="true" />
                <span>{fallbackText || 'الخطوة التالية المقترحة.'}</span>
            </div>
        );
    }

    const diff = DIFFICULTY[data.target_difficulty] || DIFFICULTY.easy;
    const advanced = data.advanced === true;
    const nextLabel = label(data.next_concept);

    return (
        <div className="genui-path-card" role="region" aria-label="المسار التعلّمي المقترح">
            <div className="genui-path-head">
                <i className="fas fa-route genui-path-icon" aria-hidden="true" />
                <span className="genui-path-title">
                    {advanced ? 'الخطوة التالية' : 'ترسيخ المهارة'}
                </span>
                <span className={`genui-path-diff genui-path-diff-${diff.cls}`}>
                    <i className={`fas ${diff.icon}`} aria-hidden="true" /> {diff.text}
                </span>
            </div>
            <p className="genui-path-rec">{rec}</p>
            {advanced && (
                <div className="genui-path-next">
                    <i className="fas fa-arrow-left" aria-hidden="true" />
                    <span>{nextLabel}</span>
                </div>
            )}
        </div>
    );
});
LearningPathCard.displayName = 'LearningPathCard';
