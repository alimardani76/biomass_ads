# Reference gasifier and cleanup provenance

These are original saved exports, not new simulations or independent validation
of the production P-1 model.

| File | Original local source | SHA-256 |
|---|---|---|
| `sim1.xlsx` | `C:\Users\KaraPardazesh\Desktop\JG\New folder\sim1.xlsx` | `82caf8d307349976962dfca754634d696358cb4f986c6a3311adeef7eb697d47` |
| `water.csv` | `C:\Users\KaraPardazesh\Desktop\JG\water.csv` | `53f9fa4f0824e857d89da7532c9e76450c80c80210bf711cecd920eaa7cf4a9d` |

`sim1.xlsx` identifies `Simulation_1.hsc` in `WorkBook Summary!B1`.
Its `Material Streams` sheet gives biomass 8 kg/h (`C7`), steam 16 kg/h
(`Q7`), air 40 kg/h (`N7`), Gasif-2 800 C (`R4`) and 100 kPa (`R5`):
mass-based S/B = 2.0. The dry `Syn Gas` flow is `AF6` =
0.86446666265 kmol/h. `Compositions!AF5/AF10/AF9/AF12` contain H2, CO,
CO2 and CH4 fractions, respectively.

`dry_gas_comparison.csv` derives its simulation fractions directly from those
cells. Simulation percentages are rounded to two decimals before subtracting
the published two-decimal percentages, matching revised SI Table S2. The
literature values are Bassyouni et al. (2014),
[doi:10.1016/j.enconman.2014.08.061](https://doi.org/10.1016/j.enconman.2014.08.061),
abstract (H2 56.27%, CO 21.71%, CO2 18.24%, CH4 3.78%); its temperature
series uses S/B = 1.5 (Fig. 5, article p. 697). These were checked against
the author's local `C:\Users\KaraPardazesh\Desktop\JG\مقاله شبیه سازی1 (1).pdf`.
The comparison uses the reported four-gas dry normalization basis. The different
S/B values make this a near-condition consistency comparison, not a matched
independent validation of P-1. The copyrighted article is not redistributed.

`water.csv` has a header followed by blank/unit rows. `Case 139` records
Gasif-2 800 C and steam 45 kg/h: the outlet named `Water` contains H2O
30.3293, N2 31.5405, H2S 0.3237 and NH3 0.0724 kg/h (SI Table S3).
The same row identifies the four `Syn Gas-1` fractions, so `carbon.csv` is
unnecessary to identify this example. This is a separate sensitivity export,
outside the 20,301-case atlas, and differs from the SI production-base-case
snapshot. X-103 imposes an idealized component split; this evidence does not
establish practical cleanup efficiencies or removal of N2 by condensation.

The authored SI's 100% solid-carbon disappearance is model-only and uses a
specified solid-outlet boundary. Its archival carbon mass-flow evidence is
outside these two small exports; the original revision cites `carbon.csv`
(`Case 20`) and HYSYS composition exports in the archive's
`reviewer_sources/R1C1.md`. `carbon.csv` was not found under
`C:\Users\KaraPardazesh\Desktop\JG` or the audit's original root below;
the revision does not give its full original path. These are not replaced with
inferred values here. The PI decision on retaining that result is pending. No documented
scientific rationale for P-1 R7/R9 zero conversions is supplied by the exports.

## Independent TSA audit: extra local inputs

The original [audit script](../../scripts/r1c5_independent_audit.py) and
[short audit report](../../reports/R1C5_zero_change_audit.md) are retained
unchanged. The report records the earlier audit; current execution results are
in [revision verification](../../reports/revision_verification.md).
The full script is not runnable from a Git-only checkout. Its default
`--original-root` is `D:\hosein\ALL DONE\ALL hyd\hyd` and it requires:

- `TSA_DATA.csv`, `book1.csv`, `PSA_DATA.csv`;
- `hydrogen to mehrdad/TSA_DATA.csv` and `git/hydrogen to mehrdad/TSA_DATA.csv`;
- `ads/Temp_313.2_Pressure0.01.xlsx`;
- `ads/Temp_374_Pressure0.06309573.xlsx`;
- `ads/Temp_450_Pressure0.63095734.xlsx`.

It also reconciles local `outputs/artifacts/tsa_temperature/` files:
`scenario_winner_maps.csv`, `winner_summary.csv`, `winner_transitions.csv`,
`strategy_selected_rows.csv`, `export_sweep_pairs.csv` and `audit.json`, plus
the tracked `outputs/artifacts/winner_map_data.csv`. The existing
`tsa_temperature_analysis.py` can regenerate these analysis artifacts from
tracked inputs; its full command also emits exploratory plots and is unnecessary
for Fig. S19. Those plots and large intermediate files are not part of this
update. No missing inputs are fabricated. For the Git-only figure redraw use
`python scripts/r1c5_minimal.py`; it computes winners directly from the source
CSVs and needs no saved temperature-summary or scenario-map CSVs.
