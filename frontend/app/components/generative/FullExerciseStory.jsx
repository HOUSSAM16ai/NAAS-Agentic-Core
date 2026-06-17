"use client";

import React, { memo, useState, useMemo } from 'react';
import { MathText } from './MathText';

/**
 * FullExerciseStory — Multi-Step Pedagogical Carousel (Protocol V32.0)
 * ───────────────────────────────────────────────────────────────────────────
 * يُصيّر القصة التربوية الشاملة لتمرين كامل كـ Carousel متعدّد الخطوات.
 *
 * ## القاعدة الصارمة (Strict Visual Governance — V32.0)
 * ١. التطهير المستحيل (Impossible Purge): إذا كانت الخطوة مستحيلة (is_possible: false
 *    أو احتمال 0)، نُصيّر البانر التربوي فقط. يُمنع منعاً باتاً عرض أي كسور (0/165)
 *    أو حسابات رياضية أو نصوص شرح تحت البانر.
 * ٢. منع جدران النصوص: يُعرض فقط الجملة الأولى من الرسالة التربوية (بحد أقصى جملة واحدة).
 *
 * شكل props (من OrchestratorClient._build_calculated_ui):
 *   { title?, n, k, total_combinations, exercise_steps:[
 *       { step_index, step_id, title, render_kind, visual_directives,
 *         numerical_state, pedagogical_message } ] }
 */

const COLOR_TOKENS = {
    red: '#ef4444',
    white: '#e5e7eb',
    green: '#22c55e',
    black: '#111827',
    gold: '#f59e0b',
    blue: '#3b82f6',
    muted: '#94a3b8',
};
const GROUP_PALETTE = ['#f59e0b', '#ef4444', '#22c55e', '#3b82f6', '#a855f7', '#14b8a6'];
const colorFor = (token, i) =>
    (token && COLOR_TOKENS[token]) || GROUP_PALETTE[i % GROUP_PALETTE.length];

// رمز التأليف C اختيار k من n — يُجبَر على الاتجاه LTR كي لا ينعكس داخل RTL.
const Cnk = memo(({ n, k }) => (
    <span className="genui-cnk" aria-label={`اختيار ${k} من ${n}`}>
        <span className="genui-cnk-c">C</span>
        <span className="genui-cnk-sub">
            <span className="genui-cnk-top">{k}</span>
            <span className="genui-cnk-bot">{n}</span>
        </span>
    </span>
));
Cnk.displayName = 'Cnk';

// كسر مُكدَّس عمودياً (بسط فوق مقام) — اتجاه LTR ثابت.
const StackFraction = memo(({ num, den }) => (
    <span className="genui-fes-frac" aria-label={`${num} على ${den}`}>
        <span className="genui-fes-frac-n">{num}</span>
        <span className="genui-fes-frac-bar" aria-hidden="true" />
        <span className="genui-fes-frac-d">{den}</span>
    </span>
));
StackFraction.displayName = 'StackFraction';

// ── خطوة المعطيات: حالة الكيس بكرات ملوّنة ───────────────────────────────────
const UrnStep = memo(({ state }) => {
    const groups = Array.isArray(state?.groups) ? state.groups : [];
    return (
        <div className="genui-fes-urn">
            {groups.map((g, i) => {
                const count = Math.max(0, Number(g.count) || 0);
                const color = colorFor(g.color, i);
                return (
                    <div className="genui-fes-urn-group" key={`${g.label}-${i}`}>
                        <div className="genui-fes-urn-balls">
                            {Array.from({ length: Math.min(count, 14) }).map((_, b) => (
                                <span
                                    className="genui-fes-ball"
                                    key={b}
                                    style={{ background: color }}
                                    aria-hidden="true"
                                />
                            ))}
                        </div>
                        <span className="genui-fes-urn-tag">
                            {g.label} <strong>({count})</strong>
                        </span>
                    </div>
                );
            })}
        </div>
    );
});
UrnStep.displayName = 'UrnStep';

// ── خطوة فضاء العيّنة: C(n,k) = total ───────────────────────────────────────
const CombinationsStep = memo(({ state }) => {
    const n = Number(state?.n);
    const k = Number(state?.k);
    const total = Number(state?.total_combinations);
    return (
        <div className="genui-fes-space">
            <Cnk n={n} k={k} />
            <span className="genui-fes-eq">=</span>
            <strong className="genui-fes-space-val">{Number.isFinite(total) ? total : '—'}</strong>
        </div>
    );
});
CombinationsStep.displayName = 'CombinationsStep';

// ── خطوة الحدث المركّب: لكل صنف C(count,k) أو بانر مستحيل (لا 0) ───────────────
const EventBreakdownStep = memo(({ state }) => {
    const groups = Array.isArray(state?.groups) ? state.groups : [];
    const sameFav = Number(state?.same_group_favorable ?? state?.p_num ?? 0);
    const total = Number(state?.total_combinations ?? state?.p_den ?? 0);

    // V32.0: Strict Governance — Detect if the entire step is an "Impossible State"
    const isStateImpossible =
        state?.is_possible === false ||
        (groups.some((g) => g.is_possible === false) && sameFav === 0);

    if (isStateImpossible) {
        const impossibleGroups = groups.filter((g) => g.is_possible === false);
        return (
            <div className="genui-fes-event is-impossible-slide">
                {impossibleGroups.length > 0 ? (
                    impossibleGroups.map((g, i) => (
                        <div className="genui-fes-impossible" key={i} style={{ padding: '1rem', textAlign: 'center' }}>
                            <i className="fas fa-ban" aria-hidden="true" style={{ marginLeft: '0.5rem' }} />
                            {g.pedagogical_string || 'هذا الحدث مستحيل (العدد غير كافٍ).'}
                        </div>
                    ))
                ) : (
                    <div className="genui-fes-impossible" style={{ padding: '1rem', textAlign: 'center' }}>
                        <i className="fas fa-ban" aria-hidden="true" style={{ marginLeft: '0.5rem' }} />
                        {state?.pedagogical_string || 'هذا الحدث مستحيل في هذه الظروف.'}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className="genui-fes-event">
            <div className="genui-fes-event-rows">
                {groups.map((g, i) => {
                    const isPossible = g.is_possible !== false;
                    const color = colorFor(g.color, i);
                    const count = Number(g.count) || 0;
                    const fav = Number(g.favorable) || 0;
                    return (
                        <div className="genui-fes-event-row" key={`${g.label}-${i}`}>
                            <span
                                className="genui-fes-dot"
                                style={{ background: color }}
                                aria-hidden="true"
                            />
                            <span className="genui-fes-event-label">{g.label}</span>
                            {isPossible ? (
                                <span className="genui-fes-event-calc">
                                    <Cnk n={count} k={Number(state?.k) || count} />
                                    <span className="genui-fes-eq">=</span>
                                    <strong>{fav}</strong>
                                </span>
                            ) : (
                                <span className="genui-fes-impossible" role="note">
                                    <i className="fas fa-ban" aria-hidden="true" />
                                    {g.pedagogical_string || 'مستحيل'}
                                </span>
                            )}
                        </div>
                    );
                })}
            </div>
            {/* V32.0: Only render probability if it's greater than zero to avoid "0/165" leaks */}
            {total > 0 && sameFav > 0 && (
                <div className="genui-fes-event-result">
                    <span className="genui-fes-event-result-label">الاحتمال</span>
                    <StackFraction num={sameFav} den={total} />
                </div>
            )}
        </div>
    );
});
EventBreakdownStep.displayName = 'EventBreakdownStep';

// ── خطوة المتغيّر العشوائي: جدول توزيع P(X=i) ─────────────────────────────────
const DistributionStep = memo(({ state }) => {
    const dist = Array.isArray(state?.distribution) ? state.distribution : [];
    const variable = typeof state?.variable_label === 'string' ? state.variable_label : 'X';
    return (
        <div className="genui-fes-dist">
            <table className="genui-fes-dist-table">
                <thead>
                    <tr>
                        <th>{variable}</th>
                        {dist.map((d, i) => (
                            <td key={`v-${i}`}>{Number(d.value)}</td>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <th>P({variable})</th>
                        {dist.map((d, i) => (
                            <td key={`p-${i}`}>
                                <StackFraction num={Number(d.p_num)} den={Number(d.p_den)} />
                            </td>
                        ))}
                    </tr>
                </tbody>
            </table>
        </div>
    );
});
DistributionStep.displayName = 'DistributionStep';

const STEP_RENDERERS = {
    urn: (state) => <UrnStep state={state} />,
    combinations: (state) => <CombinationsStep state={state} />,
    event_breakdown: (state) => <EventBreakdownStep state={state} />,
    distribution: (state) => <DistributionStep state={state} />,
};

// ── D-116: طبقة التفاعل — سؤال واحد → الطالب يحاول → تحقق → كشف الخطوة ──────────
// «قيادة لا تلقين»: لا يُكشف عدّ/كسر الخطوة حتى يحاول الطالب أو يضغط «اكشف».
// الطالب يبني الجواب بنفسه (متّسق مع «لا تكشف»). حتمي بالكامل — لا LLM.
const StepInteraction = memo(({ interactive, onReveal }) => {
    const q = interactive || {};
    const [value, setValue] = useState('');
    const [wrong, setWrong] = useState(false);
    const [showHint, setShowHint] = useState(false);

    const checkNumber = () => {
        const got = parseInt(String(value).replace(/[^0-9]/g, ''), 10);
        if (Number.isFinite(got) && got === Number(q.expected)) {
            onReveal(true);
        } else {
            setWrong(true);
            setShowHint(true);
        }
    };
    const checkChoice = (idx) => {
        if (idx === Number(q.expected_index)) {
            onReveal(true);
        } else {
            setWrong(true);
            setShowHint(true);
        }
    };

    return (
        <div className="genui-fes-interact">
            <p className="genui-fes-question">
                <i className="fas fa-circle-question" aria-hidden="true" />{' '}
                <MathText>{q.question || 'ما الخطوة التالية؟'}</MathText>
            </p>

            {q.answer_kind === 'choice' && Array.isArray(q.choices) && (
                <div className="genui-fes-choices">
                    {q.choices.map((c, i) => (
                        <button
                            key={i}
                            type="button"
                            className="genui-fes-choice"
                            onClick={() => checkChoice(i)}
                        >
                            <MathText>{String(c)}</MathText>
                        </button>
                    ))}
                </div>
            )}

            {q.answer_kind === 'number' && (
                <div className="genui-fes-numrow">
                    <input
                        className="genui-fes-input"
                        inputMode="numeric"
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && checkNumber()}
                        placeholder="اكتب العدد ثم تحقّق"
                        aria-label="إجابتك"
                    />
                    <button type="button" className="genui-fes-verify" onClick={checkNumber}>
                        تحقّق
                    </button>
                </div>
            )}

            {wrong && (
                <p className="genui-fes-feedback" role="status">
                    حاول مرة أخرى — أنت قريب 🤔
                </p>
            )}
            {showHint && q.hint && (
                <p className="genui-fes-hint">
                    <i className="fas fa-lightbulb" aria-hidden="true" /> <MathText>{String(q.hint)}</MathText>
                </p>
            )}

            <button
                type="button"
                className="genui-fes-reveal-btn"
                onClick={() => onReveal(false)}
            >
                اكشف الخطوة <i className="fas fa-arrow-down" aria-hidden="true" />
            </button>
        </div>
    );
});
StepInteraction.displayName = 'StepInteraction';

export const FullExerciseStory = memo(({ props }) => {
    if (!props || typeof props !== 'object') {
        throw new Error('FullExerciseStory: missing props');
    }
    const steps = useMemo(
        () => (Array.isArray(props.exercise_steps) ? props.exercise_steps : []),
        [props.exercise_steps],
    );
    // D-120: افتح الكاروسيل على الخطوة المطلوبة (focus_step_id) لا دائماً على الكيس.
    // سؤال P(A) ⇒ focus_step_id="same_color_event" ⇒ يهبط على خطوة الحدث مباشرةً
    // (أبيض مستحيل/أحمر 4/أخضر 10 → 14/165) بدل إعادة «فهم المعطيات» كل مرة (تقدّم
    // محسوس، لا تكرار). fallback إلى 0 عند غياب التطابق.
    const initialStep = useMemo(() => {
        const focusId = typeof props.focus_step_id === 'string' ? props.focus_step_id : '';
        if (!focusId) return 0;
        const idx = steps.findIndex((s) => s && s.step_id === focusId);
        return idx >= 0 ? idx : 0;
    }, [steps, props.focus_step_id]);
    const [active, setActive] = useState(initialStep);
    // D-116: الخطوات المكشوفة — الخطوة التفاعلية تبدأ بسؤال؛ المحتوى يُكشف بعد المحاولة.
    const [revealed, setRevealed] = useState(() => new Set());

    if (steps.length === 0) {
        throw new Error('FullExerciseStory: no steps');
    }

    const clamped = Math.min(active, steps.length - 1);
    const step = steps[clamped] || {};
    const renderKind = typeof step.render_kind === 'string' ? step.render_kind : '';
    const renderer = STEP_RENDERERS[renderKind];
    const title = typeof props.title === 'string' ? props.title : 'الشرح البصري الشامل';
    // D-116: سؤال تفاعلي حتمي لهذه الخطوة (إن وُجد ولم يُكشف بعد).
    const interactive =
        step.interactive && typeof step.interactive === 'object' && step.interactive.question
            ? step.interactive
            : null;
    const isRevealed = !interactive || revealed.has(clamped);
    const revealStep = () =>
        setRevealed((prev) => {
            const next = new Set(prev);
            next.add(clamped);
            return next;
        });
    const progressPct = Math.round(((clamped + 1) / steps.length) * 100);

    return (
        <div className="genui-fes" dir="rtl">
            <div className="genui-fes-header">
                <i className="fas fa-wand-magic-sparkles genui-fes-icon" aria-hidden="true" />
                <span className="genui-fes-title">{title}</span>
                <span className="genui-fes-badge">شرح خارق · خطوة بخطوة</span>
            </div>

            {/* مؤشّر الخطوات (dots) */}
            <div className="genui-fes-dots" role="tablist" aria-label="خطوات الشرح">
                {steps.map((s, i) => (
                    <button
                        key={s.step_id || i}
                        type="button"
                        role="tab"
                        aria-selected={i === clamped}
                        aria-label={s.title || `الخطوة ${i + 1}`}
                        className={`genui-fes-dot-btn ${i === clamped ? 'is-active' : ''}`}
                        onClick={() => setActive(i)}
                    >
                        {i + 1}
                    </button>
                ))}
            </div>

            {/* D-116: شريط التقدّم — «ماذا أفعل الآن؟» شاشة واحدة في كل مرة */}
            <div className="genui-fes-progress" aria-hidden="true">
                <div className="genui-fes-progress-fill" style={{ width: `${progressPct}%` }} />
            </div>

            {/* بطاقة الخطوة الحالية */}
            <div className="genui-fes-card">
                <h4 className="genui-fes-step-title"><MathText>{step.title}</MathText></h4>

                {/* D-116: سؤال تفاعلي أولاً (قيادة لا تلقين) — الطالب يحاول ثم يُكشف المحتوى */}
                {!isRevealed ? (
                    <StepInteraction interactive={interactive} onReveal={revealStep} />
                ) : (
                    <>
                        <div className="genui-fes-visual">
                            {renderer ? (
                                renderer(step.numerical_state)
                            ) : (
                                <div className="genui-fes-novisual">—</div>
                            )}
                        </div>

                        {/* V32.0: Strict Text Purge — Return null for impossible slides & strip text walls */}
                        {(() => {
                            const ns = step.numerical_state;
                            const isImpossible =
                                ns?.is_possible === false ||
                                (step.render_kind === 'event_breakdown' &&
                                    ns?.groups?.some((g) => g.is_possible === false) &&
                                    Number(ns?.same_group_favorable ?? ns?.p_num ?? 0) === 0);

                            if (isImpossible) return null;

                            if (
                                typeof step.pedagogical_message === 'string' &&
                                step.pedagogical_message
                            ) {
                                // Extract only the first sentence to avoid text walls.
                                const firstSentence = step.pedagogical_message.split(/[.!?](\s|$)/)[0];
                                // ISS-105: الرسالة التربوية قد تحوي رموزاً رياضية → KaTeX
                                return (
                                    <p className="genui-fes-msg">
                                        <MathText>{`${firstSentence}.`}</MathText>
                                    </p>
                                );
                            }
                            return null;
                        })()}
                    </>
                )}
            </div>

            {/* تنقّل */}
            <div className="genui-fes-nav">
                <button
                    type="button"
                    className="genui-fes-nav-btn"
                    disabled={clamped === 0}
                    onClick={() => setActive((v) => Math.max(0, v - 1))}
                >
                    <i className="fas fa-chevron-right" aria-hidden="true" /> السابق
                </button>
                <span className="genui-fes-nav-pos">
                    {clamped + 1} / {steps.length}
                </span>
                <button
                    type="button"
                    className="genui-fes-nav-btn"
                    disabled={clamped === steps.length - 1}
                    onClick={() => setActive((v) => Math.min(steps.length - 1, v + 1))}
                >
                    التالي <i className="fas fa-chevron-left" aria-hidden="true" />
                </button>
            </div>
        </div>
    );
});
FullExerciseStory.displayName = 'FullExerciseStory';
