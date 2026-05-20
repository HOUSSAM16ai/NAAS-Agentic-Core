"use client";

import React from 'react';
import { errorTracker } from '../../utils/errorTracker';

/**
 * GenerativeUIErrorBoundary
 * ─────────────────────────
 * حدّ خطأ صارم (strict React Error Boundary) يلفّ كل مكوّن واجهة توليدي.
 *
 * إذا ألقى المكوّن المُصيَّر استثناءً (props مشوَّهة، حقل ناقص، خطأ تصيير)،
 * نلتقطه ونعرض النص البديل `fallbackText` بدل أن تنهار الواجهة بالكامل.
 *
 * RULE: الواجهة يجب ألا تنهار أبداً بسبب chunk مُشوَّه من الخادم.
 */
export class GenerativeUIErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false };
    }

    static getDerivedStateFromError() {
        return { hasError: true };
    }

    componentDidCatch(error, errorInfo) {
        errorTracker.reportError(error, {
            errorInfo,
            source: 'GenerativeUIErrorBoundary',
            component: this.props.componentName,
        });
    }

    render() {
        if (this.state.hasError) {
            const fallback = this.props.fallbackText || 'تعذّر عرض المكوّن التفاعلي.';
            return (
                <div className="genui-fallback" role="note" aria-live="polite">
                    <i className="fas fa-triangle-exclamation genui-fallback-icon" aria-hidden="true" />
                    <span className="genui-fallback-text">{fallback}</span>
                </div>
            );
        }
        return this.props.children;
    }
}

GenerativeUIErrorBoundary.displayName = 'GenerativeUIErrorBoundary';
