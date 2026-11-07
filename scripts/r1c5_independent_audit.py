#!/usr/bin/env python3
"""Read-only R1C5 verification. Python 3 + numpy/pandas; prints JSON to stdout.

Defaults read the ORIGINAL CSVs, not the current analysis copies. Three saved
workbooks establish the native Excel-row -> gasifier-coordinate relationship.
Existing winner exports are opened only AFTER independent winner calculation.
No imports from the paper/R1C5 pipeline, imputation, simulation or model fitting.
Run: python scripts/r1c5_independent_audit.py
Override paths with --original-root and --analysis-root. No files are written.
"""
import argparse
import hashlib
import json
import posixpath
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd

T, M, P, E = 'T_adsorption(K)', 'MOF type', 'Productivity-H2', 'Energy Consumption'
MASS = ['MOF mass -CH4', 'MOF mass -CO', 'MOF mass -CO2']
METRICS = MASS + [P, E]
MATERIALS = ['HKUST-1', 'Cu-TDPAT', 'Zeolite 13X']
LABELS = {'HKUST': 'HKUST-1', 'Cu-TDPAT': 'Cu-TDPAT', 'Zeolite13x': 'Zeolite 13X'}
TEMPS = [313.2, 328.4, 343.6, 358.8, 374., 389.2, 404.4, 419.6, 434.8, 450.]
COORD = ['Steam - Mass Flow', 'Gasif-2 - Temperature']
RTOL, ATOL = 1e-12, 1e-12
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
SCORE_COLS = ['W', 'X', 'Y', 'Z', 'AH', 'BR', 'BS', 'BT', 'BU', 'CC',
              'DO', 'DP', 'DQ', 'DR', 'DZ']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def quantiles(values):
    return dict(zip(['min', 'p05', 'median', 'p95', 'max'],
                    np.percentile(np.asarray(values), [0, 5, 50, 95, 100]).tolist()))


def identity(path, reference):
    a, b = path.read_bytes(), reference.read_bytes()
    require(a.replace(b'\r\n', b'\n') == b.replace(b'\r\n', b'\n'),
            f'Input contents differ beyond line endings: {path}')
    return {'original_bytes': len(a), 'current_bytes': len(b),
            'original_sha256': hashlib.sha256(a).hexdigest(),
            'current_sha256': hashlib.sha256(b).hexdigest(),
            'identical_after_CRLF_normalization': True,
            'header': a.splitlines()[0].decode('utf-8-sig')}


def workbook(path, n):
    """Stream OOXML caches; keep only sample formulas, never run Excel/HYSYS."""
    def number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return np.nan

    with zipfile.ZipFile(path) as z:
        shared = ET.fromstring(z.read('xl/sharedStrings.xml'))
        strings = [''.join(x.itertext()) for x in shared.findall(NS + 'si')]
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        targets = {r.attrib['Id']: r.attrib['Target'] for r in rels}
        sheets = ET.fromstring(z.read('xl/workbook.xml')).find(NS + 'sheets')
        names = {s.attrib['name']: posixpath.normpath('xl/' + targets[
            s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']])
            for s in sheets}

        def cell(c):
            v, f = c.find(NS + 'v'), c.find(NS + 'f')
            value = v.text if v is not None else None
            if c.attrib.get('t') == 's':
                value = strings[int(value)]
            return value, f.text if f is not None else None

        parameters = {c.attrib['r']: cell(c) for c in
                      ET.fromstring(z.read(names['Sheet1'])).iter(NS + 'c')}
        gas, scores, sample = [], [], {}
        with z.open(names['Hysys']) as source:
            for _, row in ET.iterparse(source, events=('end',)):
                if row.tag != NS + 'row':
                    continue
                r = int(row.attrib['r'])
                cells = {re.sub(r'\d', '', c.attrib['r']): cell(c)
                         for c in row.findall(NS + 'c')}
                if 5 <= r <= n + 4:
                    gas.append([number(cells.get(c, (None,))[0]) for c in 'BCDEFGHIJKL'])
                    scores.append([number(cells.get(c, (None,))[0]) for c in SCORE_COLS])
                if r in [2, 5, 6, 205, n + 4]:
                    sample[r] = cells
                row.clear()
                if r >= n + 4:
                    break
    return parameters, np.asarray(gas), np.asarray(scores), sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-root', type=Path,
                        default=Path(r'D:\hosein\ALL DONE\ALL hyd\hyd'))
    parser.add_argument('--analysis-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    original, current = args.original_root, args.analysis_root
    result = {'tolerance': {'rtol': RTOL, 'atol': ATOL}, 'identity': {}}
    for name in ['TSA_DATA.csv', 'book1.csv']:
        result['identity'][name] = identity(original / name, current / 'data' / name)
    result['legacy_TSA_copies'] = {
        str(p.relative_to(original)): identity(p, current / 'data/TSA_DATA.csv')['original_sha256']
        for p in [original / 'hydrogen to mehrdad/TSA_DATA.csv',
                  original / 'git/hydrogen to mehrdad/TSA_DATA.csv']}
    gas, raw = pd.read_csv(original / 'book1.csv'), pd.read_csv(original / 'TSA_DATA.csv')
    gas.columns = gas.columns.str.strip()
    gas['scenario_id'] = gas.index
    n = len(gas)
    require(n == 20301 and len(raw) == n * 30, 'Unexpected input dimensions')
    require(not gas[COORD].duplicated().any(), 'Duplicate native coordinates')
    require(not gas.isna().any().any(), 'Missing gasifier input')
    result['missing_by_column'] = raw.isna().sum().to_dict()
    filled = raw.ffill()
    result['ffill_changes_by_column'] = ((filled != raw) & ~(filled.isna() & raw.isna())).sum().to_dict()
    require(not raw[[T, M, P, 'Unnamed: 0'] + MASS].isna().any().any(), 'Missing selection inputs')
    require(np.isfinite(raw[[T, P] + MASS]).all().all(), 'Nonfinite selection inputs')
    require((raw[P] > 0).all(), 'Nonpositive productivity')
    require(set(raw[M]) == set(LABELS) and sorted(raw[T].unique()) == TEMPS, 'Unexpected labels/set-points')

    # task2.ipynb reads Hysys with row 1 as header, slices .iloc[3:], and
    # preserves that pandas index: export index 3 corresponds to Excel row 5.
    # Join using these retained identifiers, NOT a tiled assumed scenario array.
    parameters_by_t, samples_by_t, wb_results = {}, {}, []
    mapping = None
    for temperature, filename in [
        (313.2, 'Temp_313.2_Pressure0.01.xlsx'),
        (374., 'Temp_374_Pressure0.06309573.xlsx'),
        (450., 'Temp_450_Pressure0.63095734.xlsx')]:
        print(f'Reading saved workbook {filename}', file=sys.stderr, flush=True)
        parameters, native, cached, samples = workbook(original / 'ads' / filename, n)
        require(native.shape == (n, 11), 'Unexpected native gasifier rows')
        require(np.array_equal(native, gas.drop(columns='scenario_id').to_numpy()),
                f'Native gasifier row order differs: {filename}')
        native_mapping = pd.DataFrame(native[:, :2], columns=COORD)
        native_mapping['Unnamed: 0'] = np.arange(5, n + 5) - 2
        native_mapping = native_mapping.merge(gas[COORD + ['scenario_id']], on=COORD, validate='one_to_one')
        if mapping is None:
            mapping = native_mapping
        else:
            require(mapping.equals(native_mapping), 'Workbook alignment disagreement')
        expected = np.column_stack([raw.loc[(raw[M] == label) & (raw[T] == temperature)]
                                    .set_index('Unnamed: 0').reindex(mapping['Unnamed: 0'])[METRICS]
                                    .to_numpy() for label in LABELS])
        matches = np.isclose(cached, expected, rtol=RTOL, atol=ATOL, equal_nan=True)
        require(matches.all(), f'Workbook/CSV scoring discrepancy: {filename}')
        parameters_by_t[temperature], samples_by_t[temperature] = parameters, samples
        inputs = {k: parameters[k][0] for k in
                  ['D2', 'D3', 'E3', 'D20', 'D21', 'E21', 'T15', 'T16',
                   'I2', 'I20', 'T18', 'I3', 'I21', 'T19']}
        require([float(inputs[k]) for k in ['D3', 'D21', 'T16']] == [temperature] * 3,
                'Saved temperature mismatch')
        require([float(inputs[k]) for k in ['D2', 'D20', 'T15']] == [298.] * 3
                and [float(inputs[k]) for k in ['I3', 'I21', 'T19']] == [1.] * 3,
                'Fixed TSA adsorption temperature/pressure mismatch')
        wb_results.append({'file': filename, 'native_rows_matched': n,
                           'scoring_positions_matched_including_missing': int(matches.size),
                           'inputs': inputs})
    result['legacy_workbooks'] = wb_results
    data = raw.merge(mapping, on='Unnamed: 0', how='left', validate='many_to_one')
    require(data.scenario_id.notna().all(), 'Unknown exported gasifier identifier')
    data[M] = data[M].map(LABELS)
    keys = ['scenario_id', M, T]
    require(not data.duplicated(keys).any(), 'Duplicate scenario/material/temperature')
    require(data.groupby('scenario_id').size().eq(30).all(), 'Missing combinations')
    result['alignment'] = {'rows': len(data), 'scenarios': n, 'duplicate_keys': 0,
                           'missing_combinations': 0, 'steam_values': gas[COORD[0]].nunique(),
                           'gasifier_temperatures': gas[COORD[1]].nunique(),
                           'ordering_first_each_block': raw.iloc[::n][['Unnamed: 0', M, T]].to_dict('records'),
                           'native_samples': mapping.iloc[[0, 1, 200, 201, 20300]].to_dict('records')}
    result['missing_energy_keys'] = data.loc[data[E].isna(), keys].to_dict('records')
    result['nonfinite_counts'] = {c: int((~np.isfinite(data[c])).sum()) for c in METRICS}
    index = pd.MultiIndex.from_product([range(n), MATERIALS, TEMPS], names=keys)
    scores = data.set_index(keys)[P].reindex(index).to_numpy().reshape(n, 3, 10)
    means, maxima = scores.mean(axis=2), scores.max(axis=2)
    original_winner = means.argmax(axis=1)
    strategies = {'original': original_winner}
    strategies.update({f'fixed_{t:g}K': scores[:, :, j].argmax(axis=1) for j, t in enumerate(TEMPS)})
    strategies['optimized'] = maxima.argmax(axis=1)
    result['strategies'], discrepancies = {}, []
    for name, winners in strategies.items():
        values = means if name == 'original' else maxima if name == 'optimized' else scores[:, :, list(strategies).index(name)-1]
        ties = (values == values.max(axis=1, keepdims=True)).sum(axis=1) > 1
        near_ties = np.isclose(values, values.max(axis=1, keepdims=True), rtol=RTOL, atol=ATOL).sum(axis=1) > 1
        changed = np.flatnonzero(winners != original_winner)
        result['strategies'][name] = {'counts': dict(zip(MATERIALS, np.bincount(winners, minlength=3).tolist())),
                                     'changed': len(changed), 'exact_material_ties': int(ties.sum()),
                                     'tolerance_material_ties': int(near_ties.sum())}
        discrepancies.extend({'strategy': name, 'scenario_id': int(i),
                              'original': MATERIALS[original_winner[i]], 'new': MATERIALS[winners[i]]}
                             for i in changed)
    result['winner_change_discrepancies'] = discrepancies
    result['temperature_optima'] = {}
    for j, material in enumerate(MATERIALS):
        v = scores[:, j, :]
        result['temperature_optima'][material] = {
            'first_exact_maximum_counts': dict(zip(map(str, TEMPS), np.bincount(v.argmax(axis=1), minlength=10).tolist())),
            'multiple_exact_maxima': int(((v == v.max(axis=1, keepdims=True)).sum(axis=1) > 1).sum()),
            'max_productivity_mean': float(v.max(axis=1).mean()),
            'nondecreasing_scenarios': int((np.diff(v, axis=1) >= 0).all(axis=1).sum())}
    result['endpoint_changes'] = {}
    for metric in METRICS:
        result['endpoint_changes'][metric] = {}
        for material in MATERIALS:
            v = data.loc[data[M] == material].pivot(index='scenario_id', columns=T, values=metric)[TEMPS].to_numpy()
            a, b = v[:, 0], v[:, -1]
            valid = np.isfinite(a) & np.isfinite(b)
            nonzero = valid & (a != 0)
            result['endpoint_changes'][metric][material] = {
                'percent_change_nonzero_baseline': quantiles((b[nonzero] / a[nonzero] - 1) * 100),
                'valid_pairs': int(valid.sum()), 'zero_baselines': int((valid & (a == 0)).sum()),
                'unchanged_fraction_valid_pairs': float(np.isclose(a[valid], b[valid], rtol=RTOL, atol=ATOL).mean()),
                'unchanged_entire_sweep': int(np.isclose(v, v[:, :1], rtol=RTOL, atol=ATOL).all(axis=1).sum())}
    ordered = np.sort(scores, axis=1)
    absolute = ordered[:, -1, :] - ordered[:, -2, :]
    relative = absolute / ordered[:, -2, :] * 100
    result['margins'] = {'absolute': quantiles(absolute.ravel()), 'relative_to_runner_pct': quantiles(relative.ravel()),
                         'relative_to_winner_pct': quantiles((absolute / ordered[:, -1, :] * 100).ravel()),
                         'below_1pct': int((relative < 1).sum()), 'below_5pct': int((relative < 5).sum()),
                         'per_temperature_min_relative_pct': relative.min(axis=0).tolist()}
    ratio = scores[:, 1, :] / scores[:, 2, :]
    factors = scores / scores[:, :, :1]
    spread = (factors.max(axis=1) / factors.min(axis=1) - 1) * 100
    result['temperature_factor_test'] = {
        'Cu_over_13X_range': [float(ratio.min()), float(ratio.max())],
        'ratio_endpoint_percent_change': quantiles((ratio[:, -1] / ratio[:, 0] - 1) * 100),
        'ratio_unchanged_entire_sweep': int(np.isclose(ratio, ratio[:, :1], rtol=RTOL, atol=ATOL).all(axis=1).sum()),
        'endpoint_factor_spread_pct': quantiles(spread[:, -1]),
        'all_materials_common_factor_entire_sweep': int(np.isclose(factors, factors[:, :1, :], rtol=RTOL, atol=ATOL).all(axis=(1, 2)).sum())}
    # Check the saved productivity equation directly against every raw row.
    implied = (1000 * gas['Molar Flow (Hydrogen)'].to_numpy()[data.scenario_id.to_numpy()]
               / data[MASS].max(axis=1).to_numpy())
    result['productivity_equation_mismatches'] = int((~np.isclose(implied, data[P], rtol=RTOL, atol=ATOL)).sum())
    # Targeted source-formula diagnostic: BP6 references BK5-BL5 (previous
    # gasifier row). Evaluate the same saved Cu CO equation with its own row;
    # this is arithmetic on existing coefficients, not a new process simulation.
    par = parameters_by_t[313.2]
    f = lambda k: float(par[k][0])
    partial = gas['Mole Frac (CO)'].to_numpy()[:, None] * f('I21')
    b = f('D30') * np.exp(f('D24') / (f('D32') * np.array([298.] + TEMPS)))
    uptake = f('D27') * b * partial / (1 + b * partial)
    local_capacity = uptake[:, :1] - uptake[:, 1:]
    local_mass = gas['Molar Flow (CO)'].to_numpy()[:, None] * .25 * 1000 / local_capacity
    previous_capacity = np.concatenate([local_capacity[:1], local_capacity[:-1]], axis=0)
    previous_mass = gas['Molar Flow (CO)'].to_numpy()[:, None] * .25 * 1000 / previous_capacity
    cu_mass = data.loc[data[M] == 'Cu-TDPAT'].set_index(['scenario_id', T])[MASS].reindex(
        pd.MultiIndex.from_product([range(n), TEMPS], names=['scenario_id', T])).to_numpy().reshape(n, 10, 3)
    saved_cu_co = cu_mass[:, :, 1].copy()
    cu_mass[:, :, 1] = local_mass
    corrected = scores.copy()
    corrected[:, 1, :] = 1000 * gas['Molar Flow (Hydrogen)'].to_numpy()[:, None] / cu_mass.max(axis=2)
    cw, cm = corrected.argmax(axis=1), corrected.mean(axis=2).argmax(axis=1)
    result['Cu_CO_source_diagnostic'] = {
        'saved_mass_matches_previous_row_capacity': int(np.isclose(saved_cu_co, previous_mass, rtol=RTOL, atol=ATOL).sum()),
        'saved_mass_differs_from_own_row_capacity': int((~np.isclose(saved_cu_co, local_mass, rtol=RTOL, atol=ATOL)).sum()),
        'own_row_CO_mass_percent_change': quantiles(((local_mass / saved_cu_co - 1) * 100).ravel()),
        'own_row_correction_fixed_winners_different_from_saved': int((cw != scores.argmax(axis=1)).sum()),
        'own_row_correction_fixed_vs_corrected_mean_changes': int((cw != cm[:, None]).sum()),
        'own_row_correction_mean_counts': dict(zip(MATERIALS, np.bincount(cm, minlength=3).tolist())),
        'own_row_correction_optimized_counts': dict(zip(MATERIALS, np.bincount(corrected.max(axis=2).argmax(axis=1), minlength=3).tolist()))}
    zero_methane = gas['Mole Frac (Methane)'].eq(0).to_numpy()
    result['methane_partition'] = {'zero_fraction_scenarios': int(zero_methane.sum()),
        'zero_fraction_positive_flow_scenarios': int((zero_methane & (gas['Molar Flow (Methane)'] > 0)).sum()),
        'winner_partition_mismatches': int((original_winner != np.where(zero_methane, 2, 1)).sum()),
        'zero_CH4_mass_matches_zero_fraction_all_rows': bool((data[MASS[0]].eq(0).to_numpy() == data['Mole Frac (Methane)'].eq(0).to_numpy()).all())
        if 'Mole Frac (Methane)' in data else bool((data[MASS[0]].eq(0).to_numpy() == zero_methane[data.scenario_id.to_numpy()]).all())}
    result['methane_partition']['Cu_over_13X_zero_fraction_range'] = [float(ratio[zero_methane].min()), float(ratio[zero_methane].max())]
    result['methane_partition']['Cu_over_13X_positive_fraction_range'] = [float(ratio[~zero_methane].min()), float(ratio[~zero_methane].max())]
    result['sample_productivity'] = {
        str(i): {'native': mapping.iloc[i].to_dict(), 'values_in_temperature_order':
                 dict(zip(MATERIALS, scores[i].tolist()))} for i in [0, 200, 20300]}
    result['controlling_mass_counts'] = data.assign(controlling=data[MASS].idxmax(axis=1)).groupby([M, T]).controlling.value_counts().to_dict()
    # Compact inspectable formula evidence, including upstream source defects.
    samples = samples_by_t[313.2]
    result['formula_evidence'] = {str(r): {c: samples[r][c] for c in
        ['BP', 'W', 'Z', 'BR', 'BU', 'DO', 'DR', 'DZ'] if c in samples[r]} for r in [5, 6, 205, n + 4]}
    tsa_formula_text = ' '.join(v[1] or '' for r in [5, 6] for c, v in samples[r].items()
                               if c in SCORE_COLS or c in ['N','O','P','Q','R','S','T','U','V',
                               'BI','BJ','BK','BL','BM','BN','BO','BP','BQ',
                               'DD','DE','DF','DG','DH','DI','DJ','DK','DL','DM','DN'])
    result['TSA_direct_parameter_references'] = sorted(set(re.findall(r'Sheet1!([A-Z]+\$?\d+)', tsa_formula_text)))
    refs = {ref.replace('$', '') for ref in result['TSA_direct_parameter_references']}
    require(refs & {'I2', 'I3', 'I20', 'I21', 'T18', 'T19'} == {'I3', 'I21', 'T19'},
            'Unexpected swept pressure dependency in sampled TSA formulas')
    require(not refs & {'E3', 'E21'}, 'Unexpected macro label-cell dependency')

    # Reconciliation is downstream only; no artifact supplies a scoring input.
    print('Independent calculations complete; reconciling existing exports', file=sys.stderr, flush=True)
    art = current / 'outputs/artifacts'
    mismatches = []

    def compare(name, ids, actual, expected):
        bad = ~np.isclose(actual, expected, rtol=1e-10, atol=1e-10, equal_nan=True) if np.asarray(expected).dtype.kind in 'fiu' else np.asarray(actual) != np.asarray(expected)
        mismatches.extend({'file_or_field': name, 'key': str(ids[i]), 'saved': str(actual[i]),
                           'independent': str(expected[i])} for i in np.flatnonzero(bad))

    reference = pd.read_csv(art / 'winner_map_data.csv').set_index('scenario_id').reindex(range(n))
    compare('winner_map_data.csv/winner_prod', list(range(n)), reference.winner_prod.to_numpy(), np.array(MATERIALS)[original_winner])
    for c in COORD:
        compare('winner_map_data.csv/' + c, list(range(n)), reference[c].to_numpy(), gas[c].to_numpy())
    saved = pd.read_csv(art / 'tsa_temperature/scenario_winner_maps.csv').set_index('scenario_id').reindex(range(n))
    for name, winners in strategies.items():
        compare('scenario_winner_maps.csv/' + name, list(range(n)), saved['winner_' + name].to_numpy(), np.array(MATERIALS)[winners])
        compare('scenario_winner_maps.csv/changed_' + name, list(range(n)), saved['changed_' + name].to_numpy(), winners != original_winner)
    summary = pd.read_csv(art / 'tsa_temperature/winner_summary.csv')
    for row in summary.to_dict('records'):
        name, material = row['strategy'], row[M]
        expected = result['strategies'][name]
        for c, value in [('winner_count', expected['counts'][material]), ('changed_scenarios', expected['changed']),
                         ('material_winner_tie_scenarios', expected['exact_material_ties'])]:
            compare('winner_summary.csv/' + c, [(name, material)], np.array([row[c]]), np.array([value]))
    transitions = pd.read_csv(art / 'tsa_temperature/winner_transitions.csv')
    for row in transitions.to_dict('records'):
        value = int(((original_winner == MATERIALS.index(row['original_winner'])) &
                     (strategies[row['strategy']] == MATERIALS.index(row['new_winner']))).sum())
        compare('winner_transitions.csv', [tuple(row.values())], np.array([row['scenario_count']]), np.array([value]))
    selected = pd.read_csv(art / 'tsa_temperature/strategy_selected_rows.csv')
    require(not selected.duplicated(['strategy', 'scenario_id']).any() and len(selected) == n * 12, 'Incomplete selected-row export')
    energy = data.set_index(keys)[E].reindex(index).to_numpy().reshape(n, 3, 10)
    counts = np.isfinite(energy).sum(axis=2)
    mean_energy = np.divide(np.nansum(energy, axis=2), counts,
                            out=np.full(counts.shape, np.nan), where=counts > 0)
    for name, group in selected.groupby('strategy'):
        group = group.set_index('scenario_id').reindex(range(n))
        w = strategies[name]
        tidx = scores.argmax(axis=2)[np.arange(n), w] if name == 'optimized' else None
        expected_p = means[np.arange(n), w] if name == 'original' else maxima[np.arange(n), w] if name == 'optimized' else scores[np.arange(n), w, list(strategies).index(name)-1]
        expected_t = np.full(n, np.nan) if name == 'original' else np.array(TEMPS)[tidx] if name == 'optimized' else np.full(n, TEMPS[list(strategies).index(name)-1])
        expected_e = mean_energy[np.arange(n), w] if name == 'original' else energy[np.arange(n), w, tidx] if name == 'optimized' else energy[np.arange(n), w, list(strategies).index(name)-1]
        for c, v in [(M, np.array(MATERIALS)[w]), (P, expected_p), (T, expected_t), (E, expected_e)]:
            compare('strategy_selected_rows.csv/' + name + '/' + c, list(range(n)), group[c].to_numpy(), v)
    psa = pd.read_csv(original / 'PSA_DATA.csv', usecols=['Unnamed: 0', M, 'P_adsorption'])
    require(psa[['Unnamed: 0', M]].equals(raw[['Unnamed: 0', M]]), 'PSA pairing alignment mismatch')
    pairs = pd.DataFrame({T: raw[T], 'PSA_P_adsorption_export': psa.P_adsorption}).drop_duplicates().sort_values(T)
    saved_pairs = pd.read_csv(art / 'tsa_temperature/export_sweep_pairs.csv').sort_values(T)
    require(np.array_equal(pairs.to_numpy(), saved_pairs.to_numpy()), 'Sweep-pair export mismatch')
    audit = json.loads((art / 'tsa_temperature/audit.json').read_text(encoding='utf-8'))
    require(audit['scenario_count'] == n and audit['calculation_rows'] == len(raw), 'Audit dimensions differ')
    require(all(audit['input_sha256'][name] == result['identity'][name]['current_sha256']
                for name in ['TSA_DATA.csv', 'book1.csv']), 'Audit input hashes differ')
    result['reconciliation'] = {'winner_map_cases': n, 'fixed_temperature_winner_cases': n * 10,
        'scenario_map_cases': n * 12, 'selected_rows': len(selected), 'summary_rows': len(summary),
        'transition_rows': len(transitions), 'sweep_pairs': len(pairs), 'discrepancies': mismatches}
    # JSON cannot represent tuple dictionary keys; retain groups as readable labels.
    result['controlling_mass_counts'] = {' / '.join(map(str, k)): v for k, v in result['controlling_mass_counts'].items()}
    result['verdict_saved_winners'] = 'PASS' if not discrepancies and not mismatches else 'FAIL'
    print(json.dumps(result, indent=2, default=lambda x: x.item() if isinstance(x, np.generic) else str(x), allow_nan=False))


if __name__ == '__main__':
    main()
