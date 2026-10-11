-- Copyright (C) 2026 Junhao Wu. LPPL 1.3c or later; see LICENSE.
-- Standard unpack/doc/install/ctan targets. Regression suites use make check.
module = "wiseref"

-- l3build takes full-install documentation from docfiledir, including textfiles.
-- Stage first, and use that controlled tree for every packaging source.
local errorlevel = os.execute("python3 test/release.py --stage build/release-source")
assert(errorlevel == 0, "Failed to stage release sources")
sourcefiledir = "build/release-source"
docfiledir = sourcefiledir
textfiledir = sourcefiledir

sourcefiles = {"wiseref.dtx", "wiseref.ins", "build.lua"}
installfiles = {"wiseref.sty"}
unpackfiles = {"wiseref.ins"}
unpackexe = "xetex"
unpackopts = "-interaction=nonstopmode -halt-on-error"

typesetfiles = {"wiseref-en.tex", "wiseref-zh.tex"}
typesetsourcefiles = typesetfiles
typesetexe = "lualatex"
typesetopts = "-interaction=nonstopmode -halt-on-error -no-shell-escape"
typesetruns = 3
typesetwarnings = true
demofiles = {"wiseref-example-en.tex", "wiseref-example-zh.tex"}

-- Only the controlled source copy is packaged, never test/output or caches.
textfiles = {"README.md", "LICENSE", "Makefile", "test"}
ctanreadme = "README.md"
excludefiles = {"*~", "config-*.lua"}
binaryfiles = {"*.pdf", "*.zip"}
packtdszip = true

local file = assert(io.open("wiseref.dtx", "r"))
local source = file:read("*a")
file:close()
local date, version = source:match("\\ProvidesExplPackage{wiseref}{([^}]+)}{([^}]+)}")
assert(date and version, "Missing wiseref package version")

uploadconfig = {
  pkg = "wiseref",
  author = "Junhao Wu",
  uploader = "Junhao Wu",
  email = "andrew.junhao.wu@gmail.com",
  summary = "Cross-references with configurable type names, affixes, and number formats",
  license = "lppl1.3c",
  version = "v" .. version .. " " .. date:gsub("/", "-"),
  ctanPath = "/macros/latex/contrib/wiseref",
  home = "https://github.com/hithesis/wiseref",
  repository = "https://github.com/hithesis/wiseref",
  bugtracker = "https://github.com/hithesis/wiseref/issues",
  description = [[
    Wiseref formats references to one or more labels, with per-type affixes,
    number formats, built-in language profiles, optional sorting and ranges,
    and selectable hyperlink scope. It supports pdfLaTeX, XeLaTeX, and LuaLaTeX.
  ]],
  update = false,
}
