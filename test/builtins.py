"""Check built-in Latin translations, irregular plurals, ranges and local switches.

Unicode-script translations and default auto profiles are exercised by ctan.py.
No language profile is registered by this fixture.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.Lock()
# Figure, table and lemma plurals, range separator, and number conjunction.
WORDS = {
    'french': ('Figures', 'Tables', 'Lemmes', 'à', 'et'),
    'german': ('Abbildungen', 'Tabellen', 'Lemmata', 'bis', 'und'),
    'spanish': ('Figuras', 'Cuadros', 'Lemas', 'a', 'y'),
    'portuguese': ('Figuras', 'Tabelas', 'Lemas', 'a', 'e'),
    'italian': ('Figure', 'Tabelle', 'Lemmi', '–', 'e'),
    'dutch': ('Figuren', 'Tabellen', 'Lemma’s', 't/m', 'en'),
}
ALIASES = {
    'en': 'english', 'zh': 'chinese', 'fr': 'french', 'de': 'german',
    'es': 'spanish', 'pt': 'portuguese', 'it': 'italian', 'nl': 'dutch',
    'ru': 'russian', 'el': 'greek', 'ja': 'japanese', 'ar': 'arabic',
    'UKenglish': 'english', 'USenglish': 'english', 'newzealand': 'english',
    'schinese': 'chinese', 'simplified-chinese': 'chinese', 'zh-cn': 'chinese',
    'zh-hans': 'chinese', 'francais': 'french', 'acadian': 'french',
    'canadien': 'french', 'ngerman': 'german', 'austrian': 'german',
    'naustrian': 'german', 'swissgerman': 'german', 'nswissgerman': 'german',
    'portuges': 'portuguese', 'brazil': 'portuguese', 'brazilian': 'portuguese',
}


def fixture(manager, local_languages):
    preamble = r'\documentclass{article}' + '\n'
    if manager == 'babel':
        preamble += r'\usepackage[T1]{fontenc}\usepackage{lmodern}' + '\n'
        preamble += r'\usepackage{babel}\babelprovide[import,main]{english}' + '\n'
        preamble += '\n'.join(r'\babelprovide[import]{' + lang + '}' for lang in WORDS)
    else:
        preamble += r'\usepackage{polyglossia}\setdefaultlanguage{english}' + '\n'
        preamble += r'\setotherlanguages{' + ','.join(local_languages) + '}'
        preamble += r'\setmainfont{Latin Modern Roman}'
    preamble += r'''
\usepackage{hyperref,wiseref}
\newcounter{probe}
\newcommand\BuiltCase[2]{\par\noindent B-#1-BEGIN #2 B-#1-END\par}
\begin{document}
\ExplSyntaxOn
\clist_map_inline:nn{figure,table,equation,lemma}
  {\setcounter{probe}{0}
   \int_step_inline:nn{3}
     {\group_begin:\wisereftype{#1}\refstepcounter{probe}\label{#1-##1}\group_end:}}
\ExplSyntaxOff
'''
    lines = [preamble]
    for lang in WORDS:
        lines += [r'{\wiserefsetup{lang=' + lang + '}',
                  r'\BuiltCase{' + lang + r'-figure}{\wref{figure-1,figure-2}}',
                  r'\BuiltCase{' + lang + r'-table}{\wref{table-1,table-2}}',
                  r'\BuiltCase{' + lang + r'-lemma}{\wref{lemma-1,lemma-2}}',
                  r'\BuiltCase{' + lang + r'-equation}{\wref[]{equation-1}[]}',
                  r'\wiserefsetup{compress=true}',
                  r'\BuiltCase{' + lang + r'-range}{\wref{figure-1,figure-2,figure-3}}}']
        if lang in local_languages:
            lines += [r'{\selectlanguage{' + lang + '}',
                  r'\BuiltCase{' + lang + r'-auto}{\wref{figure-1,figure-2}}',
                  r'\wiserefsetup{equation={prefix={Custom~},number-format={[#1]}},number-last-separator={+}}',
                  r'\BuiltCase{' + lang + r'-override}{\wref{equation-1,equation-2}}',
                  r'\selectlanguage{english}',
                  r'\BuiltCase{' + lang + r'-switch}{\wref{equation-1,equation-2}}}']
    lines += [r'\BuiltCase{after-group}{\wref{figure-1,figure-2}}', r'\ExplSyntaxOn']
    for alias, lang in ALIASES.items():
        lines += [r'\group_begin:\wiserefsetup{lang=' + alias + '}',
                  r'\seq_clear:N\l__wise_keys_seq\__wise_resolve_options:',
                  r'\iow_term:e{BUILT-ALIAS: ' + alias + r'=\l__wise_selected_lang_tl}',
                  r'\group_end:']
    lines += [r'\ExplSyntaxOff\end{document}']
    return '\n'.join(lines) + '\n'


def run(work, engine, manager):
    folder = work / f'{engine}-{manager}'
    folder.mkdir()
    shutil.copy2(work / 'candidate.sty', folder / 'wiseref.sty')
    local_languages = list(WORDS)
    # The Lua polyglossia Portuguese module requires an optional TeX package.
    # Keep its explicit profile tests even when the manager cannot load it.
    if engine == 'lualatex' and manager == 'polyglossia':
        available = subprocess.run(['kpsewhich', 'luavlna.sty'], capture_output=True, text=True)
        if not available.stdout.strip():
            local_languages.remove('portuguese')
    (folder / 'main.tex').write_text(fixture(manager, local_languages))
    env = os.environ.copy()
    env.update(TEXINPUTS='.:', TEXMFHOME=str(work / 'empty-texmf'))
    with (folder / 'compile.log').open('w') as stream:
        for _ in range(3):
            subprocess.run([engine, '-no-shell-escape', '-interaction=nonstopmode',
                            '-halt-on-error', '-recorder', 'main.tex'], cwd=folder,
                           env=env, stdout=stream, stderr=subprocess.STDOUT,
                           check=True, timeout=120)
    with LOCK, pdfium.PdfDocument(folder / 'main.pdf') as pdf:
        text = ''
        for page in pdf:
            tp = page.get_textpage()
            text += tp.get_text_range()
            tp.close()
            page.close()
    expected = {'after-group': 'Figures 1 and 2'}
    for lang, (figs, tabs, lemmas, span, join) in WORDS.items():
        expected.update({
            lang + '-figure': f'{figs} 1 {join} 2',
            lang + '-table': f'{tabs} 1 {join} 2',
            lang + '-lemma': f'{lemmas} 1 {join} 2',
            lang + '-equation': '(1)',
            lang + '-range': f'{figs} 1' + (span if span == '–' else f' {span} ') + '3',
        })
        if lang in local_languages:
            native = 'Fig.' if manager == 'polyglossia' and lang == 'french' else figs
            expected.update({
                lang + '-auto': f'{native} 1 {join} 2',
                lang + '-override': 'Custom [1]+[2]',
                lang + '-switch': 'Custom [1]+[2]',
            })
    actual = {}
    for key, wanted in expected.items():
        match = re.search('B-' + key + '-BEGIN(.*?)B-' + key + '-END', text, re.S)
        assert match, ('missing marker', key)
        actual[key] = re.sub(r'\s+', ' ', match[1]).strip()
        assert actual[key] == wanted, (key, wanted, actual[key])
    log = (folder / 'main.log').read_text(errors='replace')
    aliases = dict(re.findall(r'BUILT-ALIAS:\s*(\S+)=(\S+)', log))
    assert aliases == ALIASES, aliases
    assert not re.search(r'Missing character:|No profile for document language|Rerun to get wiseref|undefined references', log)
    return dict(case=folder.name, status='PASS', assertions=len(expected),
                aliases=len(aliases), output=actual,
                local_languages=local_languages,
                skipped_local_languages=sorted(set(WORDS) - set(local_languages)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    (args.work / 'empty-texmf').mkdir()
    shutil.copy2(ROOT / 'wiseref.sty', args.work / 'candidate.sty')
    cases = [(engine, 'babel') for engine in ('lualatex', 'xelatex', 'pdflatex')]
    cases += [(engine, 'polyglossia') for engine in ('lualatex', 'xelatex')]
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(run, args.work, e, m): f'{e}-{m}' for e, m in cases}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as error:
                result = dict(case=futures[future], status='FAIL', error=str(error))
            print(result['case'], result['status'], result.get('error', ''), flush=True)
            results.append(result)
            (args.work / 'results.json').write_text(json.dumps(results, indent=2))
    raise SystemExit(any(r['status'] != 'PASS' for r in results))


if __name__ == '__main__':
    main()
