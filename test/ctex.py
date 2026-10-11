"""Check ctex auto language, plain schemes, loading order and user precedence.

Each case compares ordinary output with and without wiseref, then exercises
actual references. Unicode engines use Fandol; pdfLaTeX uses fontset=none with
the distributed Arphic Type 1 CJK fonts. No hithesis code is loaded.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('reference_tests', ROOT / 'test/run.py')
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
ENGINES = ('lualatex', 'xelatex', 'pdflatex')

CHECKS = r'''
\ExplSyntaxOn
\cs_new_eq:NN\WiseOriginalResolve\__wise_resolve_options:
\cs_set_protected:Npn\__wise_resolve_options:
  {\WiseOriginalResolve\iow_term:e{CTEX-LANG:\WiseCaseName=\l__wise_selected_lang_tl}}
\ExplSyntaxOff
\newcommand\WiseCase[2]{\par\begingroup\def\WiseCaseName{#1}%
  \noindent C-#1-BEGIN #2 C-#1-END\endgroup\par}
'''


def cases():
    result = []
    for cls in ('ctexart', 'ctexbook', 'ctexrep'):
        for scheme in ('chinese', 'plain'):
            result.append(dict(name=cls + '-' + scheme, cls=cls, scheme=scheme))
    for order in ('before', 'after', 'heading'):
        for scheme in ('chinese', 'plain'):
            result.append(dict(name='package-' + order + '-' + scheme,
                               cls='article', scheme=scheme, package=order))
    for manager in ('babel', 'polyglossia'):
        result.append(dict(name='ctexart-' + manager, cls='ctexart',
                           scheme='chinese', manager=manager))
    result.append(dict(name='ctexbook-preclass', cls='ctexbook',
                       scheme='chinese', preclass=True))
    return result


def driver(case, engine, mode):
    fontset = 'none' if engine == 'pdflatex' else 'fandol'
    options = 'fontset=' + fontset
    if case['scheme'] == 'plain':
        options += ',scheme=plain'
    loaded = mode != 'baseline'
    lines = []
    if case.get('preclass') and loaded:
        lines.append(r'\RequirePackage{wiseref}')
    if case.get('package'):
        lines.append(r'\documentclass{article}')
        if case['package'] == 'after' and loaded:
            lines.append(r'\usepackage{wiseref}')
        if case['package'] == 'heading':
            options += ',heading=true'
        lines.append(r'\usepackage[' + options + ']{ctex}')
    else:
        lines.append(r'\documentclass[' + options + ',oneside]{' + case['cls'] + '}')
    if engine == 'pdflatex':
        lines += [r'\renewcommand\CJKrmdefault{gbsn}', r'\renewcommand\CJKsfdefault{gbsn}',
                  r'\renewcommand\CJKttdefault{gbsn}', r'\pdfmapfile{+gbsnu.map}']
    if case.get('manager') == 'babel':
        lines += [r'\usepackage{babel}', r'\babelprovide[import,main]{english}',
                  r'\babelprovide[import]{french}']
    elif case.get('manager') == 'polyglossia':
        lines += [r'\usepackage{polyglossia}', r'\setdefaultlanguage{english}',
                  r'\setotherlanguage{french}', r'\setmainfont{Latin Modern Roman}']
    lines += [r'\usepackage{amsmath,amsthm,hyperref}',
              r'\newtheorem{theorem}{Theorem}[section]',
              r'\newtheorem{lemma}[theorem]{Lemma}']
    if loaded and not case.get('preclass') and case.get('package') != 'after':
        lines.append(r'\usepackage{wiseref}')
    if case['cls'] in ('ctexbook', 'ctexrep'):
        lines.append(r'\def\WiseChapter{1}')
    if case.get('manager'):
        lines.append(r'\def\WiseManager{1}')
    if mode == 'references':
        lines += [r'\def\WiseChecks{1}', CHECKS]
    lines.append(r'\input{cases.tex}')
    return '\n'.join(lines) + '\n'


def compile_case(folder, case, engine, mode, work):
    folder.mkdir(parents=True)
    shutil.copy2(work / 'candidate.sty', folder / 'wiseref.sty')
    shutil.copy2(ROOT / 'test/ctex.tex', folder / 'cases.tex')
    (folder / 'main.tex').write_text(driver(case, engine, mode))
    env = os.environ.copy()
    env.update(TEXINPUTS='.:', TEXMFHOME=str(work / 'empty-texmf'))
    with (folder / 'compile.log').open('w') as stream:
        for _ in range(3):
            subprocess.run([engine, '-no-shell-escape', '-interaction=nonstopmode',
                            '-halt-on-error', '-recorder', 'main.tex'], cwd=folder,
                           env=env, stdout=stream, stderr=subprocess.STDOUT,
                           check=True, timeout=120)
    log = (folder / 'main.log').read_text(errors='replace')
    assert not re.search(r'Missing character:|undefined references|Label\(s\) may have changed', log)
    return log


def expected(case):
    chapter = case['cls'] in ('ctexbook', 'ctexrep')
    chinese = case['scheme'] == 'chinese' and not case.get('manager')
    n = '1.1' if chapter else '1'
    second = '1.2' if chapter else '2'
    third = '1.3' if chapter else '3'
    thm = '1.1.1' if chapter else '1.1'
    lem = '1.1.2' if chapter else '1.2'
    section = '1.1' if chapter else '1'
    pair = f'图{n}、{second}' if chinese else f'Figures {n} and {second}'
    eq = '式' if chinese else 'Equation '
    out = {
        'pair': pair, 'restored': pair, 'after-override': pair,
        'name-off': pair,
        'name-on': f'照片{n}、{second}' if chinese else f'照片 {n} and {second}',
        'heading-name': f'第{section}段' if chinese else f'段 {section}',
        'heading-name-off': f'第{section}节' if chinese else f'Section {section}',
        'mixed': f'图{n}，表{n}和式({n})' if chinese else f'Figure {n}, Table {n} and Equation ({n})',
        'range': f'图{n}至{third}' if chinese else f'Figures {n}–{third}',
        'equation': eq + f'({n})', 'tagged': eq + '(S)', 'bare': eq + 'S',
        'section': f'第{section}节' if chinese else f'Section {section}',
        'theorem': f'定理{thm}' if chinese else f'Theorem {thm}',
        'lemma': f'引理{lem}' if chinese else f'Lemma {lem}',
        'appendix': '附录A' if chinese else 'Appendix A',
        'renamed': f'照片{n}、{second}' if chinese else f'照片 {n} and {second}',
        'explicit-en': f'Figures {n} and {second}',
        'explicit-zh': f'图{n}、{second}',
        'override-auto': f'Custom {n}+' + eq + f'[{n}]',
        'override-en': f'Custom {n}+Equation [{n}]',
        'override-back': f'Custom {n}+' + eq + f'[{n}]',
    }
    if chapter:
        number = '一' if case['scheme'] == 'chinese' else '1'
        out['chapter'] = '第' + number + '章' if chinese else 'Chapter ' + number
    if case.get('manager'):
        out.update({'local-french': f'Figures {n} et {second}' if case['manager'] == 'babel'
                    else f'Fig. {n} et {second}', 'after-french': pair})
    profiles = {key: 'chinese' if chinese else 'english' for key in out}
    profiles.update({'explicit-en': 'english', 'explicit-zh': 'chinese', 'override-en': 'english'})
    if case.get('manager'):
        profiles['local-french'] = 'french'
    return out, profiles


def run(work, case, engine):
    root = work / (case['name'] + '-' + engine)
    phase = 'baseline'
    try:
        compile_case(root / phase, case, engine, phase, work)
        phase = 'observed'
        compile_case(root / phase, case, engine, phase, work)
        labels = base.records(root / 'baseline/main.aux', 'newlabel', 2)
        assert labels == base.records(root / 'observed/main.aux', 'newlabel', 2)
        assert base.pdf_signature(root / 'baseline/main.pdf') == base.pdf_signature(root / 'observed/main.pdf')
        assert base.link_signature(root / 'baseline/main.pdf') == base.link_signature(root / 'observed/main.pdf')
        phase = 'references'
        log = compile_case(root / phase, case, engine, phase, work)
        assert 'No profile for document language' not in log
        actual = {}
        text = ''.join(page[0] for page in base.pdf_signature(root / phase / 'main.pdf'))
        wanted, profiles = expected(case)
        for key, value in wanted.items():
            match = re.search('C-' + key + '-BEGIN(.*?)C-' + key + '-END', text, re.S)
            assert match, ('missing output', key)
            actual[key] = re.sub(r'\s+', '', match[1])
            assert actual[key] == re.sub(r'\s+', '', value), (key, value, actual[key])
        assert dict(re.findall(r'CTEX-LANG:(\S+)=(\S+)', log)) == profiles
        assert labels == base.records(root / phase / 'main.aux', 'newlabel', 2)
        wise = base.records(root / phase / 'main.aux', 'wiserefRecord', 3)
        for key, kind, tag in (('a', 'figure', 'normal'), ('t', 'table', 'normal'),
                               ('e', 'equation', 'normal'), ('tagged', 'equation', 'tag'),
                               ('bare', 'equation', 'bare'), ('thm', 'theorem', 'normal'),
                               ('lem', 'lemma', 'normal'), ('app', 'appendix', 'normal'),
                               ('unnumbered', '', 'normal')):
            assert wise[key] == [kind, tag], (key, wise[key])
        links, _ = base.link_signature(root / phase / 'main.pdf')
        assert links
        inputs = (root / phase / 'main.fls').read_text()
        assert 'hithesis.cls' not in inputs and 'docxlike.sty' not in inputs
        if not case.get('manager'):
            assert 'babel.sty' not in inputs and 'polyglossia.sty' not in inputs
        return dict(case=root.name, status='PASS', assertions=len(wanted),
                    output=actual, profiles=profiles, links=len(links))
    except Exception as error:
        path = root / phase / 'compile.log'
        return dict(case=root.name, status='FAIL', phase=phase, error=str(error), log=str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--engines', nargs='+', choices=ENGINES, default=ENGINES)
    parser.add_argument('--cases', nargs='+')
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    (args.work / 'empty-texmf').mkdir()
    shutil.copy2(ROOT / 'wiseref.sty', args.work / 'candidate.sty')
    jobs = [(case, engine) for case in cases() for engine in args.engines
            if (not args.cases or case['name'] in args.cases)
            and not (engine == 'pdflatex' and case.get('manager') == 'polyglossia')]
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run, args.work, case, engine) for case, engine in jobs]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(result['case'], result['status'], result.get('error', ''), flush=True)
            (args.work / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    raise SystemExit(any(r['status'] != 'PASS' for r in results))


if __name__ == '__main__':
    main()
