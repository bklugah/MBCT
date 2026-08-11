"""
Brain Viewer UI - Simple and Robust Implementation
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QSlider, QSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import threading


class BrainViewerTab(QWidget):
    """Brain Viewer Tab - Simple and functional"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewer_factory = None
        self.current_viewer = None
        self.current_view = 'axial'
        self.fig = None
        self.canvas = None
        self.is_loading = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the UI layout"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("🧠 Brain Viewer - MNI Templates")
        title_font = QFont('Arial', 12)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)
        
        # Control row 1: Template selection
        control_row1 = QHBoxLayout()
        control_row1.addWidget(QLabel("Template:"))
        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(250)
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        control_row1.addWidget(self.template_combo)
        
        self.template_info = QLabel("Select a template...")
        self.template_info.setFont(QFont('Consolas', 9))
        control_row1.addWidget(self.template_info)
        control_row1.addStretch()
        main_layout.addLayout(control_row1)
        
        # Control row 2: View selection
        control_row2 = QHBoxLayout()
        control_row2.addWidget(QLabel("View:"))
        
        self.view_buttons = {}
        for view_name in ['Axial', 'Coronal', 'Sagittal']:
            btn = QPushButton(view_name)
            btn.setMaximumWidth(80)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, v=view_name.lower(): self._on_view_changed(v))
            self.view_buttons[view_name.lower()] = btn
            control_row2.addWidget(btn)
        
        self.view_buttons['axial'].setChecked(True)
        
        control_row2.addSpacing(20)
        control_row2.addWidget(QLabel("Slice:"))
        self.slice_slider = QSlider(Qt.Orientation.Horizontal)
        self.slice_slider.setMaximumWidth(150)
        self.slice_slider.sliderMoved.connect(self._on_slice_changed)
        control_row2.addWidget(self.slice_slider)
        
        self.slice_spinbox = QSpinBox()
        self.slice_spinbox.setMaximumWidth(60)
        self.slice_spinbox.valueChanged.connect(self._on_spinbox_changed)
        control_row2.addWidget(self.slice_spinbox)
        
        control_row2.addStretch()
        main_layout.addLayout(control_row2)
        
        # Control row 3: Zoom and colormap
        control_row3 = QHBoxLayout()
        
        control_row3.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setMaximumWidth(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        control_row3.addWidget(self.zoom_slider)
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMaximumWidth(40)
        control_row3.addWidget(self.zoom_label)
        
        control_row3.addSpacing(20)
        
        control_row3.addWidget(QLabel("Colormap:"))
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(['gray', 'viridis', 'hot', 'jet', 'bone', 'cool'])
        self.cmap_combo.setMaximumWidth(100)
        self.cmap_combo.currentTextChanged.connect(self._on_colormap_changed)
        control_row3.addWidget(self.cmap_combo)
        
        control_row3.addStretch()
        main_layout.addLayout(control_row3)
        
        # Matplotlib canvas
        self.fig = Figure(figsize=(10, 8), dpi=100)
        self.fig.patch.set_facecolor('#f5f5f5')
        self.canvas = FigureCanvas(self.fig)
        main_layout.addWidget(self.canvas, 1)
        
        self.setLayout(main_layout)
    
    def initialize_viewer(self, template_dir: str):
        """Initialize brain viewer with templates"""
        try:
            print(f"🧠 Initializing Brain Viewer from: {template_dir}")
            
            from nct_application.brain_viewer import BrainVisualizerFactory
            
            self.viewer_factory = BrainVisualizerFactory(template_dir)
            available = self.viewer_factory.get_available_templates()
            
            if not available:
                self.template_info.setText("❌ No templates found")
                print(f"⚠️  No templates found in {template_dir}")
                return
            
            print(f"✅ Found {len(available)} templates")
            
            # Populate combo
            self.template_combo.blockSignals(True)
            self.template_combo.clear()
            
            for key in sorted(available.keys()):
                display_name = self.viewer_factory.get_template_display_name(key)
                self.template_combo.addItem(display_name, key)
            
            self.template_combo.blockSignals(False)
            
            if self.template_combo.count() > 0:
                print(f"✅ Brain Viewer initialized with {self.template_combo.count()} templates")
                self.template_combo.setCurrentIndex(0)
                self._on_template_changed()
            
        except Exception as e:
            print(f"❌ Error initializing brain viewer: {e}")
            import traceback
            traceback.print_exc()
            self.template_info.setText(f"❌ Error: {str(e)[:50]}")
    
    def _on_template_changed(self):
        """Load selected template"""
        if self.is_loading or self.template_combo.currentIndex() < 0:
            return
        
        template_key = self.template_combo.currentData()
        if not template_key:
            return
        
        self.is_loading = True
        self.template_info.setText("Loading...")
        
        # Load in background thread
        thread = threading.Thread(target=self._load_template, args=(template_key,))
        thread.daemon = True
        thread.start()
    
    def _load_template(self, template_key: str):
        """Load template in background"""
        try:
            self.current_viewer = self.viewer_factory.load_template(template_key)
            
            if self.current_viewer:
                info = self.current_viewer.get_template_info()
                info_text = (
                    f"✅ {info['name']} | "
                    f"Shape: {info['shape']} | "
                    f"Voxel: {info['voxel_size_mm']}"
                )
                self.template_info.setText(info_text)
                
                # Update slice controls
                min_slice, max_slice = self.current_viewer.get_slices_range(self.current_view)
                self.slice_slider.blockSignals(True)
                self.slice_spinbox.blockSignals(True)
                
                self.slice_slider.setRange(min_slice, max_slice)
                self.slice_spinbox.setRange(min_slice, max_slice)
                
                current = self.current_viewer.current_slice[self.current_view]
                self.slice_slider.setValue(current)
                self.slice_spinbox.setValue(current)
                
                self.slice_slider.blockSignals(False)
                self.slice_spinbox.blockSignals(False)
                
                self._render_brain()
        
        except Exception as e:
            print(f"❌ Error loading template: {e}")
            self.template_info.setText(f"❌ Error: {str(e)[:50]}")
        
        finally:
            self.is_loading = False
    
    def _on_view_changed(self, view: str):
        """Handle view change"""
        self.current_view = view
        
        # Update buttons
        for name, btn in self.view_buttons.items():
            btn.setChecked(name == view)
        
        if self.current_viewer:
            # Update slice range
            min_slice, max_slice = self.current_viewer.get_slices_range(view)
            self.slice_slider.blockSignals(True)
            self.slice_spinbox.blockSignals(True)
            
            self.slice_slider.setRange(min_slice, max_slice)
            self.slice_spinbox.setRange(min_slice, max_slice)
            
            current = self.current_viewer.current_slice[view]
            self.slice_slider.setValue(current)
            self.slice_spinbox.setValue(current)
            
            self.slice_slider.blockSignals(False)
            self.slice_spinbox.blockSignals(False)
            
            self._render_brain()
    
    def _on_slice_changed(self, value: int):
        """Handle slice slider change"""
        if self.current_viewer:
            self.current_viewer.current_slice[self.current_view] = value
            self.slice_spinbox.blockSignals(True)
            self.slice_spinbox.setValue(value)
            self.slice_spinbox.blockSignals(False)
            self._render_brain()
    
    def _on_spinbox_changed(self, value: int):
        """Handle slice spinbox change"""
        if self.current_viewer:
            self.current_viewer.current_slice[self.current_view] = value
            self.slice_slider.blockSignals(True)
            self.slice_slider.setValue(value)
            self.slice_slider.blockSignals(False)
            self._render_brain()
    
    def _on_zoom_changed(self, value: int):
        """Handle zoom change"""
        self.zoom_label.setText(f"{value}%")
        if self.current_viewer:
            self._render_brain()
    
    def _on_colormap_changed(self, cmap: str):
        """Handle colormap change"""
        if self.current_viewer:
            self._render_brain()
    
    def _render_brain(self):
        """Render the brain slice"""
        if not self.current_viewer:
            return
        
        try:
            self.fig.clear()
            ax = self.fig.add_subplot(111)
            
            # Get slice
            slice_data = self.current_viewer.get_slice(
                self.current_view,
                self.current_viewer.current_slice[self.current_view]
            )
            
            # Flip for proper orientation
            slice_data = np.flipud(slice_data.T)
            
            # Plot
            cmap = self.cmap_combo.currentText()
            im = ax.imshow(slice_data, cmap=cmap, origin='lower', interpolation='bilinear')
            
            # Colorbar
            cbar = self.fig.colorbar(im, ax=ax)
            cbar.ax.tick_params(labelsize=8)
            
            # Title and labels
            views = {'axial': 'Axial', 'coronal': 'Coronal', 'sagittal': 'Sagittal'}
            current_slice = self.current_viewer.current_slice[self.current_view]
            ax.set_title(f"{views[self.current_view]} - Slice {current_slice}", 
                        fontsize=11, fontweight='bold')
            
            ax.set_xlabel('L ← → R', fontsize=9)
            ax.set_ylabel('P ← → A', fontsize=9)
            ax.set_xticks([])
            ax.set_yticks([])
            
            # Apply zoom
            zoom = self.zoom_slider.value() / 100.0
            if zoom != 1.0:
                h, w = slice_data.shape
                ax.set_xlim(w * (1 - zoom) / 2, w * (1 + zoom) / 2)
                ax.set_ylim(h * (1 - zoom) / 2, h * (1 + zoom) / 2)
            
            self.fig.tight_layout()
            self.canvas.draw()
        
        except Exception as e:
            print(f"❌ Error rendering brain: {e}")
