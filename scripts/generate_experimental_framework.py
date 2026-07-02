"""Generate publication-quality experimental framework figure (Fig. 0)."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUTPUT_DIR = Path("paper_figures")
DPI = 300

# Palette aligned with dashboard paper figures
BLUE = "#2563eb"
PURPLE = "#7c3aed"
TEAL = "#0891b2"
GREEN = "#16a34a"
ORANGE = "#d97706"
RED = "#dc2626"
SLATE = "#334155"
MUTED = "#64748b"
LIGHT = "#f8fafc"
BORDER = "#cbd5e1"


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "figure.dpi": DPI,
            "savefig.dpi": DPI,
            "font.family": "serif",
            "font.serif": [
                "Computer Modern Serif",
                "Computer Modern",
                "Latin Modern Roman",
                "DejaVu Serif",
            ],
            "mathtext.fontset": "cm",
            "font.size": 11,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def box(ax, x, y, w, h, text, fc="#ffffff", ec=BORDER, lw=1.2, fs=10, bold=False, ha="center"):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.015",
        linewidth=lw,
        edgecolor=ec,
        facecolor=fc,
        transform=ax.transAxes,
        zorder=2,
    )
    ax.add_patch(patch)
    weight = "bold" if bold else "normal"
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha=ha,
        va="center",
        fontsize=fs,
        fontweight=weight,
        color=SLATE,
        transform=ax.transAxes,
        zorder=3,
        wrap=True,
    )


def arrow(ax, x1, y1, x2, y2, color=MUTED):
    arr = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=1.4,
        color=color,
        transform=ax.transAxes,
        zorder=1,
    )
    ax.add_patch(arr)


def contribution_box(ax, x, y, w, h, num, text):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.012",
        linewidth=1.0,
        edgecolor="#94a3b8",
        facecolor="#f1f5f9",
        transform=ax.transAxes,
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        x + 0.02,
        y + h - 0.025,
        f"({num})",
        ha="left",
        va="top",
        fontsize=10,
        fontweight="bold",
        color=BLUE,
        transform=ax.transAxes,
        zorder=3,
    )
    ax.text(
        x + 0.02,
        y + h - 0.055,
        text,
        ha="left",
        va="top",
        fontsize=8.2,
        color=SLATE,
        transform=ax.transAxes,
        zorder=3,
        wrap=True,
    )


def build_figure() -> plt.Figure:
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.97,
        "Unified Experimental Framework for Synthetic Tabular Data Generator Benchmarking",
        ha="center",
        va="top",
        fontsize=15,
        fontweight="bold",
        color=SLATE,
    )
    ax.text(
        0.5,
        0.935,
        "10 datasets  ×  6 generators  ×  10 seeds  ×  10 downstream models  |  Fidelity · Utility · Privacy",
        ha="center",
        va="top",
        fontsize=10.5,
        color=MUTED,
    )

    # --- Row 1: Benchmark scope ---
    ax.text(0.05, 0.88, "A. Benchmark scope", fontsize=11, fontweight="bold", color=SLATE)
    box(ax, 0.05, 0.78, 0.16, 0.08, "10 real datasets\n(8 clf · 2 reg)", fc="#eff6ff", ec=BLUE, bold=True, fs=9.5)
    box(ax, 0.24, 0.78, 0.16, 0.08, "6 STD generators\nCTGAN · CopulaGAN · TVAE\nGaussCop · WGAN-GP · CTAB", fc="#f5f3ff", ec=PURPLE, fs=8.5)
    box(ax, 0.43, 0.78, 0.12, 0.08, "10 random\nseeds", fc="#ecfeff", ec=TEAL, fs=9.5)
    box(ax, 0.58, 0.78, 0.16, 0.08, "10 downstream\nclassifiers / regressors", fc="#f0fdf4", ec=GREEN, fs=9.5)
    box(ax, 0.77, 0.78, 0.18, 0.08, "Unified evaluation\npipeline (SYNTH)", fc="#fff7ed", ec=ORANGE, bold=True, fs=9.5)

    arrow(ax, 0.21, 0.82, 0.24, 0.82)
    arrow(ax, 0.40, 0.82, 0.43, 0.82)
    arrow(ax, 0.55, 0.82, 0.58, 0.82)
    arrow(ax, 0.74, 0.82, 0.77, 0.82)

    # --- Row 2: Generation + evaluation ---
    ax.text(0.05, 0.72, "B. Generation & evaluation protocol", fontsize=11, fontweight="bold", color=SLATE)
    box(ax, 0.05, 0.58, 0.20, 0.10, "Real data\n(preprocess · split · subsample)", fc=LIGHT, fs=9.5)
    box(ax, 0.28, 0.58, 0.20, 0.10, "Synthetic data\ngeneration\n(per generator × seed)", fc=LIGHT, fs=9.5)
    arrow(ax, 0.25, 0.63, 0.28, 0.63)

    # Three pillars
    pillars = [
        (0.52, 0.60, 0.14, 0.08, "Fidelity", "KS · TV · Corr\nJS · Wasserstein", GREEN),
        (0.68, 0.60, 0.14, 0.08, "Utility", "TRTR baseline\nTSTR downstream", BLUE),
        (0.84, 0.60, 0.11, 0.08, "Privacy", "MIA attack\naccuracy", RED),
    ]
    for x, y, w, h, title, body, color in pillars:
        box(ax, x, y, w, h, f"{title}\n{body}", fc="#ffffff", ec=color, bold=True, fs=9)
    arrow(ax, 0.48, 0.63, 0.52, 0.64)
    arrow(ax, 0.66, 0.64, 0.68, 0.64)
    arrow(ax, 0.82, 0.64, 0.84, 0.64)

    ax.text(
        0.52,
        0.55,
        "Three-dimensional quality assessment (reproducible metrics)",
        fontsize=9,
        color=MUTED,
        style="italic",
    )

    # --- Row 3: Cross-dataset robustness ---
    ax.text(0.05, 0.48, "C. Cross-dataset robustness analysis", fontsize=11, fontweight="bold", color=SLATE)
    box(ax, 0.05, 0.34, 0.90, 0.11, "", fc=LIGHT, ec=BORDER, fs=9)
    ax.text(
        0.50,
        0.42,
        "Rank generators per dataset  →  Friedman + Nemenyi tests  →  Critical difference diagrams",
        ha="center",
        va="center",
        fontsize=9.5,
        color=SLATE,
        transform=ax.transAxes,
    )
    ax.text(
        0.50,
        0.37,
        "Assess whether generator rankings remain consistent across datasets with varying size, dimensionality, and task type",
        ha="center",
        va="center",
        fontsize=8.8,
        color=MUTED,
        transform=ax.transAxes,
    )

    # --- Row 4: Trade-off & decision support ---
    ax.text(0.05, 0.28, "D. Fidelity–utility–privacy trade-off & decision support", fontsize=11, fontweight="bold", color=SLATE)
    box(ax, 0.05, 0.14, 0.28, 0.11, "Trade-off analysis\nFidelity vs utility scatter\nPrivacy vs utility scatter\nTRTR–TSTR gap plots", fc="#ffffff", ec=TEAL, fs=8.8)
    box(ax, 0.36, 0.14, 0.28, 0.11, "Aggregate rankings\nMean TSTR ± SD\nWin-rate heatmaps\nSeed-level boxplots", fc="#ffffff", ec=BLUE, fs=8.8)
    box(ax, 0.67, 0.14, 0.28, 0.11, "Practitioner decision support\nSelect generator by deployment need:\nhigh utility · high fidelity · high privacy", fc="#fff7ed", ec=ORANGE, bold=True, fs=8.8)

    arrow(ax, 0.33, 0.195, 0.36, 0.195)
    arrow(ax, 0.64, 0.195, 0.67, 0.195)

    # --- Contributions sidebar ---
    ax.text(0.05, 0.08, "Key contributions", fontsize=10.5, fontweight="bold", color=SLATE)
    contributions = [
        "Largest unified STD benchmark to date: 6 generators, 10 datasets, 10 classifiers under one framework.",
        "Complete quality picture across fidelity, utility, and privacy with established reproducible metrics.",
        "Cross-dataset robustness analysis addressing generalisability gaps in prior studies.",
        "Quantitative fidelity–utility–privacy trade-offs enabling practitioner decision support.",
    ]
    for i, text in enumerate(contributions):
        contribution_box(ax, 0.05 + (i % 2) * 0.48, 0.01 if i >= 2 else 0.045, 0.44, 0.075 if i < 2 else 0.07, i + 1, text)

    # Legend strip
    legend_items = [
        ("TRTR", "Train on Real, Test on Real"),
        ("TSTR", "Train on Synthetic, Test on Real"),
        ("STD", "Synthetic Tabular Data"),
        ("MIA", "Membership Inference Attack"),
    ]
    lx = 0.52
    for label, desc in legend_items:
        ax.text(lx, 0.025, f"{label}:", fontsize=8, fontweight="bold", color=SLATE, transform=ax.transAxes)
        ax.text(lx + 0.04, 0.025, desc, fontsize=8, color=MUTED, transform=ax.transAxes)
        lx += 0.12

    return fig


def main() -> None:
    apply_style()
    fig = build_figure()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        path = OUTPUT_DIR / f"fig00_experimental_framework.{ext}"
        fig.savefig(path, bbox_inches="tight", dpi=DPI, facecolor="white")
        print(f"Saved {path.resolve()}")
    plt.close(fig)


if __name__ == "__main__":
    main()
