"""Check suite selection, failure policy, summaries, and workflow configuration.

Copyright (C) 2026 Junhao Wu. LPPL 1.3c or later; see LICENSE.
"""
import importlib.util
import io
import json
from pathlib import Path
import re
import tempfile
import subprocess
import sys
import unittest
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'test' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packages = load('packages')
ctan = load('ctan')
environment = load('ci-environment')
report = load('ci-report')
release = load('release')
PACKAGE_CASES = json.loads((ROOT / 'test/packages-cases.json').read_text())
CLASS_CASES = json.loads((ROOT / 'test/ctan-cases.json').read_text())


class TestCIPolicy(unittest.TestCase):
    def test_tds_keeps_runtime_sources_and_helpers_in_their_own_trees(self):
        data = {'wiseref.dtx': b'source', 'README.md': b'documentation', 'test/cases.tex': b'fixture'}
        entries = {'tex/latex/wiseref/wiseref.sty': b'runtime',
                   'source/latex/wiseref/wiseref.dtx': b'source',
                   'doc/latex/wiseref/README.md': b'documentation',
                   'doc/latex/wiseref/test/cases.tex': b'fixture'}

        def archive(files):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as writer:
                for name, content in files.items():
                    writer.writestr(name, content)
            return buffer.getvalue()

        release.validate_tds(archive(entries), data, b'runtime')
        for extra in ('tex/latex/wiseref/wiseref-probe.sty', 'doc/latex/wiseref/test/output/main.log',
                      'doc/latex/wiseref/.DS_Store'):
            with self.assertRaises(ValueError):
                release.validate_tds(archive(entries | {extra: b'extra'}), data, b'runtime')
        with self.assertRaises(ValueError):
            release.validate_tds(archive(entries | {'tex/latex/wiseref/wiseref.sty': b'stale'}), data, b'runtime')

    def test_source_staging_omits_build_results(self):
        data = release.payload(include_pdfs=False)
        self.assertFalse(any('/output/' in name or '__pycache__' in name for name in data))
        self.assertNotIn('wiseref.sty', data)
        self.assertIn('wiseref-example-en.tex', data)
        self.assertIn('wiseref-example-zh.tex', data)
        self.assertIn('build.lua', data)

    def test_release_tag_is_checked_without_building(self):
        source = (ROOT / 'wiseref.dtx').read_text()
        version = re.search(r'\\ProvidesExplPackage\{wiseref\}\{[^}]+\}\{([^}]+)\}', source).group(1)
        for tag, expected in ((f'v{version}', 0), ('v0.0-invalid', 1)):
            result = subprocess.run([sys.executable, str(ROOT / 'test/release.py'), '--check-tag', tag],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

    def test_package_suites_partition_the_full_matrix(self):
        all_jobs = {(case['name'], engine) for case, engine in packages.select_jobs(PACKAGE_CASES)}
        selected = set()
        for suite in ('portable', 'external', 'extras', 'tagging'):
            jobs = {(case['name'], engine) for case, engine in packages.select_jobs(PACKAGE_CASES, suite)}
            self.assertFalse(selected & jobs)
            selected |= jobs
        self.assertEqual(selected, all_jobs)
        self.assertEqual(len(all_jobs), 103)
        portable = packages.select_jobs(PACKAGE_CASES, 'portable')
        self.assertEqual(len(portable), 78)
        self.assertFalse(any(case.get('minted') or case.get('external') or case.get('tagged') for case, _ in portable))

    def test_empty_or_unknown_selections_fail(self):
        for kwargs in ({'names': ['misspelled']}, {'suite': 'external', 'names': ['ntheorem']}):
            with self.assertRaises(ValueError):
                packages.select_jobs(PACKAGE_CASES, **kwargs)
        for kwargs in ({'classes': ['unknown']}, {'languages': ['unknown']},
                       {'classes': ['IEEEtran'], 'languages': ['japanese']}):
            with self.assertRaises(ValueError):
                ctan.select_jobs(CLASS_CASES, **kwargs)

    def test_engine_selection(self):
        jobs = packages.select_jobs(PACKAGE_CASES, 'external', engines=['xelatex'])
        self.assertEqual(len(jobs), 4)
        self.assertEqual({engine for _, engine in jobs}, {'xelatex'})

    def test_known_error_is_only_allowed_in_its_baseline(self):
        case = next(case for case in PACKAGE_CASES if case['name'] == 'tagged-pdf')
        text = 'The number of automatic begin (13) and end (12) text-unit para hooks differ'
        self.assertEqual(packages.failure_status(case, 'baseline', text, True), 'KNOWN_BASELINE_FAILURE')
        self.assertEqual(packages.failure_status(case, 'baseline', text), 'BLOCKED_BASELINE')
        self.assertEqual(packages.failure_status(case, 'references', text, True), 'FAIL')
        self.assertEqual(packages.failure_status(case, 'observed', text, True), 'FAIL')
        self.assertEqual(packages.failure_status(case, 'baseline', text.replace('(13)', '(14)'), True), 'BLOCKED_BASELINE')
        self.assertEqual(packages.failure_status({'name': 'different-case'}, 'baseline', text, True), 'BLOCKED_BASELINE')
        self.assertEqual([case['name'] for case in PACKAGE_CASES if case.get('known_baseline_error')], ['tagged-pdf'])

    def test_ctan_baselines_and_empty_results_are_failures(self):
        self.assertTrue(ctan.results_failed([]))
        for status in ('BLOCKED_BASELINE', 'FAIL_OBSERVATION', 'FAIL_REFERENCES'):
            self.assertTrue(ctan.results_failed([{'status': 'PASS'}, {'status': status}]))
        self.assertFalse(ctan.results_failed([{'status': 'PASS'}]))

    def test_engine_year_verification(self):
        self.assertEqual(environment.verify_year(['LuaHBTeX (TeX Live 2023)', 'XeTeX (TeX Live 2023)'], '2023'), '2023')
        self.assertEqual(environment.verify_year(['pdfTeX (TeX Live 2027)'], 'latest'), '2027')
        for versions, expected in ((['LuaHBTeX (TeX Live 2024)'], '2023'),
                                   (['TeX Live 2024', 'TeX Live 2025'], 'latest'),
                                   (['unknown engine'], '2026')):
            with self.assertRaises(ValueError):
                environment.verify_year(versions, expected)

    def test_summary_does_not_count_known_failures_as_passes(self):
        counts = report.counts_for([{'status': 'PASS'}, {'status': 'KNOWN_BASELINE_FAILURE'},
                                    {'status': 'BLOCKED_BASELINE'}, {'status': 'FAIL_REFERENCES'},
                                    {'status': 'PASS', 'skipped_local_languages': ['portuguese']}])
        self.assertEqual(counts['PASS'], 2)
        self.assertEqual(counts['FAIL'], 1)
        self.assertEqual(counts['KNOWN_BASELINE_FAILURE'], 1)
        self.assertEqual(counts['BLOCKED_BASELINE'], 1)
        self.assertEqual(counts['SKIPPED_CHECKS'], 1)
        with self.assertRaises(ValueError):
            report.counts_for([{'status': 'UNKNOWN_STATUS'}])

    def test_summary_identifies_partial_runs(self):
        output = ROOT / 'test/output'
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output) as folder:
            root = Path(folder)
            (root / 'results.json').write_text(json.dumps({'expected_cases': 2, 'results': [{'status': 'PASS'}]}))
            self.assertIn('Incomplete result sets', report.render(root, 'Fixture'))

    @unittest.skipUnless((ROOT / '.github/workflows/ci.yml').is_file(),
                         'GitHub workflow files are omitted from the CTAN archive')
    def test_workflows_are_english_and_do_not_ignore_failures(self):
        for path in (ROOT / '.github').rglob('*.yml'):
            text = path.read_text(encoding='utf-8')
            self.assertTrue(text.isascii(), path)
            self.assertNotIn('continue-on-error', text)
            yaml.load(text, Loader=yaml.BaseLoader)
        ci = yaml.load((ROOT / '.github/workflows/ci.yml').read_text(), Loader=yaml.BaseLoader)
        rows = ci['jobs']['compatibility']['strategy']['matrix']['include']
        self.assertEqual({row['texlive'] for row in rows}, {'2023', '2024', '2025', '2026'})
        self.assertTrue(all('@sha256:' in row['image'] for row in rows))
        self.assertEqual(ci['jobs']['compatibility']['strategy']['fail-fast'], 'false')
        self.assertIn('pull_request', ci['on'])
        documentation = ci['jobs']['documentation']['steps']
        self.assertTrue(any(step.get('run') == 'make check-examples' for step in documentation))
        self.assertTrue(any('--check-tag' in step.get('run', '') for step in documentation))
        extended = yaml.load((ROOT / '.github/workflows/extended.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertIn('schedule', extended['on'])
        self.assertIn('workflow_dispatch', extended['on'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
