"""Compile the shipped examples against an isolated TDS installation.

Copyright (C) 2026 Junhao Wu. LPPL 1.3c or later; see LICENSE.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import zipfile

import pypdfium2 as pdfium
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('reference_tests', ROOT / 'test/run.py')
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
EXPECTED = {
    'single': ('Figure 1', '图1'),
    'mixed': ('Figure 1, Table 1 and Equation (1)', '图1，表1和式(1)'),
    'range': ('Figures 1–3', '图1至3'),
    'document-name': ('Photo 1', '照片1'),
    'profile-name': ('Figure 1', '图1'),
    'suffix-name': ('1 Photo', '1照片'),
    'number-only': ('1', '1'),
    'star': ('Photo 1', '照片1'),
}


def check_pdf(path, language):
    reader = PdfReader(path)
    destinations = reader.named_destinations
    annotations = {}
    for index, page in enumerate(reader.pages):
        annotations[index] = []
        for entry in page.get('/Annots', []):
            obj = entry.get_object()
            action = obj.get('/A', {})
            if action.get('/S') == '/GoTo':
                assert action['/D'] in destinations, ('missing target', action['/D'])
                annotations[index].append(tuple(float(value) for value in obj['/Rect']))
    outputs = {}
    with pdfium.PdfDocument(path) as pdf:
        for name, values in EXPECTED.items():
            destination = destinations['example.' + name]
            page_number = reader.get_destination_page_number(destination)
            page = pdf[page_number]
            textpage = page.get_textpage()
            left, top = float(destination.left), float(destination.top)
            chars = []
            for index in range(textpage.count_chars()):
                box = textpage.get_charbox(index)
                x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                if x >= left - 1 and top - 3 < y < top + 10:
                    chars.append((textpage.get_text_range(index, 1), box))
            text = ''.join(character for character, _ in chars)
            wanted = values[0 if language == 'en' else 1]
            normalize = lambda value: re.sub(r'\s+', '', value)
            assert normalize(text) == normalize(wanted), (name, wanted, text)
            outputs[name] = text.strip()
            if name == 'star':
                assert not any(rect[0] < (box[0] + box[2]) / 2 < rect[2]
                               and rect[1] < (box[1] + box[3]) / 2 < rect[3]
                               for character, box in chars if character.strip()
                               for rect in annotations[page_number]), 'Starred example has links'
            textpage.close()
            page.close()
    return outputs


def run_case(work, texmf, language, engine):
    folder = work / f'{engine}-{language}'
    folder.mkdir()
    source = texmf / 'doc/latex/wiseref' / f'wiseref-example-{language}.tex'
    shutil.copy2(source, folder / 'main.tex')
    env = os.environ.copy()
    env.update(TEXMFHOME=str(texmf), TEXINPUTS='.:')
    installed = texmf / 'tex/latex/wiseref/wiseref.sty'
    found = subprocess.check_output(['kpsewhich', 'wiseref.sty'], cwd=folder, env=env, text=True).strip()
    assert Path(found).resolve() == installed, ('Wrong runtime file', found, installed)
    with (folder / 'compile.log').open('w') as stream:
        for _ in range(3):
            subprocess.run([engine, '-no-shell-escape', '-recorder', '-interaction=nonstopmode',
                            '-halt-on-error', 'main.tex'], cwd=folder, env=env,
                           stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=120)
    log = (folder / 'main.log').read_text(errors='replace')
    assert not re.search(r'Missing character:|undefined references|Label\(s\) may have changed|^warning\b', log, re.M)
    inputs = (folder / 'main.fls').read_text()
    assert str(installed) in inputs, 'Installed runtime absent from the recorder file'
    outputs = check_pdf(folder / 'main.pdf', language)
    return dict(case=folder.name, status='PASS', runtime_file=str(installed),
                assertions=len(outputs), output=outputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tds', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    args.work = args.work.resolve()
    args.work.mkdir(parents=True, exist_ok=False)
    texmf = args.work / 'texmf'
    with zipfile.ZipFile(args.tds) as archive:
        for name in archive.namelist():
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError(f'Unsafe TDS path: {name}')
        runtime = [name for name in archive.namelist() if name.startswith('tex/') and not name.endswith('/')]
        assert runtime == ['tex/latex/wiseref/wiseref.sty'], runtime
        archive.extractall(texmf)
    jobs = [('en', engine) for engine in ('lualatex', 'xelatex', 'pdflatex')]
    jobs += [('zh', engine) for engine in ('lualatex', 'xelatex')]
    results = []
    for language, engine in jobs:
        try:
            result = run_case(args.work, texmf, language, engine)
        except Exception as error:
            result = dict(case=f'{engine}-{language}', status='FAIL', error=str(error))
        results.append(result)
        print(result['case'], result['status'], result.get('error', ''), flush=True)
        (args.work / 'results.json').write_text(json.dumps(dict(
            expected_cases=len(jobs), tds_sha256=hashlib.sha256(args.tds.read_bytes()).hexdigest(),
            results=results), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    raise SystemExit(any(result['status'] != 'PASS' for result in results))


if __name__ == '__main__':
    main()
