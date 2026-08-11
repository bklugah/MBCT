"""
connectivity_tab.py — "Connectivity" view for the MBCT Brain Viewer.

Load a seed-based functional-connectivity map and get:

  • an OVERVIEW glass brain — seed + target nodes, lines weighted by strength
  • a GRID of small glass brains — one per seed->target connection, each
    labelled with its anatomical region and r-value
  • a table of connections (exportable to CSV)

Rendering follows the viewer's established pattern: matplotlib on the Agg
backend, saved to PNG and shown in a QLabel (never FigureCanvasQTAgg).
"""

import os
from io import BytesIO

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QPushButton, QLineEdit, QDoubleSpinBox,
                             QSpinBox, QScrollArea, QTableWidget,
                             QTableWidgetItem, QHeaderView, QFileDialog,
                             QMessageBox, QCheckBox, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QImage

import connectivity_view as cvx


class ConnectivityTab(QWidget):
    """Seed-based FC connectome viewer."""

    file_ready = pyqtSignal(str)   # so a loaded map can be sent to the Viewer

    def __init__(self, parent_main=None):
        super().__init__()
        self.parent_main = parent_main
        self.data = None
        self.affine = None
        self.path = None
        self.seed = None
        self.targets = []
        self._figs = []

        self.setObjectName("connectivityTab")
        self.setStyleSheet(
            "#connectivityTab { background:#0a0a14; }"
            "#connectivityTab QLabel { color:#e6e9ef; }"
            "#connectivityTab QCheckBox { color:#e6e9ef; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("Connectivity  ·  seed-based FC connectome")
        title.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#7dd3fc;")
        root.addWidget(title)

        blurb = QLabel(
            "Visualises an <b>already-computed</b> seed-based FC map. The seed is "
            "taken as the map's global maximum (editable) and each supra-threshold "
            "cluster peak is reported as a target, labelled anatomically.<br>"
            "<span style='color:#f0a93b;'>Note: this tool performs no statistical "
            "testing and applies no multiple-comparison correction — statistical "
            "validity comes from the map you load. Lines indicate association with "
            "the seed, not direct anatomical connections.</span>")
        blurb.setWordWrap(True)
        blurb.setStyleSheet("color:#aeb8c6;")
        root.addWidget(blurb)

        # ---------------- controls ----------------
        g = QGridLayout()
        g.addWidget(QLabel("FC map:"), 0, 0)
        self.path_edit = QLineEdit(); self.path_edit.setReadOnly(True)
        g.addWidget(self.path_edit, 0, 1, 1, 3)
        b = QPushButton("Browse…"); b.clicked.connect(self._browse)
        g.addWidget(b, 0, 4)

        g.addWidget(QLabel("Seed MNI (x, y, z):"), 1, 0)
        seed_row = QHBoxLayout()
        self.sx = QLineEdit(); self.sy = QLineEdit(); self.sz = QLineEdit()
        for w in (self.sx, self.sy, self.sz):
            w.setMaximumWidth(70); seed_row.addWidget(w)
        self.auto_seed = QCheckBox("auto (global max)")
        self.auto_seed.setChecked(True)
        self.auto_seed.stateChanged.connect(self._toggle_seed_fields)
        seed_row.addWidget(self.auto_seed); seed_row.addStretch()
        sw = QWidget(); sw.setLayout(seed_row)
        g.addWidget(sw, 1, 1, 1, 4)
        self._toggle_seed_fields()

        g.addWidget(QLabel("Display threshold |r| ≥"), 2, 0)
        self.thr = QDoubleSpinBox(); self.thr.setRange(0.0, 1.0)
        self.thr.setSingleStep(0.05); self.thr.setValue(0.30)
        self.thr.setMaximumWidth(90)
        g.addWidget(self.thr, 2, 1)

        g.addWidget(QLabel("Min cluster (voxels):"), 2, 2)
        self.ext = QSpinBox(); self.ext.setRange(1, 100000); self.ext.setValue(20)
        self.ext.setMaximumWidth(100)
        g.addWidget(self.ext, 2, 3)

        g.addWidget(QLabel("Max connections:"), 3, 0)
        self.maxn = QSpinBox(); self.maxn.setRange(1, 60); self.maxn.setValue(12)
        self.maxn.setMaximumWidth(90)
        g.addWidget(self.maxn, 3, 1)

        g.addWidget(QLabel("Grid columns:"), 3, 2)
        self.ncols = QSpinBox(); self.ncols.setRange(1, 8); self.ncols.setValue(3)
        self.ncols.setMaximumWidth(90)
        g.addWidget(self.ncols, 3, 3)
        root.addLayout(g)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("🔗  Build connectome")
        self.run_btn.clicked.connect(self._build)
        btn_row.addWidget(self.run_btn)
        self.save_btn = QPushButton("💾  Save figures")
        self.save_btn.clicked.connect(self._save_figs)
        self.save_btn.setEnabled(False)
        btn_row.addWidget(self.save_btn)
        self.csv_btn = QPushButton("⬇  Export table (CSV)")
        self.csv_btn.clicked.connect(self._export_csv)
        self.csv_btn.setEnabled(False)
        btn_row.addWidget(self.csv_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            "background:#141520; border:1px solid #2a3a5a; border-radius:6px;"
            " padding:6px 8px; color:#ffffff;")
        root.addWidget(self.status)

        # ---------------- displays ----------------
        split = QSplitter(Qt.Orientation.Vertical)

        self.overview = QLabel("Load an FC map and click “Build connectome”.")
        self.overview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overview.setMinimumHeight(230)
        self.overview.setStyleSheet(
            "background:#000000; border:1px solid #2a3a5a; border-radius:8px;")
        split.addWidget(self.overview)

        lower = QWidget(); lv = QVBoxLayout(lower)
        lv.setContentsMargins(0, 0, 0, 0); lv.setSpacing(6)
        gl = QLabel("Individual connections")
        gl.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        gl.setStyleSheet("color:#7dd3fc;")
        lv.addWidget(gl)

        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_label = QLabel("")
        self.grid_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid_label.setStyleSheet("background:#000000;")
        self.grid_scroll.setWidget(self.grid_label)
        self.grid_scroll.setMinimumHeight(200)
        lv.addWidget(self.grid_scroll, 1)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["x", "y", "z", "peak r", "voxels", "Region", "White matter"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(190)
        lv.addWidget(self.table)

        split.addWidget(lower)
        split.setSizes([320, 420])
        root.addWidget(split, 1)

    # ------------------------------------------------------------------ data
    def _toggle_seed_fields(self):
        on = not self.auto_seed.isChecked()
        for w in (self.sx, self.sy, self.sz):
            w.setEnabled(on)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open FC map", "", "NIfTI (*.nii *.nii.gz)")
        if path:
            self.load_path(path)

    def load_path(self, path):
        try:
            import nibabel as nib
            img = nib.load(path)
            self.data = np.asarray(img.dataobj, dtype=np.float32)
            if self.data.ndim == 4:
                self.data = self.data[..., 0]
            self.affine = img.affine
            self.path = path
            self.path_edit.setText(path)
            s, v = cvx.find_seed(self.data, self.affine)
            self.sx.setText(f"{s[0]:.0f}"); self.sy.setText(f"{s[1]:.0f}")
            self.sz.setText(f"{s[2]:.0f}")
            self.status.setText(
                f"Loaded {os.path.basename(path)} — shape {self.data.shape}; "
                f"peak r={v:.2f} at ({s[0]:.0f}, {s[1]:.0f}, {s[2]:.0f}).")
        except Exception as e:
            QMessageBox.critical(self, "Load error", str(e))

    # -------------------------------------------------------------- building
    def _build(self):
        if self.data is None:
            QMessageBox.information(self, "No map", "Load an FC map first.")
            return
        try:
            seed = None
            if not self.auto_seed.isChecked():
                seed = (float(self.sx.text()), float(self.sy.text()),
                        float(self.sz.text()))
        except ValueError:
            QMessageBox.warning(self, "Invalid seed", "Enter numeric MNI x, y, z.")
            return

        self.status.setText("Extracting connections…")
        try:
            self.seed, self.targets = cvx.extract_connections(
                self.data, self.affine,
                threshold=self.thr.value(),
                min_extent=self.ext.value(),
                seed_mni=seed,
                max_targets=self.maxn.value())
        except Exception as e:
            self.status.setText(f"Extraction failed: {e}")
            return

        if not self.targets:
            self.status.setText(
                "No connected clusters survived the threshold — lower |r| or "
                "reduce the minimum cluster size.")
            self.overview.setText("No connections found.")
            self.grid_label.clear(); self.table.setRowCount(0)
            return

        self.sx.setText(f"{self.seed[0]:.0f}"); self.sy.setText(f"{self.seed[1]:.0f}")
        self.sz.setText(f"{self.seed[2]:.0f}")
        self._close_figs()

        # overview
        try:
            fig = cvx.overview_figure(self.seed, self.targets)
            self._figs.append(('overview', fig))
            self._fig_to_label(fig, self.overview)
        except Exception as e:
            self.overview.setText(f"Overview failed: {e}")

        # grid
        try:
            gfig = cvx.grid_figure(self.seed, self.targets,
                                   ncols=self.ncols.value())
            if gfig is not None:
                self._figs.append(('connections', gfig))
                self._fig_to_label(gfig, self.grid_label, scale_to_width=True)
        except Exception as e:
            self.grid_label.setText(f"Grid failed: {e}")

        # table
        rows = cvx.connection_table(self.seed, self.targets)
        self._rows = rows
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount(); self.table.insertRow(i)
            for c, key in enumerate(['x', 'y', 'z', 'r', 'voxels',
                                     'region', 'white_matter']):
                self.table.setItem(i, c, QTableWidgetItem(str(r[key])))

        self.save_btn.setEnabled(True); self.csv_btn.setEnabled(True)
        sx, sy, sz = (round(c) for c in self.seed)
        self.status.setText(
            f"Seed ({sx}, {sy}, {sz}) → {len(self.targets)} cluster peak(s) at "
            f"|r| ≥ {self.thr.value():.2f}, ≥ {self.ext.value()} voxels. "
            f"Descriptive only — peaks read from your map; no testing applied here.")

    # -------------------------------------------------------------- display
    def _fig_to_label(self, fig, label, scale_to_width=False):
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=fig.dpi,
                    facecolor=fig.get_facecolor())
        buf.seek(0)
        img = QImage(); img.loadFromData(buf.getvalue())
        pm = QPixmap.fromImage(img)
        if scale_to_width:
            w = max(1, self.grid_scroll.viewport().width() - 4)
            if pm.width() > w:
                pm = pm.scaledToWidth(w, Qt.TransformationMode.SmoothTransformation)
            label.setMinimumSize(pm.size())
        else:
            lw, lh = max(1, label.width()), max(1, label.height())
            if pm.width() > lw or pm.height() > lh:
                pm = pm.scaled(lw, lh, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(pm)

    def _close_figs(self):
        for _, f in self._figs:
            try:
                plt.close(f)
            except Exception:
                pass
        self._figs = []

    # --------------------------------------------------------------- export
    def _save_figs(self):
        if not self._figs:
            return
        d = QFileDialog.getExistingDirectory(self, "Save figures to folder")
        if not d:
            return
        base = os.path.splitext(os.path.basename(self.path or "connectome"))[0]
        base = base.replace('.nii', '')
        saved = []
        for name, fig in self._figs:
            out = os.path.join(d, f"{base}_{name}.png")
            try:
                fig.savefig(out, dpi=200, facecolor=fig.get_facecolor())
                saved.append(os.path.basename(out))
            except Exception as e:
                QMessageBox.critical(self, "Save error", str(e)); return
        self.status.setText("Saved: " + ", ".join(saved))

    def _export_csv(self):
        if not getattr(self, '_rows', None):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export connections", "", "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith('.csv'):
            path += '.csv'
        try:
            import csv
            sx, sy, sz = self.seed
            with open(path, 'w', newline='', encoding='utf-8') as fh:
                w = csv.writer(fh)
                w.writerow(['# MBCT Connectivity — cluster peaks from a '
                            'user-supplied seed-based FC map'])
                w.writerow(['# Descriptive only: peaks read from the input map; '
                            'no statistical testing or multiple-comparison '
                            'correction applied by this tool.'])
                w.writerow(['# source_map', os.path.basename(self.path or '')])
                w.writerow(['# display_threshold_abs_r', self.thr.value()])
                w.writerow(['# min_cluster_voxels', self.ext.value()])
                w.writerow(['seed_x', 'seed_y', 'seed_z'])
                w.writerow([round(sx, 1), round(sy, 1), round(sz, 1)])
                w.writerow([])
                w.writerow(['x', 'y', 'z', 'peak_r', 'voxels', 'region',
                            'white_matter'])
                for r in self._rows:
                    w.writerow([r['x'], r['y'], r['z'], r['r'], r['voxels'],
                                r['region'], r['white_matter']])
            self.status.setText(f"Exported {len(self._rows)} connections to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export error", str(e))
