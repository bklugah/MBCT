"""Splash screen for Brain Network Characterization Tool."""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt
from pathlib import Path
import os


class SplashScreen(QDialog):
    """Beautiful splash screen with professional graphical abstract."""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Multimodal Brain Network Characterization Tool (MBCT)")
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet("background-color: #ffffff; border: none;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Try multiple paths to find the image
        possible_paths = [
            Path(__file__).parent / "assets" / "graphical_abstract.png",
            Path(__file__).parent.parent / "assets" / "graphical_abstract.png",
            Path(os.getcwd()) / "assets" / "graphical_abstract.png",
            Path(os.getcwd()) / "NeuroSynthesis_NCT_Complete" / "assets" / "graphical_abstract.png",
        ]
        
        img_path = None
        for p in possible_paths:
            if p.exists():
                img_path = p
                print(f"[ok] Found graphical abstract at: {img_path}")
                break
        
        if img_path:
            pixmap = QPixmap(str(img_path))
            if not pixmap.isNull():
                # Scale to fit screen while maintaining aspect ratio
                screen = self.screen().geometry()
                max_width = min(1200, screen.width() - 40)
                max_height = min(800, screen.height() - 40)
                
                if pixmap.width() > max_width or pixmap.height() > max_height:
                    pixmap = pixmap.scaled(max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
                label = QLabel()
                label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setStyleSheet("background-color: #ffffff;")
                layout.addWidget(label)

                # "Click to continue" banner beneath the image
                hint = QLabel("Click anywhere or press Enter to continue  →")
                hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
                hint.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
                hint.setStyleSheet(
                    "color:#ffffff; background:#2563eb; padding:12px 0;"
                    "letter-spacing:0.5px;")
                layout.addWidget(hint)

                # Set window width to image; height = image + banner
                self.setFixedWidth(pixmap.width())
            else:
                raise Exception(f"Could not load image from {img_path}")
        else:
            # Fallback if image not found
            print("[warn] Graphical abstract not found in any of:")
            for p in possible_paths:
                print(f"   - {p}")
            
            label = QLabel("Multimodal Brain Network Characterization Tool (MBCT)\n\nIntegrating Functional, Molecular & Transcriptomic Architectures\n\nPress Enter or Click to Continue")
            label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: #1a3a5a; background: #ffffff; padding: 40px;")
            layout.addWidget(label)
            self.setFixedSize(1000, 700)
        
        self.setLayout(layout)
        
        # Center on screen
        screen = self.screen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )
        
    def keyPressEvent(self, event):
        """Accept any key press to close splash."""
        self.accept()
        
    def mousePressEvent(self, event):
        """Accept mouse click to close splash."""
        self.accept()
