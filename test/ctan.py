"""Test real CTAN classes in isolated baseline, observation and reference builds.

Downloads stay in a caller-selected cache. No packages are installed into the
user's TeX tree. A failed baseline is an environment/class blocker, not evidence
of a wiseref regression. No claim of statistical CTAN-wide coverage is made.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import unicodedata
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reference_tests',ROOT/'test/run.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

NAMES={
 'english':('Figure','Figures','Table','Tables','Equation','Equations','Theorem','Lemma','Appendix','and'),
 'french':('Figure','Figures','Table','Tables','Équation','Équations','Théorème','Lemme','Annexe','et'),
 'german':('Abbildung','Abbildungen','Tabelle','Tabellen','Gleichung','Gleichungen','Satz','Lemma','Anhang','und'),
 'spanish':('Figura','Figuras','Cuadro','Cuadros','Ecuación','Ecuaciones','Teorema','Lema','Apéndice','y'),
 'portuguese':('Figura','Figuras','Tabela','Tabelas','Equação','Equações','Teorema','Lema','Apêndice','e'),
 'italian':('Figura','Figure','Tabella','Tabelle','Equazione','Equazioni','Teorema','Lemma','Appendice','e'),
 'dutch':('Figuur','Figuren','Tabel','Tabellen','Vergelijking','Vergelijkingen','Stelling','Lemma','Bijlage','en'),
 'russian':('Рисунок','Рисунки','Таблица','Таблицы','Уравнение','Уравнения','Теорема','Лемма','Приложение','и'),
 'greek':('Σχήμα','Σχήματα','Πίνακας','Πίνακες','Εξίσωση','Εξισώσεις','Θεώρημα','Λήμμα','Παράρτημα','και'),
 'chinese':('图','图','表','表','式','式','定理','引理','附录','和'),
 'japanese':('図','図','表','表','式','式','定理','補題','付録','、'),
 'arabic':('الشكل','الأشكال','الجدول','الجداول','المعادلة','المعادلات','المبرهنة','القضية المساعدة','الملحق','و'),
}

def fetch(url, target):
    if target.exists():return dict(url=url,path=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),cached=True)
    request=urllib.request.Request(url,headers={'User-Agent':'wiseref-compatibility-test/0.1'})
    last=None
    for _ in range(3):
        try:
            with urllib.request.urlopen(request,timeout=90) as response:
                data=response.read(); final=response.geturl()
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            return dict(url=url,redirect=final,path=str(target),sha256=hashlib.sha256(data).hexdigest())
        except Exception as error:last=error;time.sleep(1)
    return dict(url=url,error=str(last))

def prepare(cache, manifest, download):
    cache.mkdir(parents=True,exist_ok=True);sources=[]
    if not download and (cache/'provenance.json').exists():
        sources=json.loads((cache/'provenance.json').read_text())
    if download:
        for name,url in manifest['archives'].items():
            print('PREPARE',name,flush=True)
            archive=cache/'archives'/(name+'.zip');result=fetch(url,archive);sources.append(result)
            if 'error' in result:continue
            try:
                with zipfile.ZipFile(archive) as z:
                    for entry in z.infolist():
                        rel=Path(entry.filename)
                        if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe archive path')
                        if not entry.is_dir():
                            target=cache/'packages'/name/rel;target.parent.mkdir(parents=True,exist_ok=True)
                            target.write_bytes(z.read(entry))
            except Exception as error:result['error']=str(error)
        for url in manifest['fonts']:
            print('PREPARE',url.rsplit('/',1)[-1],flush=True)
            sources.append(fetch(url,cache/'fonts'/url.rsplit('/',1)[-1]))
    # Keep the Greek/Cyrillic fixtures independent of proprietary system fonts.
    for name in ('DejaVuSerif.ttf', 'DejaVuSerif-Bold.ttf',
                 'DejaVuSerif-Italic.ttf', 'DejaVuSerif-BoldItalic.ttf'):
        matches=list((cache/'packages/dejavu').rglob(name))
        if matches:
            target=cache/'fonts'/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(matches[0],target)
    # Some CTAN archives contain documented sources rather than extracted files.
    for name in ('bxjscls','jlreq','acmart','elsarticle','babel-portuges','luacode'):
        folder=cache/'packages'/name
        targets={'babel-portuges':'portuges.ldf','luacode':'luacode.sty'}
        wanted=targets.get(name,'*.cls')
        if folder.exists() and not list(folder.rglob(wanted)):
            for installer in folder.rglob('*.ins'):
                with (installer.parent/'extract.log').open('w') as log:
                    subprocess.run(['xetex','-interaction=nonstopmode','-halt-on-error',installer.name],
                                   cwd=installer.parent,stdout=log,stderr=subprocess.STDOUT,timeout=120)
    for name,source,target in (('revtex','revtex4-2.dtx','revtex4-2.cls'),('luacode','luacode.dtx','luacode.sty')):
        folder=cache/'packages'/name
        if folder.exists() and not list(folder.rglob(target)):
            for installer in folder.rglob(source):
                with (installer.parent/'extract.log').open('w') as log:
                    subprocess.run(['xetex','-interaction=nonstopmode','-halt-on-error',installer.name],
                                   cwd=installer.parent,stdout=log,stderr=subprocess.STDOUT,timeout=120)
    folder=cache/'packages/jlreq'
    if folder.exists() and not list(folder.rglob('jfm-jlreqv.lua')):
        for builder in folder.rglob('make_variant_jfm.lua'):
            with (builder.parent/'jfm-build.log').open('w') as log:
                subprocess.run(['texlua',builder.name],cwd=builder.parent,stdout=log,
                               stderr=subprocess.STDOUT,check=True,timeout=60)
    if download:(cache/'provenance.json').write_text(json.dumps(sources,indent=2))
    return sources

def profile(lang):
    fig,figs,tab,tabs,eq,eqs,thm,lemma,app,join=NAMES[lang]
    gap='' if lang in ('chinese','japanese') else '~'
    # Custom environment identifiers need formats; ordinary types use built-ins.
    return r'\wiserefsetup{langs={'+lang+'={'+\
        f'wisethm={{prefix={{{thm}{gap}}}}},wiselemma={{prefix={{{lemma}{gap}}}}},'+\
        '}},lang='+lang+'}'

CHECKS=r'''
\ExplSyntaxOn
\cs_new_eq:NN\WiseOriginalResolve\__wise_resolve_options:
\cs_set_protected:Npn\__wise_resolve_options:{
  \WiseOriginalResolve
  \iow_term:e{WISE-RESOLVED-LANG:~\l__wise_selected_lang_tl}
}
\NewDocumentCommand\WiseExpected{mmm}{
  \prop_get:NnNTF\g__wise_labels_prop{#1}\l_tmpa_tl
    {\tl_set:Nn\l_tmpb_tl{{#2}{#3}}
     \str_if_eq:eeTF{\tl_to_str:V\l_tmpa_tl}{\tl_to_str:V\l_tmpb_tl}
       {\iow_term:n{WISE-TYPE-PASS:~#1}}
       {\iow_term:e{WISE-TYPE-FAIL:~#1~=~\tl_to_str:V\l_tmpa_tl}}}
    {\iow_term:n{WISE-TYPE-MISSING:~#1}}
}
\NewDocumentCommand\WiseRenderCase{mm}{
  \par\begingroup\setbox0=\hbox{\wref{#2}}
  \iow_term:e{WISE-OUTPUT:~#1~=~\dim_use:N\wd0}
   \ifdim\wd0>0pt\relax
     \ifdefined\WiseRTL
       \foreignlanguage{english}{\hbox{[B#1]\box0[E#1]}}
     \else\hbox{[B#1]\box0[E#1]}\fi
   \else\errmessage{Empty~reference}\fi
  \endgroup\par
}
% Exercise standard built-in formats separately from custom environment names.
% Classification and stored numbers are checked by the original label assertions.
\NewDocumentCommand\WiseRenderBuiltin{mm}{
  \group_begin:
  \prop_put:Nnn\g__wise_labels_prop{#2}{{#1}{normal}}
  \WiseRenderCase{builtin-#1}{#2}
  \group_end:
}
\ExplSyntaxOff
'''

def driver(case, engine, mode, fonts):
    cls=case['class'];options=case.get('options_by_engine',{}).get(engine,case.get('options',''))
    lines=[r'\documentclass['+options+']{'+cls+'}']
    if engine=='pdflatex' and not case.get('cjk') and not case.get('japanese'):
        lines.append(r'\usepackage[T1]{fontenc}')
    lines += [r'\usepackage{amsmath}']
    if case.get('unicode_font'):
        lines += [r'\usepackage{fontspec}',
                  r'\setmainfont{DejaVuSerif.ttf}[Path='+fonts.as_posix()+'/,BoldFont=DejaVuSerif-Bold.ttf,'
                  r'ItalicFont=DejaVuSerif-Italic.ttf,BoldItalicFont=DejaVuSerif-BoldItalic.ttf]']
    if case.get('japanese'):
        if engine=='lualatex':
            lines += [r'\usepackage{luatexja-fontspec}',r'\setmainjfont{HaranoAjiMincho-Regular.otf}[BoldFont=HaranoAjiMincho-Bold.otf]',
                      r'\setsansjfont{HaranoAjiGothic-Regular.otf}[BoldFont=HaranoAjiGothic-Bold.otf]']
        else:
            lines += [r'\setjamainfont[BoldFont=HaranoAjiMincho-Bold.otf]{HaranoAjiMincho-Regular.otf}',
                      r'\setjasansfont[BoldFont=HaranoAjiGothic-Bold.otf]{HaranoAjiGothic-Regular.otf}']
    if not case.get('cjk'):
        lines += [r'\usepackage[bidi=basic]{babel}' if case.get('arabic') else r'\usepackage{babel}',
                  r'\babelprovide[import,main]{'+case['lang']+'}']
    if case.get('arabic'):
        lines += [r'\babelprovide[import]{english}',r'\def\WiseRTL{1}',
                  r'\babelfont{rm}[Path='+fonts.as_posix()+'/,Script=Arabic,BoldFont=Amiri-Bold.ttf]{Amiri-Regular.ttf}']
    lines += [r'\usepackage{hyperref}']
    lines += [r'\newcommand\WiseAppendix{\appendices}' if cls=='IEEEtran' else r'\newcommand\WiseAppendix{\appendix}']
    if cls=='IEEEtran':lines += [r'\def\WiseIEEE{1}']
    if case.get('beamer'):
        lines += [r'\def\WiseBeamer{1}',r'\setbeamertemplate{caption}[numbered]',r'\setbeamertemplate{theorems}[numbered]']
    if case.get('chapter'):lines.append(r'\def\WiseChapter{1}')
    thm=NAMES[case['lang']][6];lemma=NAMES[case['lang']][7]
    lines += [r'\newtheorem{wisethm}{'+thm+'}[section]',r'\newtheorem{wiselemma}[wisethm]{'+lemma+'}']
    if mode!='baseline':lines += [r'\usepackage{wiseref}']
    if mode in ('references','auto-references'):
        if mode=='references':lines += [profile(case['lang'])]
        lines += [r'\def\WiseChecks{1}',CHECKS]
    lines += [r'\input{cases.tex}']
    return '\n'.join(lines)+'\n'

def environment(cache, work):
    env=os.environ.copy()
    env.update(TEXINPUTS='.:'+str(cache/'packages')+'//:',TEXMFHOME=str(work/'empty-texmf'),
               LUAINPUTS='.:'+str(cache/'packages')+'//:',
               OPENTYPEFONTS=str(cache/'fonts')+'//:',TTFONTS=str(cache/'fonts')+'//:',
               OSFONTDIR=str(cache/'fonts'),SOURCE_DATE_EPOCH='1791504000',FORCE_SOURCE_DATE='1')
    return env

def outputs(pdf):
    text=''.join(page[0] for page in base.pdf_signature(pdf));found={}
    for name in ('figure','figureplural','figurerange','table','equation','theorem','lemma',
                 'builtin-theorem','builtin-lemma','appendix','mixed'):
        # RTL extraction can reverse marker order and mirror the brackets.
        # Use exact marker names and the nearest pair, not a later output line.
        left=re.escape('B'+name)+r'(?![A-Za-z-])'
        right=re.escape('E'+name)+r'(?![A-Za-z-])'
        matches=[m for pattern in (left+r'(.*?)'+right,right+r'(.*?)'+left)
                 if (m:=re.search(pattern,text,re.S)) is not None]
        assert matches,('missing reference output',name,text)
        found[name]=min(matches,key=lambda m:len(m[1]))[1]
        assert len(normalized(found[name]))>1,('Empty marker pair',name,text)
    return found

def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',text)
                    if not c.isspace() and unicodedata.category(c)!='Cf')

def contains_word(text, word, rtl=False):
    value=normalized(text);wanted=normalized(word)
    candidates={wanted}
    if rtl:
        # PDF extraction may reverse an RTL run, or reverse each shaped word
        # while retaining the logical order of separate word runs.
        candidates.update((wanted[::-1],''.join(normalized(w)[::-1] for w in word.split())))
    return any(candidate in value for candidate in candidates)

def compile_case(folder, case, engine, mode, cache, work):
    folder.mkdir(parents=True)
    shutil.copy2(work/'candidate.sty',folder/'wiseref.sty')
    body=(ROOT/'test/ctan-body.tex').read_text()
    if case.get('beamer'):
        # Beamer collects frame bodies before execution. A conditional around
        # the opening frame must not remain unclosed during collection.
        body=body.replace(r'\ifdefined\WiseBeamer\begin{frame}[allowframebreaks]{Reference targets}\fi',
                          r'\begin{frame}[allowframebreaks]{Reference targets}')
        body=body.replace(r'\ifdefined\WiseBeamer\end{frame}\begin{frame}{Appendix targets}\fi',
                          r'\end{frame}\begin{frame}{Appendix targets}')
        body=body.replace(r'\ifdefined\WiseBeamer\end{frame}\begin{frame}[allowframebreaks]{References}\else\clearpage\fi',
                          r'\end{frame}\begin{frame}[allowframebreaks]{References}')
        body=body.replace(r'\ifdefined\WiseBeamer\end{frame}\fi',r'\end{frame}')
    (folder/'cases.tex').write_text(body)
    (folder/'main.tex').write_text(driver(case,engine,mode,cache/'fonts'))
    env=environment(cache,work)
    with (folder/'compile.log').open('w') as out:
        for _ in range(3):
            subprocess.run([engine,'-no-shell-escape','-recorder','-interaction=nonstopmode','-halt-on-error','main.tex'],
                           cwd=folder,env=env,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=180)
    log=(folder/'main.log').read_text(errors='replace')
    if re.search(r'undefined references|multiply defined|Label\(s\) may have changed|Missing character:',log):
        raise AssertionError('Unresolved labels, font characters or rerun warning; inspect main.log')
    assert (folder/'main.pdf').is_file()
    return log

def error_details(folder, error):
    path=folder/'compile.log';text=path.read_text(errors='replace') if path.exists() else ''
    lines=text.splitlines();details=[]
    for i,line in enumerate(lines):
        if line.startswith('!') or ' Error:' in line or 'not found' in line:
            details += lines[max(0,i-1):i+6]
    return dict(error=str(error),log=str(path),details='\n'.join(details[-30:]))

def test_case(work, cache, case, engine):
    name=f'{case["class"]}-{case["lang"]}-{engine}';root=work/name
    result=dict(case=name,document_class=case['class'],lang=case['lang'],engine=engine,
                ctan='https://ctan.org/pkg/'+{'IEEEtran':'ieeetran','revtex4-2':'revtex','bxjsarticle':'bxjscls',
                'ctexart':'ctex','ctexbook':'ctex','ltjsarticle':'luatexja','scrartcl':'koma-script',
                'scrreprt':'koma-script','scrbook':'koma-script','amsart':'amscls','amsbook':'amscls'}.get(case['class'],case['class']),
                custom_font=case.get('unicode_font') or case.get('japanese') or case.get('arabic') or False)
    try:
        baseline_log=compile_case(root/'baseline',case,engine,'baseline',cache,work)
    except Exception as error:
        result.update(status='BLOCKED_BASELINE',**error_details(root/'baseline',error));return result
    try:
        observer_log=compile_case(root/'observed',case,engine,'observed',cache,work)
        old=base.records(root/'baseline/main.aux','newlabel',2)
        new=base.records(root/'observed/main.aux','newlabel',2)
        assert old==new,'Standard labels changed'
        before=base.pdf_signature(root/'baseline/main.pdf');after=base.pdf_signature(root/'observed/main.pdf')
        assert before==after,'Loading wiseref changed PDF text or character positions'
        assert base.link_signature(root/'baseline/main.pdf')[0]==base.link_signature(root/'observed/main.pdf')[0], 'Standard links changed'
    except Exception as error:
        result.update(status='FAIL_OBSERVATION',**error_details(root/'observed',error));return result
    try:
        failed_phase='auto-references'
        auto_log=compile_case(root/'auto-references',case,engine,'auto-references',cache,work)
        default_output=outputs(root/'auto-references/main.pdf')
        auto_profiles=sorted(set(re.findall(r'WISE-RESOLVED-LANG:\s*(\S+)',auto_log)))
        assert auto_profiles==[case['lang']],('Wrong automatic profile',auto_profiles)
        assert 'No profile for document language' not in auto_log,'Unexpected English fallback'
        failed_phase='references'
        ref_log=compile_case(root/'references',case,engine,'references',cache,work)
        failures=re.findall(r'WISE-TYPE-(?:FAIL|MISSING):[^\n]*',ref_log)
        assert not failures,failures
        type_assertions=14 if case['class']=='IEEEtran' else 13
        assert len(re.findall('WISE-TYPE-PASS:',ref_log))==type_assertions
        assert len(re.findall('WISE-OUTPUT:',ref_log))==11
        rendered=outputs(root/'references/main.pdf')
        names=NAMES[case['lang']]
        for key,word in zip(('figure','table','equation','theorem','lemma','appendix'),
                            (names[0],names[2],names[4],names[6],names[7],names[8])):
            assert contains_word(rendered[key],word,case.get('arabic')),(key,word,rendered[key])
        for key in ('figureplural','figurerange'):
            assert contains_word(rendered[key],names[1],case.get('arabic')),(key,names[1],rendered[key])
        for key,word in (('builtin-theorem',names[6]),('builtin-lemma',names[7])):
            assert contains_word(rendered[key],word,case.get('arabic')),(key,word,rendered[key])
        join=normalized(names[-1])
        for phase,values in (('explicit',rendered),('auto',default_output)):
            for key in ('mixed','figureplural'):
                connector='、' if case['lang']=='chinese' and key=='figureplural' else join
                assert contains_word(values[key],connector,case.get('arabic')),(phase,key,connector,values[key])
        assert base.records(root/'references/main.aux','newlabel',2)==old,'Reference use changed numbering'
        links,destinations=base.link_signature(root/'references/main.pdf')
        assert links,'No reference links'
        inputs=[line[6:] for line in (root/'references/main.fls').read_text().splitlines() if line.startswith('INPUT ')]
        assert not any(Path(p).name.startswith(('hithesis','docxlike')) for p in inputs)
        classes=[Path(p) for p in inputs if Path(p).name==case['class']+'.cls']
        assert classes,'The requested real class was not loaded'
        classfile=classes[0]
        result.update(status='PASS',pages=len(before),unchanged_labels=len(old),type_assertions=type_assertions,
                       reference_cases=11,output=rendered,default_auto_output=default_output,
                      links=len(links),class_file=str(classfile),
                      class_sha256=hashlib.sha256(classfile.read_bytes()).hexdigest(),
                      class_version=re.findall(r'Document Class:[^\n]*',baseline_log),
                      other_reference_packages=sorted({Path(p).name for p in inputs if Path(p).name in ('cleveref.sty','zref-clever.sty')}),
                       default_auto_profiles=auto_profiles,
                      unsupported_auto_profile='No profile for document language' in auto_log)
    except Exception as error:result.update(status='FAIL_REFERENCES',phase=failed_phase,**error_details(root/failed_phase,error))
    return result

def report(work, results, sources):
    count={s:sum(r['status']==s for r in results) for s in ('PASS','BLOCKED_BASELINE','FAIL_OBSERVATION','FAIL_REFERENCES')}
    lines=['# CTAN class compatibility results','',
           'These are representative integration fixtures, not a statistical survey of CTAN or full author-template documents.',
            'Ordinary types use built-in translations. Configured builds add only custom theorem identifiers. Auto builds assert the actual document profile without an English fallback.',
           '',str(count),'','| Class | Language | Engine | Result |','| --- | --- | --- | --- |']
    lines += [f'| {r["document_class"]} | {r["lang"]} | {r["engine"]} | {r["status"]} |' for r in sorted(results,key=lambda r:r['case'])]
    lines += ['','## Failures and baseline blockers','']
    for r in results:
        if r['status']!='PASS':lines += [f'### {r["case"]}',r['error'],'```',r.get('details',''), '```',f'Log: `{r["log"]}`','']
    (work/'README.md').write_text('\n'.join(lines)+'\n')
    (work/'results.json').write_text(json.dumps(dict(counts=count,sources=sources,
        candidate_sha256=hashlib.sha256((work/'candidate.sty').read_bytes()).hexdigest(),
         results=results),ensure_ascii=False,indent=2))


def select_jobs(manifest, classes=None, languages=None):
    for values, field, label in ((classes, 'class', 'classes'), (languages, 'lang', 'languages')):
        unknown=set(values or ())-{case[field] for case in manifest['cases']}
        if unknown:raise ValueError('Unknown CTAN '+label+': '+', '.join(sorted(unknown)))
    jobs=[(case,e) for case in manifest['cases'] for e in case['engines']
          if (not classes or case['class'] in classes)
          and (not languages or case['lang'] in languages)]
    if not jobs:raise ValueError('No CTAN class tests selected')
    return jobs


def results_failed(results):
    return not results or any(result['status'] != 'PASS' for result in results)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--cache',type=Path,required=True);p.add_argument('--download',action='store_true')
    p.add_argument('--jobs',type=int,default=3);p.add_argument('--classes',nargs='*')
    p.add_argument('--languages',nargs='*');a=p.parse_args()
    manifest=json.loads((ROOT/'test/ctan-cases.json').read_text())
    try:cases=select_jobs(manifest,a.classes,a.languages)
    except ValueError as error:p.error(str(error))
    a.work=a.work.resolve();a.cache=a.cache.resolve();a.work.mkdir(parents=True,exist_ok=False)
    shutil.copy2(ROOT/'wiseref.sty',a.work/'candidate.sty')
    (a.work/'empty-texmf').mkdir()
    sources=prepare(a.cache,manifest,a.download)
    results=[]
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        futures=[pool.submit(test_case,a.work,a.cache,case,e) for case,e in cases]
        for future in as_completed(futures):
            r=future.result();results.append(r)
            print(f'{len(results)}/{len(cases)} {r["case"]}: {r["status"]}',flush=True)
            report(a.work,results,sources)
    print('Results:',a.work/'README.md',flush=True)
    raise SystemExit(results_failed(results))

if __name__=='__main__':main()
