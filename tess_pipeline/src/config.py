"""
config.py
---------
Central configuration for the TESS exoplanet detection pipeline.
All pipeline modules should import settings from here rather than
hard-coding values inline.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # ── Directory layout ──────────────────────────────────────────────────────
    DATA_DIR: Path = field(default_factory=lambda: Path("data"))
    RAW_DIR: Path = field(default_factory=lambda: Path("data/raw"))
    CLEAN_DIR: Path = field(default_factory=lambda: Path("data/clean"))
    PLOT_DIR: Path = field(default_factory=lambda: Path("plots"))
    LOG_DIR: Path = field(default_factory=lambda: Path("logs"))

    # ── Sky search parameters ─────────────────────────────────────────────────
    DEC_CENTER: float = -89.0       # Declination centre of the search cone (degrees)
    SEARCH_RADIUS: float = 1.5      # Search cone radius (degrees)

    # ── MAST API settings ─────────────────────────────────────────────────────
    MAST_URL: str = "https://mast.stsci.edu/api/v0.1/invoke"
    PAGESIZE: int = 50_000          # Maximum rows per paginated API request

    # ── Target-star quality cuts ──────────────────────────────────────────────
    TMAG_LIMIT: float = 13.0        # Faint-end TESS magnitude limit
    LOGG_LIMIT: float = 4.0         # Lower bound on log g (exclude giants)


# Module-level singleton – import and use directly:
#   from src.config import CFG
CFG = Config()
