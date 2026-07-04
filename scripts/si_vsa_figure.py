#!/usr/bin/env python3
"""Generate the SI VSA/PSA winner map figure."""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR  = REPO_ROOT / "data"

OUT = REPO_ROOT / "outputs" / "figures" / "si"
OUT.mkdir(parents=True, exist_ok=True)

GAS_CSV = DATA_DIR / "book1.csv"
PSA_CSV = DATA_DIR / "PSA_DATA.csv"


STEAM_COL = "Steam - Mass Flow"
TGAS_COL = "Gasif-2 - Temperature"
MOF_COL = "MOF type"
PROD_COL = "Productivity-H2"

MOF_MAP = {"HKUST": "HKUST-1", "HKUST-1": "HKUST-1",
           "Cu-TDPAT": "Cu-TDPAT",
           "zeolit": "Zeolite 13X", "zeolite": "Zeolite 13X",
           "Zeolite13x": "Zeolite 13X", "Zeolite 13X": "Zeolite 13X"}
MOF_ORDER = ["HKUST-1", "Cu-TDPAT", "Zeolite 13X"]
MOF_COLORS = {"HKUST-1": "#d62728", "Cu-TDPAT": "#2ca02c",
              "Zeolite 13X": "#1f77b4"}


def load():
    gas = pd.read_csv(GAS_CSV)
    gas.columns = gas.columns.str.strip()
    gas["scenario_id"] = gas.index

    psa = pd.read_csv(PSA_CSV)
    psa.columns = psa.columns.str.strip()
    if psa.columns[0].startswith("Unnamed"):
        psa = psa.drop(columns=psa.columns[0])
    psa = psa.ffill().reset_index(drop=True)
    psa[MOF_COL] = psa[MOF_COL].astype(str).str.strip().map(
        lambda s: MOF_MAP.get(s, s))
    rep = len(psa) // len(gas)
    psa["scenario_id"] = np.tile(np.arange(len(gas)), rep)
    return gas, psa


def main():
    gas, psa = load()

    agg = (psa.groupby(["scenario_id", MOF_COL], as_index=False)
              .agg(prod=(PROD_COL, "mean")))
    prod = agg.pivot(index="scenario_id", columns=MOF_COL, values="prod")[MOF_ORDER]
    winners = np.array(MOF_ORDER)[np.argmax(prod.to_numpy(), axis=1)]

    shares = (pd.Series(winners)
                .value_counts(normalize=True).mul(100).round(2))
    print("Winner shares:")
    for m in MOF_ORDER:
        print(f"  {m:<15} {shares.get(m, 0):.2f}%")

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
        "font.weight": "bold",
        "axes.labelweight": "bold",
        "axes.titleweight": "bold",
        "font.size": 12,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    })

    fig, ax = plt.subplots(figsize=(9, 7), constrained_layout=True)
    idx_map = {m: i for i, m in enumerate(MOF_ORDER)}
    idx = pd.Series(winners).map(idx_map).to_numpy()
    cmap = ListedColormap([MOF_COLORS[m] for m in MOF_ORDER])
    norm = BoundaryNorm(np.arange(len(MOF_ORDER) + 1) - 0.5, len(MOF_ORDER))

    ax.scatter(gas[STEAM_COL], gas[TGAS_COL], c=idx, cmap=cmap, norm=norm,
               s=12, marker="s", edgecolors="none")

    handles = [plt.Line2D([0], [0], marker="s", linestyle="", markersize=12,
                          markerfacecolor=MOF_COLORS[m],
                          markeredgecolor="none",
                          label=f"{m}  ({shares.get(m, 0):.2f}%)")
               for m in MOF_ORDER]
    ax.legend(handles=handles, loc="upper right",
              framealpha=0.92, fontsize=13)

    ax.set_xlabel("Steam mass flow (kg h$^{-1}$)", fontsize=17)
    ax.set_ylabel("Gasifier temperature (°C)", fontsize=17)
    ax.tick_params(axis="both", labelsize=14)

    out = OUT / "figS_vsa_winner_map.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()