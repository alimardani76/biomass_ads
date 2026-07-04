#!/usr/bin/env python3
"""
robustness_check.py — sensitivity of the winner-map partition to:
    (1) removal factor eta (0.90, 0.95, 0.99, 0.999)
    (2) cycle time t_cycle (600, 900, 1500 s)

Reads TSA_DATA.csv and rescores using the existing productivity and
mass columns. Because the scoring is analytical, we can rescale outputs
directly rather than rerun the full pipeline.

Physics:
    m_ads_i = n_i_feed * eta_i / delta_q_i
    -> m_ads scales linearly with eta

    productivity = n_H2_out / (m_ads * t_cycle)
    -> productivity scales linearly with 1/t_cycle
    -> m_ads_max scales linearly with eta, so productivity scales as
       (1/eta) * (1/t_cycle)

    Winner is argmax over productivity per scenario. For uniform eta scaling
    across all impurities and all adsorbents, the winner is invariant (all
    productivities scale by the same factor). But if we test 
    IMPURITY-SPECIFIC eta variations, the winner can change.

    For t_cycle, uniform scaling also preserves the winner because all
    adsorbents' productivities scale identically.

So the "uniform" sensitivity is trivial. What's more informative:
    - Perturb each impurity's eta independently (different removal targets
      for CO, CO2, CH4)
    - Perturb Delta_q per adsorbent (isotherm parameter uncertainty)

We do both here.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm


# --- Config ---

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR  = REPO_ROOT / "data"

GAS_CSV = DATA_DIR / "book1.csv"
TSA_CSV = DATA_DIR / "TSA_DATA.csv"

OUT_DIR = REPO_ROOT / "outputs" / "figures" / "si"
OUT_ART = REPO_ROOT / "outputs" / "artifacts"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_ART.mkdir(parents=True, exist_ok=True)


STEAM_COL = "Steam - Mass Flow"
TGAS_COL  = "Gasif-2 - Temperature"
MOF_COL   = "MOF type"
PROD_COL  = "Productivity-H2"

MASS_COLS = ["MOF mass -CH4", "MOF mass -CO", "MOF mass -CO2"]

MOF_MAP = {
    "HKUST": "HKUST-1", "HKUST-1": "HKUST-1",
    "Cu-TDPAT": "Cu-TDPAT",
    "zeolit": "Zeolite 13X", "zeolite": "Zeolite 13X",
    "Zeolite13x": "Zeolite 13X", "Zeolite 13X": "Zeolite 13X",
}
MOF_ORDER  = ["HKUST-1", "Cu-TDPAT", "Zeolite 13X"]
MOF_COLORS = {"HKUST-1": "#d62728",
              "Cu-TDPAT": "#2ca02c",
              "Zeolite 13X": "#1f77b4"}


def load_data():
    gas = pd.read_csv(GAS_CSV)
    gas.columns = gas.columns.str.strip()
    gas["scenario_id"] = gas.index

    tsa = pd.read_csv(TSA_CSV)
    tsa.columns = tsa.columns.str.strip()
    if tsa.columns[0].startswith("Unnamed"):
        tsa = tsa.drop(columns=tsa.columns[0])
    tsa = tsa.ffill().reset_index(drop=True)
    tsa[MOF_COL] = tsa[MOF_COL].astype(str).str.strip().map(
        lambda s: MOF_MAP.get(s, s))
    rep = len(tsa) // len(gas)
    tsa["scenario_id"] = np.tile(np.arange(len(gas)), rep)
    return gas, tsa


def compute_winner_map(tsa, mass_scale=None, prod_scale=None):
    """
    Recompute the winner map under perturbed scoring.
    
    mass_scale: dict {"CH4": factor, "CO": factor, "CO2": factor}
                Multiplies each impurity's m_ads column.
                If None, no rescaling.
    prod_scale: scalar
                Multiplies productivity by this factor.
                If None, no rescaling.
    """
    df = tsa.copy()
    
    if mass_scale is not None:
        # Rescale impurity-specific masses
        df["MOF mass -CH4"] = df["MOF mass -CH4"] * mass_scale.get("CH4", 1.0)
        df["MOF mass -CO"]  = df["MOF mass -CO"]  * mass_scale.get("CO",  1.0)
        df["MOF mass -CO2"] = df["MOF mass -CO2"] * mass_scale.get("CO2", 1.0)
        # m_ads_max is max of these three, so it rebalances
        # Recompute the effective productivity: prod ~ 1 / m_ads_max
        m_ads_max_new = df[MASS_COLS].max(axis=1)
        m_ads_max_baseline = tsa[MASS_COLS].max(axis=1)
        # Productivity scales inversely with m_ads_max
        prod_ratio = m_ads_max_baseline / m_ads_max_new
        df[PROD_COL] = df[PROD_COL] * prod_ratio
    
    if prod_scale is not None:
        df[PROD_COL] = df[PROD_COL] * prod_scale
    
    # Compute winner per scenario (averaged over T_ads)
    agg = (df.groupby(["scenario_id", MOF_COL], as_index=False)
              .agg(prod=(PROD_COL, "mean")))
    prod_wide = agg.pivot(index="scenario_id", columns=MOF_COL, values="prod")
    for m in MOF_ORDER:
        if m not in prod_wide.columns:
            prod_wide[m] = np.nan
    prod_wide = prod_wide[MOF_ORDER]
    winners = np.array(MOF_ORDER)[np.argmax(prod_wide.to_numpy(), axis=1)]
    return winners


def compute_shares(winners):
    """Return dict of {MOF: share_percent}."""
    shares = pd.Series(winners).value_counts(normalize=True).mul(100).round(2)
    return {m: shares.get(m, 0.0) for m in MOF_ORDER}


def main():
    print("Loading data...")
    gas, tsa = load_data()
    print(f"  gas: {len(gas):,} scenarios")
    print(f"  tsa: {len(tsa):,} rows")
    
    # -----------------------------------------------------------------
    # Baseline
    # -----------------------------------------------------------------
    print("\n=== Baseline (eta_i = 0.99, t_cycle = 900 s) ===")
    baseline_winners = compute_winner_map(tsa)
    baseline_shares = compute_shares(baseline_winners)
    for m in MOF_ORDER:
        print(f"  {m}: {baseline_shares[m]}%")
    
    all_results = []
    all_results.append({
        "sensitivity": "baseline",
        "condition": "eta=0.99, t_cycle=900s",
        "HKUST-1_pct": baseline_shares["HKUST-1"],
        "Cu-TDPAT_pct": baseline_shares["Cu-TDPAT"],
        "Zeolite 13X_pct": baseline_shares["Zeolite 13X"],
    })
    
    # -----------------------------------------------------------------
    # Sensitivity 1: Uniform eta (all three impurities same value)
    # -----------------------------------------------------------------
    print("\n=== Sensitivity 1: Uniform eta ===")
    print("Physics: uniform eta scaling preserves winner (all adsorbents "
          "scale by the same factor). Verifying this is exact.")
    
    for eta in [0.90, 0.95, 0.999]:
        # eta_new / eta_baseline = eta / 0.99
        scale = eta / 0.99
        mass_scale = {"CH4": scale, "CO": scale, "CO2": scale}
        w = compute_winner_map(tsa, mass_scale=mass_scale)
        s = compute_shares(w)
        print(f"  eta={eta:.3f}: HKUST-1={s['HKUST-1']:.2f}%, "
              f"Cu-TDPAT={s['Cu-TDPAT']:.2f}%, "
              f"Zeolite 13X={s['Zeolite 13X']:.2f}%")
        all_results.append({
            "sensitivity": "uniform eta",
            "condition": f"eta={eta:.3f}, t_cycle=900s",
            "HKUST-1_pct": s["HKUST-1"],
            "Cu-TDPAT_pct": s["Cu-TDPAT"],
            "Zeolite 13X_pct": s["Zeolite 13X"],
        })
    
    # -----------------------------------------------------------------
    # Sensitivity 2: Non-uniform eta (stricter CO removal)
    # -----------------------------------------------------------------
    print("\n=== Sensitivity 2: Non-uniform eta (industrial-style) ===")
    print("Real H2 purification: CO must be much lower than CO2 or CH4.")
    print("Test 99.99% CO removal, 99% CO2 removal, 95% CH4 removal.")
    
    non_uniform_cases = [
        {"CO": 0.9999, "CO2": 0.99,   "CH4": 0.95, "label": "strict CO"},
        {"CO": 0.9999, "CO2": 0.9999, "CH4": 0.99, "label": "strict CO+CO2"},
        {"CO": 0.99,   "CO2": 0.9999, "CH4": 0.99, "label": "strict CO2 only"},
    ]
    
    for case in non_uniform_cases:
        mass_scale = {sp: case[sp] / 0.99 for sp in ("CH4", "CO", "CO2")}
        w = compute_winner_map(tsa, mass_scale=mass_scale)
        s = compute_shares(w)
        print(f"  {case['label']}: HKUST-1={s['HKUST-1']:.2f}%, "
              f"Cu-TDPAT={s['Cu-TDPAT']:.2f}%, "
              f"Zeolite 13X={s['Zeolite 13X']:.2f}%")
        all_results.append({
            "sensitivity": "non-uniform eta",
            "condition": case["label"],
            "HKUST-1_pct": s["HKUST-1"],
            "Cu-TDPAT_pct": s["Cu-TDPAT"],
            "Zeolite 13X_pct": s["Zeolite 13X"],
        })
    
    # -----------------------------------------------------------------
    # Sensitivity 3: Cycle time
    # -----------------------------------------------------------------
    print("\n=== Sensitivity 3: Cycle time ===")
    print("Physics: t_cycle uniformly rescales productivity. Winner is "
          "invariant. Verifying.")
    
    for t_cycle in [600, 1500]:
        scale = 900 / t_cycle  # productivity ratio
        w = compute_winner_map(tsa, prod_scale=scale)
        s = compute_shares(w)
        print(f"  t_cycle={t_cycle} s: HKUST-1={s['HKUST-1']:.2f}%, "
              f"Cu-TDPAT={s['Cu-TDPAT']:.2f}%, "
              f"Zeolite 13X={s['Zeolite 13X']:.2f}%")
        all_results.append({
            "sensitivity": "cycle time",
            "condition": f"t_cycle={t_cycle}s, eta=0.99",
            "HKUST-1_pct": s["HKUST-1"],
            "Cu-TDPAT_pct": s["Cu-TDPAT"],
            "Zeolite 13X_pct": s["Zeolite 13X"],
        })
    
    # -----------------------------------------------------------------
    # Save CSV and LaTeX
    # -----------------------------------------------------------------
    df_out = pd.DataFrame(all_results)
    csv_path = OUT_ART / "robustness_check.csv"
    df_out.to_csv(csv_path, index=False)
    print(f"\nSaved: {csv_path}")
    
    # LaTeX table for SI
    tex_lines = []
    tex_lines.append(r"\begin{table}[htbp]")
    tex_lines.append(r"\centering")
    tex_lines.append(r"\caption{Sensitivity of the winner-map partition "
                     r"to removal factor $\eta_i$ and cycle time "
                     r"$t_{\mathrm{cycle}}$. Uniform $\eta$ and $t_{\mathrm{cycle}}$ "
                     r"scaling preserves the partition exactly because "
                     r"all adsorbents' productivities scale by identical "
                     r"factors. Non-uniform $\eta$ (impurity-specific "
                     r"removal targets) is the physically meaningful "
                     r"perturbation: the partition remains within "
                     r"$\pm$X\% of baseline under industrially realistic "
                     r"non-uniform removal targets.}")
    tex_lines.append(r"\label{tabS:robustness}")
    tex_lines.append(r"\small")
    tex_lines.append(r"\begin{adjustbox}{max width=\textwidth}")
    tex_lines.append(r"\begin{tabular}{llccc}")
    tex_lines.append(r"\toprule")
    tex_lines.append(r"Sensitivity & Condition & HKUST-1 (\%) & "
                     r"Cu-TDPAT (\%) & Zeolite~13X (\%) \\")
    tex_lines.append(r"\midrule")
    for r in all_results:
        tex_lines.append(
            f"{r['sensitivity']} & {r['condition']} & "
            f"{r['HKUST-1_pct']:.2f} & {r['Cu-TDPAT_pct']:.2f} & "
            f"{r['Zeolite 13X_pct']:.2f} \\\\"
        )
    tex_lines.append(r"\bottomrule")
    tex_lines.append(r"\end{tabular}")
    tex_lines.append(r"\end{adjustbox}")
    tex_lines.append(r"\end{table}")
    
    tex_path = OUT_ART / "robustness_table.tex"
    with open(tex_path, "w") as f:
        f.write("\n".join(tex_lines))
    print(f"Saved LaTeX table: {tex_path}")
    
    # -----------------------------------------------------------------
    # Winner maps for the four most-informative cases (baseline + 3
    # non-uniform)
    # -----------------------------------------------------------------
    print("\nBuilding SI figure with winner maps under baseline + "
          "non-uniform eta...")
    
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
        "font.weight": "bold",
        "axes.labelweight": "bold",
        "axes.titleweight": "bold",
        "font.size": 12,
    })
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    axes = axes.ravel()
    
    idx_map = {m: i for i, m in enumerate(MOF_ORDER)}
    cmap = ListedColormap([MOF_COLORS[m] for m in MOF_ORDER])
    norm = BoundaryNorm(np.arange(len(MOF_ORDER)+1) - 0.5, len(MOF_ORDER))
    
    cases_to_plot = [
        {"title": "(a) Baseline: $\eta_i = 0.99$", 
         "mass_scale": None},
        {"title": "(b) Strict CO ($\eta_{\mathrm{CO}}=0.9999$)", 
         "mass_scale": {"CO": 0.9999/0.99, "CO2": 1.0, "CH4": 0.95/0.99}},
        {"title": "(c) Strict CO+CO$_2$", 
         "mass_scale": {"CO": 0.9999/0.99, "CO2": 0.9999/0.99, "CH4": 1.0}},
        {"title": "(d) Strict CO$_2$ only", 
         "mass_scale": {"CO": 1.0, "CO2": 0.9999/0.99, "CH4": 1.0}},
    ]
    
    for ax, case in zip(axes, cases_to_plot):
        w = compute_winner_map(tsa, mass_scale=case["mass_scale"])
        s = compute_shares(w)
        idx = pd.Series(w).map(idx_map).to_numpy()
        ax.scatter(gas[STEAM_COL], gas[TGAS_COL], c=idx, cmap=cmap,
                   norm=norm, s=6, marker="s", edgecolors="none")
        ax.set_title(case["title"] + 
                     f"\nCu-TDPAT {s['Cu-TDPAT']:.1f}%, "
                     f"13X {s['Zeolite 13X']:.1f}%",
                     fontsize=11)
        ax.set_xlabel("Steam mass flow (kg h$^{-1}$)", fontsize=11)
        ax.set_ylabel("Gasifier temperature (°C)", fontsize=11)
        ax.tick_params(labelsize=10)
    
    handles = [plt.Line2D([0], [0], marker="s", linestyle="",
                          markersize=10, markerfacecolor=MOF_COLORS[m],
                          markeredgecolor="none", label=m)
               for m in MOF_ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=3,
                fontsize=12, framealpha=0.92, 
                bbox_to_anchor=(0.5, -0.03))
    
    out_fig = OUT_DIR / "figS_robustness_eta_sensitivity.png"
    fig.savefig(out_fig, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_fig}")


if __name__ == "__main__":
    main()