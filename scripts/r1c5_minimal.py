"""Count saved TSA winner labels and draw the single R1C5 SI figure.

Recounts the released source CSVs using the existing temperature-selection
functions; no simulation, model evaluation or exploratory figures are run.
Run from any directory: python scripts/r1c5_minimal.py
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

from tsa_temperature_analysis import load_data, select_strategies


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "outputs/artifacts/tsa_temperature"
FIGURE = ROOT / "outputs/figures/si/tsa_temperature/figS19_r1c5.pdf"
MATERIALS = ["Cu-TDPAT", "Zeolite 13X", "HKUST-1"]
# Identical to MOF_COLORS in paper_pipeline.py.
COLORS = {"Cu-TDPAT": "#2ca02c", "Zeolite 13X": "#1f77b4", "HKUST-1": "#d62728"}
TEMPERATURES = [313.2, 328.4, 343.6, 358.8, 374.0, 389.2, 404.4, 419.6, 434.8, 450.0]


def main(output=FIGURE):
    gas, tsa = load_data(ROOT / "data")
    winners_by_strategy, _, _, _ = select_strategies(tsa)
    maps = gas.set_index("scenario_id")[[]].copy()
    for strategy, winners in winners_by_strategy.items():
        maps[f"winner_{strategy}"] = winners
        maps[f"changed_{strategy}"] = winners.ne(winners_by_strategy["original"])
    summary_path = ART / "winner_summary.csv"
    saved = (pd.read_csv(summary_path).set_index(["strategy", "MOF type"])
             if summary_path.exists() else None)
    print(f"Source data: {len(gas):,} scenarios; {len(tsa):,} scoring rows")
    reference = pd.read_csv(ROOT / "outputs/artifacts/winner_map_data.csv").set_index("scenario_id")
    assert maps.index.is_unique and len(maps) == 20301
    assert set(maps.index) == set(reference.index)
    assert maps.winner_original.eq(reference.winner_prod.reindex(maps.index)).all()
    strategies = ["original"] + [f"fixed_{t:g}K" for t in TEMPERATURES] + ["optimized"]
    shares, changed = {}, {}
    for strategy in strategies:
        winners = maps[f"winner_{strategy}"]
        assert winners.isin(MATERIALS).all()
        counts = winners.value_counts().reindex(MATERIALS, fill_value=0)
        shares[strategy] = counts / len(maps) * 100
        differences = winners.ne(maps.winner_original)
        assert differences.eq(maps[f"changed_{strategy}"]).all()
        changed[strategy] = int(differences.sum())
        assert int(counts.sum()) == len(maps)
        assert counts.tolist() == [4640, 15661, 0]
        assert changed[strategy] == 0
        for material in MATERIALS:
            if saved is None:
                continue
            row = saved.loc[(strategy, material)]
            assert int(row.scenario_count) == len(maps)
            assert int(row.winner_count) == int(counts[material])
            assert np.isclose(row.winner_pct, shares[strategy][material], rtol=0, atol=1e-8)
            assert int(row.changed_scenarios) == changed[strategy]
            assert np.isclose(row.changed_pct, differences.mean() * 100, rtol=0, atol=1e-8)
        proportions = ", ".join(f"{m}: {counts[m]:,} ({shares[strategy][m]:.4f}%)" for m in MATERIALS)
        print(f"{strategy}: {proportions}; changed {changed[strategy]:,}/{len(maps):,} ({differences.mean()*100:.4f}%)")

    fixed = pd.DataFrame([shares[f"fixed_{t:g}K"] for t in TEMPERATURES])
    print("Fixed-set-point ranges: " + "; ".join(
        f"{m} {fixed[m].min():.4f}-{fixed[m].max():.4f}%" for m in MATERIALS))
    fixed_changes = [changed[f"fixed_{t:g}K"] / len(maps) * 100 for t in TEMPERATURES]
    print(f"Changed-winner range: {min(fixed_changes):.4f}-{max(fixed_changes):.4f}%")
    print(f"Fixed-temperature comparisons: {len(maps) * len(TEMPERATURES):,}; "
          f"changed {sum(changed[f'fixed_{t:g}K'] for t in TEMPERATURES):,}")

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
        "font.size": 9,
        "axes.labelsize": 10,
        "axes.titlesize": 10,
        "axes.linewidth": 0.7,
        "xtick.labelsize": 8,
        "ytick.labelsize": 9,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.2, 3.45))
    fig.subplots_adjust(left=0.085, right=0.985, bottom=0.24, top=0.80, wspace=0.30)
    for ax in (left, right):
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#e5e5e5", linewidth=0.5)
        ax.set_ylim(-4, 116)
        ax.set_yticks([0, 20, 40, 60, 80, 100])
        ax.tick_params(length=3, width=0.7)
    left.set_title("(a)  Fixed set-points", loc="left", fontweight="bold", pad=9)
    markers = {"Cu-TDPAT": "o", "Zeolite 13X": "s", "HKUST-1": "^"}
    for material in MATERIALS:
        left.plot(TEMPERATURES, fixed[material], color=COLORS[material],
                  marker=markers[material], markersize=3.8, linewidth=1.4, clip_on=False)
    left.set_xlim(309, 454)
    left.set_xticks(TEMPERATURES, [f"{t:g}" for t in TEMPERATURES], rotation=45, ha="right")
    left.set_xlabel("Fixed TSA thermal set-point (K)")
    left.set_ylabel("Scenarios selecting material (%)")

    right.set_title("(b)  Individual optimization", loc="left", fontweight="bold", pad=9)
    base = np.zeros(2)
    for material in MATERIALS:
        values = np.array([shares[s][material] for s in ["original", "optimized"]])
        right.bar([0, 1], values, width=0.55, bottom=base,
                  color=COLORS[material], edgecolor="white", linewidth=0.7)
        for x, value, bottom in zip([0, 1], values, base):
            if value > 0:
                right.text(x, bottom + value / 2, f"{value:.2f}%", ha="center", va="center",
                           color="white", fontsize=9, fontweight="bold")
        base += values
    right.set_xlim(-0.6, 1.6)
    right.set_xticks([0, 1], ["Original\n(temperature-averaged)", "Individually\noptimized"])
    right.tick_params(axis="x", length=0, pad=7)
    right.text(0.5, 109, f"Changed winners: {changed['optimized']/len(maps)*100:.2f}% "
               f"({changed['optimized']:,}/{len(maps):,})", ha="center", va="center", fontsize=8.5)
    right.text(0.5, -0.18, "HKUST-1: 0% in both comparisons", transform=right.transAxes,
               ha="center", va="top", color=COLORS["HKUST-1"], fontsize=8)
    fig.legend(handles=[Patch(facecolor=COLORS[m], label=m) for m in MATERIALS],
               loc="upper center", bbox_to_anchor=(0.53, 1.0), ncol=3,
               frameon=False, handlelength=1.4, columnspacing=2.0)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, metadata={"Title": "TSA temperature selection and material winners",
                                "Subject": "Reviewer 1, Comment 5; existing TSA results only"})
    plt.close(fig)
    print(f"Figure: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=FIGURE)
    main(parser.parse_args().output)
