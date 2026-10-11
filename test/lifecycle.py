"""Check loading after/before amsmath and removal with an existing aux file."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--work',type=Path,required=True)
a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False)
results=[]
for engine in ('lualatex','xelatex','pdflatex'):
    folder=a.work/engine;folder.mkdir()
    shutil.copy2(ROOT/'wiseref.sty',folder/'wiseref.sty')
    body=r'\begin{document}\begin{equation}a=b\label{a}\end{equation}'+r'\wref{a}\end{document}'
    for order in ('before','after'):
        packages=(r'\usepackage{wiseref}\usepackage{amsmath}' if order=='before'
                  else r'\usepackage{amsmath}\usepackage{wiseref}')
        (folder/'main.tex').write_text(r'\documentclass{article}'+packages+body)
        for run in range(3):
            with (folder/f'{order}-{run}.log').open('w') as output:
                subprocess.run([engine,'-interaction=nonstopmode','-halt-on-error','main.tex'],
                               cwd=folder,stdout=output,stderr=subprocess.STDOUT,check=True,timeout=60)
        assert 'Rerun to get wiseref' not in (folder/'main.log').read_text()
        assert r'\wiserefRecord{a}{equation}{normal}' in (folder/'main.aux').read_text()
    (folder/'main.tex').write_text(r'\documentclass{article}\usepackage{amsmath}'+body.replace(r'\wref',r'\ref'))
    with (folder/'removed.log').open('w') as output:
        subprocess.run([engine,'-interaction=nonstopmode','-halt-on-error','main.tex'],
                       cwd=folder,stdout=output,stderr=subprocess.STDOUT,check=True,timeout=60)
    print(engine+': load order, convergence and package removal PASS',flush=True)
    results.append(dict(case=engine,status='PASS'))
    (a.work/'results.json').write_text(json.dumps(results,indent=2)+'\n')
