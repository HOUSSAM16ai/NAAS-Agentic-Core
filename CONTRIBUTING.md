# Contributing

We welcome contributions to this open-source project! Please follow these guidelines to ensure a smooth collaboration.

## Getting Started

1. **Fork the Repository** and clone it locally.
2. **Install Dependencies:** `pip install -r requirements.txt`.
3. **Verify Installation:** Run `pytest tests/` to ensure everything is working.

## Style & Linting

We enforce strict Python formatting. Please run:
```bash
ruff check .
ruff format .
```
before submitting your changes.

## Testing

New features must include unit tests. Run the full test suite with:
```bash
pytest tests/
```

## Adding Evaluation Suites

We encourage community contributions of new red-teaming datasets or evaluation protocols.

To add a new suite:
1. **Define the Suite:** Create a new folder under `evaluation/suites/`.
2. **Scoring Rules:** Include a `scoring.py` file implementing the evaluation logic.
3. **Example Report:** Provide a `report_example.json` demonstrating the expected output format.

Example Structure:
```text
evaluation/suites/
  └── my_new_suite/
      ├── dataset.jsonl       # Red-teaming prompts
      ├── scoring.py          # Logic for bypass/interception
      └── report_example.json # Example metrics
```

## Pull Request Checklist

- [ ] Documentation updated (if applicable).
- [ ] Tests passed locally.
- [ ] Formatting checks passed.
- [ ] Evaluation suites include example reports.
- [ ] No PII or sensitive data included.
