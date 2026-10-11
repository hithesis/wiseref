# CTAN release audit (2026-10-10)

Release candidate: **v1.2026a**, dated **2026-10-10**.
Author and maintainer: Junhao Wu, <andrew.junhao.wu@gmail.com>.
Source repository: <https://github.com/hithesis/wiseref>.

The current interface uses the per-type `use-document-name=true|false` switch.
The former `name-position` option is removed; names can be placed explicitly
with `prefix` and `suffix`. The standard suites passed after the change,
including document-name precedence, nested groups, unusable names, Japanese
heading placement with ASCII affixes, and 44 ctex combinations with renamed
figures/headings. A further 33 package-interaction combinations passed.

## Requirements checked

The archive follows CTAN's [upload basics](https://ctan.org/help/upload-pkg)
and [upload addendum](https://ctan.org/file/help/ctan/CTAN-upload-addendum),
and the [TeX Live contribution instructions](https://tug.org/texlive/pkgcontrib.html).

| Item | Package arrangement |
| --- | --- |
| Package ID and runtime filename | `wiseref`, with one generated runtime file, `wiseref.sty` |
| Version | Package declaration, README, and both manuals use v1.2026a / 2026-10-10 |
| License | LPPL 1.3c or later; maintenance status `maintained`; Junhao Wu named as maintainer |
| License manifest | LICENSE names the source files, test material, and both derived manuals |
| README | English, UTF-8 without BOM, at the package root; purpose, requirements, contact, license, and build instructions |
| Documentation | Separate English and Chinese PDFs with shared dtx source and two entry points |
| Extraction | `xetex wiseref.ins` generates the runtime file without building documentation |
| Fonts and dependencies | No font or script runtime dependency; manual fonts come from TeX Live |
| Archive layout | `wiseref/` source root plus the optional sibling `wiseref.tds.zip`; core files at top level, test sources under `test/` |
| Generated files | PDFs included; generated `wiseref.sty` only in TDS, no TeX intermediates, results, or caches |
| Filenames and permissions | ASCII names without spaces or shell metacharacters; no hidden files; regular world-readable files |
| Standard builder | l3build unpack/doc/install/ctan; controlled source staging excludes caches and generated tests |
| TDS | Only `wiseref.sty` in `tex/latex/wiseref`; manuals/examples/helpers under doc, dtx/ins/build.lua under source |
| Rebuild | Unpack into a temporary directory, delete the PDFs, and run `make check-doc` using only archived sources |
| Installed examples | Five engine/language builds load the runtime from an isolated TDS tree and check real outputs/links |

Python tools and fixture `.tex` files under `test/` are development material;
they are not runtime executables or files to install in the runtime TeX tree.
`wiseref-probe.sty` is handwritten test source, not a docstrip-generated file.
No third-party classes, fonts, or downloaded archives are bundled.
GitHub workflow/action files under `.github/` are repository-only infrastructure
and are excluded from the upload. The English CI guide, Python helpers, and
dependency list under `test/` are included. Workflow-specific unit checks are
skipped when running from a CTAN archive that has no `.github/` directory.

## Build the upload

```sh
make ctan
```

This builds with `l3build ctan`, then produces `dist/wiseref-v1.2026a.zip`,
`dist/wiseref-ctan.zip`, `dist/wiseref.tds.zip`, and `dist/SHA256SUMS`.
An isolated-build log is stored alongside the versioned archive.
`test/release.py` checks filenames, duplicate basenames ignoring case, nonempty
files, UTF-8/LF text, local Markdown links, and matching dates/versions. ZIP file
permissions are normalized to 0644. A clean build checks extraction, both manuals,
and 21 live outputs and PDF link scopes per edition. Exact CTAN/TDS contents are
also required, preventing generated core files in the source upload and test
helpers in the runtime tree. The command reports the ZIP's
SHA-256 and only writes the upload archive after the clean build succeeds.

The archive contains:

```text
wiseref/
  LICENSE
  Makefile
  README.md
  build.lua
  wiseref.dtx
  wiseref.ins
  wiseref-en.tex
  wiseref-en.pdf
  wiseref-zh.tex
  wiseref-zh.pdf
  wiseref-example-en.tex
  wiseref-example-zh.tex
  test/                  # Scripts, fixtures, and reports; no generated results
wiseref.tds.zip           # Optional standard installation tree
```

## Upload form

Suggested entries for the [CTAN upload form](https://ctan.org/upload):

- Package: `wiseref`
- Version: `v1.2026a 2026-10-10`
- Author / uploader: `Junhao Wu`
- Email: `andrew.junhao.wu@gmail.com`
- License: `lppl1.3c` (the files allow this or later versions)
- Suggested CTAN directory: `/macros/latex/contrib/wiseref`
- Summary: `Cross-references with configurable type names, affixes, and number formats`
- Home page / repository: `https://github.com/hithesis/wiseref`
- Bug tracker: `https://github.com/hithesis/wiseref/issues`

Suggested description:

> Wiseref formats cross-references to one or more labels. It reads object types
> from label records and provides per-type prefix, suffix, and number formats.
> Lists support grouping, optional sorting and range compression, and selectable
> hyperlink scope. Built-in language profiles follow Babel, polyglossia, or ctex,
> with settings that can override the defaults. The package works with pdfLaTeX,
> XeLaTeX, and LuaLaTeX and requires LaTeX 2023-06-01 or later.

Suggested administrative note:

> The only runtime file is wiseref.sty, generated with xetex wiseref.ins.
> It is omitted from the unpacked source directory and included only in the
> optional wiseref.tds.zip installation archive.
> The four top-level .tex files are manuals/examples; test/ contains development
> material only. Both manuals were built with LuaLaTeX.

The CTAN catalogue API returned 404 for `wiseref` on 2026-10-10. This is a name
check, not a reservation or acceptance. The maintainer's repository URL is public,
but the repository was empty when checked and its About text still described an
older template-specific package. Publish the current sources and update that text
before presenting it as the source repository.
CTAN submission and TeX Live inclusion still require their normal
review; this audit does not claim either has happened.
