"""
utils.py
--------
Shared utility helpers for the TESS exoplanet detection pipeline.
Pipeline logic is intentionally absent here — this module contains
only infrastructure-level helpers (logging setup, directory creation,
etc.) that every other module may need.
"""

import logging
import sys
from pathlib import Path

from src.config import CFG


# ── Logging ───────────────────────────────────────────────────────────────────

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger that writes to both stdout and a rotating log file."""
    logger = logging.getLogger(name)
    if logger.handlers:
        # Avoid adding duplicate handlers when the module is reloaded
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler (one log file per named logger)
    CFG.LOG_DIR.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(CFG.LOG_DIR / f"{name}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


# ── Directory helpers ─────────────────────────────────────────────────────────

def ensure_dirs() -> None:
    """Create all pipeline directories defined in Config if they don't exist."""
    dirs = [CFG.DATA_DIR, CFG.RAW_DIR, CFG.CLEAN_DIR, CFG.PLOT_DIR, CFG.LOG_DIR]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
