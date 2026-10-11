"""Exercise auto language selection, profiles, native names and user precedence."""
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
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
LOCK=threading.Lock()
EXPECTED={
    'default':'Figure 1','custom-type':'Widget 1',
    'document-name':'Picture 1','unknown-plural':'Picture 1 and 2',
    'document-plural':'Pictures 1 and 2','explicit-language':'Figure 1',
    'registered':'Illustrations 1 et 2 et Tableau 1',
    'updated-profile':'Illustrations 1 et 2',
    'override-survives':'Photos 1 et 2','after-group':'Figure 1',
    'callback-en':'Figure 1','callback-fr':'Illustration 1',
    'format-survives':'Custom [1]','inheritance-disabled':'Figure 1',
    'disabled-plural':'Figures 1 and 2','disabled-one-type':'Figure 1 and Data 1',
    'inheritance-reenabled':'Picture 1','profile-disables-name':'Figure 1',
    'setup-enables-name':'Picture 1','nested-disables-name':'Figure 1',
    'nested-restores-name':'Picture 1','disabled-explicit-affixes':'Photo [1]!',
    'disabled-unusable-name':'Figure 1','setup-disables-profile-name':'Figure 1',
    'name-as-suffix':'1 Picture','plural-name-as-suffix':'1 and 2 Pictures',
    'suffix-name-changes':'1 Photo','fixed-lang':'Illustration 1',
    'ja-heading':'Part 1 Unit','ja-heading-off':'Part 1 Section',
    'empty-override':'1','early':'Early 1','late':'Late 1',
    'native-case':'figure 1',
    'unusable-autoref-name':'Equation (1)',
    'parameterized-name':'Figure 1',
    'cycle-rollback':'Illustration 1','old-key-rejected':'Figure 1',
    'unknown-fixed':'Figure 1',
    'old-position-rejected':'Picture 1','nonboolean-rejected':'Picture 1',
}
LOCAL={'local-french':'Image 1 et 2','local-override':'Photos 1 et 2',
       'switch-preserves':'Photos 1 and 2','back-english':'Figures 1 and 2'}

def run(work, engine, manager):
    folder=work/f'{engine}-{manager}';folder.mkdir()
    shutil.copy2(ROOT/'wiseref.sty',folder/'wiseref.sty')
    shutil.copy2(ROOT/'test/langs.tex',folder/'cases.tex')
    flag={'plain':'','babel':r'\def\WiseBabel{1}','polyglossia':r'\def\WisePolyglossia{1}'}[manager]
    (folder/'main.tex').write_text(flag+r'\input{cases.tex}')
    env=os.environ.copy();env.update(TEXINPUTS='.:',TEXMFHOME=str(work/'empty-texmf'))
    with (folder/'compile.log').open('w') as stream:
        for _ in range(3):
            subprocess.run([engine,'-no-shell-escape','-interaction=nonstopmode','-halt-on-error','-recorder','main.tex'],
                           cwd=folder,env=env,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=120)
    with LOCK,pdfium.PdfDocument(folder/'main.pdf') as pdf:
        text=''
        for page in pdf:
            tp=page.get_textpage();text+=tp.get_text_range();tp.close();page.close()
    expected=EXPECTED | (LOCAL if manager!='plain' else {})
    if manager=='babel':expected |= {'unknown-auto':'Figure 1','unknown-auto-again':'Figure 1'}
    actual={}
    for key,wanted in expected.items():
        match=re.search(f'L-{key}-B(.*?)L-{key}-E',text,re.S)
        assert match,('missing marker',key,text)
        actual[key]=re.sub(r'\s+',' ',match[1]).strip()
        assert actual[key]==wanted,(key,wanted,actual[key])
    log=(folder/'main.log').read_text(errors='replace')
    assert 'Rerun to get wiseref' not in log
    assert 'Missing character:' not in log
    assert "Unknown wiseref option 'name-position'" in log
    assert 'use-document-name' in log and 'accepts only a fixed set' in log
    if manager=='babel':assert log.count('unregistered-document')==1,log
    inputs=(folder/'main.fls').read_text()
    assert 'hithesis.cls' not in inputs and 'docxlike.sty' not in inputs
    reader=PdfReader(folder/'main.pdf');dest=reader.named_destinations;links=0
    for page in reader.pages:
        for entry in page.get('/Annots',[]):
            action=entry.get_object().get('/A',{})
            if action.get('/S')=='/GoTo':assert action['/D'] in dest;links+=1
    assert links
    return dict(case=folder.name,status='PASS',assertions=len(expected),links=links,output=actual)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False);(a.work/'empty-texmf').mkdir()
    cases=[(e,m) for e in ('lualatex','xelatex','pdflatex') for m in ('plain','babel')]
    cases += [(e,'polyglossia') for e in ('lualatex','xelatex')]
    results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(run,a.work,e,m):f'{e}-{m}' for e,m in cases}
        for future in as_completed(futures):
            try:r=future.result()
            except Exception as error:r=dict(case=futures[future],status='FAIL',error=str(error))
            print(r['case'],r['status'],r.get('error',''),flush=True);results.append(r)
            (a.work/'results.json').write_text(json.dumps(results,indent=2))
    raise SystemExit(any(r['status']!='PASS' for r in results))

if __name__=='__main__':main()
