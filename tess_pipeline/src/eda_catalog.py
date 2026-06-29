"""
eda_catalog.py
--------------
Exploratory data analysis plots for the cleaned TIC catalog.

Produces 10 publication-ready figures saved to plots/:

  fig_01_null_rates.png     – column fill-rate audit
  fig_02_classification.png – object type / luminosity class / WD flag
  fig_03_tmag.png           – TESS magnitude distributions
  fig_04_teff.png           – effective temperature distribution & spectral types
  fig_05_logg.png           – surface gravity distribution & dwarf/giant split
  fig_06_hr_proxy.png       – Kiel diagram proxy (Teff vs logg)
  fig_07_cmd.png            – colour-magnitude diagram (2-D histogram)
  fig_08_distance.png       – distance distributions
  fig_09_sky.png            – sky footprint
  fig_10_funnel.png         – target-selection funnel

Usage
-----
    python -m src.eda_catalog
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

from src.config import Config

# ---------------------------------------------------------------------------
# Global aesthetics
# ---------------------------------------------------------------------------

plt.style.use("dark_background")

plt.rcParams.update(
    {
        "figure.dpi":      120,
        "savefig.dpi":     150,
        "font.family":     "monospace",
        "axes.grid":       True,
        "grid.linewidth":  0.6,
    }
)

# Consistent accent palette
_C_BLUE   = "#4FC3F7"
_C_GREEN  = "#81C784"
_C_AMBER  = "#FFB74D"
_C_RED    = "#EF5350"
_C_VIOLET = "#CE93D8"
_C_CYAN   = "#80DEEA"


def _savefig(fig: plt.Figure, name: str, config: Config) -> None:
    """Save *fig* to config.PLOT_DIR/<name> and close it."""
    config.PLOT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.PLOT_DIR / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"saved: {name}")


# ---------------------------------------------------------------------------
# Figure 1 – Fill-rate audit
# ---------------------------------------------------------------------------

def fig_null_rates(df: pd.DataFrame, config: Config) -> None:
    """Horizontal bar chart of fill % for key TIC columns."""
    cols = [
        "Tmag", "GAIAmag", "Jmag", "w1mag", "plx",
        "Bmag", "Teff", "logg", "rad", "mass", "d", "contratio",
    ]
    present = [c for c in cols if c in df.columns]
    fill    = [df[c].notna().mean() * 100 for c in present]

    colors = []
    for f in fill:
        if f > 90:
            colors.append(_C_BLUE)
        elif f > 60:
            colors.append(_C_GREEN)
        elif f > 40:
            colors.append(_C_AMBER)
        else:
            colors.append(_C_RED)

    fig, ax = plt.subplots(figsize=(9, 6))
    bars = ax.barh(present[::-1], fill[::-1], color=colors[::-1], height=0.65)

    for bar, pct in zip(bars, fill[::-1]):
        ax.text(
            min(pct + 1, 97), bar.get_y() + bar.get_height() / 2,
            f"{pct:.1f}%", va="center", fontsize=8, color="white",
        )

    ax.set_xlim(0, 105)
    ax.set_xlabel("Fill rate (%)", fontsize=10)
    ax.set_title("Column Fill Rates — TIC Cleaned Catalog", fontsize=12, pad=12)
    ax.axvline(90, color=_C_BLUE,  lw=1, ls="--", alpha=0.6, label=">90 % (blue)")
    ax.axvline(60, color=_C_GREEN, lw=1, ls="--", alpha=0.6, label=">60 % (green)")
    ax.axvline(40, color=_C_AMBER, lw=1, ls="--", alpha=0.6, label=">40 % (amber)")
    ax.legend(fontsize=8, loc="lower right")

    _savefig(fig, "fig_01_null_rates.png", config)


# ---------------------------------------------------------------------------
# Figure 2 – Object classification overview
# ---------------------------------------------------------------------------

def fig_classification(df: pd.DataFrame, config: Config) -> None:
    """1×3: objType pie | lumclass pie | wdflag bar."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("TIC Object Classification Overview", fontsize=13, y=1.02)

    # [0] objType pie
    if "objType" in df.columns:
        vc = df["objType"].value_counts()
        axes[0].pie(
            vc.values, labels=vc.index, autopct="%1.1f%%",
            startangle=90,
            colors=plt.cm.Set2.colors,  # type: ignore[attr-defined]
            wedgeprops={"edgecolor": "0.2"},
        )
        axes[0].set_title("objType", fontsize=11)
    else:
        axes[0].text(0.5, 0.5, "objType not found", ha="center", va="center")

    # [1] lumclass pie (dropna)
    if "lumclass" in df.columns:
        vc2 = df["lumclass"].dropna().value_counts()
        axes[1].pie(
            vc2.values, labels=vc2.index, autopct="%1.1f%%",
            startangle=90,
            colors=plt.cm.Set3.colors,  # type: ignore[attr-defined]
            wedgeprops={"edgecolor": "0.2"},
        )
        axes[1].set_title("lumclass (non-null)", fontsize=11)
    else:
        axes[1].text(0.5, 0.5, "lumclass not found", ha="center", va="center")

    # [2] wdflag bar
    if "wdflag" in df.columns:
        vc3 = df["wdflag"].value_counts().sort_index()
        axes[2].bar(
            [str(v) for v in vc3.index], vc3.values,
            color=[_C_VIOLET, _C_AMBER][: len(vc3)], width=0.5,
        )
        axes[2].set_title("wdflag counts", fontsize=11)
        axes[2].set_xlabel("wdflag value")
        axes[2].set_ylabel("count")
        for x, y in enumerate(vc3.values):
            axes[2].text(x, y * 1.01, f"{y:,}", ha="center", fontsize=8)
    else:
        axes[2].text(0.5, 0.5, "wdflag not found", ha="center", va="center")

    fig.tight_layout()
    _savefig(fig, "fig_02_classification.png", config)


# ---------------------------------------------------------------------------
# Figure 3 – TESS magnitude distributions
# ---------------------------------------------------------------------------

def fig_tmag(df: pd.DataFrame, config: Config) -> None:
    """1×2: full Tmag histogram | zoomed Tmag<16 with shaded transit zone."""
    if "Tmag" not in df.columns:
        print("fig_tmag: Tmag column missing, skipping.")
        return

    tmag = df["Tmag"].dropna()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("TESS Magnitude Distribution", fontsize=13)

    # [0] Full distribution
    ax = axes[0]
    ax.hist(tmag, bins=80, color=_C_BLUE, alpha=0.85, edgecolor="none")
    ax.axvline(13, color=_C_GREEN, lw=1.5, ls="--", label="Tmag=13")
    ax.axvline(15, color=_C_AMBER, lw=1.5, ls="--", label="Tmag=15")
    ax.set_xlabel("Tmag")
    ax.set_ylabel("count")
    ax.set_title("All Stars")
    ax.legend(fontsize=9)

    # [1] Zoomed Tmag < 16 with shaded region
    ax2 = axes[1]
    tmag_zoom = tmag[tmag < 16]
    counts, edges = np.histogram(tmag_zoom, bins=80)
    ax2.bar(
        edges[:-1], counts, width=np.diff(edges),
        color=[_C_GREEN if e < 13 else _C_BLUE for e in edges[:-1]],
        alpha=0.85, align="edge", edgecolor="none",
    )
    ax2.axvspan(tmag_zoom.min(), 13, alpha=0.12, color=_C_GREEN)
    ax2.axvline(13, color=_C_GREEN, lw=1.5, ls="--", label="Tmag<13 (prime zone)")
    ax2.set_xlabel("Tmag")
    ax2.set_ylabel("count")
    ax2.set_title("Zoom: Tmag < 16")
    ax2.legend(fontsize=9)

    fig.tight_layout()
    _savefig(fig, "fig_03_tmag.png", config)


# ---------------------------------------------------------------------------
# Figure 4 – Effective temperature distributions
# ---------------------------------------------------------------------------

def fig_teff(df: pd.DataFrame, config: Config) -> None:
    """1×2: Teff histogram with spectral-type bands | SpType_est bar chart."""
    if "Teff" not in df.columns:
        print("fig_teff: Teff column missing, skipping.")
        return

    teff = df["Teff"].dropna()

    # Spectral-type band definitions [Teff_lo, Teff_hi, label, color]
    bands = [
        (0,     3700,  "M", "#EF5350"),
        (3700,  5200,  "K", "#FF8A65"),
        (5200,  6000,  "G", "#FFD54F"),
        (6000,  7500,  "F", "#AED581"),
        (7500,  10000, "A", "#4FC3F7"),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Effective Temperature Distribution", fontsize=13)

    # [0] Histogram with band overlays
    ax = axes[0]
    ax.hist(teff, bins=80, color=_C_CYAN, alpha=0.75, edgecolor="none", zorder=3)
    for lo, hi, label, color in bands:
        ax.axvspan(lo, hi, alpha=0.15, color=color, label=label, zorder=1)
        mid = (lo + hi) / 2
        ax.text(mid, ax.get_ylim()[1] * 0.92, label, ha="center", fontsize=9,
                color=color, fontweight="bold")
    ax.set_xlabel("Teff (K)")
    ax.set_ylabel("count")
    ax.set_title("Teff Histogram")
    ax.legend(fontsize=8, ncol=5, loc="upper right")

    # [1] SpType_est bar chart
    ax2 = axes[1]
    if "SpType_est" in df.columns:
        sp_order = ["M", "K", "G", "F", "A", "B", "O"]
        sp_vc    = df["SpType_est"].value_counts()
        sp_vc    = sp_vc.reindex([s for s in sp_order if s in sp_vc.index])
        sp_colors = {
            "M": "#EF5350", "K": "#FF8A65", "G": "#FFD54F",
            "F": "#AED581", "A": "#4FC3F7", "B": "#CE93D8", "O": "#80DEEA",
        }
        bar_colors = [sp_colors.get(s, _C_BLUE) for s in sp_vc.index]
        bars = ax2.bar(sp_vc.index.astype(str), sp_vc.values,
                       color=bar_colors, width=0.6)
        for bar, val in zip(bars, sp_vc.values):
            ax2.text(bar.get_x() + bar.get_width() / 2, val * 1.01,
                     f"{val:,}", ha="center", fontsize=8)
        ax2.set_xlabel("Spectral Type")
        ax2.set_ylabel("count")
        ax2.set_title("SpType_est Distribution")
    else:
        ax2.text(0.5, 0.5, "SpType_est not found", ha="center", va="center")

    fig.tight_layout()
    _savefig(fig, "fig_04_teff.png", config)


# ---------------------------------------------------------------------------
# Figure 5 – Surface gravity
# ---------------------------------------------------------------------------

def fig_logg(df: pd.DataFrame, config: Config) -> None:
    """1×2: logg histogram with giant/dwarf shading | logg bin bar chart."""
    if "logg" not in df.columns:
        print("fig_logg: logg column missing, skipping.")
        return

    logg = df["logg"].dropna()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Surface Gravity (log g) Distribution", fontsize=13)

    # [0] Histogram with shaded regions
    ax = axes[0]
    ax.hist(logg, bins=70, color=_C_VIOLET, alpha=0.80, edgecolor="none")
    ax.axvline(4.0, color=_C_AMBER, lw=2, ls="--", label="log g = 4.0 (dwarf limit)")
    ax.axvspan(logg.min(), 4.0, alpha=0.10, color=_C_RED, label="Giant region")
    ax.axvspan(4.0, logg.max(), alpha=0.10, color=_C_GREEN, label="Dwarf region")
    ax.set_xlabel("log g")
    ax.set_ylabel("count")
    ax.set_title("log g Histogram")
    ax.legend(fontsize=9)

    # [1] Binned bar chart
    ax2 = axes[1]
    bins_edges = [3.0, 3.5, 4.0, 4.2, 4.5, 4.8, 5.0, 5.3]
    counts, _ = np.histogram(logg, bins=bins_edges)
    labels = [f"{bins_edges[i]}–{bins_edges[i+1]}" for i in range(len(bins_edges) - 1)]
    bar_colors = [_C_RED if b < 4.0 else _C_GREEN for b in bins_edges[:-1]]
    bars = ax2.bar(labels, counts, color=bar_colors, width=0.7)
    for bar, val in zip(bars, counts):
        ax2.text(bar.get_x() + bar.get_width() / 2, val * 1.01,
                 f"{val:,}", ha="center", fontsize=8)
    ax2.set_xlabel("log g bin")
    ax2.set_ylabel("count")
    ax2.set_title("log g Binned Counts")
    ax2.tick_params(axis="x", rotation=35)

    fig.tight_layout()
    _savefig(fig, "fig_05_logg.png", config)


# ---------------------------------------------------------------------------
# Figure 6 – HR proxy (Kiel diagram)
# ---------------------------------------------------------------------------

def fig_hr_proxy(df: pd.DataFrame, config: Config) -> None:
    """Scatter of Teff vs logg coloured by Tmag (Kiel-diagram proxy)."""
    needed = {"Teff", "logg", "Tmag"}
    if not needed.issubset(df.columns):
        print(f"fig_hr_proxy: missing columns {needed - set(df.columns)}, skipping.")
        return

    sub = df[list(needed)].dropna()
    if len(sub) > 30_000:
        sub = sub.sample(30_000, random_state=42)

    fig, ax = plt.subplots(figsize=(9, 7))
    sc = ax.scatter(
        sub["Teff"], sub["logg"],
        c=sub["Tmag"], cmap="plasma_r",
        s=2, alpha=0.5, linewidths=0,
    )
    plt.colorbar(sc, ax=ax, label="Tmag")
    ax.axhline(4.0, color=_C_AMBER, lw=1.5, ls="--", label="log g = 4.0")
    ax.invert_xaxis()
    ax.set_xlabel("Teff (K)")
    ax.set_ylabel("log g")
    ax.set_title(f"Kiel Diagram Proxy  (n={len(sub):,})", fontsize=12)
    ax.legend(fontsize=9)

    _savefig(fig, "fig_06_hr_proxy.png", config)


# ---------------------------------------------------------------------------
# Figure 7 – Colour-magnitude diagram
# ---------------------------------------------------------------------------

def fig_cmd(df: pd.DataFrame, config: Config) -> None:
    """2-D histogram: (gaiabp − gaiarp) vs GAIAmag with log colour scale."""
    needed = {"gaiabp", "gaiarp", "GAIAmag"}
    if not needed.issubset(df.columns):
        print(f"fig_cmd: missing columns {needed - set(df.columns)}, skipping.")
        return

    sub = df[list(needed)].dropna().copy()
    sub["bp_rp_cmd"] = sub["gaiabp"] - sub["gaiarp"]

    fig, ax = plt.subplots(figsize=(8, 7))
    h = ax.hist2d(
        sub["bp_rp_cmd"], sub["GAIAmag"],
        bins=200,
        norm=mcolors.LogNorm(),
        cmap="inferno",
    )
    plt.colorbar(h[3], ax=ax, label="log count")
    ax.invert_yaxis()
    ax.set_xlabel("BP − RP (mag)")
    ax.set_ylabel("Gaia G (mag)")
    ax.set_title(f"Colour–Magnitude Diagram  (n={len(sub):,})", fontsize=12)

    _savefig(fig, "fig_07_cmd.png", config)


# ---------------------------------------------------------------------------
# Figure 8 – Distance distributions
# ---------------------------------------------------------------------------

def fig_distance(df: pd.DataFrame, config: Config) -> None:
    """1×2: histogram of d (pc) | scatter d vs Tmag (log x-scale)."""
    if "d" not in df.columns:
        print("fig_distance: d column missing, skipping.")
        return

    dist = df["d"].dropna()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Stellar Distance Distribution", fontsize=13)

    # [0] Histogram of d
    ax = axes[0]
    ax.hist(dist, bins=80, color=_C_CYAN, alpha=0.80, edgecolor="none")
    ax.set_xlabel("Distance (pc)")
    ax.set_ylabel("count")
    ax.set_title("Distance Histogram")

    # [1] Scatter d vs Tmag
    ax2 = axes[1]
    if "Tmag" in df.columns:
        sub2 = df[["d", "Tmag"]].dropna()
        if len(sub2) > 20_000:
            sub2 = sub2.sample(20_000, random_state=42)
        sc = ax2.scatter(
            sub2["d"], sub2["Tmag"],
            s=1, alpha=0.3, color=_C_VIOLET, linewidths=0,
        )
        ax2.set_xscale("log")
        ax2.set_xlabel("Distance (pc, log scale)")
        ax2.set_ylabel("Tmag")
        ax2.set_title(f"Distance vs Tmag  (n={len(sub2):,})")
    else:
        ax2.text(0.5, 0.5, "Tmag not found", ha="center", va="center")

    fig.tight_layout()
    _savefig(fig, "fig_08_distance.png", config)


# ---------------------------------------------------------------------------
# Figure 9 – Sky footprint
# ---------------------------------------------------------------------------

def fig_sky(df: pd.DataFrame, config: Config) -> None:
    """1×2: 2-D density of all stars | bright star scatter (Tmag<14)."""
    needed = {"ra", "dec"}
    if not needed.issubset(df.columns):
        print(f"fig_sky: missing columns {needed - set(df.columns)}, skipping.")
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Sky Footprint — TIC Southern Polar Cap", fontsize=13)

    # [0] 2-D density
    ax = axes[0]
    coords = df[["ra", "dec"]].dropna()
    h = ax.hist2d(
        coords["ra"], coords["dec"],
        bins=200,
        norm=mcolors.LogNorm(),
        cmap="magma",
    )
    plt.colorbar(h[3], ax=ax, label="log count")
    ax.set_xlabel("RA (deg)")
    ax.set_ylabel("Dec (deg)")
    ax.set_title(f"All Stars (n={len(coords):,})")

    # [1] Bright star scatter
    ax2 = axes[1]
    if "Tmag" in df.columns:
        bright = df[df["Tmag"] < 14][["ra", "dec", "Tmag"]].dropna()
        sc = ax2.scatter(
            bright["ra"], bright["dec"],
            c=bright["Tmag"], cmap="cool",
            s=3, alpha=0.7, linewidths=0,
        )
        plt.colorbar(sc, ax=ax2, label="Tmag")
        ax2.set_xlabel("RA (deg)")
        ax2.set_ylabel("Dec (deg)")
        ax2.set_title(f"Bright Stars Tmag < 14  (n={len(bright):,})")
    else:
        ax2.text(0.5, 0.5, "Tmag not found", ha="center", va="center")

    fig.tight_layout()
    _savefig(fig, "fig_09_sky.png", config)


# ---------------------------------------------------------------------------
# Figure 10 – Target-selection funnel
# ---------------------------------------------------------------------------

def fig_funnel(df: pd.DataFrame, config: Config) -> None:
    """Horizontal bar chart showing the progressive target-selection funnel."""
    n_total = len(df)

    # Build funnel steps
    steps: list[tuple[str, int]] = [("All TIC", n_total)]

    sub = df
    if "objType" in df.columns:
        sub = sub[sub["objType"] == "STAR"]
        steps.append(("objType == STAR", len(sub)))

    if "lumclass" in sub.columns:
        sub = sub[sub["lumclass"] == "DWARF"]
        steps.append(("lumclass == DWARF", len(sub)))

    if "wdflag" in sub.columns:
        sub = sub[sub["wdflag"] != 1]
        steps.append(("wdflag ≠ 1", len(sub)))

    if "Tmag" in sub.columns:
        sub15 = sub[sub["Tmag"] < 15]
        steps.append(("Tmag < 15", len(sub15)))
        sub13 = sub[sub["Tmag"] < 13]
        steps.append(("Tmag < 13", len(sub13)))

    if "prime_target" in df.columns:
        steps.append(("prime_target", int(df["prime_target"].sum())))

    labels  = [s[0] for s in steps]
    counts  = [s[1] for s in steps]
    max_cnt = counts[0] if counts[0] > 0 else 1

    cmap   = plt.cm.RdYlGn  # type: ignore[attr-defined]
    colors = [cmap(c / max_cnt) for c in counts]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(labels[::-1], counts[::-1], color=colors[::-1], height=0.6)

    for bar, cnt in zip(bars, counts[::-1]):
        pct = cnt / n_total * 100
        ax.text(
            bar.get_width() + max_cnt * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{cnt:,}  ({pct:.1f}%)",
            va="center", fontsize=9, color="white",
        )

    ax.set_xlim(0, max_cnt * 1.30)
    ax.set_xlabel("Star count")
    ax.set_title("Target-Selection Funnel", fontsize=13, pad=12)
    ax.grid(axis="y", linewidth=0)

    fig.tight_layout()
    _savefig(fig, "fig_10_funnel.png", config)


# ---------------------------------------------------------------------------
# Master EDA runner
# ---------------------------------------------------------------------------

def run_eda(df: pd.DataFrame, config: Config) -> None:
    """Call all 10 EDA figure functions in order."""
    print("\n" + "=" * 60)
    print("[eda] Starting EDA — generating 10 figures")
    print("=" * 60)

    fig_null_rates(df, config)
    fig_classification(df, config)
    fig_tmag(df, config)
    fig_teff(df, config)
    fig_logg(df, config)
    fig_hr_proxy(df, config)
    fig_cmd(df, config)
    fig_distance(df, config)
    fig_sky(df, config)
    fig_funnel(df, config)

    print("=" * 60)
    print(f"[eda] All figures saved to: {config.PLOT_DIR}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from src.config import Config as _Config

    _cfg     = _Config()
    _parquet = _cfg.CLEAN_DIR / "tic_clean.parquet"

    print(f"[eda] Loading {_parquet} …")
    _df = pd.read_parquet(_parquet)
    print(f"[eda] Loaded {len(_df):,} rows × {len(_df.columns)} columns")

    run_eda(_df, _cfg)
