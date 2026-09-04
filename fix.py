import sys

with open('tests/telemetry/test_otel_setup.py', 'r') as f:
    lines = f.readlines()

imports_to_move = []
other_lines = []

for line in lines:
    if line.startswith('import logging') or line.startswith('import sys') or line.startswith('from unittest.mock import MagicMock') or line.startswith('from app.telemetry.otel_setup import _try_instrument_httpx'):
        imports_to_move.append(line)
    elif line.strip() == '' and not other_lines and not imports_to_move:
        # ignore empty lines at top
        pass
    else:
        other_lines.append(line)

final_lines = []
for line in lines:
    if line.startswith('import pytest'):
        final_lines.append(line)
        for i in imports_to_move:
            final_lines.append(i)
    elif line not in imports_to_move:
        final_lines.append(line)

with open('tests/telemetry/test_otel_setup.py', 'w') as f:
    f.writelines(final_lines)
