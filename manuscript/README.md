# Revised manuscript sources

`main.tex`, `si.tex` and `references.bib` come from the final
`Overleaf_Review_Revision_Complete.zip` on the author's Desktop, directory
`Overleaf_Review_Revision/`. The archive SHA-256 is
`6b860694528797d471fbd1deb916d775ed1fa21f372f89318a577978e01e36e7`.
The two canonical documents use its `main_revision_highlighted.tex` and
`si_revision_highlighted.tex`; only figure paths were adjusted. Scientific text,
equations, tables, references and revision marks are unchanged.

In either preamble, change `\highlighttrue` to `\highlightfalse` and comment
the other switch to produce a clean version. Compile each document separately
from this directory with LuaLaTeX and BibTeX (`unsrtnat`), for example:

```bash
cd manuscript
lualatex main.tex
bibtex main
lualatex main.tex
lualatex main.tex
# Repeat with si.tex / si for the Supporting Information.
```

Existing tracked graphics are referenced in `../outputs/figures/`; the final
Fig. S19 is at `../outputs/figures/si/tsa_temperature/figS19_r1c5.pdf`.
`figures/` contains only the 15 indispensable original graphics absent from the
tracked repository (the flowsheet and SI S1-S14), copied byte-for-byte from the
archive. All tables are embedded in the two sources. SI equations S4-S7 retain
their working-capacity, inventory, productivity and regeneration-energy labels;
new validation/cleanup tables are S2/S3, and the new graphic remains S19.

The full Overleaf compilation bundle remains the separate handover archive.
Clean/highlight duplicates, response letter, reviewer correspondence, PI notes,
compiled documents and the ZIP are intentionally excluded here. Scientific
limitations and the unresolved PI decision are recorded in the root README and
the [numerical provenance note](../data/revision_validation/README.md).
