# Structural Code Intelligence - Quick Reference

## Quick Start

```bash
# Run full analysis
make analyze-structure

# Or directly
python3 tools/structural_code_intelligence.py
```

## Output Files

All reports are saved to `reports/structural_analysis/`:

- `structural_analysis_latest.json` - JSON data for programmatic access
- `structural_analysis_latest.csv` - CSV for spreadsheet analysis
- `heatmap_latest.html` - Visual heatmap (open in browser)
- `report_latest.md` - Markdown documentation

## View Results

```bash
# Open HTML heatmap
open reports/structural_analysis/heatmap_latest.html

# View Markdown report
cat reports/structural_analysis/report_latest.md

# Analyze JSON with jq
cat reports/structural_analysis/structural_analysis_latest.json | jq '.critical_hotspots'
```

## Custom Analysis

```bash
# Analyze specific paths
python3 tools/structural_code_intelligence.py \
  --targets app/api app/services

# Custom output directory
python3 tools/structural_code_intelligence.py \
  --output-dir my_reports

# Different project
python3 tools/structural_code_intelligence.py \
  --repo-path /path/to/project
```

## Understanding Results

### Hotspot Score Formula

```
Score = 0.4 × Complexity_Rank + 0.4 × Volatility_Rank + 0.2 × Smell_Rank
```

### Priority Tiers

- **CRITICAL** (≥0.7): Immediate action required
- **HIGH** (≥0.5): Address in Phase 1
- **MEDIUM** (≥0.3): Address in Phase 2
- **LOW** (<0.3): Monitor only

### Structural Smells

- **God Class**: >500 LOC or >20 methods
- **Layer Mixing**: Multiple architectural layers in one file
- **Cross-Layer Imports**: Wrong dependency direction

## Integration

### CI/CD
```yaml
# .github/workflows/code-quality.yml
- name: Structural Analysis
  run: python3 tools/structural_code_intelligence.py
```

### Make Commands
```bash
make analyze-structure    # Run analysis
make view-heatmap        # Open HTML report
make compare-baseline    # Compare with baseline
```

## Full Documentation

See `docs/STRUCTURAL_ANALYSIS_GUIDE_AR.md` for comprehensive guide.

---

**Phase 1: Measurement Only - No Refactoring**
