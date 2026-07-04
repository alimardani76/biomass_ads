#!/usr/bin/env python3
"""
sanity_check.py — pressure-test the paper against the reviewer critiques.

Runs 6 checks against your data:
    1. Gasifier composition variation ranges (Opus: atlas is not really an atlas)
    2. Molar flows per component (Opus: CH4 flow << CO2 flow)
    3. Adsorbent mass per impurity, per MOF (Opus: CH4-limited is artifact)
    4. Cross-check: how often is each impurity actually controlling?
    5. Winner-map share sanity (should reproduce 77% / 23% / 0%)
    6. ML metrics: are R2 values suspiciously perfect?

No plotting, no ML training. Just prints.

Run:
    python sanity_check.py
Or save to a file:
    python sanity_check.py > sanity_check_output.txt
"""

from pathlib import Path
import numpy as np
import pandas as pd


pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)


# ---------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR  = REPO_ROOT / "data"

GAS_CSV = DATA_DIR / "book1.csv"
TSA_CSV = DATA_DIR / "TSA_DATA.csv"


STEAM_COL = "Steam - Mass Flow"
TGAS_COL  = "Gasif-2 - Temperature"
TADS_COL  = "T_adsorption(K)"
MOF_COL   = "MOF type"

# Composition columns (mole fractions)
FRAC_COLS = ["Mole Frac (CO)",
             "Mole Frac (CO2)",
             "Mole Frac (Hydrogen)",
             "Mole Frac (Methane)"]

# Molar flow columns (candidates — script auto-detects which exist)
FLOW_CANDIDATES = [
    "Molar Flow (CO)", " Molar Flow (CO)",
    "Molar Flow (CO2)", " Molar Flow (CO2)",
    "Molar Flow (Hydrogen)", " Molar Flow (Hydrogen)",
    "Molar Flow (Methane)", " Molar Flow (Methane)",
]

MASS_COLS = ["MOF mass -CH4", "MOF mass -CO", "MOF mass -CO2"]

MOF_MAP = {
    "HKUST": "HKUST-1", "HKUST-1": "HKUST-1",
    "Cu-TDPAT": "Cu-TDPAT",
    "zeolit": "Zeolite 13X", "zeolite": "Zeolite 13X",
    "Zeolite13x": "Zeolite 13X", "Zeolite 13X": "Zeolite 13X",
}


def hdr(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# ---------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------
hdr("LOADING DATA")

gas = pd.read_csv(GAS_CSV)
gas.columns = gas.columns.str.strip()   # strip any leading/trailing spaces
print(f"book1.csv:      {len(gas):,} rows, {len(gas.columns)} columns")

tsa = pd.read_csv(TSA_CSV)
tsa.columns = tsa.columns.str.strip()
if tsa.columns[0].startswith("Unnamed"):
    tsa = tsa.drop(columns=tsa.columns[0])
tsa = tsa.ffill()
tsa[MOF_COL] = tsa[MOF_COL].astype(str).str.strip().map(
    lambda s: MOF_MAP.get(s, s))
print(f"TSA_DATA.csv:   {len(tsa):,} rows, {len(tsa.columns)} columns")


# ---------------------------------------------------------------------
# CHECK 1 — Composition ranges
# ---------------------------------------------------------------------
hdr("CHECK 1: GASIFIER COMPOSITION VARIATION\n"
    "Opus claim: 'variation is at the third decimal → not an atlas'")

present_frac = [c for c in FRAC_COLS if c in gas.columns]
missing_frac = [c for c in FRAC_COLS if c not in gas.columns]
if missing_frac:
    print(f"\n⚠ missing composition columns: {missing_frac}")

stats = pd.DataFrame({
    "min":   gas[present_frac].min(),
    "max":   gas[present_frac].max(),
    "range": gas[present_frac].max() - gas[present_frac].min(),
    "mean":  gas[present_frac].mean(),
    "std":   gas[present_frac].std(),
    "cv_%":  100 * gas[present_frac].std() /
             gas[present_frac].mean().replace(0, np.nan),
})
print("\nMole-fraction statistics across gasifier scenarios:")
print(stats.round(6))

print("\nSteam and gasifier T ranges:")
print(f"  {STEAM_COL:<25} {gas[STEAM_COL].min():.1f} - "
      f"{gas[STEAM_COL].max():.1f}  (std {gas[STEAM_COL].std():.1f})")
print(f"  {TGAS_COL:<25} {gas[TGAS_COL].min():.1f} - "
      f"{gas[TGAS_COL].max():.1f}  (std {gas[TGAS_COL].std():.1f})")

print("\n-- range-relative-to-mean verdict --")
print("   (values below 0.20 mean the composition is essentially fixed)")
for col in present_frac:
    rng = gas[col].max() - gas[col].min()
    mean = gas[col].mean()
    rel = rng / mean if mean != 0 else float('inf')
    flag = "⚠ NARROW" if rel < 0.2 else "OK"
    print(f"  {col:<25} range/mean = {rel:>7.3f}   {flag}")


# ---------------------------------------------------------------------
# CHECK 2 — Molar flows per component
# ---------------------------------------------------------------------
hdr("CHECK 2: MOLAR FLOWS BY COMPONENT\n"
    "Opus claim: 'CH4 flow is 3 orders below CO2 → CH4-limited is artifact'")

# Detect which flow columns actually exist (with or without leading space)
present_flow = []
for c in FLOW_CANDIDATES:
    if c in gas.columns and c not in present_flow:
        present_flow.append(c)
    elif c.strip() in gas.columns and c.strip() not in present_flow:
        present_flow.append(c.strip())

missing_flow = [
    "CO", "CO2", "Hydrogen", "Methane"
]
found_species = set()
for c in present_flow:
    for sp in missing_flow:
        if sp in c:
            found_species.add(sp)
missing_species = [sp for sp in missing_flow if sp not in found_species]

if missing_species:
    print(f"\n⚠ molar flow columns missing for: {missing_species}")

if not present_flow:
    print("\n⚠ no molar flow columns found — skipping Check 2")
else:
    flow_stats = pd.DataFrame({
        "min":  gas[present_flow].min(),
        "max":  gas[present_flow].max(),
        "mean": gas[present_flow].mean(),
        "std":  gas[present_flow].std(),
    })
    print("\nMolar flow statistics (kmol/h):")
    print(flow_stats.round(6))

    co2_cols = [c for c in present_flow if "CO2" in c]
    if co2_cols:
        ref = gas[co2_cols[0]].mean()
        print(f"\nRatio of mean impurity flow to CO2 (reference = "
              f"{ref:.4f} kmol/h):")
        for col in present_flow:
            if "CO2" in col:
                continue
            ratio = gas[col].mean() / ref if ref != 0 else float('inf')
            mag = int(np.floor(np.log10(max(abs(ratio), 1e-30))))
            print(f"  {col:<32} mean/CO2 = {ratio:.2e}  (10^{mag})")


# ---------------------------------------------------------------------
# CHECK 3 — Adsorbent mass per impurity, per MOF
# ---------------------------------------------------------------------
hdr("CHECK 3: ADSORBENT MASS PER IMPURITY, PER MOF\n"
    "Opus claim: 'm_ads_CH4 dwarfed by m_ads_CO2 → CH4-limited is artifact'")

missing_mass = [c for c in MASS_COLS if c not in tsa.columns]
if missing_mass:
    print(f"\n⚠ missing mass columns: {missing_mass}")

for mof in ["HKUST-1", "Cu-TDPAT", "Zeolite 13X"]:
    sub = tsa[tsa[MOF_COL] == mof]
    if len(sub) == 0:
        print(f"\n{mof}: no data")
        continue
    print(f"\n{mof}  ({len(sub):,} rows):")
    print(f"  {'target':<25} {'mean':>12} {'median':>12} "
          f"{'max':>12} {'min':>12}")
    for col in MASS_COLS:
        if col not in sub.columns:
            continue
        vals = sub[col].dropna()
        if len(vals) == 0:
            continue
        print(f"  {col:<25} {vals.mean():12.3e} {vals.median():12.3e} "
              f"{vals.max():12.3e} {vals.min():12.3e}")

    # Ratio of mean mass_CH4 to mean mass_CO2
    if "MOF mass -CH4" in sub.columns and "MOF mass -CO2" in sub.columns:
        r = sub["MOF mass -CH4"].mean() / sub["MOF mass -CO2"].mean()
        mag = int(np.floor(np.log10(max(abs(r), 1e-30))))
        print(f"  --> mean(m_ads_CH4) / mean(m_ads_CO2) = "
              f"{r:.2e}  (10^{mag})")

    # How often does each impurity actually control the bed?
    present_mass = [c for c in MASS_COLS if c in sub.columns]
    if len(present_mass) >= 2:
        max_col = sub[present_mass].idxmax(axis=1)
        counts = max_col.value_counts(normalize=True).mul(100).round(1)
        print(f"  --> controlling impurity share (by max mass):")
        for c, p in counts.items():
            print(f"        {c:<25} {p:>5.1f}%")


# ---------------------------------------------------------------------
# CHECK 4 — Which impurity actually limits Cu-TDPAT wins?
# ---------------------------------------------------------------------
hdr("CHECK 4: WHAT IS ACTUALLY LIMITING WHEN Cu-TDPAT WINS?\n"
    "Cross-check the paper's 'methane-influenced' claim.")

present_mass = [c for c in MASS_COLS if c in tsa.columns]
if len(present_mass) < 2:
    print("\n⚠ insufficient mass columns to compute limiting impurity")
else:
    tsa["limiting"] = tsa[present_mass].idxmax(axis=1).str.replace(
        "MOF mass -", "", regex=False)

    n_gas, n_tsa = len(gas), len(tsa)
    if n_tsa % n_gas != 0:
        print("\n⚠ TSA rows don't tile cleanly against gas rows")
    else:
        rep = n_tsa // n_gas
        tsa["scenario_id"] = np.tile(np.arange(n_gas), rep)

        # For each MOF, compute per-scenario average productivity to find winners
        if "Productivity-H2" in tsa.columns:
            agg = (tsa.groupby(["scenario_id", MOF_COL], as_index=False)
                   .agg(prod=("Productivity-H2", "mean")))
            prod = agg.pivot(index="scenario_id",
                             columns=MOF_COL, values="prod")
            need = ["HKUST-1", "Cu-TDPAT", "Zeolite 13X"]
            for c in need:
                if c not in prod.columns:
                    prod[c] = np.nan
            prod = prod[need]
            winner = np.array(prod.columns)[np.argmax(prod.to_numpy(), axis=1)]
            winner_by_scenario = pd.Series(winner, index=prod.index,
                                           name="winner")

            # Per-adsorbent summary
            for mof in need:
                sub = tsa[tsa[MOF_COL] == mof]
                if len(sub) == 0:
                    continue
                # Merge in which scenarios that MOF actually won
                sub = sub.merge(winner_by_scenario, left_on="scenario_id",
                                right_index=True)
                won = sub[sub["winner"] == mof]

                print(f"\n{mof}:")
                print(f"  scenarios where it wins productivity: "
                      f"{won['scenario_id'].nunique():,} "
                      f"({100*won['scenario_id'].nunique()/n_gas:.1f}%)")
                if len(won) > 0:
                    lim_shares = (won["limiting"].value_counts(normalize=True)
                                  .mul(100).round(1))
                    print(f"  when it wins, controlling impurity is:")
                    for c, p in lim_shares.items():
                        print(f"        {c:<10} {p:>5.1f}%")


# ---------------------------------------------------------------------
# CHECK 5 — Winner map share reproduction
# ---------------------------------------------------------------------
hdr("CHECK 5: WINNER-MAP SHARE SANITY\n"
    "Should reproduce ~77% Zeolite 13X, ~23% Cu-TDPAT, ~0% HKUST-1")

if "Productivity-H2" not in tsa.columns:
    print("\n⚠ Productivity-H2 column missing")
elif "scenario_id" not in tsa.columns:
    print("\n⚠ scenario_id not built (Check 4 failed earlier)")
else:
    agg = (tsa.groupby(["scenario_id", MOF_COL], as_index=False)
              .agg(prod=("Productivity-H2", "mean")))
    prod = agg.pivot(index="scenario_id", columns=MOF_COL, values="prod")
    need = ["HKUST-1", "Cu-TDPAT", "Zeolite 13X"]
    for c in need:
        if c not in prod.columns:
            prod[c] = np.nan
    prod = prod[need]
    winner = pd.Series(np.array(prod.columns)[np.argmax(prod.to_numpy(), axis=1)])
    share = winner.value_counts(normalize=True).mul(100).round(1)
    print("\nWinner shares by productivity:")
    for m, p in share.items():
        print(f"  {m:<15} {p:>5.1f}%")


# ---------------------------------------------------------------------
# CHECK 6 — ML metrics from cache
# ---------------------------------------------------------------------
hdr("CHECK 6: ML METRICS FROM CACHE\n"
    "Opus claim: 'R² = 1.0000 = XGBoost memorizing algebraic identity'")


metrics_paths = [
    REPO_ROOT / "outputs" / "artifacts" / "xgb_metrics.csv",
]

loaded = None
for p in metrics_paths:
    if p.exists():
        loaded = pd.read_csv(p)
        print(f"\nloaded from: {p}")
        break

if loaded is None:
    print("\n⚠ xgb_metrics.csv not found — skipping Check 6")
else:
    show = loaded.copy()
    show["R2_exact"] = show["R2"].map(lambda v: f"{v:.6f}")
    print("\nfull metrics table (R² rounded to 6 decimals):")
    cols_to_show = [c for c in ["split", "target", "R2_exact",
                                "MAE", "RMSE", "n_test"]
                    if c in show.columns]
    print(show[cols_to_show].to_string(index=False))

    saturated = show[show["R2"] > 0.9999]
    if len(saturated) > 0:
        print(f"\ntargets with R² > 0.9999 (candidate 'memorization'):")
        for _, row in saturated.iterrows():
            print(f"  {row['split']:<10} {row['target']:<25} "
                  f"R² = {row['R2_exact']}")
    else:
        print("\nno targets with R² > 0.9999 — no memorization signature")


# ---------------------------------------------------------------------
hdr("DONE.  Send the full stdout back for interpretation.")
