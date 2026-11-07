# Reviewer revision verification

Executed on 2026-11-07 from the repository root, with the existing local inputs.

| Check | Executed command or method | Result |
|---|---|---|
| Fig. S19 source-data recount/redraw | `python scripts/r1c5_minimal.py --output <external-temp>/figS19_redrawn.pdf` | Exit 0; 20,301 scenarios, 609,030 rows; original, ten fixed set-points and per-material optimization each give Cu-TDPAT 4,640 / Zeolite 13X 15,661 / HKUST-1 0; 0/203,010 changed fixed-temperature comparisons and 0/20,301 changed optimized winners. Existing local summary CSV also matched. |
| Git-only redraw | Same script's default command in an external temporary checkout containing only the two TSA scripts, tracked `TSA_DATA.csv`, `book1.csv` and `winner_map_data.csv` | Exit 0, same counts; no `tsa_temperature/` artifact CSV inputs required. |
| Figure identity | PyMuPDF raster comparison at 144 dpi, final archive figure versus both redraws | Exact pixel equality, 1037 x 497 pixels; visual inspection confirms the existing two-panel chart. The committed PDF remains byte-identical to the final archive. |
| Manuscript provenance | Byte comparison to highlighted main/SI archive members after only explicit `includegraphics` path substitutions; bibliography byte comparison; resolve every figure path | Exact match; all figures resolve. SI S4/S5/S6/S7 equation labels remain working capacity/inventory/productivity/energy; validation and cleanup tables remain S2/S3, base-case tables S4/S5, parameter tables S6-S10; final figure is S19. |
| Reference/cleanup evidence | `openpyxl` read-only checks of the five operating-basis cells and four gas-fraction cells listed in `data/revision_validation/README.md`; compare CSV percentages/differences; `pandas` read of `water.csv` Case 139 | All assertions passed, including SI S2 values and SI S3 component flows. Published composition and S/B basis checked in the supplied local Bassyouni PDF, abstract and article p. 697/Fig. 5. |
| Independent legacy audit | `python scripts/r1c5_independent_audit.py` | Exit 0; JSON `verdict_saved_winners` = `PASS`, reconciliation discrepancy list empty; three legacy workbooks each match 20,301 native rows and 304,515 cached scoring positions (913,545 total). Uses extra local inputs documented in the provenance note. |
| Existing smoke check | `python scripts/sanity_check.py` | Exit 0; 20,301/609,030 input rows, Cu-TDPAT 4,640 / Zeolite 13X 15,661 / HKUST-1 0; cached ML metrics inspected. Existing diagnostics flag narrow H2/CO2 variation and high cached R2 values; these are not suppressed or treated as new validation. |
| Local LaTeX compilation attempt | `lualatex --disable-installer -interaction=nonstopmode -halt-on-error ... main.tex` from `manuscript/` | Could not compile: local MiKTeX cannot build/find `lualatex.fmt`. No compilation PASS claimed; source/asset checks above passed. The separate handover ZIP retains its supplied compiled previews. |
| Staged scope and whitespace | `git diff --cached --stat`, `git status --short`, `git -c core.whitespace=cr-at-eol diff --cached --check`, staged-blob/source byte comparisons | 30 scoped files (about 1.86 MB added); only the root README modifies an already tracked file. Whitespace check passes when original Windows CRLF export endings are recognized. Source exports, authored manuscript whitespace, and the independent audit/temperature-analysis scripts remain unchanged. |

The final figure is not replaced by the newly generated PDF, whose timestamp
metadata can differ. No HYSYS runs, training, numerical IAST calculations,
complete figure regeneration or saved-score corrections were performed.
The independent audit's source-formula diagnostics remain read-only. Its
original report is preserved separately, without editing reviewer responses.
