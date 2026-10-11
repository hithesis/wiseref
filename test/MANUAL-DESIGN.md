# Manual layout and executable results

The visual reference is zhlipsum v1.2.0, which provides separate official
[English](https://mirrors.ctan.org/macros/latex/contrib/zhlipsum/zhlipsum-en.pdf)
and [Chinese](https://mirrors.ctan.org/macros/latex/contrib/zhlipsum/zhlipsum.pdf)
manuals. Its marginal command signatures, numbered framed examples and restrained
spacing are useful for a compact API guide. Wiseref's driver is independently
implemented; zhlipsum is not a build or runtime dependency.

The manuals retain ltxdoc marginal command descriptions and add consistent sans
headings, muted accent colors, running section heads, padded code panels and
numbered code/result examples. Colored text shows actual hyperlink scope.

All example results execute wiseref. The command/output table has no transcribed
output column. The manuals build real targets with captions, amsmath displays,
refstepcounter and labels, and include a target page that the links reach. A
dedicated counter supplies the chapter example in the article-class manual.
Nothing fabricates newlabel records or renders an expected-result string in place
of calling wref.

`test/manual-output.py` reads the rendered PDF line at each named example anchor,
checks both language editions, and validates numbers/affixes against the actual
PDF link annotations and first/last figure destinations. The displayed code and
live result share the same command tokens; output settings are locally grouped.
Tagged and unparenthesized equation examples must reach distinct destinations.
The checker also rejects duplicate-destination warnings and layout/font warnings.

Run `make check-doc` after rebuilding the manuals. Runtime package source remains
inside the dtx's package guard; the visual driver and fixtures are manual-only.
