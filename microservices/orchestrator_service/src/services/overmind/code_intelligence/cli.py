import argparse
from datetime import datetime
from pathlib import Path

from app.core.logging import get_logger

from .core import StructuralCodeIntelligence
from .reporters.csv_reporter import save_csv_report
from .reporters.html_reporter import generate_heatmap_html
from .reporters.json_reporter import save_json_report
from .reporters.markdown_reporter import generate_markdown_report

logger = get_logger(__name__)


def main() -> None:
    """
    نقطة الدخول الرئيسية للتحليل.
    Main entry point for structural analysis.
    """
    args = _parse_arguments()
    _prepare_output_directory(args.output_dir)

    analysis = _run_analysis(args.repo_path, args.targets)

    _generate_all_reports(analysis, args.output_dir)
    _print_summary(analysis, args.output_dir)


def _parse_arguments() -> argparse.Namespace:
    """
    تحليل وسائط سطر الأوامر.
    Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="المرحلة الأولى: التحليل الكمي البنيوي لقاعدة الشيفرة\nPhase 1: Structural Code Intelligence Analysis (Deconstructed)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=Path.cwd(),
        help="Repository path (default: current directory)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/structural_analysis"),
        help="Report output directory",
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        default=["app/api", "app/services", "app/infrastructure", "app/application/use_cases"],
        help="Target paths for analysis",
    )
    return parser.parse_args()


def _prepare_output_directory(output_dir: Path) -> None:
    """
    تحضير دليل الإخراج.
    Prepare output directory.

    Args:
        output_dir: Output directory path
    """
    output_dir.mkdir(parents=True, exist_ok=True)


def _run_analysis(repo_path: Path, targets: list[str]):
    """
    تنفيذ التحليل البنيوي.
    Run structural analysis.

    Args:
        repo_path: Repository path
        targets: Target paths to analyze

    Returns:
        Project analysis results
    """
    analyzer = StructuralCodeIntelligence(repo_path, targets)
    return analyzer.analyze_project()


def _generate_all_reports(analysis, output_dir: Path) -> None:
    """
    إنشاء جميع التقارير.
    Generate all report formats.

    Args:
        analysis: Analysis results
        output_dir: Output directory
    """
    logger.info("📝 Generating reports...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Generate timestamped reports
    _save_timestamped_reports(analysis, output_dir, timestamp)

    # Generate latest reports
    _save_latest_reports(analysis, output_dir)


def _save_timestamped_reports(analysis, output_dir: Path, timestamp: str) -> None:
    """
    حفظ تقارير بختم زمني.
    Save timestamped reports.

    Args:
        analysis: Analysis results
        output_dir: Output directory
        timestamp: Timestamp string
    """
    save_json_report(analysis, output_dir / f"structural_analysis_{timestamp}.json")
    save_csv_report(analysis, output_dir / f"structural_analysis_{timestamp}.csv")
    generate_heatmap_html(analysis, output_dir / f"heatmap_{timestamp}.html")
    generate_markdown_report(analysis, output_dir / f"report_{timestamp}.md")


def _save_latest_reports(analysis, output_dir: Path) -> None:
    """
    حفظ التقارير الأحدث.
    Save latest reports.

    Args:
        analysis: Analysis results
        output_dir: Output directory
    """
    save_json_report(analysis, output_dir / "structural_analysis_latest.json")
    save_csv_report(analysis, output_dir / "structural_analysis_latest.csv")
    generate_heatmap_html(analysis, output_dir / "heatmap_latest.html")
    generate_markdown_report(analysis, output_dir / "report_latest.md")


def _print_summary(analysis, output_dir: Path) -> None:
    """
    طباعة ملخص التحليل.
    Print analysis summary.

    Args:
        analysis: Analysis results
        output_dir: Output directory
    """
    logger.info("✅ Analysis complete!")
    logger.info("📊 Summary:")
    logger.info("  - Files analyzed: %s", analysis.total_files)
    logger.info("  - Critical hotspots: %s", len(analysis.critical_hotspots))
    logger.info("  - High hotspots: %s", len(analysis.high_hotspots))
    logger.info("📁 Reports saved to: %s", output_dir)


if __name__ == "__main__":
    main()
