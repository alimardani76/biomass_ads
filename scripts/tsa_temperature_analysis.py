#!/usr/bin/env python3
"""Reviewer 1, Comment 5: resummarize saved TSA scores; no model evaluation.

Run from any directory: python scripts/tsa_temperature_analysis.py
Dependencies: numpy, pandas, matplotlib, openpyxl (as in README.md).
Outputs: outputs/artifacts/tsa_temperature/ and outputs/figures/si/tsa_temperature/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
TEMP = "T_adsorption(K)"  # Preserve the exported name; see workbook audit.
MOF = "MOF type"
PROD = "Productivity-H2"
ENERGY = "Energy Consumption"
STEAM = "Steam - Mass Flow"
TGAS = "Gasif-2 - Temperature"
MASS = ["MOF mass -CH4", "MOF mass -CO", "MOF mass -CO2"]
MATERIALS = ["HKUST-1", "Cu-TDPAT", "Zeolite 13X"]
LABELS = {"HKUST": "HKUST-1", "HKUST-1": "HKUST-1",
          "Cu-TDPAT": "Cu-TDPAT", "Zeolite13x": "Zeolite 13X",
          "zeolit": "Zeolite 13X", "zeolite": "Zeolite 13X",
          "Zeolite 13X": "Zeolite 13X"}
TEMPERATURES = np.array([313.2, 328.4, 343.6, 358.8, 374, 389.2,
                         404.4, 419.6, 434.8, 450])
COLORS = ["#d62728", "#2ca02c", "#1f77b4"]
METRICS = MASS + [PROD, ENERGY, "maximum_adsorbent_mass_kg"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_csv(frame, path):
    frame.to_csv(path, index=False, float_format="%.12g")


def load_data(data):
    gas = pd.read_csv(data / "book1.csv")
    gas.columns = gas.columns.str.strip()
    gas["scenario_id"] = np.arange(len(gas))
    tsa = pd.read_csv(data / "TSA_DATA.csv")
    tsa.columns = tsa.columns.str.strip()
    require(len(gas) == 20301 and len(tsa) == 609030, "Unexpected atlas size")
    require(set(tsa[MOF].str.strip()) <= set(LABELS), "Unknown material")
    tsa[MOF] = tsa[MOF].str.strip().map(LABELS)
    require(np.array_equal(np.sort(tsa[TEMP].unique()), TEMPERATURES),
            "Unexpected temperature set-points")
    require(not tsa[MASS + [PROD, TEMP, MOF]].isna().any().any(),
            "Missing selection inputs; do not silently forward-fill")
    require(np.isfinite(tsa[MASS + [PROD, TEMP]].to_numpy()).all(),
            "Nonfinite selection inputs")
    require((tsa[MASS] >= 0).all().all() and (tsa[PROD] > 0).all(),
            "Invalid mass/productivity")
    require(np.isfinite(tsa[ENERGY].dropna()).all() and (tsa[ENERGY].dropna() > 0).all(),
            "Invalid saved energy")
    # Same tiling as paper_pipeline.load_data(), independently verified by
    # the retained export index and the workbook gasifier rows below.
    require("Unnamed: 0" in tsa, "Export index needed to audit row alignment")
    expected_index = np.tile(np.arange(3, len(gas) + 3), 30)
    require(np.array_equal(tsa["Unnamed: 0"], expected_index),
            "TSA export order differs from the repository scenario tiling")
    for _, block in tsa.groupby(np.arange(len(tsa)) // len(gas)):
        require(block[MOF].nunique() == block[TEMP].nunique() == 1,
                "A scenario block mixes temperatures/materials")
    tsa["scenario_id"] = np.tile(gas.scenario_id.to_numpy(), 30)
    keys = ["scenario_id", MOF, TEMP]
    require(not tsa.duplicated(keys).any(), "Duplicate scenario/material/temperature")
    require(tsa.groupby("scenario_id").size().eq(30).all(),
            "Not all scenarios have 30 combinations")
    require(tsa.groupby(["scenario_id", MOF]).size().eq(10).all(),
            "Incomplete temperature sweep")
    require(not gas.duplicated([STEAM, TGAS]).any(), "Duplicate gasifier coordinates")
    require(gas[STEAM].nunique() * gas[TGAS].nunique() == len(gas),
            "Gasifier grid is not rectangular")
    tsa["maximum_adsorbent_mass_kg"] = tsa[MASS].max(axis=1)
    tsa["controlling_impurity"] = tsa[MASS].idxmax(axis=1).str.removeprefix("MOF mass -")
    tsa["mass_maximum_tie_count"] = tsa[MASS].eq(
        tsa["maximum_adsorbent_mass_kg"], axis=0).sum(axis=1)
    # Energy NaNs remain NaN. They never determine a productivity winner.
    return gas, tsa


def audit_workbook(data, gas, tsa):
    """Read formulas/cached values only. Never recalculate a workbook formula."""
    path = data / "hysys-rev-Final.xlsx"
    formulas = load_workbook(path, read_only=True, data_only=False)
    sheet = formulas["Sheet1"]
    param_rows = list(sheet.iter_rows())
    params = {c.coordinate: c.value for row in param_rows for c in row
              if c.value is not None}
    examples = {}
    for row in formulas["Hysys"].iter_rows(min_row=2, max_row=6):
        for cell in row:
            if cell.value is not None:
                examples[cell.coordinate] = cell.value
    formulas.close()
    # These are the original adsorption/desorption labels, not inferred from
    # the misleading exported CSV name.
    for address, label in [("C2", TEMP), ("C3", "T_desorption(K)"),
                           ("C20", TEMP), ("C21", "T_desorption(K)"),
                           ("S15", TEMP), ("S16", "T_desorption(K)")]:
        require(params[address] == label, f"Workbook label changed: {address}")
    require([params[k] for k in ["D2", "D20", "T15"]] == [298, 298, 298],
            "Unexpected adsorption temperatures")
    require([params[k] for k in ["D3", "D21", "T16"]] == [450, 450, 450],
            "Unexpected cached desorption state")
    require([params[k] for k in ["I3", "I21", "T19"]] == [1, 1, 1],
            "Unexpected TSA pressure")
    require(examples["Z4"] == "molH2/Kgmof.hr" and examples["AH4"] == "MJ/KgH2",
            "Unexpected workbook output units")
    groups = [(14, 34), (61, 81), (108, 130)]  # N:AH, BI:CC, DD:DZ
    from openpyxl.utils.cell import column_index_from_string
    tsa_formulas = [value for address, value in examples.items()
                    if address.endswith("5") and isinstance(value, str)
                    and value.startswith("=")
                    and any(a <= column_index_from_string(re.sub(r"\d", "", address)) <= b
                            for a, b in groups)]
    pressure_refs = sorted({ref for value in tsa_formulas
                            for ref in re.findall(r"Sheet1!([A-Z]+\$?\d+)", value)
                            if ref.replace("$", "") in {"I2", "I3", "I20", "I21", "T18", "T19"}})
    require({v.replace("$", "") for v in pressure_refs} == {"I3", "I21", "T19"},
            "TSA formulas no longer use only fixed adsorption pressure")

    # Stream the original XML to verify all gasifier rows and every cached
    # 450 K scoring output against the CSVs without allocating all Excel cells.
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    wanted = ["W", "X", "Y", "Z", "AH", "BR", "BS", "BT", "BU", "CC",
              "DO", "DP", "DQ", "DR", "DZ"]
    gas_cols = list("BCDEFGHIJKL")
    cached_gas, cached_scores = [], []
    terminal_cells = {}
    with zipfile.ZipFile(path) as archive:
        # This workbook's second sheet is Hysys; validate that relationship.
        with archive.open("xl/worksheets/sheet2.xml") as source:
            for _, row in ET.iterparse(source, events=("end",)):
                if row.tag != ns + "row":
                    continue
                number = int(row.attrib["r"])
                if 5 <= number <= len(gas) + 4:
                    values = {}
                    for c in row.findall(ns + "c"):
                        address = c.attrib["r"]
                        col = re.sub(r"\d", "", address)
                        val = c.find(ns + "v")
                        if col in gas_cols + wanted:
                            try:
                                values[col] = float(val.text) if val is not None else np.nan
                            except (ValueError, TypeError):
                                values[col] = np.nan
                        if number == len(gas) + 4 and col in wanted:
                            f = c.find(ns + "f")
                            terminal_cells[address] = {
                                "formula": f.text if f is not None else None,
                                "cached": val.text if val is not None else None}
                    cached_gas.append([values.get(c, np.nan) for c in gas_cols])
                    cached_scores.append([values.get(c, np.nan) for c in wanted])
                row.clear()
                if number >= len(gas) + 4:
                    break
    require(np.array_equal(cached_gas, gas.drop(columns="scenario_id").to_numpy()),
            "Gasifier CSV row order does not exactly match original workbook")
    csv_scores = np.column_stack([
        tsa.loc[tsa[MOF].eq(m) & tsa[TEMP].eq(450), MASS + [PROD, ENERGY]].to_numpy()
        for m in MATERIALS])
    cache_matches = np.isclose(cached_scores, csv_scores, rtol=1e-12, atol=1e-12, equal_nan=True)
    require(cache_matches.all(), "450 K CSV scores disagree with workbook cache")

    # PSA is audited only for sweep structure, never used for TSA selection.
    psa = pd.read_csv(data / "PSA_DATA.csv")
    require(len(psa) == len(tsa), "Unexpected PSA atlas size")
    require(np.array_equal(psa["Unnamed: 0"], tsa["Unnamed: 0"]),
            "PSA/TSA index alignment changed")
    require(np.array_equal(psa[MOF].str.strip().map(LABELS), tsa[MOF]),
            "PSA/TSA material alignment changed")
    pairs = pd.DataFrame({TEMP: tsa[TEMP], "PSA_P_adsorption_export": psa.P_adsorption})
    pairs = pairs.drop_duplicates().sort_values(TEMP)
    require(len(pairs) == 10, "PSA pressure and TSA temperature sweeps are no longer paired")
    return {
        "parameters_Sheet1": params, "Hysys_examples_rows_2_to_6": examples,
        "terminal_scoring_cells": terminal_cells,
        "gasifier_rows_exactly_equal": len(cached_gas),
        "cached_450K_scoring_cells_verified": int(cache_matches.size),
        "TSA_pressure_formula_references": pressure_refs,
        "temperature_interpretation":
            "CSV name preserved. Workbook adsorption is 298 K; varying set-point is "
            "consistent with desorption: 450 K CSV scores match cached formulas using "
            "Sheet1 D3/D21/T16. No original export automation is supplied.",
        "pressure_interpretation":
            "TSA and PSA exports contain ten paired sweep positions, not a joint T-P "
            "factorial. TSA formulas use fixed 1 bar I3/I21/T19, not swept PSA "
            "desorption pressure I2/I20/T18. Paired export correlation is not a TSA "
            "temperature-pressure interaction.",
    }, pairs


def select_strategies(tsa):
    def winner(frame):
        frame = frame.reindex(columns=MATERIALS).sort_index()
        return frame.idxmax(axis=1), frame.eq(frame.max(axis=1), axis=0).sum(axis=1)
    mean = tsa.groupby(["scenario_id", MOF])[PROD].mean().unstack(MOF)
    original, ties = winner(mean)
    strategies = {"original": original}
    tie_counts = {"original": ties}
    for t in TEMPERATURES:
        key = f"fixed_{t:g}K"
        strategies[key], tie_counts[key] = winner(tsa.loc[tsa[TEMP].eq(t)].pivot(
            index="scenario_id", columns=MOF, values=PROD))
    ordered = tsa.sort_values(["scenario_id", MOF, TEMP])
    # idxmax chooses the first exact maximum, hence lowest T for exact ties.
    best_index = ordered.groupby(["scenario_id", MOF])[PROD].idxmax()
    optimal = ordered.loc[best_index].copy()
    maxima = tsa.groupby(["scenario_id", MOF])[PROD].transform("max")
    cooptimal = tsa.loc[tsa[PROD].eq(maxima)]
    tie_info = cooptimal.groupby(["scenario_id", MOF])[TEMP].agg(
        optimal_temperature_count="size",
        all_optimal_temperatures_K=lambda x: ";".join(f"{t:g}" for t in sorted(x)))
    optimal = optimal.merge(tie_info, on=["scenario_id", MOF], validate="one_to_one")
    strategies["optimized"], tie_counts["optimized"] = winner(optimal.pivot(
        index="scenario_id", columns=MOF, values=PROD))
    frequencies = []
    for m in MATERIALS:
        for t in TEMPERATURES:
            chosen = int((optimal[MOF].eq(m) & optimal[TEMP].eq(t)).sum())
            possible = int((cooptimal[MOF].eq(m) & cooptimal[TEMP].eq(t)).sum())
            frequencies.append({MOF: m, TEMP: t, "selected_count": chosen,
                                "selected_pct": chosen / len(original) * 100,
                                "cooptimal_count": possible,
                                "cooptimal_pct": possible / len(original) * 100})
    return strategies, tie_counts, optimal, pd.DataFrame(frequencies)


def summarize_strategies(gas, tsa, strategies, ties, optimal):
    n = len(gas)
    rows, transitions, selected_rows = [], [], []
    original = strategies["original"]
    maps = gas[["scenario_id", STEAM, TGAS]].copy()
    for key, winners in strategies.items():
        maps[f"winner_{key}"] = winners.to_numpy()
        maps[f"changed_{key}"] = winners.ne(original).to_numpy()
        t = float(key[6:-1]) if key.startswith("fixed_") else np.nan
        for m in MATERIALS:
            rows.append({"strategy": key, TEMP: t, MOF: m,
                         "definition": ("maximum mean productivity over ten set-points" if key == "original"
                                        else "maximum productivity after per-material discrete temperature optimization"
                                        if key == "optimized" else "maximum productivity at a common set-point"),
                         "scenario_count": n, "winner_count": int(winners.eq(m).sum()),
                         "winner_pct": winners.eq(m).mean() * 100,
                         "changed_scenarios": int(winners.ne(original).sum()),
                         "changed_pct": winners.ne(original).mean() * 100,
                         "gained_scenarios": int((winners.eq(m) & original.ne(m)).sum()),
                         "lost_scenarios": int((winners.ne(m) & original.eq(m)).sum()),
                         "material_winner_tie_scenarios": int(ties[key].gt(1).sum())})
            for dest in MATERIALS:
                transitions.append({"strategy": key, "original_winner": m,
                                    "new_winner": dest,
                                    "scenario_count": int((original.eq(m) & winners.eq(dest)).sum())})
        if key == "original":
            # This row represents a mean score, not an actual selected temperature.
            scores = tsa.groupby(["scenario_id", MOF], as_index=False)[METRICS].mean()
            scores[TEMP] = np.nan
        elif key == "optimized":
            scores = optimal.copy()
        else:
            scores = tsa.loc[tsa[TEMP].eq(t)].copy()
        scores["winner"] = scores.scenario_id.map(winners)
        selected = scores.loc[scores[MOF].eq(scores.winner)].copy()
        selected["strategy"] = key
        selected["changed_from_original"] = selected.scenario_id.map(winners.ne(original))
        selected_rows.append(selected[["strategy", "scenario_id", MOF, TEMP,
                                       PROD, ENERGY, "changed_from_original"]])
    selected = pd.concat(selected_rows, ignore_index=True)
    selected_summary = selected.groupby("strategy", sort=False).agg(
        mean_winning_productivity=(PROD, "mean"),
        mean_winning_energy=(ENERGY, "mean"), energy_valid_count=(ENERGY, "count"),
        energy_missing_count=(ENERGY, lambda s: int(s.isna().sum()))).reset_index()
    return pd.DataFrame(rows), maps, pd.DataFrame(transitions), selected, selected_summary


def analyze_trends(tsa, optimal):
    rows, limits, associations = [], [], []
    for (m, t), sub in tsa.groupby([MOF, TEMP], sort=False):
        row = {MOF: m, TEMP: t, "scenario_count": len(sub),
               "energy_missing_count": int(sub[ENERGY].isna().sum())}
        for metric in METRICS:
            v = sub[metric].dropna()
            for stat, value in [("mean", v.mean()), ("median", v.median()),
                                ("min", v.min()), ("max", v.max()),
                                ("q10", v.quantile(.1)), ("q90", v.quantile(.9))]:
                row[f"{metric}__{stat}"] = value
        rows.append(row)
        for impurity in ["CH4", "CO", "CO2"]:
            count = int(sub.controlling_impurity.eq(impurity).sum())
            limits.append({MOF: m, TEMP: t, "controlling_impurity": impurity,
                           "count": count, "pct": 100 * count / len(sub),
                           "mass_tie_rows": int(sub.mass_maximum_tie_count.gt(1).sum())})
    for m, sub in tsa.groupby(MOF, sort=False):
        p = sub.pivot(index="scenario_id", columns=TEMP, values=PROD).reindex(columns=TEMPERATURES)
        e = sub.pivot(index="scenario_id", columns=TEMP, values=ENERGY).reindex(columns=TEMPERATURES)
        paired = e.notna().all(axis=1)
        correlations = p.loc[paired].corrwith(e.loc[paired], axis=1)
        chosen = optimal.loc[optimal[MOF].eq(m)]
        associations.append({MOF: m, "pooled_pearson_r": sub[[PROD, ENERGY]].corr().iloc[0, 1],
                             "within_scenario_r_mean": correlations.mean(),
                             "within_scenario_r_min": correlations.min(),
                             "within_scenario_r_max": correlations.max(),
                             "complete_energy_scenarios": int(paired.sum()),
                             "productivity_nondecreasing_scenarios": int((p.diff(axis=1).iloc[:, 1:] >= 0).all(axis=1).sum()),
                             "energy_strictly_increasing_scenarios": int((e.loc[paired].diff(axis=1).iloc[:, 1:] > 0).all(axis=1).sum()),
                             "mean_productivity_at_selected_T": chosen[PROD].mean(),
                             "mean_energy_at_selected_T": chosen[ENERGY].mean(),
                             "selected_energy_valid_count": int(chosen[ENERGY].notna().sum()),
                             "selected_energy_missing_count": int(chosen[ENERGY].isna().sum()),
                             "multiple_optimal_temperatures_scenarios": int(chosen.optimal_temperature_count.gt(1).sum())})
        for metric in MASS:
            values = sub.pivot(index="scenario_id", columns=TEMP, values=metric).reindex(columns=TEMPERATURES)
            associations[-1][f"{metric}__nonincreasing_scenarios"] = int(
                (values.diff(axis=1).iloc[:, 1:] <= 0).all(axis=1).sum())
    return pd.DataFrame(rows), pd.DataFrame(limits), pd.DataFrame(associations)


def boundaries(gas, strategies):
    """Report actual adjacent grid cells straddling Cu/13X, without interpolation."""
    rows = []
    for key, winners in strategies.items():
        frame = gas[["scenario_id", STEAM, TGAS]].copy()
        frame["winner"] = winners.to_numpy()
        grid = frame.pivot(index=TGAS, columns=STEAM, values="scenario_id").sort_index().sort_index(axis=1)
        ids = grid.to_numpy()
        for direction, left, right in [("gasifier_temperature", ids[:-1], ids[1:]),
                                        ("steam_flow", ids[:, :-1], ids[:, 1:])]:
            wl, wr = winners.to_numpy()[left], winners.to_numpy()[right]
            cross = ((wl == "Cu-TDPAT") & (wr == "Zeolite 13X")) | ((wl == "Zeolite 13X") & (wr == "Cu-TDPAT"))
            for a, b in zip(left[cross], right[cross]):
                rows.append({"strategy": key, "direction": direction,
                             "scenario_id_a": a, "scenario_id_b": b,
                             "steam_a_kg_h": gas.at[a, STEAM], "steam_b_kg_h": gas.at[b, STEAM],
                             "gasifier_T_a_C": gas.at[a, TGAS], "gasifier_T_b_C": gas.at[b, TGAS]})
    return pd.DataFrame(rows)


def make_figures(gas, summary, maps, trends, freq, out):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    def save(fig, name):
        for suffix in ["png", "pdf"]:
            fig.savefig(out / f"{name}.{suffix}", dpi=300, bbox_inches="tight")
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    fixed = summary.loc[summary.strategy.str.startswith("fixed_")]
    for m, color in zip(MATERIALS, COLORS):
        s = fixed.loc[fixed[MOF].eq(m)].sort_values(TEMP)
        ax.plot(s[TEMP], s.winner_pct, "o-", color=color, label=m)
    ax.set(xlabel=TEMP, ylabel="Gasifier scenarios won (%)", ylim=(-3, 103))
    ax.set_xticks(TEMPERATURES, [f"{t:g}" for t in TEMPERATURES], rotation=45)
    ax.legend(loc="center right")
    ax.set_title("Adsorbent winner shares at all ten common set-points")
    save(fig, "winner_shares_vs_temperature")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for m, color in zip(MATERIALS, COLORS):
        s = trends.loc[trends[MOF].eq(m)].sort_values(TEMP)
        for ax, metric in zip(axes, [PROD, ENERGY]):
            ax.plot(s[TEMP], s[f"{metric}__mean"], "o-", color=color, label=m)
            ax.fill_between(s[TEMP], s[f"{metric}__q10"], s[f"{metric}__q90"], color=color, alpha=.10)
    axes[0].set(ylabel=r"Hydrogen productivity (mol kg$^{-1}$ h$^{-1}$)", title="(a) Saved productivity")
    axes[1].set(ylabel=r"Energy consumption (MJ kg$_{H_2}^{-1}$)", title="(b) Saved regeneration energy")
    for ax in axes:
        ax.set_xlabel(TEMP)
    axes[0].legend()
    fig.suptitle("Lines: scenario means; bands: 10th–90th percentiles")
    save(fig, "productivity_energy_vs_temperature")
    # Representative panels use both endpoints and the lower central grid value;
    # every fixed temperature is still quantified and mapped in the all-ten figure.
    selections = [("original", "Original: mean over ten"),
                  ("fixed_313.2K", "Fixed: 313.2 K"), ("fixed_374K", "Fixed: 374 K"),
                  ("fixed_450K", "Fixed: 450 K"), ("optimized", "Individually optimized")]
    def draw_map(ax, key, title):
        f = gas[[STEAM, TGAS]].copy()
        f["code"] = maps[f"winner_{key}"].map(dict(zip(MATERIALS, range(3))))
        matrix = f.pivot(index=TGAS, columns=STEAM, values="code").sort_index().sort_index(axis=1)
        ax.pcolormesh(matrix.columns, matrix.index, matrix.to_numpy(), shading="nearest",
                      cmap=ListedColormap(COLORS), vmin=-.5, vmax=2.5, rasterized=True)
        ax.set_title(title)
        ax.set_xlabel(r"Steam flow (kg h$^{-1}$)")
        ax.set_ylabel("Gasifier temperature (°C)")
    fig, axes = plt.subplots(1, 5, figsize=(16, 3.8), layout="constrained")
    for ax, (key, title) in zip(axes, selections):
        draw_map(ax, key, title)
    handles = [Patch(color=c, label=m) for m, c in zip(MATERIALS, COLORS)]
    fig.legend(handles=handles, loc="outside lower center", ncol=3)
    save(fig, "strategy_winner_maps")
    fig, axes = plt.subplots(2, 5, figsize=(15, 7), layout="constrained")
    for ax, t in zip(axes.flat, TEMPERATURES):
        changed = summary.loc[summary.strategy.eq(f"fixed_{t:g}K"), "changed_scenarios"].iloc[0]
        draw_map(ax, f"fixed_{t:g}K", f"{t:g} K; {changed:,} changed")
    fig.legend(handles=handles, loc="outside lower center", ncol=3)
    save(fig, "all_fixed_temperature_winner_maps")
    fig, axes = plt.subplots(1, 3, figsize=(11, 4), sharey=True, layout="constrained")
    for ax, m, color in zip(axes, MATERIALS, COLORS):
        s = freq.loc[freq[MOF].eq(m)].sort_values(TEMP)
        xx = np.arange(len(s))
        ax.bar(xx, s.selected_pct, color=color, label="Selected (lowest T on ties)")
        ax.plot(xx, s.cooptimal_pct, "ko", markersize=4, label="Any exact optimum")
        ax.set_xticks(xx, [f"{t:g}" for t in TEMPERATURES], rotation=60)
        ax.set(title=m, xlabel=TEMP, ylim=(0, 108))
    axes[0].set_ylabel("Gasifier scenarios (%)")
    axes[1].legend(fontsize=8, loc="upper left")
    save(fig, "optimal_temperature_distribution")
    fig, axes = plt.subplots(1, 3, figsize=(11, 4), sharey=True, layout="constrained")
    for ax, metric in zip(axes, MASS):
        for m, color in zip(MATERIALS, COLORS):
            s = trends.loc[trends[MOF].eq(m)].sort_values(TEMP)
            ax.plot(s[TEMP], s[f"{metric}__mean"], "o-", color=color, label=m)
        ax.set(title=metric.removeprefix("MOF mass -"), xlabel=TEMP)
    axes[0].set_ylabel("Mean required adsorbent mass (kg)")
    axes[2].legend()
    save(fig, "adsorbent_mass_vs_temperature")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs/artifacts/tsa_temperature")
    parser.add_argument("--figure-dir", type=Path, default=ROOT / "outputs/figures/si/tsa_temperature")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.figure_dir.mkdir(parents=True, exist_ok=True)
    gas, tsa = load_data(args.data_dir)
    print(f"Validated {len(gas):,} scenarios, each with all 30 combinations", flush=True)
    audit, pairs = audit_workbook(args.data_dir, gas, tsa)
    strategies, ties, optimal, freq = select_strategies(tsa)
    reference_path = ROOT / "outputs/artifacts/winner_map_data.csv"
    if reference_path.exists():
        reference = pd.read_csv(reference_path).sort_values("scenario_id")
        require(np.array_equal(reference.scenario_id, gas.scenario_id), "Reference scenario IDs differ")
        require(np.array_equal(reference[[STEAM, TGAS]], gas[[STEAM, TGAS]]), "Reference coordinates differ")
        mismatches = int(reference.winner_prod.ne(strategies["original"].to_numpy()).sum())
        require(mismatches == 0, "Original selection differs from released winner map")
        audit["reference_winner_map_mismatches"] = mismatches
    else:
        audit["reference_winner_map_mismatches"] = None
    summary, maps, transitions, selected, selected_summary = summarize_strategies(
        gas, tsa, strategies, ties, optimal)
    trends, limits, associations = analyze_trends(tsa, optimal)
    edges = boundaries(gas, strategies)
    baseline_edges = set(map(tuple, edges.loc[edges.strategy.eq("original"),
                                             ["scenario_id_a", "scenario_id_b"]].to_numpy()))
    boundary_summary = []
    for key in strategies:
        current = edges.loc[edges.strategy.eq(key)]
        current_edges = set(map(tuple, current[["scenario_id_a", "scenario_id_b"]].to_numpy()))
        if key == "original":
            scores = tsa.groupby(["scenario_id", MOF])[PROD].mean().unstack(MOF)
        elif key == "optimized":
            scores = optimal.pivot(index="scenario_id", columns=MOF, values=PROD)
        else:
            scores = tsa.loc[tsa[TEMP].eq(float(key[6:-1]))].pivot(
                index="scenario_id", columns=MOF, values=PROD)
        gap = (scores["Cu-TDPAT"] - scores["Zeolite 13X"]).abs() / scores[["Cu-TDPAT", "Zeolite 13X"]].max(axis=1)
        boundary_summary.append({"strategy": key, "crossing_grid_edges": len(current_edges),
                                 "gasifier_temperature_edges": int(current.direction.eq("gasifier_temperature").sum()),
                                 "steam_flow_edges": int(current.direction.eq("steam_flow").sum()),
                                 "removed_boundary_edges": len(baseline_edges - current_edges),
                                 "added_boundary_edges": len(current_edges - baseline_edges),
                                 "minimum_Cu_13X_relative_productivity_gap_pct": 100 * gap.min()})
    audit["input_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in [args.data_dir / n for n in
                                       ["TSA_DATA.csv", "book1.csv", "PSA_DATA.csv", "hysys-rev-Final.xlsx"]]}
    audit["scenario_count"] = len(gas)
    audit["calculation_rows"] = len(tsa)
    audit["gasifier_grid"] = {STEAM: gas[STEAM].nunique(), TGAS: gas[TGAS].nunique()}
    audit["missing_energy_rows"] = tsa.loc[tsa[ENERGY].isna(), ["scenario_id", MOF, TEMP]].to_dict("records")
    audit["energy_handling"] = "No imputation; means exclude missing saved energies and include valid counts."
    audit["temperature_tie_handling"] = "Lowest temperature among exact productivity maxima; all maxima are also exported."
    audit["positive_methane_flow_but_zero_mole_fraction_scenarios"] = int(
        (gas["Molar Flow (Methane)"].gt(0) & gas["Mole Frac (Methane)"].eq(0)).sum())
    audit["winner_equals_methane_mole_fraction_zero_partition"] = bool(np.array_equal(
        strategies["original"].eq("Zeolite 13X"), gas["Mole Frac (Methane)"].eq(0)))
    outputs = {"winner_summary.csv": summary, "scenario_winner_maps.csv": maps,
               "winner_transitions.csv": transitions, "strategy_selected_rows.csv": selected,
               "strategy_performance_summary.csv": selected_summary,
               "optimal_material_scenario.csv": optimal.drop(columns="Unnamed: 0"),
               "optimal_temperature_frequencies.csv": freq, "temperature_trends.csv": trends,
               "controlling_impurity.csv": limits, "productivity_energy_association.csv": associations,
               "boundary_grid_edges.csv": edges, "export_sweep_pairs.csv": pairs,
               "boundary_summary.csv": pd.DataFrame(boundary_summary),
               "missing_energy_rows.csv": tsa.loc[tsa[ENERGY].isna(), ["scenario_id", MOF, TEMP]]}
    for name, frame in outputs.items():
        write_csv(frame, args.output_dir / name)
    (args.output_dir / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    make_figures(gas, summary, maps, trends, freq, args.figure_dir)
    print(summary[["strategy", MOF, "winner_count", "winner_pct", "changed_scenarios"]].to_string(index=False))
    print("\nProductivity-selected operating points (energy from the same saved row):")
    print(associations.to_string(index=False))
    print(f"\nOutputs: {args.output_dir}\nFigures: {args.figure_dir}")


if __name__ == "__main__":
    main()
