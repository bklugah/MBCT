"""
White Matter Analysis Tab
Analyzes white matter using white matter tract atlases
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QComboBox, QProgressBar, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from pathlib import Path
import traceback

from nct_application.white_matter_analysis import WhiteMatterAnalysis
from nct_application.white_matter_config import WhiteMatterConfig

class WhiteMatterWorkerThread(QThread):
    """Worker thread for white matter analysis."""
    
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, dict)
    
    def __init__(self, wm_analysis, input_file, atlas_code):
        super().__init__()
        self.wm_analysis = wm_analysis
        self.input_file = input_file
        self.atlas_code = atlas_code
    
    def run(self):
        try:
            self.progress.emit("🔄 Analyzing white matter...")
            results = self.wm_analysis.analyze_white_matter(
                self.input_file,
                self.atlas_code
            )
            self.finished.emit(True, results)
        except Exception as e:
            self.finished.emit(False, {'error': str(e)})

class WhiteMatterTab(QWidget):
    """Tab for white matter analysis."""
    
    def __init__(self):
        super().__init__()
        self.input_file = None
        self.wm_analysis = None
        self.worker_thread = None
        self._build()
        self._init_analysis()
    
    def _init_analysis(self):
        """Initialize white matter analysis."""
        atlas_dir = WhiteMatterConfig.get_atlas_dir()
        if atlas_dir:
            self.wm_analysis = WhiteMatterAnalysis(atlas_dir)
            self.lbl_status.setText("✅ White matter atlases loaded")
        else:
            self.lbl_status.setText("⚠️  White matter atlases not found")
    
    def _build(self):
        """Build the white matter analysis UI."""
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)
        
        # Title
        title = QLabel("🧬 White Matter Analysis")
        title.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
        title.setStyleSheet("color:#38b6ff;")
        root.addWidget(title)
        
        # Description
        desc = QLabel(
            "Analyze white matter using tract atlases.\n"
            "Supports: ICBM White Matter Probability Map, JHU-ICBM Tracts"
        )
        desc.setFont(QFont('Segoe UI', 9))
        desc.setStyleSheet("color:#b0b0c8;")
        root.addWidget(desc)
        
        # File selection
        file_row = QHBoxLayout()
        file_row.setSpacing(6)
        
        lbl_file = QLabel("📄 White Matter Image:")
        lbl_file.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        lbl_file.setStyleSheet("color:#7090b8;")
        file_row.addWidget(lbl_file)
        
        self.lbl_file = QLabel("(No file selected)")
        self.lbl_file.setFont(QFont('Consolas', 9))
        self.lbl_file.setStyleSheet("color:#a0a0b8;")
        file_row.addWidget(self.lbl_file)
        
        btn_browse = QPushButton("Browse...")
        btn_browse.setMaximumWidth(100)
        btn_browse.setMinimumHeight(28)
        btn_browse.clicked.connect(self._select_file)
        file_row.addWidget(btn_browse)
        
        file_row.addStretch()
        root.addLayout(file_row)
        
        # Atlas selection
        atlas_row = QHBoxLayout()
        atlas_row.setSpacing(6)
        
        lbl_atlas = QLabel("🗺️  Select Atlas:")
        lbl_atlas.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        lbl_atlas.setStyleSheet("color:#7090b8;")
        atlas_row.addWidget(lbl_atlas)
        
        self.combo_atlas = QComboBox()
        self.combo_atlas.setMinimumWidth(300)
        self.combo_atlas.setMinimumHeight(28)
        
        # Populate atlases
        if self.wm_analysis:
            for atlas_code, atlas_name in self.wm_analysis.get_available_atlases().items():
                self.combo_atlas.addItem(f"{atlas_name} ({atlas_code})", atlas_code)
        else:
            self.combo_atlas.addItem("(No atlases available)", None)
        
        atlas_row.addWidget(self.combo_atlas)
        atlas_row.addStretch()
        root.addLayout(atlas_row)
        
        # Analyze button
        btn_analyze = QPushButton("🔬 Analyze White Matter")
        btn_analyze.setMinimumHeight(36)
        btn_analyze.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        btn_analyze.setStyleSheet(
            "background:#1a4a8a; color:#ffffff; border:1px solid #2a5aaa; "
            "border-radius:4px; padding:6px;"
        )
        btn_analyze.clicked.connect(self._analyze)
        root.addWidget(btn_analyze)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(24)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background: #0a0a14; border: 1px solid #2a2a44; "
            "border-radius: 4px; } "
            "QProgressBar::chunk { background: #38b6ff; }"
        )
        root.addWidget(self.progress_bar)
        
        # Results display
        lbl_results = QLabel("📊 Analysis Results:")
        lbl_results.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
        lbl_results.setStyleSheet("color:#38b6ff;")
        root.addWidget(lbl_results)
        
        self.text_results = QTextEdit()
        self.text_results.setReadOnly(True)
        self.text_results.setMinimumHeight(200)
        self.text_results.setFont(QFont('Consolas', 8))
        self.text_results.setStyleSheet("background:#0c0c1a; border:1px solid #2a2a44; border-radius:4px;")
        root.addWidget(self.text_results)
        
        # Status
        self.lbl_status = QLabel("Initializing...")
        self.lbl_status.setFont(QFont('Segoe UI', 9))
        self.lbl_status.setStyleSheet("color:#7090b0;")
        root.addWidget(self.lbl_status)
        
        root.addStretch()
    
    def _select_file(self):
        """Select white matter image file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select White Matter Image (FA, MD, etc.)",
            "",
            "NIfTI Files (*.nii *.nii.gz);;All Files (*)"
        )
        
        if file_path:
            self.input_file = file_path
            self.lbl_file.setText(str(Path(file_path).name))
    
    def _analyze(self):
        """Run white matter analysis."""
        if not self.input_file:
            QMessageBox.warning(self, "Error", "Please select a white matter image file")
            return
        
        if not self.wm_analysis:
            QMessageBox.warning(self, "Error", "White matter atlases not initialized")
            return
        
        atlas_code = self.combo_atlas.currentData()
        if not atlas_code:
            QMessageBox.warning(self, "Error", "Please select an atlas")
            return
        
        # Clear results
        self.text_results.clear()
        self.progress_bar.setVisible(True)
        
        # Run analysis in thread
        self.worker_thread = WhiteMatterWorkerThread(
            self.wm_analysis,
            self.input_file,
            atlas_code
        )
        self.worker_thread.progress.connect(self._log)
        self.worker_thread.finished.connect(self._on_analysis_complete)
        self.worker_thread.start()
    
    def _log(self, msg):
        """Add log message."""
        self.text_results.append(msg)
    
    def _on_analysis_complete(self, success, results):
        """Handle analysis completion."""
        self.progress_bar.setVisible(False)
        
        if success:
            self._display_results(results)
            QMessageBox.information(self, "✅ Analysis Complete", "White matter analysis finished")
        else:
            error_msg = results.get('error', 'Unknown error')
            self.text_results.setText(f"❌ Analysis failed:\n{error_msg}")
            QMessageBox.warning(self, "❌ Analysis Failed", f"Error: {error_msg}")
    
    def _display_results(self, results):
        """Display analysis results."""
        output = []
        output.append(f"✅ Analysis Complete\n")
        output.append(f"Atlas: {results.get('atlas', 'Unknown')}")
        output.append(f"Input: {Path(results.get('input_file', '')).name}")
        output.append(f"Shape: {results.get('input_shape', 'Unknown')}\n")
        
        if 'error' in results:
            output.append(f"❌ Error: {results['error']}")
        else:
            summary = results.get('summary', {})
            output.append("📊 Summary:")
            for key, value in summary.items():
                output.append(f"  {key}: {value}")
            
            tracts = results.get('tracts', {})
            if tracts:
                output.append(f"\n📍 Detected {len(tracts)} tracts with overlap:")
                for tract_name, tract_data in list(tracts.items())[:10]:
                    dice = tract_data.get('dice', 0)
                    output.append(f"  {tract_name}: {dice:.4f}")
                if len(tracts) > 10:
                    output.append(f"  ... and {len(tracts) - 10} more")
        
        self.text_results.setText('\n'.join(output))
