# User-manual coverage audit

The two manuals use the same documented source. This audit covers the accepted
wiseref user interface, not every TeX construction or every third-party package
option. Section names below identify the descriptions in both language editions.

| Interface | Covered in |
| --- | --- |
| `\wref[prefix]{labels}[suffix]`, omitted/empty arguments, mixed groups | Reference commands; Multiple and mixed references |
| `\wref*`, local link suppression | Reference commands; General options |
| `\wiserefsetup`, incremental settings, TeX grouping, package-load distinction | Configuration |
| `lang`, auto/babel/polyglossia/ctex, explicit selection, expandable selector | Configuration; Following the document |
| `langs`, partial profiles, updating built-ins | Adding or updating a language profile |
| `lang-aliases`, valid identifiers, case folding, forward aliases and cycle rejection | Adding or updating a language profile |
| `prefix`, `suffix`, per-type scope | Type-specific settings |
| `prefix-plural`, `suffix-plural`, singular-setter reset/order | Type-specific settings |
| `number-format`, raw `#1`, TeX macro escaping, bare-tag exception | Type-specific settings |
| `use-document-name=true/false`, default, auto-only scope, explicit affix precedence | Following the document; Type-specific settings |
| Placing a document name explicitly with `prefix`/`suffix`, dynamic macro and plural forms | Following the document |
| `links=none/numbers/numbers-and-affixes`, destinations, connectors | General options |
| `sort`, `compress`, input order, minimum run length, exclusions, repeated labels | Multiple and mixed references; Sorting and ranges |
| Six separator keys, defaults, examples, empty values, scope | General options |
| Built-in types, open registry, case-sensitive identifiers, reserved general keys | Type-specific settings |
| Third-party counter names, standard reference targets, custom-counter example | Counters supplied by other packages |
| `\wisereftype{type}`, group scope, `\wisereftype{}` | Numbering and compatibility |
| `\wiserefRecord{label}{type}{mode}` | Counters supplied by other packages; auxiliary-data inspection, not user formatting |
| amsmath tag/tag*, optional package order, ntheorem, external properties | Installation; Numbering and compatibility |
| External document prerequisites, prefix and loader example | Numbering and compatibility |
| Unsupported types, undefined/unnumbered labels, recompilation, package removal | Installation; Numbering and compatibility |
| PDF-safe heading text | Numbering and compatibility |
| Argument-taking names and unusable autoref macros | Numbering and compatibility |

The accepted separator keys are `number-separator`, `number-last-separator`,
`group-separator`, `group-last-separator`, `range-separator`, and `name-separator`.
The latter affects inherited prefix names, not literal affixes supplied by users.

Rejected historical keys (`language`, `link`, `link-affixes`, `name-in-link`, `name-position`) are
not alternative usages. The current interface is `lang` and `links`; README
documents migration of the former link switches and name-position option.

Compatibility reports state the tested versions and configurations. A manual
description does not establish universal compatibility, automatic support for
every new counter, or a statistical percentage of package coverage.
