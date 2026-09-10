#Klugah-Brown 2026
"""
paths.py — portable path resolution for MBCT.

Works the same whether the app runs from source or as a PyInstaller bundle.

Two kinds of location:

  resource_dir()  -> where READ-ONLY bundled data lives (templates, atlases,
                     precomputed JSON, assets). Next to the executable in a
                     PyInstaller one-folder build; the source tree otherwise.

  user_data_dir() -> where the app may WRITE (Neurosynth corpus a user adds,
                     downloaded atlases, saved sessions, logs). An OS-appropriate
                     per-user folder, never the install directory (which is
                     read-only on Windows/macOS).
"""

import os
import sys
from pathlib import Path

APP_NAME = "MBCT"


def resource_dir() -> Path:
    """Directory containing bundled read-only resources."""
    
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return Path(base)
        return Path(sys.executable).resolve().parent
    
    return Path(__file__).resolve().parent


def user_data_dir() -> Path:
    """Per-user writable directory for caches, downloads, and saved sessions."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux / other
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def resource_path(*parts) -> Path:
    """Path to a bundled resource, e.g. resource_path('mni_templates')."""
    return resource_dir().joinpath(*parts)


def user_path(*parts) -> Path:
    """Path inside the per-user writable dir, e.g. user_path('sessions')."""
    p = user_data_dir().joinpath(*parts)
    return p
