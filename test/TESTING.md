# Building and testing wiseref

Run commands from the package directory. `make sty` extracts the runtime file;
`make doc` builds both manuals with LuaLaTeX. The Chinese manual uses ctex's
plain scheme and Fandol; the English manual uses Latin Modern without a CJK
backend. All fonts used by the manuals are distributed with TeX Live.

The driver also uses ltxdoc, geometry, amsmath, booktabs, listings, xcolor,
caption, titlesec, fancyhdr, enumitem, and hyperref. These are documentation
dependencies, not wiseref runtime dependencies.

## Standard suites

Tests need Python 3.10 or later, pypdf, pypdfium2, and the TeX engines used
by each suite. `make check` runs these commands with timestamped work directories:

```sh
make sty
python3 test/run.py --work /tmp/wiseref-tests
python3 test/lifecycle.py --work /tmp/wiseref-lifecycle
python3 test/langs.py --work /tmp/wiseref-langs
python3 test/builtins.py --work /tmp/wiseref-builtins
python3 test/ctex.py --work /tmp/wiseref-ctex
```

Work directories must not already exist.

CI dependencies, including PyYAML for workflow/policy checks, are pinned in
[requirements-ci.txt](requirements-ci.txt). See [CI.md](CI.md) for the multi-release
matrix, scheduled integrations, summaries, and artifact retention.

- `run.py`: 36 standard-class combinations compare labels, PDF text, character
  positions, and links with and without wiseref. Six API combinations check 34
  outputs, all three link modes, starred calls, and group restoration.
- `lifecycle.py`: amsmath loading order, auxiliary-file convergence, and removal
  of wiseref while retaining the existing aux file.
- `langs.py`: eight combinations test Babel/polyglossia, document names, custom
  profiles, aliases, and explicit-setting precedence. Document-name switches
  are checked at profile/setup level, through nested groups and with unusable
  name commands. Suffix examples test dynamic names and explicit plurals.
  An ASCII-affix fixture checks Japanese heading-name placement without CJK fonts.
- `builtins.py`: five combinations test the six Latin-script profiles,
  singular/plural names, ranges, local switches, and 30 aliases. The Lua
  polyglossia Portuguese local-switch check is skipped if `luavlna` is absent;
  explicit Portuguese and the other manager/engine checks still run.
- `ctex.py`: 44 combinations test three engines, Chinese/plain schemes, class
  and package loading order, heading mode, pre-class loading, and manager
  precedence. Unicode engines use Fandol; pdfLaTeX uses `fontset=none` with
  distributed Arphic Type 1 CJK fonts. These fonts belong to the fixtures.
  Renamed figures and headings also check `use-document-name` off/on behavior.

`make check-doc` verifies source extraction and 21 live results in each manual.
It checks actual PDF link annotations, first/last destinations, equation-tag
targets, and absence of links on starred calls. Layout, font, rerun, and
duplicate-destination warnings fail the check.

## Optional integration suites

```sh
python3 test/ctan.py --download \
  --cache /tmp/wiseref-ctan-cache --work /tmp/wiseref-ctan-results
python3 test/packages.py --work /tmp/wiseref-packages
```

The class suite downloads missing class sources and test fonts into its cache.
It does not install them into the TeX tree. The package suite uses installed
packages, Biber for bibliography fixtures, and restricted shell escape with
`latexminted` for highlighting. Use `--biber /path/to/biber` to select a working
backend. A blocked ordinary baseline produces a nonzero exit status.

The package runner also accepts `--suite portable|external|extras|tagging|all`
and `--engines`. `--allow-known-baselines` recognizes only the documented
comprehensive tagging error in its unloaded baseline; it never marks it as a
pass. Unknown or empty case selections are errors in both integration runners.

The recorded runs used TeX Live 2026. See [class compatibility](CTAN-COMPATIBILITY.md)
and [package compatibility](PACKAGE-COMPATIBILITY.md) for the dated results,
configuration requirements, and untested cases. Standalone tests reject other
automatic-reference packages; interaction tests load the packages they compare.

## CTAN archive

`make ctan` runs `l3build ctan`, verifies the manuals in `build/doc`, checks the
CTAN and TDS file lists, and rebuilds the manuals in a temporary directory using
only the archive's contents. The archive has a `wiseref/` source root and an
optional sibling `wiseref.tds.zip`. Tests and reports remain under `test/` in
the source root; generated results and local caches are excluded.

`test/release.py` uses only the Python standard library for packing; its clean
build invokes `make check-doc`, which needs the PDF libraries listed above.
All Python scripts here are development tools, not installed runtime commands.

`make check-examples` extracts the TDS archive into an isolated TEXMFHOME and
compiles the included English example with Lua/Xe/pdf engines and the Chinese
example with Lua/Xe engines. It checks the resolved runtime path, eight actual
outputs per build, valid link destinations, and the unlinked starred reference.
