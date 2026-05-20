"use client";

import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

/**
 * ProbabilityTree — Cognitive UI (Explorable Explanation)
 * ────────────────────────────────────────────────────────
 * شجرة احتمالات SVG تفاعلية مُصمَّمة لطلاب الثانوي (لا قراءة آلية):
 *   • فروع منحنية (Bézier) بسماكة تتناسب مع الاحتمال (تدفّق الطاقة).
 *   • ترميز لوني دلالي: مسار النجاح (دافئ أحمر/كهرماني) مقابل مسار
 *     المكمِّل/الفشل (بارد نيلي) — العقدة وحافتها الواردة بنفس اللون.
 *   • احتمالات بصيغة كسور إنسانية (½ ، ¾ ، 3⁄10) بدل الأرقام العشرية المجرّدة.
 *   • تلميح (tooltip) يُصيَّر عبر React Portal على مستوى <body> فلا يُقصُّ
 *     أبداً تحت العُقد الشقيقة (إصلاح كارثة z-index داخل <foreignObject>).
 *
 * شكل props المتوقَّع (من OrchestratorClient._detect_probability_tree):
 *   { title?, is_illustrative?, tree: { label, p?, children?[] } }
 * (نقبل props.data كبديل توافقي.)
 *
 * عند props مشوَّهة / شجرة ضخمة جداً → نُلقي استثناءً يلتقطه
 * GenerativeUIErrorBoundary فيعرض fallback أنيق.
 */

// ─── هندسة التخطيط (px في فضاء viewBox) ───────────────────────────────────────
const PAD = 30;
const NODE_W = 154;
const NODE_H = 56;
const LEVEL_GAP = 200; // المسافة الأفقية بين المستويات
const ROW_GAP = 100; // المسافة العمودية بين الأوراق
const MAX_NODES = 160; // حدّ أمان — أكبر من ذلك يسقط للنص البديل

// ─── أدوات إنسنة الرياضيات: تحويل عشري → كسر ──────────────────────────────────
// كسور Unicode الأنيقة لأكثر القيم شيوعاً في تمارين البكالوريا.
const VULGAR_FRACTIONS = {
    '1/2': '½',
    '1/3': '⅓',
    '2/3': '⅔',
    '1/4': '¼',
    '3/4': '¾',
    '1/5': '⅕',
    '2/5': '⅖',
    '3/5': '⅗',
    '4/5': '⅘',
    '1/6': '⅙',
    '5/6': '⅚',
    '1/8': '⅛',
    '3/8': '⅜',
    '5/8': '⅝',
    '7/8': '⅞',
};

const gcd = (a, b) => (b === 0 ? a : gcd(b, a % b));

/**
 * يحوّل احتمالاً (0..1) إلى كسر بسيط إن أمكن (مقام ≤ 20، ضمن هامش صغير)،
 * وإلا يُعيد القيمة العشرية فقط. يُعيد أيضاً رمز الكسر الأنيق عند توفّره.
 */
const decimalToFraction = (p) => {
    if (typeof p !== 'number' || Number.isNaN(p)) return null;
    const decimal = p.toFixed(p < 0.1 || p > 0.9 ? 3 : 2).replace(/\.?0+$/, '');
    if (p <= 0) return { num: 0, den: 1, label: '0', vulgar: null, isClean: true, decimal };
    if (p >= 1) return { num: 1, den: 1, label: '1', vulgar: null, isClean: true, decimal };

    const MAX_DEN = 20;
    const EPS = 1.5e-3;
    let best = null;
    for (let den = 2; den <= MAX_DEN; den += 1) {
        const num = Math.round(p * den);
        if (num <= 0 || num >= den) continue;
        if (Math.abs(num / den - p) <= EPS) {
            const g = gcd(num, den);
            best = { num: num / g, den: den / g };
            break;
        }
    }
    if (!best) return { num: null, den: null, label: null, vulgar: null, isClean: false, decimal };
    const key = `${best.num}/${best.den}`;
    return {
        num: best.num,
        den: best.den,
        label: key,
        vulgar: VULGAR_FRACTIONS[key] || null,
        isClean: true,
        decimal,
    };
};

// ─── الترميز اللوني الدلالي حسب نتيجة الفرع ───────────────────────────────────
// المكمِّل (Ā ، B̄ ، علامة المدّ العلوي U+0304/U+0305 ، نفي صريح) = فشل/بارد.
// خلاف ذلك = نجاح/دافئ. الجذر محايد.
const COMPLEMENT_RE =
    /[̄̅]|[ĀāŌōȲȳ]|\b(?:not|fail|echec|échec)\b|عدم|فشل|أسود|سالب/i;

const classifyOutcome = (label, depth) => {
    if (depth === 0) return 'root';
    return COMPLEMENT_RE.test(label) ? 'failure' : 'success';
};

// قوة السماكة/الشفافية حسب الاحتمال (تدفّق الطاقة عبر الفرع)
const strokeWidthFor = (p) => 2.5 + (p ?? 0.5) * 9; // 2.5 .. 11.5
const opacityFor = (p) => 0.34 + (p ?? 0.5) * 0.58; // 0.34 .. 0.92

/**
 * يسطّح الشجرة إلى عُقد وحواف مع حساب الصف (row) والعمق واحتمال المسار التراكمي
 * ونتيجة الفرع (outcome). post-order: الأوراق تأخذ صفوفاً متتابعة، والأم = متوسط
 * صفوف أبنائها.
 */
const layoutTree = (root) => {
    const nodes = [];
    const edges = [];
    let leaf = 0;
    let maxDepth = 0;

    const walk = (node, depth, parent, joint) => {
        if (!node || typeof node !== 'object' || typeof node.label !== 'string') {
            throw new Error('ProbabilityTree: malformed node');
        }
        if (nodes.length >= MAX_NODES) {
            throw new Error('ProbabilityTree: tree too large to render');
        }
        maxDepth = Math.max(maxDepth, depth);
        const p = typeof node.p === 'number' && !Number.isNaN(node.p) ? node.p : null;
        const nodeJoint = p !== null ? joint * p : joint;
        const children = Array.isArray(node.children) ? node.children : [];

        const rec = {
            id: nodes.length,
            depth,
            label: node.label,
            p,
            joint: nodeJoint,
            outcome: classifyOutcome(node.label, depth),
            row: 0,
        };
        nodes.push(rec);

        if (children.length === 0) {
            rec.row = leaf;
            leaf += 1;
        } else {
            const childIds = children.map((c) => walk(c, depth + 1, rec, nodeJoint));
            rec.row =
                childIds.reduce((sum, cid) => sum + nodes[cid].row, 0) / childIds.length;
        }
        if (parent) edges.push({ from: parent, to: rec });
        return rec.id;
    };

    walk(root, 0, null, 1);
    const leafCount = Math.max(1, leaf);
    const width = PAD * 2 + maxDepth * LEVEL_GAP + NODE_W;
    const height = PAD * 2 + (leafCount - 1) * ROW_GAP + NODE_H;

    // إحداثيات الزاوية العلوية-اليسرى لكل عقدة (RTL: الجذر في أقصى اليمين)
    const xOf = (n) => PAD + (maxDepth - n.depth) * LEVEL_GAP;
    const yOf = (n) => PAD + n.row * ROW_GAP;

    return { nodes, edges, width, height, xOf, yOf, maxDepth };
};

// ─── عرض الكسر (Fraction) ─────────────────────────────────────────────────────
const FractionView = memo(({ frac, compact = false }) => {
    if (!frac) return null;
    if (frac.isClean && frac.vulgar) {
        return <span className="genui-frac-vulgar">{frac.vulgar}</span>;
    }
    if (frac.isClean && frac.num !== null) {
        return (
            <span className="genui-frac" aria-label={`${frac.num} على ${frac.den}`}>
                <span className="genui-frac-n">{frac.num}</span>
                <span className="genui-frac-bar" aria-hidden="true" />
                <span className="genui-frac-d">{frac.den}</span>
            </span>
        );
    }
    return <span className={`genui-frac-dec${compact ? ' is-compact' : ''}`}>{frac.decimal}</span>;
});
FractionView.displayName = 'FractionView';

// ─── حافة منحنية موزونة بالاحتمال ولونها حسب نتيجة الابن ──────────────────────
const Edge = memo(({ x1, y1, x2, y2, p, depth, outcome }) => {
    const dx = Math.max(40, (x1 - x2) * 0.5);
    const d = `M ${x1} ${y1} C ${x1 - dx} ${y1}, ${x2 + dx} ${y2}, ${x2} ${y2}`;
    return (
        <path
            className="genui-edge"
            d={d}
            fill="none"
            stroke={`url(#genui-edge-${outcome})`}
            strokeWidth={strokeWidthFor(p)}
            strokeLinecap="round"
            pathLength="1"
            filter="url(#genui-glow)"
            style={{
                opacity: opacityFor(p),
                animationDelay: `${0.12 + depth * 0.16}s`,
            }}
        />
    );
});
Edge.displayName = 'Edge';

// ─── عقدة زجاجية تفاعلية ──────────────────────────────────────────────────────
const GlassNode = memo(({ node, x, y, onShow, onHide, frac }) => {
    const ref = useRef(null);

    const reveal = useCallback(() => {
        if (ref.current) onShow(node, ref.current.getBoundingClientRect());
    }, [node, onShow]);

    const toggle = useCallback(() => {
        if (ref.current) onShow(node, ref.current.getBoundingClientRect(), true);
    }, [node, onShow]);

    return (
        <foreignObject x={x} y={y} width={NODE_W} height={NODE_H} style={{ overflow: 'visible' }}>
            <div
                ref={ref}
                className="genui-glass-node"
                data-outcome={node.outcome}
                style={{ animationDelay: `${node.depth * 0.16 + (node.row % 4) * 0.04}s` }}
                tabIndex={0}
                role="button"
                aria-label={`${node.label}${frac ? `، الاحتمال ${frac.label || frac.decimal}` : ''}`}
                onMouseEnter={reveal}
                onMouseLeave={onHide}
                onFocus={reveal}
                onBlur={onHide}
                onClick={toggle}
            >
                <span className="genui-node-label">{node.label}</span>
                {frac && (
                    <span className="genui-node-prob" data-outcome={node.outcome}>
                        <FractionView frac={frac} compact />
                    </span>
                )}
            </div>
        </foreignObject>
    );
});
GlassNode.displayName = 'GlassNode';

// ─── التلميح عبر Portal (يطفو فوق كل شيء، لا يُقصّ أبداً) ──────────────────────
const TooltipPortal = memo(({ tip }) => {
    if (!tip) return null;
    const { node, left, top, placement, frac, jointFrac } = tip;
    const isRoot = node.depth === 0;
    const formula = isRoot ? 'نقطة البداية' : `P(${node.label})`;

    return createPortal(
        <div
            className="genui-tip-portal"
            data-placement={placement}
            data-outcome={node.outcome}
            role="tooltip"
            style={{ left: `${left}px`, top: `${top}px` }}
        >
            <span className="genui-tip-formula">
                {formula}
                {!isRoot && frac && (
                    <>
                        {' = '}
                        <FractionView frac={frac} />
                        {frac.decimal && <span className="genui-tip-dec">({frac.decimal})</span>}
                    </>
                )}
            </span>
            {!isRoot && (
                <span className="genui-tip-joint">
                    احتمال المسار ={' '}
                    {jointFrac ? (
                        <strong className="genui-tip-joint-val">
                            <FractionView frac={jointFrac} />
                            {jointFrac.decimal && (
                                <span className="genui-tip-dec">({jointFrac.decimal})</span>
                            )}
                        </strong>
                    ) : null}
                </span>
            )}
            <span className="genui-tip-arrow" aria-hidden="true" />
        </div>,
        document.body,
    );
});
TooltipPortal.displayName = 'TooltipPortal';

export const ProbabilityTree = memo(({ props }) => {
    if (!props || typeof props !== 'object') {
        throw new Error('ProbabilityTree: missing props');
    }
    const tree = props.tree || props.data;
    if (!tree || typeof tree !== 'object') {
        throw new Error('ProbabilityTree: missing tree');
    }
    const { title, is_illustrative: isIllustrative } = props;

    // الحساب الهندسي مرة واحدة (يُلقي للـ ErrorBoundary عند التشوّه/الضخامة)
    const { nodes, edges, width, height, xOf, yOf } = useMemo(() => layoutTree(tree), [tree]);

    // كسور محسوبة مسبقاً لكل عقدة (احتمال الفرع + احتمال المسار التراكمي)
    const fracById = useMemo(() => {
        const map = {};
        for (const n of nodes) {
            map[n.id] = {
                p: n.p !== null ? decimalToFraction(n.p) : null,
                joint: decimalToFraction(n.joint),
            };
        }
        return map;
    }, [nodes]);

    const [mounted, setMounted] = useState(false);
    const [tip, setTip] = useState(null);
    const pinnedRef = useRef(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    const placeTip = useCallback(
        (node, rect, pin = false) => {
            // النقر يثبّت/يلغي التثبيت؛ التمرير يعرض فقط إن لم يكن مثبتاً
            if (pin && pinnedRef.current && tip && tip.node.id === node.id) {
                pinnedRef.current = false;
                setTip(null);
                return;
            }
            if (pin) pinnedRef.current = true;
            const left = rect.left + rect.width / 2;
            const placeAbove = rect.bottom + 130 > window.innerHeight;
            setTip({
                node,
                left,
                top: placeAbove ? rect.top - 10 : rect.bottom + 10,
                placement: placeAbove ? 'above' : 'below',
                frac: fracById[node.id]?.p || null,
                jointFrac: fracById[node.id]?.joint || null,
            });
        },
        [fracById, tip],
    );

    const hideTip = useCallback(() => {
        if (pinnedRef.current) return; // مثبَّت بنقرة → لا يُخفى بمغادرة المؤشر
        setTip(null);
    }, []);

    // إغلاق التلميح عند التمرير/تغيير الحجم/مفتاح Escape (تفادي مواضع قديمة)
    useEffect(() => {
        if (!tip) return undefined;
        const close = () => {
            pinnedRef.current = false;
            setTip(null);
        };
        const onKey = (e) => {
            if (e.key === 'Escape') close();
        };
        window.addEventListener('scroll', close, true);
        window.addEventListener('resize', close);
        window.addEventListener('keydown', onKey);
        return () => {
            window.removeEventListener('scroll', close, true);
            window.removeEventListener('resize', close);
            window.removeEventListener('keydown', onKey);
        };
    }, [tip]);

    return (
        <div className="genui-probability-tree" dir="rtl">
            <div className="genui-tree-header">
                <i className="fas fa-diagram-project genui-tree-icon" aria-hidden="true" />
                <span className="genui-tree-title">
                    {typeof title === 'string' ? title : 'شجرة الاحتمالات'}
                </span>
                {isIllustrative && (
                    <span className="genui-tree-illustrative" title="رسم توضيحي بقيم افتراضية">
                        توضيحي
                    </span>
                )}
            </div>

            <div
                className="genui-tree-canvas"
                style={{ aspectRatio: `${width} / ${height}`, maxWidth: `${width}px` }}
            >
                <svg
                    className="genui-tree-svg"
                    viewBox={`0 0 ${width} ${height}`}
                    preserveAspectRatio="none"
                    role="img"
                    aria-label="شجرة احتمالات تفاعلية"
                >
                    <defs>
                        {/* تدرّجات لونية حسب نتيجة الفرع */}
                        <linearGradient id="genui-edge-success" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#f59e0b" />
                            <stop offset="100%" stopColor="#ef4444" />
                        </linearGradient>
                        <linearGradient id="genui-edge-failure" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#38bdf8" />
                            <stop offset="100%" stopColor="#6366f1" />
                        </linearGradient>
                        <linearGradient id="genui-edge-root" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#22d3ee" />
                            <stop offset="100%" stopColor="#3b82f6" />
                        </linearGradient>
                        <filter id="genui-glow" x="-30%" y="-30%" width="160%" height="160%">
                            <feGaussianBlur stdDeviation="2.2" result="blur" />
                            <feMerge>
                                <feMergeNode in="blur" />
                                <feMergeNode in="SourceGraphic" />
                            </feMerge>
                        </filter>
                    </defs>

                    {edges.map((e) => (
                        <Edge
                            key={`e-${e.from.id}-${e.to.id}`}
                            x1={xOf(e.from)}
                            y1={yOf(e.from) + NODE_H / 2}
                            x2={xOf(e.to) + NODE_W}
                            y2={yOf(e.to) + NODE_H / 2}
                            p={e.to.p}
                            depth={e.to.depth}
                            outcome={e.to.outcome}
                        />
                    ))}

                    {nodes.map((n) => (
                        <GlassNode
                            key={`n-${n.id}`}
                            node={n}
                            x={xOf(n)}
                            y={yOf(n)}
                            onShow={placeTip}
                            onHide={hideTip}
                            frac={fracById[n.id]?.p || null}
                        />
                    ))}
                </svg>
            </div>

            {mounted && <TooltipPortal tip={tip} />}
        </div>
    );
});
ProbabilityTree.displayName = 'ProbabilityTree';
