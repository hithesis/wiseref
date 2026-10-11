# Package compatibility (2026-10-09)

TeX Live 2026: **103 combinations inspected**, **101 PASS**,
**2 BLOCKED_BASELINE**, **0 wiseref test failures**. Passing configurations include
the explicit thmtools workaround below. The two blocked tagged-PDF baselines are
not compatibility passes. These counts describe this test set, not a percentage
of CTAN packages or real-world documents.

On 2026-10-10, after the document-name interface change, a focused rerun passed
33/33 combinations: cleveref before/after wiseref, thmtools shared counters,
ntheorem and its before/after stress fixtures, caption/enumitem, subfig,
listings/longtable, xr, and xr-hyper, each with all three engines. This is a
rerun of those scenarios, not a new run of the entire 103-case matrix.

The CI portable suite was subsequently checked locally on TeX Live 2026:
78/78 combinations passed. The tagging suite produced two basic-fixture passes
and two `KNOWN_BASELINE_FAILURE` records matching the paragraph-hook error below.

| Scenario | Engines | Combinations | Result |
| --- | --- | ---: | --- |
| unicode-math, Latin Modern Math / TeX Gyre Termes Math, before/after wiseref | Lua, Xe | 8 | PASS |
| mathtools, before/after wiseref | Lua, Xe, pdf | 6 | PASS |
| mathtools + unicode-math | Lua, Xe | 2 | PASS |
| mathtools showonlyrefs, including unicode-math | Where supported | 5 | PASS |
| cleveref, before/after wiseref, after hyperref | Lua, Xe, pdf | 6 | PASS |
| varioref | Lua, Xe, pdf | 3 | PASS |
| zref-clever, separate standard and zref labels | Lua, Xe, pdf | 3 | PASS |
| thmtools, independent theorem counters | Lua, Xe, pdf | 3 | PASS |
| thmtools sibling counter, public first-aid hook workaround | Lua, Xe, pdf | 3 | PASS |
| thmtools sibling counter + cleveref, same workaround | Lua, Xe, pdf | 3 | PASS |
| ntheorem shared counter, automatic detection | Lua, Xe, pdf | 3 | PASS |
| ntheorem shared counter, explicit lemma type | Lua, Xe, pdf | 3 | PASS |
| ntheorem before/after wiseref, named/custom/unnumbered/nested environments | Lua, Xe, pdf | 6 | PASS |
| caption/subcaption + enumitem, Roman item references | Lua, Xe, pdf | 3 | PASS |
| subfig | Lua, Xe, pdf | 3 | PASS |
| listings + longtable | Lua, Xe, pdf | 3 | PASS |
| algorithm + algorithmicx/algpseudocode | Lua, Xe, pdf | 3 | PASS |
| algorithm2e | Lua, Xe, pdf | 3 | PASS |
| xr/xr-hyper, external types, tags, appendices and ranges, loading order | Lua, Xe, pdf | 12 | PASS |
| biblatex numeric/authoryear, actual Biber builds | Lua, Xe, pdf | 6 | PASS |
| minted, actual latexminted highlighting | Lua, Xe, pdf | 3 | PASS |
| tcolorbox numbered theorem | Lua, Xe, pdf | 3 | PASS |
| mdframed numbered theorem | Lua, Xe, pdf | 3 | PASS |
| thmtools restatable theorem | Lua, Xe, pdf | 3 | PASS |
| Tagged PDF: basic figures/tables/equations/references | Lua, pdf | 2 | PASS |
| Tagged PDF: comprehensive package fixture | Lua, pdf | 2 | BLOCKED_BASELINE |

## Checks and configuration

Each case has an ordinary-reference baseline, the same document with wiseref
loaded, and a build that actually calls wref. Observation must preserve standard
labels, PDF text and character positions, and links, including other packages'
own references. Nameref and refcount are also exercised through hyperref.

Actual references assert types, equation tag/tag* formats, multi-line and
subequation references, compressed ranges, shared counters, subfigures, list
items and footnotes. Links must reach valid destinations; starred references have
no links. Showonlyrefs tests require distinct numbers and reference marks for
equations used only by wref, rather than accepting a stale hidden number.
External tests include normal/tag/tag* equations, appendices, endpoint links and
range compression. References from different PDFs are not compressed into a
single range. Tagged-PDF comparisons use structural destination identity and role,
not PdfReader memory addresses in indirect-object representations.

The fixtures explicitly configure additional counters:

```latex
\wiserefsetup{
  lstlisting={prefix={Listing~}},
  algorithm={prefix={Algorithm~}},
  algocf={prefix={Algorithm~}},
  listing={prefix={Listing~}},
  tcb@cnt@wisebox={prefix={Boxed~}},
}
```

These are integration tests of the real counters, not built-in translations for
every counter supplied by another package. Math font files are selected by their
TeX Live filenames, avoiding a local XeTeX font-name lookup failure that also
occurred in the baseline.

## Fixes prompted by the tests

- **mathtools showonlyrefs:** wref marks all equation labels in a call through the
  public `\noeqref` command, including intermediate labels in compressed ranges.
  Recompilation gives equations used only by wref visible, distinct numbers.
  No private mathtools state is read or replaced.
- **cleveref:** a generic trailing hook on its optional-argument refstepcounter
  dispatcher disturbed argument scanning. Wiseref clears unnumbered-target
  state on the underlying counter step, excluding page shipping, and preserves
  the dispatcher.
- **listings:** macro-based label names are expanded consistently with standard
  auxiliary writing before metadata lookup, preventing permanent rerun warnings.
- **ntheorem:** a signature-checked before hook records the actual theorem
  environment and backing counter. Nested equation and footnote labels retain
  their types, unnumbered theorem styles remain unnumbered, and optional titles
  do not replace type names. Explicit `\wisereftype` remains available.
- **External types:** public LaTeX record properties carry type and tag mode
  under `<label>@wiseref`. xr/xr-hyper preserve the suffix while adding their
  prefix, so no XR parser or label-name heuristic is needed.

## Configuration and remaining boundaries

**Ntheorem:** shared counters work automatically, including custom theorem
names, nested environments, equations and footnotes. Declaration keywords are
used as type names rather than optional theorem titles. The explicit override
still works for special environments:

```latex
\AddToHook{env/lemma/begin}{\wisereftype{lemma}}
```

**External references:** the source document must load the current wiseref and be
recompiled. Automatic type import also needs LaTeX's record-property interface
and an xr/xr-hyper version that imports those properties (tested on TeX Live 2026).
Older kernels still support ordinary local wiseref records. A source without type
metadata cannot supply automatic types; standard number-only fallback remains.

**Thmtools sibling:** the raw 2026 baseline fails with `Command \c@lemma already
defined`: thmtools creates a counter alias, then the kernel's amsthm first-aid
rewrite tries to create the self-alias `lemma -> lemma` again. The tested article
configuration removes that named hook before loading amsthm:

```latex
\RemoveFromHook{package/amsthm/after}[firstaid/aliascounter]
\usepackage{amsthm,thmtools}
```

The same configuration is used in the ordinary baseline and wiseref builds;
shared counters passed all engines, also with cleveref. Wiseref does not silently
disable this kernel hook. The snippet applies before amsthm is loaded; class-level
first-aid hooks in AMS classes are a separate configuration, not covered by it.

**Tagged PDF:** the focused fixture contains actual `/StructTreeRoot` data and
valid normal/structural links and passed LuaLaTeX and pdfLaTeX. The comprehensive
fixture still fails without wiseref with `The number of automatic begin (13) and
end (12) text-unit para hooks differ`. Full tagged-PDF interoperability is therefore
not established. No tagging errors are suppressed.

## Reproduction and provenance

```sh
make sty
python3 test/packages.py --work /tmp/wiseref-packages
# Focused Unicode math test:
python3 test/packages.py --work /tmp/wiseref-unicode \
  --cases unicode-lm-before unicode-lm-after \
          unicode-termes-before unicode-termes-after unicode-mathtools
```

Work directories must not exist. No packages are installed or downloaded.
The command exits nonzero for a blocked baseline or regression; `LIMITATION`
means the documented fallback or explicit configuration was verified.
Minted fixtures use restricted shell escape with the TeX Live-approved
`latexminted` executable. Biblatex fixtures actually invoke Biber and check the
rendered citations/bibliography. `--biber /path/to/biber` selects its executable.
Use `--suite portable|external|extras|tagging|all` to select a group, or `--engines`
to restrict engines. An unknown name or empty selection is an error.
`--allow-known-baselines` accepts only a manifest-listed error in the unloaded
baseline and records it separately; it does not excuse any wiseref regression.
On this Mac, the installed universal Biber launcher failed while thinning itself;
tests used an arm64 copy extracted with lipo into the temporary directory. The
installed executable was not modified. Biber was version 2.21.

`packages-cases.json` records scenarios. `results.json` records the candidate
SHA-256, package version banners, outputs, assertions and failure logs. The
counts above describe the run on 2026-10-09. A new run writes its results and
logs to the chosen work directory; rerun it to check a different candidate.

These are representative integrations, not every package-option combination.
Other bibliography/highlighting styles, full tagged-PDF
combinations, custom classes and older distributions need their own verification.
