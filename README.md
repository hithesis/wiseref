# wiseref

Version v1.2026a (2026-10-10)

Wiseref adds type names to cross-references and formats lists of labels.
Use `\wref{picture}` in place of `Figure~\ref{picture}`, then set names,
number formats, separators, and links through `\wiserefsetup`.
Prefix and suffix arguments can override the wording for a single call.

Author and maintainer: Junhao Wu <andrew.junhao.wu@gmail.com>

Source: <https://github.com/hithesis/wiseref>

Bug reports: <https://github.com/hithesis/wiseref/issues>

Copyright 2026 Junhao Wu. Distributed under the
[LaTeX Project Public License](https://www.latex-project.org/lppl/), version
1.3c or later, with maintenance status `maintained`. See [LICENSE](LICENSE).

LaTeX 2023-06-01 or later is required. LuaLaTeX, XeLaTeX, and pdfLaTeX are
supported; hyperref is optional. Wiseref requires no special fonts, CJK backend,
or external executable at runtime. It does not depend on cleveref.

Hyperref's `\autoref`, cleveref, and zref-clever also add type names.
Wiseref uses a prefix/suffix interface with separate number formats.
Special counters may need settings or adapters; the document supplies fonts,
text direction, and any grammatical inflection.

## Source and manual

`wiseref.dtx` is the source of both the package and its manuals.
`wiseref.ins` extracts the package with docstrip. `wiseref-en.tex` and
`wiseref-zh.tex` are small language-specific entry points using the shared driver
and content in the dtx. `wiseref.sty`, `wiseref-en.pdf`, and `wiseref-zh.pdf` are
generated files; edit the dtx instead.

```sh
make sty   # Extract wiseref.sty with xetex wiseref.ins
make doc   # Build both language editions
make doc-en # Build the English manual, wiseref-en.pdf
make doc-zh # Build the Chinese manual, wiseref-zh.pdf
make check-doc # Check the rendered examples and their PDF links
make check # Run the standard regression suites
make ctan # Build and verify dist/wiseref-v1.2026a.zip
make check-examples # Compile the shipped examples using the TDS installation
```

XeTeX extraction preserves the UTF-8 strings in the language profiles.
The English and Chinese manuals are separate PDFs with the same sections and API
coverage. Both use ltxdoc, Latin Modern, listings, and LuaLaTeX. The Chinese
edition also uses ctex in plain scheme and Fandol; the English edition does not
load a CJK backend. These Chinese font dependencies are only for building the
Chinese manual. Without make, run `xetex wiseref.ins`, then
`latexmk -lualatex wiseref-en.tex` and `latexmk -lualatex wiseref-zh.tex`.

Examples in the manuals execute the displayed commands. Their links lead to
numbered demonstration objects. See [manual design](test/MANUAL-DESIGN.md)
for the layout reference and output checks.

`wiseref.sty` is the only runtime file. The `.tex` entry points are documentation
sources; files under `test/` are development tools, fixtures, and reports.
The unpacked CTAN directory includes both PDFs and their sources, but omits the
generated `.sty`, TeX intermediate files, and local caches. `make ctan` uses
`l3build ctan`, checks its contents and TDS layout, and rebuilds both manuals
from the unpacked archive. The generated `.sty` appears only in the TDS install
tree. Verified assets in `dist/` have stable names: `wiseref-ctan.zip`,
`wiseref.tds.zip`, the versioned upload ZIP, and `SHA256SUMS`.

`build.lua` also supplies `l3build unpack`, `l3build doc`, and `l3build install`.
These targets use Python 3 to stage a controlled source tree; the direct XeTeX
extraction and latexmk commands above do not need Python. PDF verification
additionally needs pypdf/pypdfium2. Regression tests are run by `make check`.

[English](wiseref-example-en.tex) and [Chinese](wiseref-example-zh.tex) examples
are complete documents. The English example works with all three engines;
the Chinese example uses XeLaTeX or LuaLaTeX with Fandol. `make check-examples`
loads wiseref from a temporary TEXMF tree extracted from `wiseref.tds.zip`,
so it tests the installable package rather than a `.sty` beside the document.

## Quick start

Place the generated `wiseref.sty` beside the main document, or install it
in a local TEXMF tree. Load hyperref near the end of the package list, subject
to any package-specific ordering requirements. Both amsmath and hyperref may
be loaded before or after wiseref.

```latex
\usepackage{amsmath}  % If needed
\usepackage{wiseref}
\usepackage{hyperref} % Optional: load near the end of the package list

See \wref{structure}.
\wref[Photo~]{structure}
\wref{chapter}[.]
\wref*{structure}
```

Use ordinary `\label` commands. Label names are arbitrary: no `fig:` or
`eq:` naming convention is required. Compile at least twice, or use latexmk.
`lang=auto` is the default. It follows the current babel or polyglossia language,
including local switches, and inherits existing document names. Without a
language manager it selects Chinese when a ctex Chinese scheme is loaded,
otherwise it uses the English fallback. Built-in profiles cover English
(`en`), Chinese (`zh`), French (`fr`), German (`de`), Spanish (`es`), Portuguese
(`pt`), Italian (`it`), Dutch (`nl`), Russian (`ru`), Greek (`el`), Japanese (`ja`),
and Arabic (`ar`). Full language names and common Babel regional aliases are
accepted. These languages require no user profile registration. Fonts, script
support, and text direction remain the document's responsibility.

Default ctex documents need no additional language setup:

```latex
\documentclass{ctexart} % Also ctexbook or ctexrep
\usepackage{wiseref}   % lang=auto selects Chinese
```

This also works with `\usepackage{ctex}`, including loading ctex after wiseref.
`scheme=plain` alone retains the English fallback. Detection uses LaTeX's
loaded-file information for ctex's Chinese scheme, without reading private ctex
variables. Babel/polyglossia language switches and an explicit `lang` selection
have higher priority. Renaming captions does not change the detected language.

## Configuration

Pass settings to `\wiserefsetup` after loading the package, not as `\usepackage`
options. Values containing commas need braces. The language-edition manuals
describe every accepted general/type key; see the maintained
[user-interface coverage audit](test/MANUAL-COVERAGE.md).

```latex
\wiserefsetup{
  lang=en,
  figure={prefix={Photo~},prefix-plural={Photos~},suffix={}},
  equation={prefix={Eq.~},suffix={},number-format={\textup{(#1)}}},
  sort=false, compress=false,
  links=numbers-and-affixes,
}
```

`\wref[prefix]{label list}[suffix]` overrides affixes for one call.
Omitted arguments inherit the settings; empty arguments clear the corresponding
affix. The starred form suppresses links. Equation parentheses belong to the
number format, so clearing affixes does not remove them.

`links` selects which text carries hyperlinks:

| Value | Numbers | Prefix and suffix |
| --- | --- | --- |
| `none` | No links | No links |
| `numbers` | Linked | No links |
| `numbers-and-affixes` (default) | Linked | Linked |

Each number links to its own target. In `numbers-and-affixes` mode, the prefix
links to the first target and the suffix to the last. Connectors remain unlinked.
Without hyperref, all modes produce plain text. `\wref*` suppresses links for
that call without changing the configured mode. `links` replaces the previous
`link`, `link-affixes`, and `name-in-link` keys.

Input order is preserved by default, with adjacent targets of the same type
forming a group. Sorting and compression
must be enabled explicitly; custom tags and alphabetic sublabels are not
compressed as numeric ranges. Settings inside a TeX group remain local.
See `wiseref-en.pdf` or `wiseref-zh.pdf` for all options and examples.

Changing `lang` does not overwrite explicit formats or connectors. Auto mode
reads names such as `\figurename` and `\tablename` at each reference. A renamed
document term has no automatically invented plural; configure it explicitly if
needed. `use-document-name=false` disables document-name inheritance for a type
in auto mode; it keeps profile affixes and any explicit settings. The default
is `true`. Explicit `lang` selections use profile names regardless of this switch.

To put the current document name after the number, set the affixes directly:

```latex
\wiserefsetup{figure={prefix={},suffix={~\figurename}}}
```

Clear both affixes to print only numbers. The former `name-position` key is
no longer accepted; there is no separate position option.

Type names normally follow the target's counter name. They are configuration
identifiers, not printed names or label-name prefixes. The type registry is open:
packages using standard numbered targets and labels generally work directly,
while additional counters may need explicit affixes. For example, listings uses
`lstlisting`, minted's float uses `listing`, algorithm uses `algorithm`, and
algorithm2e uses `algocf`. Creating a counter alone is insufficient; establish a
reference with `\refstepcounter` and `\label`:

```latex
\newcounter{experiment}
\wiserefsetup{experiment={prefix={Experiment~},suffix={}}}
\refstepcounter{experiment}\label{exp:first}
See \wref{exp:first}.
```

Custom environments or nonstandard label mechanisms may require `\wisereftype`
or an adapter. The middle field of `\wiserefRecord{label}{type}{mode}` in the aux
file identifies the recorded type. Setting its format does not reclassify labels.

```latex
\wiserefsetup{
  langs={french={
    figure={prefix={Figure~},prefix-plural={Figures~}},
    table={prefix={Tableau~},prefix-plural={Tableaux~}},
    number-last-separator={~et~},group-last-separator={~et~},
  }},
  lang-aliases={fr=french},
  lang=auto,
}
```

The example updates the built-in French profile without resetting its other fields. A new
partial profile uses the English fallback for unspecified fields. In auto mode,
inherited document names outrank profile names, and
explicit setup values outrank both. Declarations and aliases are local to a TeX
group. A missing explicit profile is an error; an unknown document language
warns once and uses the fallback. The old `language` option is not supported.

Defaults use standalone singular/plural names. They do not automatically inflect
grammatical case or select Arabic dual forms; use explicit affixes when the
surrounding sentence requires them. French defaults use `Table`/`Tables`, and
Spanish defaults use `Cuadro`/`Cuadros`; inherited caption names and user settings
can select other terms. Names and connectors were checked against the language
data of zref-clever, cleveref, Babel, and polyglossia; none is a runtime dependency
of wiseref.

## Development and tests

GitHub Actions runs three-engine regressions and portable package interactions
on pinned TeX Live 2023, 2024, 2025, and 2026 images. Weekly/tagged/manual jobs
also test the complete package matrix, real CTAN classes, and a rolling latest
distribution. Workflow validation, manual/link checks, clean archive builds,
English summaries, and failure artifacts are included. See [CI](test/CI.md)
for triggers, environment pins, and the known-baseline failure policy.

`make check-doc` checks source extraction, rendered examples, and PDF links.
`make check` runs the standard reference, lifecycle, language, and ctex suites.
Tests require Python 3, pypdf, pypdfium2, and the relevant TeX tools.
Installation and manual compilation do not require Python.

See [test instructions](test/TESTING.md) for individual commands and optional
integration suites. Historical TeX Live 2026 runs passed 57 class/language
combinations; the package-interaction run passed 101 of 103 cases, with two
tagged-PDF baselines failing without wiseref. These results apply to the versions
and configurations in the [class report](test/CTAN-COMPATIBILITY.md) and
[package report](test/PACKAGE-COMPATIBILITY.md).

This is an unpublished release candidate. The CTAN upload notes and file checks
are recorded in [the release audit](test/CTAN-RELEASE.md).
