"""
MBCT Brain Viewer — standalone edition.

Combines the interactive statistical brain-map viewer with the lightweight
map-manipulation tools from the full MBCT suite:

  Viewer
    • Single / triplanar / glass-brain views, 3D surface (browser)
    • Draggable linked crosshair, MNI go-to, threshold & cluster controls
    • Live anatomical labels — Harvard-Oxford (gray matter) + JHU-ICBM
      (white-matter regions and tracts, with probabilities)

  Map Tools
    • Converter            (resample to a standard MNI grid)
    • Threshold & Binarize
    • ROI Tool             (build sphere/atlas ROIs, extract signal)
    • Combine Maps         (arithmetic and logical combinations)

Any tool result can be sent straight to the viewer with "Open in Viewer".
Meta-analysis tools live in the separate MBCT Meta-Analysis Tool, so this app
needs no NiMARE and no Neurosynth corpus.

Shares the exact same code as the full app, so fixes apply everywhere.
"""

import sys
import matplotlib
matplotlib.use('Agg')   # never FigureCanvasQTAgg — QLabel-based rendering only

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLabel, QTabWidget)
from PyQt6.QtGui import QIcon, QFont

import theme_manager as tm
from brain_viewer_stats_tab import BrainViewerStatsTab
from utilities_tab import UtilitiesTab
from connectivity_tab import ConnectivityTab

APP_TITLE = "MBCT Brain Viewer"


class BrainViewerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 860)

        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QLabel(f"  {APP_TITLE}")
        header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.setStyleSheet("color:#e6e9ef; background:#16171f; padding:12px 6px;")
        v.addWidget(header)

        self.tabs = QTabWidget()
        self.viewer = BrainViewerStatsTab()
        # only the lightweight map tools (no NiMARE / corpus dependencies)
        self.tools = UtilitiesTab(parent_main=self, tools='maps')
        self.connectivity = ConnectivityTab(parent_main=self)

        self.tabs.addTab(self.viewer, "🧠  Brain Viewer")
        self.tabs.addTab(self.connectivity, "🔗  Connectivity")
        self.tabs.addTab(self.tools, "🔧  Map Tools")
        v.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        # "Open in Viewer" from any tool -> load it and switch to the viewer
        try:
            self.tools.file_ready.connect(self._open_in_viewer)
        except Exception as e:
            print(f"⚠️ could not wire Open-in-Viewer: {e}")

        try:
            icon_path = tm.logo_for_theme(tm.CURRENT, variant='icon')
            if icon_path:
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass

    def _open_in_viewer(self, path):
        try:
            self.viewer.load_overlay_path(path)
            self.tabs.setCurrentWidget(self.viewer)
        except Exception as e:
            print(f"⚠️ could not open in viewer: {e}")


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

    win = BrainViewerWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
