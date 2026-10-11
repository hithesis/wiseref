"""Verify the generated package matches the active package guard in the dtx."""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--sty', type=Path, default=ROOT/'wiseref.sty')
a = p.parse_args()
source = (ROOT/'wiseref.dtx').read_text()
start = source.index('%<*package>') + len('%<*package>')
end = source.index('%</package>', start)

def active(text):
    return [line.rstrip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith('%')]

assert active(source[start:end]) == active(a.sty.read_text()), \
    'wiseref.sty is out of sync; run make sty'
print('dtx package guard and generated wiseref.sty: PASS')
