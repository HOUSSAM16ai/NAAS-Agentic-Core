"use client";

import React, { memo } from 'react';
import { CombinationsVisualizer } from './CombinationsVisualizer';
import { FullExerciseStory } from './FullExerciseStory';
import { GenerativeUIErrorBoundary } from './GenerativeUIErrorBoundary';
import { ImpossibleDrawAnimation } from './ImpossibleDrawAnimation';
import { ProbabilityTree } from './ProbabilityTree';

/**
 * GenerativeUIRenderer
 * ────────────────────
 * نقطة الدخول الوحيدة لتصيير مكوّنات الواجهة التوليدية القادمة عبر البث.
 *
 * - سجلّ صريح (whitelist) للمكوّنات المعروفة. أي مكوّن خارج السجل → نص بديل.
 * - كل مكوّن مُغلَّف بـ `GenerativeUIErrorBoundary` → استثناء التصيير لا يُسقط
 *   المحادثة، بل يعرض `fallbackText`.
 *
 * Cognitive Load Theory: نُصيّر فقط المكوّن المطلوب صراحةً عبر حالة الرسم —
 * لا نُلوّث DOM بمكوّنات غير مُستدعاة.
 */

// stub: bkt_hint_display مُسجَّل كنوع معروف لكن لم يُبنَ بعد — يعرض النص البديل
// بأمان (info note) بدل الانهيار.
const BktHintStub = memo(({ fallbackText }) => (
    <div className="genui-bkt-stub" role="note">
        <i className="fas fa-lightbulb genui-bkt-icon" aria-hidden="true" />
        <span>{fallbackText || 'مؤشر إتقان المهارة (قريباً).'}</span>
    </div>
));
BktHintStub.displayName = 'BktHintStub';

const COMPONENT_REGISTRY = {
    probability_tree: (props) => <ProbabilityTree props={props} />,
    combinations_visualizer: (props) => <CombinationsVisualizer props={props} />,
    full_exercise_story: (props) => <FullExerciseStory props={props} />,
    impossible_draw_animation: (props) => <ImpossibleDrawAnimation props={props} />,
    bkt_hint_display: (props, fallbackText) => <BktHintStub fallbackText={fallbackText} />,
};

const FallbackNote = memo(({ text }) => (
    <div className="genui-fallback" role="note" aria-live="polite">
        <i className="fas fa-circle-info genui-fallback-icon" aria-hidden="true" />
        <span className="genui-fallback-text">{text}</span>
    </div>
));
FallbackNote.displayName = 'FallbackNote';

export const GenerativeUIRenderer = memo(({ uiComponent }) => {
    const safe = uiComponent && typeof uiComponent === 'object' ? uiComponent : {};
    const component = typeof safe.component === 'string' ? safe.component : '';
    const props = safe.props && typeof safe.props === 'object' ? safe.props : {};
    const fallbackText = typeof safe.fallbackText === 'string' && safe.fallbackText
        ? safe.fallbackText
        : 'تعذّر عرض المكوّن التفاعلي.';

    const factory = COMPONENT_REGISTRY[component];

    // مكوّن مجهول (لم يصل لخط الدفاع في الخادم) → نص بديل بدون محاولة تصيير
    if (!factory) {
        return <FallbackNote text={fallbackText} />;
    }

    return (
        <GenerativeUIErrorBoundary fallbackText={fallbackText} componentName={component}>
            {factory(props, fallbackText)}
        </GenerativeUIErrorBoundary>
    );
});
GenerativeUIRenderer.displayName = 'GenerativeUIRenderer';
