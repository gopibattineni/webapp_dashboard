"""
Publication-quality figures for synthetic data benchmarking (TRTR/TSTR).

Usage
-----
# Demo data (no input file):
python scripts/generate_paper_figures.py

# Your results CSV:
python scripts/generate_paper_figures.py --input path/to/results.csv

Expected columns:
  dataset, generator, seed, classifier, metric,
  trtr_score, tstr_score, fidelity_score, mia_score

Dependencies:
  pip install pandas numpy matplotlib seaborn scipy scikit-posthocs
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scikit_posthocs as sp
import seaborn as sns
from scipy import stats

# ---------------------------------------------------------------------------
# Publication style
# ---------------------------------------------------------------------------

GENERATORS = [
    "CTGAN",
    "CopulaGAN",
    "TVAE",
    "GaussianCopula",
    "WGAN_GP",
    "CTABGAN",
]

GENERATOR_LABELS = {
    "CTGAN": "CTGAN",
    "CopulaGAN": "CopulaGAN",
    "TVAE": "TVAE",
    "GaussianCopula": "GaussianCopula",
    "WGAN_GP": "WGAN-GP",
    "CTABGAN": "CTABGAN",
}

GENERATOR_COLORS = {
    "CTGAN": "#2563eb",
    "CopulaGAN": "#7c3aed",
    "TVAE": "#0891b2",
    "GaussianCopula": "#16a34a",
    "WGAN_GP": "#d97706",
    "CTABGAN": "#dc2626",
}

DATASETS = [
    "Cancer",
    "MAGIC",
    "Adult",
    "Forest",
    "Bank",
    "Wine",
    "Mushroom",
    "CDC Diabetes",
    "Metro",
    "Online Shopping",
]

OUTPUT_DIR = Path("paper_figures")
DPI = 300


def apply_pub_style() -> None:
    mpl.rcParams.update(
        {
            "figure.dpi": DPI,
            "savefig.dpi": DPI,
            "font.family": "serif",
            "font.serif": [
                "Computer Modern Serif",
                "Computer Modern",
                "Latin Modern Roman",
                "CMU Serif",
                "DejaVu Serif",
            ],
            "mathtext.fontset": "cm",
            "font.size": 12,
            "axes.titlesize": 14,
            "axes.labelsize": 13,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 11,
            "axes.linewidth": 1.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def save_figure(fig: plt.Figure, name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        path = OUTPUT_DIR / f"{name}.{ext}"
        fig.savefig(path, bbox_inches="tight", dpi=DPI)
        print(f"  saved {path}")


def normalize_generators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["generator"] = (
        out["generator"]
        .astype(str)
        .str.replace("WGAN-GP", "WGAN_GP", regex=False)
        .str.strip()
    )
    return out


def aggregate_tstr(df: pd.DataFrame) -> pd.DataFrame:
    """Mean TSTR per dataset × generator × seed (averaged over classifiers)."""
    return (
        df.groupby(["dataset", "generator", "seed"], as_index=False)
        .agg(
            tstr_score=("tstr_score", "mean"),
            trtr_score=("trtr_score", "mean"),
            fidelity_score=("fidelity_score", "mean"),
            mia_score=("mia_score", "mean"),
        )
    )


def aggregate_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per dataset × generator with means across seeds/classifiers."""
    return (
        df.groupby(["dataset", "generator"], as_index=False)
        .agg(
            tstr_score=("tstr_score", "mean"),
            tstr_std=("tstr_score", "std"),
            trtr_score=("trtr_score", "mean"),
            fidelity_score=("fidelity_score", "mean"),
            mia_score=("mia_score", "mean"),
        )
    )


# ---------------------------------------------------------------------------
# Demo data (replace with --input CSV in practice)
# ---------------------------------------------------------------------------

def make_demo_data(n_seeds: int = 10, n_classifiers: int = 10, rng: np.random.Generator | None = None) -> pd.DataFrame:
    rng = rng or np.random.default_rng(42)
    classifiers = [f"M{i + 1}" for i in range(n_classifiers)]
    rows = []

    gen_effects = {
        "CTGAN": 0.02,
        "CopulaGAN": -0.03,
        "TVAE": 0.01,
        "GaussianCopula": 0.00,
        "WGAN_GP": 0.03,
        "CTABGAN": 0.04,
    }

    for ds_i, dataset in enumerate(DATASETS):
        ds_effect = rng.normal(0, 0.02)
        for gen in GENERATORS:
            ge = gen_effects[gen]
            for seed in range(n_seeds):
                seed_noise = rng.normal(0, 0.015)
                for clf in classifiers:
                    trtr = np.clip(0.72 + ds_effect + rng.normal(0, 0.04), 0.45, 0.98)
                    gap = np.clip(0.06 - ge + ds_effect * 0.2 + seed_noise + rng.normal(0, 0.02), -0.02, 0.18)
                    tstr = np.clip(trtr - gap, 0.40, 0.97)
                    fidelity = np.clip(0.55 + ge * 2 + rng.normal(0, 0.06), 0.2, 0.95)
                    mia = np.clip(0.52 - ge * 0.5 + rng.normal(0, 0.05), 0.35, 0.70)
                    rows.append(
                        {
                            "dataset": dataset,
                            "generator": gen,
                            "seed": seed,
                            "classifier": clf,
                            "metric": "accuracy",
                            "trtr_score": trtr,
                            "tstr_score": tstr,
                            "fidelity_score": fidelity,
                            "mia_score": mia,
                        }
                    )
    return pd.DataFrame(rows)


def load_data(path: Path | None) -> pd.DataFrame:
    if path is None:
        print("No --input provided; using reproducible demo data.")
        return normalize_generators(make_demo_data())
    df = pd.read_csv(path)
    required = {
        "dataset",
        "generator",
        "seed",
        "classifier",
        "trtr_score",
        "tstr_score",
        "fidelity_score",
        "mia_score",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {sorted(missing)}")
    return normalize_generators(df)


# ---------------------------------------------------------------------------
# Figure 4 — Dataset × Generator heatmap (mean TSTR)
# ---------------------------------------------------------------------------

def fig04_heatmap_tstr(summary: pd.DataFrame) -> None:
    pivot = summary.pivot(index="dataset", columns="generator", values="tstr_score")
    pivot = pivot.reindex(index=DATASETS, columns=GENERATORS)
    pivot = pivot.dropna(how="all")
    pivot = pivot[[c for c in GENERATORS if c in pivot.columns]]

    fig, ax = plt.subplots(figsize=(7.2, 6.0))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".3f",
        cmap="YlGnBu",
        linewidths=0.6,
        linecolor="white",
        cbar_kws={"label": "Mean TSTR score", "shrink": 0.85},
        annot_kws={"size": 10},
        ax=ax,
    )
    ax.set_xlabel("Generator")
    ax.set_ylabel("Dataset")
    ax.set_title("Mean TSTR performance by dataset and generator")
    ax.set_xticklabels([GENERATOR_LABELS.get(g, g) for g in pivot.columns], rotation=35, ha="right")
    fig.tight_layout()
    save_figure(fig, "fig04_heatmap_tstr")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2 — Bar plot: mean TSTR per generator ± std across seeds
# ---------------------------------------------------------------------------

def fig02_bar_tstr_by_generator(seed_df: pd.DataFrame) -> None:
    agg = (
        seed_df.groupby("generator")["tstr_score"]
        .agg(["mean", "std"])
        .reindex(GENERATORS)
        .dropna()
    )

    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    x = np.arange(len(agg))
    colors = [GENERATOR_COLORS[g] for g in agg.index]
    ax.bar(
        x,
        agg["mean"],
        yerr=agg["std"],
        capsize=4,
        color=colors,
        edgecolor="black",
        linewidth=0.6,
        error_kw={"elinewidth": 1.2, "capthick": 1.2},
    )
    ax.set_xticks(x)
    ax.set_xticklabels([GENERATOR_LABELS[g] for g in agg.index], rotation=30, ha="right")
    ax.set_ylabel("Mean TSTR score")
    ax.set_xlabel("Generator")
    ax.set_title("Average TSTR performance across datasets and classifiers")
    ymax = (agg["mean"] + agg["std"]).max()
    ax.text(
        0.02,
        0.98,
        f"Error bars: SD across {seed_df['seed'].nunique()} seeds",
        transform=ax.transAxes,
        va="top",
        fontsize=10,
        color="#334155",
    )
    ax.set_ylim(0, ymax * 1.15 if ymax > 0 else 1)
    fig.tight_layout()
    save_figure(fig, "fig02_bar_tstr_generators")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 3 — TRTR vs TSTR gap per generator
# ---------------------------------------------------------------------------

def fig03_trtr_tstr_gap(summary: pd.DataFrame) -> None:
    plot_df = summary.copy()
    plot_df["gap"] = plot_df["trtr_score"] - plot_df["tstr_score"]
    agg = plot_df.groupby("generator")["gap"].agg(["mean", "std"]).reindex(GENERATORS).dropna()

    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    x = np.arange(len(agg))
    colors = [GENERATOR_COLORS[g] for g in agg.index]
    ax.bar(
        x,
        agg["mean"],
        yerr=agg["std"],
        capsize=4,
        color=colors,
        edgecolor="black",
        linewidth=0.6,
        error_kw={"elinewidth": 1.2, "capthick": 1.2},
    )
    ax.axhline(0, color="#64748b", linewidth=1, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels([GENERATOR_LABELS[g] for g in agg.index], rotation=30, ha="right")
    ax.set_ylabel("TRTR − TSTR (utility gap)")
    ax.set_xlabel("Generator")
    ax.set_title("Utility gap: train-on-real vs train-on-synthetic")
    fig.tight_layout()
    save_figure(fig, "fig03_trtr_tstr_gap")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 4 — Fidelity vs Utility scatter
# ---------------------------------------------------------------------------

def fig04_fidelity_vs_utility(summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.8, 5.5))
    for gen in GENERATORS:
        sub = summary[summary["generator"] == gen]
        if sub.empty:
            continue
        ax.scatter(
            sub["fidelity_score"],
            sub["tstr_score"],
            label=GENERATOR_LABELS[gen],
            color=GENERATOR_COLORS[gen],
            s=70,
            alpha=0.85,
            edgecolors="white",
            linewidths=0.5,
        )

    r, p = stats.pearsonr(summary["fidelity_score"], summary["tstr_score"])
    ax.text(
        0.03,
        0.97,
        f"Pearson r = {r:.3f}\np = {p:.2e}",
        transform=ax.transAxes,
        va="top",
        fontsize=11,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#cbd5e1"),
    )
    ax.set_xlabel("Fidelity score (composite)")
    ax.set_ylabel("Mean TSTR score")
    ax.set_title("Fidelity vs utility")
    ax.legend(frameon=True, loc="lower right", title="Generator")
    fig.tight_layout()
    save_figure(fig, "fig05_fidelity_vs_utility")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 5 — Privacy (MIA) vs Utility scatter
# ---------------------------------------------------------------------------

def fig05_mia_vs_utility(summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.8, 5.5))
    for gen in GENERATORS:
        sub = summary[summary["generator"] == gen]
        if sub.empty:
            continue
        ax.scatter(
            sub["mia_score"],
            sub["tstr_score"],
            label=GENERATOR_LABELS[gen],
            color=GENERATOR_COLORS[gen],
            s=70,
            alpha=0.85,
            edgecolors="white",
            linewidths=0.5,
        )

    r, p = stats.pearsonr(summary["mia_score"], summary["tstr_score"])
    ax.text(
        0.03,
        0.97,
        f"Pearson r = {r:.3f}\np = {p:.2e}",
        transform=ax.transAxes,
        va="top",
        fontsize=11,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#cbd5e1"),
    )
    ax.set_xlabel("MIA score (lower = more private)")
    ax.set_ylabel("Mean TSTR score")
    ax.set_title("Privacy vs utility")
    ax.legend(frameon=True, loc="lower right", title="Generator")
    fig.tight_layout()
    save_figure(fig, "fig06_mia_vs_utility")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 6 — Boxplots: TSTR across seeds per generator
# ---------------------------------------------------------------------------

def fig06_boxplot_seeds(seed_df: pd.DataFrame) -> None:
    plot_df = seed_df.copy()
    plot_df["generator"] = plot_df["generator"].map(lambda g: GENERATOR_LABELS.get(g, g))
    order = [GENERATOR_LABELS[g] for g in GENERATORS if g in seed_df["generator"].unique()]

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    sns.boxplot(
        data=plot_df,
        x="generator",
        y="tstr_score",
        order=order,
        hue="generator",
        palette=[GENERATOR_COLORS[g] for g in GENERATORS if g in seed_df["generator"].unique()],
        linewidth=1.0,
        fliersize=3,
        legend=False,
        ax=ax,
    )
    sns.stripplot(
        data=plot_df,
        x="generator",
        y="tstr_score",
        order=order,
        color="black",
        alpha=0.25,
        size=2.5,
        jitter=0.18,
        ax=ax,
    )
    ax.set_xlabel("Generator")
    ax.set_ylabel("TSTR score")
    ax.set_title("TSTR distribution across random seeds")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    save_figure(fig, "fig07_boxplot_tstr_seeds")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 7 — Average generator ranking across datasets
# ---------------------------------------------------------------------------

def fig07_average_ranking(summary: pd.DataFrame) -> None:
    rank_df = summary.copy()
    rank_df["rank"] = rank_df.groupby("dataset")["tstr_score"].rank(ascending=False, method="average")
    avg_rank = rank_df.groupby("generator")["rank"].mean().reindex(GENERATORS).dropna()
    avg_rank = avg_rank.sort_values()

    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    y = np.arange(len(avg_rank))
    colors = [GENERATOR_COLORS[g] for g in avg_rank.index]
    ax.barh(y, avg_rank.values, color=colors, edgecolor="black", linewidth=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels([GENERATOR_LABELS[g] for g in avg_rank.index])
    ax.invert_yaxis()
    ax.set_xlabel("Average rank across datasets (1 = best)")
    ax.set_title("Generator ranking by mean TSTR performance")
    for i, (gen, val) in enumerate(avg_rank.items()):
        ax.text(val + 0.05, i, f"{val:.2f}", va="center", fontsize=10)
    fig.tight_layout()
    save_figure(fig, "fig07_average_ranking")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 1 — Friedman test + Critical Difference diagram
# ---------------------------------------------------------------------------

def fig01_friedman_cd(summary: pd.DataFrame) -> dict[str, float]:
    """Friedman test on dataset-blocked mean TSTR; CD diagram via scikit-posthocs."""
    pivot = summary.pivot(index="dataset", columns="generator", values="tstr_score")
    pivot = pivot[[c for c in GENERATORS if c in pivot.columns]].dropna(axis=0, how="any")

    if pivot.shape[0] < 3 or pivot.shape[1] < 3:
        print("  Skipping Friedman/CD: need ≥3 datasets and ≥3 generators with complete data.")
        return {}

    arrays = [pivot[col].values for col in pivot.columns]
    friedman = stats.friedmanchisquare(*arrays)

    ranks = pivot.rank(axis=1, ascending=False)
    avg_ranks = ranks.mean().sort_values()

    pvals = sp.posthoc_nemenyi_friedman(pivot.values)
    pvals.index = pivot.columns
    pvals.columns = pivot.columns
    sig = pvals < 0.05

    rank_dict = avg_ranks.to_dict()

    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    sp.critical_difference_diagram(
        rank_dict,
        sig,
        ax=ax,
        label_fmt_left="{label}\n({rank:.2f})",
    )
    ax.set_title(
        f"Critical difference diagram (Friedman χ²={friedman.statistic:.2f}, p={friedman.pvalue:.2e})",
        pad=14,
    )
    fig.tight_layout()
    save_figure(fig, "fig01_friedman_cd")

    stats_path = OUTPUT_DIR / "fig01_friedman_stats.txt"
    with stats_path.open("w", encoding="utf-8") as f:
        f.write("Friedman test (dataset blocks)\n")
        f.write(f"  chi2 = {friedman.statistic:.6f}\n")
        f.write(f"  p    = {friedman.pvalue:.6e}\n\n")
        f.write("Average ranks (lower is better):\n")
        for gen, r in avg_ranks.items():
            f.write(f"  {GENERATOR_LABELS.get(gen, gen):15s} {r:.4f}\n")
        f.write("\nNemenyi post-hoc p-values:\n")
        f.write(pvals.to_string())
    print(f"  saved {stats_path}")

    plt.close(fig)
    return {"chi2": friedman.statistic, "p": friedman.pvalue}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate publication figures for SD benchmarking.")
    parser.add_argument("--input", type=Path, default=None, help="CSV with benchmarking results")
    args = parser.parse_args()

    apply_pub_style()
    df = load_data(args.input)
    seed_df = aggregate_tstr(df)
    summary = aggregate_summary(df)

    print(f"Rows: {len(df):,} | Datasets: {df['dataset'].nunique()} | Generators: {df['generator'].nunique()}")
    print(f"Writing figures to ./{OUTPUT_DIR}/")

    fig01_friedman_cd(summary)
    fig02_bar_tstr_by_generator(seed_df)
    fig03_trtr_tstr_gap(summary)
    fig04_heatmap_tstr(summary)
    fig05_fidelity_vs_utility(summary)
    fig06_mia_vs_utility(summary)
    fig07_boxplot_seeds(seed_df)

    print("Done.")


if __name__ == "__main__":
    main()
