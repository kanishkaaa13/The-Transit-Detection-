<h1 align="center">🌌 TESS Exoplanet Explorer</h1>

<p align="center">
  <b>AI-Powered Exoplanet Transit Detection & Mission Control Dashboard using NASA TESS Photometry</b>
</p>

<p align="center">
  Built for ISRO Bharatiya Antariksh Hackathon (ISRO BAH 2026)
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/PyTorch-1D_CNN-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white"/>
  <img src="https://img.shields.io/badge/scikit--learn-XGBoost-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white"/>
  <img src="https://img.shields.io/badge/NASA-TESS-0B3D91?style=for-the-badge&logo=nasa&logoColor=white"/>
  <img src="https://img.shields.io/badge/React-Dashboard-61DAFB?style=for-the-badge&logo=react&logoColor=black"/>
  <img src="https://img.shields.io/badge/TypeScript-Frontend-3178C6?style=for-the-badge&logo=typescript&logoColor=white"/>
  <img src="https://img.shields.io/badge/Vite-Build-646CFF?style=for-the-badge&logo=vite&logoColor=white"/>
  <img src="https://img.shields.io/badge/Tailwind-UI-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white"/>
</p>

<p align="center">
  🔭 Detect &nbsp;•&nbsp; 📊 Classify &nbsp;•&nbsp; 🌍 Visualize &nbsp;•&nbsp; 🤖 Explain
</p>

---

## 🚀 Overview

**TESS Exoplanet Explorer** is an end-to-end astronomy pipeline and interactive dashboard that identifies potential exoplanets by analyzing photometric light curves from NASA's Transiting Exoplanet Survey Satellite (TESS).

Starting from a catalog of **~19 lakh (1.9 million) TIC stars**, the pipeline applies a series of hard astrophysical filters and machine learning models to surface a curated set of high-confidence transit candidates — currently **63 prime targets** analyzed from a single TESS sector — which are then explored through an interactive web dashboard.

The goal is not just detection, but **interpretability**: every prediction is accompanied by the physical reasoning behind it, so researchers can trust and verify what the model finds.

---

## ✨ Key Features

- ✅ **Transparent Detection** — Interpretable AI with class-level reasoning, not a black box
- ✅ **Prioritized Analysis** — Confidence-scored candidate ranking for efficient follow-up
- ✅ **Habitability Indicators** — Derived parameter-based habitable zone assessment
- ✅ **Interactive Sky Visualization** — Real celestial sky map with classified targets plotted by true coordinates
- ✅ **Automated Reporting** — One-click scientific detection & analysis report generation
- ✅ **AI Chat Assistant** — Natural language Q&A on transit parameters and detections
- ✅ **Mission Control Dashboard** — Live pipeline stats, activity log, and priority queue

---

## 🛰 Pipeline Architecture

```text
TIC CATALOG (~19,00,000 stars)
        │
        ▼
┌──────────────────────────────────────────┐
│ STAGE 1 — HARD FILTERS                    │
│ lumclass == DWARF, wdflag != 1,           │
│ Tmag < 13, logg > 4.0, disposition clean  │
│ → OUTPUT: ~1,100 prime targets            │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│ STAGE 2 — TRANSIT DETECTION               │
│ Box Least Squares (BLS) / TLS             │
│ → period, depth, duration, mid-time       │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│ STAGE 3 — PARAMETER ESTIMATION            │
│ R_planet, orbital distance (Kepler's 3rd),│
│ density consistency, SNR, HZ check        │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│ STAGE 4 — FALSE POSITIVE CLASSIFICATION   │
│ 1D CNN + tabular ML (RF / XGBoost)        │
│ Tests: blend ratio, density, eclipse      │
│ shape, secondary eclipse, odd-even depth  │
│ → [Planet, EB, Blend, Noise, FP]          │
└──────────────────────────────────────────┘
        │
        ▼
   63 Classified Targets → Dashboard
```

---

## 🧠 Detection & Classification

| Stage | Method | Purpose |
|---|---|---|
| Signal search | BLS / TLS | Find periodic transit-like dips |
| Classification | 1D CNN | Learn transit shape directly from folded light curve |
| Vetting | Random Forest / XGBoost | Tabular false-positive checks (blend, density, eclipse tests) |
| Output | Ensemble confidence | Final probability across Planet / EB / Blend / Noise classes |

Each detection includes a **"Why this classification?"** breakdown showing which of the five vetting tests passed or failed, so results are explainable rather than opaque.

---

## 🌍 Dashboard

Built as a standalone React + TypeScript single-page app:

- **Light Curve Viewer** — fetch and visualize TESS photometry per TIC ID, run on-demand detection
- **Southern Sky Map** — real celestial imagery with classified targets plotted at true RA/Dec, zoom/pan, classification filters
- **Priority Queue** — all targets ranked by detection confidence
- **Summary Reports** — auto-generated scientific writeups per target, exportable as PDF
- **AI Chat Assistant** — ask natural-language questions about any target's parameters or classification

---

## 🛠 Tech Stack

**Pipeline / ML**
🐍 Python · PyTorch · scikit-learn · XGBoost · Astropy · Astroquery · Lightkurve · `batman` (transit modeling) · NumPy · Pandas

**Dashboard**
⚛ React · TypeScript · Vite · Tailwind CSS · shadcn/ui · Recharts · Framer Motion

**Data & APIs**
☁ NASA MAST (TESS light curves) · TIC Catalog · AstronomyAPI (sky chart rendering)

---

## 📊 Current Scope

- Catalog analyzed: **~19,00,000 TIC stars** (Stage 1 EDA)
- Prime targets after filtering: **~1,100**
- Targets with full light curve analysis: **63** (single TESS sector, 120s SPOC cadence)
- Classifier: 1D CNN v1.0 + tabular ensemble vetting

> This is a hackathon proof-of-concept run on real TESS data for a curated target set. Full-catalog automation and multi-sector analysis are the next planned phase.

---

## 🔭 Roadmap

- [ ] Multi-sector light curve aggregation
- [ ] Automated end-to-end pipeline (catalog → detection → dashboard, no manual steps)
- [ ] Expand classifier ensemble (CNN + tabular stacking)
- [ ] Cross-validated accuracy benchmarking on confirmed TESS Objects of Interest (TOIs)
- [ ] Live light curve ingestion for arbitrary TIC IDs

---

## 👥 Team

*Add team member names and roles here.*

---

<p align="center">Built with 🔭 for ISRO Bharatiya Antariksh Hackathon 2026</p>