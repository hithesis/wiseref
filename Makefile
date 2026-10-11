PACKAGE = wiseref

.PHONY: all sty doc doc-en doc-zh check check-doc ctan check-examples
all: doc

sty: $(PACKAGE).sty
$(PACKAGE).sty: $(PACKAGE).dtx $(PACKAGE).ins
	xetex -interaction=nonstopmode -halt-on-error $(PACKAGE).ins

doc: doc-en doc-zh
doc-en: $(PACKAGE)-en.pdf
doc-zh: $(PACKAGE)-zh.pdf
$(PACKAGE)-en.pdf: $(PACKAGE)-en.tex $(PACKAGE).dtx $(PACKAGE).sty
	latexmk -lualatex -interaction=nonstopmode -halt-on-error $(PACKAGE)-en.tex
$(PACKAGE)-zh.pdf: $(PACKAGE)-zh.tex $(PACKAGE).dtx $(PACKAGE).sty
	latexmk -lualatex -interaction=nonstopmode -halt-on-error $(PACKAGE)-zh.tex

check-doc: doc
	python3 test/check-build.py
	python3 test/manual-output.py

ctan:
	l3build ctan
	python3 test/check-build.py --sty build/unpacked/wiseref.sty
	python3 test/manual-output.py --root build/doc
	$(MAKE) sty
	python3 test/release.py --documents build/doc

check-examples:
	python3 test/examples.py --tds wiseref.tds.zip --work test/output/examples-$$(date +%Y%m%d-%H%M%S)

check: sty
	python3 test/check-build.py
	python3 test/run.py --work test/output/references-$$(date +%Y%m%d-%H%M%S)
	python3 test/lifecycle.py --work test/output/lifecycle-$$(date +%Y%m%d-%H%M%S)
	python3 test/langs.py --work test/output/langs-$$(date +%Y%m%d-%H%M%S)
	python3 test/builtins.py --work test/output/builtins-$$(date +%Y%m%d-%H%M%S)
	python3 test/ctex.py --work test/output/ctex-$$(date +%Y%m%d-%H%M%S)
