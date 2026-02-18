"""
قوالب HTML للتقارير | HTML Templates for Reports.

هذا الملف يحتوي على جميع قوالب HTML المستخدمة في تقارير تحليل الكود.
فصل القوالب عن منطق البرمجة يجعل الكود أنظف وأسهل في الصيانة.

المبادئ المطبقة:
- Separation of Concerns: فصل العرض (Presentation) عن المنطق (Logic)
- DRY: قوالب قابلة لإعادة الاستخدام
- KISS: قوالب بسيطة وواضحة
"""


def _get_base_styles() -> str:
    """
    أنماط CSS الأساسية للصفحة (body, container, headings).

    Returns:
        str: أنماط CSS الأساسية
    """
    return """
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a1a1a;  /* خلفية داكنة للراحة البصرية */
            color: #e0e0e0;       /* نص فاتح للتباين */
            padding: 20px;        /* مسافة حول المحتوى */
            direction: rtl;       /* اتجاه النص من اليمين لليسار */
        }
        .container {
            max-width: 1400px;    /* عرض أقصى للقراءة المريحة */
            margin: 0 auto;       /* توسيط المحتوى */
        }
        h1 {
            color: #00d4ff;       /* لون مميز للعنوان الرئيسي */
            text-align: center;
            margin-bottom: 10px;
        }
    """


def _get_summary_styles() -> str:
    """
    أنماط CSS لمنطقة الملخص والإحصائيات.

    Returns:
        str: أنماط CSS للملخص
    """
    return """
        .summary {
            background: #2a2a2a;  /* خلفية أفتح قليلاً */
            padding: 20px;
            border-radius: 8px;   /* زوايا مستديرة */
            margin-bottom: 30px;
            border-left: 4px solid #00d4ff;  /* شريط جانبي مميز */
        }
        .summary h2 {
            margin-top: 0;
            color: #00d4ff;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));  /* شبكة متجاوبة */
            gap: 15px;
            margin-top: 15px;
        }
        .stat {
            background: #1a1a1a;
            padding: 15px;
            border-radius: 6px;
        }
        .stat-label {
            color: #888;          /* لون أغمق للتسميات */
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #00d4ff;       /* لون مميز للقيم */
        }
    """


def _get_heatmap_file_row_styles() -> str:
    """
    أنماط CSS لصفوف الملفات في الخريطة الحرارية.

    Returns:
        str: أنماط CSS لصفوف الملفات
    """
    return """
        .heatmap {
            display: grid;
            gap: 10px;
        }
        .file-row {
            background: #2a2a2a;
            padding: 15px;
            border-radius: 6px;
            border-right: 6px solid;  /* الشريط الجانبي الملون */
            transition: transform 0.2s;  /* حركة سلسة عند التفاعل */
        }
        .file-row:hover {
            transform: translateX(-5px);  /* حركة طفيفة عند المرور */
            box-shadow: 0 4px 12px rgba(0, 212, 255, 0.3);  /* ظل توضيحي */
        }
        .file-name {
            font-size: 1.1em;
            font-weight: bold;
            margin-bottom: 10px;
            color: #fff;
        }
        .file-metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            font-size: 0.9em;
        }
        .metric {
            display: flex;
            justify-content: space-between;
        }
        .metric-label {
            color: #888;
        }
        .metric-value {
            color: #00d4ff;
            font-weight: bold;
        }
    """


def _get_severity_color_styles() -> str:
    """
    أنماط CSS لألوان مستويات الخطورة (critical, high, medium, low).

    Returns:
        str: أنماط CSS لألوان الخطورة
    """
    return """
        /* ألوان حسب مستوى الخطورة */
        .file-row.critical {
            border-right-color: #ff4444;  /* أحمر للحرج */
            background: linear-gradient(90deg, #2a2a2a 0%, #3a1a1a 100%);
        }
        .file-row.high {
            border-right-color: #ff9944;  /* برتقالي للعالي */
            background: linear-gradient(90deg, #2a2a2a 0%, #3a2a1a 100%);
        }
        .file-row.medium {
            border-right-color: #ffdd44;  /* أصفر للمتوسط */
            background: linear-gradient(90deg, #2a2a2a 0%, #3a3a1a 100%);
        }
        .file-row.low {
            border-right-color: #44ff44;  /* أخضر للمنخفض */
            background: linear-gradient(90deg, #2a2a2a 0%, #1a3a1a 100%);
        }
    """


def _get_badge_styles() -> str:
    """
    أنماط CSS للشارات (badges) حسب مستوى الخطورة.

    Returns:
        str: أنماط CSS للشارات
    """
    return """
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
            margin-right: 8px;
        }
        .badge.critical {
            background: #ff4444;
            color: white;
        }
        .badge.high {
            background: #ff9944;
            color: white;
        }
        .badge.medium {
            background: #ffdd44;
            color: black;
        }
        .badge.low {
            background: #44ff44;
            color: black;
        }
    """


def _get_legend_styles() -> str:
    """
    أنماط CSS لدليل الألوان (legend).

    Returns:
        str: أنماط CSS لدليل الألوان
    """
    return """
        .legend {
            background: #2a2a2a;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }
        .legend-items {
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
            margin-top: 10px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .legend-color {
            width: 30px;
            height: 20px;
            border-radius: 4px;
        }
    """


def get_html_styles() -> str:
    """
    الحصول على أنماط CSS الكاملة للتقرير.

    Returns:
        str: كود CSS كامل مُجمّع من جميع helper methods

    ملاحظة:
        تم تقسيم الأنماط إلى helper methods صغيرة لتطبيق مبدأ SRP (Single Responsibility).
        كل helper method مسؤول عن مجموعة أنماط محددة فقط.
    """
    return (
        _get_base_styles()
        + _get_summary_styles()
        + _get_heatmap_file_row_styles()
        + _get_severity_color_styles()
        + _get_badge_styles()
        + _get_legend_styles()
    )


def create_file_row_html(
    relative_path: str,
    priority_tier: str,
    hotspot_score: float,
    file_complexity: int,
    code_lines: int,
    num_functions: int,
    commits_last_12months: int,
    bugfix_commits: int,
    smells_html: str,
) -> str:
    """
    إنشاء HTML لصف ملف واحد في الخريطة الحرارية.

    Args:
        relative_path: المسار النسبي للملف
        priority_tier: مستوى الأولوية (Critical, High, Medium, Low)
        hotspot_score: درجة الخطورة (0.0 - 1.0)
        file_complexity: التعقيد الكلي للملف
        code_lines: عدد أسطر الكود
        num_functions: عدد الدوال
        commits_last_12months: عدد التعديلات في آخر 12 شهر
        bugfix_commits: عدد commits إصلاح الأخطاء
        smells_html: الروائح البنيوية (HTML formatted)

    Returns:
        str: HTML كامل لصف الملف

    ملاحظة: كل معامل له دور واضح في بناء التقرير
    """
    tier_class = priority_tier.lower()  # تحويل إلى lowercase لاستخدامه كـ CSS class

    return f"""
        <div class="file-row {tier_class}">
            <div class="file-name">
                <span class="badge {tier_class}">{priority_tier}</span>
                {relative_path}
            </div>
            <div class="file-metrics">
                <div class="metric">
                    <span class="metric-label">درجة الخطورة:</span>
                    <span class="metric-value">{hotspot_score:.4f}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">التعقيد الكلي:</span>
                    <span class="metric-value">{file_complexity}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">أسطر الكود:</span>
                    <span class="metric-value">{code_lines}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">الدوال:</span>
                    <span class="metric-value">{num_functions}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">التعديلات (12 شهر):</span>
                    <span class="metric-value">{commits_last_12months}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">إصلاحات الأخطاء:</span>
                    <span class="metric-value">{bugfix_commits}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">الروائح البنيوية:</span>
                    <span class="metric-value">{smells_html}</span>
                </div>
            </div>
        </div>"""


def create_complete_html(
    timestamp: str,
    total_files: int,
    total_code_lines: int,
    total_functions: int,
    total_classes: int,
    avg_file_complexity: float,
    max_file_complexity: int,
    file_rows_html: str,
) -> str:
    """
    إنشاء HTML كامل للتقرير.

    Args:
        timestamp: وقت إنشاء التقرير
        total_files: إجمالي عدد الملفات
        total_code_lines: إجمالي أسطر الكود
        total_functions: إجمالي عدد الدوال
        total_classes: إجمالي عدد الكلاسات
        avg_file_complexity: متوسط التعقيد
        max_file_complexity: أقصى تعقيد
        file_rows_html: HTML لجميع صفوف الملفات (مجمّعة)

    Returns:
        str: مستند HTML كامل

    ملاحظة: تم تقسيم الدالة إلى helper methods لتطبيق KISS
    """
    styles = get_html_styles()
    header = _create_html_header(timestamp)
    summary = _create_summary_section(
        total_files,
        total_code_lines,
        total_functions,
        total_classes,
        avg_file_complexity,
        max_file_complexity,
    )
    legend = _create_legend_section()

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>خريطة حرارية - التحليل البنيوي للكود</title>
    <style>{styles}</style>
</head>
<body>
    <div class="container">
        {header}
        {summary}
        {legend}
        <div class="heatmap">
            {file_rows_html}
        </div>
    </div>
</body>
</html>"""


def _create_html_header(timestamp: str) -> str:
    """إنشاء رأس الصفحة مع العنوان والتاريخ."""
    return f"""<h1>🔥 خريطة حرارية - التحليل البنيوي للكود</h1>
        <p style="text-align: center; color: #888;">تم الإنشاء: {timestamp}</p>"""


def _create_summary_section(
    total_files: int,
    total_code_lines: int,
    total_functions: int,
    total_classes: int,
    avg_file_complexity: float,
    max_file_complexity: int,
) -> str:
    """إنشاء قسم الملخص مع الإحصائيات."""
    stats = _create_stat_items(
        total_files,
        total_code_lines,
        total_functions,
        total_classes,
        avg_file_complexity,
        max_file_complexity,
    )
    return f"""<div class="summary">
            <h2>📊 ملخص المشروع</h2>
            <div class="stats">
                {stats}
            </div>
        </div>"""


def _create_stat_items(
    total_files: int,
    total_code_lines: int,
    total_functions: int,
    total_classes: int,
    avg_file_complexity: float,
    max_file_complexity: int,
) -> str:
    """إنشاء عناصر الإحصائيات."""
    stat_data = [
        ("إجمالي الملفات", total_files),
        ("أسطر الكود", f"{total_code_lines:,}"),
        ("إجمالي الدوال", total_functions),
        ("إجمالي الكلاسات", total_classes),
        ("متوسط التعقيد", f"{avg_file_complexity:.1f}"),
        ("أقصى تعقيد", max_file_complexity),
    ]

    return "\n".join(
        f"""<div class="stat">
                    <div class="stat-label">{label}</div>
                    <div class="stat-value">{value}</div>
                </div>"""
        for label, value in stat_data
    )


def _create_legend_section() -> str:
    """إنشاء قسم دليل الألوان."""
    legend_items = [
        ("#ff4444", "حرج (≥0.7)"),
        ("#ff9944", "عالي (≥0.5)"),
        ("#ffdd44", "متوسط (≥0.3)"),
        ("#44ff44", "منخفض (&lt;0.3)"),
    ]

    items_html = "\n".join(
        f"""<div class="legend-item">
                    <div class="legend-color" style="background: {color};"></div>
                    <span>{label}</span>
                </div>"""
        for color, label in legend_items
    )

    return f"""<div class="legend">
            <h3>دليل الألوان</h3>
            <div class="legend-items">
                {items_html}
            </div>
        </div>"""
