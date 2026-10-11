# Continuous integration

All workflow names, step names, comments, and summary text are in English.
Multilingual reference strings remain in their original languages.

## Pull requests and pushes

The `CI` workflow runs on pull requests, pushes to `main`, version tags starting
with `v`, and manual dispatches.

| Job | Environment | Checks |
| --- | --- | --- |
| Workflow and test-policy checks | Python 3.12, actionlint 1.7.12 | Workflow syntax, Python syntax, case selection, result classification, and summary behavior |
| TeX Live compatibility | TL 2023, 2024, 2025, 2026 | Source extraction, standard/API/lifecycle tests, languages, ctex, and portable package interactions |
| Manuals, archives, and installed examples | Pinned TL 2026 | Both manuals, 21 live outputs/links per edition, CTAN/TDS contents, a clean rebuild, and five example builds from an isolated installation |

Each TeX Live job uses LuaLaTeX, XeLaTeX, and pdfLaTeX where supported by the
fixture. The core suites contain 102 configurations; the portable package suite
adds 78. It includes unicode-math with two fonts, mathtools/showonlyrefs,
cleveref/varioref/zref-clever, theorem packages, captions, lists, code listings,
algorithms, and theorem boxes. Jobs run independently with `fail-fast: false`.
The final `CI passed` job succeeds only when lint, all compatibility jobs, and
documentation succeed. Use that stable job name for a required branch check.
Version-tag runs also check that the tag matches the version declared in the dtx.

The historic releases are final TeX Live snapshots, not tests of every kernel
update during each year. In particular, the TL 2023 snapshot does not establish
support for the exact LaTeX 2023-06-01 minimum. Older package APIs and fonts may
expose real incompatibilities: these jobs fail rather than silently substituting
current packages or changing the expected reference output.

## Weekly, tagged, and manually triggered checks

`Extended compatibility` runs every Monday at 03:41 UTC, on `v*` tags, and on
manual dispatch.

- A pinned TL 2026 job runs all 103 package combinations, including external
  references, actual Biber bibliographies, minted highlighting, and tagged PDF.
- A rolling `texlive/texlive:latest` job repeats the core and complete package
  matrices to detect changes in upstream TeX distributions and packages.
- A pinned TL 2026 class job runs the 57 real-class/language combinations.
  Classes include KOMA-Script, memoir, AMS, beamer, ctex, Japanese classes,
  IEEEtran, elsarticle, REVTeX, acmart, and abntex2. Twelve language profiles are
  exercised with actual fonts and reference output.

Newer external record-property/XR interfaces, minted's restricted-shell helper,
and the tagging fixture are tested with current distributions. They are not
assumed to exist in old snapshots. The portable suite excludes these scenarios
explicitly; the full matrix keeps them. No job enables unrestricted shell escape.

The CTAN class job downloads current class archives on each run. Only fonts are
cached. Greek/Cyrillic fixtures use DejaVu Serif from CTAN rather than Times New
Roman. Downloaded classes/fonts are isolated and never installed into the TeX tree.

## Failure policy

A compilation error, wrong output, wrong type, broken link, altered ordinary
reference, missing glyph, or nonconvergent aux file fails its test. An unknown
case name or an empty selection fails before any builds. CTAN baseline blockers
also produce a nonzero exit status.

The comprehensive tagged-PDF baseline has one documented kernel error:
automatic begin `(13)` and end `(12)` text-unit paragraph hooks differ. Full CI
uses `--allow-known-baselines` to recognize only this manifest-listed error,
only before wiseref is loaded. It is recorded as `KNOWN_BASELINE_FAILURE`, not
`PASS`. A different error, an error after loading wiseref, or a failure in the
basic tagged-PDF fixture remains a job failure. There is no `continue-on-error`.
If the baseline is fixed upstream, the test proceeds to wiseref checks normally.

## Toolchain and artifacts

Stable images are pinned by digest. They were checked against the
[Island of TeX registry](https://hub.docker.com/r/texlive/texlive/tags) and
[xu-cheng's TeX Live images](https://github.com/xu-cheng/latex-docker) on
2026-10-10. Do not run `tlmgr update --all` in historic jobs: that would change
the environment being tested. Review the digest pins periodically.

`ci-environment.py` verifies the engine years and records the image, Python/PDF
library versions, engine banners, Biber/minted versions, source hash, and commit
SHA. A compiled probe also records the LaTeX kernel date, expl3 date, and
availability of the record-property interface. Python dependencies are pinned in
[requirements-ci.txt](requirements-ci.txt).
All three formats are initialized serially before parallel test builds, avoiding
first-use format-generation races in historic images. Their kernel dates must agree.
The container uses a virtual environment with system packages visible so TeX
Live's bundled helpers can still use their dependencies.

Each test job writes an English table with separate counts for passes, failures,
blocked baselines, known baseline failures, limitations, and skipped checks.
Logs, JSON results, generated fixture sources, and package snapshots are uploaded
even if a test step fails. PDFs and the verified CTAN ZIP have a separate artifact.
The packaging job uses `l3build ctan` and publishes stable artifact filenames:
`wiseref-ctan.zip`, `wiseref.tds.zip`, the versioned upload ZIP, and `SHA256SUMS`.
English examples run with all three engines; Chinese examples run with Lua/Xe.
Their runtime file must resolve inside the extracted TDS tree. Actual output and
starred-reference link suppression are checked, as well as successful compilation.

## Upstream workflow references

The standard build and example checks take cues from Yanshuo Chu's recent
commits on the upstream master branch:

- [6c36467](https://github.com/hithesis/hithesis/commit/6c36467a8c481f69589139261f5bdc9cc9f27272): build documentation and CTAN archives with l3build.
- [6444673](https://github.com/hithesis/hithesis/commit/64446730b3c2c2f8d683ec85e97c0c43dddff548): keep generated files, hidden files, and duplicate example copies out of the upload.
- [4b15e1d](https://github.com/hithesis/hithesis/commit/4b15e1de5f24217c1a9d56f2d97580c7576e9e15): extract runtime files separately from preparing example trees.
- [e1c69d9](https://github.com/hithesis/hithesis/commit/e1c69d9daf36a5908ee03986056dc5036f93ce48): prepare runnable examples before compiling them in CI.

Wiseref's source staging and archive checker enforce the corresponding file
rules. Documentation sources/test helpers stay in the doc/source trees; only
`wiseref.sty` is installed in `tex/latex/wiseref`. The multi-release matrix and
PDF/type/link assertions remain specific to this package.

Local equivalents:

```sh
python3 -m pip install -r test/requirements-ci.txt
python3 test/test-ci.py
make check
python3 test/packages.py --suite portable --work /tmp/wiseref-portable
python3 test/packages.py --suite all --allow-known-baselines --work /tmp/wiseref-full
make ctan
make check-examples
```

Workflow YAML and local test-policy checks can be validated without Docker.
Recorded results apply to the tested commit and environment; a code fix still
needs a new hosted run to establish the full matrix result.

Local checks on 2026-10-10 passed actionlint, nine CI-policy tests, Python syntax,
the 78-case portable suite, the four Greek/Russian DejaVu cases, and all three
lifecycle cases. Tagging produced two basic passes and two matching known
baseline failures. These checks preceded the first hosted historic-image run.

## First hosted run and compatibility fixes

[Run 38110108326](https://github.com/hithesis/wiseref/actions/runs/38110108326)
passed the TL 2026 core/portable suites and workflow checks. It exposed three
issues: archive PDF validation used the source-root path instead of `build/doc`,
TL 2023 lacked convenience conditionals used by the package, and shared theorem
counters lost the environment type on earlier kernels. The archive reader now
validates the actual PDF location. Package/property checks use the supported TF
forms; old file-load checks read the same LaTeX version record as the newer API.
Signature-checked theorem hooks retain environment types and handle cleveref's
dispatcher and thmtools restatable wrappers without altering standard numbering.

Local reproduction uses clean source copies and isolated Linux containers.
The exact CI TL 2023 image passed the 36 observation cases and six API cases
after the fixes. Supplemental historic snapshots exercised language/ctex and
theorem-package scenarios. ARM-host amd64 emulation also produced transient
engine crashes; these are not treated as passes or suppressed in hosted CI.
