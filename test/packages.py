"""Test package interactions against isolated ordinary-reference baselines.

Passing observation checks establish that loading wiseref preserves numbering,
text, character positions, and other packages' references. Actual wref calls
also assert types, formatting and links. Additional counters receive explicit
formats; external label metadata uses LaTeX's public record-property interface.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('reference_tests', ROOT / 'test/run.py')
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
ENGINES = ('lualatex', 'xelatex', 'pdflatex')
SUITES = ('all', 'portable', 'external', 'extras', 'tagging')


def suite_for(case):
    if case.get('tagged'):
        return 'tagging'
    if case.get('external'):
        return 'external'
    if case.get('biblatex') or case.get('minted'):
        return 'extras'
    return 'portable'


def select_jobs(manifest, suite='all', names=None, engines=ENGINES):
    unknown = set(names or ()) - {case['name'] for case in manifest}
    if unknown:
        raise ValueError('Unknown package cases: ' + ', '.join(sorted(unknown)))
    jobs = [(case, engine) for case in manifest for engine in case.get('engines', ENGINES)
            if engine in engines and (suite == 'all' or suite_for(case) == suite)
            and (not names or case['name'] in names)]
    if not jobs:
        raise ValueError('No package tests selected')
    return jobs


def failure_status(case, phase, log, allow_known_baselines=False):
    if phase != 'baseline':
        return 'FAIL'
    pattern = case.get('known_baseline_error')
    if allow_known_baselines and pattern and re.search(pattern, log, re.S):
        return 'KNOWN_BASELINE_FAILURE'
    return 'BLOCKED_BASELINE'


CHECKS = r'''
\wiserefsetup{lang=en,lstlisting={prefix={Listing~}},
              algorithm={prefix={Algorithm~}},algocf={prefix={Algorithm~}},
              listing={prefix={Listing~}},claim={prefix={Claim~}},
              framedtheorem={prefix={Framed~}},tcb@cnt@wisebox={prefix={Boxed~}}}
\newcommand\WiseCase[2]{\par\noindent CASE-#1-BEGIN #2 CASE-#1-END\par}
'''


def driver(case, loaded, references=False):
    early = loaded and case.get('order') == 'before'
    lines = ([r'\DocumentMetadata{lang=en-US,tagging=on}'] if case.get('tagged') else [])
    lines += [r'\documentclass{article}', r'\errorcontextlines=100']
    if case.get('shared_theorem'):
        # thmtools already provides aliases. The 2026 amsthm first-aid rewrite
        # otherwise tries to create lemma -> lemma a second time.
        lines.append(r'\RemoveFromHook{package/amsthm/after}[firstaid/aliascounter]')
    if early:
        lines.append(r'\usepackage{wiseref}')
    lines.append(r'\usepackage{' + ('mathtools' if case.get('mathtools') else 'amsmath') + '}')
    if case.get('mathtools'):
        lines.append(r'\def\WiseMathtools{1}')
    if case.get('showonlyrefs'):
        lines.append(r'\mathtoolsset{showonlyrefs}')
    if case.get('unicode'):
        font = {'Latin Modern Math': 'latinmodern-math.otf',
                'TeX Gyre Termes Math': 'texgyretermes-math.otf'}[case['unicode']]
        lines += [r'\usepackage{unicode-math}', r'\setmathfont{' + font + '}',
                  r'\def\WiseUnicode{1}']
    if case.get('theorems') == 'ntheorem':
        lines.append(r'\usepackage[amsmath,hyperref]{ntheorem}')
    else:
        lines.append(r'\usepackage{amsthm}')
    if case.get('theorems') == 'thmtools':
        lines += [r'\usepackage{thmtools}', r'\declaretheorem[numberwithin=section]{theorem}',
                  r'\declaretheorem[' + ('sibling=theorem' if case.get('shared_theorem') else 'numberwithin=section') + ']{lemma}']
    else:
        lines += [r'\newtheorem{theorem}{Theorem}[section]', r'\newtheorem{lemma}[theorem]{Lemma}']
    if case.get('nt_stress'):
        lines += [r'\newtheorem{claim}[theorem]{Claim}', r'\newtheorem*{remark}{Remark}',
                  r'\def\WiseNTStress{1}']
    lines.append(r'\usepackage{' + ('subfig' if case.get('subfig') else 'subcaption') + '}')
    if case.get('subfig'):
        lines.append(r'\def\WiseSubfig{1}')
    if case.get('enumitem'):
        lines += [r'\usepackage{enumitem}', r'\def\WiseEnumitem{1}']
    if case.get('listing'):
        lines += [r'\usepackage{listings,longtable}', r'\def\WiseListing{1}']
    if case.get('algorithm'):
        lines += [r'\usepackage{algorithm,algpseudocode}', r'\def\WiseAlgorithm{1}']
    if case.get('algorithm2e'):
        lines += [r'\usepackage{algorithm2e}', r'\def\WiseAlgorithmTwo{1}']
    if case.get('biblatex'):
        lines += [r'\usepackage[backend=biber,style=' + case['biblatex'] + ']{biblatex}',
                  r'\addbibresource{sample.bib}', r'\def\WiseBibliography{1}']
    if case.get('minted'):
        lines += [r'\usepackage{minted}', r'\def\WiseMinted{1}']
    if case.get('tcolorbox'):
        lines += [r'\usepackage{tcolorbox}', r'\tcbuselibrary{theorems,breakable}',
                  r'\newtcbtheorem[number within=section]{wisebox}{Boxed theorem}{breakable}{bx}',
                  r'\def\WiseTcolorbox{1}']
    if case.get('mdframed'):
        lines += [r'\usepackage{mdframed}',
                  r'\newmdtheoremenv{framedtheorem}{Framed theorem}[section]',
                  r'\def\WiseMdframed{1}']
    if case.get('restatable'):
        lines.append(r'\def\WiseRestatable{1}')
    if case.get('references') == 'varioref':
        lines += [r'\usepackage{varioref}', r'\def\WiseVarioref{1}']
    if case.get('external'):
        lines += [r'\usepackage{' + case.get('xr', 'xr-hyper') + '}', r'\externaldocument[remote-]{external}',
                  r'\def\WiseExternal{1}']
    if loaded and not early and case.get('order') != 'after':
        lines.append(r'\usepackage{wiseref}')
    lines.append(r'\usepackage{hyperref}')
    if case.get('references') == 'cleveref':
        lines += [r'\usepackage{cleveref}', r'\def\WiseCleveref{1}']
    elif case.get('references') == 'zref-clever':
        lines += [r'\usepackage{zref-clever}', r'\def\WiseZref{1}']
    if loaded and case.get('order') == 'after':
        lines.append(r'\usepackage{wiseref}')
    if references:
        lines += [r'\def\WiseChecks{1}', CHECKS]
        if case.get('external'):
            lines += [r'\ExplSyntaxOn',
                      r'\__wise_get_type:n{remote-equation}',
                      r'\iow_term:e{WISE-EXTERNAL-TYPE:\l__wise_current_type_tl/\l__wise_format_mode_tl}',
                      r'\ExplSyntaxOff']
        if case.get('explicit_lemma'):
            lines.append(r'\AddToHook{env/lemma/begin}{\wisereftype{lemma}}')
    lines.append(r'\input{cases.tex}')
    return '\n'.join(lines) + '\n'


def compile_document(folder, engine, env, external=False, shell_restricted=False, bibliography=False, biber='biber'):
    job = 'external' if external else 'main'
    with (folder / (job + '-compile.log')).open('w') as stream:
        for run in range(5):
            subprocess.run([engine, '-shell-restricted' if shell_restricted else '-no-shell-escape',
                            '-recorder', '-interaction=nonstopmode',
                            '-halt-on-error', job + '.tex'], cwd=folder, env=env,
                           stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=120)
            log = (folder / (job + '.log')).read_text(errors='replace')
            if bibliography and run == 0:
                subprocess.run([biber, '--noconf', job], cwd=folder, env=env,
                               stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=120)
            rerun = re.search(r'undefined references|Label\(s\) may have changed|Rerun to get wiseref|Rerun to get cross-references', log)
            if run >= 2 and not rerun:
                break
    assert not rerun, 'Unconverged references after five runs'
    assert 'Missing character:' not in log
    return log


def all_links(path):
    reader = PdfReader(path)

    def semantic(value):
        if hasattr(value, 'get_object'):
            value = value.get_object()
        if isinstance(value, dict):
            if value.get('/Type') == '/StructElem':
                # Structure destinations have cyclic parent links. Compare the
                # destination's stable identity/role, not a PdfReader memory ID.
                return ('StructElem', str(value.get('/ID')), str(value.get('/S')))
            if value.get('/Type') == '/Page':
                return ('Page', next((i for i, page in enumerate(reader.pages)
                                     if page.indirect_reference == value.indirect_reference), None))
            return tuple(sorted((str(key), semantic(item)) for key, item in value.items()))
        if isinstance(value, (list, tuple)):
            return tuple(semantic(item) for item in value)
        return str(value)

    result = []
    for index, page in enumerate(reader.pages):
        for entry in page.get('/Annots', []):
            obj = entry.get_object()
            if obj.get('/Subtype') == '/Link':
                result.append((index, tuple(obj['/Rect']), repr(semantic(obj.get('/A', obj.get('/Dest'))))))
    return result


def compile_phase(root, phase, case, engine, work, biber='biber'):
    folder = root / phase
    folder.mkdir(parents=True)
    shutil.copy2(work / 'candidate.sty', folder / 'wiseref.sty')
    fixture = 'tagged.tex' if case.get('tagged_simple') else 'packages.tex'
    shutil.copy2(ROOT / 'test' / fixture, folder / 'cases.tex')
    (folder / 'main.tex').write_text(driver(case, phase != 'baseline', phase == 'references'))
    if case.get('biblatex'):
        (folder / 'sample.bib').write_text('@book{sample, author={Doe, Jane}, title={Sample book}, date={2020}, publisher={Example Press}}\n')
    env = os.environ.copy()
    env.update(TEXINPUTS='.:', TEXMFHOME=str(work / 'empty-texmf'))
    if case.get('external'):
        (folder / 'external.tex').write_text(r'''
\documentclass{article}\usepackage{amsmath,wiseref}\usepackage{hyperref}
\begin{document}
\begin{equation}a=b\label{equation}\end{equation}
\begin{equation}a=c\label{next}\end{equation}
\begin{equation}a=d\label{third}\end{equation}
\begin{equation}c=d\tag{S}\label{tagged}\end{equation}
\begin{equation}e=f\tag*{S}\label{bare}\end{equation}
\appendix\section{Supplement}\label{appendix}
\end{document}
''')
        compile_document(folder, engine, env, external=True)
    return compile_document(folder, engine, env, shell_restricted=bool(case.get('minted')),
                            bibliography=bool(case.get('biblatex')), biber=biber)


def number(labels, key):
    return base.arguments(labels[key][0], 0, 2)[0].replace('{', '').replace('}', '')


def expectations(case, labels):
    def n(key):
        return number(labels, key)
    if case.get('tagged_simple'):
        return {'figure': 'Figure ' + n('picture'), 'table': 'Table ' + n('table'),
                'equation': 'Equation (' + n('equation') + ')',
                'only-wise': 'Equation (' + n('only-wise') + ')',
                'align': 'Equations (' + n('line-a') + ') and (' + n('line-b') + ')',
                'range': 'Equations (' + n('equation') + ')–(' + n('line-a') + ')',
                'tagged': 'Equation (S)', 'bare': 'Equation S',
                'appendix': 'Appendix ' + n('appendix'), 'star': 'Figure ' + n('picture')}
    result = {
        'figure': 'Figure ' + n('picture'), 'table': 'Table ' + n('table'),
        'equation': 'Equation (' + n('equation') + ')',
        'only-wise': 'Equation (' + n('only-wise') + ')',
        'align': 'Equations (' + n('line-a') + ') and (' + n('line-b') + ')',
        'range': 'Equations (' + n('equation') + ')–(' + n('line-a') + ')',
        'subequation': 'Equation (' + n('child-a') + ')',
        'tagged': 'Equation (S)', 'bare': 'Equation S',
        'theorem': 'Theorem ' + n('statement'), 'lemma': 'Lemma ' + n('lemma'),
        'panel': 'Figure ' + n('panel'), 'item': 'Item ' + n('item'),
        'footnote': 'Footnote ' + n('note'), 'appendix': 'Appendix ' + n('appendix'),
        'star': 'Figure ' + n('picture'),
    }
    if case.get('mathtools'):
        result['split'] = 'Equation (' + n('split') + ')'
    if case.get('listing'):
        result.update({'listing': 'Listing ' + n('program'), 'longtable': 'Table ' + n('long-table')})
    if case.get('algorithm') or case.get('algorithm2e'):
        result['algorithm'] = 'Algorithm ' + n('procedure')
    if case.get('external'):
        result.update({'external': 'Equation (1)', 'external-tag': 'Equation (S)',
                       'external-bare': 'Equation S', 'external-appendix': 'Appendix A',
                       'external-range': 'Equations (1)–(3)',
                       'origins': 'Equations (1), (2) and (3)'})
    if case.get('nt_stress'):
        result.update({'nt-claim': 'Claim ' + n('nt-claim'),
                       'nt-title': 'Lemma ' + n('nt-title'),
                       'nt-nested': 'Lemma ' + n('nt-nested'),
                       'nt-equation': 'Equation (' + n('nt-equation') + ')',
                       'nt-footnote': 'Footnote ' + n('nt-footnote'),
                       'nt-star': n('nt-star')})
    if case.get('minted'):
        result['minted'] = 'Listing ' + n('minted-code')
    if case.get('tcolorbox'):
        result['boxed'] = 'Boxed ' + n('bx:box')
    if case.get('mdframed'):
        result['framed'] = 'Framed ' + n('framed')
    if case.get('restatable'):
        result['restated'] = 'Theorem ' + n('restated')
    return result


def test_case(work, case, engine, biber='biber', allow_known_baselines=False):
    root = work / (case['name'] + '-' + engine)
    result = dict(case=root.name, engine=engine, settings=case)
    phase = 'baseline'
    try:
        baseline_log = compile_phase(root, phase, case, engine, work, biber)
        phase = 'observed'
        compile_phase(root, phase, case, engine, work, biber)
        labels = base.records(root / 'baseline/main.aux', 'newlabel', 2)
        assert labels == base.records(root / 'observed/main.aux', 'newlabel', 2), 'Standard label records changed'
        assert base.pdf_signature(root / 'baseline/main.pdf') == base.pdf_signature(root / 'observed/main.pdf'), 'Text or character positions changed'
        assert all_links(root / 'baseline/main.pdf') == all_links(root / 'observed/main.pdf'), 'Ordinary links changed'
        phase = 'references'
        log = compile_phase(root, phase, case, engine, work, biber)
        actual_labels = base.records(root / phase / 'main.aux', 'newlabel', 2)
        if not case.get('showonlyrefs'):
            assert labels == actual_labels, 'Using wref changed ordinary numbering'
        wise = base.records(root / phase / 'main.aux', 'wiserefRecord', 3)
        types = {'picture': 'figure', 'table': 'table', 'equation': 'equation',
                 'only-wise': 'equation', 'line-a': 'equation', 'line-b': 'equation',
                 'child-a': 'equation', 'tagged': 'equation', 'bare': 'equation',
                 'statement': 'theorem', 'lemma': 'lemma', 'panel': 'subfigure',
                 'item': 'enumi', 'note': 'footnote', 'appendix': 'appendix', 'unnumbered': ''}
        if case.get('tagged_simple'):
            types = {key: kind for key, kind in types.items()
                     if key in ('picture', 'table', 'equation', 'only-wise',
                                'line-a', 'line-b', 'tagged', 'bare', 'appendix')}
        if case.get('mathtools'):
            types['split'] = 'equation'
        if case.get('listing'):
            types.update({'program': 'lstlisting', 'long-table': 'table'})
        if case.get('algorithm') or case.get('algorithm2e'):
            types['procedure'] = 'algorithm' if case.get('algorithm') else 'algocf'
        if case.get('nt_stress'):
            types.update({'nt-claim': 'claim', 'nt-title': 'lemma', 'nt-nested': 'lemma',
                          'nt-equation': 'equation', 'nt-footnote': 'footnote', 'nt-star': ''})
        if case.get('minted'):
            types['minted-code'] = 'listing'
        if case.get('tcolorbox'):
            types['bx:box'] = 'tcb@cnt@wisebox'
        if case.get('mdframed'):
            types['framed'] = 'framedtheorem'
        if case.get('restatable'):
            types['restated'] = 'theorem'
        for key, kind in types.items():
            assert wise.get(key, [None])[0] == kind, (key, 'wrong type', wise.get(key), kind)
        assert wise['tagged'][1] == 'tag' and wise['bare'][1] == 'bare'
        if case.get('showonlyrefs'):
            for key in ('equation', 'only-wise', 'line-a', 'line-b', 'child-a', 'split'):
                assert number(actual_labels, key), ('Referenced equation has no number', key)
            numbers = [number(actual_labels, key) for key in
                       ('equation', 'only-wise', 'line-a', 'line-b', 'split')]
            assert len(set(numbers)) == len(numbers), ('Referenced equations share stale hidden numbers', numbers)
            for key in ('only-wise', 'line-a', 'line-b', 'child-a', 'split'):
                assert r'\MT@newlabel{' + key + '}' in (root / phase / 'main.aux').read_text(), key
        wanted = expectations(case, actual_labels)
        text = ''.join(page[0] for page in base.pdf_signature(root / phase / 'main.pdf'))
        if case.get('biblatex'):
            assert 'Sample book' in text and 'Doe' in text, 'Bibliography not rendered'
            assert 'Please (re)run Biber' not in log and 'undefined citations' not in log
        if case.get('minted'):
            assert 'print' in text and 'value' in text, 'Highlighted code not rendered'
            assert any(folder.name.startswith('_minted') for folder in (root / phase).iterdir()), 'Minted cache not generated'
        if case.get('tagged'):
            reader = PdfReader(root / phase / 'main.pdf')
            assert '/StructTreeRoot' in reader.trailer['/Root'], 'PDF not tagged'
        outputs = {}
        for key, value in wanted.items():
            match = re.search('CASE-' + key + '-BEGIN(.*?)CASE-' + key + '-END', text, re.S)
            assert match, ('missing output', key)
            outputs[key] = re.sub(r'\s+', ' ', match[1]).strip()
            assert outputs[key] == value, (key, value, outputs[key])
        links, _ = base.link_signature(root / phase / 'main.pdf')
        annotations = [(page, tuple(float(x) for x in rect), action, 0)
                       for page, rect, action in all_links(root / phase / 'main.pdf')]
        base.assert_case_links(root / phase / 'main.pdf', annotations, wanted)
        assert links
        inputs = (root / phase / 'main.fls').read_text()
        assert 'hithesis.cls' not in inputs and 'docxlike.sty' not in inputs
        versions = re.findall(r'Package: (?:unicode-math\S*|mathtools|cleveref|varioref|zref-clever|thmtools|ntheorem|subcaption|subfig|caption|enumitem|listings|longtable|algorithm\S*|xr(?:-hyper)?|hyperref|biblatex|minted\S*|tcolorbox|mdframed|tagpdf\S*|latex-lab\S*|fontspec\S*) [^\n]+', baseline_log)
        result.update(status='PASS', assertions=len(wanted), type_assertions=len(types),
                      versions=versions, output=outputs, links=len(links))
        if case.get('external'):
            assert any('external.pdf' in action and ('/GoToR' in action or '/URI' in action)
                       for _, _, action, _ in annotations), 'Missing external PDF link'
            assert 'WISE-EXTERNAL-TYPE:equation/normal' in log
            assert 'has no numbered target' not in log
    except Exception as error:
        path = root / phase / 'main-compile.log'
        log = path.read_text(errors='replace') if path.exists() else ''
        result.update(status=failure_status(case, phase, log, allow_known_baselines),
                      phase=phase, error=str(error), log=str(path))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--suite', choices=SUITES, default='all')
    parser.add_argument('--engines', nargs='+', choices=ENGINES, default=ENGINES)
    parser.add_argument('--allow-known-baselines', action='store_true',
                        help='Report only manifest-listed baseline errors as known failures, never as passes')
    parser.add_argument('--jobs', type=int, default=3)
    parser.add_argument('--biber', default='biber', help='Biber executable for bibliography fixtures')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'test/packages-cases.json').read_text())
    try:
        jobs = select_jobs(manifest, args.suite, args.cases, args.engines)
    except ValueError as error:
        parser.error(str(error))
    args.work.mkdir(parents=True, exist_ok=False)
    (args.work / 'empty-texmf').mkdir()
    shutil.copy2(ROOT / 'wiseref.sty', args.work / 'candidate.sty')
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(test_case, args.work, case, engine, args.biber, args.allow_known_baselines)
                   for case, engine in jobs]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(result['case'], result['status'], result.get('error', result.get('limitation', '')), flush=True)
            (args.work / 'results.json').write_text(json.dumps(dict(
                 candidate_sha256=hashlib.sha256((args.work / 'candidate.sty').read_bytes()).hexdigest(),
                 biber_command=args.biber, suite=args.suite,
                 allow_known_baselines=args.allow_known_baselines,
                 expected_cases=len(jobs), results=results), ensure_ascii=False, indent=2))
    print('Counts:', {status: sum(r['status'] == status for r in results)
                      for status in ('PASS', 'LIMITATION', 'FAIL', 'BLOCKED_BASELINE', 'KNOWN_BASELINE_FAILURE')}, flush=True)
    raise SystemExit(any(r['status'] in ('FAIL', 'BLOCKED_BASELINE') for r in results))


if __name__ == '__main__':
    main()
