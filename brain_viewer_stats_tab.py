"""
brain_viewer_stats_tab.py
A standalone statistical Brain Viewer tab.

Load any NIfTI (activation/statistical map, cluster image, ROI, or mask) over
a template underlay and inspect it with SPM/FSL/MRIcroGL-style tools:
  - triplanar (axial/coronal/sagittal) rendering with crosshair
  - mouse-scroll to change slice, click to inspect value + coordinates
  - intensity thresholding (positive/negative tails)
  - connected-component cluster extent analysis -> sortable peaks table
  - whole-image / supra-threshold intensity statistics
  - intensity histogram
  - export each cluster as its own NIfTI
  - up to 3 simultaneous overlays, each with its own colormap & opacity

Visual style: minimal dark-navy, deliberately cleaner/flatter than the
Results tab so the two viewers feel distinct.
"""

from pathlib import Path
from io import BytesIO

import numpy as np
import nibabel as nib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from PyQt6.QtWidgets import (
    QApplication,
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QSlider, QDoubleSpinBox, QSpinBox, QFrame, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QTabWidget, QListWidget, QListWidgetItem, QAbstractItemView, QSplitter,
    QSizePolicy, QLineEdit
)
from PyQt6.QtGui import QPixmap, QImage, QColor, QFont
from PyQt6.QtCore import Qt, QEvent, QTimer

import viewer_stats as vs
try:
    import theme_manager as tm
except Exception:
    tm = None
try:
    import anatomy_lookup as anat
except Exception:
    anat = None
try:
    import whitematter_lookup as wm
except Exception:
    wm = None


# ---------------------------------------------------------------------------
# Overlay record
# ---------------------------------------------------------------------------

class _Overlay:
    __slots__ = ('name', 'data', 'affine', 'disp_data', 'cmap', 'alpha',
                 'visible', 'thr_pos', 'thr_neg', 'vmin', 'vmax')

    def __init__(self, name, data, affine):
        self.name = name
        self.data = data            # original data (for stats / clusters / export)
        self.affine = affine
        self.disp_data = data       # data resampled to the display grid (set later)
        self.cmap = 'hot'
        self.alpha = 0.75
        self.visible = True
        self.thr_pos = None
        self.thr_neg = None
        finite = data[np.isfinite(data) & (data != 0)]
        if finite.size:
            self.vmin = float(np.percentile(finite, 2))
            self.vmax = float(np.percentile(finite, 98))
        else:
            self.vmin, self.vmax = 0.0, 1.0


class BrainViewerStatsTab(QWidget):
    """Standalone statistical brain map viewer."""

    OVERLAY_CMAPS = ['hot', 'cool', 'viridis', 'plasma', 'inferno', 'jet',
                     'autumn', 'winter', 'spring', 'Reds', 'Blues', 'Greens',
                     'RdBu_r', 'seismic', 'bwr']
    UNDERLAY_CMAPS = ['gray', 'bone', 'gist_gray', 'binary_r']

    def __init__(self):
        super().__init__()

        # underlay
        self.under_data = None
        self.under_affine = None
        self.under_cmap = 'gray'
        self.under_vmin = 0.0
        self.under_vmax = 1.0

        # overlays (max 3)
        self.overlays = []           # list[_Overlay]
        self.active_ov = None        # index into overlays for the stats panel

        # view state
        self.view = 'axial'
        self.slice_idx = {'axial': 0, 'coronal': 0, 'sagittal': 0}
        self.crosshair_ijk = None    # voxel in underlay space
        self._debug_click = True     # TEMP: print click mapping diagnostics
        self.triplanar = True
        self.glass_mode = False
        self.zoom = 1.0

        # cluster results for the active overlay
        self.clusters = []
        self.cluster_labels = None

        self.template_dir = self._guess_template_dir()

        self._render_timer = QTimer(); self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render)

        self._compute_responsive_dims()
        self._build_ui()
        self._scan_templates()
        self._apply_style()

    # ------------------------------------------------------- responsive sizing
    def _compute_responsive_dims(self):
        """Derive panel widths / canvas minimums from the actual screen size so
        the tab looks right on a small laptop and a large 4K display alike."""
        screen_w, screen_h = 1920, 1080  # safe fallback
        try:
            scr = QApplication.primaryScreen()
            if scr is not None:
                geo = scr.availableGeometry()
                screen_w, screen_h = geo.width(), geo.height()
        except Exception:
            pass

        # left rail: ~14% of width, clamped to a readable range
        self.rail_w = int(max(220, min(screen_w * 0.14, 320)))
        # right stats panel: ~22% of width, clamped
        self.right_w = int(max(360, min(screen_w * 0.22, 520)))
        # initial center share is whatever is left
        self.center_w = max(480, screen_w - self.rail_w - self.right_w)
        # canvas minimum: scale with screen but stay modest so small screens cope
        self.canvas_min = int(max(180, min(screen_h * 0.22, 360)))
        # histogram / table minimum heights scale a little too
        self.hist_min_h = int(max(150, min(screen_h * 0.18, 260)))
        self.table_min_h = int(max(140, min(screen_h * 0.18, 260)))


    # ------------------------------------------------------------------ paths
    def _guess_template_dir(self):
        here = Path(__file__).resolve().parent
        for c in (here / 'mni_templates', here / 'brain_templates',
                  here / 'Resources' / 'standard',
                  here.parent / 'mni_templates'):
            if c.exists():
                return c
        return None

    def _scan_templates(self):
        self.template_combo.clear()
        self.template_combo.addItem("— no underlay —", None)
        self._template_paths = {}
        if self.template_dir and self.template_dir.exists():
            files = sorted(list(self.template_dir.glob('*.nii.gz')) +
                           list(self.template_dir.glob('*.nii')))
            for f in files:
                self.template_combo.addItem(f.stem, str(f))
                self._template_paths[f.stem] = str(f)
        # auto-pick an MNI-ish default
        for i in range(self.template_combo.count()):
            t = self.template_combo.itemText(i).lower()
            if 'mni' in t or 'mni152' in t:
                self.template_combo.setCurrentIndex(i)
                break

    # ------------------------------------------------------------------- UI
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- left rail: loading + display controls ----
        left = self._build_left_rail()

        # ---- center: viewer ----
        center = QFrame(); center.setObjectName("viewerArea")
        cv = QVBoxLayout(center); cv.setContentsMargins(8, 8, 8, 8); cv.setSpacing(6)

        # top bar: view buttons + coordinate readout
        topbar = QHBoxLayout()
        self.view_btns = {}
        for v in ('axial', 'coronal', 'sagittal'):
            b = QPushButton(v.capitalize()); b.setCheckable(True)
            b.setObjectName("viewBtn"); b.setMaximumWidth(90)
            b.clicked.connect(lambda _, vv=v: self._set_single_view(vv))
            self.view_btns[v] = b
            topbar.addWidget(b)
        self.tri_btn = QPushButton("Triplanar"); self.tri_btn.setCheckable(True)
        self.tri_btn.setChecked(True); self.tri_btn.setObjectName("viewBtn")
        self.tri_btn.clicked.connect(self._set_triplanar)
        topbar.addWidget(self.tri_btn)
        self.glass_btn = QPushButton("Glass Brain"); self.glass_btn.setCheckable(True)
        self.glass_btn.setObjectName("viewBtn"); self.glass_btn.setMaximumWidth(110)
        self.glass_btn.clicked.connect(self._set_glass)
        topbar.addWidget(self.glass_btn)
        self.surf3d_btn = QPushButton("3D Surface")
        self.surf3d_btn.setObjectName("viewBtn"); self.surf3d_btn.setMaximumWidth(110)
        self.surf3d_btn.setToolTip("Open an interactive, rotatable 3D surface view in your browser")
        self.surf3d_btn.clicked.connect(self._open_3d_surface)
        topbar.addWidget(self.surf3d_btn)
        topbar.addStretch()
        self.coord_lbl = QLabel("Voxel: —    MNI: —    Value: —")
        self.coord_lbl.setObjectName("coordReadout")
        self.coord_lbl.setFont(QFont('Consolas', 10))
        topbar.addWidget(self.coord_lbl)
        cv.addLayout(topbar)

        # MNI "go to" row + anatomical label
        mni_row = QHBoxLayout()
        mni_row.addWidget(QLabel("Go to MNI:"))
        self.mni_x = QLineEdit(); self.mni_x.setPlaceholderText("X"); self.mni_x.setMaximumWidth(60)
        self.mni_y = QLineEdit(); self.mni_y.setPlaceholderText("Y"); self.mni_y.setMaximumWidth(60)
        self.mni_z = QLineEdit(); self.mni_z.setPlaceholderText("Z"); self.mni_z.setMaximumWidth(60)
        for w in (self.mni_x, self.mni_y, self.mni_z):
            w.setFont(QFont('Consolas', 10))
            w.returnPressed.connect(self._goto_mni)
            mni_row.addWidget(w)
        go_btn = QPushButton("Go"); go_btn.setMaximumWidth(50)
        go_btn.clicked.connect(self._goto_mni)
        mni_row.addWidget(go_btn)
        mni_row.addSpacing(16)
        self.anat_lbl = QLabel("📍 —")
        self.anat_lbl.setObjectName("anatReadout")
        self.anat_lbl.setFont(QFont('Segoe UI', 10))
        self.anat_lbl.setWordWrap(True)
        mni_row.addWidget(self.anat_lbl, 1)
        cv.addLayout(mni_row)

        # the canvases
        self.canvas_holder = QFrame(); self.canvas_holder.setObjectName("canvasHolder")
        self.canvas_layout = QHBoxLayout(self.canvas_holder)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0); self.canvas_layout.setSpacing(4)
        self.canvas_axial = self._make_canvas()
        self.canvas_coronal = self._make_canvas()
        self.canvas_sagittal = self._make_canvas()
        self.canvas_single = self._make_canvas()
        for c in (self.canvas_axial, self.canvas_coronal, self.canvas_sagittal):
            self.canvas_layout.addWidget(c)
        self.canvas_layout.addWidget(self.canvas_single)
        self.canvas_single.hide()
        cv.addWidget(self.canvas_holder, 1)

        # slice + zoom sliders
        srow = QHBoxLayout()
        srow.addWidget(QLabel("Slice"))
        self.slice_slider = QSlider(Qt.Orientation.Horizontal)
        self.slice_slider.valueChanged.connect(self._on_slice)
        srow.addWidget(self.slice_slider, 3)
        srow.addWidget(QLabel("Zoom"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 300); self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom)
        srow.addWidget(self.zoom_slider, 1)
        cv.addLayout(srow)

        # ---- right: stats panel ----
        right = self._build_right_panel()

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(left); split.addWidget(center); split.addWidget(right)
        split.setSizes([self.rail_w, self.center_w, self.right_w])
        # center viewer absorbs extra space when the window grows/shrinks
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        split.setChildrenCollapsible(False)
        root.addWidget(split)

    def _make_canvas(self):
        lbl = QLabel(); lbl.setObjectName("brainCanvas")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setMinimumSize(self.canvas_min, self.canvas_min)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lbl.installEventFilter(self)
        return lbl

    def _build_left_rail(self):
        f = QFrame(); f.setObjectName("leftRail")
        f.setMinimumWidth(210); f.setMaximumWidth(self.rail_w)
        L = QVBoxLayout(f); L.setContentsMargins(12, 12, 12, 12); L.setSpacing(10)

        title = QLabel("BRAIN VIEWER"); title.setObjectName("railTitle")
        title.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        L.addWidget(title)
        sub = QLabel("Statistical map inspection")
        sub.setObjectName("railSub"); L.addWidget(sub)

        L.addWidget(self._rule())

        L.addWidget(self._h("UNDERLAY"))
        self.template_combo = QComboBox()
        self.template_combo.currentIndexChanged.connect(self._on_template)
        L.addWidget(self.template_combo)
        urow = QHBoxLayout(); urow.addWidget(QLabel("Colormap"))
        self.under_cmap_combo = QComboBox(); self.under_cmap_combo.addItems(self.UNDERLAY_CMAPS)
        self.under_cmap_combo.currentTextChanged.connect(self._on_under_cmap)
        urow.addWidget(self.under_cmap_combo); L.addLayout(urow)

        L.addWidget(self._rule())

        L.addWidget(self._h("OVERLAYS  (max 3)"))
        self.btn_load = QPushButton("➕  Load map / ROI / mask")
        self.btn_load.setObjectName("primaryBtn")
        self.btn_load.clicked.connect(self._load_overlay)
        L.addWidget(self.btn_load)
        self.ov_list = QListWidget(); self.ov_list.setMaximumHeight(96)
        self.ov_list.currentRowChanged.connect(self._on_ov_selected)
        L.addWidget(self.ov_list)
        orow = QHBoxLayout()
        self.btn_remove = QPushButton("Remove"); self.btn_remove.clicked.connect(self._remove_overlay)
        orow.addWidget(self.btn_remove)
        self.chk_visible = QCheckBox("Visible"); self.chk_visible.setChecked(True)
        self.chk_visible.stateChanged.connect(self._on_visible_toggle)
        orow.addWidget(self.chk_visible); L.addLayout(orow)

        # per-overlay appearance
        L.addWidget(self._h("APPEARANCE"))
        crow = QHBoxLayout(); crow.addWidget(QLabel("Colormap"))
        self.ov_cmap_combo = QComboBox(); self.ov_cmap_combo.addItems(self.OVERLAY_CMAPS)
        self.ov_cmap_combo.currentTextChanged.connect(self._on_ov_cmap)
        crow.addWidget(self.ov_cmap_combo); L.addLayout(crow)
        arow = QHBoxLayout(); arow.addWidget(QLabel("Opacity"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100); self.opacity_slider.setValue(75)
        self.opacity_slider.valueChanged.connect(self._on_opacity)
        arow.addWidget(self.opacity_slider); L.addLayout(arow)

        L.addStretch()
        return f

    def _build_right_panel(self):
        f = QFrame(); f.setObjectName("rightPanel")
        f.setMinimumWidth(340); f.setMaximumWidth(self.right_w)
        L = QVBoxLayout(f); L.setContentsMargins(10, 12, 10, 12); L.setSpacing(8)

        L.addWidget(self._h("THRESHOLD & CLUSTERS"))

        # threshold controls
        trow = QGridLayout()
        trow.addWidget(QLabel("Positive ≥"), 0, 0)
        self.thr_pos = QDoubleSpinBox(); self.thr_pos.setRange(-1e6, 1e6)
        self.thr_pos.setDecimals(3); self.thr_pos.setValue(0.0); self.thr_pos.setSingleStep(0.1)
        trow.addWidget(self.thr_pos, 0, 1)
        self.chk_pos = QCheckBox("on"); self.chk_pos.setChecked(True); trow.addWidget(self.chk_pos, 0, 2)
        trow.addWidget(QLabel("Negative ≤"), 1, 0)
        self.thr_neg = QDoubleSpinBox(); self.thr_neg.setRange(-1e6, 1e6)
        self.thr_neg.setDecimals(3); self.thr_neg.setValue(0.0); self.thr_neg.setSingleStep(0.1)
        trow.addWidget(self.thr_neg, 1, 1)
        self.chk_neg = QCheckBox("on"); self.chk_neg.setChecked(False); trow.addWidget(self.chk_neg, 1, 2)
        trow.addWidget(QLabel("Min extent (vox)"), 2, 0)
        self.min_extent = QSpinBox(); self.min_extent.setRange(0, 100000); self.min_extent.setValue(10)
        trow.addWidget(self.min_extent, 2, 1)
        trow.addWidget(QLabel("Connectivity"), 3, 0)
        self.conn_combo = QComboBox(); self.conn_combo.addItems(['6', '18', '26'])
        self.conn_combo.setCurrentText('18'); trow.addWidget(self.conn_combo, 3, 1)
        L.addLayout(trow)

        # ── Live threshold slider (drag to set the positive threshold) ──
        thr_slide_row = QHBoxLayout()
        thr_slide_row.addWidget(QLabel("Threshold"))
        self.thr_slider = QSlider(Qt.Orientation.Horizontal)
        self.thr_slider.setRange(0, 1000)   # mapped to [vmin..vmax] of active overlay
        self.thr_slider.setValue(0)
        self.thr_slider.valueChanged.connect(self._on_thr_slider)
        thr_slide_row.addWidget(self.thr_slider, 1)
        self.thr_slider_lbl = QLabel("0.000")
        self.thr_slider_lbl.setFont(QFont('Consolas', 9))
        self.thr_slider_lbl.setMinimumWidth(54)
        thr_slide_row.addWidget(self.thr_slider_lbl)
        L.addLayout(thr_slide_row)

        # ── Live cluster-extent slider ──
        ext_slide_row = QHBoxLayout()
        ext_slide_row.addWidget(QLabel("Min cluster"))
        self.ext_slider = QSlider(Qt.Orientation.Horizontal)
        self.ext_slider.setRange(0, 500)
        self.ext_slider.setValue(10)
        self.ext_slider.valueChanged.connect(self._on_ext_slider)
        ext_slide_row.addWidget(self.ext_slider, 1)
        self.ext_slider_lbl = QLabel("10 vox")
        self.ext_slider_lbl.setFont(QFont('Consolas', 9))
        self.ext_slider_lbl.setMinimumWidth(54)
        ext_slide_row.addWidget(self.ext_slider_lbl)
        L.addLayout(ext_slide_row)

        brow = QHBoxLayout()
        self.btn_analyze = QPushButton("⚡ Analyze clusters")
        self.btn_analyze.setObjectName("primaryBtn")
        self.btn_analyze.clicked.connect(self._run_clusters)
        brow.addWidget(self.btn_analyze)
        self.btn_export_cl = QPushButton("💾 Export clusters")
        self.btn_export_cl.clicked.connect(self._export_clusters)
        brow.addWidget(self.btn_export_cl)
        L.addLayout(brow)

        # cluster table
        self.cl_table = QTableWidget(); self.cl_table.setColumnCount(5)
        self.cl_table.setHorizontalHeaderLabels(['#', 'Voxels', 'mm³', 'Peak', 'MNI (x,y,z)'])
        self.cl_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cl_table.verticalHeader().setVisible(False)
        self.cl_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cl_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cl_table.setMinimumHeight(self.table_min_h)
        self.cl_table.clicked.connect(self._on_cluster_click)
        L.addWidget(self.cl_table, 1)

        # tabs: stats / histogram
        tabs = QTabWidget()
        # stats text
        self.stats_lbl = QLabel("Load a map to see statistics.")
        self.stats_lbl.setObjectName("statsText"); self.stats_lbl.setWordWrap(True)
        self.stats_lbl.setFont(QFont('Consolas', 9))
        self.stats_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        sw = QWidget(); sl = QVBoxLayout(sw); sl.addWidget(self.stats_lbl); sl.addStretch()
        tabs.addTab(sw, "Statistics")
        # histogram
        self.hist_canvas = QLabel(); self.hist_canvas.setObjectName("histCanvas")
        self.hist_canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hist_canvas.setMinimumHeight(self.hist_min_h)
        hw = QWidget(); hl = QVBoxLayout(hw); hl.addWidget(self.hist_canvas)
        tabs.addTab(hw, "Histogram")
        L.addWidget(tabs, 1)

        return f

    def _h(self, text):
        l = QLabel(text); l.setObjectName("sectionHead")
        l.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold)); return l

    def _rule(self):
        fr = QFrame(); fr.setObjectName("rule"); fr.setFixedHeight(1); return fr

    # --------------------------------------------------------------- loading
    def _on_template(self, idx):
        path = self.template_combo.currentData()
        if not path:
            self.under_data = None; self.under_affine = None
            self._queue(); return
        try:
            img = nib.load(path)
            d = img.get_fdata()
            if d.ndim > 3: d = d[..., 0]
            self.under_data = np.asarray(d, dtype=np.float32)
            self.under_affine = img.affine
            finite = self.under_data[np.isfinite(self.under_data) & (self.under_data != 0)]
            if finite.size:
                self.under_vmin = float(np.percentile(finite, 2))
                self.under_vmax = float(np.percentile(finite, 98))
            self._reset_slices(self.under_data.shape)
            if self.crosshair_ijk is None:
                self.crosshair_ijk = tuple(s // 2 for s in self.under_data.shape)
            # existing overlays must be re-projected onto the new underlay grid
            for ov in self.overlays:
                self._resample_overlay_for_display(ov)
            self._queue()
        except Exception as e:
            QMessageBox.critical(self, "Underlay error", str(e))

    def _load_overlay(self):
        if len(self.overlays) >= 3:
            QMessageBox.information(self, "Limit", "Up to 3 overlays at once. Remove one first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Load map / ROI / mask", "", "NIfTI (*.nii *.nii.gz)")
        if not path:
            return
        self.load_overlay_path(path)

    def load_overlay_path(self, path):
        """Load a specific NIfTI file as an overlay (no dialog). Public so other
        tabs (e.g. Utilities) can hand a freshly-made file straight to the viewer."""
        if len(self.overlays) >= 3:
            QMessageBox.information(self, "Limit", "Up to 3 overlays at once. Remove one first.")
            return
        try:
            img = nib.load(path)
            d = img.get_fdata()
            if d.ndim > 3: d = d[..., 0]
            ov = _Overlay(Path(path).stem, np.asarray(d, dtype=np.float32), img.affine)
            # build the display version on the current reference grid
            self._resample_overlay_for_display(ov)
            self.overlays.append(ov)
            self.ov_list.addItem(QListWidgetItem(ov.name))
            self.ov_list.setCurrentRow(len(self.overlays) - 1)
            # if no underlay yet, use overlay geometry for slices/crosshair
            if self.under_data is None:
                self._reset_slices(ov.data.shape)
                self.crosshair_ijk = tuple(s // 2 for s in ov.data.shape)
            # sensible default threshold from the data
            self.thr_pos.setValue(round(float(ov.vmax) * 0.5, 2))
            self._update_stats_panel()
            self._queue()
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Overlay error", str(e))

    def _resample_overlay_for_display(self, ov):
        """Resample an overlay onto the current display grid (underlay if loaded,
        else its own grid) so it always renders aligned, regardless of the
        overlay's native resolution/space. Original data is preserved for stats."""
        ref_shape = self._ref_shape()
        ref_aff = self.under_affine if self.under_data is not None else None
        # nothing to match against, or already identical grid -> use original
        if ref_aff is None or (ov.data.shape == ref_shape and
                               np.allclose(ov.affine, ref_aff, atol=1e-4)):
            ov.disp_data = ov.data
            return
        try:
            from nilearn.image import resample_img
            src = nib.Nifti1Image(ov.data, ov.affine)
            res = resample_img(src, target_affine=ref_aff,
                               target_shape=ref_shape, interpolation='continuous',
                               force_resample=True, copy_header=True)
            dd = res.get_fdata()
            if dd.ndim > 3: dd = dd[..., 0]
            ov.disp_data = np.asarray(dd, dtype=np.float32)
            print(f"ℹ️ Resampled overlay '{ov.name}' {ov.data.shape} -> {ov.disp_data.shape} for display")
        except TypeError:
            # older nilearn without force_resample/copy_header
            from nilearn.image import resample_img
            src = nib.Nifti1Image(ov.data, ov.affine)
            res = resample_img(src, target_affine=ref_aff, target_shape=ref_shape,
                               interpolation='continuous')
            dd = res.get_fdata()
            if dd.ndim > 3: dd = dd[..., 0]
            ov.disp_data = np.asarray(dd, dtype=np.float32)
        except Exception as e:
            print(f"⚠️ Could not resample overlay '{ov.name}': {e}; showing on native grid.")
            ov.disp_data = ov.data

    def _remove_overlay(self):
        r = self.ov_list.currentRow()
        if 0 <= r < len(self.overlays):
            self.overlays.pop(r)
            self.ov_list.takeItem(r)
            self.clusters = []; self.cluster_labels = None
            self._refresh_cluster_table()
            self._update_stats_panel()
            self._queue()

    def _on_ov_selected(self, row):
        if 0 <= row < len(self.overlays):
            self.active_ov = row
            ov = self.overlays[row]
            self.ov_cmap_combo.blockSignals(True)
            self.ov_cmap_combo.setCurrentText(ov.cmap); self.ov_cmap_combo.blockSignals(False)
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(int(ov.alpha * 100)); self.opacity_slider.blockSignals(False)
            self.chk_visible.blockSignals(True)
            self.chk_visible.setChecked(ov.visible); self.chk_visible.blockSignals(False)
            self._update_stats_panel()

    # ---------------------------------------------------- appearance handlers
    def _active(self):
        if self.active_ov is not None and 0 <= self.active_ov < len(self.overlays):
            return self.overlays[self.active_ov]
        return None

    def _on_thr_slider(self, val):
        """Map slider [0..1000] to the active overlay's value range and apply
        it as the positive threshold, live."""
        ov = self._active() or (self.overlays[0] if self.overlays else None)
        if ov is None:
            self.thr_slider_lbl.setText("—")
            return
        try:
            lo = float(getattr(ov, 'vmin', None) if ov.vmin is not None else np.nanmin(ov.data))
            hi = float(getattr(ov, 'vmax', None) if ov.vmax is not None else np.nanmax(ov.data))
        except Exception:
            lo, hi = 0.0, 1.0
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            lo, hi = 0.0, 1.0
        thr = lo + (val / 1000.0) * (hi - lo)
        self.thr_slider_lbl.setText(f"{thr:.3f}")
        # drive the existing positive-threshold spinbox (keeps everything in sync)
        self.chk_pos.setChecked(True)
        self.thr_pos.blockSignals(True)
        self.thr_pos.setValue(thr)
        self.thr_pos.blockSignals(False)
        self._queue()   # re-render with new threshold applied to the map

    def _on_ext_slider(self, val):
        """Live minimum cluster extent (voxels)."""
        self.ext_slider_lbl.setText(f"{val} vox")
        self.min_extent.blockSignals(True)
        self.min_extent.setValue(val)
        self.min_extent.blockSignals(False)
        # If clusters were already computed, recompute with the new extent.
        if getattr(self, 'clusters', None):
            self._run_clusters()

    def _on_under_cmap(self, c): self.under_cmap = c; self._queue()
    def _on_ov_cmap(self, c):
        ov = self._active()
        if ov: ov.cmap = c; self._queue()
    def _on_opacity(self, v):
        ov = self._active()
        if ov: ov.alpha = v / 100.0; self._queue()
    def _on_visible_toggle(self, _):
        ov = self._active()
        if ov: ov.visible = self.chk_visible.isChecked(); self._queue()

    # ----------------------------------------------------------- view control
    def _set_single_view(self, v):
        self.view = v; self.triplanar = False; self.glass_mode = False
        self.glass_btn.setChecked(False)
        self.tri_btn.setChecked(False)
        for vv, b in self.view_btns.items():
            b.setChecked(vv == v)
        for c in (self.canvas_axial, self.canvas_coronal, self.canvas_sagittal):
            c.hide()
        self.canvas_single.show()
        self._sync_slice_slider()
        self._queue()

    def _set_triplanar(self):
        self.triplanar = True; self.glass_mode = False
        self.glass_btn.setChecked(False)
        self.tri_btn.setChecked(True)
        for b in self.view_btns.values(): b.setChecked(False)
        self.canvas_single.hide()
        for c in (self.canvas_axial, self.canvas_coronal, self.canvas_sagittal):
            c.show()
        self._sync_slice_slider()
        self._queue()

    def _set_glass(self):
        """Glass-brain mode: render the active overlay as a BrainNet-style
        maximum-intensity glass-brain projection (via nilearn) on the single canvas."""
        self.glass_mode = True; self.triplanar = False
        self.glass_btn.setChecked(True)
        self.tri_btn.setChecked(False)
        for b in self.view_btns.values(): b.setChecked(False)
        for c in (self.canvas_axial, self.canvas_coronal, self.canvas_sagittal):
            c.hide()
        self.canvas_single.show()
        self._queue()

    def _ref_shape(self):
        if self.under_data is not None: return self.under_data.shape
        if self.overlays: return self.overlays[0].data.shape
        return None

    def _reset_slices(self, shape):
        self.slice_idx = {'axial': shape[2] // 2,
                          'coronal': shape[1] // 2,
                          'sagittal': shape[0] // 2}
        self._sync_slice_slider()

    def _axis_for_view(self, v):
        return {'axial': 2, 'coronal': 1, 'sagittal': 0}[v]

    def _sync_slice_slider(self):
        shape = self._ref_shape()
        if not shape: return
        v = self.view
        ax = self._axis_for_view(v)
        self.slice_slider.blockSignals(True)
        self.slice_slider.setRange(0, shape[ax] - 1)
        self.slice_slider.setValue(self.slice_idx[v])
        self.slice_slider.blockSignals(False)

    def _on_slice(self, val):
        self.slice_idx[self.view] = val
        if self.crosshair_ijk is not None:
            ijk = list(self.crosshair_ijk)
            ijk[self._axis_for_view(self.view)] = val
            self.crosshair_ijk = tuple(ijk)
        self._queue()

    def _on_zoom(self, v):
        self.zoom = v / 100.0; self._queue()

    # ------------------------------------------------------ mouse interaction
    def eventFilter(self, obj, event):
        canvases = {self.canvas_axial: 'axial', self.canvas_coronal: 'coronal',
                    self.canvas_sagittal: 'sagittal', self.canvas_single: self.view}
        if obj in canvases and self._ref_shape() is not None:
            if event.type() == QEvent.Type.Wheel:
                view = canvases[obj] if obj is not self.canvas_single else self.view
                ax = self._axis_for_view(view)
                shape = self._ref_shape()
                step = 1 if event.angleDelta().y() > 0 else -1
                new = max(0, min(self.slice_idx[view] + step, shape[ax] - 1))
                self.slice_idx[view] = new
                if self.crosshair_ijk is not None:
                    ijk = list(self.crosshair_ijk); ijk[ax] = new
                    self.crosshair_ijk = tuple(ijk)
                if view == self.view:
                    self.slice_slider.blockSignals(True)
                    self.slice_slider.setValue(new); self.slice_slider.blockSignals(False)
                self._queue()
                return True
            if event.type() == QEvent.Type.MouseButtonPress:
                if getattr(self, 'glass_mode', False) and obj is self.canvas_single:
                    self._dragging_xhair = True
                    self._handle_glass_click(obj, event)
                    return True
                view = canvases[obj] if obj is not self.canvas_single else self.view
                self._dragging_xhair = True
                self._handle_click(obj, view, event)
                return True
            if event.type() == QEvent.Type.MouseMove:
                if getattr(self, '_dragging_xhair', False):
                    if getattr(self, 'glass_mode', False) and obj is self.canvas_single:
                        self._handle_glass_click(obj, event)
                        return True
                    view = canvases[obj] if obj is not self.canvas_single else self.view
                    self._handle_click(obj, view, event)
                    return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._dragging_xhair = False
                return True
        return super().eventFilter(obj, event)

    def _goto_mni(self):
        """Move the crosshair to a user-typed MNI coordinate."""
        shape = self._ref_shape()
        aff = self.under_affine if self.under_affine is not None else (
            self.overlays[0].affine if self.overlays else None)
        if shape is None or aff is None:
            QMessageBox.information(self, "No image",
                                    "Load an underlay or overlay first.")
            return
        try:
            x = float(self.mni_x.text()); y = float(self.mni_y.text()); z = float(self.mni_z.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid MNI",
                                "Please enter numeric X, Y, Z values.")
            return
        # world(MNI) -> voxel via inverse affine
        inv = np.linalg.inv(aff)
        v = inv @ np.array([x, y, z, 1.0])
        ijk = [int(round(v[0])), int(round(v[1])), int(round(v[2]))]
        ijk = [max(0, min(ijk[a], shape[a] - 1)) for a in range(3)]
        self.crosshair_ijk = tuple(ijk)
        # keep each plane's slice index in sync with the crosshair
        for view in ('axial', 'coronal', 'sagittal'):
            ax = self._axis_for_view(view)
            self.slice_idx[view] = ijk[ax]
        # update the active single-view slider too
        if not self.triplanar:
            ax = self._axis_for_view(self.view)
            self.slice_slider.blockSignals(True)
            self.slice_slider.setValue(ijk[ax])
            self.slice_slider.blockSignals(False)
        self._update_coord_readout()
        self._queue()

    def _handle_click(self, label, view, event):
        """Map a click on a brain canvas to a voxel using the axes' OWN inverse
        transform — exact, mirroring the Results tab. Adapted to this viewer's
        plain .T render transform (no fliplr/rot90)."""
        shape = self._ref_shape()
        if shape is None:
            return
        ax = getattr(self, '_view_ax', {}).get(view)
        pix = label.pixmap()
        if ax is None or pix is None or pix.isNull():
            return
        img_w, img_h = pix.width(), pix.height()
        lab_w, lab_h = label.width(), label.height()
        # pixmap is centered in the label (AlignCenter): subtract the offset
        off_x = max(0, (lab_w - img_w) / 2.0)
        off_y = max(0, (lab_h - img_h) / 2.0)
        ix = event.pos().x() - off_x
        iy = event.pos().y() - off_y
        if getattr(self, '_debug_click', False):
            print(f"[click] view={view} label=({lab_w}x{lab_h}) pix=({img_w}x{img_h}) "
                  f"pos=({event.pos().x()},{event.pos().y()}) -> img=({ix:.1f},{iy:.1f})")
        if ix < 0 or iy < 0 or ix > img_w or iy > img_h:
            if getattr(self, '_debug_click', False):
                print("   -> outside pixmap bounds, ignored")
            return
        # image pixel -> figure pixel (pixmap may be scaled vs native fig size)
        fig = ax.figure
        fig_w_px = fig.get_figwidth() * fig.dpi
        fig_h_px = fig.get_figheight() * fig.dpi
        fx_px = ix * (fig_w_px / img_w)
        fy_px = iy * (fig_h_px / img_h)
        # matplotlib display origin is bottom-left; Qt is top-left -> flip y
        disp_y = fig_h_px - fy_px
        try:
            col, row = ax.transData.inverted().transform((fx_px, disp_y))
        except Exception:
            return
        # (col, row) are data coords of the displayed slice (origin='lower', .T):
        #   axial    col=X(i), row=Y(j)
        #   coronal  col=X(i), row=Z(k)
        #   sagittal col=Y(j), row=Z(k)
        ijk = list(self.crosshair_ijk) if self.crosshair_ijk else [s // 2 for s in shape]
        if view == 'axial':
            ijk[0] = int(round(col)); ijk[1] = int(round(row))
        elif view == 'coronal':
            ijk[0] = int(round(col)); ijk[2] = int(round(row))
        else:                     # sagittal
            ijk[1] = int(round(col)); ijk[2] = int(round(row))
        ijk = [max(0, min(ijk[i], shape[i] - 1)) for i in range(3)]
        if getattr(self, '_debug_click', False):
            print(f"   -> col={col:.1f} row={row:.1f} -> ijk={ijk}")
        self.crosshair_ijk = tuple(ijk)
        # Linked navigation: keep every plane's slice index on the crosshair
        for vw in ('axial', 'coronal', 'sagittal'):
            ax2 = self._axis_for_view(vw)
            self.slice_idx[vw] = ijk[ax2]
        self._update_coord_readout()
        self._queue()

    def _update_coord_readout(self):
        if self.crosshair_ijk is None:
            return
        i, j, k = self.crosshair_ijk
        aff = self.under_affine if self.under_affine is not None else (
            self.overlays[0].affine if self.overlays else None)
        mni_s = "—"
        mni_xyz = None
        if aff is not None:
            x, y, z = vs.voxel_to_mni((i, j, k), aff)
            mni_xyz = (x, y, z)
            mni_s = f"({x:.0f}, {y:.0f}, {z:.0f})"
        # value from active overlay (or first), sampled in its own grid if same shape
        val_s = "—"
        ov = self._active() or (self.overlays[0] if self.overlays else None)
        if ov is not None:
            v = vs.value_at_voxel(ov.data, (i, j, k)) if ov.data.shape == self._ref_shape() else None
            if v is not None:
                val_s = f"{v:.3f}"
        self.coord_lbl.setText(f"Voxel: ({i}, {j}, {k})    MNI: {mni_s}    Value: {val_s}")

        # Cortical/subcortical anatomical label (Harvard-Oxford + Brodmann),
        # plus white-matter tract labelling (JHU-ICBM: maxprob + probabilities).
        if hasattr(self, 'anat_lbl'):
            if mni_xyz is not None and anat is not None:
                try:
                    info = anat.label_at_mni(*mni_xyz)
                    region = info.get('region', '—')
                    ba = info.get('brodmann', '—')
                    ba_txt = f"  ·  {ba}" if ba and ba != '—' else ""
                    text = f"📍 GM: {region}{ba_txt}"

                    # White-matter labelling (JHU-ICBM)
                    if wm is not None:
                        try:
                            winfo = wm.wm_label_at_mni(*mni_xyz)
                            wregion = winfo.get('region', '—')
                            tract = winfo.get('tract', '—')
                            probs = wm.wm_tract_probs_at_mni(*mni_xyz, top=3)
                            parts = []
                            # ICBM-DTI-81 region (this is where corpus callosum,
                            # internal capsule, etc. are named)
                            if wregion and wregion != '—':
                                parts.append(wregion)
                            # probabilistic tracts, else the maxprob tract
                            if probs:
                                parts.append(", ".join(f"{n} ({p:.0f}%)"
                                                       for n, p in probs))
                            elif tract and tract != '—':
                                parts.append(tract)
                            if parts:
                                self._wm_ok = True
                                text += "\n🧵 WM: " + "  ·  ".join(parts)
                            elif not getattr(self, '_wm_ok', False):
                                st = wm.wm_status()
                                if st != 'loaded':
                                    text += f"\n🧵 WM: ({st})"
                        except Exception as we:
                            text += f"\n🧵 WM: (error: {we})"

                    self.anat_lbl.setText(text)
                except Exception as e:
                    self.anat_lbl.setText(f"📍 (lookup error: {e})")
            elif anat is None:
                self.anat_lbl.setText("📍 anatomical labels need nilearn (Harvard-Oxford atlas)")
            else:
                self.anat_lbl.setText("📍 —")

    # ------------------------------------------------------------- clustering
    def _run_clusters(self):
        ov = self._active()
        if ov is None:
            QMessageBox.information(self, "No overlay", "Load and select an overlay first.")
            return
        thr_pos = self.thr_pos.value() if self.chk_pos.isChecked() else None
        thr_neg = self.thr_neg.value() if self.chk_neg.isChecked() else None
        if thr_pos is None and thr_neg is None:
            QMessageBox.information(self, "No threshold",
                                   "Enable at least one threshold (positive or negative).")
            return
        conn = int(self.conn_combo.currentText())
        ext = self.min_extent.value()
        try:
            self.clusters, self.cluster_labels = vs.cluster_analysis(
                ov.data, ov.affine, thr_pos=thr_pos, thr_neg=thr_neg,
                connectivity=conn, min_extent=ext)
            self._refresh_cluster_table()
            self._update_stats_panel()
            self._render_histogram()
            print(f"✅ Found {len(self.clusters)} clusters "
                  f"(thr+={thr_pos}, thr-={thr_neg}, conn={conn}, extent≥{ext})")
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Cluster error", str(e))

    def _refresh_cluster_table(self):
        self.cl_table.setRowCount(0)
        for c in self.clusters:
            r = self.cl_table.rowCount(); self.cl_table.insertRow(r)
            pm = c['peak_mni']
            cells = [str(c['id']), f"{c['n_voxels']:,}", f"{c['volume_mm3']:.0f}",
                     f"{c['peak_value']:+.2f}",
                     f"{pm[0]:.0f}, {pm[1]:.0f}, {pm[2]:.0f}"]
            for col, txt in enumerate(cells):
                it = QTableWidgetItem(txt)
                if col != 4:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.cl_table.setItem(r, col, it)

    def _on_cluster_click(self, idx):
        r = idx.row()
        if 0 <= r < len(self.clusters):
            c = self.clusters[r]
            self.crosshair_ijk = c['peak_voxel']
            # move the slices to the peak so it's visible
            i, j, k = c['peak_voxel']
            self.slice_idx = {'axial': k, 'coronal': j, 'sagittal': i}
            self._sync_slice_slider()
            self._update_coord_readout()
            self._queue()

    def _export_clusters(self):
        if not self.clusters or self.cluster_labels is None:
            QMessageBox.information(self, "No clusters", "Run cluster analysis first.")
            return
        ov = self._active()
        out = QFileDialog.getExistingDirectory(self, "Folder for cluster NIfTIs")
        if not out:
            return
        try:
            saved = vs.export_clusters(out, self.clusters, self.cluster_labels,
                                       ov.affine, data=ov.data, masked_values=True)
            QMessageBox.information(self, "Exported",
                                    f"Saved {len(saved)} cluster file(s) to:\n{out}")
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Export error", str(e))

    # ----------------------------------------------------------------- stats
    def _update_stats_panel(self):
        ov = self._active()
        if ov is None:
            self.stats_lbl.setText("Load a map to see statistics.")
            return
        thr_pos = self.thr_pos.value() if self.chk_pos.isChecked() else None
        thr_neg = self.thr_neg.value() if self.chk_neg.isChecked() else None
        whole = vs.intensity_stats(ov.data)
        lines = [f"<b style='color:#7dd3fc'>{ov.name}</b>",
                 f"shape: {ov.data.shape}",
                 "",
                 "<b>Whole image (non-zero)</b>",
                 f"  N voxels : {whole['n']:,}",
                 f"  min/max  : {whole['min']:.3f} / {whole['max']:.3f}",
                 f"  mean±sd  : {whole['mean']:.3f} ± {whole['std']:.3f}",
                 f"  median   : {whole['median']:.3f}",
                 f"  +/- count: {whole['n_pos']:,} / {whole['n_neg']:,}"]
        if thr_pos is not None or thr_neg is not None:
            m = vs.threshold_mask(ov.data, thr_pos, thr_neg)
            sup = vs.intensity_stats(ov.data, mask=m)
            vol = sup['n'] * vs.voxel_volume_mm3(ov.affine)
            lines += ["",
                      "<b>Supra-threshold</b>",
                      f"  thr +≥{thr_pos}  −≤{thr_neg}",
                      f"  N voxels : {sup['n']:,}  ({vol:.0f} mm³)",
                      f"  mean±sd  : {sup['mean']:.3f} ± {sup['std']:.3f}"]
        if self.clusters:
            lines += ["", f"<b>Clusters:</b> {len(self.clusters)} "
                          f"(largest {self.clusters[0]['n_voxels']:,} vox)"]
        self.stats_lbl.setText("<br>".join(lines).replace("None", "off"))

    def _render_histogram(self):
        ov = self._active()
        if ov is None:
            return
        col = tm.figure_colors() if tm is not None else {
            'fig': '#0c1424', 'ax': '#0c1424', 'text': '#7090b8',
            'spine': '#2a3a5a', 'accent': '#38b6ff'}
        counts, edges = vs.histogram(ov.data, bins=60)
        centers = (edges[:-1] + edges[1:]) / 2
        fig, ax = plt.subplots(figsize=(4.2, 2.4), dpi=90, facecolor=col['fig'])
        ax.set_facecolor(col['ax'])
        ax.bar(centers, counts, width=(edges[1]-edges[0]), color=col['accent'], alpha=0.85)
        for spine in ax.spines.values(): spine.set_color(col['spine'])
        ax.tick_params(colors=col['text'], labelsize=7)
        ax.set_xlabel('intensity', color=col['text'], fontsize=8)
        ax.set_ylabel('count', color=col['text'], fontsize=8)
        # threshold guides
        if self.chk_pos.isChecked():
            ax.axvline(self.thr_pos.value(), color='#4ade80', lw=1, ls='--')
        if self.chk_neg.isChecked():
            ax.axvline(self.thr_neg.value(), color='#f87171', lw=1, ls='--')
        fig.tight_layout()
        self._fig_to_label(fig, self.hist_canvas)
        plt.close(fig)

    # --------------------------------------------------------------- rendering
    def resizeEvent(self, event):
        """Re-render slices to fill the new canvas size when the window or
        splitter is resized (debounced via the render timer)."""
        super().resizeEvent(event)
        if self._ref_shape() is not None:
            self._queue()

    def showEvent(self, event):
        """First paint once the real widget size is known."""
        super().showEvent(event)
        if self._ref_shape() is not None:
            self._queue()

    def _queue(self):
        self._render_timer.stop(); self._render_timer.start(40)

    def _slice_2d(self, vol, view, idx):
        if view == 'axial':
            return vol[:, :, min(idx, vol.shape[2]-1)].T
        if view == 'coronal':
            return vol[:, min(idx, vol.shape[1]-1), :].T
        return vol[min(idx, vol.shape[0]-1), :, :].T

    def _render(self):
        shape = self._ref_shape()
        if shape is None:
            return
        if getattr(self, 'glass_mode', False):
            self._render_glass()
            self._update_coord_readout()
            return
        if self.triplanar:
            for view, canvas in (('axial', self.canvas_axial),
                                 ('coronal', self.canvas_coronal),
                                 ('sagittal', self.canvas_sagittal)):
                self._render_one(view, self.slice_idx[view], canvas, small=True)
        else:
            self._render_one(self.view, self.slice_idx[self.view],
                             self.canvas_single, small=False)
        self._update_coord_readout()

    def _open_3d_surface(self):
        """Open an interactive, rotatable 3D surface rendering of the active
        overlay (or underlay) in the system browser. Uses nilearn's surface
        viewer, which produces self-contained interactive HTML — no VTK, so
        there's no native crash risk."""
        try:
            from nilearn import plotting as niplot
            import nibabel as nib
        except Exception as e:
            QMessageBox.information(self, "3D Surface needs nilearn",
                                    "The interactive 3D surface view requires nilearn.\n\n"
                                    "pip install nilearn")
            print(f"⚠️ 3D surface unavailable: {e}")
            return

        ov = self._active() or (self.overlays[0] if self.overlays else None)
        if ov is not None:
            img = nib.Nifti1Image(np.asarray(ov.data, dtype=np.float32), ov.affine)
            cmap = getattr(ov, 'cmap', 'hot')
            title = ov.name
            # use the positive threshold if set
            thr = self.thr_pos.value() if self.chk_pos.isChecked() and self.thr_pos.value() > 0 else None
        elif self.under_data is not None:
            img = nib.Nifti1Image(np.asarray(self.under_data, dtype=np.float32),
                                  self.under_affine)
            cmap = self.under_cmap; title = "Underlay"; thr = None
        else:
            QMessageBox.information(self, "No image",
                                    "Load an overlay or underlay first.")
            return

        try:
            import tempfile, webbrowser, os
            view = niplot.view_img_on_surf(img, surf_mesh='fsaverage5',
                                           cmap=cmap, threshold=thr,
                                           title=title)
            out = os.path.join(tempfile.gettempdir(), "mbct_3d_surface.html")
            view.save_as_html(out)
            webbrowser.open('file://' + os.path.realpath(out))
            print(f"✅ 3D surface opened in browser: {out}")
        except Exception as e:
            QMessageBox.warning(self, "3D Surface error",
                                f"Could not build the 3D surface view:\n{e}")
            print(f"⚠️ 3D surface error: {e}")
            import traceback; traceback.print_exc()

    def _render_glass(self):
        """Render a BrainNet-style glass-brain projection of the active overlay
        (falls back to the underlay) using nilearn. Result is shown as a pixmap
        in the single canvas."""
        canvas = self.canvas_single
        try:
            from nilearn import plotting as niplot
            import nibabel as nib
        except Exception as e:
            canvas.setText("Glass brain needs nilearn.\n\npip install nilearn")
            print(f"⚠️ Glass brain unavailable: {e}")
            return

        # Choose what to display: active overlay > first overlay > underlay
        ov = self._active() or (self.overlays[0] if self.overlays else None)
        if ov is not None:
            img = nib.Nifti1Image(np.asarray(ov.data, dtype=np.float32), ov.affine)
            cmap = getattr(ov, 'cmap', 'hot')
            has_stat = True
        elif self.under_data is not None:
            img = nib.Nifti1Image(np.asarray(self.under_data, dtype=np.float32),
                                  self.under_affine)
            cmap = self.under_cmap
            has_stat = True
        else:
            canvas.setText("Load an overlay or underlay to view the glass brain.")
            return

        try:
            fig = plt.figure(figsize=(7, 3), facecolor='black')
            display = niplot.plot_glass_brain(
                img, figure=fig, display_mode='lyrz',
                colorbar=True, cmap=cmap, black_bg=True,
                plot_abs=False, alpha=0.85)
            # mark the current crosshair location if available
            if self.crosshair_ijk is not None:
                aff = self.under_affine if self.under_affine is not None else ov.affine
                x, y, z = vs.voxel_to_mni(self.crosshair_ijk, aff)
                try:
                    display.add_markers([(x, y, z)], marker_color='lime',
                                        marker_size=40)
                except Exception:
                    pass
            fig.canvas.draw()   # ensure each panel's transData is valid
            # Close the PREVIOUS glass fig (avoid leak), keep THIS one alive so
            # its panel transforms remain valid for click mapping.
            prev = getattr(self, '_glass_fig', None)
            if prev is not None and prev is not fig:
                try:
                    plt.close(prev)
                except Exception:
                    pass
            self._glass_display = display
            self._glass_fig = fig
            buf = BytesIO()
            # NO bbox_inches='tight' — cropping would break click mapping.
            fig.savefig(buf, format='png', dpi=fig.dpi, facecolor='black',
                        pad_inches=0)
            buf.seek(0)
            image = QImage(); image.loadFromData(buf.getvalue())
            pm = QPixmap.fromImage(image)
            cw = max(1, canvas.width()); ch = max(1, canvas.height())
            scaled = pm.scaled(cw, ch, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            # Record the displayed pixmap geometry for click mapping.
            self._glass_pm_w = scaled.width()
            self._glass_pm_h = scaled.height()
            self._glass_native_w = pm.width()
            self._glass_native_h = pm.height()
            canvas.setPixmap(scaled)
        except Exception as e:
            canvas.setText(f"Glass brain render error:\n{e}")
            print(f"⚠️ Glass brain render error: {e}")
            import traceback; traceback.print_exc()

    def _handle_glass_click(self, label, event):
        """Map a click on the glass brain to an MNI coordinate. The glass brain
        shows projections (l/r=sagittal, y=coronal, z=axial); each nilearn panel
        is in MNI mm. We find which panel was clicked and invert that panel's
        transform. A projection gives 2 of 3 MNI coords; the third is kept from
        the current crosshair (a projection can't resolve depth)."""
        display = getattr(self, '_glass_display', None)
        fig = getattr(self, '_glass_fig', None)
        if display is None or fig is None:
            return
        aff = self.under_affine if self.under_affine is not None else (
            self.overlays[0].affine if self.overlays else None)
        shape = self._ref_shape()
        if aff is None or shape is None:
            return
        pix = label.pixmap()
        if pix is None or pix.isNull():
            return
        # label pixel -> displayed-pixmap pixel (centered in label)
        pm_w = getattr(self, '_glass_pm_w', pix.width())
        pm_h = getattr(self, '_glass_pm_h', pix.height())
        lw, lh = label.width(), label.height()
        ix = event.pos().x() - max(0, (lw - pm_w) / 2.0)
        iy = event.pos().y() - max(0, (lh - pm_h) / 2.0)
        if ix < 0 or iy < 0 or ix > pm_w or iy > pm_h:
            return
        # displayed pixmap -> native figure pixels
        nat_w = getattr(self, '_glass_native_w', pm_w)
        nat_h = getattr(self, '_glass_native_h', pm_h)
        fx_px = ix * (nat_w / pm_w)
        fy_px = iy * (nat_h / pm_h)
        # figure pixel (top-left origin) -> matplotlib display (bottom-left)
        fig_h_px = fig.get_figheight() * fig.dpi
        disp_x = fx_px
        disp_y = fig_h_px - fy_px

        # Current crosshair in MNI (depth fallback for the collapsed axis)
        cx, cy, cz = vs.voxel_to_mni(self.crosshair_ijk, aff) if self.crosshair_ijk \
            else (0.0, 0.0, 0.0)
        new_mni = [cx, cy, cz]

        # Find the panel whose axes bbox (in display pixels) contains the click.
        hit = None
        for key, slicer in display.axes.items():
            ax = slicer.ax
            bbox = ax.get_window_extent()   # display pixels
            if bbox.x0 <= disp_x <= bbox.x1 and bbox.y0 <= disp_y <= bbox.y1:
                hit = (key, slicer, ax); break
        if hit is None:
            if getattr(self, '_debug_click', False):
                print(f"[glass] click outside panels disp=({disp_x:.0f},{disp_y:.0f})")
            return
        key, slicer, ax = hit
        xdata, ydata = ax.transData.inverted().transform((disp_x, disp_y))
        direction = slicer.direction   # 'l','r','y','z'
        # Panel data axes (verified): l/r -> (x=MNI Y, y=MNI Z);
        #   y(coronal) -> (x=MNI X, y=MNI Z);  z(axial) -> (x=MNI X, y=MNI Y)
        if direction in ('l', 'r'):
            new_mni[1] = xdata; new_mni[2] = ydata    # set Y, Z (X kept)
        elif direction == 'y':
            new_mni[0] = xdata; new_mni[2] = ydata    # set X, Z (Y kept)
        else:  # 'z' axial
            new_mni[0] = xdata; new_mni[1] = ydata    # set X, Y (Z kept)

        # MNI -> voxel
        inv = np.linalg.inv(aff)
        v = inv @ np.array([new_mni[0], new_mni[1], new_mni[2], 1.0])
        ijk = [int(round(v[0])), int(round(v[1])), int(round(v[2]))]
        ijk = [max(0, min(ijk[a], shape[a] - 1)) for a in range(3)]
        if getattr(self, '_debug_click', False):
            print(f"[glass] panel={direction} data=({xdata:.0f},{ydata:.0f}) "
                  f"-> MNI=({new_mni[0]:.0f},{new_mni[1]:.0f},{new_mni[2]:.0f}) ijk={ijk}")
        self.crosshair_ijk = tuple(ijk)
        for vw in ('axial', 'coronal', 'sagittal'):
            self.slice_idx[vw] = ijk[self._axis_for_view(vw)]
        self._update_coord_readout()
        self._queue()

    def _render_one(self, view, idx, canvas, small):
        shape = self._ref_shape()
        # figure aspect matches the SLICE data aspect (cols x rows) so the axes
        # fill the figure with no letterboxing -> click mapping stays exact and
        # anatomy is undistorted. Pixel size scales with the canvas.
        if view == 'axial':
            cols, rows = shape[0], shape[1]       # X, Y
        elif view == 'coronal':
            cols, rows = shape[0], shape[2]       # X, Z
        else:
            cols, rows = shape[1], shape[2]       # Y, Z
        long_px = max(canvas.width(), canvas.height(), 200)
        dpi = 90
        scale = long_px / dpi / max(cols, rows)
        figsize = (cols * scale, rows * scale)
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi, facecolor='#000000')
        ax.set_facecolor('#000000')

        # underlay
        if self.under_data is not None and self.under_data.shape == shape:
            u = self._slice_2d(self.under_data, view, idx)
            uw = np.clip((u - self.under_vmin) / (self.under_vmax - self.under_vmin + 1e-6), 0, 1)
            ax.imshow(uw, cmap=self.under_cmap, origin='lower', interpolation='bilinear', aspect='auto')

        # overlays (rendered from display-grid data so they always align)
        for ov in self.overlays:
            if not ov.visible:
                continue
            od = ov.disp_data
            if od.shape != shape:
                continue
            s = self._slice_2d(od, view, idx)
            disp = s.copy()
            # apply thresholds to what is shown
            tp = self.thr_pos.value() if self.chk_pos.isChecked() else None
            tn = self.thr_neg.value() if self.chk_neg.isChecked() else None
            keep = np.zeros(disp.shape, dtype=bool)
            if tp is None and tn is None:
                keep = disp != 0
            else:
                if tp is not None: keep |= disp >= tp
                if tn is not None: keep |= disp <= tn
            masked = np.ma.masked_where(~keep, disp)
            ax.imshow(masked, cmap=ov.cmap, alpha=ov.alpha, origin='lower',
                      interpolation='nearest', aspect='auto',
                      vmin=ov.vmin, vmax=ov.vmax)

        # crosshair
        if self.crosshair_ijk is not None:
            self._draw_crosshair(ax, view, shape)

        if self.zoom != 1.0:
            h, w = (shape[1], shape[0]) if view == 'axial' else \
                   (shape[2], shape[0]) if view == 'coronal' else (shape[2], shape[1])
            cx, cy = w / 2, h / 2
            ax.set_xlim(cx - w/self.zoom/2, cx + w/self.zoom/2)
            ax.set_ylim(cy - h/self.zoom/2, cy + h/self.zoom/2)

        ax.set_xticks([]); ax.set_yticks([])
        ax.set_axis_off()
        # axes fill the whole figure so screen pixels map 1:1 to data extent
        ax.set_position([0, 0, 1, 1])
        if small:
            ax.text(0.5, 0.97, view.capitalize(), transform=ax.transAxes,
                    ha='center', va='top', color='#6e8cb8', fontsize=8)
        # Store the data extent AND the live axes for exact click->data mapping.
        # We must draw the figure (so transData is valid) and must NOT close it,
        # or transData becomes unusable. Keep one figure per view alive.
        if not hasattr(self, '_view_extent'):
            self._view_extent = {}
        if not hasattr(self, '_view_ax'):
            self._view_ax = {}
        self._view_extent[view] = (ax.get_xlim(), ax.get_ylim())
        self._view_ax[view] = ax
        self._fig_to_label(fig, canvas)
        # NOTE: do not plt.close(fig) — keep it alive so transData stays valid.
        # Close any *previous* figure for this view to avoid leaks.
        prev = getattr(self, '_view_fig', {}).get(view)
        if prev is not None and prev is not fig:
            try:
                plt.close(prev)
            except Exception:
                pass
        if not hasattr(self, '_view_fig'):
            self._view_fig = {}
        self._view_fig[view] = fig

    def _draw_crosshair(self, ax, view, shape):
        i, j, k = self.crosshair_ijk
        # Plain .T with origin='lower':
        #   axial    -> col = X(i), row = Y(j)
        #   coronal  -> col = X(i), row = Z(k)
        #   sagittal -> col = Y(j), row = Z(k)
        if view == 'axial':
            col = i; row = j
        elif view == 'coronal':
            col = i; row = k
        else:
            col = j; row = k
        ax.axvline(col, color='#39ff14', lw=0.8, alpha=0.8)
        ax.axhline(row, color='#39ff14', lw=0.8, alpha=0.8)

    def _fig_to_label(self, fig, label):
        buf = BytesIO()
        # Save at the figure's own dpi so the pixmap's pixel size is exactly
        # figwidth*dpi x figheight*dpi — required for accurate click mapping.
        fig.savefig(buf, format='png', dpi=fig.dpi, pad_inches=0,
                    facecolor=fig.get_facecolor())
        buf.seek(0)
        img = QImage(); img.loadFromData(buf.getvalue())
        pm = QPixmap.fromImage(img)
        # Scale to fit the label so the DISPLAYED pixmap size equals pm.width()/
        # height() (what _handle_click reads). Keeps aspect; centered by Align.
        lw, lh = max(1, label.width()), max(1, label.height())
        if pm.width() > lw or pm.height() > lh:
            pm = pm.scaled(lw, lh, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(pm)

    # ----------------------------------------------------------------- style
    # The brain display (#brainCanvas / #viewerArea / #canvasHolder) stays
    # true black in BOTH themes — that's the imaging convention. Only the
    # surrounding panels switch between light (win11) and dark (navy).
    _DARK_STYLE = """
            QWidget { color:#cdd9e8; }
            #leftRail, #rightPanel { background:#0a0f1c; }
            #viewerArea, #canvasHolder { background:#000000; }
            #railTitle { color:#e8f0fa; letter-spacing:2px; }
            #railSub { color:#5a6c86; font-size:9pt; }
            #sectionHead { color:#4f7bbf; letter-spacing:1px; }
            #rule { background:#16223a; }
            #coordReadout { color:#7dd3fc; }
            #brainCanvas { background:#000000; border:1px solid #16223a; border-radius:4px; }
            #histCanvas { background:#0c1424; border:1px solid #16223a; border-radius:4px; }
            QPushButton { background:#12203a; color:#cdd9e8; border:1px solid #1d3358;
                padding:6px 10px; border-radius:5px; }
            QPushButton:hover { background:#1a2c4d; }
            QPushButton:checked { background:#1d4ed8; border-color:#3b82f6; color:white; }
            #primaryBtn { background:#155e9c; border-color:#1f7ec4; color:#eaf4ff; font-weight:bold; }
            #primaryBtn:hover { background:#1976c4; }
            #viewBtn { padding:5px 8px; }
            QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QListWidget, QTableWidget {
                background:#0c1424; color:#cdd9e8; border:1px solid #1d3358; border-radius:4px; padding:3px; }
            QHeaderView::section { background:#12203a; color:#9fb8d8; border:none; padding:4px; }
            QTableWidget { gridline-color:#16223a; }
            QTableWidget::item:selected { background:#1d4ed8; color:white; }
            QSlider::groove:horizontal { background:#16223a; height:5px; border-radius:2px; }
            QSlider::handle:horizontal { background:#38b6ff; width:13px; margin:-5px 0; border-radius:6px; }
            QTabWidget::pane { border:1px solid #16223a; }
            QTabBar::tab { background:#0c1424; color:#7e98bd; padding:5px 12px; }
            QTabBar::tab:selected { background:#12203a; color:#cde4ff; }
            QCheckBox { color:#9fb8d8; }
            #statsText { padding:6px; }
    """
    _LIGHT_STYLE = """
            QWidget { color:#1a1a1a; }
            #leftRail, #rightPanel { background:#fbfbfb; }
            #viewerArea, #canvasHolder { background:#000000; }
            #railTitle { color:#0a3f7a; letter-spacing:2px; }
            #railSub { color:#888888; font-size:9pt; }
            #sectionHead { color:#0a84ff; letter-spacing:1px; }
            #rule { background:#e2e2e2; }
            #coordReadout { color:#0a3f7a; }
            #brainCanvas { background:#000000; border:0.5px solid rgba(0,0,0,0.12); border-radius:4px; }
            #histCanvas { background:#ffffff; border:0.5px solid rgba(0,0,0,0.12); border-radius:4px; }
            QPushButton { background:#ffffff; color:#1a1a1a; border:0.5px solid rgba(0,0,0,0.18);
                padding:6px 10px; border-radius:5px; }
            QPushButton:hover { background:#f0f0f0; }
            QPushButton:checked { background:#0a84ff; border-color:#0a84ff; color:white; }
            #primaryBtn { background:#0a84ff; border-color:#0a84ff; color:#ffffff; font-weight:500; }
            #primaryBtn:hover { background:#1a90ff; }
            #viewBtn { padding:5px 8px; }
            QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QListWidget, QTableWidget {
                background:#ffffff; color:#1a1a1a; border:0.5px solid rgba(0,0,0,0.18); border-radius:4px; padding:3px; }
            QHeaderView::section { background:#f6f6f6; color:#333333; border:none; padding:4px; }
            QTableWidget { gridline-color:#ececec; }
            QTableWidget::item:selected { background:#cfe4fb; color:#0a3f7a; }
            QSlider::groove:horizontal { background:#dcdcdc; height:5px; border-radius:2px; }
            QSlider::handle:horizontal { background:#0a84ff; width:13px; margin:-5px 0; border-radius:6px; }
            QTabWidget::pane { border:0.5px solid rgba(0,0,0,0.10); }
            QTabBar::tab { background:#f0f0f0; color:#555555; padding:5px 12px; }
            QTabBar::tab:selected { background:#ffffff; color:#0a3f7a; }
            QCheckBox { color:#444444; }
            #statsText { padding:6px; }
    """

    def _apply_style(self):
        theme = getattr(tm, 'CURRENT', 'win11')
        self.setStyleSheet(self._LIGHT_STYLE if theme == 'win11' else self._DARK_STYLE)

    def apply_external_theme(self, name):
        """Called by the main window when the user toggles the app theme."""
        self.setStyleSheet(self._LIGHT_STYLE if name == 'win11' else self._DARK_STYLE)
        self._queue()  # re-render histogram/slices with theme-aware colors
