# Representative CTAN class compatibility

## Results (2026-10-09)

TeX Live 2026: **57/57 combinations passed**, covering **17 real document
classes** and **12 languages**. Three engines were used where the class supports
them. Japanese classes were tested with their Unicode backends; the Arabic case
used LuaLaTeX and Babel with `bidi=basic`.

| Class | Languages in the matrix | Combinations |
| --- | --- | ---: |
| scrartcl | German, Dutch, Greek, Russian, Arabic | 11 |
| scrreprt | French | 3 |
| scrbook | Portuguese | 3 |
| memoir | Spanish, Italian | 6 |
| amsart | English | 3 |
| amsbook | English | 3 |
| beamer | English, French | 4 |
| ctexart | Chinese | 2 |
| ctexbook | Chinese | 2 |
| ltjsarticle | Japanese | 1 |
| bxjsarticle | Japanese | 2 |
| jlreq | Japanese | 1 |
| IEEEtran | English | 3 |
| elsarticle | English, French | 4 |
| revtex4-2 | English | 3 |
| acmart | English | 3 |
| abntex2 | Portuguese | 3 |

An additional three-engine IEEEtran check covers a starred section following a
numbered appendix: it remains an unnumbered target, while the preceding appendix
retains its number and reference type.

## What was checked

Each combination has four isolated builds:

1. The real class and ordinary reference commands, without wiseref.
2. The same document with wiseref loaded, without changing the reference text.
3. Actual wiseref references in default auto mode, using built-in translations.
4. Actual references with an explicitly selected built-in profile and additional
   formats for custom theorem identifiers; ordinary type translations are not
   registered or replaced by the test.

The baseline and observation builds must have identical standard label records,
page text, character bounding boxes, and ordinary link rectangles/destinations.
Reference builds assert types and tag modes for figures, tables, equations,
multi-line equations, shared theorem counters, appendices, and appendix equations.
Eleven outputs cover individual references, a mixed list, figure plurals and
ranges, and built-in theorem/lemma formats independently of the custom identifiers.
They are checked for expected localized words and connectors, and links must
point to existing destinations. Auto builds must select the actual document
language, with no missing-profile warning or English fallback. Ctex fixtures use
their Chinese scheme without Babel; Japanese fixtures import their language
through Babel.
Undefined references, missing glyphs, and nonconvergent auxiliary data fail a case.

Arabic PDF text extraction can reverse glyph order and mirror punctuation. The
fixture preserves the Arabic reference box while placing only the test markers
in an English span. Word assertions account for reversed RTL runs and shaped
words; this does not establish correct typography for every RTL construction.

## Fixes prompted by these tests

- Some hyperref Greek/Russian names use legacy font commands that are absent in
  Unicode documents configured through Babel locale imports. Auto mode
  ignores a borrowed reference-name macro containing an undefined command,
  warns once, and uses the language profile rather than executing the broken name.
- IEEEtran's numbered appendix sections internally use starred heading machinery.
  Its public `appendices`/`section` path is adapted so numbered and explicitly
  starred sections remain distinct. No kernel numbering or caption implementation
  is replaced.

Several first-run baseline failures were test/setup issues, not wiseref failures:
Beamer needed a native frame fixture, documented CTAN sources needed extraction,
and Japanese classes needed their font/JFM files. These were corrected in the
isolated cache before the final matrix. No package was installed into the user's
TeX tree for this test.

## Reproduction and provenance

```sh
make sty
python3 test/ctan.py --download \
  --cache /tmp/wiseref-ctan-cache \
  --work /tmp/wiseref-ctan-results
```

The work directory must not already exist. The cache can be reused without
`--download`. Use `--classes IEEEtran memoir` or `--languages arabic` for a targeted run.

`ctan-cases.json` lists the classes, class options, engines, source archives, and
fonts. Installed classes are loaded directly; missing classes/support files are
downloaded from CTAN into the cache. Preparation records source URLs and SHA-256
hashes. Each result records the actual class path, hash, version banner, engine,
reference output, and the profile selected in default auto mode. A frozen copy of
wiseref is used for the whole run.

The counts above describe the run on 2026-10-09, with a supplementary IEEEtran
starred-section check. Each new run writes logs and `results.json` to the chosen
work directory; rerun it to check a different candidate.
On 2026-10-10, the four Greek/Russian combinations passed again with the new
DejaVu font setup. This was a focused rerun, not another full 57-case run.

## Ctex auto detection

Auto mode recognizes ctex's loaded Chinese scheme without a language manager.
It uses LaTeX's loaded-file interface, not ctex's private state. Plain schemes
retain the English fallback; explicit language settings and Babel/polyglossia
take precedence. The four ctex class/engine combinations were rerun without Babel.

The separate `ctex.py` suite covers 44 combinations of three engines, Chinese/plain
schemes, ctex classes and package loading order, heading mode, pre-class loading,
and language-manager precedence. It also checks caption renaming, explicit
language selection, user formats/connectors, tag modes, and auxiliary convergence.
The class's raw numbers are preserved, including Chinese chapter numbers.

```sh
python3 test/ctex.py --work /tmp/wiseref-ctex
```

Unicode tests use Fandol; pdfLaTeX uses the distributed Arphic Type 1 CJK fonts
with `fontset=none`, without relying on system Windows font files. Detailed
results are written to `results.json` in the chosen work directory; `make check`
uses a timestamped directory under `test/output/ctex-*`.

## Limits of the result

This is a representative class-integration matrix, not a statistical survey of
CTAN and not a build of every publisher's complete author example.

- All twelve languages in this matrix have built-in profiles. Names supply
  standalone singular/plural forms, not automatic case or Arabic dual inflection.
  Native caption names remain authoritative in auto mode, including abbreviations;
  renamed terms have no automatically guessed plural.
- Greek/Russian fixtures now use DejaVu Serif from CTAN in an isolated font cache.
  The original 2026-10-09 run used a locally installed Unicode font.
  Japanese cases use Harano Aji, and Arabic uses Amiri. These fonts belong to the test setup, not
  the package's runtime requirements.
- Template-specific bibliography, external-reference, indexing, overlay,
  accessibility/tagging, and custom-counter combinations have not all been tested.
- The recorded versions passed on TeX Live 2026. Other releases need their own run.

## Translation references

Standalone names and connectors were compared with the distributed language data
of [zref-clever](https://ctan.org/pkg/zref-clever) and
[cleveref](https://ctan.org/pkg/cleveref), and caption data from
[Babel](https://ctan.org/pkg/babel) and
[polyglossia](https://ctan.org/pkg/polyglossia). Their terminology differs in places;
for example, French has `Table` and `Tableau`, and Spanish has `Cuadro` and `Tabla`.
Wiseref uses full standalone names by default and continues to inherit document
terms in auto mode. Arabic mathematical theorem/lemma/corollary terminology was
also checked against the terminology section of
[the Arabic theorem article](https://ar.wikipedia.org/wiki/مبرهنة).
No upstream reference-package implementation or runtime dependency is introduced.
