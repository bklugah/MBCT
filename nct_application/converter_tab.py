"""
Converter Utility Tab
Allows users to convert NIfTI files to standard dimensions
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QComboBox, QProgressBar, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from pathlib import Path
import traceback

from nct_application.nifti_converter import NiftiConverter
from nct_application.white_matter_config import WhiteMatterConfig

class ConverterThread(QThread):
    """Worker thread for NIfTI conversion."""
    
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, input_path, output_path, target_shape):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.target_shape = target_shape
    
    def run(self):
        try:
            self.progress.emit("🔄 Starting conversion...")
            success, msg = NiftiConverter.resample_to_target(
                self.input_path,
                self.output_path,
                self.target_shape,
                interpolation='linear'
            )
            self.finished.emit(success, msg)
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")

class ConverterTab(QWidget):
    """Utility tab for converting NIfTI files."""
    
    def __init__(self):
        super().__init__()
        self.input_file = None
        self.converter_thread = None
        self._build()
    
    def _build(self):
        """Build the converter UI."""
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)
        
        # Title
        title = QLabel("🧠 NIfTI Dimension Converter")
        title.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
        title.setStyleSheet("color:#38b6ff;")
        root.addWidget(title)
        
        # Description
        desc = QLabel(
            "Convert NIfTI files to standard dimensions.\n"
            "Useful for preprocessing files that don't match atlas requirements."
        )
        desc.setFont(QFont('Segoe UI', 9))
        desc.setStyleSheet("color:#b0b0c8;")
        root.addWidget(desc)
        
        # Input file selection
        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        
        lbl_input = QLabel("📁 Input NIfTI File:")
        lbl_input.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        lbl_input.setStyleSheet("color:#7090b8;")
        input_row.addWidget(lbl_input)
        
        self.lbl_input_file = QLabel("(No file selected)")
        self.lbl_input_file.setFont(QFont('Consolas', 9))
        self.lbl_input_file.setStyleSheet("color:#a0a0b8;")
        input_row.addWidget(self.lbl_input_file)
        
        btn_browse = QPushButton("Browse...")
        btn_browse.setMaximumWidth(100)
        btn_browse.setMinimumHeight(28)
        btn_browse.clicked.connect(self._select_input_file)
        input_row.addWidget(btn_browse)
        
        input_row.addStretch()
        root.addLayout(input_row)
        
        # Input info
        self.lbl_input_info = QLabel("Dimensions: (unknown)")
        self.lbl_input_info.setFont(QFont('Consolas', 8))
        self.lbl_input_info.setStyleSheet("color:#808090;")
        root.addWidget(self.lbl_input_info)
        
        # Tissue Type Selection
        tissue_row = QHBoxLayout()
        tissue_row.setSpacing(6)
        
        lbl_tissue = QLabel("🧬 Tissue Type:")
        lbl_tissue.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        lbl_tissue.setStyleSheet("color:#7090b8;")
        tissue_row.addWidget(lbl_tissue)
        
        self.tissue_combo = QComboBox()
        self.tissue_combo.addItems(["Gray Matter", "White Matter"])
        self.tissue_combo.setMinimumWidth(150)
        self.tissue_combo.setMinimumHeight(28)
        self.tissue_combo.currentIndexChanged.connect(self._on_tissue_changed)
        tissue_row.addWidget(self.tissue_combo)
        
        tissue_row.addStretch()
        root.addLayout(tissue_row)
        
        # Tissue info
        self.lbl_tissue_info = QLabel("🧠 Gray Matter: Standard cortical and subcortical parcellations")
        self.lbl_tissue_info.setFont(QFont('Consolas', 8))
        self.lbl_tissue_info.setStyleSheet("color:#808090;")
        root.addWidget(self.lbl_tissue_info)
        
        # Atlas dimensions info box
        self.atlas_dims_box = QTextEdit()
        self.atlas_dims_box.setReadOnly(True)
        self.atlas_dims_box.setMaximumHeight(120)
        self.atlas_dims_box.setFont(QFont('Consolas', 8))
        self.atlas_dims_box.setStyleSheet("""
            QTextEdit {
                background-color: #0a0e27;
                color: #7dd3fc;
                border: 1px solid #1e3a5f;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        self._update_atlas_dims_display()
        root.addWidget(self.atlas_dims_box)
        
        # Target dimension selection
        dim_row = QHBoxLayout()
        dim_row.setSpacing(6)
        
        lbl_dim = QLabel("🎯 Target Dimension:")
        lbl_dim.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        lbl_dim.setStyleSheet("color:#7090b8;")
        dim_row.addWidget(lbl_dim)
        
        self.combo_dim = QComboBox()
        self.combo_dim.setMinimumWidth(300)
        self.combo_dim.setMinimumHeight(28)
        
        # Populate dimensions with space information
        dimension_map = {
            'FSLMNI2mm': ('(91, 109, 91)', '91×109×91 - MNI152 Standard'),
            'FSLMNI1mm': ('(182, 218, 182)', '182×218×182 - MNI152 1mm'),
            'FSLMNI4mm': ('(46, 55, 46)', '46×55×46 - MNI152 4mm'),
            'MNI_2mm': ('(91, 109, 91)', '91×109×91 - Standard MNI'),
        }
        
        for space_code, (shape_tuple, display_text) in dimension_map.items():
            self.combo_dim.addItem(display_text, space_code)
        
        self.combo_dim.currentIndexChanged.connect(self._on_dimension_changed)
        dim_row.addWidget(self.combo_dim)
        dim_row.addStretch()
        root.addLayout(dim_row)
        
        # Target info with SPACE information
        self.lbl_target_info = QLabel("🎯 Target: FSLMNI2mm (91×109×91) - For: MG360J12, AL20, TY7, White Matter Atlases")
        self.lbl_target_info.setFont(QFont('Consolas', 8))
        self.lbl_target_info.setStyleSheet("color:#808090;")
        root.addWidget(self.lbl_target_info)
        
        # Output file selection
        output_row = QHBoxLayout()
        output_row.setSpacing(6)
        
        lbl_output = QLabel("💾 Output Location:")
        lbl_output.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        lbl_output.setStyleSheet("color:#7090b8;")
        output_row.addWidget(lbl_output)
        
        self.lbl_output_file = QLabel("(Same as input directory)")
        self.lbl_output_file.setFont(QFont('Consolas', 9))
        self.lbl_output_file.setStyleSheet("color:#a0a0b8;")
        output_row.addWidget(self.lbl_output_file)
        
        btn_output = QPushButton("Browse...")
        btn_output.setMaximumWidth(100)
        btn_output.setMinimumHeight(28)
        btn_output.clicked.connect(self._select_output_dir)
        output_row.addWidget(btn_output)
        
        output_row.addStretch()
        root.addLayout(output_row)
        
        # Convert button
        btn_convert = QPushButton("🔄 Convert NIfTI")
        btn_convert.setMinimumHeight(36)
        btn_convert.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        btn_convert.setStyleSheet(
            "background:#1a4a8a; color:#ffffff; border:1px solid #2a5aaa; "
            "border-radius:4px; padding:6px;"
        )
        btn_convert.clicked.connect(self._convert)
        root.addWidget(btn_convert)
        
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
        
        # Status/log
        lbl_status = QLabel("📋 Conversion Log:")
        lbl_status.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
        lbl_status.setStyleSheet("color:#38b6ff;")
        root.addWidget(lbl_status)
        
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setMaximumHeight(150)
        self.text_log.setFont(QFont('Consolas', 8))
        self.text_log.setStyleSheet("background:#0c0c1a; border:1px solid #2a2a44; border-radius:4px;")
        root.addWidget(self.text_log)
        
        root.addStretch()
    
    def _select_input_file(self):
        """Select input NIfTI file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select NIfTI File",
            "",
            "NIfTI Files (*.nii *.nii.gz);;All Files (*)"
        )
        
        if file_path:
            self.input_file = file_path
            self.lbl_input_file.setText(str(Path(file_path).name))
            
            # Get dimensions
            shape = NiftiConverter.get_dimensions(file_path)
            if shape:
                self.lbl_input_info.setText(f"Dimensions: {shape}")
            else:
                self.lbl_input_info.setText("Dimensions: (error reading file)")
    
    def _select_output_dir(self):
        """Select output directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory"
        )
        
        if dir_path:
            self.lbl_output_file.setText(str(Path(dir_path).name))
    
    def _on_tissue_changed(self):
        """Update displayed atlases and dimensions based on tissue type."""
        tissue_type = self.tissue_combo.currentText()
        
        if tissue_type == "Gray Matter":
            self.lbl_tissue_info.setText(
                "🧠 Gray Matter: 23 cortical and subcortical atlases"
            )
        else:
            self.lbl_tissue_info.setText(
                "⚪ White Matter: 2 white matter atlases (ICBM_Wmpm, JHU-ICBM)"
            )
        
        # Update atlas dimensions display
        self._update_atlas_dims_display()
        
        # Update dimension dropdown for tissue type
        self._update_dimension_combo_for_tissue()
        
        # Update dimension info to show available atlases
        self._on_dimension_changed()
    
    def _update_atlas_dims_display(self):
        """Display atlas dimensions and formats"""
        tissue_type = self.tissue_combo.currentText()
        
        if tissue_type == "Gray Matter":
            info = """📊 GRAY MATTER ATLASES (23 total)

FSLMNI2mm (91×109×91):
  • Resolution: 2mm voxels
  • Voxel size: 2×2×2 mm
  • All 23 gray matter atlases
  
FSLMNI1mm (182×218×182):
  • Resolution: 1mm voxels
  • Selected atlases available"""
        else:  # White Matter
            info = """📊 WHITE MATTER ATLASES

JHU-ICBM ONLY (182×218×182):
  • Resolution: 1mm voxels
  • Voxel size: 1×1×1 mm
  
  Components:
  • 48 labeled white matter regions
  • 20 probabilistic fiber tracts
  
⚠️ All white matter files are 1mm resolution
   Must convert to FSLMNI1mm (182×218×182)"""
        
        self.atlas_dims_box.setText(info)
    
    def _update_dimension_combo_for_tissue(self):
        """Update dimension dropdown based on tissue type"""
        tissue_type = self.tissue_combo.currentText()
        current_data = self.combo_dim.currentData()
        
        self.combo_dim.blockSignals(True)
        self.combo_dim.clear()
        
        if tissue_type == "Gray Matter":
            self.combo_dim.addItem("FSLMNI2mm (91×109×91)", "FSLMNI2mm")
            self.combo_dim.addItem("FSLMNI1mm (182×218×182)", "FSLMNI1mm")
            self.combo_dim.addItem("FSLMNI4mm (46×55×46)", "FSLMNI4mm")
            self.combo_dim.addItem("MNI 2mm (91×109×91)", "MNI_2mm")
        else:  # White Matter
            # ✅ ONLY FSLMNI1mm for white matter (JHU-ICBM is 1mm only)
            self.combo_dim.addItem("⚠️ FSLMNI1mm (182×218×182) - REQUIRED for JHU-ICBM", "FSLMNI1mm")
        
        # Try to restore previous selection
        if current_data and tissue_type == "Gray Matter":
            idx = self.combo_dim.findData(current_data)
            if idx >= 0:
                self.combo_dim.setCurrentIndex(idx)
        
        self.combo_dim.blockSignals(False)
    
    def _on_dimension_changed(self):
        """Update target dimension info and show compatible atlases."""
        space_code = self.combo_dim.currentData()
        
        # Map space to ACTUALLY AVAILABLE atlases (ALL 23 gray matter + 2 white matter)
        space_to_atlases = {
            'FSLMNI2mm': {
                'gray': [
                    'MG360J12', 'HCPICA', 'AL20', 'UKBICA',
                    'AS400K17', 'AS200K17', 'AS400Y17', 'AS200Y17',
                    'XS268_8', 'XS368_8', 'WS90_14',
                    'EG286_12', 'TL12', 'EG17', 'EG5',
                    'TY7', 'TY17',
                    'XY200K17', 'XY200Y17', 'XY400K17', 'XY400Y17',
                    'TW_TASK_NETS', 'DU15NET',
                ],
                'white': ['JHU-ICBM']
            },
            'FSLMNI1mm': {
                'gray': [
                    'MG360J12', 'HCPICA', 'AL20', 'UKBICA',
                    'AS400K17', 'AS200K17', 'AS400Y17', 'AS200Y17',
                    'XS268_8', 'XS368_8', 'WS90_14',
                    'EG286_12', 'TL12', 'EG17', 'EG5',
                    'TY7', 'TY17',
                    'XY200K17', 'XY200Y17', 'XY400K17', 'XY400Y17',
                    'TW_TASK_NETS', 'DU15NET',
                ],
                'white': ['JHU-ICBM']
            },
            'FSLMNI4mm': {
                'gray': [
                    'MG360J12', 'HCPICA', 'AL20', 'UKBICA',
                    'AS400K17', 'AS200K17', 'AS400Y17', 'AS200Y17',
                    'XS268_8', 'XS368_8', 'WS90_14',
                    'EG286_12', 'TL12', 'EG17', 'EG5',
                    'TY7', 'TY17',
                    'XY200K17', 'XY200Y17', 'XY400K17', 'XY400Y17',
                    'TW_TASK_NETS', 'DU15NET',
                ],
                'white': ['JHU-ICBM']
            },
            'MNI_2mm': {
                'gray': [
                    'MG360J12', 'HCPICA', 'AL20', 'UKBICA',
                    'AS400K17', 'AS200K17', 'AS400Y17', 'AS200Y17',
                    'XS268_8', 'XS368_8', 'WS90_14',
                    'EG286_12', 'TL12', 'EG17', 'EG5',
                    'TY7', 'TY17',
                    'XY200K17', 'XY200Y17', 'XY400K17', 'XY400Y17',
                    'TW_TASK_NETS', 'DU15NET',
                ],
                'white': ['JHU-ICBM']
            },
        }
        
        info = WhiteMatterConfig.get_dimension_info(space_code)
        shape = info.get('shape', (0, 0, 0))
        
        atlases = space_to_atlases.get(space_code, {'gray': [], 'white': []})
        gray_atlases = ', '.join(atlases['gray'])
        white_atlases = ', '.join(atlases['white'])
        
        info_text = (
            f"🎯 Target: {space_code} {shape}\n"
            f"📊 Available Gray Matter: {gray_atlases}\n"
            f"⚪ Available White Matter: {white_atlases}"
        )
        self.lbl_target_info.setText(info_text)
    
    def _convert(self):
        """Start conversion."""
        if not self.input_file:
            QMessageBox.warning(self, "Error", "Please select an input file")
            return
        
        # Get target dimension
        dim_code = self.combo_dim.currentData()
        info = WhiteMatterConfig.get_dimension_info(dim_code)
        target_shape = info.get('shape', (91, 109, 91))
        
        # Determine output path
        input_path = Path(self.input_file)
        output_dir = Path(self.lbl_output_file.text()) if self.lbl_output_file.text() != "(Same as input directory)" else input_path.parent
        output_path = output_dir / f"{input_path.stem}_converted_{dim_code}.nii.gz"
        
        # Log
        self.text_log.clear()
        self._log(f"📂 Input: {input_path.name}")
        self._log(f"📂 Output: {output_path.name}")
        self._log(f"🎯 Target: {target_shape}")
        self._log(f"\n🔄 Starting conversion...\n")
        
        # Start conversion thread
        self.converter_thread = ConverterThread(
            str(self.input_file),
            str(output_path),
            target_shape
        )
        self.converter_thread.progress.connect(self._log)
        self.converter_thread.finished.connect(self._on_conversion_complete)
        
        self.progress_bar.setVisible(True)
        self.converter_thread.start()
    
    def _log(self, msg):
        """Add log message."""
        self.text_log.append(msg)
    
    def _on_conversion_complete(self, success, msg):
        """Handle conversion completion."""
        self.progress_bar.setVisible(False)
        self._log(msg)
        
        if success:
            QMessageBox.information(
                self,
                "✅ Conversion Complete",
                f"File successfully converted!\n\nMessage: {msg}"
            )
        else:
            QMessageBox.warning(
                self,
                "❌ Conversion Failed",
                f"Conversion failed!\n\nMessage: {msg}"
            )
