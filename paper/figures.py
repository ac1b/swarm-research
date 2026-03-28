#!/usr/bin/env python3
"""Generate figures for the SwarmOpt NeurIPS workshop paper."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "fig"
OUT.mkdir(exist_ok=True)

# Style
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})

COLORS = {
    "full": "#2563EB",
    "no_backtrack": "#F59E0B",
    "single_agent": "#EF4444",
    "no_board": "#8B5CF6",
}


# ── Figure 1: Component Ablation (Game-AI + Bio-Opt side by side) ──

def fig_ablation():
    fig, axes = plt.subplots(1, 2, figsize=(5.5, 2.2))

    # Game-AI (n=7)
    ax = axes[0]
    configs = ["Full", "No-Backtrack", "Single-Agent"]
    means = [87.5, 80.5, 80.4]
    stds = [16.1, 9.4, 10.1]
    colors = [COLORS["full"], COLORS["no_backtrack"], COLORS["single_agent"]]
    bars = ax.bar(configs, means, yerr=stds, capsize=4, color=colors, edgecolor="white", linewidth=0.5, width=0.65)
    ax.axhline(y=25.6, color="gray", linestyle="--", linewidth=0.8, label="Baseline (25.6)")
    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Game-AI (maximize)")
    ax.set_ylim(0, 115)
    ax.legend(fontsize=7, loc="upper left")
    # Annotate bars
    for bar, m in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, f"{m:.1f}",
                ha="center", va="bottom", fontsize=7.5)

    # Bio-Opt (n=3)
    ax = axes[1]
    means = [49.9, 45.3, 43.2]
    stds = [6.2, 6.0, 3.2]
    bars = ax.bar(configs, means, yerr=stds, capsize=4, color=colors, edgecolor="white", linewidth=0.5, width=0.65)
    ax.axhline(y=39.6, color="gray", linestyle="--", linewidth=0.8, label="Baseline (39.6)")
    ax.set_ylabel("Motif Score")
    ax.set_title("Bio-Opt (maximize)")
    ax.set_ylim(0, 65)
    ax.legend(fontsize=7, loc="upper left")
    for bar, m in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f"{m:.1f}",
                ha="center", va="bottom", fontsize=7.5)

    plt.tight_layout()
    fig.savefig(OUT / "ablation.pdf")
    fig.savefig(OUT / "ablation.png")
    plt.close(fig)
    print("  ablation.pdf")


# ── Figure 2: Round Scaling (Game-AI) ──

def fig_rounds():
    fig, ax = plt.subplots(figsize=(3.2, 2.2))

    rounds = [0, 2, 4, 8, 12]
    means = [25.6, 67.7, 85.4, 91.3, 97.9]
    stds = [0, 7.8, 15.0, 7.6, 3.6]
    backtracks = [0, 0, 0, 1.3, 1.3]

    ax.errorbar(rounds, means, yerr=stds, fmt="o-", color=COLORS["full"],
                capsize=4, linewidth=1.5, markersize=5, label="Score")
    ax.fill_between(rounds, [m-s for m,s in zip(means, stds)],
                    [m+s for m,s in zip(means, stds)],
                    alpha=0.15, color=COLORS["full"])

    # Mark where backtracking kicks in
    ax.axvline(x=6, color="gray", linestyle=":", linewidth=0.7)
    ax.text(6.3, 40, "backtrack\nthreshold", fontsize=6.5, color="gray", va="bottom")

    ax.set_xlabel("Optimization Rounds")
    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Game-AI: Score vs. Rounds")
    ax.set_ylim(0, 115)
    ax.set_xticks(rounds)

    # Annotate key points
    ax.annotate(f"baseline\n{means[0]}%", (0, means[0]), textcoords="offset points",
                xytext=(12, -8), fontsize=7, color="gray")
    ax.annotate(f"{means[-1]}%", (12, means[-1]), textcoords="offset points",
                xytext=(-20, 8), fontsize=7.5, fontweight="bold")

    plt.tight_layout()
    fig.savefig(OUT / "rounds.pdf")
    fig.savefig(OUT / "rounds.png")
    plt.close(fig)
    print("  rounds.pdf")


# ── Figure 3: Search Tree Visualization (conceptual) ──

def fig_tree():
    fig, ax = plt.subplots(figsize=(3.8, 2.8))
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(-0.5, 4.5)
    ax.set_aspect("equal")
    ax.axis("off")

    # Node positions (x, y) — tree grows downward visually, but y=0 is bottom
    nodes = {
        "R":  (0, 4.0, "25.6", "#9CA3AF"),         # root / baseline
        "A1": (-1.2, 3.0, "58.8", "#93C5FD"),       # round 1
        "A2": (-1.2, 2.0, "73.8", "#93C5FD"),       # round 2
        "A3": (-1.2, 1.0, "73.8", "#FCA5A5"),       # stale → abandoned
        "B1": (0.6, 2.0, "82.5", "#86EFAC"),        # backtrack target
        "B2": (0.6, 1.0, "91.3", "#86EFAC"),        # continued
        "B3": (0.6, 0.0, "100", "#34D399"),         # best
    }

    edges = [
        ("R", "A1", "-"),
        ("A1", "A2", "-"),
        ("A2", "A3", "--"),   # stale
        ("R", "B1", "-"),
        ("B1", "B2", "-"),
        ("B2", "B3", "-"),
    ]

    # Draw edges
    for src, dst, style in edges:
        sx, sy, _, _ = nodes[src]
        dx, dy, _, _ = nodes[dst]
        ls = "--" if style == "--" else "-"
        color = "#D1D5DB" if style == "--" else "#6B7280"
        lw = 0.8 if style == "--" else 1.2
        ax.plot([sx, dx], [sy, dy], ls=ls, color=color, linewidth=lw, zorder=1)

    # Backtrack arrow
    ax.annotate("", xy=(0.15, 2.6), xytext=(-0.75, 1.3),
                arrowprops=dict(arrowstyle="->", color="#EF4444", lw=1.5,
                                connectionstyle="arc3,rad=-0.3"))
    ax.text(-0.8, 1.8, "backtrack", fontsize=6.5, color="#EF4444", ha="center",
            fontstyle="italic", rotation=30)

    # Draw nodes
    for name, (x, y, score, color) in nodes.items():
        circle = plt.Circle((x, y), 0.32, color=color, ec="white", linewidth=1.5, zorder=2)
        ax.add_patch(circle)
        ax.text(x, y, score, ha="center", va="center", fontsize=6.5, fontweight="bold", zorder=3)

    # Labels
    ax.text(0, 4.45, "Baseline", ha="center", fontsize=7, color="#6B7280")
    ax.text(-1.8, 1.0, "abandoned", ha="center", fontsize=6.5, color="#EF4444", fontstyle="italic")
    ax.text(1.3, 0.0, "global best", ha="center", fontsize=6.5, color="#059669", fontweight="bold")

    # Cross out abandoned
    ax.plot([-1.45, -0.95], [0.75, 1.25], color="#EF4444", linewidth=1.5, zorder=4)
    ax.plot([-1.45, -0.95], [1.25, 0.75], color="#EF4444", linewidth=1.5, zorder=4)

    ax.set_title("Search Tree with Backtracking", fontsize=9, pad=8)

    plt.tight_layout()
    fig.savefig(OUT / "tree.pdf")
    fig.savefig(OUT / "tree.png")
    plt.close(fig)
    print("  tree.pdf")


# ── Figure 4: Backtrack Depth ──

def fig_depth():
    fig, ax = plt.subplots(figsize=(2.8, 2.2))

    ks = ["k=1\n(aggressive)", "k=2\n(moderate)", "k=5\n(conservative)"]
    means = [79.0, 91.3, 79.2]
    stds = [9.5, 7.6, 7.3]
    bts = [2.7, 0.3, 0.0]
    colors = ["#FCA5A5", "#86EFAC", "#93C5FD"]

    bars = ax.bar(ks, means, yerr=stds, capsize=4, color=colors, edgecolor="white", linewidth=0.5, width=0.6)
    for bar, m, bt in zip(bars, means, bts):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5, f"{m:.1f}",
                ha="center", va="bottom", fontsize=7.5, fontweight="bold")
        ax.text(bar.get_x() + bar.get_width()/2, 5, f"{bt:.1f} bt",
                ha="center", va="bottom", fontsize=6.5, color="#6B7280")

    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Backtrack Threshold (Game-AI)")
    ax.set_ylim(0, 112)

    plt.tight_layout()
    fig.savefig(OUT / "depth.pdf")
    fig.savefig(OUT / "depth.png")
    plt.close(fig)
    print("  depth.pdf")


if __name__ == "__main__":
    print("Generating figures...")
    fig_ablation()
    fig_rounds()
    fig_tree()
    fig_depth()
    print("Done.")
