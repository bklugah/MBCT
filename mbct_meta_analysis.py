"""
MBCT Meta-Analysis Tool — standalone edition.

A lightweight app exposing only the Neurosynth meta-analysis tools from the
full MBCT suite:
    • Term  → Map          (Neurosynth meta-analytic map for a term)
    • Coordinate → Terms   (decode a coordinate to terms, FDR-corrected)
    • MACM                 (meta-analytic coactivation; inside Coordinate→Terms)

Shares the exact same code as the full app (utilities_tab.UtilitiesTab with
meta_only=True), so fixes made to the full suite apply here automatically.
"""

import sys
import matplotlib
matplotlib.use('Agg')   # never FigureCanvasQTAgg — QLabel-based rendering only

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont

import theme_manager as tm
from paths import resource_path
from utilities_tab import UtilitiesTab

APP_TITLE = "MBCT Meta-Analysis Tool"


class MetaAnalysisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1100, 760)

        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # slim header
        header = QLabel(f"  {APP_TITLE}")
        header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.setStyleSheet("color:#e6e9ef; background:#16171f; padding:12px 6px;")
        v.addWidget(header)

        # the meta-analysis-only utilities panel
        self.tools = UtilitiesTab(parent_main=None, meta_only=True)
        v.addWidget(self.tools, 1)

        self.setCentralWidget(central)

        # window icon (fall back silently if missing)
        try:
            icon_path = tm.logo_for_theme(tm.CURRENT, variant='icon')
            if icon_path:
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    try:
        tm.apply_theme(app, tm.detect_os_theme())
    except Exception:
        tm.apply_theme(app, 'dark')
    try:
        icon_path = tm.logo_for_theme(tm.CURRENT, variant='icon')
        if icon_path:
            app.setWindowIcon(QIcon(str(icon_path)))
    except Exception:
        pass

    win = MetaAnalysisWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
