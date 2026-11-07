**PASS — the 0/20,301 winner-change result is genuine for the saved TSA scores.** Independently joining native workbook rows to gasifier coordinates reproduces all 203,010 fixed-temperature winners and all 20,301 optimized winners. Temperature changes productivity substantially and differently for each material, but never reverses the winning ranking. This verifies the released calculations; it does not establish a physically temperature-independent system. Source-formula and export-provenance qualifications are documented below.

Audit date: 2026-11-05. Original inputs: `D:\hosein\ALL DONE\ALL hyd\hyd`; analysis root: `C:\Users\KaraPardazesh\Desktop\JG\winner`. No figures, simulations, model fits, workbook edits or manuscript edits were made.

**1. Identity, keys and missing data**

| Input | Original bytes | Current bytes | Rows excluding header |
|---|---:|---:|---:|
| TSA_DATA.csv | 60,887,047 | 60,278,016 | 609,030 |
| book1.csv | 1,294,900 | 1,274,598 | 20,301 |

SHA-256 hashes, original / current:

- TSA: `f2b93a535ebe33c2e955d1f8618c1d4f286f1a82b9e9a0642c2812f9e517f2de` / `12e00b355490b694629d751a5b946ec7691051925b9543485d13265b07dffefc`.
- Gasifier: `7f205dd0fb3cfce024e72aec956825401832ab1f9f537b532b9b923be1e7bd2a` / `79e42b8a21f171f243bbfff48ef0c8bc7386d202881fa31315d7c0e1b2bef541`.

Both files are byte-identical after CRLF-to-LF normalization, including headers and every record. The two legacy `hydrogen to mehrdad/TSA_DATA.csv` copies have the original TSA hash. The TSA header is the retained unnamed export index, three impurity masses, `Productivity-H2`, `Energy Consumption`, `T_adsorption(K)`, and `MOF type`. `book1.csv` contains steam rate, gasifier temperature, hydrogen mass flow, four species molar flows and four mole fractions; its CO molar-flow header retains a leading space, removed when resolving column names.

`task2.ipynb`, cells 2–8, reads each `Hysys` sheet with Excel row 1 as the pandas header and selects `.iloc[3:]`. Thus CSV export index 3 identifies Excel row 5, not gasifier scenario 3. The independent script uses this native identifier to join workbook steam/temperature coordinates to `book1.csv`; it does not tile scenario IDs. All eleven gasifier quantities, in all 20,301 rows, exactly match `book1.csv` in each of three sampled workbooks.

Actual ordering: material outermost (HKUST, Cu-TDPAT, Zeolite13x), ten ascending thermal set-points next, then 20,301 gasifier records. Steam runs 50–150 kg/h, with gasifier temperature 650–850 °C varying fastest. Every 20,301-row block has constant material/set-point and export indices 3–20,303. Representative alignment:

| scenario_id | Export index | Hysys row | Steam kg/h | Gasifier °C |
|---:|---:|---:|---:|---:|
| 0 | 3 | 5 | 50 | 650 |
| 1 | 4 | 6 | 50 | 651 |
| 200 | 203 | 205 | 50 | 850 |
| 201 | 204 | 206 | 51 | 650 |
| 20,300 | 20,303 | 20,305 | 150 | 850 |

There are **zero duplicate keys and zero missing scenario/material/temperature combinations**: 20,301 × 3 × 10 = 609,030. No keys, masses or productivities are missing/nonfinite. Ten energies are NaN: Zeolite, scenario 20,300, at every set-point. `tsa.ffill()` changes precisely those ten energies and no keys or productivities. Their source is an Excel `#DIV/0!` cache, not a blank meaning “same as above”; the audit does not fill them.

**2. Independent selection and reconciliation**

Exact argmax selects materials from raw productivities. The original winner maximizes each material's mean over ten set-points; optimization first takes each material's maximum over those set-points. No existing pipeline module or winner export supplies calculation inputs.

| Selection | HKUST-1 | Cu-TDPAT | Zeolite 13X | Changes versus original |
|---|---:|---:|---:|---:|
| Mean over ten set-points | 0 | 4,640 | 15,661 | 0/20,301 |
| Each fixed set-point, all ten checked separately | 0 | 4,640 | 15,661 | 0/20,301 at each |
| Per-material maximum over temperature | 0 | 4,640 | 15,661 | 0/20,301 |

Shares are 0%, 22.856016945% and 77.143983055%. There are **zero material-winner ties**, exact or within the numerical tolerance below, in all twelve strategies. HKUST and Cu uniquely maximize at 450 K in every scenario. Zeolite uniquely maximizes at 450 K in 15,661 scenarios; the other 4,640 have exact equal maxima at 434.8 and 450 K. Choosing the first maximum selects 434.8 K for those ties. Mean per-material maxima are respectively 3.078981958, 4.567095461 and 5.823368646 mol H2 kg adsorbent⁻¹ h⁻¹.

Reconciliation found **no discrepancies; discrepancy list: `[]`**. Checks covered `winner_map_data.csv` (20,301 productivity winners and gasifier coordinates), `scenario_winner_maps.csv` (243,612 labels and change flags), `winner_summary.csv` (36 count/tie rows), `winner_transitions.csv` (108 transition rows), and `strategy_selected_rows.csv` (243,612 selected material/productivity/temperature/energy records). Ten `export_sweep_pairs.csv` pairs agree with the original PSA export indices/materials and pressures. `audit.json` dimensions and current input hashes agree. Its statement that export automation was unavailable is qualified by the legacy VBA snippets found here; those snippets are inconsistent with the saved workbook cells, as detailed below. Productivity-per-energy winners are outside this audit's selection criterion.

**3. Temperature dependence of the saved values**

“Unchanged” means `abs(b-a) <= 1e-12 + 1e-12*abs(b)` in the native units. Percent change is `100*(value_450/value_313.2 - 1)`, computed per scenario before taking percentiles. Exact comparisons determine argmax. Exported rounded metrics are reconciled at `rtol=atol=1e-10`.

| Metric | Material | P5 change % | Median change % | P95 change % | Unchanged endpoint pairs % |
|---|---|---:|---:|---:|---:|
| Productivity-H2 | HKUST-1 | +175.7469 | +175.8046 | +196.8722 | 0 |
| Productivity-H2 | Cu-TDPAT | +143.5715 | +143.7584 | +201.5489 | 0 |
| Productivity-H2 | Zeolite 13X | +118.9489 | +124.8832 | +165.7926 | 0 |
| Energy Consumption | HKUST-1 | +182.4003 | +197.8434 | +198.3041 | 0 |
| Energy Consumption | Cu-TDPAT | +181.3539 | +214.5417 | +215.3019 | 0 |
| Energy Consumption | Zeolite 13X | +163.3461 | +167.2020 | +230.7717 | 0 |
| MOF mass -CH4 | HKUST-1 | −66.3160 | −66.3153 | −66.3153 | 77.1440 |
| MOF mass -CH4 | Cu-TDPAT | −66.8388 | −66.8376 | −66.8376 | 77.1440 |
| MOF mass -CH4 | Zeolite 13X | −63.3222 | −61.6711 | −61.6711 | 77.1440 |
| MOF mass -CO | HKUST-1 | −63.7644 | −63.7419 | −63.7349 | 0 |
| MOF mass -CO | Cu-TDPAT | −59.0665 | −58.9735 | −58.9443 | 0 |
| MOF mass -CO | Zeolite 13X | −57.3916 | −55.3983 | −54.3273 | 0 |
| MOF mass -CO2 | HKUST-1 | −62.5911 | −62.5742 | −62.5214 | 0 |
| MOF mass -CO2 | Cu-TDPAT | −66.1096 | −66.0781 | −65.9792 | 0 |
| MOF mass -CO2 | Zeolite 13X | −85.4560 | −85.4388 | −85.3842 | 0 |

All metrics have 20,301 valid endpoint pairs except Zeolite energy (20,300). CH4 percentage-change percentiles use the 4,640 nonzero baselines; all 15,661 zero baselines remain exactly zero throughout the ten-point sweep and are counted in the unchanged fraction. No productivity sweep is numerically constant; all 60,903 scenario/material productivity sweeps are nondecreasing.

**4. Margin evidence and explanation**

Across 203,010 scenario/temperature comparisons, margin is the largest productivity minus the second-largest; relative margin divides by the runner-up.

| Margin | Minimum | P5 | Median | P95 |
|---|---:|---:|---:|---:|
| Absolute, mol H2 kg adsorbent⁻¹ h⁻¹ | 0.130469509 | 0.381712402 | 1.922281784 | 2.717999841 |
| Relative to runner-up, % | 18.964246 | 19.731485 | 48.381926 | 67.892519 |

There are **zero margins below 1% or 5%**. Even using the winner as denominator, the minimum gap is 15.941131%. The minimum runner-relative gap occurs at scenario 1, 313.2 K: Cu 1.170859780 versus HKUST 0.984211495; Zeolite is 0.583641597.

Temperature does not act as a common multiplier. For each scenario, normalize each material's productivity by its own 313.2 K value. At 450 K the spread `100*(largest factor/smallest factor - 1)` has minimum/P5/median/P95/maximum 7.8441/12.1976/22.6453/25.9412/26.2209%. Zero scenarios share a common factor throughout the sweep at the stated tolerance. Cu/13X productivity ratio changes in every scenario; its endpoint percentage-change P5/median/P95 is +3.2989/+9.7624/+15.5793%, with range −6.6315 to +15.5793%.

The leading explanation is **different temperature responses that retain substantial ranking gaps, within a methane-dependent mass-sizing model**. Zeolite's controlling mass is CH4 in exactly the 4,640 positive-methane-fraction scenarios, where Cu wins at every temperature; otherwise CO controls and Zeolite wins. The Cu/13X ratio remains 1.376402–2.200193 in the positive-fraction group and 0.575317–0.810348 in the zero-fraction group over all temperatures. CO2 never controls any material's maximum mass. All materials' saved CH4 masses are zero exactly where saved methane mole fraction is zero. However, 3,147 such scenarios retain positive methane molar flow: the coarse saved composition/zero-mass convention materially limits physical extrapolation. These files do not establish the crossover for unrounded compositions.

**5. Targeted legacy trace and source discrepancies**

Read-only OOXML inspection covered these three original workbooks: `ads/Temp_313.2_Pressure0.01.xlsx`, `ads/Temp_374_Pressure0.06309573.xlsx`, and `ads/Temp_450_Pressure0.63095734.xlsx`. For each, all 20,301 native gasifier rows match `book1.csv`; all 304,515 cached mass/productivity/energy positions match the corresponding raw TSA records, treating the terminal error as missing. Total: **913,545 matched scoring positions**, including three missing-energy positions. No other large legacy workbook was needed.

Formula trace: HKUST uses temperature-dependent Langmuir uptake, e.g. `Hysys!N5/O5`, at `Sheet1!D2/D3`; Cu uses the corresponding `BI5/BJ5` expressions with `D20/D21`. Zeolite uses the temperature-dependent Sips form in `DD5/DE5` with `T15/T16`. Working capacity is adsorption uptake minus desorption uptake. Impurity mass is `1000*impurity_molar_flow*cycle_time/working_capacity`; the controlling mass is the maximum of the three impurity masses. `Z5`, `BU5` and `DR5` compute `1000*hydrogen_molar_flow/maximum_mass` after cancelling the explicit cycle-time factors. This last equation reproduces **all 609,030 saved productivities**, with zero mismatches. The TSA cycle-time cells `Y2/BT2/DQ2` are 0.25 h. Zero methane masses in sampled zero-fraction rows are stored constants, not missing values; the files do not preserve the editing rule that replaced the otherwise singular mass expression.

Actual adsorption inputs `D2/D20/T15` are 298 K in all three workbooks. Desorption inputs `D3/D21/T16` are respectively 313.2, 374 and 450 K and feed uptake, working capacity, mass and productivity. `F3=D3-D2`, `F21=D21-D20`, `V15=T16-T15` also feed sensible heat. The CSV's `T_adsorption(K)` header therefore mislabels a desorption-side sweep. `task2.ipynb` labels it this way when exporting, while cell 34 labels a later plot “Desorption Temperature(K)”.

The supplied `snippet2.txt` VBA is **not an exact reproducible generator**: it writes temperatures to `E3/E21/T16`, but `E3/E21` contain the text `delta T` and have no dependency path to the TSA outputs in these saved files. The live inputs are `D3/D21/T16`. It also loops over `UBound(Values)` although its declared arrays are `ValuesT/ValuesP`. Thus propagation from `E3/E21` cannot be confirmed; those addresses are wrong for these workbooks. Nevertheless, the saved numeric inputs, formulas and caches prove that both MOFs' desorption temperatures actually changed. `task2.ipynb` also relies on unsorted `os.listdir('ads')` to pair filenames with temperature labels; the three full cache comparisons detect no mispairing at the sampled positions.

Co-varied `I2/I20/T18` contain 0.01, 0.06309573 and 0.63095734 bar. They feed PSA desorption formulas. The sampled TSA formula chains use `I3/I21/T19`, fixed at 1 bar, with no reference to those swept pressure cells. Parameter precedents are constants or temperature/heat-capacity expressions, not indirect PSA-pressure links. For example, PSA `AK5` uses `I2*L5`, whereas TSA `O5` uses `I3*L5`. These are paired TSA-temperature/PSA-pressure exports, not a TSA pressure sensitivity or a joint factorial experiment.

Two source-formula defects require qualification:

- **Cu CO working capacity:** `BP6=BK5-BL5` uses the preceding gasifier row, unlike the same-row pattern intended by the surrounding formulas. Evaluating the saved Cu CO equation with original coefficients shows that all 203,010 saved Cu CO masses match the previous-row convention; 970 differ from their same-row calculation. Replacing only this reference in arithmetic changes those masses by −1.2772% to +3.3787%. **Corrected R1C5 summary is unchanged:** HKUST 0, Cu 4,640, Zeolite 15,661 under the corrected mean, every fixed temperature and per-material optimization; fixed-versus-corrected-mean changes remain 0/203,010. This diagnostic does not overwrite the released scores.
- **Zeolite energy:** `DZ5` divides by `D6*BT$2`, and the terminal `DZ20305` by `D20306*BT$2`, causing `#DIV/0!`. The next-row hydrogen mass flow explains the ten missing exported energies. Energy is not used in the productivity argmax; reported energy changes describe saved values with this source defect.

Zeolite's high-temperature plateau is model-induced: the CH4 desorption uptake is clipped with `DF5=IF(DE5<0,0,DE5)`. Its fitted saturation expression `13.69-0.03167*T` becomes negative at both 434.8 and 450 K, so clipped desorption uptake is zero at both. Where CH4 controls, the two productivities are exactly equal. This explains the temperature-optimum ties without implying temperature-independent adsorption physics.

Limits: cached outputs were directly checked at three representative temperatures, not all ten workbooks; all ten CSV temperatures were independently selected and compared. The supplied VBA cannot establish the exact historical generation procedure, and the origin of hard-coded zero methane masses is not recoverable here. Neither limitation prevents verification of the zero-change result for the saved atlas.

**6. Inspectable raw examples and reproduction**

Productivities below are raw CSV values rounded to six decimals, in mol H2 kg adsorbent⁻¹ h⁻¹. Column temperatures are desorption-side set-points in K. Scenario 0 is steam 50 kg/h, gasifier 650 °C, export index 3; scenario 200 is 50 kg/h, 850 °C, index 203; scenario 20,300 is 150 kg/h, 850 °C, index 20,303.

| Scenario / material | 313.2 | 328.4 | 343.6 | 358.8 | 374 | 389.2 | 404.4 | 419.6 | 434.8 | 450 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 / HKUST | 0.946163 | 1.546705 | 1.942247 | 2.211334 | 2.399681 | 2.534878 | 2.634122 | 2.708450 | 2.765127 | 2.809052 |
| 0 / Cu | 1.125595 | 1.846520 | 2.325266 | 2.653406 | 2.884669 | 3.051721 | 3.175066 | 3.267943 | 3.339119 | 3.394538 |
| 0 / 13X | 0.561078 | 0.918807 | 1.150811 | 1.303457 | 1.405078 | 1.473348 | 1.519498 | 1.550789 | 1.569009 | 1.569009 |
| 200 / HKUST | 1.131063 | 1.818209 | 2.252986 | 2.538070 | 2.730968 | 2.865175 | 2.960890 | 3.030681 | 3.082592 | 3.121902 |
| 200 / Cu | 1.954143 | 3.048576 | 3.690775 | 4.083570 | 4.332835 | 4.496282 | 4.606633 | 4.683110 | 4.737368 | 4.776686 |
| 200 / 13X | 2.491040 | 3.958575 | 4.811508 | 5.300461 | 5.576722 | 5.730365 | 5.814312 | 5.859248 | 5.882720 | 5.894611 |
| 20300 / HKUST | 1.144312 | 1.838881 | 2.278111 | 2.566011 | 2.760770 | 2.896249 | 2.992860 | 3.063299 | 3.115688 | 3.155359 |
| 20300 / Cu | 1.991684 | 3.102791 | 3.753327 | 4.150695 | 4.402655 | 4.567782 | 4.679229 | 4.756446 | 4.811221 | 4.850908 |
| 20300 / 13X | 3.461888 | 5.371312 | 6.410703 | 6.968706 | 7.263819 | 7.417330 | 7.495699 | 7.534843 | 7.553890 | 7.562858 |

Run `python scripts/r1c5_independent_audit.py` from the analysis root, or supply `--original-root` and `--analysis-root`. Requires Python, NumPy and pandas; workbook inspection uses standard-library ZIP/XML readers. The script prints checks, counts, quantiles and complete discrepancy lists as JSON to stdout and writes no files. Existing R1C5.md, Fig. S19 and reviewer response text are preserved. The original zero-change numerical conclusion needs no correction; the physical interpretation remains specific to the saved working-capacity and composition conventions.
