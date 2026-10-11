"""Write an English CI summary without treating baseline blockers as passes.

Copyright (C) 2026 Junhao Wu. LPPL 1.3c or later; see LICENSE.
"""
import argparse
from collections import Counter
import json
from pathlib import Path


def counts_for(results):
    counts = Counter()
    for result in results:
        status = result['status']
        if status.startswith('FAIL'):
            status = 'FAIL'
        if status not in ('PASS', 'FAIL', 'BLOCKED_BASELINE', 'KNOWN_BASELINE_FAILURE', 'LIMITATION'):
            raise ValueError(f'Unrecognized test status: {status}')
        counts[status] += 1
        counts['SKIPPED_CHECKS'] += len(result.get('skipped_local_languages', []))
    return counts


def render(root, label):
    lines = [f'## {label}', '', '| Suite | Pass | Fail | Blocked baseline | Known baseline failure | Limitation | Skipped checks |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    files = sorted(set(root.rglob('results.json')) | set(root.rglob('contract-results.json')))
    incomplete = []
    for path in files:
        document = json.loads(path.read_text(encoding='utf-8'))
        results = document if isinstance(document, list) else document['results']
        counts = counts_for(results)
        name = path.relative_to(root).as_posix().replace('|', '\\|')
        lines.append('| ' + name + ' | ' + ' | '.join(str(counts[key]) for key in
                     ('PASS', 'FAIL', 'BLOCKED_BASELINE', 'KNOWN_BASELINE_FAILURE', 'LIMITATION', 'SKIPPED_CHECKS')) + ' |')
        if isinstance(document, dict) and document.get('expected_cases', len(results)) != len(results):
            incomplete.append(name)
    if not files:
        lines += ['', 'No test result files were recorded. Check the setup and test step logs.']
    if incomplete:
        lines += ['', 'Incomplete result sets: ' + ', '.join(incomplete) + '. Check the failed or cancelled steps.']
    lines += ['', 'Known baseline failures, blocked baselines, limitations, and skipped checks are not passes.',
              'The job conclusion also includes command failures before a JSON result was written.',
              'Download the log artifact for engine/package versions, sources, and individual failures.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('test/output'))
    parser.add_argument('--label', required=True)
    parser.add_argument('--summary', type=Path, required=True)
    args = parser.parse_args()
    with args.summary.open('a', encoding='utf-8') as stream:
        stream.write(render(args.root, args.label))


if __name__ == '__main__':
    main()
