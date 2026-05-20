"use client";

import React, { memo } from 'react';

/**
 * ProbabilityTree
 * ───────────────
 * يصيّر شجرة احتمالات تفاعلية من props بُنيت في الخادم
 * (`OrchestratorClient._detect_probability_tree`).
 *
 * شكل props المتوقَّع:
 *   {
 *     title?: string,
 *     is_illustrative?: boolean,
 *     tree: { label: string, p?: number, children?: TreeNode[] }
 *   }
 *
 * عند props مشوَّهة (tree مفقود/غير كائن) نُلقي استثناءً عمداً ليلتقطه
 * `GenerativeUIErrorBoundary` ويعرض النص البديل — لا تصيير جزئي مكسور.
 */

const formatProbability = (p) => {
    if (typeof p !== 'number' || Number.isNaN(p)) return null;
    // عرض ككسر عشري نظيف (0.30) — RTL-safe
    return p.toFixed(2);
};

const TreeNode = memo(({ node, depth = 0 }) => {
    if (!node || typeof node !== 'object' || typeof node.label !== 'string') {
        throw new Error('ProbabilityTree: malformed node');
    }
    const children = Array.isArray(node.children) ? node.children : [];
    const pLabel = formatProbability(node.p);

    return (
        <li className="genui-tree-node" data-depth={depth}>
            <div className="genui-tree-cell">
                {pLabel !== null && (
                    <span className="genui-tree-prob" aria-label={`الاحتمال ${pLabel}`}>
                        {pLabel}
                    </span>
                )}
                <span className="genui-tree-label">{node.label}</span>
            </div>
            {children.length > 0 && (
                <ul className="genui-tree-children">
                    {children.map((child, idx) => (
                        <TreeNode key={`${depth}-${idx}-${child?.label ?? idx}`} node={child} depth={depth + 1} />
                    ))}
                </ul>
            )}
        </li>
    );
});
TreeNode.displayName = 'TreeNode';

export const ProbabilityTree = memo(({ props }) => {
    if (!props || typeof props !== 'object') {
        throw new Error('ProbabilityTree: missing props');
    }
    const { title, tree, is_illustrative: isIllustrative } = props;
    if (!tree || typeof tree !== 'object') {
        throw new Error('ProbabilityTree: missing tree');
    }

    return (
        <div className="genui-probability-tree" dir="rtl">
            <div className="genui-tree-header">
                <i className="fas fa-sitemap genui-tree-icon" aria-hidden="true" />
                <span className="genui-tree-title">{typeof title === 'string' ? title : 'شجرة الاحتمالات'}</span>
                {isIllustrative && (
                    <span className="genui-tree-illustrative" title="رسم توضيحي بقيم افتراضية">
                        توضيحي
                    </span>
                )}
            </div>
            <ul className="genui-tree-root">
                <TreeNode node={tree} depth={0} />
            </ul>
        </div>
    );
});
ProbabilityTree.displayName = 'ProbabilityTree';
