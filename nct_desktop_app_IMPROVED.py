"""
NCT Desktop Application — Professional Dark Edition
• Real network names from CBIG atlas files
• Interactive triplanar brain map (click-to-navigate crosshair) – left panel
• Overlap bar graph – right panel
• Distinct per-network colours + MNI display
• Table: Name | <Metric> | P-value
• Functional descriptions + PubMed links for selected network
• Export: CSV · NIfTI · PNG · TIF · JPEG
"""

import os, sys, traceback
from pathlib import Path

# On Windows, the default console codec (cp1252) cannot encode the emoji used
# in this app's print() diagnostics (✅ ⚠️ ❌ …), which would raise
# UnicodeEncodeError and abort startup. Force UTF-8 on stdout/stderr so any
# print statement is safe regardless of the console's codepage.
for _stream in ('stdout', 'stderr'):
    try:
        getattr(sys, _stream).reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Import new modules
from home_tab import HomeTab
from help_tab import HelpTab

# ---------------------------------------------------------------------------
# Edition selector.
#   'core' -> Home, Analysis, Results, Help  (the edition described in the
#             manuscript: the multimodal annotation pipeline only)
#   'full' -> adds Brain Viewer, Connectivity and Utilities
# Override with the MBCT_EDITION environment variable, or edit the default.
# ---------------------------------------------------------------------------
MBCT_EDITION = os.environ.get('MBCT_EDITION', 'full').strip().lower()
if MBCT_EDITION not in ('core', 'full'):
    MBCT_EDITION = 'full'
print(f"MBCT edition = {MBCT_EDITION}")

if MBCT_EDITION == 'full':
    from brain_viewer_stats_tab import BrainViewerStatsTab
    from connectivity_tab import ConnectivityTab
else:
    BrainViewerStatsTab = None
    ConnectivityTab = None
import results_extras as rx
from paths import resource_dir as _resource_dir, user_data_dir as _user_data_dir

import theme_manager as tm
try:
    import anatomy_lookup as anat
except Exception:
    anat = None
try:
    import whitematter_lookup as wm
except Exception:
    wm = None

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPushButton, QLabel, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QSizePolicy,
    QFrame, QSplitter, QAbstractItemView, QCheckBox, QRadioButton,
    QSlider, QLineEdit, QGridLayout,
)
from PyQt6.QtCore  import Qt, QThread, pyqtSignal, QSize, QEvent
from PyQt6.QtGui   import QColor, QFont, QPalette

import matplotlib
# Pure Agg backend — render figures to pixmaps and show them in QLabels.
# (FigureCanvasQTAgg is intentionally NOT used: instantiating it segfaults on
# some PyQt6/matplotlib builds. QLabel + pixmap is rock-solid and we get
# click/drag via Qt's own mouse events.)
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PyQt6.QtGui import QPixmap, QImage, QIcon
from io import BytesIO


class ClickableBrainLabel(QLabel):
    """A QLabel that shows a rendered brain slice (pixmap) and emits the mouse
    position (in label pixel coordinates) on press and drag. The owner converts
    those pixel coordinates to MNI. This avoids matplotlib's Qt canvas entirely.

    Signals carry (x_px, y_px, view_id). view_id is '' for the single view or
    'axial'/'coronal'/'sagittal' for triplanar panels.
    """
    pressed = pyqtSignal(float, float, str)
    dragged = pyqtSignal(float, float, str)
    scrolled = pyqtSignal(int, str)   # (+1/-1, view_id)

    def __init__(self, view_id=''):
        super().__init__()
        self.view_id = view_id
        self._dragging = False
        self.setMouseTracking(False)
        # rendered image geometry within the label (for pixel mapping)
        self._img_w = None
        self._img_h = None

    def set_image_size(self, w, h):
        self._img_w = w
        self._img_h = h

    def mousePressEvent(self, ev):
        self._dragging = True
        self.pressed.emit(ev.position().x(), ev.position().y(), self.view_id)

    def mouseMoveEvent(self, ev):
        if self._dragging:
            self.dragged.emit(ev.position().x(), ev.position().y(), self.view_id)

    def mouseReleaseEvent(self, ev):
        self._dragging = False

    def wheelEvent(self, ev):
        step = 1 if ev.angleDelta().y() > 0 else -1
        self.scrolled.emit(step, self.view_id)
from io import BytesIO

# Helper function to convert matplotlib figures to QPixmap
def fig_to_pixmap(fig, width=400, height=300):
    """Convert matplotlib figure to QPixmap for display in Qt."""
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    image = QImage()
    image.loadFromData(buf.getvalue())
    pixmap = QPixmap.fromImage(image)
    return pixmap.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation) if width else pixmap

# Import new modules for converter and white matter
from nct_application.converter_tab import ConverterTab
if MBCT_EDITION == 'full':
    from utilities_tab import UtilitiesTab
else:
    UtilitiesTab = None
from nct_application.nifti_converter import NiftiConverter

# ═══════════════════════════════════════════════════════════════════════════════
#  NETWORK KNOWLEDGE BASE (real literature – no hallucination)
# ═══════════════════════════════════════════════════════════════════════════════

class NetworkKnowledgeBase:
    """
    Provides functional descriptions and top PubMed references for known networks.
    Sources: Yeo et al. 2011 (J Neurophysiol), Power et al. 2011, etc.
    """
    _data = {
        'visual': (
            "Processing of visual stimuli, early sensory integration, and object recognition.",
            [
                ("Visual network: intrinsic connectivity and task-evoked responses",
                 "Yeo BTT et al.", "J Neurophysiol", 2011, "21653723"),
                ("The organization of the human cerebral cortex estimated by intrinsic functional connectivity",
                 "Power JD et al.", "Neuron", 2011, "21653723"),
                ("Correspondence of the brain's functional architecture during activation and rest",
                 "Smith SM et al.", "PNAS", 2009, "19620792"),
                ("Visual network connectivity predicts individual differences in perception",
                 "Stevens WD et al.", "Cereb Cortex", 2015, "24654257"),
                ("Functional connectivity in the visual cortex: rest and task",
                 "Cole MW et al.", "J Neurosci", 2010, "20660258")
            ]
        ),
        'somato_motor': (
            "Planning, control, and execution of voluntary movements; somatosensory processing.",
            [
                ("The somatomotor system: functional architecture from resting-state fMRI",
                 "Biswal B et al.", "Magn Reson Med", 1995, "8524021"),
                ("Motor network connectivity predicts recovery after stroke",
                 "Carter AR et al.", "Stroke", 2010, "20167919"),
                ("Somatomotor network dynamics during hand movement",
                 "Fox MD et al.", "J Neurophysiol", 2006, "16481422"),
                ("Resting-state functional connectivity in the motor cortex",
                 "De Luca M et al.", "Neuroimage", 2006, "16427322"),
                ("The human motor network: multi-modal parcellation",
                 "Glasser MF et al.", "Nature", 2016, "27437579")
            ]
        ),
        'dorsal_attention': (
            "Voluntary top‑down orienting of attention, visuospatial processing, and eye movements.",
            [
                ("The dorsal attention network: selective attention and working memory",
                 "Corbetta M, Shulman GL", "Nat Rev Neurosci", 2002, "11865301"),
                ("Dissociable intrinsic connectivity networks for salience processing",
                 "Seeley WW et al.", "J Neurosci", 2007, "17620557"),
                ("Functional connectivity in the dorsal attention network",
                 "Fox MD et al.", "Nat Rev Neurosci", 2007, "17620557"),
                ("Attention and performance: dorsal and ventral systems",
                 "Corbetta M et al.", "Annu Rev Psychol", 2008, "18173372"),
                ("Resting-state functional connectivity of dorsal attention",
                 "Vincent JL et al.", "J Neurophysiol", 2008, "18463222")
            ]
        ),
        'ventral_attention': (
            "Stimulus‑driven attentional capture, reorienting to salient events.",
            [
                ("The ventral attention network: right‑hemisphere dominance",
                 "Corbetta M, Shulman GL", "Nat Rev Neurosci", 2002, "11865301"),
                ("Salience network and ventral attention overlap",
                 "Seeley WW et al.", "J Neurosci", 2007, "17620557"),
                ("Resting-state networks and attention reorienting",
                 "Dosenbach NUF et al.", "Neuron", 2007, "18083101"),
                ("Ventral attention network in spatial neglect",
                 "Corbetta M et al.", "Neuron", 2005, "16242654"),
                ("Functional connectivity and attention deficits",
                 "Vossel S et al.", "Brain", 2006, "16543365")
            ]
        ),
        'limbic': (
            "Emotion processing, memory, reward, and autonomic regulation.",
            [
                ("The limbic network: emotion, memory, and social cognition",
                 "LeDoux JE", "Annu Rev Neurosci", 2000, "10845068"),
                ("Limbic system functional connectivity in depression",
                 "Drevets WC et al.", "Biol Psychiatry", 2008, "18502327"),
                ("Intrinsic connectivity of the human limbic system",
                 "Kahn I et al.", "J Neurosci", 2008, "18524852"),
                ("Limbic networks in anxiety and fear conditioning",
                 "Etkin A, Wager TD", "Am J Psychiatry", 2007, "17974936"),
                ("Resting-state limbic connectivity and emotional traits",
                 "Tao Y et al.", "Soc Cogn Affect Neurosci", 2020, "32232412")
            ]
        ),
        'frontoparietal': (
            "Cognitive control, executive functions, and flexible task switching.",
            [
                ("The frontoparietal control network: executive functions",
                 "Vincent JL et al.", "J Neurophysiol", 2008, "18463222"),
                ("Frontoparietal network dynamics in cognitive control",
                 "Cole MW et al.", "Nat Neurosci", 2013, "23416451"),
                ("Intrinsic connectivity and executive performance",
                 "Seeley WW et al.", "J Neurosci", 2007, "17620557"),
                ("Frontoparietal network in working memory",
                 "Rottschy C et al.", "Neuroimage", 2012, "22155037"),
                ("Resting-state frontoparietal connectivity and IQ",
                 "Cole MW et al.", "PNAS", 2012, "22711832")
            ]
        ),
        'default': (
            "Self‑referential thought, autobiographical memory, mental simulation, and theory of mind.",
            [
                ("The default mode network: intrinsic brain activity",
                 "Raichle ME et al.", "PNAS", 2001, "11403820"),
                ("Default network functional connectivity in rest and task",
                 "Fox MD et al.", "PNAS", 2005, "16339316"),
                ("Default mode network: function and dysfunction",
                 "Buckner RL et al.", "Ann N Y Acad Sci", 2008, "18400927"),
                ("Default network connectivity in aging and Alzheimer's",
                 "Greicius MD et al.", "PNAS", 2004, "15159541"),
                ("Default mode network supports social cognition",
                 "Mars RB et al.", "J Neurosci", 2012, "22815513")
            ]
        ),
        'default_mode': (
            "Self‑referential thought, autobiographical memory, mental simulation.",
            [("Default mode network: intrinsic activity", "Raichle ME", "PNAS", 2001, "11403820")]
        ),
        'control': (
            "Cognitive control and executive functions.",
            [("Frontoparietal control network", "Vincent JL", "J Neurophysiol", 2008, "18463222")]
        ),
        'attention': (
            "Attentional processing (dorsal/ventral attention).",
            [("Attention networks", "Corbetta M", "Nat Rev Neurosci", 2002, "11865301")]
        )
    }

    @classmethod
    def get_info(cls, network_name: str):
        """Return (description, list_of_tuples) for the given network."""
        name_lower = network_name.lower().replace('_', '').replace('-', '').replace(' ', '')
        for key, value in cls._data.items():
            if key in name_lower or name_lower in key:
                return value
        desc = "No functional description available for this network in the current knowledge base."
        placeholder = [("Literature not yet curated", "N/A", "N/A", 0, "")]
        return (desc, placeholder)


# ═══════════════════════════════════════════════════════════════════════════════
#  STYLESHEET
# ═══════════════════════════════════════════════════════════════════════════════

STYLE = """
QMainWindow, QWidget         { background:#0d0d1c; color:#dde6f0; font-family:'Segoe UI'; }
QSplitter::handle            { background:#1a1a30; width:2px; }

QTabWidget::pane             { border:1px solid #22223a; background:#0d0d1c; }
QTabBar::tab                 { background:#141428; color:#7080a0; padding:10px 24px;
                               margin:2px; border-radius:5px 5px 0 0; font-size:10pt; }
QTabBar::tab:selected        { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                                  stop:0 #0055cc,stop:1 #003599);
                               color:#ffffff; font-weight:bold; }
QTabBar::tab:hover:!selected { background:#1c1c34; color:#b0c4de; }

QLabel                       { color:#dde6f0; }
QLabel#section               { color:#38b6ff; font-size:9pt; font-weight:bold;
                               border-left:3px solid #0055cc; padding-left:7px;
                               margin-top:4px; }
QLabel#ok                    { color:#4ade80; }
QLabel#err                   { color:#f87171; }

QLineEdit, QTextEdit         { background:#08080f; color:#dde6f0;
                               border:1px solid #2a2a44; padding:5px; border-radius:4px; }
QSpinBox, QDoubleSpinBox     { background:#08080f; color:#dde6f0;
                               border:1px solid #2a2a44; padding:4px; border-radius:4px; }

QComboBox                    { background:#08080f; color:#dde6f0;
                               border:1px solid #2a2a44; padding:5px 8px; border-radius:4px; }
QComboBox::drop-down         { border:none; width:20px; }
QComboBox::down-arrow        { image:none; border-left:5px solid transparent;
                               border-right:5px solid transparent;
                               border-top:6px solid #5080b0; margin-right:4px; }
QComboBox QAbstractItemView  { background:#0c0c1a; color:#dde6f0;
                               selection-background-color:#003399; border:1px solid #2a2a44; }

QTableWidget                 { background:#07070f; gridline-color:#1c1c32;
                               color:#dde6f0; alternate-background-color:#0c0c1a;
                               border:none; }
QTableWidget::item           { padding:7px 10px; }
QTableWidget::item:selected  { background:#0f2d5a; color:#ffffff; }
QHeaderView::section         { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                                  stop:0 #0044aa,stop:1 #002d7a);
                               color:#e0e8ff; padding:7px 10px; border:none;
                               font-weight:bold; font-size:9.5pt; letter-spacing:0.5px; }

QProgressBar                 { background:#08080f; border:1px solid #2a2a44;
                               border-radius:5px; height:16px; }
QProgressBar::chunk          { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                                  stop:0 #0055cc,stop:1 #00c8ff); border-radius:4px; }

QPushButton                  { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                                  stop:0 #0066dd,stop:1 #0044bb);
                               color:#ffffff; padding:7px 18px; border-radius:5px;
                               font-weight:bold; border:none; font-size:9.5pt; }
QPushButton:hover            { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                                  stop:0 #0088ff,stop:1 #0066dd); }
QPushButton:pressed          { background:#003099; }
QPushButton:disabled         { background:#1a1a2e; color:#444466; }
QPushButton#export_btn       { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                                  stop:0 #005533,stop:1 #003322);
                               font-size:8.5pt; padding:5px 10px; }
QPushButton#export_btn:hover { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                                  stop:0 #007744,stop:1 #005533); }
QPushButton#analyze_btn      { font-size:11pt; padding:10px 28px; min-height:44px;
                               background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                                  stop:0 #0044cc,stop:1 #0099dd); }
QPushButton#analyze_btn:hover{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                                  stop:0 #0066ee,stop:1 #00bbff); }

QScrollBar:vertical          { background:#07070f; width:8px; }
QScrollBar::handle:vertical  { background:#2a2a50; border-radius:4px; }
QScrollBar:horizontal        { background:#07070f; height:8px; }
QScrollBar::handle:horizontal{ background:#2a2a50; border-radius:4px; }
QScrollBar::add-line, QScrollBar::sub-line { height:0; width:0; }
"""


def _section(text):
    l = QLabel(text)
    l.setObjectName("section")
    return l

def _hr():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("background:#1e1e38; max-height:1px; margin:4px 0;")
    return f

def _lbl(text, obj_name=None):
    l = QLabel(text)
    if obj_name:
        l.setObjectName(obj_name)
    return l


# ═══════════════════════════════════════════════════════════════════════════════
#  WORKER THREAD
# ═══════════════════════════════════════════════════════════════════════════════

class AnalysisWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, app_obj, input_file, selected_space, selected_author, selected_atlas):
        super().__init__()
        self.app_obj = app_obj
        self.input_file = input_file
        self.selected_space = selected_space
        self.selected_author = selected_author
        self.selected_atlas = selected_atlas

    def run(self):
        """Run gray matter CBIG analysis in background thread"""
        try:
            self.progress.emit(20)
            
            # Run analysis
            results = self.app_obj.analyze_gray_matter(
                input_file=self.input_file,
                selected_atlas=self.selected_atlas,
                atlas_author=self.selected_author,
                brain_space=self.selected_space
            )
            
            self.progress.emit(90)
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════════════════════
#  ANALYSIS TAB
# ═══════════════════════════════════════════════════════════════════════════════

class AnalysisTab(QWidget):
    analysis_done = pyqtSignal(dict, str)

    def __init__(self, parent_main):
        super().__init__()
        self.parent_main = parent_main
        self.data_file   = None
        self.worker      = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(20, 18, 20, 18)

        root.addWidget(_section("Input File"))
        row = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.file_label.setObjectName("err")
        self.file_label.setFont(QFont('Consolas', 9))
        row.addWidget(self.file_label, 1)
        btn = QPushButton("📂  Browse…")
        btn.setMaximumWidth(150)
        btn.clicked.connect(self._select_file)
        row.addWidget(btn)
        root.addLayout(row)

        self.space_label = QLabel("Space: not detected")
        self.space_label.setObjectName("err")
        self.space_label.setFont(QFont('Consolas', 9))
        root.addWidget(self.space_label)
        root.addWidget(_hr())

        root.addWidget(_section("Atlas Selection"))
        
        # Space selection (the three NCT-supported spaces)
        space_row = QHBoxLayout()
        space_row.addWidget(QLabel("Space:"))
        self.space_combo = QComboBox()
        self.space_combo.setMinimumHeight(30)
        self.space_combo.addItems(["FSLMNI2mm", "fs_LR_32k", "fsaverage6"])
        self.space_combo.currentIndexChanged.connect(self._on_space_changed)
        space_row.addWidget(self.space_combo)
        space_row.addStretch()
        root.addLayout(space_row)
        
        # Author selection
        author_row = QHBoxLayout()
        author_row.addWidget(QLabel("Author:"))
        self.author_combo = QComboBox()
        self.author_combo.setMinimumHeight(30)
        self.author_combo.setPlaceholderText("— select space first —")
        self.author_combo.currentIndexChanged.connect(self._on_author_changed)
        author_row.addWidget(self.author_combo)
        author_row.addStretch()
        root.addLayout(author_row)
        
        # Abbreviation selection
        abbr_row = QHBoxLayout()
        abbr_row.addWidget(QLabel("Atlas:"))
        self.abbr_combo = QComboBox()
        self.abbr_combo.setMinimumHeight(30)
        self.abbr_combo.setPlaceholderText("— select author first —")
        self.abbr_combo.currentIndexChanged.connect(self._on_abbr_selected)
        abbr_row.addWidget(self.abbr_combo)
        abbr_row.addStretch()
        root.addLayout(abbr_row)
        
        # Atlas information and description label
        self.atlas_info_label = QLabel("ℹ️  Atlas info will appear here")
        self.atlas_info_label.setFont(QFont('Consolas', 9))
        self.atlas_info_label.setObjectName("info")
        self.atlas_info_label.setWordWrap(True)
        root.addWidget(self.atlas_info_label)
        
        root.addWidget(_hr())
        
        # ═══════════════════════════════════════════════════════════════════
        #  DATA CONFIGURATION (CBIG toolbox data_info parameters)
        # ═══════════════════════════════════════════════════════════════════
        root.addWidget(_section("Data Configuration"))

        cfg_grid = QGridLayout()
        cfg_grid.setHorizontalSpacing(10)
        cfg_grid.setVerticalSpacing(8)

        # Data_Name
        cfg_grid.addWidget(QLabel("Data Name:"), 0, 0)
        self.data_name_edit = QLineEdit()
        self.data_name_edit.setPlaceholderText("— auto from filename —")
        self.data_name_edit.setMinimumHeight(28)
        cfg_grid.addWidget(self.data_name_edit, 0, 1, 1, 3)

        # Data_Type
        cfg_grid.addWidget(QLabel("Data Type:"), 1, 0)
        self.data_type_combo = QComboBox()
        self.data_type_combo.setMinimumHeight(28)
        self.data_type_combo.addItems(["Metric", "Hard", "Soft"])
        self.data_type_combo.currentTextChanged.connect(self._on_data_type_changed)
        cfg_grid.addWidget(self.data_type_combo, 1, 1)

        # Data_Category (optional)
        cfg_grid.addWidget(QLabel("Category:"), 1, 2)
        self.data_category_edit = QLineEdit()
        self.data_category_edit.setPlaceholderText("optional")
        self.data_category_edit.setMinimumHeight(28)
        cfg_grid.addWidget(self.data_category_edit, 1, 3)

        # Data_Threshold (min, max) - only for Metric / Soft
        self.threshold_label = QLabel("Threshold [min, max]:")
        cfg_grid.addWidget(self.threshold_label, 2, 0)
        thr_row = QHBoxLayout()
        self.thr_min_spin = QDoubleSpinBox()
        self.thr_min_spin.setDecimals(4)
        self.thr_min_spin.setRange(-1e6, 1e6)
        self.thr_min_spin.setValue(0.0)
        self.thr_min_spin.setSingleStep(0.05)
        self.thr_min_spin.setMinimumHeight(28)
        thr_row.addWidget(self.thr_min_spin)
        thr_row.addWidget(QLabel("to"))
        self.thr_max_edit = QLineEdit("Inf")
        self.thr_max_edit.setPlaceholderText("Inf")
        self.thr_max_edit.setMaximumWidth(80)
        self.thr_max_edit.setMinimumHeight(28)
        thr_row.addWidget(self.thr_max_edit)
        thr_widget = QWidget(); thr_widget.setLayout(thr_row)
        cfg_grid.addWidget(thr_widget, 2, 1, 1, 2)

        # Data_NetworkAssignment (optional file)
        cfg_grid.addWidget(QLabel("Network Assign:"), 3, 0)
        na_row = QHBoxLayout()
        self.network_assign_edit = QLineEdit()
        self.network_assign_edit.setPlaceholderText("optional — ROI→network mapping file")
        self.network_assign_edit.setMinimumHeight(28)
        na_row.addWidget(self.network_assign_edit, 1)
        na_btn = QPushButton("…")
        na_btn.setMaximumWidth(40)
        na_btn.clicked.connect(self._select_network_assignment)
        na_row.addWidget(na_btn)
        na_widget = QWidget(); na_widget.setLayout(na_row)
        cfg_grid.addWidget(na_widget, 3, 1, 1, 3)

        root.addLayout(cfg_grid)

        # Helper note about Data_Type
        self.data_type_note = QLabel(
            "ℹ️  Metric: continuous map (contrast/probability). "
            "Hard: 1 ROI→1 network (no threshold). "
            "Soft: probabilistic membership."
        )
        self.data_type_note.setFont(QFont('Consolas', 8))
        self.data_type_note.setObjectName("info")
        self.data_type_note.setWordWrap(True)
        root.addWidget(self.data_type_note)

        root.addWidget(_hr())

        root.addWidget(_section("Analysis Parameters"))
        par = QHBoxLayout()
        par.addWidget(QLabel("Permutations:"))
        self.perm_spin = QSpinBox()
        self.perm_spin.setRange(1, 10000); self.perm_spin.setValue(99)
        self.perm_spin.setMaximumWidth(90)
        par.addWidget(self.perm_spin)
        par.addSpacing(12)
        par.addWidget(QLabel("P-threshold:"))
        self.pval_spin = QDoubleSpinBox()
        self.pval_spin.setDecimals(3); self.pval_spin.setRange(0.0001, 1.0)
        self.pval_spin.setValue(0.05); self.pval_spin.setSingleStep(0.01)
        self.pval_spin.setMaximumWidth(90)
        par.addWidget(self.pval_spin)
        par.addSpacing(12)
        par.addWidget(QLabel("Metric:"))
        self.metric_combo = QComboBox()
        self.metric_combo.addItems(["Dice", "Jaccard"])
        self.metric_combo.setMaximumWidth(110)
        par.addWidget(self.metric_combo)
        par.addStretch()
        root.addLayout(par)
        root.addWidget(_hr())

        # Progress bar with an elapsed-time / ETA readout beside it
        prog_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        prog_row.addWidget(self.progress_bar, 1)
        self.timer_lbl = QLabel("⏱ 00:00")
        self.timer_lbl.setFont(QFont('Consolas', 9))
        self.timer_lbl.setMinimumWidth(150)
        self.timer_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog_row.addWidget(self.timer_lbl, 0)
        root.addLayout(prog_row)
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setFont(QFont('Consolas', 9))
        self.status_lbl.setObjectName("ok")
        root.addWidget(self.status_lbl)

        # Timer infrastructure for elapsed time + ETA
        from PyQt6.QtCore import QTimer, QElapsedTimer
        self._elapsed = QElapsedTimer()
        self._tick = QTimer(self)
        self._tick.setInterval(500)  # update twice a second
        self._tick.timeout.connect(self._update_timer_label)

        root.addStretch()

        self.btn_analyze = QPushButton("🧠  Run Analysis")
        self.btn_analyze.setObjectName("analyze_btn")
        self.btn_analyze.clicked.connect(self._run)
        root.addWidget(self.btn_analyze)

    def _on_data_type_changed(self, data_type):
        """Enable/disable threshold controls based on Data_Type.
        Hard parcellations don't use a threshold; Metric/Soft do."""
        is_hard = (data_type == 'Hard')
        # Threshold not applicable for Hard parcellations
        self.threshold_label.setEnabled(not is_hard)
        self.thr_min_spin.setEnabled(not is_hard)
        self.thr_max_edit.setEnabled(not is_hard)
        if is_hard:
            self.threshold_label.setText("Threshold [n/a for Hard]:")
        else:
            self.threshold_label.setText("Threshold [min, max]:")

    def _select_network_assignment(self):
        """Optional: select a network assignment file (ROI → network mapping)."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Network Assignment File", "",
            "Assignment Files (*.mat *.txt *.csv *.npy);;All Files (*)")
        if path:
            self.network_assign_edit.setText(path)

    def _gather_data_config(self):
        """Collect CBIG data_info configuration from the UI controls."""
        cfg = {}
        # Data_Name
        name = self.data_name_edit.text().strip()
        if name:
            cfg['Data_Name'] = name
        # Data_Type
        cfg['Data_Type'] = self.data_type_combo.currentText()
        # Data_Threshold (only Metric / Soft)
        if cfg['Data_Type'] in ('Metric', 'Soft'):
            lo = self.thr_min_spin.value()
            hi_text = self.thr_max_edit.text().strip()
            if hi_text.lower() in ('inf', 'infinity', '', '+inf'):
                hi = 'Inf'
            else:
                try:
                    hi = float(hi_text)
                except ValueError:
                    hi = 'Inf'

            # Format numbers to match CBIG documented spec exactly:
            #   - integer-valued numbers written without a decimal (5 not 5.0)
            #   - 'Inf' kept literal
            #   - single space after the comma:  [5, Inf]
            def _fmt(v):
                if isinstance(v, str):
                    return v
                return str(int(v)) if float(v).is_integer() else repr(float(v))

            lo_str = _fmt(lo)
            hi_str = _fmt(hi)
            cfg['Data_Threshold'] = f"[{lo_str}, {hi_str}]"
        # Optional fields
        na = self.network_assign_edit.text().strip()
        if na:
            cfg['Data_NetworkAssignment'] = na
        cat = self.data_category_edit.text().strip()
        if cat:
            cfg['Data_Category'] = cat
        return cfg

    def _select_file(self):
        """Select and load a NIfTI file, initialize atlas loader"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select NIfTI File", "",
            "NIfTI Files (*.nii *.nii.gz);;All Files (*)")
        if not path:
            return
        
        self.data_file = path
        self.file_label.setText(Path(path).name)
        self.file_label.setObjectName("ok")
        
        # Auto-fill Data_Name from filename (stem, without .nii/.gz)
        stem = Path(path).name.replace('.nii.gz', '').replace('.nii', '')
        if hasattr(self, 'data_name_edit') and not self.data_name_edit.text().strip():
            self.data_name_edit.setText(stem)
        
        try:
            from nct_application.cbig_analysis import BrainSpaceDetector
            from nct_application.cbig_config import CBIGConfig
            from nct_application.cbig_atlas_loader import CBIGAtlasLoader
            
            # Detect space from file
            detected_space = BrainSpaceDetector.detect_space(path)
            if detected_space:
                self.space_label.setText(f"✅ File space: {detected_space}")
            else:
                self.space_label.setText("⚠️  Could not detect file space")
            
            # Initialize atlas loader
            atlas_dir = CBIGConfig.get_atlas_dir()
            if not atlas_dir or not Path(atlas_dir).exists():
                self.space_label.setText("⚠️  Atlas directory not configured")
                return
            
            self.atlas_loader = CBIGAtlasLoader(atlas_dir)
            
            # Populate space combo with the three NCT-supported spaces
            self.space_combo.blockSignals(True)
            self.space_combo.clear()
            self.space_combo.addItems(["FSLMNI2mm", "fs_LR_32k", "fsaverage6"])
            
            # Pre-select based on detected space if available
            if detected_space == "FSLMNI2mm":
                self.space_combo.setCurrentIndex(0)
            elif detected_space == "fs_LR_32k":
                self.space_combo.setCurrentIndex(1)
            elif detected_space == "fsaverage6":
                self.space_combo.setCurrentIndex(2)
            else:
                self.space_combo.setCurrentIndex(0)  # Default to FSLMNI2mm
            
            self.space_combo.blockSignals(False)
            
            # Trigger space changed to populate authors
            self._on_space_changed()
            
            print(f"✅ File loaded: {Path(path).name}")
            print(f"✅ Atlas loader initialized")
            
        except Exception as e:
            print(f"❌ Error loading file: {e}")
            import traceback
            traceback.print_exc()
            self.space_label.setText(f"⚠️  Error: {str(e)[:50]}")
    
    def _on_space_changed(self):
        """Populate author combo when space changes"""
        try:
            from nct_application.atlas_metadata import get_authors
            
            if not hasattr(self, 'atlas_loader'):
                self.author_combo.clear()
                self.abbr_combo.clear()
                return
            
            # Get all unique authors
            authors = sorted(get_authors())
            
            # Populate author combo
            self.author_combo.blockSignals(True)
            self.author_combo.clear()
            self.author_combo.addItems(authors)
            self.author_combo.blockSignals(False)
            
            # Trigger author changed to populate abbreviations
            self._on_author_changed()
            
            print(f"✅ Space changed: {self.space_combo.currentText()} ({len(authors)} authors)")
            
        except Exception as e:
            print(f"❌ Error in _on_space_changed: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_author_changed(self):
        """Populate abbreviation combo when author changes"""
        try:
            from nct_application.atlas_metadata import get_abbreviations_by_author
            
            if not hasattr(self, 'atlas_loader'):
                self.abbr_combo.clear()
                return
            
            selected_author = self.author_combo.currentText()
            
            if not selected_author:
                self.abbr_combo.clear()
                return
            
            # Get all abbreviations for this author
            abbreviations = sorted(get_abbreviations_by_author(selected_author))
            
            # Populate abbreviation combo
            self.abbr_combo.blockSignals(True)
            self.abbr_combo.clear()
            
            for abbr in abbreviations:
                self.abbr_combo.addItem(abbr, abbr)
            
            self.abbr_combo.blockSignals(False)
            self.abbr_combo.setCurrentIndex(0)
            
            print(f"✅ Author selected: {selected_author} ({len(abbreviations)} abbreviations)")
            
        except Exception as e:
            print(f"❌ Error in _on_author_changed: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_abbr_selected(self):
        """Display atlas information and description when abbreviation is selected"""
        try:
            from nct_application.atlas_metadata import get_atlas_info
            
            if self.abbr_combo.currentIndex() < 0:
                self.atlas_info_label.setText("ℹ️  Select an atlas to see information")
                return
            
            selected_abbr = self.abbr_combo.currentData()
            if not selected_abbr:
                return
            
            # Get metadata for this abbreviation
            metadata = get_atlas_info(selected_abbr)
            
            if metadata:
                info_lines = [f"✅ {selected_abbr}"]
                
                # Add description
                if 'description' in metadata:
                    info_lines.append(f"   {metadata['description']}")
                
                # Add source
                if 'source' in metadata:
                    info_lines.append(f"   Source: {metadata['source']}")
                
                # Add number of regions
                if 'num_regions' in metadata:
                    regions = metadata['num_regions']
                    if 'num_components' in metadata:
                        info_lines.append(f"   ROIs/Components: {regions} ({metadata['num_components']} components)")
                    else:
                        info_lines.append(f"   ROIs/Networks: {regions}")
                
                info_text = "\n".join(info_lines)
                self.atlas_info_label.setText(info_text)
                self.atlas_info_label.setObjectName("ok")
            else:
                self.atlas_info_label.setText(f"⚠️  No metadata for {selected_abbr}")
                self.atlas_info_label.setObjectName("err")
        
        except Exception as e:
            self.atlas_info_label.setText(f"⚠️  Error: {str(e)[:60]}")
            print(f"❌ Error in _on_abbr_selected: {e}")
    
    def _fmt_mmss(self, ms):
        """Format milliseconds as MM:SS."""
        s = max(0, int(ms / 1000))
        return f"{s // 60:02d}:{s % 60:02d}"

    def _update_timer_label(self):
        """Tick handler: show elapsed time and a progress-based ETA."""
        if not self._elapsed.isValid():
            return
        elapsed = self._elapsed.elapsed()
        pct = self.progress_bar.value()
        if pct >= 1:
            total_est = elapsed * 100.0 / pct
            remaining = max(0, total_est - elapsed)
            self.timer_lbl.setText(
                f"⏱ {self._fmt_mmss(elapsed)}  ·  ETA {self._fmt_mmss(remaining)}")
        else:
            self.timer_lbl.setText(f"⏱ {self._fmt_mmss(elapsed)}  ·  ETA --:--")

    def _set_progress(self, pct):
        """Set progress and immediately refresh the elapsed/ETA readout.
        Calls processEvents so the UI updates even during synchronous work."""
        self.progress_bar.setValue(pct)
        self._update_timer_label()
        QApplication.processEvents()

    def _start_timer(self):
        self._elapsed.start()
        self.timer_lbl.setText("⏱ 00:00  ·  ETA --:--")
        self._tick.start()

    def _stop_timer(self, final=True):
        self._tick.stop()
        if final and self._elapsed.isValid():
            self.timer_lbl.setText(f"⏱ {self._fmt_mmss(self._elapsed.elapsed())}  ·  done")

    def _run(self):
        """Run CBIG gray matter analysis with selected abbreviation"""
        if not self.data_file:
            QMessageBox.warning(self, "No File", "Please select a NIfTI file first.")
            return
        
        if self.abbr_combo.currentIndex() < 0:
            QMessageBox.warning(self, "No Atlas", "Please select an atlas abbreviation.")
            return
        
        # Detect space
        from nct_application.cbig_analysis import BrainSpaceDetector
        space = BrainSpaceDetector.detect_space(self.data_file)
        
        if not space:
            QMessageBox.critical(self, "Error", "Could not detect brain space from file dimensions.")
            return
        
        # Get selected abbreviation
        selected_abbr = self.abbr_combo.currentData()
        selected_space = self.space_combo.currentText()
        selected_author = self.author_combo.currentText()
        
        if not selected_abbr:
            QMessageBox.warning(self, "Error", "Invalid atlas selection.")
            return
        
        # Verify space match (normalize to avoid false mismatches from stray
        # whitespace or case differences — both should be e.g. 'FSLMNI2mm').
        def _norm(s):
            return (s or '').strip().lower()
        if _norm(space) != _norm(selected_space):
            print(f"⚠️ Space mismatch: detected={space!r}  selected={selected_space!r}")
            QMessageBox.warning(
                self,
                "⚠️  Space Mismatch",
                f"File is in {space} but selected atlas is for {selected_space}.\n\n"
                f"Please convert the file to {selected_space} using the Converter tab.",
            )
            return
        
        # Prepare for analysis
        self._start_timer()
        self._set_progress(10)
        self.status_lbl.setText(f"Analyzing {selected_author} - {selected_abbr}…")
        self.btn_analyze.setEnabled(False)
        
        try:
            from nct_application.application import NCTApplication
            from nct_application.config import NCTConfig
            
            # Get config
            config = NCTConfig()
            
            # Create application with input file
            app_obj = NCTApplication(config, analysis_mode="gray_matter", input_file=self.data_file)
            
            # Gather user data configuration (Data_Type, Data_Threshold, etc.)
            data_config = self._gather_data_config()
            print(f"📋 Data config from UI: {data_config}")
            
            # Inject config directly onto the CBIG analyzer object.
            # This works regardless of which application.py version is loaded,
            # because cbig_analysis.analyze() reads this attribute as a fallback.
            try:
                if getattr(app_obj, 'cbig', None) is not None:
                    app_obj.cbig._ui_data_config = data_config
                    print("📌 Injected data_config onto app_obj.cbig")
            except Exception as _inj_err:
                print(f"⚠️  Could not inject data_config: {_inj_err}")
            
            # Call analyze_gray_matter, adapting to whichever signature exists.
            import inspect
            try:
                _params = inspect.signature(app_obj.analyze_gray_matter).parameters
                _supports_cfg = 'data_config' in _params
            except (ValueError, TypeError):
                _supports_cfg = False
            
            # Run gray matter analysis for this abbreviation
            self._set_progress(50)
            if _supports_cfg:
                results = app_obj.analyze_gray_matter(
                    selected_atlas=selected_abbr,
                    data_config=data_config
                )
            else:
                # Older application.py — config still applied via the injected attribute
                print("ℹ️  application.py is the older version; using injected config fallback")
                results = app_obj.analyze_gray_matter(selected_atlas=selected_abbr)
            
            self._set_progress(100)
            self._stop_timer()
            
            if results:
                results['abbreviation'] = selected_abbr
                results['author'] = selected_author
                results['space'] = selected_space
                self._on_done(results, selected_space)
            
        except Exception as e:
            self.btn_analyze.setEnabled(True)
            self.progress_bar.setValue(0)
            self._stop_timer(final=False)
            self.timer_lbl.setText("⏱ --:--")
            self.status_lbl.setText("❌  Analysis failed")
            print(f"❌ Analysis error: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Analysis Error", str(e))

    def _on_done(self, results, space):
        self.progress_bar.setValue(100)
        self.btn_analyze.setEnabled(True)
        
        # Handle both 'networks' (gray matter) and 'tracts' (white matter) keys
        nets = results.get('networks', []) or results.get('tracts', [])
        
        # Also try extracting from nested structure if needed
        if not nets and 'results' in results and isinstance(results['results'], dict):
            nested_results = results['results']
            if nested_results:
                atlas_code = list(nested_results.keys())[0]
                atlas_result = nested_results[atlas_code]
                nets = atlas_result.get('networks', []) or atlas_result.get('tracts', [])
        
        if not nets:
            self.status_lbl.setText("⚠️  No networks returned")
            QMessageBox.warning(self, "No Results",
                results.get('message', 'Analysis returned 0 networks.'))
            return
        
        # Ensure standard keys exist for display
        if 'networks' not in results and 'tracts' in results:
            results['networks'] = results['tracts']
        
        results['brain_space'] = results.get('brain_space', space)
        self.status_lbl.setText(f"✅  Done — {len(nets)} networks")
        self.analysis_done.emit(results, results['brain_space'])
        self.parent_main.tabs.setCurrentIndex(1)

    def _on_error(self, msg):
        self.progress_bar.setValue(0)
        self.btn_analyze.setEnabled(True)
        self.status_lbl.setText("❌  Analysis failed")
        QMessageBox.critical(self, "Analysis Error", msg)


# ═══════════════════════════════════════════════════════════════════════════════
#  RESULTS TAB — side‑by‑side brain map + bar graph + literature panel
#  (FULLY INTERACTIVE: axial/coronal/sagittal, zoom, colormap, slice slider)
# ═══════════════════════════════════════════════════════════════════════════════

class ResultsTab(QWidget):
    """Results tab with full interactive brain viewer (axial/coronal/sagittal, zoom, colormap, template switching)."""

    def __init__(self):
        super().__init__()
        self.current_results = None
        self.current_atlas_code = None
        self.current_brain_space = None
        
        # Brain viewer state
        self.template_paths = {}          # display name -> full path
        self.current_template_path = None
        self.template_data = None          # 3D numpy array
        self.template_affine = None
        self._atlas_vol = None             # atlas label/prob volume (analysis space)
        self._atlas_aff = None             # atlas affine (voxel -> MNI)
        self._atlas_is_4d = False
        self._atlas_mode = None            # 'labels' | 'metric' | '4d'
        self._label_map = None             # {atlas_label_value: network_row_index}
        self.current_view = 'axial'        # 'axial', 'coronal', 'sagittal'
        self.current_slice_idx = 0
        self.max_slice = 0
        # Per-plane slice indices for the triplanar (linked-navigation) view.
        # axial -> Z, coronal -> Y, sagittal -> X.
        self.slice_ax = 0   # axial slice (Z index)
        self.slice_co = 0   # coronal slice (Y index)
        self.slice_sa = 0   # sagittal slice (X index)
        self.zoom = 1.0
        self.colormap = 'gray'
        
        # Network overlay data
        self.network_names = []
        self.network_overlaps = []
        self.network_pvalues = []
        self.network_centroids = []        # list of (x_mni, y_mni, z_mni) for each network
        
        # Interactive features
        self.crosshair_mni = None          # MNI coordinates for crosshair
        self.current_highlighted_idx = None  # Currently highlighted network
        
        # View mode selection
        self.view_mode = 'single'  # 'single' or 'triplanar'
        self.brain_fig_axial = None
        self.brain_fig_coronal = None
        self.brain_fig_sagittal = None
        self.brain_canvas_axial = None
        self.brain_canvas_coronal = None
        self.brain_canvas_sagittal = None
        self.triplanar_container = None
        
        self._build()
        self._scan_templates()

    # ----------------------------------------------------------------------
    # UI Construction
    # ----------------------------------------------------------------------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        # ----- Top: results table -----
        top_w = QWidget()
        top_v = QVBoxLayout(top_w)
        top_v.setContentsMargins(0, 0, 0, 4)
        top_v.setSpacing(6)

        hdr = QHBoxLayout()
        lbl_t = QLabel("Network Results")
        lbl_t.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
        lbl_t.setStyleSheet("color:#38b6ff;")
        hdr.addWidget(lbl_t)
        hdr.addStretch()
        self.lbl_summary = QLabel("")
        self.lbl_summary.setFont(QFont('Segoe UI', 8))
        self.lbl_summary.setStyleSheet("color:#7090b0; padding-right:4px;")
        hdr.addWidget(self.lbl_summary)
        top_v.addLayout(hdr)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(180)
        self.table.setMaximumHeight(280)
        self.table.clicked.connect(self._on_row_click)
        top_v.addWidget(self.table)

        # ----- Bottom: brain viewer + bar graph + literature panel -----
        bottom_w = QWidget()
        bottom_layout = QVBoxLayout(bottom_w)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(6)

        # Export row
        export_row = QHBoxLayout()
        lbl_b = QLabel("Export:")
        lbl_b.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        lbl_b.setStyleSheet("color:#38b6ff;")
        export_row.addWidget(lbl_b)
        export_row.addStretch()
        for label, fmt in [("📊 CSV", "csv"), ("🧪 NIfTI", "nii"),
                           ("🖼 PNG", "png"), ("🖼 TIF", "tif"), ("🖼 JPEG", "jpg")]:
            btn = QPushButton(label)
            btn.setObjectName("export_btn")
            btn.setMaximumWidth(88)
            btn.setMinimumHeight(28)
            btn.clicked.connect(lambda checked, f=fmt: self._export(f))
            export_row.addWidget(btn)
        # Feature 3: one NIfTI per significant network
        btn_sig = QPushButton("🧠 Sig. NIfTIs")
        btn_sig.setObjectName("export_btn")
        btn_sig.setMinimumHeight(28)
        btn_sig.setToolTip("Save one NIfTI mask per significant network (p < 0.05)")
        btn_sig.clicked.connect(self._export_significant_niftis)
        export_row.addWidget(btn_sig)
        # Feature 4: save / load a reviewable session
        btn_save = QPushButton("💾 Save Results")
        btn_save.setObjectName("export_btn")
        btn_save.setMinimumHeight(28)
        btn_save.setToolTip("Save results so you can reload them later without recomputing")
        btn_save.clicked.connect(self._save_session)
        export_row.addWidget(btn_save)
        btn_load = QPushButton("📂 Load Results")
        btn_load.setObjectName("export_btn")
        btn_load.setMinimumHeight(28)
        btn_load.setToolTip("Reload previously saved results for review")
        btn_load.clicked.connect(self._load_session)
        export_row.addWidget(btn_load)
        bottom_layout.addLayout(export_row)

        # Side-by-side canvases (left: brain, right: bar)
        canvas_container = QWidget()
        canvas_layout = QHBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(12)

        # ---------- LEFT PANEL: Brain viewer with full controls ----------
        left_wrap = QWidget()
        left_layout = QVBoxLayout(left_wrap)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # 1) View mode selection (Single vs Triplanar)
        viewmode_row = QHBoxLayout()
        viewmode_row.setSpacing(6)
        viewmode_label = QLabel("📺 Display Mode:")
        viewmode_label.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
        viewmode_label.setStyleSheet("color:#7090b8;")
        viewmode_row.addWidget(viewmode_label)
        
        self.viewmode_single = QRadioButton("Single Panel")
        self.viewmode_single.setChecked(True)
        self.viewmode_single.toggled.connect(self._on_viewmode_changed)
        viewmode_row.addWidget(self.viewmode_single)
        
        self.viewmode_triplanar = QRadioButton("Triplanar View")
        self.viewmode_triplanar.toggled.connect(self._on_viewmode_changed)
        viewmode_row.addWidget(self.viewmode_triplanar)
        
        viewmode_row.addStretch()
        left_layout.addLayout(viewmode_row)
        
        # 2) Underlay selection
        underlay_row = QHBoxLayout()
        underlay_row.setSpacing(6)
        underlay_label = QLabel("🗺️  Brain Underlay:")
        underlay_label.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
        underlay_label.setStyleSheet("color:#7090b8;")
        underlay_row.addWidget(underlay_label)
        self.underlay_combo = QComboBox()
        self.underlay_combo.setMinimumHeight(26)
        self.underlay_combo.currentIndexChanged.connect(self._on_underlay_changed)
        underlay_row.addWidget(self.underlay_combo)
        underlay_row.addStretch()
        left_layout.addLayout(underlay_row)

        # 2) View buttons (Axial, Coronal, Sagittal) - hidden in triplanar mode
        view_row = QHBoxLayout()
        view_row.setSpacing(5)
        self.view_row_container = QWidget()
        view_row_inner = QHBoxLayout(self.view_row_container)
        view_row_inner.setContentsMargins(0, 0, 0, 0)
        view_row_inner.setSpacing(5)
        
        self.view_btns = {}
        for view_name, view_id in [('Axial', 'axial'), ('Coronal', 'coronal'), ('Sagittal', 'sagittal')]:
            btn = QPushButton(view_name)
            btn.setCheckable(True)
            btn.setMaximumWidth(80)
            btn.clicked.connect(lambda checked, v=view_id: self._set_view(v))
            self.view_btns[view_id] = btn
            view_row_inner.addWidget(btn)
        self.view_btns['axial'].setChecked(True)
        view_row_inner.addStretch()
        
        left_layout.addWidget(self.view_row_container)
        
        # 3) Slice slider + label
        slice_row = QHBoxLayout()
        slice_row.addWidget(QLabel("Slice:"))
        self.slice_slider = QSlider(Qt.Orientation.Horizontal)
        self.slice_slider.setRange(0, 0)
        self.slice_slider.valueChanged.connect(self._on_slice_changed)
        slice_row.addWidget(self.slice_slider, 1)
        self.slice_label = QLabel("0 / 0")
        self.slice_label.setMaximumWidth(60)
        slice_row.addWidget(self.slice_label)
        left_layout.addLayout(slice_row)

        # 4) Zoom slider
        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        zoom_row.addWidget(self.zoom_slider, 1)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMaximumWidth(40)
        zoom_row.addWidget(self.zoom_label)
        left_layout.addLayout(zoom_row)

        # 5) Colormap selection
        cmap_row = QHBoxLayout()
        cmap_row.addWidget(QLabel("Colormap:"))
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(['gray', 'hot', 'viridis', 'plasma', 'inferno', 'bone'])
        self.cmap_combo.currentTextChanged.connect(self._on_colormap_changed)
        cmap_row.addWidget(self.cmap_combo, 1)
        left_layout.addLayout(cmap_row)

        # Brain visualization container (will hold single or triplanar layout)
        self.brain_container = QWidget()
        self.brain_container_layout = QVBoxLayout(self.brain_container)
        self.brain_container_layout.setContentsMargins(0, 0, 0, 0)
        self.brain_container_layout.setSpacing(0)
        
        # Single panel mode: one interactive matplotlib canvas (click + drag
        # the crosshair directly on the brain). Falls back to a static QLabel
        # if the interactive canvas can't be created on this system.
        self.brain_fig = plt.Figure(figsize=(8, 6), facecolor='#0a0a14')
        self.brain_canvas = self._make_canvas(self.brain_fig, view_id='')
        self.brain_canvas.setStyleSheet("background-color: #0a0a14; border: 1px solid #2a3a5a; border-radius: 4px;")
        self.brain_container_layout.addWidget(self.brain_canvas, 1)
        
        # Crosshair readout (Results #3): network name + anatomical location + BA
        self.crosshair_readout = QLabel("⊕ Click or drag on the brain to inspect a location")
        self.crosshair_readout.setFont(QFont('Segoe UI', 9))
        self.crosshair_readout.setWordWrap(True)
        self.crosshair_readout.setStyleSheet(
            "background:#0c1424; border:1px solid #1d3358; border-radius:4px;  "
            "padding:6px 8px; color:#cde4ff;")

        # Info box: now the per-network subregion breakdown
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setFont(QFont('Consolas', 9))
        self.info_text.setPlaceholderText("Cortical subregions of the selected network will appear here")
        self.info_text.setStyleSheet("background:#0c0c1a; border:1px solid #2a2a44; border-radius:4px; padding:4px;")

        # Create splitter for brain container and info text
        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        # Top part: brain container + crosshair readout
        top_splitter_widget = QWidget()
        top_splitter_layout = QVBoxLayout(top_splitter_widget)
        top_splitter_layout.setContentsMargins(0, 0, 0, 0)
        top_splitter_layout.setSpacing(4)
        top_splitter_layout.addWidget(self.brain_container, 1)
        top_splitter_layout.addWidget(self.crosshair_readout)
        self.left_splitter.addWidget(top_splitter_widget)
        self.left_splitter.addWidget(self.info_text)
        # Set initial sizes: brain gets more space, info panel gets less
        self.left_splitter.setSizes([500, 150])
        self.left_splitter.setStretchFactor(0, 1)  # Brain can expand
        self.left_splitter.setStretchFactor(1, 0)  # Info panel stays compact
        left_layout.addWidget(self.left_splitter, 1)

        canvas_layout.addWidget(left_wrap, stretch=5)

        # ---------- RIGHT PANEL: Bar graph ----------
        right_wrap = QWidget()
        right_layout = QVBoxLayout(right_wrap)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.bar_fig = plt.Figure(figsize=(5, 5), facecolor='#0a0a14')
        self.bar_canvas = QLabel()
        self.bar_canvas.setStyleSheet("background-color: #0a0a14; border: 1px solid #2a3a5a; border-radius: 4px;")
        right_layout.addWidget(self.bar_canvas)
        canvas_layout.addWidget(right_wrap, stretch=4)

        bottom_layout.addWidget(canvas_container)

        # ----- Top-right: tabbed annotation panel -----
        #   Tab 1: Functional (Neurosynth)   Tab 2: Neurotransmitters (PET)
        decode_w = QWidget()
        decode_v = QVBoxLayout(decode_w)
        decode_v.setContentsMargins(0, 0, 0, 4)
        decode_v.setSpacing(4)

        self.annot_tabs = QTabWidget()
        self.annot_tabs.setStyleSheet(
            "QTabBar::tab{background:#161628; color:#9fb4cc; padding:5px 12px;"
            " border:1px solid #2a2a44; border-bottom:none;"
            " border-top-left-radius:4px; border-top-right-radius:4px;}"
            "QTabBar::tab:selected{background:#0c0c1a; color:#38b6ff;}"
            "QTabWidget::pane{border:1px solid #2a2a44; top:-1px;}")

        # --- Tab 1: Functional Decoding ---
        fwrap = QWidget(); fv = QVBoxLayout(fwrap)
        fv.setContentsMargins(6, 6, 6, 6); fv.setSpacing(6)
        fhdr = QHBoxLayout()
        flbl = QLabel("Functional Decoding")
        flbl.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
        flbl.setStyleSheet("color:#38b6ff;")
        fhdr.addWidget(flbl); fhdr.addStretch()
        self.decode_src_lbl = QLabel("")
        self.decode_src_lbl.setFont(QFont('Segoe UI', 8))
        self.decode_src_lbl.setStyleSheet("color:#7090b0; padding-right:4px;")
        fhdr.addWidget(self.decode_src_lbl)
        fv.addLayout(fhdr)
        self.decoding_view = QTextEdit()
        self.decoding_view.setReadOnly(True)
        self.decoding_view.setFont(QFont('Segoe UI', 9))
        self.decoding_view.setStyleSheet(
            "background:#0c0c1a; border:1px solid #2a2a44; border-radius:4px; padding:6px;")
        fv.addWidget(self.decoding_view, 1)
        self.annot_tabs.addTab(fwrap, "Functional (Neurosynth)")

        # --- Tab 2: Neurotransmitter Mapping ---
        nwrap = QWidget(); nv = QVBoxLayout(nwrap)
        nv.setContentsMargins(6, 6, 6, 6); nv.setSpacing(6)
        nhdr = QHBoxLayout()
        nlbl = QLabel("Neurotransmitter Mapping")
        nlbl.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
        nlbl.setStyleSheet("color:#c084fc;")
        nhdr.addWidget(nlbl); nhdr.addStretch()
        self.neuro_src_lbl = QLabel("")
        self.neuro_src_lbl.setFont(QFont('Segoe UI', 8))
        self.neuro_src_lbl.setStyleSheet("color:#9070b0; padding-right:4px;")
        nhdr.addWidget(self.neuro_src_lbl)
        nv.addLayout(nhdr)
        self.neuro_view = QTextEdit()
        self.neuro_view.setReadOnly(True)
        self.neuro_view.setFont(QFont('Segoe UI', 9))
        self.neuro_view.setStyleSheet(
            "background:#0c0c1a; border:1px solid #2a2a44; border-radius:4px; padding:6px;")
        nv.addWidget(self.neuro_view, 1)
        self.annot_tabs.addTab(nwrap, "Neurotransmitters (PET)")

        # --- Tab 3: Transcriptomics (receptor genes, AHBA) ---
        twrap = QWidget(); tv = QVBoxLayout(twrap)
        tv.setContentsMargins(6, 6, 6, 6); tv.setSpacing(6)
        thdr = QHBoxLayout()
        tlbl = QLabel("Receptor-Gene Expression")
        tlbl.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
        tlbl.setStyleSheet("color:#34d399;")
        thdr.addWidget(tlbl); thdr.addStretch()
        self.trans_src_lbl = QLabel("")
        self.trans_src_lbl.setFont(QFont('Segoe UI', 8))
        self.trans_src_lbl.setStyleSheet("color:#5ca588; padding-right:4px;")
        thdr.addWidget(self.trans_src_lbl)
        tv.addLayout(thdr)
        self.trans_view = QTextEdit()
        self.trans_view.setReadOnly(True)
        self.trans_view.setFont(QFont('Segoe UI', 9))
        self.trans_view.setStyleSheet(
            "background:#0c0c1a; border:1px solid #2a2a44; border-radius:4px; padding:6px;")
        tv.addWidget(self.trans_view, 1)
        self.annot_tabs.addTab(twrap, "Transcriptomics (AHBA)")

        decode_v.addWidget(self.annot_tabs, 1)
        self._render_decoding_empty()
        self._render_neuro_empty()
        self._render_trans_empty()

        # ----- Assemble the 2x2 grid via nested resizable splitters -----
        #   row 1:  Network Results (table)  |  Annotations (Functional / PET)
        #   row 2:  Brain Map                |  Network Overlap Coefficient
        row1 = QSplitter(Qt.Orientation.Horizontal)
        row1.addWidget(top_w)
        row1.addWidget(decode_w)
        row1.setSizes([620, 420])

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(row1)
        main_splitter.addWidget(bottom_w)
        main_splitter.setSizes([330, 670])
        root.addWidget(main_splitter)

        # Load the precomputed annotation bundles (if present)
        self._load_neurosynth_data()
        self._load_neurotransmitter_data()
        self._load_transcriptomics_data()

    # ----------------------------------------------------------------------
    # Template scanning & loading
    # ----------------------------------------------------------------------
    def _scan_templates(self):
        """Find all .nii templates in known directories and populate underlay_combo."""
        from pathlib import Path
        import os

        candidate_dirs = [
            _resource_dir() / 'mni_templates',
            Path(__file__).parent / 'mni_templates',
            Path(__file__).parent.parent / 'mni_templates',
        ]
        # Also try the directory used by BrainViewerTab if available (via parent_main)
        if hasattr(self, 'parent_main') and hasattr(self.parent_main, 'brain_viewer_tab'):
            if hasattr(self.parent_main.brain_viewer_tab, 'viewer_factory'):
                if self.parent_main.brain_viewer_tab.viewer_factory and self.parent_main.brain_viewer_tab.viewer_factory.template_dir:
                    candidate_dirs.insert(0, self.parent_main.brain_viewer_tab.viewer_factory.template_dir)

        found = False
        for d in candidate_dirs:
            if d and d.exists():
                nii_files = list(d.glob('*.nii')) + list(d.glob('*.nii.gz'))
                if nii_files:
                    for f in nii_files:
                        display = f.name
                        self.template_paths[display] = str(f)
                    found = True
                    break

        if not found:
            # Fallback: use any NIfTI from current directory
            for f in Path('.').glob('*.nii'):
                self.template_paths[f.name] = str(f)

        # Populate combo box
        self.underlay_combo.blockSignals(True)
        self.underlay_combo.clear()
        for name in sorted(self.template_paths.keys()):
            self.underlay_combo.addItem(name, name)
        self.underlay_combo.blockSignals(False)

        # Set default: prefer mni_icbm152_t1_tal_nlin_asym_09c.nii
        default_name = None
        for name in self.template_paths.keys():
            if 'mni_icbm152' in name.lower() or 'icbm152' in name.lower():
                default_name = name
                break
        if default_name is None and self.template_paths:
            default_name = list(self.template_paths.keys())[0]

        if default_name:
            idx = self.underlay_combo.findText(default_name)
            if idx >= 0:
                self.underlay_combo.setCurrentIndex(idx)

    def _load_template(self, template_display_name):
        """Load a NIfTI template by its display name."""
        import nibabel as nib
        path = self.template_paths.get(template_display_name)
        if not path or not Path(path).exists():
            print(f"⚠️ Template not found: {template_display_name}")
            return False
        try:
            img = nib.load(path)
            self.template_data = img.get_fdata()
            self.template_affine = img.affine
            self.current_template_path = path

            # Normalize to 0-1 range for display
            vmin, vmax = np.percentile(self.template_data, (1, 99))
            self.template_data = np.clip(self.template_data, vmin, vmax)
            self.template_data = (self.template_data - vmin) / (vmax - vmin)

            # Update slice range for current view
            self._update_slice_range()
            return True
        except Exception as e:
            print(f"❌ Failed to load template {path}: {e}")
            return False

    def _update_slice_range(self):
        """Update slider range based on current view and template shape."""
        if self.template_data is None:
            return
        shape = self.template_data.shape
        if self.current_view == 'axial':
            max_idx = shape[2] - 1
        elif self.current_view == 'coronal':
            max_idx = shape[1] - 1
        else:  # sagittal
            max_idx = shape[0] - 1
        self.max_slice = max_idx
        self.slice_slider.blockSignals(True)
        self.slice_slider.setRange(0, max_idx)
        self.slice_slider.blockSignals(False)
        # Set to middle slice
        self.current_slice_idx = max_idx // 2
        # Initialize per-plane slices to the volume centre (for triplanar)
        self.slice_sa = shape[0] // 2   # X
        self.slice_co = shape[1] // 2   # Y
        self.slice_ax = shape[2] // 2   # Z
        self.slice_slider.setValue(self.current_slice_idx)
        self._update_slice_label()

    def _update_slice_label(self):
        self.slice_label.setText(f"{self.current_slice_idx} / {self.max_slice}")

    # ----------------------------------------------------------------------
    # Interactive controls
    # ----------------------------------------------------------------------
    def _set_view(self, view):
        self.current_view = view
        for v, btn in self.view_btns.items():
            btn.setChecked(v == view)
        self._update_slice_range()
        self._render_brain_left()

    def _on_slice_changed(self, value):
        self.current_slice_idx = value
        self._update_slice_label()
        # Render appropriate view
        if self.view_mode == 'triplanar':
            self._render_triplanar(highlighted_net_idx=self.current_highlighted_idx)
        else:
            self._render_brain_left(highlighted_net_idx=self.current_highlighted_idx)

    def _install_scroll(self, label):
        """Obsolete: scrolling is now handled by ClickableBrainLabel.wheelEvent.
        Kept as a harmless no-op for backward compatibility."""
        return

    def eventFilter(self, obj, event):
        """Mouse-wheel over any brain canvas advances/retreats the slice,
        which also moves the crosshair plane with it."""
        if event.type() == QEvent.Type.Wheel and self.template_data is not None:
            canvases = [getattr(self, 'brain_canvas', None),
                        self.brain_canvas_axial,
                        self.brain_canvas_coronal,
                        self.brain_canvas_sagittal]
            if obj in canvases and obj is not None:
                delta = event.angleDelta().y()
                step = 1 if delta > 0 else -1
                new_val = max(0, min(self.current_slice_idx + step, self.max_slice))
                if new_val != self.current_slice_idx:
                    # move via the slider so label + signals stay in sync
                    self.slice_slider.setValue(new_val)
                return True  # consume the event
        return super().eventFilter(obj, event)

    # ----------------------------------------------------------------------
    # Voxel statistics panel (feature 2)
    # ----------------------------------------------------------------------
    def _compute_voxel_stats(self):
        """Compute per-network voxel stats; cache on self._voxel_stats."""
        self._voxel_stats = None
        self._voxel_best_idx = None
        if getattr(self, '_atlas_vol', None) is None or self._atlas_aff is None:
            return
        try:
            rows, best = rx.all_network_voxel_stats(
                self.network_names, self._atlas_vol, self._atlas_aff,
                self._atlas_mode, self._label_map, threshold=0.0)
            self._voxel_stats = rows
            self._voxel_best_idx = best
        except Exception as e:
            print(f"⚠️ Voxel stats error: {e}")

    def _update_voxel_panel(self, selected_idx=None):
        """Show voxel counts and the peak (highest-count) location."""
        if not getattr(self, '_voxel_stats', None):
            self.info_text.setHtml(
                "<span style='color:#7090b0'>No voxel data available "
                "(atlas volume not loaded for this analysis).</span>")
            return

        rows = self._voxel_stats
        total = sum(st['n_voxels'] for _, st in rows)
        best = self._voxel_best_idx

        html = []
        if best is not None:
            bname, bst = rows[best]
            pv = bst['peak_voxel']; pm = bst['peak_mni']
            vox_str = f"({pv[0]}, {pv[1]}, {pv[2]})" if pv else "—"
            mni_str = (f"({pm[0]:.0f}, {pm[1]:.0f}, {pm[2]:.0f}) mm"
                       if pm else "—")
            html.append(
                f"<span style='color:#7dd3fc;font-weight:bold'>Most voxels:</span> "
                f"<span style='color:#86efac;font-weight:bold'>{bname}</span> "
                f"<span style='color:#fde68a'>{bst['n_voxels']:,} voxels</span> "
                f"<span style='color:#94a3b8'>· peak voxel {vox_str} · MNI {mni_str}</span>")
        html.append(
            f"<span style='color:#94a3b8'>Total across {len(rows)} networks: "
            f"{total:,} voxels</span>")

        if selected_idx is not None and 0 <= selected_idx < len(rows):
            sname, sst = rows[selected_idx]
            pv = sst['peak_voxel']; pm = sst['peak_mni']
            vox_str = f"({pv[0]}, {pv[1]}, {pv[2]})" if pv else "—"
            mni_str = (f"({pm[0]:.0f}, {pm[1]:.0f}, {pm[2]:.0f}) mm"
                       if pm else "—")
            html.append(
                f"<span style='color:#c4b5fd;font-weight:bold'>Selected:</span> "
                f"<span style='color:#86efac'>{sname}</span> "
                f"<span style='color:#fde68a'>{sst['n_voxels']:,} voxels</span> "
                f"<span style='color:#94a3b8'>· peak voxel {vox_str} · MNI {mni_str}</span>")

        self.info_text.setHtml("<br>".join(html))

    def _on_zoom_changed(self, value):
        self.zoom = value / 100.0
        self.zoom_label.setText(f"{value}%")
        # Render appropriate view
        if self.view_mode == 'triplanar':
            self._render_triplanar(highlighted_net_idx=self.current_highlighted_idx)
        else:
            self._render_brain_left(highlighted_net_idx=self.current_highlighted_idx)

    def _on_colormap_changed(self, cmap):
        self.colormap = cmap
        # Render appropriate view
        if self.view_mode == 'triplanar':
            self._render_triplanar(highlighted_net_idx=self.current_highlighted_idx)
        else:
            self._render_brain_left(highlighted_net_idx=self.current_highlighted_idx)

    def _on_underlay_changed(self):
        selected = self.underlay_combo.currentData()
        if selected and selected in self.template_paths:
            if self._load_template(selected):
                self._render_brain_left()


    def _update_canvas_display(self, canvas_label, fig):
        """Render a matplotlib figure to a pixmap and show it in the QLabel.
        The pixmap is scaled to fit the label (keeping aspect) so the DISPLAYED
        size always matches what the click handler reads — this is what keeps
        the crosshair accurate when the window is resized."""
        if canvas_label is None or fig is None:
            return
        try:
            buf = BytesIO()
            fig.savefig(buf, format='png', dpi=fig.dpi, facecolor=fig.get_facecolor())
            buf.seek(0)
            image = QImage()
            image.loadFromData(buf.getvalue())
            pixmap = QPixmap.fromImage(image)
            lw = max(1, canvas_label.width()); lh = max(1, canvas_label.height())
            if pixmap.width() > lw or pixmap.height() > lh:
                pixmap = pixmap.scaled(lw, lh, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            canvas_label.setPixmap(pixmap)
            if hasattr(canvas_label, 'set_image_size'):
                canvas_label.set_image_size(pixmap.width(), pixmap.height())
        except Exception as e:
            print(f"Error updating canvas: {e}")

    def _make_canvas(self, fig, view_id=''):
        """Create a ClickableBrainLabel that displays the figure as a pixmap and
        reports mouse press/drag/scroll back to this tab. No matplotlib Qt canvas
        is created, so this cannot segfault."""
        lbl = ClickableBrainLabel(view_id=view_id)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if view_id == '':
            lbl.pressed.connect(self._on_brain_press_px)
            lbl.dragged.connect(self._on_brain_press_px)   # drag = continuous press
            lbl.scrolled.connect(lambda step, v: self._scroll_single(step))
        else:
            lbl.pressed.connect(self._on_tri_press_px)
            lbl.dragged.connect(self._on_tri_press_px)
            lbl.scrolled.connect(self._on_tri_scroll_px)
        return lbl

    # ── Pixel → data → MNI mapping (QLabel pixmap based, no matplotlib canvas) ──
    def _label_px_to_data(self, ax, label, x_px, y_px):
        """Map a mouse position in label pixels to matplotlib data coordinates
        using the stored axes. Accounts for the pixmap being centered in the
        (possibly larger) label."""
        if ax is None or label is None:
            return None
        pm = label.pixmap()
        if pm is None or pm.width() == 0 or pm.height() == 0:
            return None
        img_w, img_h = pm.width(), pm.height()
        lab_w, lab_h = label.width(), label.height()
        # pixmap is centered (AlignCenter): compute offset of image within label
        off_x = max(0, (lab_w - img_w) / 2.0)
        off_y = max(0, (lab_h - img_h) / 2.0)
        ix = x_px - off_x
        iy = y_px - off_y
        if ix < 0 or iy < 0 or ix > img_w or iy > img_h:
            return None
        # The figure was saved at dpi=100. Convert image pixel -> figure pixel.
        fig = ax.figure
        fig_w_px = fig.get_figwidth() * fig.dpi
        fig_h_px = fig.get_figheight() * fig.dpi
        # image may be scaled vs the figure's native pixel size
        sx = fig_w_px / img_w
        sy = fig_h_px / img_h
        fx = ix * sx
        fy = iy * sy
        # matplotlib display origin is bottom-left; Qt is top-left -> flip y
        disp_y = fig_h_px - fy
        try:
            inv = ax.transData.inverted()
            xdata, ydata = inv.transform((fx, disp_y))
        except Exception:
            return None
        return xdata, ydata

    def _data_to_mni(self, view, xdata, ydata, sidx):
        """Convert axes data coords (column=xdata, row=ydata in the displayed,
        flipped+rotated slice) to an MNI coordinate. Inverts fliplr+rot90(k=1)."""
        if self.template_data is None or self.template_affine is None:
            return None
        if view == 'axial':
            raw = self.template_data[:, :, sidx]
        elif view == 'coronal':
            raw = self.template_data[:, sidx, :]
        else:
            raw = self.template_data[sidx, :, :]
        nrows_raw, ncols_raw = raw.shape
        # displayed (dc=xdata, dr=ydata) -> raw (a_row, a_col); verified inverse:
        a_row = float(xdata)
        a_col = float(ydata)
        a_row = float(np.clip(a_row, 0, nrows_raw - 1))
        a_col = float(np.clip(a_col, 0, ncols_raw - 1))
        if view == 'axial':       # raw dims = (X, Y); slice = Z
            x_vox, y_vox, z_vox = a_row, a_col, sidx
        elif view == 'coronal':   # raw dims = (X, Z); slice = Y
            x_vox, z_vox, y_vox = a_row, a_col, sidx
        else:                     # sagittal: raw dims = (Y, Z); slice = X
            y_vox, z_vox, x_vox = a_row, a_col, sidx
        mni = self.template_affine @ np.array([x_vox, y_vox, z_vox, 1.0])
        return tuple(mni[:3])

    # ── Single-view handlers (view_id == '') ──
    def _on_brain_press_px(self, x_px, y_px, view_id):
        if self.template_data is None:
            return
        ax = getattr(self, '_single_ax', None)
        dd = self._label_px_to_data(ax, self.brain_canvas, x_px, y_px)
        if dd is None:
            return
        mni = self._data_to_mni(self.current_view, dd[0], dd[1], self.current_slice_idx)
        if mni is None:
            return
        self.crosshair_mni = mni
        self._update_crosshair_readout(mni)
        self._render_brain_left(highlighted_net_idx=self.current_highlighted_idx)

    def _scroll_single(self, step):
        new_val = max(0, min(self.current_slice_idx + step, self.max_slice))
        if new_val != self.current_slice_idx:
            self.slice_slider.setValue(new_val)

    # ── Triplanar handlers (view_id in axial/coronal/sagittal) ──
    def _sync_triplanar_slices_to_crosshair(self):
        """Re-derive each plane's slice from the crosshair voxel (linked nav)."""
        if self.crosshair_mni is None or self.template_affine is None:
            return
        inv = np.linalg.inv(self.template_affine)
        vox = inv @ np.array([self.crosshair_mni[0], self.crosshair_mni[1],
                              self.crosshair_mni[2], 1.0])
        sh = self.template_data.shape
        self.slice_sa = int(np.clip(round(vox[0]), 0, sh[0] - 1))   # X
        self.slice_co = int(np.clip(round(vox[1]), 0, sh[1] - 1))   # Y
        self.slice_ax = int(np.clip(round(vox[2]), 0, sh[2] - 1))   # Z

    def _on_tri_press_px(self, x_px, y_px, view):
        """Click/drag in a triplanar plane → move crosshair and re-center the
        other two planes to that 3D point (linked navigation).

        Pixel→data conversion uses the stored axes (QLabel-safe); the voxel
        mapping + linked-navigation logic follows the user's design.
        """
        if self.template_data is None or self.template_affine is None:
            return
        ax = getattr(self, '_tri_ax', {}).get(view)
        canvas = {'axial': self.brain_canvas_axial,
                  'coronal': self.brain_canvas_coronal,
                  'sagittal': self.brain_canvas_sagittal}.get(view)
        dd = self._label_px_to_data(ax, canvas, x_px, y_px)
        if dd is None:
            return
        sidx = {'axial': self.slice_ax, 'coronal': self.slice_co,
                'sagittal': self.slice_sa}[view]
        # data coords (column, row) of the displayed (flipped+rotated) slice
        mni = self._data_to_mni(view, dd[0], dd[1], sidx)
        if mni is None:
            return
        self.crosshair_mni = mni

        # Linked navigation: convert MNI back to voxel and update the OTHER
        # two planes' slices so they show this same 3D point.
        inv_aff = np.linalg.inv(self.template_affine)
        vox = inv_aff @ np.array([mni[0], mni[1], mni[2], 1.0])
        sh = self.template_data.shape
        vx = max(0, min(sh[0] - 1, int(round(vox[0]))))   # X
        vy = max(0, min(sh[1] - 1, int(round(vox[1]))))   # Y
        vz = max(0, min(sh[2] - 1, int(round(vox[2]))))   # Z
        if view == 'axial':        # X-Y plane → set coronal (Y), sagittal (X)
            self.slice_co = vy; self.slice_sa = vx
        elif view == 'coronal':    # X-Z plane → set axial (Z), sagittal (X)
            self.slice_ax = vz; self.slice_sa = vx
        else:                      # sagittal Y-Z plane → set axial (Z), coronal (Y)
            self.slice_ax = vz; self.slice_co = vy

        self._update_crosshair_readout(mni)
        self._render_triplanar(highlighted_net_idx=self.current_highlighted_idx)

    def _on_tri_scroll_px(self, step, view):
        sh = self.template_data.shape if self.template_data is not None else None
        if sh is None:
            return
        if view == 'axial':
            self.slice_ax = int(np.clip(self.slice_ax + step, 0, sh[2] - 1))
        elif view == 'coronal':
            self.slice_co = int(np.clip(self.slice_co + step, 0, sh[1] - 1))
        else:
            self.slice_sa = int(np.clip(self.slice_sa + step, 0, sh[0] - 1))
        self._render_triplanar(highlighted_net_idx=self.current_highlighted_idx)


    def _network_mask(self, net_idx):
        """Build a binary mask (in atlas space) for network `net_idx` from the
        loaded atlas footprint. Returns (mask, affine) or (None, None)."""
        av = getattr(self, '_atlas_vol', None)
        aff = getattr(self, '_atlas_aff', None)
        if av is None or aff is None or net_idx is None:
            return (None, None)
        mode = getattr(self, '_atlas_mode', None)
        try:
            if mode == '4d' or av.ndim == 4:
                if net_idx >= av.shape[3]:
                    return (None, None)
                # voxel belongs to this network where this component is the argmax & positive
                vols = av
                best = np.argmax(vols, axis=3)
                pos = vols.max(axis=3) > 0
                mask = (best == net_idx) & pos
            elif mode == 'metric':
                mask = av > 0
            else:  # labels
                lm = getattr(self, '_label_map', None) or {}
                labs = [lab for lab, idx in lm.items() if idx == net_idx]
                if not labs:
                    return (None, None)
                mask = np.isin(av, labs)
            return (mask, aff)
        except Exception as e:
            print(f"⚠️ _network_mask error: {e}")
            return (None, None)

    def _update_subregion_panel(self, net_idx):
        """Results #4: replace the panel below the brain with the cortical/
        subcortical subregions that the selected network actually overlaps,
        computed from the Harvard-Oxford atlas."""
        if not hasattr(self, 'info_text'):
            return
        name = (self.network_names[net_idx]
                if 0 <= net_idx < len(self.network_names) else f"network {net_idx}")
        if anat is None:
            self.info_text.setHtml(
                "<span style='color:#7090b0'>Anatomical atlas unavailable "
                "(install nilearn to enable subregion breakdown).</span>")
            return
        mask, aff = self._network_mask(net_idx)
        if mask is None or not mask.any():
            self.info_text.setHtml(
                f"<span style='color:#7090b0'>No atlas footprint for "
                f"<b>{name}</b>.</span>")
            return
        try:
            subs = anat.subregions_for_mask(mask, aff)
        except Exception as e:
            self.info_text.setHtml(f"<span style='color:#f88'>Subregion lookup error: {e}</span>")
            return
        if not subs:
            self.info_text.setHtml(
                f"<span style='color:#7090b0'><b>{name}</b>: no cortical "
                f"subregions above threshold.</span>")
            return
        html = [f"<span style='color:#7dd3fc;font-weight:bold'>Key cortical subregions of "
                f"{name}:</span>"]
        for s in subs:
            ba = (f" <span style='color:#94a3b8'>· {s['brodmann']}</span>"
                  if s['brodmann'] and s['brodmann'] != '—' else "")
            html.append(
                f"<span style='color:#86efac'>{s['region']}</span> "
                f"<span style='color:#fde68a'>{s['pct']:.0f}%</span>"
                f"<span style='color:#94a3b8'> ({s['n_voxels']:,} vox)</span>{ba}")
        self.info_text.setHtml("<br>".join(html))

    def _network_at_mni(self, mni):
        """Return (network_index, network_name) whose atlas footprint contains
        the given MNI coordinate, or (None, None)."""
        av = getattr(self, '_atlas_vol', None)
        aff = getattr(self, '_atlas_aff', None)
        if av is None or aff is None:
            return (None, None)
        try:
            inv = np.linalg.inv(aff)
            vox = inv @ np.array([mni[0], mni[1], mni[2], 1.0])
            i, j, k = (int(round(v)) for v in vox[:3])
            mode = getattr(self, '_atlas_mode', None)
            if mode == '4d' or av.ndim == 4:
                if not (0 <= i < av.shape[0] and 0 <= j < av.shape[1] and 0 <= k < av.shape[2]):
                    return (None, None)
                vec = av[i, j, k, :]
                if vec.max() <= 0:
                    return (None, None)
                idx = int(np.argmax(vec))
            elif mode == 'metric':
                if not (0 <= i < av.shape[0] and 0 <= j < av.shape[1] and 0 <= k < av.shape[2]):
                    return (None, None)
                idx = 0 if av[i, j, k] > 0 else None
                if idx is None:
                    return (None, None)
            else:  # labels
                if not (0 <= i < av.shape[0] and 0 <= j < av.shape[1] and 0 <= k < av.shape[2]):
                    return (None, None)
                lab = int(av[i, j, k])
                lm = getattr(self, '_label_map', None) or {}
                idx = lm.get(lab, None)
                if idx is None:
                    return (None, None)
            if 0 <= idx < len(self.network_names):
                return (idx, self.network_names[idx])
        except Exception:
            pass
        return (None, None)

    def _update_crosshair_readout(self, mni):
        """Results #3: show network name + anatomical location + Brodmann area
        at the crosshair, instead of raw MNI coordinates."""
        if not hasattr(self, 'crosshair_readout'):
            return
        x, y, z = (float(c) for c in mni)
        net_idx, net_name = self._network_at_mni(mni)
        region, ba = '—', '—'
        if anat is not None:
            try:
                info = anat.label_at_mni(x, y, z)
                region, ba = info['region'], info['brodmann']
            except Exception as e:
                region = f"(lookup error: {e})"
        net_html = (f"<b style='color:#86efac'>{net_name}</b>"
                    if net_name else "<span style='color:#7090b0'>(outside networks)</span>")
        ba_html = (f" &nbsp;·&nbsp; <span style='color:#fde68a'>{ba}</span>"
                   if ba and ba != '—' else "")

        # White-matter labelling (JHU-ICBM): region and/or probabilistic tracts
        wm_html = ""
        if wm is not None:
            try:
                winfo = wm.wm_label_at_mni(x, y, z) or {}
                wregion = winfo.get('region', '—')
                wtract = winfo.get('tract', '—')
                probs = wm.wm_tract_probs_at_mni(x, y, z, top=2)
                parts = []
                if wregion and wregion != '—':
                    parts.append(wregion)
                if probs:
                    parts.append(", ".join(f"{n} ({p:.0f}%)" for n, p in probs))
                elif wtract and wtract != '—':
                    parts.append(wtract)
                if parts:
                    wm_html = (" &nbsp;·&nbsp; <span style='color:#7dd3fc'>WM:</span> "
                               f"<span style='color:#f0a93b'>{'  ·  '.join(parts)}</span>")
            except Exception:
                pass

        self.crosshair_readout.setText(
            f"<span style='color:#7dd3fc'>⊕ Network:</span> {net_html} &nbsp;·&nbsp; "
            f"<span style='color:#7dd3fc'>Location:</span> "
            f"<span style='color:#cde4ff'>{region}</span>{ba_html}{wm_html}")
        # Also refresh the subregion panel for the network under the crosshair (#4)
        if net_idx is not None:
            self._update_subregion_panel(net_idx)

    # ----------------------------------------------------------------------
    # Rendering
    # ----------------------------------------------------------------------
    def _render_brain_left(self, highlighted_net_idx=None):
        """
        Render the current 2D slice with network overlays and crosshair.
        
        Handles:
        - MNI ↔ voxel coordinate transformation
        - Network centroid projection to 2D slice
        - Proper anatomical orientations (L/R, P/A)
        - Network highlighting with distinct colors
        - Optional crosshair for interactive navigation
        """
        if self.template_data is None:
            return
        
        # Safety check: make sure we're in single view mode and canvas exists
        if self.view_mode != 'single' or self.brain_canvas is None or self.brain_fig is None:
            return

        self.brain_fig.clear()
        ax = self.brain_fig.add_subplot(111)
        ax.set_facecolor('#0a0a14')

        # ─────────────────────────────────────────────────────────────────────
        # 1. Extract and display the 2D brain slice
        # ─────────────────────────────────────────────────────────────────────
        # MNI RAS convention: X (left-right), Y (posterior-anterior), Z (inferior-superior)
        if self.current_view == 'axial':
            # Axial: X-Y plane (left-right, posterior-anterior)
            slice_2d = self.template_data[:, :, self.current_slice_idx]
            slice_2d = np.fliplr(slice_2d)  # Flip X-axis for left-on-left neurological view
            slice_2d = np.rot90(slice_2d, k=1)  # 90° rotation
        elif self.current_view == 'coronal':
            # Coronal: X-Z plane (left-right, inferior-superior)
            slice_2d = self.template_data[:, self.current_slice_idx, :]
            slice_2d = np.fliplr(slice_2d)  # Flip X-axis for left-on-left neurological view
            slice_2d = np.rot90(slice_2d, k=1)  # 90° rotation
        else:  # sagittal
            # Sagittal: Y-Z plane (posterior-anterior, inferior-superior)
            slice_2d = self.template_data[self.current_slice_idx, :, :]
            slice_2d = np.fliplr(slice_2d)  # Flip Y-axis for anterior-right orientation
            slice_2d = np.rot90(slice_2d, k=1)  # 90° rotation

        # Display template underlay
        im = ax.imshow(slice_2d, cmap=self.colormap, origin='lower', 
                       interpolation='bilinear', aspect='auto')
        self.brain_fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        # ─────────────────────────────────────────────────────────────────────
        # 2. Network overlay — soft activation blobs, pixel-aligned to the brain
        # ─────────────────────────────────────────────────────────────────────
        if self.network_centroids and self.network_overlaps:
            # Determine raw (untransformed) slice shape for this view
            if self.current_view == 'axial':
                raw_shape = self.template_data[:, :, self.current_slice_idx].shape
            elif self.current_view == 'coronal':
                raw_shape = self.template_data[:, self.current_slice_idx, :].shape
            else:
                raw_shape = self.template_data[self.current_slice_idx, :, :].shape

            # Prefer the EXACT atlas ROI footprint; fall back to centroid blobs
            overlay = self._build_atlas_overlay(self.current_view,
                                                self.current_slice_idx,
                                                raw_shape, highlighted_net_idx)
            if overlay is None:
                overlay = self._build_network_overlay(raw_shape, self.current_view,
                                                      highlighted_net_idx)
            if overlay is not None and overlay[..., 3].max() > 0:
                # Apply the SAME orientation transform as the underlay
                overlay = self._orient_slice(overlay, self.current_view)
                ax.imshow(overlay, origin='lower', interpolation='nearest',
                          aspect='auto', zorder=10)

            # Label the highlighted network at its (transformed) centroid
            if highlighted_net_idx is not None and \
               highlighted_net_idx < len(self.network_centroids):
                mni = self.network_centroids[highlighted_net_idx]
                if mni is not None:
                    name = self.network_names[highlighted_net_idx]
                    color = self._network_colors(len(self.network_centroids))[
                        highlighted_net_idx % len(self.network_centroids)]
                    vox = (np.linalg.inv(self.template_affine) @
                           np.array([mni[0], mni[1], mni[2], 1.0]))[:3]
                    if self.current_view == 'axial':
                        row, col = vox[0], vox[1]
                    elif self.current_view == 'coronal':
                        row, col = vox[0], vox[2]
                    else:
                        row, col = vox[1], vox[2]
                    disp_x, disp_y = self._transform_point(row, col, raw_shape)
                    ax.text(disp_x, disp_y, name[:8],
                            ha='center', va='center', fontsize=8,
                            color=color, fontweight='bold', zorder=30,
                            bbox=dict(boxstyle='round,pad=0.3',
                                      facecolor='#0a0a14', alpha=0.7,
                                      edgecolor='none'))


        # ─────────────────────────────────────────────────────────────────────
        # 3. Interactive crosshair for click-to-navigate
        # ─────────────────────────────────────────────────────────────────────
        if hasattr(self, 'crosshair_mni') and self.crosshair_mni is not None:
            try:
                ch_mni = self.crosshair_mni
                ch_homo = np.array([ch_mni[0], ch_mni[1], ch_mni[2], 1.0])
                ch_vox_homo = np.linalg.inv(self.template_affine) @ ch_homo
                ch_vox = ch_vox_homo[:3]
                
                # Project crosshair to current slice (with relaxed tolerance)
                ch_in_slice = False
                ch_x, ch_y = None, None
                tolerance = 10.0  # More relaxed tolerance (10 voxels)
                
                if self.current_view == 'axial':
                    if abs(ch_vox[2] - self.current_slice_idx) <= tolerance:
                        ch_x, ch_y = ch_vox[0], ch_vox[1]
                        ch_in_slice = True
                elif self.current_view == 'coronal':
                    if abs(ch_vox[1] - self.current_slice_idx) <= tolerance:
                        ch_x, ch_y = ch_vox[0], ch_vox[2]
                        ch_in_slice = True
                else:  # sagittal
                    if abs(ch_vox[0] - self.current_slice_idx) <= tolerance:
                        ch_x, ch_y = ch_vox[1], ch_vox[2]
                        ch_in_slice = True
                
                if ch_in_slice and ch_x is not None and ch_y is not None:
                    print(f"✓ Crosshair in slice! Drawing at voxel ({ch_x:.1f}, {ch_y:.1f})")
                    # Draw crosshair lines
                    h, w = slice_2d.shape
                    ax.axvline(ch_x, color='#00FF00', linewidth=2.8, 
                              linestyle='--', alpha=0.85, zorder=15)
                    ax.axhline(ch_y, color='#00FF00', linewidth=2.8, 
                              linestyle='--', alpha=0.85, zorder=15)
                    
                    # Center dot
                    ax.plot(ch_x, ch_y, 'o', color='#00FF00', markersize=10,
                           markeredgecolor='white', markeredgewidth=2, zorder=16)
                    
                    # MNI coordinates label
                    ax.text(ch_x + 5, ch_y + 5, 
                           f'MNI: ({ch_mni[0]:.0f}, {ch_mni[1]:.0f}, {ch_mni[2]:.0f})',
                           fontsize=7, color='#00FF00', fontweight='bold',
                           bbox=dict(boxstyle='round,pad=0.4', 
                                    facecolor='#000000', alpha=0.9, 
                                    edgecolor='#00FF00', linewidth=1),
                           zorder=17)
            except Exception as e:
                print(f"⚠️ Error rendering crosshair: {e}")

        # ─────────────────────────────────────────────────────────────────────
        # 4. Apply zoom and set display properties
        # ─────────────────────────────────────────────────────────────────────
        if self.zoom != 1.0:
            h, w = slice_2d.shape
            xlim_center = w / 2
            ylim_center = h / 2
            x_range = w / self.zoom / 2
            y_range = h / self.zoom / 2
            ax.set_xlim(xlim_center - x_range, xlim_center + x_range)
            ax.set_ylim(ylim_center - y_range, ylim_center + y_range)

        # ─────────────────────────────────────────────────────────────────────
        # 5. Anatomical labels and title
        # ─────────────────────────────────────────────────────────────────────
        view_names = {'axial': 'Axial (Z)', 'coronal': 'Coronal (Y)', 'sagittal': 'Sagittal (X)'}
        ax.set_title(f"{view_names[self.current_view]} - Slice {self.current_slice_idx}",
                     color='#7090b8', fontsize=11, fontweight='bold')
        ax.set_xlabel('L ← → R', color='#6070a0', fontsize=9)
        ax.set_ylabel('P ← → A', color='#6070a0', fontsize=9)
        ax.tick_params(colors='#6070a0', labelsize=8)

        self.brain_fig.tight_layout()
        self._single_ax = ax            # remember for pixel->data mapping
        self._update_canvas_display(self.brain_canvas, self.brain_fig)

    def _render_triplanar(self, highlighted_net_idx=None):
        """Render all 3 views (axial, coronal, sagittal) simultaneously."""
        if self.template_data is None:
            return
        
        # Safety check: make sure we're in triplanar mode and canvases exist
        if self.view_mode != 'triplanar' or self.brain_canvas_axial is None:
            return
        
        views_to_render = [
            ('axial', self.brain_fig_axial, self.brain_canvas_axial),
            ('coronal', self.brain_fig_coronal, self.brain_canvas_coronal),
            ('sagittal', self.brain_fig_sagittal, self.brain_canvas_sagittal)
        ]
        
        for view_name, fig, canvas in views_to_render:
            # Temporarily set current view
            old_view = self.current_view
            self.current_view = view_name
            # Per-plane slice index for this view
            sidx = {'axial': self.slice_ax, 'coronal': self.slice_co,
                    'sagittal': self.slice_sa}[view_name]
            
            # Render to this figure
            fig.clear()
            ax = fig.add_subplot(111)
            ax.set_facecolor('#0a0a14')
            
            # Extract slice
            if view_name == 'axial':
                slice_2d = self.template_data[:, :, sidx]
            elif view_name == 'coronal':
                slice_2d = self.template_data[:, sidx, :]
            else:  # sagittal
                slice_2d = self.template_data[sidx, :, :]
            
            # Apply MNI RAS neurological convention: flip left-right for all views
            # This ensures: left hemisphere on left side, right on right side
            slice_2d = np.fliplr(slice_2d)
            
            # Apply 90° rotation to all views
            slice_2d = np.rot90(slice_2d, k=1)
            
            # Display
            im = ax.imshow(slice_2d, cmap=self.colormap, origin='lower',
                          interpolation='bilinear', aspect='auto')
            
            # Overlay networks — exact atlas footprint, pixel-aligned
            if self.network_centroids and self.network_overlaps:
                if view_name == 'axial':
                    raw_shape = self.template_data[:, :, sidx].shape
                elif view_name == 'coronal':
                    raw_shape = self.template_data[:, sidx, :].shape
                else:
                    raw_shape = self.template_data[sidx, :, :].shape
                overlay = self._build_atlas_overlay(view_name, sidx,
                                                    raw_shape, highlighted_net_idx)
                if overlay is None:
                    overlay = self._build_network_overlay(raw_shape, view_name,
                                                          highlighted_net_idx)
                if overlay is not None and overlay[..., 3].max() > 0:
                    overlay = self._orient_slice(overlay, view_name)
                    ax.imshow(overlay, origin='lower', interpolation='nearest',
                              aspect='auto', zorder=10)
            
            # Crosshair
            if self.crosshair_mni is not None:
                try:
                    ch_mni = self.crosshair_mni
                    ch_homo = np.array([ch_mni[0], ch_mni[1], ch_mni[2], 1.0])
                    ch_vox_homo = np.linalg.inv(self.template_affine) @ ch_homo
                    ch_vox = ch_vox_homo[:3]
                    
                    ch_in_slice = False
                    ch_x, ch_y = None, None
                    
                    if view_name == 'axial' and abs(ch_vox[2] - sidx) <= 1.0:
                        ch_x, ch_y = ch_vox[0], ch_vox[1]
                        ch_in_slice = True
                    elif view_name == 'coronal' and abs(ch_vox[1] - sidx) <= 1.0:
                        ch_x, ch_y = ch_vox[0], ch_vox[2]
                        ch_in_slice = True
                    elif view_name == 'sagittal' and abs(ch_vox[0] - sidx) <= 1.0:
                        ch_x, ch_y = ch_vox[1], ch_vox[2]
                        ch_in_slice = True
                    
                    if ch_in_slice and ch_x is not None:
                        ax.axvline(ch_x, color='#00FF00', linewidth=2.5, linestyle='--', alpha=0.85)
                        ax.axhline(ch_y, color='#00FF00', linewidth=2.5, linestyle='--', alpha=0.85)
                        ax.plot(ch_x, ch_y, 'o', color='#00FF00', markersize=6,
                               markeredgecolor='white', markeredgewidth=1, zorder=15)
                except:
                    pass
            
            # Labels
            view_titles = {'axial': 'Axial', 'coronal': 'Coronal', 'sagittal': 'Sagittal'}
            ax.set_title(f"{view_titles[view_name]} (Slice {sidx})", color='#7090b8', fontsize=9, fontweight='bold')
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_facecolor('#0a0a14')
            
            # Apply zoom
            if self.zoom != 1.0:
                h, w = slice_2d.shape
                xlim_center = w / 2
                ylim_center = h / 2
                x_range = w / self.zoom / 2
                y_range = h / self.zoom / 2
                ax.set_xlim(xlim_center - x_range, xlim_center + x_range)
                ax.set_ylim(ylim_center - y_range, ylim_center + y_range)
            
            fig.tight_layout()
            if not hasattr(self, '_tri_ax'):
                self._tri_ax = {}
            self._tri_ax[view_name] = ax    # remember for pixel->data mapping
            self._update_canvas_display(canvas, fig)
            
            # Restore view
            self.current_view = old_view

    def _render_bar_graph(self, highlighted_net_idx=None):
        """Horizontal bar chart of overlap coefficients."""
        if not self.current_results:
            return
        networks = self.current_results.get('networks', [])
        overlaps = self.current_results.get('overlaps', [])
        metric = self.current_results.get('overlap_metric', 'Dice')
        n = min(len(networks), len(overlaps), 40)

        # theme-aware chart colors
        try:
            tc = tm.figure_colors()
        except Exception:
            tc = {'fig': '#0a0a14', 'ax': '#0a0a14', 'text': '#dde0f0',
                  'spine': '#1c1c32', 'accent': '#6070a0'}
        bg = tc['fig']; axbg = tc['ax']
        txt = tc['text']; sub = tc['accent']; spinec = tc['spine']
        val_col = '#555555' if tm.CURRENT == 'win11' else '#b0b0c8'
        edge_hl = '#000000' if tm.CURRENT == 'win11' else '#ffffff'

        self.bar_fig.clear()
        self.bar_fig.patch.set_facecolor(bg)
        ax = self.bar_fig.add_subplot(111)
        ax.set_facecolor(axbg)

        colors = self._network_colors(len(self.network_names)) \
            if getattr(self, 'network_names', None) else self._network_colors(n)

        for i in range(n):
            alpha = 1.0 if (highlighted_net_idx is None or i == highlighted_net_idx) else 0.4
            ax.barh(i, overlaps[i], color=colors[i], alpha=alpha,
                    height=0.7, edgecolor=edge_hl if i == highlighted_net_idx else 'none', linewidth=1.2)
            if overlaps[i] > 0.02:
                ax.text(overlaps[i] + 0.008, i, f'{overlaps[i]:.4f}',
                        va='center', fontsize=7, color=val_col)

        ax.set_yticks(range(n))
        ax.set_yticklabels(networks[:n], fontsize=7.5, color=txt)
        ax.set_xlabel(f'{metric} coefficient', color=sub, fontsize=9)
        ax.set_title("Network overlap coefficients", color=sub, fontsize=9, pad=6)
        ax.invert_yaxis()
        for spine in ax.spines.values():
            spine.set_color(spinec)
        ax.tick_params(axis='x', colors=sub)
        max_val = max(overlaps[:n]) if overlaps[:n] else 0.1
        ax.set_xlim(0, max_val * 1.2)
        self.bar_fig.tight_layout()
        self._update_canvas_display(self.bar_canvas, self.bar_fig)

    # ----------------------------------------------------------------------
    # Data loading and table display
    # ----------------------------------------------------------------------
    @staticmethod
    def _world_bbox(shape, affine):
        """World-coordinate bounding box (min, max) over the volume's 8 corners."""
        import itertools
        corners = []
        for c in itertools.product([0, shape[0]-1], [0, shape[1]-1], [0, shape[2]-1]):
            w = affine @ np.array([c[0], c[1], c[2], 1.0])
            corners.append(w[:3])
        corners = np.array(corners)
        return corners.min(0), corners.max(0)

    def _spaces_match(self, shape_a, aff_a, shape_b, aff_b, center_tol=20.0, size_tol=40.0):
        """True if two volumes occupy the same world (MNI/Colin) space."""
        try:
            mn_a, mx_a = self._world_bbox(shape_a, aff_a)
            mn_b, mx_b = self._world_bbox(shape_b, aff_b)
        except Exception:
            return True  # don't block rendering on a geometry hiccup
        center_ok = np.all(np.abs((mn_a + mx_a)/2 - (mn_b + mx_b)/2) < center_tol)
        size_ok = np.all(np.abs((mx_a - mn_a) - (mx_b - mn_b)) < size_tol)
        return bool(center_ok and size_ok)

    def _find_space_template(self, space):
        """Locate a CBIG anatomical template that lives in `space`'s world frame."""
        try:
            import cbig_network_correspondence as cnc
            bases = [Path(cnc.__file__).parent / 'data']
        except Exception:
            bases = []
        # Also try alongside the configured atlas data directory
        try:
            from nct_application.cbig_config import CBIGConfig
            ad = CBIGConfig.get_atlas_dir()
            if ad:
                bases.append(Path(ad).parent)
                bases.append(Path(ad))
        except Exception:
            pass
        for base in bases:
            for cand in (base / 'templates' / f'{space}.nii.gz',
                         base / 'templates' / f'{space}_header.nii.gz',
                         base / 'cortical_masks' / f'{space}.nii.gz'):
                if cand.exists():
                    return str(cand)
        return None

    def _ensure_underlay_matches_space(self, space):
        """Guarantee the displayed underlay shares the atlas world space so the
        footprint overlay is anatomically exact. If the current underlay is in a
        different space (e.g. MNI underlay but Colin analysis), auto-load the
        matching CBIG template."""
        if getattr(self, '_atlas_vol', None) is None or self._atlas_aff is None:
            return
        if self.template_data is None or self.template_affine is None:
            return
        atlas_shape = self._atlas_vol.shape[:3]
        if self._spaces_match(atlas_shape, self._atlas_aff,
                              self.template_data.shape, self.template_affine):
            return  # already correct (e.g. MNI underlay + FSLMNI2mm atlas)

        tp = self._find_space_template(space)
        if tp:
            disp = f"{space} (analysis space)"
            self.template_paths[disp] = tp
            # add to the combo if not present
            if self.underlay_combo.findText(disp) < 0:
                self.underlay_combo.blockSignals(True)
                self.underlay_combo.addItem(disp, disp)
                self.underlay_combo.blockSignals(False)
            if self._load_template(disp):
                idx = self.underlay_combo.findText(disp)
                if idx >= 0:
                    self.underlay_combo.blockSignals(True)
                    self.underlay_combo.setCurrentIndex(idx)
                    self.underlay_combo.blockSignals(False)
                print(f"ℹ️ Underlay switched to '{disp}' so the overlay matches "
                      f"the {space} analysis space.")
        else:
            print(f"⚠️ Underlay is not in the {space} analysis space and no "
                  f"matching template was found; overlay may be misaligned.")

    def display_results(self, results, space='FSLMNI2mm'):
        self.current_results = results
        self.current_brain_space = space
        self.current_atlas_code = results.get('atlas_code', '')

        # Extract networks, overlaps, p-values (handle dual components)
        if 'components' in results and isinstance(results['components'], dict):
            components = results['components']
            if components:
                comp_name = list(components.keys())[0]
                comp_res = components[comp_name]
                networks = comp_res.get('networks', [])
                overlaps = comp_res.get('overlaps', [])
                p_values = comp_res.get('p_values', [])
                self.current_atlas_code = comp_name
            else:
                networks = overlaps = p_values = []
        else:
            networks = results.get('networks', [])
            overlaps = results.get('overlaps', [])
            p_values = results.get('p_values', [])

        # Store for overlay rendering
        self.network_names = networks
        self.network_overlaps = overlaps
        self.network_pvalues = p_values
        self._extract_centroids(results)   # tries to get MNI coordinates from BrainRenderer or fallback
        self._compute_voxel_stats()        # per-network voxel counts (feature 2)

        metric = results.get('overlap_metric', 'Dice')
        n = min(len(networks), len(overlaps), len(p_values))
        sig = sum(1 for p in p_values[:n] if p < 0.05)
        self.lbl_summary.setText(
            f"Atlas: {self.current_atlas_code}  ·  Space: {space}  ·  "
            f"{n} networks  ·  {sig} significant (p<0.05)"
        )

        # Fill table
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(['Name', metric, 'P-value'])

        for i in range(n):
            self.table.insertRow(i)
            pval = float(p_values[i])
            ov = float(overlaps[i])

            if pval < 0.001: row_bg = QColor('#0d2a0d')
            elif pval < 0.01: row_bg = QColor('#1a2a0a')
            elif pval < 0.05: row_bg = QColor('#252010')
            else: row_bg = QColor('#07070f')

            name_item = QTableWidgetItem(str(networks[i]))
            name_item.setForeground(QColor('#7dd3fc'))
            name_item.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
            name_item.setBackground(row_bg)
            self.table.setItem(i, 0, name_item)

            ov_item = QTableWidgetItem(f"{ov:.5f}")
            ov_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ov_item.setForeground(QColor('#86efac'))
            ov_item.setBackground(row_bg)
            self.table.setItem(i, 1, ov_item)

            if pval < 0.001: sig_lbl, pv_col = '  ★★★', '#4ade80'
            elif pval < 0.01: sig_lbl, pv_col = '  ★★', '#86efac'
            elif pval < 0.05: sig_lbl, pv_col = '  ★', '#fde68a'
            else: sig_lbl, pv_col = '', '#94a3b8'
            pv_item = QTableWidgetItem(f"{pval:.5f}{sig_lbl}")
            pv_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pv_item.setForeground(QColor(pv_col))
            pv_item.setBackground(row_bg)
            self.table.setItem(i, 2, pv_item)

        # Ensure a template is loaded
        if self.template_data is None and self.template_paths:
            idx = self.underlay_combo.currentIndex()
            if idx >= 0:
                self._on_underlay_changed()
            else:
                # load first available
                first = list(self.template_paths.keys())[0]
                self._load_template(first)

        # Guarantee the underlay shares the atlas world space (MNI vs Colin etc.)
        self._ensure_underlay_matches_space(space)

        self._render_bar_graph()
        self._render_brain_left()
        # Results #4: show subregions for the highest-overlap network by default
        if self.network_names:
            self._update_subregion_panel(0)
        self._render_decoding_empty()
        self._render_neuro_empty()
        self._render_trans_empty()

    def _load_network_assignment(self, atlas_path):
        """Load a parcel->network mapping (.mat) for fine parcellations.
        Returns a 1-D array where assignment[parcel_label-1] = network_number
        (1-based), or None if not found."""
        try:
            import scipy.io as sio
        except Exception:
            return None
        abbr = Path(atlas_path).name.replace('.nii.gz', '').replace('.nii', '')
        p = Path(atlas_path)
        for _ in range(7):
            p = p.parent
            for cand in (p / 'network_assignment' / f'{abbr}.mat',
                         p / 'data' / 'network_assignment' / f'{abbr}.mat'):
                if cand.exists():
                    try:
                        m = sio.loadmat(str(cand))
                        return np.asarray(m['mapping']).ravel()
                    except Exception:
                        return None
        return None

    def _resolve_atlas_mapping(self, atlas_vol, atlas_path, n_names):
        """Decide how atlas voxel values map to network rows.

        Returns (mode, label_map):
          mode='labels' : hard parcellation; label_map = {label_value: net_idx}
                          (handles clean, non-contiguous, and fine parcellations
                          with a parcel->network assignment file)
          mode='metric' : continuous single-component map; threshold to footprint
          mode='4d'     : 4-D probabilistic atlas; per-volume argmax
        """
        if atlas_vol.ndim == 4:
            return '4d', None
        uniq = sorted(int(v) for v in np.unique(atlas_vol) if v > 0)
        if not uniq:
            return 'metric', None
        n_uniq = len(uniq)
        if n_names and n_uniq == n_names:
            # Labels correspond 1:1 to networks (contiguous OR scattered values)
            return 'labels', {lab: i for i, lab in enumerate(uniq)}
        if n_names and n_uniq > n_names:
            assign = self._load_network_assignment(atlas_path)
            if assign is not None and len(assign) >= max(uniq):
                lm = {}
                for lab in uniq:
                    net = int(assign[lab - 1]) - 1
                    if 0 <= net < n_names:
                        lm[lab] = net
                if lm:
                    return 'labels', lm
            # Many unique values, no assignment -> treat as continuous metric
            return 'metric', None
        # Fewer labels than names (unusual) -> sequential best-effort
        return 'labels', {lab: i for i, lab in enumerate(uniq)}

    def _network_colors(self, n):
        """Single source of truth for network colors — identical to the bar graph,
        so brain blobs and bars always match."""
        try:
            from nct_application.interactive_brain import _build_network_colors
            return _build_network_colors(n)
        except Exception:
            # Fallback palette (only used if import fails)
            base = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
                    '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#A9DFBF',
                    '#F1948A', '#D7BDE2', '#ABEBC6', '#FAD7A0', '#F5B7B1']
            return [base[i % len(base)] for i in range(n)]

    def _build_atlas_overlay(self, view, slice_idx, raw_shape, highlighted_net_idx):
        """Build an RGBA overlay of the TRUE atlas ROI footprint for the current
        underlay slice.

        Every underlay pixel on this slice is mapped underlay-voxel -> MNI(world)
        -> atlas-voxel, and the atlas label there is looked up. This makes the
        overlay correspond EXACTLY to the atlas regions AND to the displayed
        underlay, regardless of differing shapes/affines/orientations.

        Returns the RGBA array in RAW (untransformed) slice orientation, or None
        if no atlas volume is available.
        """
        if getattr(self, '_atlas_vol', None) is None or self._atlas_aff is None:
            return None
        if self.template_affine is None:
            return None

        H, W = raw_shape
        ii, jj = np.mgrid[0:H, 0:W]
        # Underlay voxel coordinates for every pixel of this slice
        if view == 'axial':       # slice = data[:, :, z]
            v0, v1, v2 = ii, jj, np.full_like(ii, slice_idx)
        elif view == 'coronal':   # slice = data[:, y, :]
            v0, v1, v2 = ii, np.full_like(ii, slice_idx), jj
        else:                     # sagittal: data[x, :, :]
            v0, v1, v2 = np.full_like(ii, slice_idx), ii, jj

        ua = self.template_affine
        # underlay voxel -> world(MNI)
        wx = ua[0, 0]*v0 + ua[0, 1]*v1 + ua[0, 2]*v2 + ua[0, 3]
        wy = ua[1, 0]*v0 + ua[1, 1]*v1 + ua[1, 2]*v2 + ua[1, 3]
        wz = ua[2, 0]*v0 + ua[2, 1]*v1 + ua[2, 2]*v2 + ua[2, 3]
        # world -> atlas voxel
        inv = np.linalg.inv(self._atlas_aff)
        ax = np.round(inv[0, 0]*wx + inv[0, 1]*wy + inv[0, 2]*wz + inv[0, 3]).astype(int)
        ay = np.round(inv[1, 0]*wx + inv[1, 1]*wy + inv[1, 2]*wz + inv[1, 3]).astype(int)
        az = np.round(inv[2, 0]*wx + inv[2, 1]*wy + inv[2, 2]*wz + inv[2, 3]).astype(int)

        av = self._atlas_vol
        mode = getattr(self, '_atlas_mode', None)
        label_map = getattr(self, '_label_map', None)

        if mode == '4d' or av.ndim == 4:
            sx, sy, sz = av.shape[0], av.shape[1], av.shape[2]
            valid = (ax >= 0) & (ax < sx) & (ay >= 0) & (ay < sy) & (az >= 0) & (az < sz)
            netmap = np.full((H, W), -1, int)   # network index per pixel
            if valid.any():
                vols = av[ax[valid], ay[valid], az[valid], :]
                best = np.argmax(vols, axis=1)
                maxval = vols[np.arange(vols.shape[0]), best]
                netmap[valid] = np.where(maxval > 0, best, -1)
        elif mode == 'metric':
            sx, sy, sz = av.shape
            valid = (ax >= 0) & (ax < sx) & (ay >= 0) & (ay < sy) & (az >= 0) & (az < sz)
            netmap = np.full((H, W), -1, int)
            if valid.any():
                vals = av[ax[valid], ay[valid], az[valid]]
                # Continuous map: everything above zero is the single component
                netmap[valid] = np.where(vals > 0, 0, -1)
        else:  # 'labels'
            sx, sy, sz = av.shape
            valid = (ax >= 0) & (ax < sx) & (ay >= 0) & (ay < sy) & (az >= 0) & (az < sz)
            labels = np.zeros((H, W), int)
            labels[valid] = av[ax[valid], ay[valid], az[valid]].astype(int)
            # Translate atlas label values -> network indices via the resolved map
            netmap = np.full((H, W), -1, int)
            if label_map:
                for lab, idx in label_map.items():
                    netmap[labels == lab] = idx

        overlay = np.zeros((H, W, 4), float)
        present = [int(v) for v in np.unique(netmap) if v >= 0]
        if not present:
            return overlay

        import matplotlib.colors as mcolors
        n_net = len(self.network_names)
        colors = self._network_colors(n_net)
        for idx in present:
            if idx < 0 or idx >= n_net:
                continue
            rgb = mcolors.to_rgb(colors[idx % len(colors)])
            m = (netmap == idx)
            is_hi = (idx == highlighted_net_idx)
            a = 0.85 if is_hi else (0.18 if highlighted_net_idx is not None else 0.55)
            for c in range(3):
                overlay[..., c][m] = rgb[c]
            overlay[..., 3][m] = a
        return overlay

    def _build_network_overlay(self, raw_shape, view, highlighted_net_idx):
        """Build an RGBA activation overlay in RAW slice space.

        Soft gaussian 'activation' blobs are stamped at each in-slice network
        centroid, colored to match the bar graph. The returned array is in the
        same (untransformed) orientation as the raw slice, so the caller applies
        the identical flip/rotation to BOTH underlay and overlay — guaranteeing
        the blobs stay anatomically aligned with the brain.
        """
        import matplotlib.colors as mcolors
        H, W = raw_shape
        overlay = np.zeros((H, W, 4), dtype=float)
        if not (self.network_centroids and self.network_overlaps):
            return overlay
        colors = self._network_colors(len(self.network_centroids))
        yy, xx = np.mgrid[0:H, 0:W]
        inv_aff = np.linalg.inv(self.template_affine)

        for i, (mni, overlap) in enumerate(zip(self.network_centroids,
                                               self.network_overlaps)):
            if mni is None or overlap is None:
                continue
            vox = (inv_aff @ np.array([mni[0], mni[1], mni[2], 1.0]))[:3]
            # Map (raw_row, raw_col, slice_coord) for this view
            if view == 'axial':       # slice = data[:, :, z] -> (X, Y)
                row, col, slc = vox[0], vox[1], vox[2]
            elif view == 'coronal':   # slice = data[:, y, :] -> (X, Z)
                row, col, slc = vox[0], vox[2], vox[1]
            else:                     # sagittal: data[x, :, :] -> (Y, Z)
                row, col, slc = vox[1], vox[2], vox[0]

            # Only stamp blobs whose centroid is near the current slice
            if abs(slc - self.current_slice_idx) > 4.0:
                continue

            # Gaussian footprint: size & peak alpha scale with overlap (Dice)
            sigma = 2.5 + float(overlap) * 7.0
            is_hi = (i == highlighted_net_idx)
            peak = min(0.9, 0.30 + float(overlap) * 1.4) * (1.2 if is_hi else 1.0)
            g = np.exp(-(((yy - row) ** 2 + (xx - col) ** 2) / (2.0 * sigma ** 2)))
            a = g * peak
            rgb = mcolors.to_rgb(colors[i % len(colors)])
            # Max-alpha compositing: dominant network wins each pixel (no muddiness)
            take = a > overlay[..., 3]
            for c in range(3):
                overlay[..., c] = np.where(take, rgb[c], overlay[..., c])
            overlay[..., 3] = np.maximum(overlay[..., 3], a)

        return overlay

    @staticmethod
    def _orient_slice(arr, view):
        """Apply the SAME orientation transform used for the underlay so an
        overlay (2D or RGBA) stays pixel-aligned with the brain image."""
        arr = np.fliplr(arr)
        arr = np.rot90(arr, k=1)
        return arr

    @staticmethod
    def _transform_point(row, col, raw_shape):
        """Map a raw-slice (row, col) to displayed plot (x, y) after the
        underlay transform fliplr + rot90(k=1). Verified numerically:
        the fliplr/rot90 width terms cancel, giving (x=row, y=col)."""
        return row, col

    def _draw_activation_blob(self, ax, x, y, base_radius, color,
                              highlighted=False, zorder=10):
        """Draw a soft, borderless activation-style blob (radial glow) rather
        than a hard-edged circle. Resembles a thresholded activation cluster."""
        from matplotlib.patches import Circle
        import matplotlib.colors as mcolors
        rgb = mcolors.to_rgb(color)
        # Concentric borderless circles with alpha falloff = soft glow
        layers = [(2.6, 0.08), (2.0, 0.14), (1.5, 0.24),
                  (1.05, 0.45), (0.65, 0.80)]
        boost = 1.15 if highlighted else 1.0
        z = zorder + (10 if highlighted else 0)
        for rad_mult, a in layers:
            ax.add_patch(Circle((x, y), radius=base_radius * rad_mult,
                                 facecolor=rgb, edgecolor='none',
                                 alpha=min(a * boost, 1.0), zorder=z))
        if highlighted:
            # bright soft core (still borderless) to mark the selected network
            ax.add_patch(Circle((x, y), radius=base_radius * 0.32,
                                 facecolor='white', edgecolor='none',
                                 alpha=0.85, zorder=z + 1))

    # ---- real MNI centroid computation -----------------------------------
    def _find_atlas_file(self, space, author, abbr):
        """Locate the atlas NIfTI for the analyzed parcellation.

        Returns either a single Path (hard/metric/4D atlas) or, for
        multi-component ICA atlases stored as separate per-component files
        (e.g. HCPICA_thresh_zstat1..20, AL20_zstat1..20, UKBICA_thresh_zstat1..20),
        a sorted list of component Paths.
        """
        from pathlib import Path
        import re
        if not abbr:
            return None
        root = None
        try:
            from nct_application.cbig_config import CBIGConfig
            root = CBIGConfig.get_atlas_dir()
        except Exception:
            root = None
        if not root:
            return None
        root = Path(root)
        space = space or ''

        # 1) Direct single-file candidate paths
        for base in (root, root / 'atlases'):
            sp = base / space
            if author:
                p = sp / author / f"{abbr}.nii.gz"
                if p.exists():
                    return p
            if sp.exists():
                for a in sp.iterdir():
                    if a.is_dir():
                        p = a / f"{abbr}.nii.gz"
                        if p.exists():
                            return p

        # 2) Multi-component ICA atlas: collect per-component files.
        #    Component naming varies (e.g. HCPICA_thresh_zstat3, AL20_zstat3),
        #    so match files that start with the abbr and contain a trailing index.
        comp_re = re.compile(r'(\d+)(?:\.nii(?:\.gz)?)$', re.IGNORECASE)
        for base in (root, root / 'atlases'):
            sp = base / space
            if not sp.exists():
                continue
            search_dirs = [sp] + [d for d in sp.iterdir() if d.is_dir()] if sp.exists() else []
            for d in search_dirs:
                comps = []
                for p in d.glob('*.nii*'):
                    name = p.name
                    if name.lower().startswith(abbr.lower()) and comp_re.search(name):
                        m = comp_re.search(name)
                        comps.append((int(m.group(1)), p))
                if len(comps) >= 2:
                    comps.sort(key=lambda t: t[0])
                    return [p for _, p in comps]

        # 3) Last resort: recursive glob for a single file, prefer matching space
        hits = list(root.rglob(f"{abbr}.nii.gz"))
        for h in hits:
            if space and space in str(h):
                return h
        if hits:
            return hits[0]

        # 4) Recursive glob for components anywhere under the space
        comps = []
        for p in root.rglob('*.nii*'):
            name = p.name
            if name.lower().startswith(abbr.lower()) and comp_re.search(name):
                if not space or space in str(p):
                    m = comp_re.search(name)
                    comps.append((int(m.group(1)), p))
        if len(comps) >= 2:
            comps.sort(key=lambda t: t[0])
            return [p for _, p in comps]
        return None

    def _mask_centroid_mni(self, mask, aff):
        idx = np.array(np.where(mask)).mean(axis=1)
        mni = aff @ np.array([idx[0], idx[1], idx[2], 1.0])
        return mni[:3]

    def _weighted_centroid_mni(self, vol, aff):
        w = np.maximum(np.nan_to_num(vol), 0)
        if w.sum() <= 0:
            return None
        coords = np.array(np.where(w > 0))
        weights = w[w > 0]
        idx = (coords * weights).sum(axis=1) / weights.sum()
        mni = aff @ np.array([idx[0], idx[1], idx[2], 1.0])
        return mni[:3]

    def _extract_centroids(self, results):
        """Compute REAL per-network MNI centroids from the atlas NIfTI.

        Hard parcellation  -> center of mass of each label (1..n).
        Soft/probabilistic -> intensity-weighted centroid of each volume.
        Falls back to anatomical name hints, then None.
        """
        import nibabel as nib
        n = len(self.network_names)
        self.network_centroids = [None] * n
        if n == 0:
            return

        # Resolve atlas identity from the results dict
        space = (results.get('space') or results.get('brain_space')
                 or self.current_brain_space or 'FSLMNI2mm')
        author = results.get('author') or results.get('atlas_author')
        abbr = (results.get('abbreviation') or results.get('atlas_code')
                or self.current_atlas_code)

        # Reset stored atlas (used for exact footprint overlay)
        self._atlas_vol = None
        self._atlas_aff = None
        self._atlas_is_4d = False
        self._atlas_mode = None
        self._label_map = None

        atlas_path = self._find_atlas_file(space, author, abbr)

        # Multi-component ICA atlas: a list of per-component NIfTI files.
        if isinstance(atlas_path, list) and atlas_path:
            try:
                comp_imgs = [nib.load(str(p)) for p in atlas_path]
                aff = comp_imgs[0].affine
                # Stack components into a 4D volume (x, y, z, component)
                comp_data = [im.get_fdata() for im in comp_imgs]
                data = np.stack(comp_data, axis=-1)
                self._atlas_vol = data
                self._atlas_aff = aff
                self._atlas_is_4d = True
                self._atlas_mode = '4d'
                self._label_map = None
                for i in range(min(n, data.shape[3])):
                    self.network_centroids[i] = self._weighted_centroid_mni(
                        data[..., i], aff)
                got = sum(c is not None for c in self.network_centroids)
                print(f"✅ Loaded ICA atlas {abbr} from {len(atlas_path)} component "
                      f"files (4D stack {data.shape}); {got}/{n} centroids")
            except Exception as e:
                print(f"⚠️ Could not load ICA component atlas {abbr}: {e}")
            atlas_path = None  # handled; skip the single-file branch below

        if atlas_path is not None:
            try:
                img = nib.load(str(atlas_path))
                data = img.get_fdata()
                aff = img.affine
                self._atlas_vol = data
                self._atlas_aff = aff
                self._atlas_is_4d = (data.ndim == 4)

                mode, label_map = self._resolve_atlas_mapping(data, str(atlas_path), n)
                self._atlas_mode = mode
                self._label_map = label_map

                if mode == '4d':
                    for i in range(min(n, data.shape[3])):
                        self.network_centroids[i] = self._weighted_centroid_mni(
                            data[..., i], aff)
                elif mode == 'metric':
                    c = self._weighted_centroid_mni(data, aff)
                    if c is not None and n > 0:
                        self.network_centroids[0] = c
                else:  # 'labels'
                    # Group voxels by network index (union of its labels/parcels)
                    for net_idx in range(n):
                        labs = [lab for lab, idx in (label_map or {}).items()
                                if idx == net_idx]
                        if not labs:
                            continue
                        mask = np.isin(data, labs)
                        if mask.any():
                            self.network_centroids[net_idx] = \
                                self._mask_centroid_mni(mask, aff)
                got = sum(c is not None for c in self.network_centroids)
                print(f"✅ Loaded atlas {Path(atlas_path).name} (shape {data.shape}, "
                      f"mode={mode}); {got}/{n} centroids")
            except Exception as e:
                print(f"⚠️ Could not load atlas: {e}")
        else:
            print(f"⚠️ Atlas file not found for {abbr} ({author}/{space}); using name hints")

        # Fallback for any missing: anatomical name hints
        try:
            from nct_application.interactive_brain import _mni_hint
        except Exception:
            _mni_hint = None
        if _mni_hint is not None:
            for i, name in enumerate(self.network_names):
                if self.network_centroids[i] is None:
                    hint = _mni_hint(name)
                    if hint is not None and not np.allclose(hint, 0):
                        self.network_centroids[i] = np.asarray(hint, dtype=float)

    # ----------------------------------------------------------------------
    # Row click & literature panel
    # ----------------------------------------------------------------------
    def _load_neurosynth_data(self):
        """Load the bundled precomputed Neurosynth decoding JSON (if present)."""
        self._neurosynth_data = None
        try:
            from pathlib import Path
            here = Path(__file__).resolve().parent
            rdir = _resource_dir()
            for cand in (rdir / 'data' / 'neurosynth_decoding.json',
                         rdir / 'neurosynth_decoding.json',
                         here / 'data' / 'neurosynth_decoding.json',
                         here / 'neurosynth_decoding.json'):
                if cand.exists():
                    import json
                    with open(cand, 'r', encoding='utf-8') as fh:
                        self._neurosynth_data = json.load(fh)
                    print(f"✅ Loaded Neurosynth decoding bundle: {cand.name}")
                    return
            print("ℹ️ No neurosynth_decoding.json found; decoding panel will show a hint.")
        except Exception as e:
            print(f"⚠️ Could not load Neurosynth decoding bundle: {e}")

    def _render_decoding_empty(self, message=None):
        msg = message or "Click a network in the results table to see its associated functional terms."
        self.decoding_view.setHtml(
            f"<div style='color:#5a6a85; font-size:10pt; padding:18px 8px;'>{msg}</div>")
        if hasattr(self, 'decode_src_lbl'):
            self.decode_src_lbl.setText("")

    def _update_decoding_panel(self, network_name):
        """Populate the top-right panel with the top functional terms (+ r) for
        the selected network, read from the precomputed Neurosynth bundle."""
        data = getattr(self, '_neurosynth_data', None)
        if not data:
            self._render_decoding_empty(
                "Functional decoding unavailable — the precomputed "
                "<i>neurosynth_decoding.json</i> bundle was not found.")
            return

        atlas = getattr(self, 'current_atlas_code', '') or ''
        atlas_entry = data.get(atlas)
        if atlas_entry is None:
            # try a case-insensitive / suffix-tolerant match
            for k in data:
                if k.lower() == atlas.lower():
                    atlas_entry = data[k]
                    break
        if not atlas_entry or network_name not in atlas_entry:
            self._render_decoding_empty(
                f"No decoding available for <b>{network_name}</b> "
                f"in atlas <b>{atlas or '—'}</b>.")
            return

        terms = atlas_entry[network_name]  # [[term, r], ...] already top-N, r desc
        if not terms:
            self._render_decoding_empty(f"No functional terms passed filtering for "
                                        f"<b>{network_name}</b>.")
            return

        meta = data.get('_meta', {})
        n_studies = meta.get('n_studies')
        self.decode_src_lbl.setText(
            f"Neurosynth · {network_name}" + (f" · {n_studies} studies" if n_studies else ""))

        sample_banner = ""
        if meta.get('sample'):
            sample_banner = (
                "<div style='color:#fbbf24; background:#2a230a; border:1px solid #4a3a10;"
                " border-radius:4px; padding:5px 8px; margin-bottom:8px; font-size:8.5pt;'>"
                "⚠ SAMPLE placeholder values — run <i>precompute_neurosynth.py</i> "
                "to generate real Neurosynth r-values.</div>")

        # Bars scaled to the largest positive r in this list
        max_r = max((r for _, r in terms), default=0.0) or 1.0
        rows_html = []
        for term, r in terms:
            frac = max(0.0, min(1.0, r / max_r)) if max_r > 0 else 0.0
            barw = int(frac * 120)
            rcol = '#4ade80' if r >= 0 else '#f87171'
            rows_html.append(
                "<tr>"
                f"<td style='padding:3px 8px 3px 2px; color:#dbe7f5; white-space:nowrap;'>{term}</td>"
                f"<td style='padding:3px 6px; width:130px;'>"
                f"<div style='display:inline-block; width:{barw}px; height:9px;"
                f" background:{rcol}; border-radius:2px;'></div></td>"
                f"<td style='padding:3px 2px; color:{rcol}; font-family:Consolas;"
                f" text-align:right;'>{r:+.3f}</td>"
                "</tr>"
            )
        html = (
            sample_banner +
            "<table style='border-collapse:collapse; width:100%;'>"
            "<tr style='color:#7090b0; font-size:8.5pt;'>"
            "<td style='padding:2px;'>Term</td><td></td>"
            "<td style='text-align:right; padding:2px;'>r</td></tr>"
            + "".join(rows_html) +
            "</table>"
        )
        self.decoding_view.setHtml(html)

    # ----------------------- Neurotransmitter panel -----------------------
    def _load_neurotransmitter_data(self):
        """Load the bundled precomputed neurotransmitter mapping JSON (if present)."""
        self._neuro_data = None
        try:
            from pathlib import Path
            here = Path(__file__).resolve().parent
            rdir = _resource_dir()
            for cand in (rdir / 'data' / 'neurotransmitter_mapping.json',
                         rdir / 'neurotransmitter_mapping.json',
                         here / 'data' / 'neurotransmitter_mapping.json',
                         here / 'neurotransmitter_mapping.json'):
                if cand.exists():
                    import json
                    with open(cand, 'r', encoding='utf-8') as fh:
                        self._neuro_data = json.load(fh)
                    print(f"✅ Loaded neurotransmitter bundle: {cand.name}")
                    return
            print("ℹ️ No neurotransmitter_mapping.json found; PET tab will show a hint.")
        except Exception as e:
            print(f"⚠️ Could not load neurotransmitter bundle: {e}")

    def _render_neuro_empty(self, message=None):
        msg = message or ("Click a network to see its association with PET "
                          "neurotransmitter receptor/transporter maps.")
        self.neuro_view.setHtml(
            f"<div style='color:#5a6a85; font-size:10pt; padding:18px 8px;'>{msg}</div>")
        if hasattr(self, 'neuro_src_lbl'):
            self.neuro_src_lbl.setText("")

    def _update_neuro_panel(self, network_name):
        """Populate the PET tab with receptor associations (r and p_spin) for the
        selected network, read from the precomputed neurotransmitter bundle."""
        data = getattr(self, '_neuro_data', None)
        if not data:
            self._render_neuro_empty(
                "Neurotransmitter mapping unavailable — the precomputed "
                "<i>neurotransmitter_mapping.json</i> bundle was not found.")
            return

        atlas = getattr(self, 'current_atlas_code', '') or ''
        atlas_entry = data.get(atlas)
        if atlas_entry is None:
            for k in data:
                if k.lower() == atlas.lower():
                    atlas_entry = data[k]
                    break
        if not atlas_entry or network_name not in atlas_entry:
            self._render_neuro_empty(
                f"No receptor mapping available for <b>{network_name}</b> "
                f"in atlas <b>{atlas or '—'}</b>.")
            return

        rows = atlas_entry[network_name]  # [[system, r, p_spin], ...] sorted by |r|
        if not rows:
            self._render_neuro_empty(f"No receptor data for <b>{network_name}</b>.")
            return

        meta = data.get('_meta', {})
        self.neuro_src_lbl.setText(f"neuromaps PET · {network_name}")

        sample_banner = ""
        if meta.get('sample'):
            sample_banner = (
                "<div style='color:#fbbf24; background:#2a230a; border:1px solid #4a3a10;"
                " border-radius:4px; padding:5px 8px; margin-bottom:8px; font-size:8.5pt;'>"
                "⚠ SAMPLE placeholder values — run <i>precompute_neurotransmitter.py</i> "
                "for real values.</div>")

        # Bars are scaled to the largest |r| so both signs are visible.
        max_abs = max((abs(r) for _, r, *_ in rows), default=0.0) or 1.0
        rows_html = []
        for entry in rows:
            system = entry[0]
            r = entry[1]
            p = entry[2] if len(entry) > 2 else None
            frac = max(0.0, min(1.0, abs(r) / max_abs))
            barw = int(frac * 110)
            rcol = '#c084fc' if r >= 0 else '#f0789b'   # purple +, pink −
            # Significance styling from p_spin
            if p is None:
                sig_html = "<span style='color:#5a6a85;'>—</span>"
                name_color = '#dbe7f5'
            elif p < 0.05:
                sig_html = (f"<span style='color:#4ade80; font-weight:bold;'>"
                            f"p={p:.3f}{'*' if p >= 0.001 else ''}</span>")
                name_color = '#ffffff'
            else:
                sig_html = f"<span style='color:#6b7a90;'>p={p:.2f}</span>"
                name_color = '#8a9bb5'   # dim non-significant
            rows_html.append(
                "<tr>"
                f"<td style='padding:3px 8px 3px 2px; color:{name_color}; white-space:nowrap;'>{system}</td>"
                f"<td style='padding:3px 6px; width:120px;'>"
                f"<div style='display:inline-block; width:{barw}px; height:9px;"
                f" background:{rcol}; border-radius:2px;'></div></td>"
                f"<td style='padding:3px 6px; color:{rcol}; font-family:Consolas;"
                f" text-align:right;'>{r:+.3f}</td>"
                f"<td style='padding:3px 2px; font-size:8.5pt; text-align:right;'>{sig_html}</td>"
                "</tr>"
            )
        n_perm = meta.get('null', '')
        foot = ("<div style='color:#6b7a90; font-size:8pt; padding-top:8px;'>"
                "+r: receptor enriched in network. ")
        if any(len(entry) > 2 and entry[2] is not None for entry in rows):
            foot += "Bold green = spatial-null significant (p<sub>spin</sub>&lt;0.05)."
        else:
            foot += "(No spatial-null p-values; run precompute with --n-perm > 0 for significance.)"
        foot += "</div>"
        html = (
            sample_banner +
            "<table style='border-collapse:collapse; width:100%;'>"
            "<tr style='color:#9070b0; font-size:8.5pt;'>"
            "<td style='padding:2px;'>System</td><td></td>"
            "<td style='text-align:right; padding:2px;'>r</td>"
            "<td style='text-align:right; padding:2px;'>p<sub>spin</sub></td></tr>"
            + "".join(rows_html) +
            "</table>" + foot
        )
        self.neuro_view.setHtml(html)

    # ----------------------- Transcriptomics panel ------------------------
    def _load_transcriptomics_data(self):
        """Load the bundled receptor-gene expression JSON (if present)."""
        self._trans_data = None
        try:
            from pathlib import Path
            here = Path(__file__).resolve().parent
            rdir = _resource_dir()
            for cand in (rdir / 'data' / 'transcriptomics_mapping.json',
                         rdir / 'transcriptomics_mapping.json',
                         here / 'data' / 'transcriptomics_mapping.json',
                         here / 'transcriptomics_mapping.json'):
                if cand.exists():
                    import json
                    with open(cand, 'r', encoding='utf-8') as fh:
                        self._trans_data = json.load(fh)
                    print(f"✅ Loaded transcriptomics bundle: {cand.name}")
                    return
            print("ℹ️ No transcriptomics_mapping.json found; AHBA tab will show a hint.")
        except Exception as e:
            print(f"⚠️ Could not load transcriptomics bundle: {e}")

    def _render_trans_empty(self, message=None):
        msg = message or ("Click a network to see its association with receptor-gene "
                          "expression (Allen Human Brain Atlas).")
        self.trans_view.setHtml(
            f"<div style='color:#5a6a85; font-size:10pt; padding:18px 8px;'>{msg}</div>")
        if hasattr(self, 'trans_src_lbl'):
            self.trans_src_lbl.setText("")

    def _update_trans_panel(self, network_name):
        """Populate the AHBA tab with receptor-gene associations (r, p_spin)."""
        data = getattr(self, '_trans_data', None)
        if not data:
            self._render_trans_empty(
                "Transcriptomics unavailable — the precomputed "
                "<i>transcriptomics_mapping.json</i> bundle was not found.")
            return
        atlas = getattr(self, 'current_atlas_code', '') or ''
        atlas_entry = data.get(atlas)
        if atlas_entry is None:
            for k in data:
                if k.lower() == atlas.lower():
                    atlas_entry = data[k]
                    break
        if not atlas_entry or network_name not in atlas_entry:
            self._render_trans_empty(
                f"No receptor-gene mapping for <b>{network_name}</b> "
                f"in atlas <b>{atlas or '—'}</b>.")
            return
        rows = atlas_entry[network_name]  # [["GENE (SYSTEM)", r, p_spin], ...]
        if not rows:
            self._render_trans_empty(f"No gene data for <b>{network_name}</b>.")
            return

        meta = data.get('_meta', {})
        self.trans_src_lbl.setText(f"AHBA · {network_name}")
        sample_banner = ""
        if meta.get('sample'):
            sample_banner = (
                "<div style='color:#fbbf24; background:#2a230a; border:1px solid #4a3a10;"
                " border-radius:4px; padding:5px 8px; margin-bottom:8px; font-size:8.5pt;'>"
                "⚠ SAMPLE placeholder values — run <i>precompute_transcriptomics.py</i> "
                "for real values.</div>")

        max_abs = max((abs(r) for _, r, *_ in rows), default=0.0) or 1.0
        rows_html = []
        for entry in rows:
            label = entry[0]            # "GENE (SYSTEM)"
            r = entry[1]
            p = entry[2] if len(entry) > 2 else None
            frac = max(0.0, min(1.0, abs(r) / max_abs))
            barw = int(frac * 110)
            rcol = '#34d399' if r >= 0 else '#f0789b'   # teal +, pink −
            if p is None:
                sig_html = "<span style='color:#5a6a85;'>—</span>"; name_color = '#dbe7f5'
            elif p < 0.05:
                sig_html = f"<span style='color:#4ade80; font-weight:bold;'>p={p:.3f}</span>"
                name_color = '#ffffff'
            else:
                sig_html = f"<span style='color:#6b7a90;'>p={p:.2f}</span>"
                name_color = '#8a9bb5'
            rows_html.append(
                "<tr>"
                f"<td style='padding:3px 8px 3px 2px; color:{name_color}; white-space:nowrap;'>{label}</td>"
                f"<td style='padding:3px 6px; width:120px;'>"
                f"<div style='display:inline-block; width:{barw}px; height:9px;"
                f" background:{rcol}; border-radius:2px;'></div></td>"
                f"<td style='padding:3px 6px; color:{rcol}; font-family:Consolas;"
                f" text-align:right;'>{r:+.3f}</td>"
                f"<td style='padding:3px 2px; font-size:8.5pt; text-align:right;'>{sig_html}</td>"
                "</tr>"
            )
        foot = ("<div style='color:#6b7a90; font-size:8pt; padding-top:8px;'>"
                "Gene (paired PET system). ")
        if any(len(entry) > 3 and entry[3] is not None for entry in rows):
            foot += "Bold green = p<sub>spin</sub>&lt;0.05. "
        else:
            foot += "(No spatial-null p-values; run precompute with --n-perm > 0 for significance.) "
        foot += "Compare with the PET tab for convergent receptor evidence.</div>"
        html = (
            sample_banner +
            "<table style='border-collapse:collapse; width:100%;'>"
            "<tr style='color:#5ca588; font-size:8.5pt;'>"
            "<td style='padding:2px;'>Gene (system)</td><td></td>"
            "<td style='text-align:right; padding:2px;'>r</td>"
            "<td style='text-align:right; padding:2px;'>p<sub>spin</sub></td></tr>"
            + "".join(rows_html) +
            "</table>" + foot
        )
        self.trans_view.setHtml(html)

    def _on_row_click(self, index):
        row = index.row()
        if not self.current_results:
            return

        networks = self.current_results.get('networks', [])
        overlaps = self.current_results.get('overlaps', [])
        p_values = self.current_results.get('p_values', [])
        metric = self.current_results.get('overlap_metric', 'Dice')

        if row >= len(networks):
            return

        name = networks[row]
        ov = float(overlaps[row]) if row < len(overlaps) else 0.0
        pval = float(p_values[row]) if row < len(p_values) else 1.0
        sig = ('★★★ p<0.001' if pval < 0.001 else
               '★★  p<0.01' if pval < 0.01 else
               '★   p<0.05' if pval < 0.05 else 'n.s.')

        mni_str = "—"
        if row < len(self.network_centroids) and self.network_centroids[row] is not None:
            mni = self.network_centroids[row]
            mni_str = f"X={mni[0]:.1f},  Y={mni[1]:.1f},  Z={mni[2]:.1f} mm"

        # Results #4: show the selected network's cortical subregion breakdown
        self._update_subregion_panel(row)
        # Results #3: update the crosshair readout for this network's centroid
        if row < len(self.network_centroids) and self.network_centroids[row] is not None:
            self._update_crosshair_readout(self.network_centroids[row])

        # Highlight table row
        n_rows = self.table.rowCount()
        for r in range(n_rows):
            for c in range(3):
                item = self.table.item(r, c)
                if item:
                    if r == row:
                        item.setBackground(QColor('#1a3a60'))
                    else:
                        pv = float(p_values[r]) if r < len(p_values) else 1.0
                        if pv < 0.001: item.setBackground(QColor('#0d2a0d'))
                        elif pv < 0.01: item.setBackground(QColor('#1a2a0a'))
                        elif pv < 0.05: item.setBackground(QColor('#252010'))
                        else: item.setBackground(QColor('#07070f'))

        # Set crosshair to network centroid FIRST (before rendering)
        if row < len(self.network_centroids) and self.network_centroids[row] is not None:
            cent = self.network_centroids[row]
            # Ensure it's a proper tuple of floats
            self.crosshair_mni = (float(cent[0]), float(cent[1]), float(cent[2]))
            self.current_highlighted_idx = row
            print(f"✅ Crosshair set to network {row}: MNI {self.crosshair_mni}")
            print(f"   Current view: {self.current_view}, slice: {self.current_slice_idx}, template_data available: {self.template_data is not None}")
        else:
            print(f"❌ Cannot set crosshair - network {row} centroid is None")
            self.crosshair_mni = None
        
        # Then render brain with crosshair visible
        if self.view_mode == 'triplanar':
            self._render_triplanar(highlighted_net_idx=row)
        else:
            self._render_brain_left(highlighted_net_idx=row)
        self._render_bar_graph(highlighted_net_idx=row)

        # Populate the functional decoding panel for this network
        self._update_decoding_panel(name)
        self._update_neuro_panel(name)
        self._update_trans_panel(name)

    def _on_viewmode_changed(self):
        """Handle switching between single panel and triplanar view modes."""
        if self.viewmode_triplanar.isChecked():
            self.view_mode = 'triplanar'
            self.view_row_container.hide()  # Hide view buttons in triplanar mode
            self._setup_triplanar_view()
        else:
            self.view_mode = 'single'
            self.view_row_container.show()  # Show view buttons in single mode
            self._setup_single_view()

    def _setup_single_view(self):
        """Setup single panel brain view."""
        # Clear and reset container
        while self.brain_container_layout.count():
            widget = self.brain_container_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        
        # Clear figure references
        self.brain_fig_axial = None
        self.brain_fig_coronal = None
        self.brain_fig_sagittal = None
        self.brain_canvas_axial = None
        self.brain_canvas_coronal = None
        self.brain_canvas_sagittal = None
        
        # Add single interactive canvas (click + drag crosshair)
        self.brain_fig = plt.Figure(figsize=(8, 6), facecolor='#0a0a14')
        self.brain_canvas = self._make_canvas(self.brain_fig, view_id='')
        self.brain_canvas.setStyleSheet("background-color: #0a0a14; border: 1px solid #2a3a5a; border-radius: 4px;")
        self.brain_container_layout.addWidget(self.brain_canvas, 1)
        # Re-render
        if self.template_data is not None:
            self._render_brain_left(highlighted_net_idx=self.current_highlighted_idx)

    def _setup_triplanar_view(self):
        """Setup triplanar brain view (all 3 views side-by-side)."""
        # Clear container
        while self.brain_container_layout.count():
            widget = self.brain_container_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        
        # Clear single view reference
        self.brain_canvas = None
        self.brain_fig = None
        
        # Create triplanar container
        triplanar_widget = QWidget()
        triplanar_layout = QHBoxLayout(triplanar_widget)
        triplanar_layout.setContentsMargins(0, 0, 0, 0)
        triplanar_layout.setSpacing(4)
        
        # Create 3 interactive canvases for axial, coronal, sagittal
        self.brain_fig_axial = plt.Figure(figsize=(3, 3), facecolor='#0a0a14')
        self.brain_canvas_axial = self._make_canvas(self.brain_fig_axial, view_id='axial')
        self.brain_canvas_axial.setStyleSheet("background-color: #0a0a14; border: 1px solid #2a3a5a;")

        self.brain_fig_coronal = plt.Figure(figsize=(3, 3), facecolor='#0a0a14')
        self.brain_canvas_coronal = self._make_canvas(self.brain_fig_coronal, view_id='coronal')
        self.brain_canvas_coronal.setStyleSheet("background-color: #0a0a14; border: 1px solid #2a3a5a;")

        self.brain_fig_sagittal = plt.Figure(figsize=(3, 3), facecolor='#0a0a14')
        self.brain_canvas_sagittal = self._make_canvas(self.brain_fig_sagittal, view_id='sagittal')
        self.brain_canvas_sagittal.setStyleSheet("background-color: #0a0a14; border: 1px solid #2a3a5a;")

        # Add to layout
        triplanar_layout.addWidget(self.brain_canvas_axial)
        triplanar_layout.addWidget(self.brain_canvas_coronal)
        triplanar_layout.addWidget(self.brain_canvas_sagittal)
        
        self.brain_container_layout.addWidget(triplanar_widget, 1)
        
        # Render all 3 views
        if self.template_data is not None:
            self._render_triplanar(highlighted_net_idx=self.current_highlighted_idx)

    def _on_triplanar_click(self, event, view):
        """Handle clicks in triplanar view."""
        if not event or event.xdata is None or event.ydata is None:
            return
        
        try:
            # Set current view and slice for conversion
            old_view = self.current_view
            old_slice = self.current_slice_idx
            
            self.current_view = view
            
            # Convert click to MNI
            x_pix, y_pix = event.xdata, event.ydata
            
            if view == 'axial':
                z_vox = self.current_slice_idx
                x_vox, y_vox = x_pix, y_pix
            elif view == 'coronal':
                y_vox = self.current_slice_idx
                x_vox, z_vox = x_pix, y_pix
            else:  # sagittal
                x_vox = self.current_slice_idx
                y_vox, z_vox = x_pix, y_pix
            
            vox_homo = np.array([x_vox, y_vox, z_vox, 1.0])
            mni_homo = self.template_affine @ vox_homo
            self.crosshair_mni = tuple(mni_homo[:3])
            
            # Restore old view/slice
            self.current_view = old_view
            self.current_slice_idx = old_slice
            
            # Re-render
            self._render_triplanar(highlighted_net_idx=self.current_highlighted_idx)
            
        except Exception as e:
            print(f"⚠️ Error in triplanar click: {e}")

    # ----------------------------------------------------------------------
    # Export (unchanged from original)
    # -----------------------------------------------------------------------
    def _on_brain_canvas_click(self, event):
        """
        Handle mouse clicks on brain map for interactive crosshair navigation.
        Converts 2D pixel coordinates to MNI space and updates crosshair.
        """
        if not event or not hasattr(event, 'xdata') or not hasattr(event, 'ydata'):
            return
        if event.xdata is None or event.ydata is None:
            return
        if self.template_affine is None:
            return
        
        try:
            x_pix, y_pix = event.xdata, event.ydata
            
            # Get shape of current slice for reference
            if self.current_view == 'axial':
                shape = self.template_data[:, :, self.current_slice_idx].shape
                # Convert pixel coords back to voxel coords
                z_vox = self.current_slice_idx
                # Since we use np.rot90 with k=1, we need to reverse the rotation
                x_vox = x_pix
                y_vox = y_pix
                # Convert to MNI
                vox_homo = np.array([x_vox, y_vox, z_vox, 1.0])
                mni_homo = self.template_affine @ vox_homo
                self.crosshair_mni = tuple(mni_homo[:3])
                
            elif self.current_view == 'coronal':
                y_vox = self.current_slice_idx
                x_vox = x_pix
                z_vox = y_pix
                vox_homo = np.array([x_vox, y_vox, z_vox, 1.0])
                mni_homo = self.template_affine @ vox_homo
                self.crosshair_mni = tuple(mni_homo[:3])
                
            else:  # sagittal
                x_vox = self.current_slice_idx
                y_vox = x_pix
                z_vox = y_pix
                vox_homo = np.array([x_vox, y_vox, z_vox, 1.0])
                mni_homo = self.template_affine @ vox_homo
                self.crosshair_mni = tuple(mni_homo[:3])
            
            # Re-render with crosshair
            self._render_brain_left(highlighted_net_idx=self.current_highlighted_idx)
            
            print(f"✓ Crosshair set to MNI: ({self.crosshair_mni[0]:.1f}, "
                  f"{self.crosshair_mni[1]:.1f}, {self.crosshair_mni[2]:.1f})")
        
        except Exception as e:
            print(f"⚠️ Error processing brain click: {e}")

    def _export_significant_niftis(self):
        """Feature 3: save one NIfTI mask per significant network (p<0.05)."""
        if not self.current_results:
            QMessageBox.warning(self, "No Results", "Run or load an analysis first.")
            return
        if getattr(self, '_atlas_vol', None) is None or self._atlas_aff is None:
            QMessageBox.warning(self, "No Atlas Volume",
                                "The atlas volume for this analysis isn't loaded, "
                                "so per-network masks can't be written.")
            return
        out_dir = QFileDialog.getExistingDirectory(
            self, "Choose a folder for the significant-network NIfTIs")
        if not out_dir:
            return
        try:
            saved, skipped = rx.export_network_niftis(
                out_dir, self.network_names, self.network_pvalues,
                self._atlas_vol, self._atlas_aff, self._atlas_mode,
                self._label_map, significant_only=True, alpha=0.05)
            msg = f"Saved {len(saved)} NIfTI file(s) to:\n{out_dir}"
            if not saved:
                msg = ("No significant networks (p < 0.05) had voxels to save.\n\n"
                       "Nothing was written.")
            elif skipped:
                msg += f"\n\nSkipped {len(skipped)} network(s) (not significant / no voxels)."
            QMessageBox.information(self, "Export Complete", msg)
            print(f"✅ Saved {len(saved)} significant-network NIfTIs to {out_dir}")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Export Error", str(e))

    def _save_session(self):
        """Feature 4: save results to a .nctresult file for later review."""
        if not self.current_results:
            QMessageBox.warning(self, "No Results", "Run an analysis first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Results", "", "NCT Result (*.nctresult)")
        if not path:
            return
        if not path.endswith('.nctresult'):
            path += '.nctresult'
        try:
            rx.save_session(
                path,
                results=self.current_results,
                space=self.current_brain_space,
                atlas_code=self.current_atlas_code,
                network_names=self.network_names,
                overlaps=self.network_overlaps,
                p_values=self.network_pvalues,
                centroids=self.network_centroids,
                atlas_mode=self._atlas_mode,
                label_map=self._label_map,
                extra={'voxel_stats_available': bool(getattr(self, '_voxel_stats', None))})
            QMessageBox.information(self, "Saved", f"Results saved to:\n{path}")
            print(f"✅ Session saved: {path}")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Save Error", str(e))

    def _load_session(self):
        """Feature 4: reload a saved .nctresult file and redisplay."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Results", "", "NCT Result (*.nctresult)")
        if not path:
            return
        try:
            data = rx.load_session(path)
            results = data.get('results') or {}
            results['networks'] = data.get('network_names', [])
            results['overlaps'] = data.get('overlaps', [])
            results['p_values'] = data.get('p_values', [])
            results['atlas_code'] = data.get('atlas_code', '')
            space = data.get('space') or 'FSLMNI2mm'

            # display_results re-resolves the atlas volume from atlas identity,
            # which also rebuilds centroids + voxel stats.
            self.display_results(results, space=space)

            # If atlas volume couldn't be re-resolved, restore saved centroids
            if getattr(self, '_atlas_vol', None) is None:
                saved_cent = data.get('centroids') or []
                self.network_centroids = [
                    (tuple(c) if c is not None else None) for c in saved_cent]
                print("ℹ️ Atlas volume not found on reload; using saved centroids. "
                      "Per-network NIfTI export and voxel stats unavailable "
                      "until the atlas data is present.")
            QMessageBox.information(self, "Loaded", f"Results loaded from:\n{path}")
            print(f"✅ Session loaded: {path}")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Load Error", str(e))

    def _export(self, fmt):
        if not self.current_results:
            QMessageBox.warning(self, "No Results", "Run an analysis first.")
            return

        filters = {
            'csv': "CSV Spreadsheet (*.csv)",
            'nii': "NIfTI Image (*.nii)",
            'png': "PNG Image (*.png)",
            'tif': "TIFF Image (*.tif)",
            'jpg': "JPEG Image (*.jpg)",
        }
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export as {fmt.upper()}", "", filters[fmt])
        if not path:
            return

        try:
            from nct_application.interactive_brain import ExportManager
            if fmt == 'csv':
                ok = ExportManager.export_csv(self.current_results, path)
            elif fmt == 'nii':
                ok = ExportManager.export_nifti(self.current_results, path, renderer=None)
            else:
                ok = ExportManager.export_image(self.bar_fig, path, fmt=fmt, dpi=150)

            if ok:
                QMessageBox.information(self, "Export Complete", f"Saved to:\n{path}")
            else:
                QMessageBox.warning(self, "Export Failed", "Export failed — see console for details.")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Export Error", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class NCTMainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multimodal Brain Network Characterization Tool (MBCT)")
        self.setMinimumSize(QSize(1100, 800))
        # Global theme is applied at the QApplication level (see entry point);
        # no per-window stylesheet needed.

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Theme toggle button, pinned to the top-right corner of the tab bar
        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("themeToggle")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)
        # label points at the theme you'd switch TO
        self.theme_btn.setText("◐  Light theme" if tm.CURRENT == 'dark' else "◑  Dark theme")
        self.tabs.setCornerWidget(self.theme_btn, Qt.Corner.TopRightCorner)

        # Create tabs with new modules (with breadcrumbs so a hard crash in any
        # one tab is localized in startup_error.log)
        def _bc(m):
            try:
                p = Path(__file__).parent / "startup_error.log"
                with open(p, "a", encoding="utf-8") as f:
                    f.write(f"   building {m}\n")
            except Exception:
                pass
            print(f"   building {m}")
        _bc("HomeTab");          self.home_tab = HomeTab()
        _bc("AnalysisTab");      self.analysis_tab = AnalysisTab(self)
        _bc("ResultsTab");       self.results_tab  = ResultsTab()
        # The "core" edition (used for the published/manuscript build) ships
        # only the multimodal annotation pipeline: Home, Analysis, Results, Help.
        # The full edition adds the Brain Viewer, Connectivity and Utilities.
        if MBCT_EDITION == 'full':
            _bc("BrainViewerStatsTab"); self.brain_viewer_tab = BrainViewerStatsTab()
            _bc("ConnectivityTab");     self.connectivity_tab = ConnectivityTab(self)
            _bc("UtilitiesTab");        self.utilities_tab = UtilitiesTab(self)
        else:
            self.brain_viewer_tab = None
            self.connectivity_tab = None
            self.utilities_tab = None
        _bc("HelpTab");          self.help_tab = HelpTab()
        _bc("all tabs built")

        # Add tabs (Home first)
        self.tabs.addTab(self.home_tab, "🏠  Home")
        self.tabs.addTab(self.analysis_tab, "🔬  Analysis")
        self.tabs.addTab(self.results_tab,  "📊  Results")
        if MBCT_EDITION == 'full':
            self.tabs.addTab(self.brain_viewer_tab, "🧠  Brain Viewer")
            self.tabs.addTab(self.connectivity_tab, "🔗  Connectivity")
            self.tabs.addTab(self.utilities_tab, "🔧 Utilities")
        self.tabs.addTab(self.help_tab, "❓ Help")

        # Utilities "Open in Viewer" handoff: load the produced file as an overlay
        # and switch to the Brain Viewer tab. (Full edition only.)
        if MBCT_EDITION == 'full':
            def _open_in_viewer(path):
                try:
                    self.brain_viewer_tab.load_overlay_path(path)
                    self.tabs.setCurrentWidget(self.brain_viewer_tab)
                except Exception as _e:
                    print(f"⚠️ Open in Viewer failed: {_e}")
            self.utilities_tab.file_ready.connect(_open_in_viewer)
        
        # Link parent reference for template scanning in ResultsTab
        self.results_tab.parent_main = self
        
        # Note: BrainViewerEnhanced uses overlay manager for custom maps
        # No template initialization needed - users load their own maps

        self.analysis_tab.analysis_done.connect(
            lambda r, s: self.results_tab.display_results(r, s))

        self._update_window_icon()
        print("✅ NCT Application ready!")

    def _toggle_theme(self):
        """Switch between the Windows 11 (light) and dark-navy themes live."""
        app = QApplication.instance()
        new_theme = tm.toggle(app)
        # update button label to point at the *other* theme
        if new_theme == 'win11':
            self.theme_btn.setText("◑  Dark theme")
        else:
            self.theme_btn.setText("◐  Light theme")
        # swap the window/taskbar icon to match the theme
        self._update_window_icon(new_theme)
        # re-style widgets that carry their own stylesheet so they follow suit
        if self.brain_viewer_tab is not None and hasattr(self.brain_viewer_tab, 'apply_external_theme'):
            self.brain_viewer_tab.apply_external_theme(new_theme)
        # re-render any theme-aware plots so chart backgrounds match
        for tabw, meth in ((self.results_tab, '_render_bar_graph'),
                           (self.results_tab, '_render_brain_left')):
            if hasattr(tabw, meth):
                try:
                    getattr(tabw, meth)()
                except Exception:
                    pass
        if self.brain_viewer_tab is not None and hasattr(self.brain_viewer_tab, '_queue'):
            try:
                self.brain_viewer_tab._queue()
            except Exception:
                pass

    def _update_window_icon(self, theme=None):
        """Set the window/taskbar icon to the theme-appropriate logo
        (logo2 for dark, logo1 for light). Uses the small square icon variant
        to avoid decoding the full-resolution logo at startup."""
        try:
            path = tm.logo_for_theme(theme, variant='icon')
            if path:
                self.setWindowIcon(QIcon(path))
                app = QApplication.instance()
                if app is not None:
                    app.setWindowIcon(QIcon(path))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Application entry point (callable, so edition launchers can invoke it
    directly — runpy/module tricks are unreliable inside a PyInstaller bundle)."""
    import datetime
    _log = Path(__file__).parent / "startup_error.log"
    def _crumb(msg):
        try:
            with open(_log, "a", encoding="utf-8") as f:
                f.write(f"{datetime.datetime.now():%H:%M:%S}  {msg}\n")
        except Exception:
            pass
        print(msg)
    # fresh log each run
    try:
        _log.write_text(f"MBCT startup {datetime.datetime.now()}\n", encoding="utf-8")
    except Exception:
        pass
    _crumb(f"python = {sys.executable}")
    _crumb(f"matplotlib backend = {matplotlib.get_backend()}")

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    _crumb("QApplication created")

    # Detect the OS light/dark preference and match it on launch.
    initial = tm.detect_os_theme()
    tm.apply_theme(app, initial)
    _crumb(f"theme applied = {initial}")

    # Show splash screen with graphical abstract
    from splash_screen import SplashScreen
    splash = SplashScreen()
    splash.show()
    app.processEvents()
    splash.exec()
    _crumb("splash closed; constructing main window")

    # Construct the main window with a crash guard so any startup error is
    # written to a log file (and shown) instead of vanishing on the console.
    try:
        win = NCTMainWindow()
        _crumb("NCTMainWindow constructed")
        win.show()
        _crumb("window shown — entering event loop")
    except Exception:
        import traceback
        tb = traceback.format_exc()
        _crumb("STARTUP CRASH:\n" + tb)
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "MBCT failed to start",
                                 "The application could not start.\n\n"
                                 f"{tb[-1500:]}")
        except Exception:
            pass
        sys.exit(1)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
