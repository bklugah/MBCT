"""Utility Tab for brain space detection and conversion"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QTextEdit, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from nct_application.cbig_analysis import BrainSpaceDetector


class UtilityTab(QWidget):
    """Utility tab for space detection and conversion"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("🔧 Utilities")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #00d4ff;")
        layout.addWidget(title)
        
        # Space Detection Section
        detection_frame = self.create_detection_section()
        layout.addWidget(detection_frame)
        
        # Conversion Section (future)
        conversion_frame = self.create_conversion_section()
        layout.addWidget(conversion_frame)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def create_detection_section(self):
        """Create brain space detection section"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border: 1px solid #343548;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        
        # Header
        header = QLabel("Brain Space Detector")
        header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header.setStyleSheet("color: #00d4ff;")
        layout.addWidget(header)
        
        # Description
        desc = QLabel(
            "Upload a NIfTI file to detect its brain space.\n"
            "Supported spaces: fs_LR_32k, fsaverage6, FSLMNI2mm"
        )
        desc.setFont(QFont("Segoe UI", 10))
        desc.setStyleSheet("color: #a0a0a0;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # File selection
        file_layout = QHBoxLayout()
        self.space_file_label = QLabel("No file selected")
        self.space_file_label.setStyleSheet("color: #808080; font-style: italic;")
        file_layout.addWidget(self.space_file_label)
        
        browse_btn = QPushButton("📂 Browse")
        browse_btn.setMaximumWidth(150)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a3e;
                color: #e0e0e0;
                border: 1px solid #00d4ff;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #3a3a4e;
            }
        """)
        browse_btn.clicked.connect(self.browse_file_for_detection)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)
        
        # Results
        self.space_result = QTextEdit()
        self.space_result.setReadOnly(True)
        self.space_result.setMaximumHeight(150)
        self.space_result.setStyleSheet("""
            QTextEdit {
                background-color: #0f0f1e;
                color: #00d4ff;
                border: 1px solid #343548;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Courier New';
                font-size: 10pt;
            }
        """)
        self.space_result.setPlaceholderText("Detection results will appear here...")
        layout.addWidget(self.space_result)
        
        return frame
    
    def create_conversion_section(self):
        """Create (future) space conversion section"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border: 1px solid #343548;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        
        # Header
        header = QLabel("Space Conversion (Coming Soon)")
        header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header.setStyleSheet("color: #ffaa00;")
        layout.addWidget(header)
        
        # Placeholder
        desc = QLabel(
            "Convert between brain spaces using FSL or Workbench tools.\n\n"
            "Supported conversions:\n"
            "• FSLMNI2mm ↔ fsaverage6 (via Workbench)\n"
            "• FSLMNI2mm ↔ fs_LR_32k (via Workbench)\n\n"
            "Feature coming in next release..."
        )
        desc.setFont(QFont("Segoe UI", 10))
        desc.setStyleSheet("color: #a0a0a0;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        return frame
    
    def browse_file_for_detection(self):
        """Browse and detect space of a NIfTI file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select NIfTI file to detect space",
            "",
            "NIfTI files (*.nii *.nii.gz);;All files (*)"
        )
        
        if not file_path:
            return
        
        self.space_file_label.setText(f"File: {file_path}")
        
        # Detect space
        space = BrainSpaceDetector.detect_space(file_path)
        
        if space:
            result_text = (
                f"✅ Space Detected: {space}\n\n"
                f"File: {file_path}\n\n"
                f"Details:\n"
            )
            if space == 'fs_LR_32k':
                result_text += "• Surface-based (32,492 vertices per hemisphere)\n• HCP convention\n• Used by Glasser and others"
            elif space == 'fsaverage6':
                result_text += "• Surface-based (40,962 vertices per hemisphere)\n• FreeSurfer standard\n• Widely compatible"
            elif space == 'FSLMNI2mm':
                result_text += "• Volumetric (91×109×91 voxels)\n• 2mm isotropic resolution\n• FSL standard"
            
            result_text += f"\n\n✅ This file is compatible with the toolbox!"
        else:
            result_text = (
                f"❌ Space Not Recognized\n\n"
                f"File: {file_path}\n\n"
                f"This file does not appear to be in a supported format.\n"
                f"Supported spaces:\n"
                f"• fs_LR_32k (32,492 vertices/hemi)\n"
                f"• fsaverage6 (40,962 vertices/hemi)\n"
                f"• FSLMNI2mm (91×109×91 voxels)\n\n"
                f"Use the Conversion tool above to convert your file."
            )
        
        self.space_result.setText(result_text)
