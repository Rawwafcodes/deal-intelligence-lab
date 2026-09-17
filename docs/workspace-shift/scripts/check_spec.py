"""Validate this documentation package; does not test the application."""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
errors = []
for path in root.rglob('*.md'):
    body = path.read_text(encoding='utf-8')
    for target in re.findall(r'\]\(([^)]+)\)', body):
        if '://' in target or target.startswith('#'):
            continue
        if not (path.parent / target.split('#')[0]).exists():
            errors.append(f'{path.relative_to(root)}: missing {target}')
template = json.loads((root / 'examples/reconciliation-template.json').read_text())
seen = set()
for stage in template['stages']:
    if stage['id'] in seen:
        errors.append('Duplicate stage ID')
    if not set(stage['depends_on']).issubset(seen):
        errors.append(f'Invalid dependency order: {stage["id"]}')
    seen.add(stage['id'])
if template['status'] != 'illustrative_not_executable':
    errors.append('Example must remain explicitly illustrative')
if errors:
    raise SystemExit('\n'.join(errors))
print('PASS: internal Markdown links, JSON, stage IDs and dependencies')
