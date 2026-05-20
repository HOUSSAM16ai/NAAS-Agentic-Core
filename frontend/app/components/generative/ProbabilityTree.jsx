"use client";

import React, { memo, useMemo } from 'react';

/**
 * ProbabilityTree — Cognitive UI (Explorable Explanation)
 * ────────────────────────────────────────────────────────
 * يحوّل شجرة الاحتمالات من قائمة عمودية ميتة إلى شجرة SVG تفاعلية:
 *   • فروع منحنية (Bézier) بسماكة تتناسب مع الاحتمال (تدفّق الطاقة).
 *   • ظهور تدريجي متدرّج (staggered spawn) — الجذر ثم تتدفّق الفروع للأبناء.
 *   • عُقد زجاجية (glass-morphism) تفاعلية: hover/tap → تكبير + صيغة الاحتمال
 *     الشرطي P(B|A) واحتمال المسار التراكمي.
 *
 * شكل props المتوقَّع (من OrchestratorClient._detect_probability_tree):
 *   { title?, is_illustrative?, tree: { label, p?, children?[] } }
 * (نقبل props.data كبديل توافقي.)
 *
 * عند props مشوَّهة / شجرة ضخمة جداً → نُلقي استثناءً ليلتقطه
 * GenerativeUIErrorBoundary ويعرض fallback أنيق.
 */

// ─── هندسة التخطيط (px في فضاء viewBox) ───────────────────────────────────────
const PAD = 30;
const NODE_W = 150;
const NODE_H = 54;
const LEVEL_GAP = 200; // المسافة الأفقية بين المستويات
const ROW_GAP = 96; // المسافة العمودية بين الأوراق
const MAX_NODES = 160; // حدّ أمان — أكبر من ذلك يسقط للنص البديل

const fmt = (p, digits = 2) =>
    typeof p === 'number' && !Number.isNaN(p) ? p.toFixed(digits) : null;

/**
 * يسطّح الشجرة إلى عُقد وحواف مع حساب الصف (row) والعمق واحتمال المسار التراكمي.
 * post-order: الأوراق تأخذ صفوفاً متتابعة، والعقدة الأم = متوسط صفوف أبنائها.
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

// قوة اللون/التوهج حسب الاحتمال
const strokeWidthFor = (p) => 2.5 + (p ?? 0.5) * 9; // 2.5 .. 11.5
const opacityFor = (p) => 0.32 + (p ?? 0.5) * 0.6; // 0.32 .. 0.92

const Edge = memo(({ x1, y1, x2, y2, p, depth }) => {
    // منحنى S أفقي بين حافة الأم اليسرى وحافة الابن اليمنى
    const dx = Math.max(40, (x1 - x2) * 0.5);
    const d = `M ${x1} ${y1} C ${x1 - dx} ${y1}, ${x2 + dx} ${y2}, ${x2} ${y2}`;
    return (
        <path
            className="genui-edge"
            d={d}
            fill="none"
            stroke="url(#genui-edge-grad)"
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

const GlassNode = memo(({ node, x, y }) => {
    const pLabel = fmt(node.p);
    const jointLabel = fmt(node.joint, 3);
    const isRoot = node.depth === 0;

    const formula = isRoot
        ? 'نقطة البداية'
        : pLabel !== null
          ? `P(${node.label}) = ${pLabel}`
          : `P(${node.label})`;

    const spawnDelay = `${node.depth * 0.16 + (node.row % 4) * 0.04}s`;

    return (
        <foreignObject
            x={x}
            y={y}
            width={NODE_W}
            height={NODE_H}
            style={{ overflow: 'visible' }}
        >
            <div
                className={`genui-glass-node${isRoot ? ' genui-glass-root' : ''}`}
                style={{ animationDelay: spawnDelay }}
                tabIndex={0}
                role="button"
                aria-label={`${node.label}${pLabel !== null ? `، الاحتمال ${pLabel}` : ''}`}
            >
                <span className="genui-node-label">{node.label}</span>
                {pLabel !== null && <span className="genui-node-prob">{pLabel}</span>}

                <div className="genui-node-tip" role="tooltip">
                    <span className="genui-tip-formula">{formula}</span>
                    {!isRoot && (
                        <span className="genui-tip-joint">
                            احتمال المسار = <strong>{jointLabel}</strong>
                        </span>
                    )}
                </div>
            </div>
        </foreignObject>
    );
});
GlassNode.displayName = 'GlassNode';

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
    const { nodes, edges, width, height, xOf, yOf } = useMemo(
        () => layoutTree(tree),
        [tree],
    );

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
                        <linearGradient id="genui-edge-grad" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#22d3ee" />
                            <stop offset="55%" stopColor="#3b82f6" />
                            <stop offset="100%" stopColor="#6366f1" />
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
                        />
                    ))}

                    {nodes.map((n) => (
                        <GlassNode key={`n-${n.id}`} node={n} x={xOf(n)} y={yOf(n)} />
                    ))}
                </svg>
            </div>
        </div>
    );
});
ProbabilityTree.displayName = 'ProbabilityTree';
