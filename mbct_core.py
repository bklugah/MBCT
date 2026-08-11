"""
mbct_core.py — MBCT (core edition) launcher.

The edition described in the manuscript: the multimodal annotation pipeline
only — Home, Analysis, Results and Help. The Brain Viewer, Connectivity and
Utilities tabs are excluded (they ship in the full edition, and as the separate
MBCT Brain Viewer / MBCT Meta-Analysis Tool applications).

The edition flag must be set BEFORE the main module is imported, because that
module decides at import time which tabs to build.
"""

import os

# Must precede the import below.
os.environ['MBCT_EDITION'] = 'core'

from nct_desktop_app_IMPROVED import main

if __name__ == '__main__':
    main()
