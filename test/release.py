"""Pack a CTAN upload and rebuild its documentation from the archived sources.

Copyright (C) 2026 Junhao Wu. LPPL 1.3c or later; see LICENSE.
"""
import argparse
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import stat
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    'LICENSE', 'Makefile', 'README.md', 'build.lua', 'wiseref.dtx', 'wiseref.ins',
    'wiseref-en.tex', 'wiseref-zh.tex', 'wiseref-en.pdf', 'wiseref-zh.pdf',
    'wiseref-example-en.tex', 'wiseref-example-zh.tex',
)
TEST_SUFFIXES = {'.py', '.tex', '.json', '.md', '.txt'}


def payload(include_pdfs=True, documents=ROOT):
    files = [ROOT / name for name in ROOT_FILES if include_pdfs or not name.endswith('.pdf')]
    files.extend(sorted(path for path in (ROOT / 'test').iterdir()
                        if path.is_file() and (path.suffix in TEST_SUFFIXES
                                              or path.name == 'wiseref-probe.sty')))
    data = {}
    basenames = set()
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Not a regular source file: {relative}')
        for part in PurePosixPath(relative).parts:
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', part):
                raise ValueError(f'Invalid CTAN filename: {relative}')
        if path.name.lower() in basenames:
            raise ValueError(f'Duplicate filename ignoring case: {relative}')
        basenames.add(path.name.lower())
        content = ((documents / path.name) if path.suffix == '.pdf' else path).read_bytes()
        if not content:
            raise ValueError(f'Empty file: {relative}')
        if path.suffix != '.pdf':
            content.decode('utf-8')
            if content.startswith(b'\xef\xbb\xbf') or b'\r' in content:
                raise ValueError(f'Text must be UTF-8 without BOM and use LF: {relative}')
        elif not content.startswith(b'%PDF-'):
            raise ValueError(f'Invalid PDF header: {relative}')
        data[relative] = content
    for name, content in data.items():
        if name.endswith('.md'):
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', content.decode('utf-8')):
                if re.match(r'[a-z]+:|#', link):
                    continue
                target = (ROOT / name).parent / link.split('#', 1)[0]
                relative = target.resolve().relative_to(ROOT).as_posix()
                if relative not in data:
                    raise ValueError(f'Markdown link omitted from archive: {name} -> {link}')
    return data


def validate_tds(content, data, runtime=None):
    if runtime is None:
        runtime = (ROOT / 'wiseref.sty').read_bytes()
    expected = {'tex/latex/wiseref/wiseref.sty': runtime}
    for name, value in data.items():
        area = 'source' if name in ('wiseref.dtx', 'wiseref.ins', 'build.lua') else 'doc'
        expected[f'{area}/latex/wiseref/{name}'] = value
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if archive.testzip() is not None:
            raise ValueError('TDS ZIP integrity check failed')
        actual = {entry.filename for entry in archive.infolist() if not entry.is_dir()}
        if actual != set(expected):
            raise ValueError(f'Unexpected TDS contents: missing={sorted(set(expected)-actual)[:10]}, extra={sorted(actual-set(expected))[:10]}')
        for name, value in expected.items():
            if archive.read(name) != value:
                raise ValueError(f'TDS file differs from current source/output: {name}')
    print('TDS layout: PASS (one runtime file; documentation, examples, and sources in their own trees)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Output .zip path (default: dist/wiseref-vVERSION.zip)')
    parser.add_argument('--stage', type=Path, help='Stage source-only files for l3build packaging')
    parser.add_argument('--check-tag', help='Check a release tag against the declared version, without building')
    parser.add_argument('--documents', type=Path, default=ROOT, help='Directory containing the current manual PDFs and build records')
    args = parser.parse_args()
    source = (ROOT / 'wiseref.dtx').read_text(encoding='utf-8')
    date, version = re.search(r'\\ProvidesExplPackage\{wiseref\}\{([^}]+)\}\{([^}]+)\}', source).groups()
    if not re.fullmatch(r'[0-9][A-Za-z0-9.-]*', version):
        raise ValueError(f'Invalid release version: {version}')
    if f'\\date{{{date}\\qquad v{version}}}' not in source:
        raise ValueError('Manual date/version differs from the package declaration')
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    if f'Version v{version} ({date.replace("/", "-")})' not in readme:
        raise ValueError('README date/version differs from the package declaration')
    if args.check_tag:
        if args.check_tag != f'v{version}':
            raise ValueError(f'Release tag {args.check_tag} does not match v{version}')
        print(f'Release tag {args.check_tag}: PASS')
        return
    if args.stage:
        stage = args.stage.resolve()
        if stage != ROOT / 'build/release-source':
            raise ValueError('Source staging must use build/release-source')
        data = payload(include_pdfs=False)
        if stage.exists():
            shutil.rmtree(stage)
        for name, content in data.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        print(f'l3build source staging: PASS ({len(data)} files)')
        return
    for language in ('en', 'zh'):
        pdf = args.documents / f'wiseref-{language}.pdf'
        inputs = (ROOT / 'wiseref.dtx', ROOT / 'wiseref.ins', ROOT / f'wiseref-{language}.tex')
        if not pdf.is_file() or pdf.stat().st_mtime < max(path.stat().st_mtime for path in inputs):
            raise ValueError(f'{pdf.name} is missing or stale; run make check-doc')

    data = payload(documents=args.documents)
    tds = (ROOT / 'wiseref.tds.zip').read_bytes()
    validate_tds(tds, data)
    with zipfile.ZipFile(ROOT / 'wiseref-ctan.zip') as archive:
        expected = {f'wiseref/{name}': value for name, value in data.items()}
        expected['wiseref.tds.zip'] = tds
        actual = {entry.filename for entry in archive.infolist() if not entry.is_dir()}
        if archive.testzip() is not None or actual != set(expected):
            raise ValueError(f'Unexpected l3build CTAN contents: missing={sorted(set(expected)-actual)[:10]}, extra={sorted(actual-set(expected))[:10]}')
        for name, value in expected.items():
            if archive.read(name) != value:
                raise ValueError(f'l3build CTAN file differs from current source/output: {name}')
    buffer = io.BytesIO()
    year, month, day = map(int, date.split('/'))
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(data.items()):
            info = zipfile.ZipInfo(f'wiseref/{name}', (year, month, day, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.internal_attr = 0 if name.endswith('.pdf') else 1
            archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED)
        info = zipfile.ZipInfo('wiseref.tds.zip', (year, month, day, 0, 0, 0))
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        archive.writestr(info, tds, compress_type=zipfile.ZIP_DEFLATED)
    output = args.output or ROOT / 'dist' / f'wiseref-v{version}.zip'
    if output.suffix != '.zip':
        raise ValueError('The output filename must end in .zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='wiseref-release-', dir=output.parent) as work:
        with zipfile.ZipFile(buffer) as archive:
            if archive.testzip() is not None:
                raise ValueError('ZIP integrity check failed')
            archive.extractall(work)
        package = Path(work) / 'wiseref'
        for language in ('en', 'zh'):
            (package / f'wiseref-{language}.pdf').unlink()
        result = subprocess.run(['make', 'check-doc'], cwd=package,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        log = output.with_suffix('.build.log')
        log.write_text(result.stdout, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(f'Clean archive build failed; see {log}')
        print('Clean archive build: PASS (source extraction, both manuals, live outputs and links)')
    output.write_bytes(buffer.getvalue())
    if args.documents.resolve() != ROOT:
        for language in ('en', 'zh'):
            for suffix in ('.pdf', '.aux', '.log'):
                shutil.copy2(args.documents / f'wiseref-{language}{suffix}', ROOT / f'wiseref-{language}{suffix}')
    for name in ('wiseref-ctan.zip', 'wiseref.tds.zip'):
        (output.parent / name).write_bytes((ROOT / name).read_bytes())
    assets = [output, output.parent / 'wiseref-ctan.zip', output.parent / 'wiseref.tds.zip']
    (output.parent / 'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in assets), encoding='utf-8')
    print(f'CTAN file checks: PASS ({len(data)} files, UTF-8/LF text, regular 0644 files)')
    print(f'Archive: {output}')
    print(f'SHA-256: {hashlib.sha256(buffer.getvalue()).hexdigest()}')


if __name__ == '__main__':
    main()
