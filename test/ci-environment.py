"""Record the CI toolchain and verify the requested TeX Live year.

Copyright (C) 2026 Junhao Wu. LPPL 1.3c or later; see LICENSE.
"""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def verify_year(versions, expected):
    years = set()
    for value in versions:
        match = re.search(r'TeX Live (\d{4})', value)
        if not match:
            raise ValueError(f'Missing TeX Live year in engine banner: {value}')
        years.add(match.group(1))
    if len(years) != 1 or (expected != 'latest' and years != {expected}):
        raise ValueError(f'TeX Live year mismatch: requested {expected}, found {sorted(years)}')
    return years.pop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-year', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    engines = {name: subprocess.check_output([name, '--version'], text=True).splitlines()[0]
               for name in ('lualatex', 'xelatex', 'pdflatex', 'xetex')}
    year = verify_year(engines.values(), args.expected_year)
    probe = args.output.parent / 'ci-toolchain-probe'
    probe.mkdir(parents=True, exist_ok=True)
    (probe / 'probe.tex').write_text(r'''\documentclass{article}
\begin{document}
\typeout{CI-KERNEL:\fmtversion}
\typeout{CI-PROPERTY-API:\ifdefined\RecordProperties true\else false\fi}
Toolchain probe.
\end{document}
''', encoding='utf-8')
    with (probe / 'compile.log').open('w', encoding='utf-8') as stream:
        subprocess.run(['pdflatex', '-no-shell-escape', '-interaction=nonstopmode',
                        '-halt-on-error', 'probe.tex'], cwd=probe, stdout=stream,
                       stderr=subprocess.STDOUT, check=True, timeout=60)
    log = (probe / 'probe.log').read_text(errors='replace')
    kernel = re.search(r'CI-KERNEL:(\S+)', log).group(1)
    expl3 = re.search(r'L3 programming layer <([^>]+)>', log).group(1)
    property_api = 'CI-PROPERTY-API:true' in log
    tools = {}
    for name in ('latexmk', 'biber', 'latexminted'):
        executable = shutil.which(name)
        if executable:
            result = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=30)
            tools[name] = {'path': executable, 'exit_code': result.returncode,
                           'version': (result.stdout + result.stderr).strip()}
        else:
            tools[name] = {'path': None}
    record = dict(texlive_year=year, requested_year=args.expected_year,
                  latex_kernel=kernel, expl3_date=expl3, record_properties=property_api,
                  image=os.environ.get('CI_TEXLIVE_IMAGE'), revision=os.environ.get('GITHUB_SHA'),
                  platform=platform.platform(), python=platform.python_version(), engines=engines,
                  tools=tools, libraries={name: metadata.version(name)
                                         for name in ('pypdf', 'pypdfium2', 'PyYAML')},
                  source_sha256=hashlib.sha256((ROOT / 'wiseref.dtx').read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(f'TeX Live {year}: toolchain recorded in {args.output}')


if __name__ == '__main__':
    main()
