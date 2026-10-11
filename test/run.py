"""Probe portable label metadata; build isolated standard-class documents.

This is a test of the substrate for wiseref, not an implementation of wref.
Every fixture is compiled both with and without the observation hook.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading

import pypdfium2 as pdfium
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ENGINES = ('lualatex', 'xelatex', 'pdflatex')
CLASSES = ('article', 'book', 'report')
# PDFium is not thread-safe. TeX jobs may run concurrently; PDF inspection may not.
PDFIUM_LOCK = threading.Lock()


def arguments(text, start, count):
    """Read balanced TeX groups from our own non-executing auxiliary record."""
    groups = []
    pos = start
    for _ in range(count):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text) or text[pos] != '{':
            raise ValueError(f'Missing argument at {text[pos:pos+80]!r}')
        depth, begin = 1, pos + 1
        pos += 1
        while depth:
            if pos >= len(text):
                raise ValueError('Unterminated auxiliary record')
            if text[pos] == '\\':
                # Escaped braces do not change grouping depth.
                if pos + 1 < len(text) and text[pos+1] in '{}':
                    pos += 2
                    continue
            if text[pos] == '{':
                depth += 1
            elif text[pos] == '}':
                depth -= 1
            pos += 1
        groups.append(text[begin:pos-1])
    return groups


def records(path, command, count):
    text = path.read_text(errors='replace')
    found = {}
    for match in re.finditer(r'(?m)^\\' + re.escape(command) + r'(?=\s*\{)', text):
        values = arguments(text, match.end(), count)
        if values[0] in found:
            raise AssertionError(f'Duplicate record: {values[0]}')
        found[values[0]] = values[1:]
    return found


def expectations(cls):
    chapter = cls != 'article'
    eq = '1.' if chapter else ''
    section = '1.1' if chapter else '1'
    figure = '1.1' if chapter else '1'
    panels = '1.2' if chapter else '2'
    expected = {
        'main-section': ('section', section),
        'alpha': ('figure', figure),
        'eq:not-equation': ('table', figure),
        'fig:not-figure': ('equation', eq+'1'),
        'row-one': ('equation', eq+'2'),
        'row-two': ('equation', eq+'3'),
        'family': ('equation', eq+'4'),
        'family-one': ('equation', eq+'4a'),
        'family-two': ('equation', eq+'4b'),
        'tag-with-parentheses': ('equation', '{S}'),
        'tag-without-parentheses': ('equation', 'S'),
        'statement': ('theorem', section+'.1'),
        'shared-counter': ('lemma', section+'.2'),
        'nested-label': ('lemma', section+'.2'),
        'outer-item': ('enumi', '1'),
        'inner-item': ('enumii', '1a'),
        'note': ('footnote', '1'),
        'panel-one': ('subfigure', panels+'a'),
        'panel-two': ('subfigure', panels+'b'),
        'panels': ('figure', panels),
        'moving-title': ('section', '1.2' if chapter else '2'),
        'supplement': ('appendix', 'A'),
        'appendix-equation': ('equation', 'A.1' if chapter else '5'),
    }
    if chapter:
        expected['main-chapter'] = ('chapter', '1')
    return expected


def pdf_signature(path):
    """Observe text and character positions without relying on PDF object IDs."""
    pages = []
    with PDFIUM_LOCK, pdfium.PdfDocument(path) as pdf:
        for page in pdf:
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            boxes = [tuple(round(v, 4) for v in textpage.get_charbox(i))
                     for i in range(textpage.count_chars())]
            pages.append((text, boxes))
            textpage.close()
            page.close()
    return pages


def link_signature(path):
    reader = PdfReader(path)
    destinations = reader.named_destinations
    links = []
    for index, page in enumerate(reader.pages):
        for entry in page.get('/Annots', []):
            annotation = entry.get_object()
            if annotation.get('/Subtype') != '/Link':
                continue
            action = annotation.get('/A', {})
            if action.get('/S') != '/GoTo':
                continue
            destination = action['/D']
            assert isinstance(destination, str), destination
            assert destination in destinations, destination
            links.append((index, tuple(float(x) for x in annotation['/Rect']), destination,
                          reader.get_destination_page_number(destinations[destination])))
    return links, set(destinations)


def assert_case_links(path, annotations, expected):
    """Locate acceptance outputs and verify local link suppression/restoration."""
    seen = set()
    with PDFIUM_LOCK, pdfium.PdfDocument(path) as pdf:
        for page_index, page in enumerate(pdf):
            textpage = page.get_textpage()
            for key in expected:
                start_search = textpage.search(f'CASE-{key}-BEGIN')
                start = start_search.get_next()
                start_search.close()
                if start is None:
                    continue
                end_search = textpage.search(f'CASE-{key}-END')
                end = end_search.get_next()
                end_search.close()
                assert end is not None and end[0] > start[0], ('split acceptance case', key)
                boxes = [textpage.get_charbox(i) for i in range(start[0]+start[1], end[0])
                         if textpage.get_text_range(i, 1).strip()]
                linked = any(
                    p == page_index and any(
                        rect[0] < (box[0]+box[2])/2 < rect[2]
                        and rect[1] < (box[1]+box[3])/2 < rect[3] for box in boxes)
                    for p, rect, _, _ in annotations)
                assert linked == (key not in ('star', 'link-off', 'links-off', 'links-star')), ('wrong link state', key)
                seen.add(key)
            textpage.close()
            page.close()
    assert seen == set(expected), ('missing linked cases', set(expected)-seen)


def assert_link_modes(path, annotations, labels):
    """Verify the actual clickable words and first/last destinations in each mode."""
    targets = {key: arguments(labels[key][0], 0, 4)[3] for key in ('alpha', 'beta')}
    modes = {'links-all': 'all', 'links-num': 'numbers', 'links-off': 'none',
             'links-star': 'none', 'links-reset': 'all'}
    seen = set()
    with PDFIUM_LOCK, pdfium.PdfDocument(path) as pdf:
        for page_index, page in enumerate(pdf):
            tp = page.get_textpage()
            for key, mode in modes.items():
                search = tp.search(f'CASE-{key}-BEGIN')
                start = search.get_next()
                search.close()
                if start is None:
                    continue
                search = tp.search(f'CASE-{key}-END')
                end = search.get_next()
                search.close()
                assert end is not None and end[0] > start[0], key
                first = start[0] + start[1]
                text = tp.get_text_range(first, end[0] - first)
                for word, target in (('Head', 'alpha'), ('1', 'alpha'),
                                     ('and', None), ('2', 'beta'), ('Tail', 'beta')):
                    offset = text.index(word)
                    boxes = [tp.get_charbox(first + offset + i) for i in range(len(word))]
                    actual = {destination for p, rect, destination, _ in annotations
                              if p == page_index and all(
                                  rect[0] < (box[0] + box[2]) / 2 < rect[2]
                                  and rect[1] < (box[1] + box[3]) / 2 < rect[3]
                                  for box in boxes)}
                    clickable = mode != 'none' and target is not None and (
                        mode == 'all' or word in ('1', '2'))
                    wanted = {targets[target]} if clickable else set()
                    assert actual == wanted, ('link scope/destination', key, word, wanted, actual)
                seen.add(key)
            tp.close()
            page.close()
    assert seen == set(modes), ('missing link modes', seen)


def driver(cls, links, observe, theorems, candidate=False):
    return '\n'.join([
        r'\documentclass{' + cls + '}',
        r'\usepackage{amsmath}',
        r'\usepackage{amsthm}' if theorems == 'amsthm' else '',
        r'\usepackage{subcaption}',
        r'\newtheorem{theorem}{Theorem}[section]',
        r'\newtheorem{lemma}[theorem]{Lemma}',
        r'\newenvironment{probe-wrapper}{}{}',
        r'\usepackage{hyperref}' if links else '',
        r'\usepackage{wiseref}' if candidate and observe else '',
        r'\usepackage{wiseref-probe}' if observe else '',
        r'\input{cases.tex}', '',
    ])


def compile_document(folder, engine, source, env, fixture='cases.tex', candidate=None):
    folder.mkdir()
    (folder/'main.tex').write_text(source)
    shutil.copy2(HERE/fixture, folder/'cases.tex')
    shutil.copy2(HERE/'wiseref-probe.sty', folder/'wiseref-probe.sty')
    if candidate is not None:
        shutil.copy2(candidate, folder/'wiseref.sty')
    with (folder/'compile.log').open('w') as output:
        for _ in range(3):
            subprocess.run([engine, '-no-shell-escape', '-recorder',
                            '-interaction=nonstopmode', '-halt-on-error', 'main.tex'],
                           cwd=folder, env=env, stdout=output,
                           stderr=subprocess.STDOUT, timeout=120, check=True)
    log = (folder/'main.log').read_text(errors='replace')
    assert not re.search(r'undefined references|multiply defined|Label\(s\) may have changed', log), folder
    inputs = [line[6:] for line in (folder/'main.fls').read_text().splitlines()
              if line.startswith('INPUT ')]
    forbidden_names = {'cleveref.sty', 'smartref.sty'}
    if candidate is None:
        forbidden_names.add('wiseref.sty')
    forbidden = [p for p in inputs if Path(p).name.startswith(('hithesis', 'docxlike'))
                 or Path(p).name in forbidden_names]
    assert not forbidden, forbidden
    return log


def check_case(work, engine, cls, links, theorems, candidate=None):
    name = f'{engine}-{cls}-{theorems}-' + ('links' if links else 'plain')
    folder = work/name
    folder.mkdir()
    env = os.environ.copy()
    env.update(SOURCE_DATE_EPOCH='1791417600', FORCE_SOURCE_DATE='1',
               TEXINPUTS='.:', TEXMFHOME=str(work/'empty-texmf'))
    result = dict(case=name, engine=engine, document_class=cls, hyperref=links, theorems=theorems)
    failed_log = folder/'baseline/compile.log'
    try:
        for mode in ('baseline', 'observed'):
            failed_log = folder/mode/'compile.log'
            compile_document(folder/mode, engine, driver(cls, links, mode == 'observed', theorems, candidate is not None), env,
                             candidate=candidate if mode == 'observed' else None)
        baseline = records(folder/'baseline/main.aux', 'newlabel', 2)
        actual = records(folder/'observed/main.aux', 'newlabel', 2)
        assert baseline == actual, 'Observation changed standard label records'
        captured = records(folder/'observed/main.aux', 'WiseProbeRecord', 6)
        expected = expectations(cls)
        if candidate is not None:
            typed = records(folder/'observed/main.aux', 'wiserefRecord', 3)
            for key, (kind, _) in expected.items():
                assert typed[key][0] == kind, (key, 'wrong reference type', typed[key], kind)
            assert typed['tag-with-parentheses'][1] == 'tag'
            assert typed['tag-without-parentheses'][1] == 'bare'
            assert typed['unnumbered'][0] == '', ('stale unnumbered target', typed['unnumbered'])
        issues = []
        for key, (kind, number) in expected.items():
            assert key in actual and key in captured, ('missing label', key)
            standard = arguments(actual[key][0], 0, 2)
            counter, value, environment, anchor, page = captured[key]
            assert standard[0] == value == number, (key, standard[0], value, number)
            assert standard[1] == page, (key, standard[1], page)
            if links:
                assert anchor, ('missing link target', key)
            if counter != kind:
                issues.append(dict(label=key, expected_type=kind, counter=counter,
                                   environment=environment, number=value))
        before = pdf_signature(folder/'baseline/main.pdf')
        after = pdf_signature(folder/'observed/main.pdf')
        assert before == after, 'Observation changed PDF text or character positions'
        original_links, _ = link_signature(folder/'baseline/main.pdf')
        observed_links, destinations = link_signature(folder/'observed/main.pdf')
        assert original_links == observed_links, 'Observation changed PDF links'
        if links:
            assert observed_links, 'Missing PDF links'
            for key in expected:
                assert captured[key][3] in destinations, ('missing destination', key)
        else:
            assert not observed_links
        text = ''.join(page[0] for page in after)
        assert '??' not in text and 'REFERENCE-CHECK-END' in text
        result.update(status='PASS', labels=len(expected), pages=len(after),
                      links=len(observed_links), counter_only_mismatches=issues,
                      records={k: dict(counter=v[0], number=v[1], environment=v[2],
                                       anchor=v[3], page=v[4]) for k, v in captured.items()})
    except Exception as error:
        result.update(status='FAIL', error=str(error), log=str(failed_log))
    return result


def check_contract(work, candidate, engine, links):
    name = f'contract-{engine}-' + ('links' if links else 'plain')
    folder = work/name
    source = '\n'.join([
        r'\documentclass{article}', r'\usepackage{amsmath}',
        r'\usepackage{hyperref}' if links else '',
        r'\usepackage{wiseref}', r'\input{cases.tex}', '',
    ])
    env = os.environ.copy()
    env.update(TEXINPUTS='.:', TEXMFHOME=str(work/'empty-texmf'))
    compile_document(folder, engine, source, env, 'contract.tex', candidate)
    expected = json.loads((HERE/'contract.json').read_text())
    pages = pdf_signature(folder/'main.pdf')
    text = '\n'.join(page[0] for page in pages)
    for key, wanted in expected.items():
        match = re.search(r'CASE-' + re.escape(key) + r'-BEGIN\s*(.*?)\s*CASE-'
                          + re.escape(key) + '-END', text, re.S)
        assert match, ('missing output marker', name, key)
        actual = re.sub(r'\s+', ' ', match[1]).strip()
        assert actual == wanted, (name, key, wanted, actual)
    annotations, _ = link_signature(folder/'main.pdf')
    if links:
        assert annotations
        assert_case_links(folder/'main.pdf', annotations, expected)
        assert_link_modes(folder/'main.pdf', annotations, records(folder/'main.aux', 'newlabel', 2))
    else:
        assert not annotations
    return dict(case=name, status='PASS', output_assertions=len(expected))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=3)
    parser.add_argument('--candidate', type=Path, default=HERE.parent/'wiseref.sty',
                        help='Optional independent wiseref.sty to run API acceptance tests')
    args = parser.parse_args()
    args.work = args.work.resolve()
    if args.candidate is not None:
        args.candidate = args.candidate.resolve(strict=True)
    args.work.mkdir(parents=True, exist_ok=False)
    (args.work/'empty-texmf').mkdir()
    environment = {
        'engines': {engine: subprocess.check_output([engine, '--version'], text=True).splitlines()[0]
                    for engine in ENGINES},
        'fixtures': {name: hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                     for name in ('cases.tex', 'wiseref-probe.sty', 'contract.tex', 'contract.json')},
    }
    (args.work/'environment.json').write_text(json.dumps(environment, indent=2))
    results = []
    cases = [(e, c, h, t) for e in ENGINES for c in CLASSES
             for h in (False, True) for t in ('kernel', 'amsthm')]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(check_case, args.work, *case, candidate=args.candidate) for case in cases]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f'{len(results)}/{len(cases)} {result["case"]}: {result["status"]}', flush=True)
            if result['status'] == 'FAIL':
                print(result['error'], flush=True)
            (args.work/'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    passed = sum(r['status'] == 'PASS' for r in results)
    print(f'Baseline and observation checks: {passed}/{len(cases)} PASS', flush=True)
    contract_results = []
    if args.candidate is not None:
        for engine in ENGINES:
            for links in (False, True):
                try:
                    result = check_contract(args.work, args.candidate, engine, links)
                except Exception as error:
                    result = dict(case=f'contract-{engine}-{links}', status='FAIL', error=str(error))
                contract_results.append(result)
                print(f'{result["case"]}: {result["status"]}', flush=True)
        (args.work/'contract-results.json').write_text(json.dumps(contract_results, indent=2))
    else:
        print('wref API acceptance: NOT RUN (no candidate supplied)', flush=True)
    return int(passed != len(cases) or any(r['status'] != 'PASS' for r in contract_results))


if __name__ == '__main__':
    sys.exit(main())
