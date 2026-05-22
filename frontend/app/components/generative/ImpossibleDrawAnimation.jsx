"use client";

import React, { memo, useMemo } from 'react';

/**
 * ImpossibleDrawAnimation — Visual Pedagogy for Impossible Draws (Protocol V26.2)
 * ───────────────────────────────────────────────────────────────────────────
 * بدل عرض رياضيات منحلّة (C_2^3 = 0) للطالب الحائر، نروي قصة بصرية:
 *   • كيس يحوي «المتاح» كرات فقط.
 *   • محاولة سحب «المطلوب» (> المتاح) → اهتزاز/فشل لطيف (bag_shake).
 *   • رسالة تربوية تشرح لماذا الاحتمال = صفر.
 *
 * عقد مُفكَّك صارم (decoupled) من الخلفية:
 *   props = {
 *     title, ui_mode: "impossible_case",
 *     visual_directives: { animation_hint, fallback_math },
 *     numerical_state: { available_items, requested_items, item_color },
 *     pedagogical_message, item_label, container
 *   }
 *
 * props مشوَّهة → throw → يلتقطها GenerativeUIErrorBoundary (fallback أنيق).
 */

const COLOR_CSS = {
    white: '#f8fafc',
    red: '#ef4444',
    green: '#22c55e',
    blue: '#3b82f6',
    gold: '#f59e0b',
    yellow: '#f59e0b',
    black: '#1f2937',
};

const Ball = memo(({ color, available }) => (
    <span
        className="genui-imp-ball"
        style={{
            background: COLOR_CSS[color] || color || '#f8fafc',
            border: '2px solid rgba(0,0,0,0.18)',
            opacity: available ? 1 : 0.28,
        }}
        aria-hidden="true"
    />
));
Ball.displayName = 'Ball';

export const ImpossibleDrawAnimation = memo(({ props }) => {
    if (!props || typeof props !== 'object') {
        throw new Error('ImpossibleDrawAnimation: missing props');
    }
    const numeric = props.numerical_state || {};
    const directives = props.visual_directives || {};
    const available = Number(numeric.available_items);
    const requested = Number(numeric.requested_items);
    const color = typeof numeric.item_color === 'string' ? numeric.item_color : 'white';

    if (!Number.isFinite(available) || !Number.isFinite(requested) || requested <= available) {
        throw new Error('ImpossibleDrawAnimation: invalid numerical_state');
    }

    const title = typeof props.title === 'string' ? props.title : 'عملية مستحيلة';
    const itemLabel = typeof props.item_label === 'string' ? props.item_label : 'عنصر';
    const container = typeof props.container === 'string' ? props.container : 'كيس';
    const message =
        typeof props.pedagogical_message === 'string'
            ? props.pedagogical_message
            : 'هذه العملية مستحيلة، واحتمال حدوثها هو صفر.';
    const shake = directives.animation_hint === 'bag_shake';

    // كرات «متاحة» (مملوءة) + كرات «مطلوبة ناقصة» (شبحية) لإبراز الفجوة بصرياً.
    const ghost = Math.max(0, requested - available);
    const balls = useMemo(
        () => [
            ...Array.from({ length: available }, (_, i) => ({ key: `a${i}`, available: true })),
            ...Array.from({ length: ghost }, (_, i) => ({ key: `g${i}`, available: false })),
        ],
        [available, ghost],
    );

    return (
        <div className="genui-impossible" dir="rtl">
            <style>{`
                @keyframes genuiBagShake {
                    0%,100% { transform: translateX(0) rotate(0); }
                    15% { transform: translateX(-6px) rotate(-3deg); }
                    30% { transform: translateX(6px) rotate(3deg); }
                    45% { transform: translateX(-5px) rotate(-2deg); }
                    60% { transform: translateX(5px) rotate(2deg); }
                    75% { transform: translateX(-3px) rotate(-1deg); }
                }
                .genui-impossible {
                    border: 1px solid var(--border-color, #e5e5e5);
                    border-radius: 16px; padding: 1.1rem 1.25rem; margin: 0.5rem 0;
                    background: var(--surface-elevated, #fafafa);
                }
                .genui-imp-head { display:flex; align-items:center; gap:.55rem; margin-bottom:.9rem; }
                .genui-imp-title { font-weight:800; font-size:1.05rem; }
                .genui-imp-badge {
                    margin-inline-start:auto; font-size:.72rem; font-weight:700;
                    padding:.2rem .6rem; border-radius:999px;
                    background:rgba(239,68,68,.12); color:#ef4444; border:1px solid rgba(239,68,68,.3);
                }
                .genui-imp-stage { display:flex; align-items:center; gap:1rem; flex-wrap:wrap; margin-bottom:.9rem; }
                .genui-imp-bag {
                    position:relative; min-width:130px; padding:.9rem; border-radius:14px;
                    background:linear-gradient(160deg,#92400e,#b45309); box-shadow:inset 0 -8px 16px rgba(0,0,0,.25);
                    display:flex; flex-wrap:wrap; gap:.4rem; justify-content:center; align-items:center;
                    animation:${shake ? 'genuiBagShake .9s ease-in-out infinite' : 'none'};
                }
                .genui-imp-bag-label {
                    position:absolute; top:-.7rem; inset-inline-start:.6rem; font-size:.7rem;
                    background:#78350f; color:#fff; padding:.05rem .5rem; border-radius:999px;
                }
                .genui-imp-ball { width:22px; height:22px; border-radius:50%; display:inline-block; }
                .genui-imp-arrow { font-size:1.4rem; color:#ef4444; }
                .genui-imp-ask { font-weight:700; }
                .genui-imp-ask b { color:#ef4444; }
                .genui-imp-counts { display:flex; gap:1.2rem; margin-bottom:.8rem; font-size:.9rem; }
                .genui-imp-counts span b { font-size:1.1rem; }
                .genui-imp-prob {
                    display:inline-flex; align-items:center; gap:.4rem; font-weight:800;
                    color:#ef4444; margin-bottom:.7rem;
                }
                .genui-imp-msg {
                    background:rgba(239,68,68,.07); border-inline-start:3px solid #ef4444;
                    padding:.7rem .9rem; border-radius:8px; line-height:1.7;
                }
            `}</style>

            <div className="genui-imp-head">
                <i className="fas fa-triangle-exclamation" style={{ color: '#ef4444' }} aria-hidden="true" />
                <span className="genui-imp-title">{title}</span>
                <span className="genui-imp-badge">مستحيل</span>
            </div>

            <div className="genui-imp-stage">
                <div className="genui-imp-bag" role="img" aria-label={`${container} يحوي ${available} ${itemLabel}`}>
                    <span className="genui-imp-bag-label">{container}</span>
                    {balls.map((b) => (
                        <Ball key={b.key} color={color} available={b.available} />
                    ))}
                </div>
                <span className="genui-imp-arrow" aria-hidden="true">⟸</span>
                <span className="genui-imp-ask">
                    نحاول سحب <b>{requested}</b> {itemLabel}
                </span>
            </div>

            <div className="genui-imp-counts">
                <span>المتاح: <b>{available}</b></span>
                <span>المطلوب: <b>{requested}</b></span>
            </div>

            <div className="genui-imp-prob" aria-label="الاحتمال يساوي صفر">
                <i className="fas fa-equals" aria-hidden="true" />
                الاحتمال = 0
            </div>

            <p className="genui-imp-msg">{message}</p>
        </div>
    );
});
ImpossibleDrawAnimation.displayName = 'ImpossibleDrawAnimation';
