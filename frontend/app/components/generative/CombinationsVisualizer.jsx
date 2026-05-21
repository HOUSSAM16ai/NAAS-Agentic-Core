"use client";

import React, { memo, useMemo } from 'react';

/**
 * CombinationsVisualizer — Cognitive UI for Simultaneous Draws (Combinatorics)
 * ───────────────────────────────────────────────────────────────────────────
 * يُصيّر مسائل السحب الآني («دفعة واحدة») بصرياً عبر التأليفات (Combinations)،
 * لا شجرة احتمالات تتابعية (التي تكون خاطئة رياضياً للسحب الآني — Protocol V19.0).
 *
 * يعرض:
 *   • فضاء العيّنة C(n, k) — العدد الكلي للتأليفات الممكنة.
 *   • لكل مجموعة (لون/صنف): عددها وعدد تأليفات «k من نفس الصنف» = C(count, k).
 *   • احتمال الحدث «k من نفس الصنف» = Σ C(countᵢ, k) / C(n, k) ككسر دقيق.
 *
 * شكل props المتوقَّع (من OrchestratorClient._build_calculated_ui):
 *   { title?, n, k, total_combinations, groups:[{label,count,favorable_combinations}],
 *     same_group_favorable, formula? }
 *
 * عند props مشوَّهة → يُلقي استثناءً يلتقطه GenerativeUIErrorBoundary (fallback أنيق).
 */

// ألوان دلالية للمجموعات (تدوير لطيف، لا يحمل دلالة "نجاح/فشل")
const GROUP_PALETTE = ['#f59e0b', '#ef4444', '#22c55e', '#3b82f6', '#a855f7', '#14b8a6'];

const SymbolCnk = memo(({ n, k }) => (
    <span className="genui-cnk" aria-label={`عدد التأليفات: اختيار ${k} من ${n}`}>
        <span className="genui-cnk-c">C</span>
        <span className="genui-cnk-sub">
            <span className="genui-cnk-top">{k}</span>
            <span className="genui-cnk-bot">{n}</span>
        </span>
    </span>
));
SymbolCnk.displayName = 'SymbolCnk';

export const CombinationsVisualizer = memo(({ props }) => {
    if (!props || typeof props !== 'object') {
        throw new Error('CombinationsVisualizer: missing props');
    }
    const n = Number(props.n);
    const k = Number(props.k);
    const totalCombinations = Number(props.total_combinations);
    const groups = Array.isArray(props.groups) ? props.groups : [];
    const sameGroupFavorable = Number(props.same_group_favorable ?? 0);

    if (!Number.isFinite(n) || !Number.isFinite(k) || !Number.isFinite(totalCombinations) || totalCombinations < 1) {
        throw new Error('CombinationsVisualizer: invalid n/k/total');
    }

    const title = typeof props.title === 'string' ? props.title : 'تأليفات السحب الآني';
    const maxFav = useMemo(
        () => Math.max(1, ...groups.map((g) => Number(g.favorable_combinations) || 0)),
        [groups],
    );
    // احتمال الحدث «k من نفس الصنف» كنسبة عشرية للعرض
    const sameDecimal = totalCombinations > 0
        ? (sameGroupFavorable / totalCombinations).toFixed(4).replace(/\.?0+$/, '')
        : '0';

    return (
        <div className="genui-combinations" dir="rtl">
            <div className="genui-comb-header">
                <i className="fas fa-layer-group genui-comb-icon" aria-hidden="true" />
                <span className="genui-comb-title">{title}</span>
                <span className="genui-comb-badge" title="سحب آني (دفعة واحدة) — تأليفي لا تتابعي">
                    دفعة واحدة
                </span>
            </div>

            {/* فضاء العيّنة */}
            <div className="genui-comb-space">
                <span className="genui-comb-space-label">فضاء العيّنة</span>
                <span className="genui-comb-space-formula">
                    <SymbolCnk n={n} k={k} />
                    <span className="genui-comb-eq">=</span>
                    <strong className="genui-comb-space-val">{totalCombinations}</strong>
                </span>
            </div>

            {/* المجموعات */}
            <div className="genui-comb-groups">
                {groups.map((g, i) => {
                    const count = Number(g.count) || 0;
                    const fav = Number(g.favorable_combinations) || 0;
                    const color = GROUP_PALETTE[i % GROUP_PALETTE.length];
                    const width = `${Math.round((fav / maxFav) * 100)}%`;
                    return (
                        <div className="genui-comb-group" key={`${g.label}-${i}`}>
                            <div className="genui-comb-group-head">
                                <span className="genui-comb-dot" style={{ background: color }} aria-hidden="true" />
                                <span className="genui-comb-group-label">{g.label}</span>
                                <span className="genui-comb-group-count">العدد: {count}</span>
                            </div>
                            <div className="genui-comb-bar-track">
                                <div
                                    className="genui-comb-bar"
                                    style={{ width, background: color }}
                                    aria-hidden="true"
                                />
                                <span className="genui-comb-bar-val">
                                    <SymbolCnk n={count} k={k} /> = {fav}
                                </span>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* احتمال "k من نفس الصنف" */}
            <div className="genui-comb-result">
                <span className="genui-comb-result-label">احتمال {k} من نفس الصنف</span>
                <span className="genui-comb-result-frac" aria-label={`${sameGroupFavorable} على ${totalCombinations}`}>
                    <span className="genui-comb-frac-n">{sameGroupFavorable}</span>
                    <span className="genui-comb-frac-bar" aria-hidden="true" />
                    <span className="genui-comb-frac-d">{totalCombinations}</span>
                </span>
                <span className="genui-comb-result-dec">≈ {sameDecimal}</span>
            </div>
        </div>
    );
});
CombinationsVisualizer.displayName = 'CombinationsVisualizer';
