"""Verify actual live results and clickable words in both generated manuals."""
from pathlib import Path
import argparse
import importlib.util
import re

import pypdfium2 as pdfium
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--root', type=Path, default=ROOT, help='Directory containing manual PDFs, aux files, and logs')
a = p.parse_args()
DOCUMENTS = a.root.resolve()
SPEC = importlib.util.spec_from_file_location('reference_tests', ROOT / 'test/run.py')
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def check(language):
    path = DOCUMENTS / f'wiseref-{language}.pdf'
    reader = PdfReader(path)
    destinations = reader.named_destinations
    labels = base.records(DOCUMENTS / f'wiseref-{language}.aux', 'newlabel', 2)
    figure_targets = {key: base.arguments(labels[key][0], 0, 4)[3]
                      for key in ('picture-a', 'picture-b')}
    equation_targets = {key: base.arguments(labels[key][0], 0, 4)[3]
                        for key in ('equation', 'live-tag', 'live-bare')}
    assert len(set(equation_targets.values())) == 3, ('duplicate equation targets', equation_targets)
    positions = {(reader.get_destination_page_number(destinations[target]),
                  float(destinations[target].top)) for target in equation_targets.values()}
    assert len(positions) == 3, ('overlapping equation destinations', equation_targets)
    expected = {
        'live.quick': ('Figure 1', '图1'),
        'live.mixed': ('Figures 1 and 2, Table 1 and Equation (3)', '图1、2，表1和式(3)'),
        'live.french': ('Figures 1 et 2 et Table 1', 'Figures 1 et 2 et Table 1'),
        'live.suffix-name': ('1 Figure', '1图'),
        'live.format': ('Equation [3]', '式[3]'),
        'live.counter': ('Experiment 1', '实验1'),
        'live.links-none': ('Head 1 and 2 Tail', 'Head 1、2 Tail'),
        'live.links-numbers': ('Head 1 and 2 Tail', 'Head 1、2 Tail'),
        'live.links-affixes': ('Head 1 and 2 Tail', 'Head 1、2 Tail'),
        'live.range': ('Figures 1–3', '图1至3'),
        'live.tag': ('Equation (S)', '式(S)'),
        'live.bare': ('Equation S', '式S'),
        'row.single': ('Figure 1', '图1'),
        'row.chapter': ('Chapter 2', '第2章'),
        'row.equation': ('Equation (3)', '式(3)'),
        'row.prefix': ('Photo 1', 'Photo 1'),
        'row.suffix': ('Chapter 2.', '第2.'),
        'row.both': ('Part 2!', 'Part 2!'),
        'row.empty': ('2', '2'),
        'row.raw-equation': ('(3)', '(3)'),
        'row.star': ('Figure 1', '图1'),
    }
    annotations = {}
    for index, page in enumerate(reader.pages):
        annotations[index] = []
        for entry in page.get('/Annots', []):
            obj = entry.get_object()
            action = obj.get('/A', {})
            if hasattr(action, 'get_object'):
                action = action.get_object()
            if action.get('/S') == '/GoTo':
                target = action['/D']
                assert target in destinations, ('missing target', target)
                annotations[index].append((tuple(float(x) for x in obj['/Rect']), str(target)))
    found = {}
    with pdfium.PdfDocument(path) as pdf:
        for name, values in expected.items():
            destination = destinations[name]
            page_number = reader.get_destination_page_number(destination)
            page = pdf[page_number]
            tp = page.get_textpage()
            left, top = float(destination.left), float(destination.top)
            chars = []
            for index in range(tp.count_chars()):
                character = tp.get_text_range(index, 1)
                box = tp.get_charbox(index)
                x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                # hypertarget is placed at the result's text baseline.
                if x >= left - 1 and top - 3 < y < top + 10:
                    chars.append((character, box))
            text = ''.join(character for character, _ in chars)
            normalize = lambda value: re.sub(r'\s+', '', value)
            wanted = values[0 if language == 'en' else 1]
            assert normalize(text) == normalize(wanted), (language, name, wanted, text, left, top)
            found[name] = text.strip()
            if name in ('live.tag', 'live.bare'):
                logical = equation_targets['live-tag' if name == 'live.tag' else 'live-bare']
                for character, box in chars:
                    if not character.strip():
                        continue
                    actual = {target for rect, target in annotations[page_number]
                              if rect[0] < (box[0] + box[2]) / 2 < rect[2]
                              and rect[1] < (box[1] + box[3]) / 2 < rect[3]}
                    assert actual == {logical}, (language, name, character, actual, logical)
            if name.startswith('live.links-'):
                plain = ''.join(character for character, _ in chars)
                for word, logical in (('Head', figure_targets['picture-a']), ('1', figure_targets['picture-a']),
                                      ('and' if language == 'en' else '、', None),
                                      ('2', figure_targets['picture-b']), ('Tail', figure_targets['picture-b'])):
                    offset = plain.index(word)
                    boxes = [box for _, box in chars[offset:offset + len(word)]]
                    actual = {target for rect, target in annotations[page_number]
                              if all(rect[0] < (box[0] + box[2]) / 2 < rect[2]
                                     and rect[1] < (box[1] + box[3]) / 2 < rect[3]
                                     for box in boxes)}
                    linked = logical is not None and (name == 'live.links-affixes' or (
                        name == 'live.links-numbers' and word in ('1', '2')))
                    assert actual == ({logical} if linked else set()), (language, name, word, actual)
            if name in ('row.star', 'live.links-none'):
                assert not any(any(rect[0] < (box[0] + box[2]) / 2 < rect[2]
                                   and rect[1] < (box[1] + box[3]) / 2 < rect[3]
                                   for character, box in chars if character.strip())
                               for rect, _ in annotations[page_number]), name
            tp.close()
            page.close()
    log = (DOCUMENTS / f'wiseref-{language}.log').read_text(errors='replace')
    assert not re.search(r'^warning\b|Warning:|Overfull|Underfull|Missing character:|undefined references|Rerun to get wiseref',
                         log, re.MULTILINE)
    print(f'{path.name}: {len(found)} live outputs and link scopes PASS')


for language in ('en', 'zh'):
    check(language)
