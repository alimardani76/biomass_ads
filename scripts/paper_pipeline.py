#!/usr/bin/env python3
"""
paper_pipeline.py — monolithic reproduction pipeline for the paper.

Regenerates all six data-derived figures. Trains XGBoost once, saves everything,
then reuses cached models on subsequent runs unless --retrain is passed.

USAGE
    First run (trains, ~2 min):
        python paper_pipeline.py
    Subsequent runs (uses cache, ~30 sec):
        python paper_pipeline.py
    Force retrain:
        python paper_pipeline.py --retrain
    Single stage only:
        python paper_pipeline.py --stage kde

CACHE (outputs/artifacts/)
    models/                  XGBoost native JSON per (target, split)
    xgb_metrics.csv          held-out R2 / MAE / RMSE
    xgb_predictions_all.csv  y_true / y_pred for parity plots
    shap_mean_abs_all.csv    TreeSHAP mean |contribution|
    xgb_model_card.json      config manifest

FIGURES
    outputs/figures/main/
        fig2_winner_map.png
        fig3_syngas_composition_maps.png
        fig4_energy_productivity_tradeoff.png
        fig5_productivity_distributions.png
        fig6_treeshap_grouped.png
        fig7_adsorbent_mass_scaling.png
    outputs/figures/si/
        figS_xgb_parity_random.png
        figS_xgb_parity_grouped.png
"""

from __future__ import annotations
import argparse, gc, json, warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR  = REPO_ROOT / "data"
OUT       = REPO_ROOT / "outputs"

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import ListedColormap, BoundaryNorm, LogNorm
from scipy.optimize import curve_fit

from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor
import xgboost as xgb


# =====================================================================
# CONFIG
# =====================================================================



GAS_CSV = DATA_DIR / "book1.csv"
TSA_CSV = DATA_DIR / "TSA_DATA.csv"

OUT       = REPO_ROOT / "outputs"
FIG_MAIN  = OUT / "figures" / "main"
FIG_SI    = OUT / "figures" / "si"
ART       = OUT / "artifacts"
MODELS    = ART / "models"

for d in (FIG_MAIN, FIG_SI, ART, MODELS):
    d.mkdir(parents=True, exist_ok=True)

STEAM_COL = "Steam - Mass Flow"
TGAS_COL  = "Gasif-2 - Temperature"        # °C
TADS_COL  = "T_adsorption(K)"              # K
MOF_COL   = "MOF type"

FRAC_COLS = ["Mole Frac (CO)", "Mole Frac (CO2)",
             "Mole Frac (Hydrogen)", "Mole Frac (Methane)"]

TARGETS = [
    "MOF mass -CH4",
    "MOF mass -CO",
    "MOF mass -CO2",
    "Productivity-H2",
    "Energy Consumption",
]

TARGET_LABELS = {
    "MOF mass -CH4":      r"$m_{\mathrm{ads},\mathrm{CH_4}}$ (kg)",
    "MOF mass -CO":       r"$m_{\mathrm{ads},\mathrm{CO}}$ (kg)",
    "MOF mass -CO2":      r"$m_{\mathrm{ads},\mathrm{CO_2}}$ (kg)",
    "Productivity-H2":    r"$\Pi_{\mathrm{H_2}}$ (mol kg$^{-1}$ h$^{-1}$)",
    "Energy Consumption": r"$E_{\mathrm{reg}}$ (MJ kg$_{\mathrm{H_2}}^{-1}$)",
}

FRAC_LABELS = {
    "Mole Frac (CO)":       r"x(CO)",
    "Mole Frac (CO2)":      r"x(CO$_2$)",
    "Mole Frac (Hydrogen)": r"x(H$_2$)",
    "Mole Frac (Methane)":  r"x(CH$_4$)",
}
FRAC_PANEL_ORDER  = ["Mole Frac (Hydrogen)", "Mole Frac (CO2)",
                     "Mole Frac (Methane)",  "Mole Frac (CO)"]
FRAC_PANEL_LETTER = {"Mole Frac (Hydrogen)": "(a)",
                     "Mole Frac (CO2)":      "(b)",
                     "Mole Frac (Methane)":  "(c)",
                     "Mole Frac (CO)":       "(d)"}

MOF_MAP = {
    "HKUST":       "HKUST-1",  "HKUST-1":     "HKUST-1",
    "Cu-TDPAT":    "Cu-TDPAT",
    "zeolit":      "Zeolite 13X", "zeolite": "Zeolite 13X",
    "Zeolite13x":  "Zeolite 13X", "Zeolite 13X": "Zeolite 13X",
}
MOF_ORDER  = ["HKUST-1", "Cu-TDPAT", "Zeolite 13X"]
MOF_COLORS = {"HKUST-1": "#d62728",
              "Cu-TDPAT": "#2ca02c",
              "Zeolite 13X": "#1f77b4"}

FEATURE_LABELS = {
    STEAM_COL:            "Steam mass flow",
    TGAS_COL:             "Gasifier T",
    TADS_COL:             r"$T_{\mathrm{ads}}$",
    "ads_HKUST-1":        "ads. = HKUST-1",
    "ads_Cu-TDPAT":       "ads. = Cu-TDPAT",
    "ads_Zeolite 13X":    "ads. = Zeolite 13X",
}

# Tableau-10 qualitative palette — colorblind-safe, print-safe
FEATURE_COLORS = {
    STEAM_COL:          "#e15759",   # coral red
    TGAS_COL:           "#4e79a7",   # deep blue
    TADS_COL:           "#59a14f",   # forest green
    "ads_HKUST-1":      "#f28e2b",   # warm orange
    "ads_Cu-TDPAT":     "#b07aa1",   # muted purple
    "ads_Zeolite 13X":  "#edc948",   # mustard
}

RANDOM_STATE  = 442
TEST_FRACTION = 0.15
SHAP_MAX_N    = 3000

XGB_PARAMS = dict(
    n_estimators=600, max_depth=5, learning_rate=0.04,
    subsample=0.85, colsample_bytree=0.85,
    objective="reg:squarederror",
    random_state=RANDOM_STATE, n_jobs=-1,
    reg_lambda=1.0, reg_alpha=0.0, tree_method="hist",
)

METRICS_CSV = ART / "xgb_metrics.csv"
PREDS_CSV   = ART / "xgb_predictions_all.csv"
SHAP_CSV    = ART / "shap_mean_abs_all.csv"
CARD_JSON   = ART / "xgb_model_card.json"


# =====================================================================
# STYLE
# =====================================================================

def _style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
        "font.weight": "bold",
        "axes.labelweight": "bold",
        "axes.titleweight": "bold",
        "font.size": 12,
        "axes.titlesize": 13,
        "axes.labelsize": 13,
        "legend.fontsize": 11,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    })


def _panel_label(ax, letter):
    """Bold panel letter at top-left, above the axes."""
    ax.text(
        -0.02, 1.08, letter,
        transform=ax.transAxes,
        ha="left", va="bottom",
        fontsize=26, fontweight="bold",
        family="Arial",
    )


# =====================================================================
# DATA LOADING
# =====================================================================

def load_data():
    gas = pd.read_csv(GAS_CSV)
    gas.columns = gas.columns.str.strip()
    gas["scenario_id"] = gas.index

    tsa = pd.read_csv(TSA_CSV)
    tsa.columns = tsa.columns.str.strip()
    if tsa.columns[0].startswith("Unnamed"):
        tsa = tsa.drop(columns=tsa.columns[0])
    tsa = tsa.ffill().reset_index(drop=True)

    n_gas, n_tsa = len(gas), len(tsa)
    if n_tsa % n_gas != 0:
        raise ValueError(f"TSA rows ({n_tsa}) not multiple of gas rows ({n_gas})")
    rep = n_tsa // n_gas
    print(f"[load] gas={n_gas} tsa={n_tsa} repeats/scenario={rep}")

    scenario_ids = np.tile(gas["scenario_id"].to_numpy(), rep)
    gas_rep = pd.concat(
        [gas[FRAC_COLS + [STEAM_COL, TGAS_COL]]] * rep, ignore_index=True)

    df = pd.concat([pd.DataFrame({"scenario_id": scenario_ids}),
                    gas_rep.reset_index(drop=True),
                    tsa], axis=1)
    df = df.loc[:, ~df.columns.duplicated()].copy()

    df[MOF_COL] = df[MOF_COL].astype(str).str.strip().map(
        lambda s: MOF_MAP.get(s, s))
    unk = set(df[MOF_COL].unique()) - set(MOF_ORDER)
    if unk:
        raise ValueError(f"Unknown adsorbent labels: {unk}")

    df["limiting"] = df[["MOF mass -CH4", "MOF mass -CO", "MOF mass -CO2"]] \
        .idxmax(axis=1).str.replace("MOF mass -", "", regex=False)

    return gas, df


# =====================================================================
# FIG 2 — WINNER MAP
# =====================================================================

def stage_winner(gas, df):
    _style()
    print("[winner] Fig 2")

    agg = (df.groupby(["scenario_id", MOF_COL], as_index=False)
             .agg(prod=("Productivity-H2", "mean"),
                  energy=("Energy Consumption", "mean")))
    agg["prod_per_e"] = agg["prod"] / agg["energy"]

    prod = agg.pivot(index="scenario_id", columns=MOF_COL, values="prod")[MOF_ORDER]
    ppe  = agg.pivot(index="scenario_id", columns=MOF_COL, values="prod_per_e")[MOF_ORDER]

    win_prod = np.array(MOF_ORDER)[np.argmax(prod.to_numpy(), axis=1)]
    win_ppe  = np.array(MOF_ORDER)[np.argmax(ppe.to_numpy(),  axis=1)]

    result = gas[["scenario_id", STEAM_COL, TGAS_COL]].copy()
    result["winner_prod"] = win_prod
    result["winner_ppe"]  = win_ppe
    result.to_csv(ART / "winner_map_data.csv", index=False)

    print("  share (Π):    ",
          dict(pd.Series(win_prod).value_counts(normalize=True).mul(100).round(1)))
    print("  share (Π/E):  ",
          dict(pd.Series(win_ppe).value_counts(normalize=True).mul(100).round(1)))

    def _idx(s):
        return pd.Series(s).map({m: i for i, m in enumerate(MOF_ORDER)}).to_numpy()

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2), constrained_layout=True)
    kwargs = dict(
        s=8, marker="s", edgecolors="none",
        cmap=ListedColormap([MOF_COLORS[m] for m in MOF_ORDER]),
        norm=BoundaryNorm(np.arange(len(MOF_ORDER)+1) - 0.5, len(MOF_ORDER)),
    )
    axes[0].scatter(result[STEAM_COL], result[TGAS_COL], c=_idx(win_prod), **kwargs)
    axes[0].set_xlabel("Steam mass flow (kg h$^{-1}$)", fontsize=17)
    axes[0].set_ylabel("Gasifier temperature (°C)", fontsize=17)
    axes[0].tick_params(axis="both", labelsize=14)
    _panel_label(axes[0], "(a)")

    axes[1].scatter(result[STEAM_COL], result[TGAS_COL], c=_idx(win_ppe), **kwargs)
    axes[1].set_xlabel("Steam mass flow (kg h$^{-1}$)", fontsize=17)
    axes[1].tick_params(axis="both", labelsize=14)
    _panel_label(axes[1], "(b)")

    handles = [plt.Line2D([0], [0], marker="s", linestyle="", markersize=10,
                          markerfacecolor=MOF_COLORS[m], markeredgecolor="none",
                          label=m) for m in MOF_ORDER]
    axes[0].legend(handles=handles, loc="upper right",
                   framealpha=0.92, fontsize=14)

    fig.savefig(FIG_MAIN / "fig2_winner_map.png")
    plt.close(fig)


# =====================================================================
# FIG 3 — SYNGAS COMPOSITION MAPS
# =====================================================================

def stage_compose(gas):
    _style()
    print("[compose] Fig 3")

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 10), constrained_layout=True)
    for ax, col in zip(axes.ravel(), FRAC_PANEL_ORDER):
        sc = ax.scatter(gas[STEAM_COL], gas[TGAS_COL],
                        c=gas[col], cmap="viridis", s=8, edgecolors="none")
        cb = fig.colorbar(sc, ax=ax, shrink=0.85)
        cb.set_label(FRAC_LABELS[col], fontsize=15)
        cb.ax.tick_params(labelsize=12)
        ax.set_xlabel("Steam mass flow (kg h$^{-1}$)", fontsize=16)
        ax.set_ylabel("Gasifier temperature (°C)", fontsize=16)
        ax.tick_params(axis="both", labelsize=13)
        _panel_label(ax, FRAC_PANEL_LETTER[col])

    fig.savefig(FIG_MAIN / "fig3_syngas_composition_maps.png")
    plt.close(fig)


# =====================================================================
# FIG 4 — ENERGY–PRODUCTIVITY ENVELOPES
# =====================================================================

def stage_envelope(df):
    _style()
    print("[envelope] Fig 4")

    row_order = ["Cu-TDPAT", "HKUST-1", "Zeolite 13X"]
    row_letters = {"Cu-TDPAT":    ("(a)", "(b)"),
                   "HKUST-1":     ("(c)", "(d)"),
                   "Zeolite 13X": ("(e)", "(f)")}
    limits = ["CH4", "CO"]

    tads_values = sorted(df[TADS_COL].unique())
    n_tads = len(tads_values)
    base = plt.get_cmap("viridis", n_tads)
    discrete_colors = [base(i) for i in range(n_tads)]
    disc_cmap = ListedColormap(discrete_colors)
    disc_norm = BoundaryNorm(np.arange(n_tads + 1) - 0.5, n_tads)
    tads_to_idx = {v: i for i, v in enumerate(tads_values)}

    fig, axes = plt.subplots(3, 2, figsize=(12, 13.5), constrained_layout=True,gridspec_kw={'width_ratios': [1, 1]})
    for r, mof in enumerate(row_order):
        for c, lim in enumerate(limits):
            ax = axes[r, c]
            sub = df[(df[MOF_COL] == mof) & (df["limiting"] == lim)]
            if len(sub) == 0:
                ax.set_axis_off(); continue
            color_idx = sub[TADS_COL].map(tads_to_idx).to_numpy()
            sc = ax.scatter(sub["Productivity-H2"], sub["Energy Consumption"],
                            c=color_idx, cmap=disc_cmap, norm=disc_norm,
                            s=6, alpha=0.75, edgecolors="none")
            if c == 1:
                cbar = fig.colorbar(sc, ax=ax, shrink=0.85,
                                    ticks=np.arange(n_tads))
                cbar.ax.set_yticklabels([f"{v:.0f}" for v in tads_values])
                cbar.set_label(r"$T_{\mathrm{ads}}$ (K)", fontsize=15)
                cbar.ax.tick_params(labelsize=12)
            ax.set_xlabel(r"$\Pi_{\mathrm{H_2}}$ (mol kg$^{-1}$ h$^{-1}$)",
                          fontsize=17)
            ax.set_ylabel(r"$E_{\mathrm{reg}}$ (MJ kg$_{\mathrm{H_2}}^{-1}$)",
                          fontsize=17)
            ax.tick_params(axis="both", labelsize=13)
            _panel_label(ax, row_letters[mof][c])

    fig.savefig(FIG_MAIN / "fig4_energy_productivity_tradeoff.png")
    plt.close(fig)


# =====================================================================
# FIG 5 — PRODUCTIVITY DISTRIBUTIONS
# =====================================================================




def stage_kde(df):
    _style()
    print("[kde] Fig 5 — empirical CDFs")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), constrained_layout=True)

    for ax, lim, letter in zip(axes, ["CH4", "CO"], ["(a)", "(b)"]):
        sub = df[df["limiting"] == lim]

        # Plot each CDF twice: thick semi-transparent halo underneath,
        # then crisp thin line on top — reads clean at both large and small sizes
        for mof in MOF_ORDER:
            data = sub[sub[MOF_COL] == mof]["Productivity-H2"].to_numpy()
            if len(data) < 5:
                continue
            data_sorted = np.sort(data)
            cdf = np.arange(1, len(data_sorted) + 1) / len(data_sorted)

            ax.plot(data_sorted, cdf,
                    color=MOF_COLORS[mof], lw=6.0, alpha=0.18,
                    solid_capstyle="round")
            ax.plot(data_sorted, cdf,
                    color=MOF_COLORS[mof], lw=2.6, alpha=1.0,
                    label=mof, solid_capstyle="round")

        # Faint horizontal reference lines at quartiles
        for q in (0.25, 0.50, 0.75):
            ax.axhline(q, color="0.75", lw=0.9, linestyle=":", zorder=0)

        ax.set_ylim(0, 1.02)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["0", "0.25", "0.50", "0.75", "1.0"])

        ax.set_xlabel(r"$\Pi_{\mathrm{H_2}}$ (mol kg$^{-1}$ h$^{-1}$)",
                      fontsize=17)
        ax.set_ylabel("cumulative fraction", fontsize=17)
        ax.tick_params(axis="both", labelsize=14)

        # Thin frame, no top/right spines — cleaner look
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_linewidth(1.2)

        # Legend bottom-right in panel (a), where curves are lower
        # and bottom-right in panel (b) similarly
        ax.legend(fontsize=14, loc="lower right", framealpha=0.92,
                  frameon=True, edgecolor="0.7")

        _panel_label(ax, letter)

    fig.savefig(FIG_MAIN / "fig5_productivity_distributions.png")
    plt.close(fig)





# =====================================================================
# ML — TRAIN / SAVE / LOAD
# =====================================================================

def _sanitize(s):
    return s.replace(" ", "_").replace("/", "_").replace("-", "").replace(",", "")


def _model_path(target, split_kind):
    return MODELS / f"xgb_{_sanitize(target)}_{split_kind}.json"


def _prepare_ml_data(df):
    feats = [STEAM_COL, TGAS_COL, TADS_COL]
    dummies = pd.get_dummies(df[MOF_COL], prefix="ads")
    for m in MOF_ORDER:
        col = f"ads_{m}"
        if col not in dummies.columns:
            dummies[col] = 0
    dummies = dummies[[f"ads_{m}" for m in MOF_ORDER]].astype(np.int8)

    X = pd.concat([df[feats].astype(np.float32).reset_index(drop=True),
                   dummies.reset_index(drop=True)], axis=1)
    y = df[TARGETS].astype(np.float32)
    scenario_id = df["scenario_id"].to_numpy()
    return X, y, scenario_id


def _split_indices(X, scenario_id, split_kind):
    if split_kind == "random":
        return train_test_split(
            np.arange(len(X)), test_size=TEST_FRACTION,
            random_state=RANDOM_STATE, shuffle=True)
    scen = np.unique(scenario_id)
    tr_s, te_s = train_test_split(scen, test_size=TEST_FRACTION,
                                   random_state=RANDOM_STATE, shuffle=True)
    mask_test = np.isin(scenario_id, te_s)
    return np.where(~mask_test)[0], np.where(mask_test)[0]


def _models_exist():
    return all(_model_path(t, s).exists()
               for t in TARGETS for s in ("random", "grouped"))


def train_and_cache(df):
    print("[train] fitting XGBoost models — slow step (~2 min)")
    gc.collect()

    X, y, scenario_id = _prepare_ml_data(df)
    del df; gc.collect()

    all_metrics, all_preds, all_shap = [], [], []

    for split_kind in ["random", "grouped"]:
        print(f"  split = {split_kind}")
        train_idx, test_idx = _split_indices(X, scenario_id, split_kind)

        dmat_test = xgb.DMatrix(X.iloc[test_idx].values,
                                 feature_names=list(X.columns))

        booster_cache = {}
        for target in TARGETS:
            m = XGBRegressor(**XGB_PARAMS)
            m.fit(X.iloc[train_idx], y[target].iloc[train_idx])
            booster = m.get_booster()
            booster.save_model(str(_model_path(target, split_kind)))
            booster_cache[target] = booster
            del m; gc.collect()

        for target, booster in booster_cache.items():
            y_true = y[target].iloc[test_idx].to_numpy()
            y_pred = booster.predict(dmat_test)
            all_metrics.append(pd.DataFrame([{
                "split": split_kind, "target": target,
                "R2": r2_score(y_true, y_pred),
                "MAE": mean_absolute_error(y_true, y_pred),
                "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
                "n_test": len(y_true),
            }]))
            all_preds.append(pd.DataFrame({
                "split": split_kind, "target": target,
                "y_true": y_true, "y_pred": y_pred,
            }))

        rng = np.random.default_rng(RANDOM_STATE)
        shap_idx = rng.choice(test_idx,
                              size=min(SHAP_MAX_N, len(test_idx)),
                              replace=False)
        Xs = X.iloc[shap_idx]
        dmat_shap = xgb.DMatrix(Xs.values, feature_names=list(Xs.columns))
        rows = []
        for target, booster in booster_cache.items():
            contribs = booster.predict(dmat_shap, pred_contribs=True)[:, :-1]
            mean_abs = np.abs(contribs).mean(axis=0)
            for feat, val in zip(X.columns, mean_abs):
                rows.append({"split": split_kind, "target": target,
                             "feature": feat, "mean_abs_shap": float(val)})
        all_shap.append(pd.DataFrame(rows))

        del dmat_test, dmat_shap, booster_cache
        gc.collect()

    metrics = pd.concat(all_metrics, ignore_index=True)
    preds   = pd.concat(all_preds,   ignore_index=True)
    shap_df = pd.concat(all_shap,    ignore_index=True)
    metrics.to_csv(METRICS_CSV, index=False)
    preds.to_csv(PREDS_CSV, index=False)
    shap_df.to_csv(SHAP_CSV, index=False)

    card = {
        "model_type": "XGBoost tree-ensemble regressors",
        "features": list(X.columns),
        "targets": TARGETS,
        "splits": {"random": "random 85/15 row split",
                   "grouped": "gasifier-scenario grouped 85/15"},
        "xgboost_parameters": XGB_PARAMS,
        "shap_sample_size": SHAP_MAX_N,
        "cache_files": {
            "metrics": METRICS_CSV.name,
            "predictions": PREDS_CSV.name,
            "shap": SHAP_CSV.name,
            "models_dir": MODELS.name,
        },
    }
    with open(CARD_JSON, "w") as f:
        json.dump(card, f, indent=2)

    print(metrics.to_string(index=False))
    return metrics, preds, shap_df


def load_cached():
    preds = pd.read_csv(PREDS_CSV)
    shap_df = pd.read_csv(SHAP_CSV)
    return preds, shap_df


# =====================================================================
# FIG 6 (main) + FIG S (parity) — from ML cache
# =====================================================================

def stage_ml_plots(preds, shap_df):
    _style()
    print("[ml] Fig 6 + SI parity plots (from cache)")

    panel_letters = ["(a)", "(b)", "(c)", "(d)", "(e)"]

    # -------- SI parity plots — hexbin density --------
    for split_kind in ["random", "grouped"]:
        fig, axes = plt.subplots(1, len(TARGETS),
                                 figsize=(4.8*len(TARGETS), 4.8))
        for ax, target, letter in zip(axes, TARGETS, panel_letters):
            sub = preds[(preds["split"] == split_kind) &
                        (preds["target"] == target)]
            yt, yp = sub["y_true"].to_numpy(), sub["y_pred"].to_numpy()
            lo, hi = float(min(yt.min(), yp.min())), \
                     float(max(yt.max(), yp.max()))
            span = hi - lo
            lo, hi = lo - 0.02*span, hi + 0.02*span
            hb = ax.hexbin(yt, yp, gridsize=18, mincnt=1,
                           cmap="viridis", norm=LogNorm(),
                           extent=[lo, hi, lo, hi])
            cbar = fig.colorbar(hb, ax=ax, shrink=0.68)
            cbar.set_label("count", fontsize=13)
            cbar.ax.tick_params(labelsize=11)

            ax.plot([lo, hi], [lo, hi], "k--", lw=1)
            r2 = r2_score(yt, yp)
            ax.set_xlabel(f"True   ($R^2$ = {r2:.3f})", fontsize=13)
            ax.set_ylabel(f"Predicted   {TARGET_LABELS[target]}", fontsize=13)
            ax.tick_params(axis="both", labelsize=12)
            ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
            ax.set_aspect("equal", adjustable="box")
            _panel_label(ax, letter)
        fig.tight_layout()
        fig.savefig(FIG_SI / f"figS_xgb_parity_{split_kind}.png")
        plt.close(fig)

    # -------- Fig 6 — 2+2+1 layout, per-descriptor color --------
    fig = plt.figure(figsize=(13, 14), constrained_layout=True)
    gs = fig.add_gridspec(3, 2)


    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])
    ax_e = fig.add_subplot(gs[2, 0])   # bottom-left, single column
    panel_axes = [ax_a, ax_b, ax_c, ax_d, ax_e]


    for ax, target, letter in zip(panel_axes, TARGETS, panel_letters):
        sub = shap_df[(shap_df["split"] == "grouped") &
                      (shap_df["target"] == target)] \
                .sort_values("mean_abs_shap", ascending=True)
        # Each descriptor gets a fixed color across all panels
        bar_colors = [FEATURE_COLORS.get(f, "#888888") for f in sub["feature"]]
        labels = [FEATURE_LABELS.get(f, f) for f in sub["feature"]]
        ax.barh(labels, sub["mean_abs_shap"],
                color=bar_colors, edgecolor="none")
        ax.set_xlabel(f"mean |TreeSHAP|   {TARGET_LABELS[target]}",
                      fontsize=15)
        ax.tick_params(axis="both", labelsize=13)
        _panel_label(ax, letter)

    fig.savefig(FIG_MAIN / "fig6_treeshap_grouped.png")
    plt.close(fig)


# =====================================================================
# FIG 7 — ADSORBENT MASS SCALING
# =====================================================================

def stage_mass(df):
    _style()
    print("[mass] Fig 7")

    df = df.copy()
    df["m_ads_max"] = df[["MOF mass -CH4", "MOF mass -CO", "MOF mass -CO2"]].max(axis=1)

    def _fit(x, a, b, c):
        return a / x + b * x + c

    order   = ["Cu-TDPAT", "HKUST-1", "Zeolite 13X"]
    letters = ["(a)", "(b)", "(c)"]

    rng = np.random.default_rng(RANDOM_STATE)
    n_show = 10_000

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.4), constrained_layout=True)
    for ax, mof, letter in zip(axes, order, letters):
        sub = df[df[MOF_COL] == mof].sort_values("m_ads_max")
        x = sub["m_ads_max"].to_numpy()
        y = sub["Productivity-H2"].to_numpy()
        keep = np.isfinite(x) & np.isfinite(y) & (x > 0)
        x, y = x[keep], y[keep]

        if len(x) > n_show:
            idx = rng.choice(len(x), size=n_show, replace=False)
            xs, ys = x[idx], y[idx]
        else:
            xs, ys = x, y

        ax.scatter(xs, ys, s=20, alpha=0.35, color=MOF_COLORS[mof],
                   edgecolors="none")
        try:
            popt, _ = curve_fit(_fit, x, y, maxfev=100000)
            xf = np.linspace(x.min(), x.max(), 300)
            ax.plot(xf, _fit(xf, *popt), color="black", lw=2, label="fitted")
            ax.legend(loc="upper right", framealpha=0.92, fontsize=12)
        except Exception as e:
            print(f"    fit failed for {mof}: {e}")

        ax.set_xlabel(rf"$m_{{\mathrm{{ads,max}}}}$ (kg)   ({mof})",
                      fontsize=17)
        ax.set_ylabel(r"$\Pi_{\mathrm{H_2}}$ (mol kg$^{-1}$ h$^{-1}$)",
                      fontsize=17)
        ax.tick_params(axis="both", labelsize=14)
        _panel_label(ax, letter)

    fig.savefig(FIG_MAIN / "fig7_adsorbent_mass_scaling.png")
    plt.close(fig)


# =====================================================================
# MAIN
# =====================================================================

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", default="all",
                   choices=["all", "winner", "compose", "envelope",
                            "kde", "ml", "mass"])
    p.add_argument("--retrain", action="store_true",
                   help="force ML retraining even if cache exists")
    args = p.parse_args()

    gas, df = load_data()
    print(f"[main] dataset: {df.shape}\n")

    if args.stage in ("all", "winner"):   stage_winner(gas, df)
    if args.stage in ("all", "compose"):  stage_compose(gas)
    if args.stage in ("all", "envelope"): stage_envelope(df)
    if args.stage in ("all", "kde"):      stage_kde(df)

    if args.stage in ("all", "ml"):
        need_train = args.retrain or not (
            _models_exist() and PREDS_CSV.exists() and SHAP_CSV.exists()
        )
        if need_train:
            _, preds, shap_df = train_and_cache(df)
        else:
            print("[ml] cache found — loading predictions and SHAP from disk")
            preds, shap_df = load_cached()
        stage_ml_plots(preds, shap_df)

    if args.stage in ("all", "mass"):     stage_mass(df)

    print(f"\n[main] done. outputs in {OUT}")


if __name__ == "__main__":
    main()