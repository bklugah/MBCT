"""
utilities_tab.py
================
A single "Utilities" tab hosting several self-contained neuroimaging tools,
selected from a left-hand list. Each tool follows the same flow:
    load input(s) -> configure -> run -> save (+ optional "Open in Viewer").

Tools
-----
1. Converter            : resample a NIfTI onto a standard space's real grid
2. Threshold & Binarize : value/cluster threshold -> thresholded map or mask
3. ROI Tool             : build (sphere / atlas label) AND extract signal
4. Combine Maps         : arithmetic (add/sub/mean/mul) + logical (conj/contrast/union)
5. Term -> Map          : Neurosynth meta-analytic map for a term (NiMARE)
6. Coordinate -> Terms  : Neurosynth functional term profile at an MNI point (NiMARE)

Outputs are saved to a user-chosen file; an optional "Open in Viewer" button
emits `file_ready(path)` which the main window connects to the Brain Viewer.

Grid mismatches (Combine / ROI extract) are auto-resampled to a reference grid
with a visible note in the tool's status line.
"""

from pathlib import Path
import traceback

import numpy as np
import nibabel as nib

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QListWidget, QListWidgetItem, QStackedWidget,
    QFileDialog, QMessageBox, QTextEdit, QDoubleSpinBox, QSpinBox, QFrame,
    QCheckBox, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QPointF, QRectF
from PyQt6.QtGui import (QFont, QPainter, QColor, QPen, QBrush, QPixmap,
                         QImage, QLinearGradient, QRadialGradient)

try:
    import anatomy_lookup as anat
except Exception:
    anat = None


# User-chosen Neurosynth corpus directory (set via the data panel / settings).
# None means "auto-resolve" (project corpus folder, then home cache).
_USER_CORPUS_DIR = None


def set_neurosynth_dir(path):
    """Set the Neurosynth corpus directory used by the meta-analysis tools."""
    global _USER_CORPUS_DIR
    _USER_CORPUS_DIR = path or None


# Non-cognitive / methodological / anatomical vocabulary to hide from the
# decoded term profile (matches the curated stop-list described in the
# manuscript). Matching is done on whole words within the cleaned term.
_NOISE_TERMS = {
    # method / acquisition / analysis
    'fmri', 'mri', 'pet', 'eeg', 'meg', 'bold', 'voxel', 'voxels', 'cluster',
    'clusters', 'coordinate', 'coordinates', 'roi', 'rois', 'correlation',
    'correlations', 'correlated', 'analysis', 'analyses', 'signal', 'signals',
    'task', 'tasks', 'trial', 'trials', 'block', 'design', 'contrast',
    'contrasts', 'condition', 'conditions', 'response', 'responses', 'measure',
    'measures', 'measured', 'measurement', 'data', 'dataset', 'group', 'groups',
    'subject', 'subjects', 'participant', 'participants', 'session', 'sessions',
    'scan', 'scans', 'scanning', 'imaging', 'image', 'images', 'map', 'maps',
    'activation', 'activations', 'activity', 'deactivation', 'functional',
    'connectivity', 'network', 'networks', 'resting', 'rest', 'state',
    'seed', 'spatial', 'temporal', 'baseline', 'effect', 'effects', 'model',
    'models', 'regression', 'parameter', 'parameters', 'threshold', 'whole brain',
    'gray matter', 'white matter', 'matter', 'cortex', 'cortical', 'subcortical',
    'region', 'regions', 'regional', 'area', 'areas', 'areal', 'volume', 'volumes',
    'hemisphere', 'hemispheres', 'bilateral', 'unilateral', 'left', 'right',
    'anterior', 'posterior', 'dorsal', 'ventral', 'medial', 'lateral', 'inferior',
    'superior', 'gyrus', 'gyri', 'sulcus', 'sulci', 'lobe', 'lobes', 'lobule',
    # generic / filler
    'increased', 'decreased', 'increase', 'decrease', 'higher', 'lower', 'greater',
    'reduced', 'enhanced', 'differences', 'difference', 'related', 'associated',
    'association', 'role', 'processing', 'process', 'processes', 'function',
    'functions', 'performance', 'control', 'controls', 'healthy', 'patients',
    'patient', 'clinical', 'studies', 'study', 'results', 'findings', 'evidence',
    'suggest', 'observed', 'significant', 'significantly', 'comparison',
    'compared', 'using', 'use', 'used', 'present', 'specific', 'general',
}


def _is_noise(term):
    """True if a (cleaned) Neurosynth term is non-cognitive / methodological."""
    t = term.strip().lower()
    if not t:
        return True
    if t in _NOISE_TERMS:
        return True
    # multiword terms: noise if every word is itself noise
    words = t.split()
    if len(words) > 1 and all(w in _NOISE_TERMS for w in words):
        return True
    return False


# Standard spaces this app supports: (display, shape, voxel-size mm)
STANDARD_SPACES = {
    'FSLMNI2mm': ((91, 109, 91), 2.0),
    'FSLMNI1mm': ((182, 218, 182), 1.0),
    'FSLMNI4mm': ((46, 55, 46), 4.0),
}


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------
def _load_nifti(path):
    """Load a NIfTI, returning (data, affine, header). 4D -> first volume."""
    img = nib.load(str(path))
    data = img.get_fdata()
    if data.ndim > 3:
        data = data[..., 0]
    return np.asarray(data, dtype=np.float32), img.affine, img.header


def _save_nifti(data, affine, path, header=None):
    img = nib.Nifti1Image(np.asarray(data), affine, header)
    nib.save(img, str(path))


def _looks_like_labels(data):
    """Heuristic: integer-valued, few unique values -> a label/mask image."""
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return False
    if not np.allclose(finite, np.round(finite)):
        return False
    return np.unique(finite).size <= 1000


def _resample_to(data, affine, ref_affine, ref_shape, labels=False):
    """Resample (data, affine) onto a reference grid (ref_affine, ref_shape).
    Nearest-neighbour for label/mask data, linear otherwise. Uses nilearn."""
    from nilearn.image import resample_img
    src = nib.Nifti1Image(np.asarray(data, dtype=np.float32), affine)
    interp = 'nearest' if labels else 'continuous'
    out = resample_img(src, target_affine=ref_affine,
                       target_shape=tuple(int(s) for s in ref_shape),
                       interpolation=interp)
    return np.asarray(out.get_fdata(), dtype=np.float32), out.affine


def _is_dark():
    try:
        import theme_manager as _tm
        return _tm.CURRENT == 'dark'
    except Exception:
        return True


def _colors():
    """The Utilities panels sit on a fixed DARK stacked-widget background in
    BOTH themes, so text is white/light regardless of the app theme (dark text
    would be invisible on the dark panel). Accent hues are used only for
    headings/section labels."""
    return {
        'accent': '#60a5fa',      # section labels
        'heading': '#7dd3fc',     # panel titles
        'body': '#e6e9ef',        # blurbs / secondary text  -> near-white
        'status_fg': '#ffffff',   # status text -> white
        'status_bg': '#141520',
        'status_border': '#2a3a5a',
        'sel_bg': '#2f5a94',
    }


def _section(text):
    l = QLabel(text)
    l.setObjectName("section")
    l.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
    l.setStyleSheet(f"color:{_colors()['accent']};")
    return l


# ---------------------------------------------------------------------------
# Base panel: gives each tool a consistent input row, status line, and a
# Save / Open-in-Viewer button pair.
# ---------------------------------------------------------------------------
class _ToolPanel(QWidget):
    def __init__(self, owner, title, blurb):
        super().__init__()
        self.owner = owner          # the UtilitiesTab (for file_ready signal)
        self._result = None         # (data, affine, header) pending save
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(16, 14, 16, 14)
        self.root.setSpacing(10)
        h = QLabel(title); h.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        h.setStyleSheet(f"color:{_colors()['heading']};")
        self.root.addWidget(h)
        if blurb:
            b = QLabel(blurb); b.setWordWrap(True)
            b.setStyleSheet(f"color:{_colors()['body']};")
            self.root.addWidget(b)

    def _status_line(self):
        c = _colors()
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"background:{c['status_bg']}; border:1px solid {c['status_border']}; "
            f"border-radius:6px; padding:6px 8px; color:{c['status_fg']};")
        self.root.addWidget(self.status)

    def _save_row(self):
        row = QHBoxLayout()
        self.btn_save = QPushButton("💾  Save result…")
        self.btn_save.clicked.connect(self._on_save)
        self.btn_save.setEnabled(False)
        row.addWidget(self.btn_save)
        self.btn_view = QPushButton("🧠  Open in Viewer")
        self.btn_view.clicked.connect(self._on_open_in_viewer)
        self.btn_view.setEnabled(False)
        row.addWidget(self.btn_view)
        row.addStretch()
        self.root.addLayout(row)

    def _set_result(self, data, affine, header=None, note=""):
        self._result = (data, affine, header)
        self.btn_save.setEnabled(True)
        self.btn_view.setEnabled(True)
        if note and hasattr(self, 'status'):
            self.status.setText(note)

    def _pick_open(self, caption="Open NIfTI"):
        path, _ = QFileDialog.getOpenFileName(
            self, caption, "", "NIfTI (*.nii *.nii.gz);;All files (*)")
        return path

    def _on_save(self):
        if self._result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save NIfTI", "", "NIfTI (*.nii.gz);;NIfTI (*.nii)")
        if not path:
            return
        if not (path.endswith('.nii') or path.endswith('.nii.gz')):
            path += '.nii.gz'
        try:
            data, affine, header = self._result
            _save_nifti(data, affine, path, header)
            self._last_saved = path
            if hasattr(self, 'status'):
                self.status.setText(f"Saved: {path}")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Save error", str(e))

    def _on_open_in_viewer(self):
        """Save to a temp file if needed, then hand the path to the viewer."""
        try:
            import tempfile, os
            path = getattr(self, '_last_saved', None)
            if path is None or not os.path.exists(path):
                if self._result is None:
                    return
                data, affine, header = self._result
                path = os.path.join(tempfile.gettempdir(),
                                    f"mbct_util_{id(self)}.nii.gz")
                _save_nifti(data, affine, path, header)
            self.owner.file_ready.emit(path)
            if hasattr(self, 'status'):
                self.status.setText(f"Sent to Brain Viewer: {path}")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Open in Viewer error", str(e))


# ---------------------------------------------------------------------------
# 1. Converter — resample onto a standard space's real reference grid
# ---------------------------------------------------------------------------
class ConverterPanel(_ToolPanel):
    def __init__(self, owner):
        super().__init__(owner, "Space Converter",
            "Resample a NIfTI onto a standard MNI space's real grid (correct "
            "affine + shape). Labels/masks use nearest-neighbour automatically.")
        self._in = None  # (data, affine, header)

        grid = QGridLayout()
        grid.addWidget(QLabel("Input file:"), 0, 0)
        self.in_lbl = QLineEdit(); self.in_lbl.setReadOnly(True)
        grid.addWidget(self.in_lbl, 0, 1)
        b = QPushButton("Browse…"); b.clicked.connect(self._browse)
        grid.addWidget(b, 0, 2)

        grid.addWidget(QLabel("Target space:"), 1, 0)
        self.space_combo = QComboBox()
        for k, (shape, vox) in STANDARD_SPACES.items():
            self.space_combo.addItem(f"{k}  {shape}", k)
        grid.addWidget(self.space_combo, 1, 1, 1, 2)

        grid.addWidget(QLabel("Interpolation:"), 2, 0)
        self.interp_combo = QComboBox()
        self.interp_combo.addItems(["auto (detect labels)", "linear", "nearest"])
        grid.addWidget(self.interp_combo, 2, 1, 1, 2)
        self.root.addLayout(grid)

        run = QPushButton("🔄  Convert"); run.clicked.connect(self._run)
        self.root.addWidget(run)
        self._status_line()
        self._save_row()

    def _browse(self):
        p = self._pick_open("Select NIfTI to convert")
        if not p:
            return
        self.in_lbl.setText(p)
        try:
            self._in = _load_nifti(p)
            d, aff, _ = self._in
            self.status.setText(f"Loaded {Path(p).name}  shape={d.shape}")
        except Exception as e:
            self.status.setText(f"Load error: {e}")
            self._in = None

    def _run(self):
        if self._in is None:
            QMessageBox.information(self, "No input", "Choose an input file.")
            return
        data, affine, header = self._in
        space = self.space_combo.currentData()
        shape, vox = STANDARD_SPACES[space]
        # Build the standard space's real affine: diagonal voxel size,
        # origin centered so the FOV matches the standard template extent.
        ref_affine = np.eye(4)
        ref_affine[0, 0] = -vox      # radiological L-R like FSL MNI
        ref_affine[1, 1] = vox
        ref_affine[2, 2] = vox
        # center the volume on MNI origin
        ref_affine[0, 3] = vox * (shape[0] // 2)
        ref_affine[1, 3] = -vox * (shape[1] // 2)
        ref_affine[2, 3] = -vox * (shape[2] // 2)

        sel = self.interp_combo.currentText()
        if sel.startswith("auto"):
            labels = _looks_like_labels(data)
        else:
            labels = (sel == "nearest")
        try:
            out, out_aff = _resample_to(data, affine, ref_affine, shape, labels=labels)
            kind = "nearest (labels/mask)" if labels else "linear"
            self._set_result(out, out_aff, header,
                note=f"Converted {data.shape} → {tuple(shape)} in {space} "
                     f"using {kind} interpolation.")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Convert error", str(e))


# ---------------------------------------------------------------------------
# 2. Threshold & Binarize
# ---------------------------------------------------------------------------
class ThresholdPanel(_ToolPanel):
    def __init__(self, owner):
        super().__init__(owner, "Threshold & Binarize",
            "Apply a value threshold and/or a minimum cluster-extent threshold. "
            "Output either the thresholded values or a binary mask.")
        self._in = None

        grid = QGridLayout()
        grid.addWidget(QLabel("Input map:"), 0, 0)
        self.in_lbl = QLineEdit(); self.in_lbl.setReadOnly(True)
        grid.addWidget(self.in_lbl, 0, 1)
        b = QPushButton("Browse…"); b.clicked.connect(self._browse)
        grid.addWidget(b, 0, 2)

        grid.addWidget(QLabel("Keep values >"), 1, 0)
        self.thr_min = QDoubleSpinBox(); self.thr_min.setRange(-1e6, 1e6)
        self.thr_min.setDecimals(3); self.thr_min.setValue(0.0)
        grid.addWidget(self.thr_min, 1, 1)
        self.use_abs = QCheckBox("use |value| (two-sided)")
        grid.addWidget(self.use_abs, 1, 2)

        grid.addWidget(QLabel("Min cluster size (vox):"), 2, 0)
        self.min_ext = QSpinBox(); self.min_ext.setRange(0, 100000); self.min_ext.setValue(0)
        grid.addWidget(self.min_ext, 2, 1)
        grid.addWidget(QLabel("Connectivity:"), 2, 2)
        self.conn = QComboBox(); self.conn.addItems(["6", "18", "26"]); self.conn.setCurrentText("18")
        grid.addWidget(self.conn, 3, 2)

        self.binarize = QCheckBox("Output binary mask (else keep values)")
        grid.addWidget(self.binarize, 3, 0, 1, 2)
        self.root.addLayout(grid)

        run = QPushButton("⚙️  Apply"); run.clicked.connect(self._run)
        self.root.addWidget(run)
        self._status_line()
        self._save_row()

    def _browse(self):
        p = self._pick_open("Select map to threshold")
        if not p:
            return
        self.in_lbl.setText(p)
        try:
            self._in = _load_nifti(p)
            d = self._in[0]
            self.status.setText(f"Loaded shape={d.shape}  range=[{np.nanmin(d):.3f}, {np.nanmax(d):.3f}]")
        except Exception as e:
            self.status.setText(f"Load error: {e}")
            self._in = None

    def _run(self):
        if self._in is None:
            QMessageBox.information(self, "No input", "Choose a map first.")
            return
        from scipy import ndimage
        data, affine, header = self._in
        vals = np.abs(data) if self.use_abs.isChecked() else data
        keep = vals > self.thr_min.value()

        min_ext = self.min_ext.value()
        removed = 0
        if min_ext > 0 and keep.any():
            c = int(self.conn.currentText())
            if c == 6:
                struct = ndimage.generate_binary_structure(3, 1)
            elif c == 18:
                struct = ndimage.generate_binary_structure(3, 2)
            else:
                struct = ndimage.generate_binary_structure(3, 3)
            lab, n = ndimage.label(keep, structure=struct)
            if n > 0:
                sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
                small = np.where(sizes < min_ext)[0] + 1
                removed = len(small)
                if removed:
                    keep[np.isin(lab, small)] = False

        if self.binarize.isChecked():
            out = keep.astype(np.float32)
        else:
            out = np.where(keep, data, 0).astype(np.float32)
        n_vox = int(keep.sum())
        self._set_result(out, affine, header,
            note=f"Threshold >{self.thr_min.value():g}"
                 f"{' (abs)' if self.use_abs.isChecked() else ''}; "
                 f"min cluster {min_ext} vox → {n_vox:,} voxels kept"
                 + (f", {removed} small clusters removed." if removed else "."))


# ---------------------------------------------------------------------------
# 3. ROI Tool — build (sphere / atlas label) AND extract signal
# ---------------------------------------------------------------------------
class ROIPanel(_ToolPanel):
    def __init__(self, owner):
        super().__init__(owner, "ROI Tool",
            "Build an ROI (a sphere at an MNI coordinate, or one atlas label "
            "as a mask) and/or extract signal from maps within an ROI.")
        self._roi = None       # (mask_data, affine)
        self._extract_maps = []  # list of (name, data, affine)

        # --- Build section ---
        self.root.addWidget(_section("Build ROI"))
        mode_row = QHBoxLayout()
        self.bg = QButtonGroup(self)
        self.rb_sphere = QRadioButton("Sphere at MNI"); self.rb_sphere.setChecked(True)
        self.rb_atlas = QRadioButton("Atlas label")
        self.bg.addButton(self.rb_sphere); self.bg.addButton(self.rb_atlas)
        mode_row.addWidget(self.rb_sphere); mode_row.addWidget(self.rb_atlas)
        mode_row.addStretch()
        self.root.addLayout(mode_row)

        sph = QGridLayout()
        sph.addWidget(QLabel("MNI X,Y,Z:"), 0, 0)
        self.sx = QLineEdit("0"); self.sy = QLineEdit("0"); self.sz = QLineEdit("0")
        for w in (self.sx, self.sy, self.sz):
            w.setMaximumWidth(60); w.setFont(QFont('Consolas', 10))
        sb = QHBoxLayout()
        sb.addWidget(self.sx); sb.addWidget(self.sy); sb.addWidget(self.sz); sb.addStretch()
        sw = QWidget(); sw.setLayout(sb); sph.addWidget(sw, 0, 1)
        sph.addWidget(QLabel("Radius (mm):"), 1, 0)
        self.radius = QDoubleSpinBox(); self.radius.setRange(1, 50); self.radius.setValue(6)
        sph.addWidget(self.radius, 1, 1)
        sph.addWidget(QLabel("Grid space:"), 2, 0)
        self.sphere_space = QComboBox()
        for k in STANDARD_SPACES: self.sphere_space.addItem(k, k)
        sph.addWidget(self.sphere_space, 2, 1)
        self.root.addLayout(sph)

        atl = QGridLayout()
        atl.addWidget(QLabel("Atlas:"), 0, 0)
        self.atlas_combo = QComboBox()
        self.atlas_combo.addItems(["Harvard-Oxford cortical", "Harvard-Oxford subcortical"])
        atl.addWidget(self.atlas_combo, 0, 1)
        atl.addWidget(QLabel("Region:"), 1, 0)
        self.region_combo = QComboBox()
        atl.addWidget(self.region_combo, 1, 1)
        self.atlas_combo.currentIndexChanged.connect(self._populate_regions)
        self.root.addLayout(atl)

        build = QPushButton("🔨  Build ROI"); build.clicked.connect(self._build)
        self.root.addWidget(build)

        # --- Extract section ---
        self.root.addWidget(_section("Extract signal"))
        ex_row = QHBoxLayout()
        addm = QPushButton("Add map(s)…"); addm.clicked.connect(self._add_maps)
        ex_row.addWidget(addm)
        clearm = QPushButton("Clear maps"); clearm.clicked.connect(self._clear_maps)
        ex_row.addWidget(clearm)
        ex_row.addStretch()
        self.root.addLayout(ex_row)
        self.maps_lbl = QLabel("No maps added.")
        self.maps_lbl.setStyleSheet(f"color:{_colors()['body']};")
        self.root.addWidget(self.maps_lbl)
        extract = QPushButton("📊  Extract values"); extract.clicked.connect(self._extract)
        self.root.addWidget(extract)

        self.table = QTableWidget(); self.table.setMinimumHeight(140)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Map", "Mean", "Peak", "Min", "Voxels"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.root.addWidget(self.table)

        self._status_line()
        self._save_row()   # saves the built ROI mask
        self._populate_regions()

    def _populate_regions(self):
        self.region_combo.clear()
        if anat is None:
            self.region_combo.addItem("(nilearn/Harvard-Oxford unavailable)")
            return
        try:
            ho = anat._load_ho() if hasattr(anat, '_load_ho') else None
            key = 'cort' if self.atlas_combo.currentIndex() == 0 else 'sub'
            labels = ho[f'{key}_labels'] if ho else []
            for i, name in enumerate(labels):
                if i == 0:
                    continue  # background
                self.region_combo.addItem(name, i)
        except Exception as e:
            self.region_combo.addItem(f"(atlas error: {e})")

    def _build(self):
        if self.rb_sphere.isChecked():
            self._build_sphere()
        else:
            self._build_atlas_label()

    def _build_sphere(self):
        try:
            x, y, z = float(self.sx.text()), float(self.sy.text()), float(self.sz.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Enter numeric MNI X, Y, Z."); return
        space = self.sphere_space.currentData()
        shape, vox = STANDARD_SPACES[space]
        aff = np.eye(4)
        aff[0, 0] = -vox; aff[1, 1] = vox; aff[2, 2] = vox
        aff[0, 3] = vox * (shape[0] // 2)
        aff[1, 3] = -vox * (shape[1] // 2)
        aff[2, 3] = -vox * (shape[2] // 2)
        inv = np.linalg.inv(aff)
        ci, cj, ck = (inv @ np.array([x, y, z, 1.0]))[:3]
        rad_vox = self.radius.value() / vox
        ii, jj, kk = np.mgrid[0:shape[0], 0:shape[1], 0:shape[2]]
        dist = np.sqrt((ii - ci) ** 2 + (jj - cj) ** 2 + (kk - ck) ** 2)
        mask = (dist <= rad_vox).astype(np.float32)
        self._roi = (mask, aff)
        self._set_result(mask, aff, None,
            note=f"Sphere ROI: center MNI ({x:.0f},{y:.0f},{z:.0f}), "
                 f"r={self.radius.value():g}mm → {int(mask.sum()):,} voxels in {space}.")

    def _build_atlas_label(self):
        if anat is None:
            QMessageBox.information(self, "Unavailable",
                "Harvard-Oxford atlas needs nilearn."); return
        try:
            ho = anat._load_ho()
            if ho is None:
                QMessageBox.information(self, "Unavailable",
                    "Harvard-Oxford atlas could not be loaded."); return
            key = 'cort' if self.atlas_combo.currentIndex() == 0 else 'sub'
            idx = self.region_combo.currentData()
            data = ho[f'{key}_data']
            aff = ho[f'{key}_aff']
            mask = (np.asarray(data) == idx).astype(np.float32)
            self._roi = (mask, aff)
            name = self.region_combo.currentText()
            self._set_result(mask, aff, None,
                note=f"Atlas ROI: {name} → {int(mask.sum()):,} voxels.")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Atlas ROI error", str(e))

    def _add_maps(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add map(s)", "", "NIfTI (*.nii *.nii.gz)")
        for p in paths:
            try:
                d, a, _ = _load_nifti(p)
                self._extract_maps.append((Path(p).stem, d, a))
            except Exception as e:
                print(f"map load error {p}: {e}")
        self.maps_lbl.setText(f"{len(self._extract_maps)} map(s) added.")

    def _clear_maps(self):
        self._extract_maps = []
        self.maps_lbl.setText("No maps added.")
        self.table.setRowCount(0)

    def _extract(self):
        if self._roi is None:
            QMessageBox.information(self, "No ROI", "Build an ROI first."); return
        if not self._extract_maps:
            QMessageBox.information(self, "No maps", "Add at least one map."); return
        mask, maff = self._roi
        notes = []
        self.table.setRowCount(0)
        for name, data, aff in self._extract_maps:
            m = mask
            if data.shape != mask.shape or not np.allclose(aff, maff):
                # auto-resample the MASK onto the map grid (nearest) + note it
                m, _ = _resample_to(mask, maff, aff, data.shape, labels=True)
                notes.append(f"{name}: resampled ROI to map grid")
            sel = data[m > 0.5]
            sel = sel[np.isfinite(sel)]
            if sel.size == 0:
                row = (name, "—", "—", "—", "0")
            else:
                row = (name, f"{sel.mean():.4f}", f"{sel.max():.4f}",
                       f"{sel.min():.4f}", f"{sel.size:,}")
            r = self.table.rowCount(); self.table.insertRow(r)
            for c, val in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(str(val)))
        note = "Extracted values for {} map(s).".format(len(self._extract_maps))
        if notes:
            note += "  (" + "; ".join(notes) + ")"
        self.status.setText(note)


# ---------------------------------------------------------------------------
# 4. Combine Maps — arithmetic + logical modes
# ---------------------------------------------------------------------------
class CombinePanel(_ToolPanel):
    def __init__(self, owner):
        super().__init__(owner, "Combine Maps",
            "Combine two or more maps. Arithmetic: add/subtract/mean/multiply. "
            "Logical (on thresholded maps): conjunction/contrast/union. "
            "Mismatched grids are auto-resampled to the first map, with a note.")
        self._maps = []   # list of (name, data, affine, header)

        row = QHBoxLayout()
        addb = QPushButton("Add maps…"); addb.clicked.connect(self._add)
        row.addWidget(addb)
        clr = QPushButton("Clear"); clr.clicked.connect(self._clear)
        row.addWidget(clr); row.addStretch()
        self.root.addLayout(row)
        self.maps_lbl = QLabel("No maps loaded.")
        self.maps_lbl.setStyleSheet(f"color:{_colors()['body']};")
        self.root.addWidget(self.maps_lbl)

        grid = QGridLayout()
        grid.addWidget(QLabel("Mode:"), 0, 0)
        self.mode = QComboBox()
        self.mode.addItems(["Arithmetic", "Logical (set-based)"])
        self.mode.currentIndexChanged.connect(self._mode_changed)
        grid.addWidget(self.mode, 0, 1)
        grid.addWidget(QLabel("Operation:"), 1, 0)
        self.op = QComboBox()
        grid.addWidget(self.op, 1, 1)
        grid.addWidget(QLabel("Logical threshold >"), 2, 0)
        self.lthr = QDoubleSpinBox(); self.lthr.setRange(-1e6, 1e6)
        self.lthr.setDecimals(3); self.lthr.setValue(0.0)
        grid.addWidget(self.lthr, 2, 1)
        self.root.addLayout(grid)

        run = QPushButton("➕  Combine"); run.clicked.connect(self._run)
        self.root.addWidget(run)
        self._status_line()
        self._save_row()
        self._mode_changed()

    def _mode_changed(self):
        self.op.clear()
        if self.mode.currentIndex() == 0:
            self.op.addItems(["Add (A+B+…)", "Subtract (A−B−…)",
                              "Mean", "Multiply (A×B×…)"])
            self.lthr.setEnabled(False)
        else:
            self.op.addItems(["Conjunction (all)", "Contrast (A and not others)",
                              "Union (any)"])
            self.lthr.setEnabled(True)

    def _add(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add maps", "", "NIfTI (*.nii *.nii.gz)")
        for p in paths:
            try:
                d, a, h = _load_nifti(p)
                self._maps.append((Path(p).stem, d, a, h))
            except Exception as e:
                print(f"load error {p}: {e}")
        self.maps_lbl.setText(f"{len(self._maps)} map(s): " +
                              ", ".join(m[0] for m in self._maps))

    def _clear(self):
        self._maps = []
        self.maps_lbl.setText("No maps loaded.")

    def _aligned_stack(self):
        """Resample all maps onto the first map's grid; return (stack, affine, header, notes)."""
        name0, d0, a0, h0 = self._maps[0]
        stack = [d0]
        notes = []
        for name, d, a, h in self._maps[1:]:
            if d.shape != d0.shape or not np.allclose(a, a0):
                d, _ = _resample_to(d, a, a0, d0.shape, labels=False)
                notes.append(f"{name} resampled to {name0}")
            stack.append(d)
        return np.stack(stack, axis=-1), a0, h0, notes

    def _run(self):
        if len(self._maps) < 2:
            QMessageBox.information(self, "Need 2+ maps", "Add at least two maps."); return
        try:
            stack, affine, header, notes = self._aligned_stack()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Align error", str(e)); return

        if self.mode.currentIndex() == 0:  # arithmetic
            op = self.op.currentIndex()
            if op == 0:   out = np.nansum(stack, axis=-1)
            elif op == 1:
                out = stack[..., 0].copy()
                for i in range(1, stack.shape[-1]):
                    out = out - stack[..., i]
            elif op == 2: out = np.nanmean(stack, axis=-1)
            else:         out = np.nanprod(stack, axis=-1)
        else:  # logical
            thr = self.lthr.value()
            bins = stack > thr
            op = self.op.currentIndex()
            if op == 0:   out = np.all(bins, axis=-1)
            elif op == 1: out = bins[..., 0] & ~np.any(bins[..., 1:], axis=-1)
            else:         out = np.any(bins, axis=-1)
            out = out.astype(np.float32)

        note = f"Combined {len(self._maps)} maps ({self.op.currentText()})."
        if notes:
            note += "  (" + "; ".join(notes) + ")"
        self._set_result(np.asarray(out, dtype=np.float32), affine, header, note=note)


# ---------------------------------------------------------------------------
# 5. Term -> Map  (NiMARE / Neurosynth)
# ---------------------------------------------------------------------------
class _NimareWorker(QThread):
    done = pyqtSignal(object)     # (data, affine) or None
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, kind, payload):
        super().__init__()
        self.kind = kind          # 'term_map' | 'decode_point'
        self.payload = payload

    def run(self):
        try:
            if self.kind == 'term_map':
                self._term_map()
            elif self.kind == 'macm':
                self._macm()
            else:
                self._decode_point()
        except FileNotFoundError as e:
            self.failed.emit(str(e))
        except (EOFError, OSError) as e:
            self.failed.emit(
                "A Neurosynth corpus file appears corrupt or unreadable.\n"
                "Re-download the version-7 files into the corpus folder.\n\n"
                + f"{e}\n{traceback.format_exc()}")
        except Exception as e:
            self.failed.emit(f"{e}\n{traceback.format_exc()}")

    # Where the Neurosynth v7 corpus lives. Resolved at runtime so it can be
    # overridden by the app's "Neurosynth Data" setting; falls back to the
    # in-project corpus folder and then the legacy auto-download cache.
    @staticmethod
    def _corpus_dir():
        import os
        # 1) explicit override via env or module-level setting
        override = os.environ.get("MBCT_NEUROSYNTH_DIR")
        if override and os.path.isdir(override):
            return override
        if _USER_CORPUS_DIR and os.path.isdir(_USER_CORPUS_DIR):
            return _USER_CORPUS_DIR
        # 2) search bundled-resource dir, the project dir, and the user-data dir
        search_roots = []
        try:
            from paths import resource_dir, user_data_dir
            search_roots.append(Path(resource_dir()))
            search_roots.append(Path(user_data_dir()))
        except Exception:
            pass
        search_roots.append(Path(__file__).resolve().parent)
        for root in search_roots:
            for cand in (root / "neurosynth_cache" / "corpus",
                         root / "neurosynth_cache" / "neurosynth",
                         root / "neurosynth_cache",
                         root / "corpus"):
                if cand.is_dir() and any(cand.glob("*coordinates.tsv.gz")):
                    return str(cand)
        # 3) legacy auto-download cache in the home dir
        home = os.path.join(os.path.expanduser("~"), ".mbct_neurosynth")
        for cand in (os.path.join(home, "neurosynth"), home):
            if os.path.isdir(cand):
                return cand
        return None

    def _dataset(self):
        """Build a NiMARE Dataset from the LOCAL Neurosynth v7 corpus files.
        No network access: reads coordinates/metadata/features/vocabulary
        straight from the corpus folder via convert_neurosynth_to_dataset.
        """
        import os, glob
        from nimare.io import convert_neurosynth_to_dataset

        folder = self._corpus_dir()
        print(f"[corpus] _corpus_dir() -> {folder}")
        if not folder:
            raise FileNotFoundError(
                "Neurosynth corpus not found. Place the version-7 files in "
                "a 'neurosynth_cache/corpus' folder, or set the data directory "
                "in the Neurosynth Data panel.")

        def _find(pattern):
            hits = glob.glob(os.path.join(folder, pattern))
            return hits[0] if hits else None

        coords = _find("*version-7_coordinates.tsv.gz")
        meta = _find("*version-7_metadata.tsv.gz")
        feats = _find("*vocab-terms_source-abstract_type-tfidf_features.npz")
        vocab = _find("*vocab-terms_vocabulary.txt")
        print(f"[corpus] coords={bool(coords)} meta={bool(meta)} "
              f"feats={bool(feats)} vocab={bool(vocab)}")
        if not (coords and meta and feats):
            try:
                present = os.listdir(folder)
            except Exception:
                present = "(could not list)"
            print(f"[corpus] folder contents: {present}")
            missing = [n for n, v in [("coordinates", coords),
                                      ("metadata", meta),
                                      ("features(terms)", feats)] if not v]
            raise FileNotFoundError(
                f"Corpus folder '{folder}' is missing: {', '.join(missing)}.")

        self.progress.emit("Loading local Neurosynth corpus…")
        # NiMARE expects annotations as a list of dicts pairing each features
        # file with its vocabulary. (Passing a bare path fails on some versions
        # with: string indices must be integers — annotations_dict["features"].)
        annotations = [{"vocabulary": vocab, "features": feats}] if vocab else \
                      [{"features": feats}]
        try:
            dset = convert_neurosynth_to_dataset(
                coordinates_file=coords, metadata_file=meta,
                annotations_files=annotations)
        except (TypeError, KeyError):
            # Fallback for versions that accept a bare features path.
            dset = convert_neurosynth_to_dataset(
                coordinates_file=coords, metadata_file=meta,
                annotations_files=feats)
        # Neurosynth coordinates are MNI152; tag the space so NiMARE applies the
        # right transforms (and to silence the "unrecognized space UNKNOWN" note).
        try:
            dset.space = "mni152_2mm"
            if "space" in dset.coordinates.columns:
                dset.coordinates["space"] = "MNI"
        except Exception:
            pass
        return dset

    def _term_map(self):
        from nimare.meta.cbma import MKDAChi2
        term = self.payload['term']
        dset = self._dataset()
        self.progress.emit(f"Selecting studies for '{term}'…")
        feature = f"terms_abstract_tfidf__{term}"
        ids = dset.get_studies_by_label(labels=[feature], label_threshold=0.001)
        if not ids:
            self.failed.emit(f"No studies found for term '{term}'."); return
        dset_sel = dset.slice(ids)
        self.progress.emit(f"Running meta-analysis on {len(ids)} studies…")
        meta = MKDAChi2()
        res = meta.fit(dset_sel, dset)

        # Map names differ across NiMARE versions. Prefer the "association/
        # specificity" map (term-specific), then "consistency/uniformity".
        try:
            available = list(res.maps.keys())
        except Exception:
            available = []
        preferred = [
            "z_desc-associationMinusUnassociated",
            "z_desc-association",
            "z_desc-specificity",
            "z_desc-consistency",
            "z_desc-uniformity",
        ]
        name = next((p for p in preferred if p in available), None)
        if name is None:
            # any z-map, else any map at all
            name = next((m for m in available if m.startswith("z_")),
                        available[0] if available else None)
        if name is None:
            self.failed.emit("Meta-analysis produced no maps."); return
        self.progress.emit(f"Extracting map '{name}'…")
        img = res.get_map(name)
        self.done.emit((np.asarray(img.get_fdata(), dtype=np.float32), img.affine))

    def _decode_point(self):
        from nimare.decode import discrete
        x, y, z = self.payload['xyz']
        radius = self.payload.get('radius', 6)
        use_fdr = self.payload.get('fdr', True)
        dset = self._dataset()
        self.progress.emit("Selecting studies near the coordinate…")
        ids = dset.get_studies_by_coordinate([[x, y, z]], r=radius)
        if not ids:
            self.failed.emit("No studies near that coordinate."); return
        self.progress.emit(f"Decoding {len(ids)} studies…")
        # NiMARE's `correction` argument is a no-op in some installed versions
        # (it returns identical tables), so we apply Benjamini–Hochberg FDR
        # ourselves on the p-value columns and add explicit corrected columns.
        decoder = discrete.NeurosynthDecoder(correction=None)
        decoder.fit(dset)
        df = decoder.transform(ids=ids)
        if use_fdr:
            try:
                from statsmodels.stats.multitest import multipletests
                for col in ('pReverse', 'pForward'):
                    if col in df.columns:
                        pv = df[col].to_numpy(dtype=float)
                        ok = np.isfinite(pv)
                        corr = np.full_like(pv, np.nan)
                        if ok.any():
                            corr[ok] = multipletests(pv[ok], alpha=0.05,
                                                     method='fdr_bh')[1]
                        df[col + '_fdr'] = corr
            except Exception as e:
                print(f"⚠️ FDR correction failed, showing raw p only: {e}")
        # tell the display whether corrected columns are present
        df.attrs['fdr'] = bool(use_fdr and 'pReverse_fdr' in df.columns)
        self.done.emit(('decode', df))

    def _macm(self):
        """Meta-analytic coactivation: studies activating at the seed are
        meta-analyzed (MKDA density) to show where they co-activate."""
        from nimare.meta.cbma import MKDADensity
        x, y, z = self.payload['xyz']
        radius = self.payload.get('radius', 6)
        dset = self._dataset()
        self.progress.emit("Finding studies that activate at the seed…")
        ids = dset.get_studies_by_coordinate([[x, y, z]], r=radius)
        if not ids:
            self.failed.emit("No studies activate at that coordinate."); return
        sel = dset.slice(ids)
        self.progress.emit(f"Running MACM on {len(ids)} studies…")
        meta = MKDADensity()
        res = meta.fit(sel)
        try:
            available = list(res.maps.keys())
        except Exception:
            available = []
        # MKDADensity produces 'z' (also 'stat', 'p'); prefer the z map.
        name = ("z" if "z" in available
                else next((m for m in available if m.startswith("z")), None)
                or ("stat" if "stat" in available else None)
                or (available[0] if available else None))
        if name is None:
            self.failed.emit("MACM produced no maps."); return
        self.progress.emit(f"Extracting MACM map '{name}'…")
        img = res.get_map(name)
        self.done.emit((np.asarray(img.get_fdata(), dtype=np.float32), img.affine))


class _TermMapAnimation(QWidget):
    """A lightweight, dependency-free looping animation depicting the idea of
    'a term flowing into a brain map'. Painted with QPainter on a QTimer; no
    image assets, crisp at any size."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._t = 0.0
        self._words = ["pain", "memory", "fear", "reward", "language",
                       "attention", "motor", "emotion"]
        self._wi = 0
        self._timer = QTimer(self)
        self._timer.setInterval(40)  # ~25 fps
        self._timer.timeout.connect(self._tick)

    def start(self): self._timer.start()
    def stop(self): self._timer.stop()

    def _tick(self):
        self._t += 0.04
        # cycle the displayed word every ~3 seconds
        if int(self._t * 1000) % 3000 < 40:
            self._wi = (self._wi + 1) % len(self._words)
        self.update()

    def paintEvent(self, ev):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cy = h / 2.0

        # left: the term "chip"
        term = self._words[self._wi]
        chip_w = min(150, w * 0.32); chip_h = 44
        chip_x = w * 0.06; chip_y = cy - chip_h / 2
        grad = QLinearGradient(chip_x, chip_y, chip_x, chip_y + chip_h)
        grad.setColorAt(0, QColor("#1e88e5")); grad.setColorAt(1, QColor("#0d47a1"))
        p.setBrush(QBrush(grad)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(chip_x, chip_y, chip_w, chip_h), 10, 10)
        p.setPen(QColor("#ffffff"))
        f = QFont('Segoe UI', 13, QFont.Weight.Bold); p.setFont(f)
        p.drawText(QRectF(chip_x, chip_y, chip_w, chip_h),
                   Qt.AlignmentFlag.AlignCenter, term)

        # middle: flowing arrow with moving dots
        ax0 = chip_x + chip_w + 14
        ax1 = w * 0.62
        p.setPen(QPen(QColor("#3a4a66"), 3))
        p.drawLine(QPointF(ax0, cy), QPointF(ax1, cy))
        # arrowhead
        p.setBrush(QColor("#3a4a66")); p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPointF(ax1 + 10, cy), QPointF(ax1 - 4, cy - 7),
                      QPointF(ax1 - 4, cy + 7))
        # moving dots along the arrow
        n_dots = 4
        for i in range(n_dots):
            frac = ((self._t * 0.6) + i / n_dots) % 1.0
            dx = ax0 + frac * (ax1 - ax0)
            r = 4 + 2 * math.sin(self._t * 3 + i)
            alpha = int(120 + 120 * math.sin(frac * math.pi))
            p.setBrush(QColor(56, 182, 255, alpha))
            p.drawEllipse(QPointF(dx, cy), r, r)

        # right: pulsing 'brain map' blob (concentric radial glow + hotspots)
        bx = w * 0.82; by = cy
        base_r = min(w * 0.14, h * 0.4)
        pulse = 1.0 + 0.06 * math.sin(self._t * 2.0)
        for rad_mult, col in [(1.25, QColor(56, 182, 255, 30)),
                              (1.0, QColor(56, 182, 255, 60)),
                              (0.7, QColor(120, 210, 255, 110))]:
            rr = base_r * rad_mult * pulse
            rg = QRadialGradient(bx, by, rr)
            rg.setColorAt(0, col)
            rg.setColorAt(1, QColor(col.red(), col.green(), col.blue(), 0))
            p.setBrush(QBrush(rg)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(bx, by), rr, rr)
        # a few "activation" hotspots that drift
        for i in range(3):
            ang = self._t * (0.7 + 0.2 * i) + i * 2.1
            hx = bx + math.cos(ang) * base_r * 0.4
            hy = by + math.sin(ang * 1.3) * base_r * 0.35
            hr = 6 + 3 * math.sin(self._t * 2 + i)
            hot = QRadialGradient(hx, hy, hr)
            hot.setColorAt(0, QColor("#ff5252")); hot.setColorAt(1, QColor(255, 82, 82, 0))
            p.setBrush(QBrush(hot)); p.drawEllipse(QPointF(hx, hy), hr, hr)
        p.end()


class TermMapPanel(_ToolPanel):
    def __init__(self, owner):
        super().__init__(owner, "Term → Map (Neurosynth)",
            "Type a term and generate its Neurosynth meta-analytic map "
            "(reads the local v7 corpus — no download).")
        row = QGridLayout()
        row.addWidget(QLabel("Term:"), 0, 0)
        self.term = QLineEdit(); self.term.setPlaceholderText("e.g. working memory, pain, fear")
        self.term.returnPressed.connect(self._run)
        row.addWidget(self.term, 0, 1)
        self.root.addLayout(row)
        self.run_btn = QPushButton("🧮  Generate map"); self.run_btn.clicked.connect(self._run)
        self.root.addWidget(self.run_btn)

        # Looping animation occupies the empty space (idle / while running).
        self.anim = _TermMapAnimation()
        self.root.addWidget(self.anim, 1)
        self.anim.start()

        # Result preview (hidden until a map is generated): big term -> arrow -> thumbnail
        self.result_box = QWidget()
        rb = QHBoxLayout(self.result_box)
        rb.setContentsMargins(8, 8, 8, 8); rb.setSpacing(14)
        self.result_term = QLabel("")
        self.result_term.setFont(QFont('Segoe UI', 20, QFont.Weight.Bold))
        self.result_term.setStyleSheet(f"color:{_colors()['accent']};")
        rb.addWidget(self.result_term)
        arrow = QLabel("➜"); arrow.setFont(QFont('Segoe UI', 24, QFont.Weight.Bold))
        arrow.setStyleSheet("color:#86efac;")
        rb.addWidget(arrow)
        self.result_thumb = QLabel()
        self.result_thumb.setMinimumSize(220, 120)
        self.result_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_thumb.setStyleSheet(
            "background:#05050c; border:1px solid #2a3a5a; border-radius:6px;")
        rb.addWidget(self.result_thumb)
        rb.addStretch()
        self.result_box.hide()
        self.root.addWidget(self.result_box)

        self._status_line()
        self._save_row()
        self._worker = None

    def _run(self):
        term = self.term.text().strip().lower()
        if not term:
            QMessageBox.information(self, "No term", "Enter a term."); return
        self.run_btn.setEnabled(False)
        self.result_box.hide()
        self.anim.show(); self.anim.start()
        self.status.setText("Starting…")
        self._worker = _NimareWorker('term_map', {'term': term})
        self._worker.progress.connect(lambda m: self.status.setText(m))
        self._worker.failed.connect(self._on_fail)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_fail(self, msg):
        self.run_btn.setEnabled(True)
        self.status.setText("Failed — see console.")
        print(msg)
        QMessageBox.critical(self, "Term → Map error", msg.split("\n")[0])

    def _on_done(self, result):
        self.run_btn.setEnabled(True)
        data, affine = result
        # stop+hide the loop, reveal the real result
        self.anim.stop(); self.anim.hide()
        self.result_term.setText(self.term.text().strip())
        # render a thumbnail of the ACTUAL generated map (glass brain if possible)
        try:
            self._make_thumb(data, affine)
        except Exception as e:
            print(f"thumb error: {e}")
            self.result_thumb.setText("(map ready — Open in Viewer)")
        self.result_box.show()
        self._set_result(data, affine, None,
            note=f"Generated meta-analytic map for '{self.term.text().strip()}'. "
                 "Save it or Open in Viewer.")

    def _make_thumb(self, data, affine):
        """Render a small glass-brain thumbnail of the generated map."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from io import BytesIO
        import nibabel as nib
        img = nib.Nifti1Image(np.asarray(data, dtype=np.float32), affine)
        fig = plt.figure(figsize=(3.2, 1.7), facecolor='#05050c')
        try:
            from nilearn import plotting as niplot
            niplot.plot_glass_brain(img, figure=fig, display_mode='z',
                                    colorbar=False, black_bg=True, plot_abs=False)
        except Exception:
            # fallback: a middle axial slice
            ax = fig.add_subplot(111); ax.set_facecolor('#05050c')
            mid = data.shape[2] // 2
            ax.imshow(data[:, :, mid].T, origin='lower', cmap='hot'); ax.axis('off')
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, facecolor='#05050c',
                    bbox_inches='tight', pad_inches=0)
        plt.close(fig); buf.seek(0)
        im = QImage(); im.loadFromData(buf.getvalue())
        pm = QPixmap.fromImage(im).scaled(
            self.result_thumb.width(), self.result_thumb.height(),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.result_thumb.setPixmap(pm)


# ---------------------------------------------------------------------------
# 6. Coordinate -> Terms  (NiMARE / Neurosynth)
# ---------------------------------------------------------------------------
class CoordTermsPanel(_ToolPanel):
    def __init__(self, owner):
        super().__init__(owner, "Coordinate → Terms (Neurosynth)",
            "Given an MNI coordinate, return the Neurosynth functional term "
            "profile of nearby studies, using the local Neurosynth v7 corpus.")
        grid = QGridLayout()
        grid.addWidget(QLabel("MNI X,Y,Z:"), 0, 0)
        self.cx = QLineEdit("0"); self.cy = QLineEdit("0"); self.cz = QLineEdit("0")
        rr = QHBoxLayout()
        for w in (self.cx, self.cy, self.cz):
            w.setMaximumWidth(60); w.setFont(QFont('Consolas', 10)); rr.addWidget(w)
        rr.addStretch(); rw = QWidget(); rw.setLayout(rr)
        grid.addWidget(rw, 0, 1)
        grid.addWidget(QLabel("Radius (mm):"), 1, 0)
        self.radius = QSpinBox(); self.radius.setRange(1, 20); self.radius.setValue(6)
        grid.addWidget(self.radius, 1, 1)
        self.fdr_chk = QCheckBox("FDR correction (Benjamini-Hochberg)")
        self.fdr_chk.setChecked(True)
        grid.addWidget(self.fdr_chk, 2, 0, 1, 2)
        grid.addWidget(QLabel("Show:"), 3, 0)
        show_row = QHBoxLayout()
        self.show_combo = QComboBox()
        self.show_combo.addItems(["10", "25", "50", "All"])
        self.show_combo.setCurrentText("25")
        self.show_combo.setMaximumWidth(80)
        self.show_combo.currentIndexChanged.connect(self._refresh_table)
        show_row.addWidget(self.show_combo)
        self.noise_chk = QCheckBox("Hide non-cognitive / noise terms")
        self.noise_chk.setChecked(True)
        self.noise_chk.stateChanged.connect(self._refresh_table)
        show_row.addWidget(self.noise_chk)
        show_row.addStretch()
        sw2 = QWidget(); sw2.setLayout(show_row)
        grid.addWidget(sw2, 3, 1)
        self.root.addLayout(grid)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("🔎  Decode coordinate"); self.run_btn.clicked.connect(self._run)
        btn_row.addWidget(self.run_btn)
        self.macm_btn = QPushButton("🧠  Coactivation map (MACM)")
        self.macm_btn.setToolTip("Meta-analytic coactivation: where else do studies "
                                 "activating this point tend to activate?")
        self.macm_btn.clicked.connect(self._run_macm)
        btn_row.addWidget(self.macm_btn)
        self.export_btn = QPushButton("⬇  Export full CSV")
        self.export_btn.setToolTip("Save the complete decoded term profile (all columns) to CSV")
        self.export_btn.clicked.connect(self._export_csv)
        self.export_btn.setEnabled(False)
        btn_row.addWidget(self.export_btn)
        btn_row.addStretch()
        self.root.addLayout(btn_row)

        self.table = QTableWidget(); self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Term", "Association"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(220)
        self.root.addWidget(self.table)
        self._status_line()
        self._save_row()    # to save the MACM map (Open in Viewer too)
        self._worker = None
        self._decode_df = None   # full decoded DataFrame (for export + redraw)

    def _run(self):
        try:
            x, y, z = float(self.cx.text()), float(self.cy.text()), float(self.cz.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Enter numeric MNI X, Y, Z."); return
        self.run_btn.setEnabled(False); self.macm_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.status.setText("Starting…")
        self._worker = _NimareWorker('decode_point',
                                     {'xyz': (x, y, z), 'radius': self.radius.value(),
                                      'fdr': self.fdr_chk.isChecked()})
        self._worker.progress.connect(lambda m: self.status.setText(m))
        self._worker.failed.connect(self._on_fail)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _run_macm(self):
        try:
            x, y, z = float(self.cx.text()), float(self.cy.text()), float(self.cz.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Enter numeric MNI X, Y, Z."); return
        self.run_btn.setEnabled(False); self.macm_btn.setEnabled(False)
        self.status.setText("Starting MACM…")
        self._worker = _NimareWorker('macm',
                                     {'xyz': (x, y, z), 'radius': self.radius.value()})
        self._worker.progress.connect(lambda m: self.status.setText(m))
        self._worker.failed.connect(self._on_fail)
        self._worker.done.connect(self._on_macm_done)
        self._worker.start()

    def _on_macm_done(self, result):
        self.run_btn.setEnabled(True); self.macm_btn.setEnabled(True)
        data, affine = result
        self._set_result(data, affine, None,
            note="Meta-analytic coactivation map (MACM) for this coordinate. "
                 "Save or Open in Viewer to inspect where co-activation occurs.")

    def _on_fail(self, msg):
        self.run_btn.setEnabled(True); self.macm_btn.setEnabled(True)
        self.status.setText("Failed — see console.")
        print(msg)
        QMessageBox.critical(self, "Decode error", msg.split("\n")[0])

    def _on_done(self, result):
        self.run_btn.setEnabled(True); self.macm_btn.setEnabled(True)
        _, df = result
        self._decode_df = df
        self.export_btn.setEnabled(True)
        self._refresh_table()

    @staticmethod
    def _clean_term(t):
        s = str(t)
        if '__' in s:
            s = s.split('__', 1)[1]
        return s

    def _refresh_table(self):
        """(Re)draw the term table from the stored full result, honouring the
        Show count and the noise filter. Cheap, so it runs on every toggle."""
        df = self._decode_df
        if df is None:
            return
        try:
            has_fdr = 'pReverse_fdr' in df.columns
            work = df.copy()
            work['__term'] = [self._clean_term(t) for t in work.index]

            # keep only positively-associated terms (zReverse > 0) as the base
            if 'zReverse' in work.columns:
                work = work[work['zReverse'] > 0]
            # optional noise filter
            if self.noise_chk.isChecked():
                work = work[~work['__term'].map(_is_noise)]

            # sort: by FDR p (ascending) if present, else posterior (descending)
            if has_fdr:
                work = work.sort_values('pReverse_fdr', ascending=True,
                                        na_position='last')
                sort_note = "sorted by FDR-corrected p"
            else:
                work = work.sort_values('probReverse', ascending=False)
                sort_note = "sorted by posterior probability"

            sel = self.show_combo.currentText()
            total = len(work)
            if sel != "All":
                work = work.head(int(sel))
            shown = len(work)

            cols = [("Term", '__term'),
                    ("z (assoc.)", 'zReverse'),
                    ("Posterior", 'probReverse'),
                    ("p (assoc.)", 'pReverse')]
            if has_fdr:
                cols.append(("p (FDR)", 'pReverse_fdr'))

            self.table.setRowCount(0)
            self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels([c[0] for c in cols])
            for _, row in work.iterrows():
                r = self.table.rowCount(); self.table.insertRow(r)
                for ci, (_, key) in enumerate(cols):
                    if key == '__term':
                        txt = str(row['__term'])
                    elif key in df.columns:
                        v = row[key]
                        try:
                            txt = f"{v:.3g}" if key.startswith('p') else f"{v:.3f}"
                        except Exception:
                            txt = str(v)
                    else:
                        txt = "—"
                    self.table.setItem(r, ci, QTableWidgetItem(txt))
            self.status.setText(
                f"Showing {shown} of {total} positively-associated terms "
                f"({sort_note}; "
                + ("FDR-corrected p shown" if has_fdr else "raw p shown")
                + ("; noise terms hidden" if self.noise_chk.isChecked() else "")
                + "). Use Export full CSV for the complete profile.")
        except Exception as e:
            self.status.setText(f"Could not format table: {e}")
            print(e)

    def _export_csv(self):
        """Write the COMPLETE decoded profile (all terms, all columns) to CSV."""
        if self._decode_df is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export decoded terms", "", "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith('.csv'):
            path += '.csv'
        try:
            out = self._decode_df.copy()
            out.insert(0, 'term', [self._clean_term(t) for t in out.index])
            out.to_csv(path, index=False)
            self.status.setText(f"Exported {len(out)} terms to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export error", str(e))


# ---------------------------------------------------------------------------
# The Utilities tab itself: left list + right stacked panels
# ---------------------------------------------------------------------------
class UtilitiesTab(QWidget):
    file_ready = pyqtSignal(str)   # emitted when a tool sends a file to the Viewer

    def __init__(self, parent_main=None, meta_only=False, tools='all'):
        super().__init__()
        self.parent_main = parent_main
        self.meta_only = meta_only
        # meta_only kept for backward compatibility with earlier callers
        self.tools_mode = 'meta' if meta_only else tools
        # The Utilities area uses a fixed dark background in BOTH themes, so all
        # of its text is white/light for readability (a theme-driven dark text
        # colour would be invisible here). This container rule covers every
        # QLabel/checkbox/field label in the tab at once.
        self.setObjectName("utilitiesTab")
        self.setStyleSheet(
            "#utilitiesTab { background:#0a0a14; }"
            "#utilitiesTab QLabel { color:#e6e9ef; }"
            "#utilitiesTab QCheckBox { color:#e6e9ef; }"
            "#utilitiesTab QRadioButton { color:#e6e9ef; }")
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # Left tool menu — kept dark in both themes to match the panel area
        self.menu = QListWidget()
        self.menu.setMaximumWidth(230)
        _c = _colors()
        self.menu.setStyleSheet(
            "QListWidget{background:#141520; border:0.5px solid rgba(255,255,255,0.12);"
            " border-radius:8px; padding:6px; font-size:10pt; color:#e6e9ef;}"
            "QListWidget::item{padding:9px 10px; border-radius:6px;}"
            f"QListWidget::item:selected{{background:{_c['sel_bg']}; color:#ffffff;}}")
        root.addWidget(self.menu)

        # Right stack
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(
            "QStackedWidget{background:#0a0a14; border:1px solid #2a2a44; border-radius:6px;}")
        root.addWidget(self.stack, 1)

        self._all_tools = [
            ("🔄  Converter", ConverterPanel, 'maps'),
            ("⚙️  Threshold & Binarize", ThresholdPanel, 'maps'),
            ("🎯  ROI Tool", ROIPanel, 'maps'),
            ("➕  Combine Maps", CombinePanel, 'maps'),
            ("🧮  Term → Map", TermMapPanel, 'meta'),
            ("🔎  Coordinate → Terms", CoordTermsPanel, 'meta'),
        ]
        # tools mode:  'all'  -> everything (full MBCT app)
        #              'meta' -> only meta-analysis (MBCT Meta-Analysis Tool)
        #              'maps' -> only map-manipulation (MBCT Brain Viewer)
        want = self.tools_mode
        self._tools = []
        for name, cls, kind in self._all_tools:
            if want != 'all' and kind != want:
                continue
            self._tools.append((name, cls(self)))
        for name, panel in self._tools:
            QListWidgetItem(name, self.menu)
            self.stack.addWidget(panel)
        self.menu.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.menu.setCurrentRow(0)
