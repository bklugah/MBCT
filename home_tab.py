"""Professional Home/Landing tab with animations, walkthrough, and quick start."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QFrame, QScrollArea, QProgressBar
)
from PyQt6.QtGui import QFont, QColor, QPixmap
from PyQt6.QtCore import Qt, QSize, QTimer, QRect, QPoint, pyqtProperty, QVariantAnimation, QPropertyAnimation, QEasingCurve
from pathlib import Path


class AnimatedLabel(QLabel):
    """Label that fades in smoothly."""
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setOpacity(0)
        
    def setOpacity(self, opacity):
        """Set opacity value (0.0 to 1.0)."""
        self.opacity = opacity
        self.update()
        
    def paintEvent(self, event):
        """Paint with opacity."""
        from PyQt6.QtGui import QPainter
        painter = QPainter(self)
        painter.setOpacity(self.opacity)
        super().paintEvent(event)
        painter.end()
    
    def animate_in(self, duration=500):
        """Fade in animation."""
        anim = QVariantAnimation(self)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.valueChanged.connect(self.setOpacity)
        anim.start()
        return anim


class WelcomeTab(QWidget):
    """Polished welcome / landing screen."""

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.start_animations()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        
        try:
            import theme_manager as _tm
            dark = (_tm.CURRENT == 'dark')
        except Exception:
            dark = True
        if dark:
            hero_bg = "#16171f"; badge_c = "#60a5fa"; title_c = "#f0f3f8"
            abbr_c = "#3b82f6"; sub_c = "#aeb8c6"; hint_c = "#8b95a5"
        else:
            hero_bg = "#f6f8fa"; badge_c = "#2563eb"; title_c = "#14203a"
            abbr_c = "#2563eb"; sub_c = "#4a5568"; hint_c = "#6a7686"

        bg = QFrame()
        bg.setObjectName("welcomeHero")
        bg.setStyleSheet(f"#welcomeHero {{ background:{hero_bg}; }}")
        outer = QVBoxLayout(bg)
        outer.setContentsMargins(56, 0, 56, 0)
        outer.setSpacing(0)

        
        top_row = QHBoxLayout()
        self.logo_left = QLabel()
        self.logo_right = QLabel()
        for lab, align in ((self.logo_left, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                           (self.logo_right, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)):
            lab.setAlignment(align)
        self._load_corner_logos()
        top_row.addWidget(self.logo_left, 0, Qt.AlignmentFlag.AlignTop)
        top_row.addStretch(1)
        top_row.addWidget(self.logo_right, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(top_row)

        outer.addStretch(1)

        
        self.badge = AnimatedLabel("MULTIMODAL NEUROIMAGING ANALYTICS")
        self.badge.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setStyleSheet(f"color:{badge_c}; letter-spacing:5px;")
        outer.addWidget(self.badge)

        outer.addSpacing(18)

        self.title = AnimatedLabel("Multimodal Brain Network\nCharacterization Tool")
        self.title.setFont(QFont("Segoe UI", 46, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(f"color:{title_c};")
        outer.addWidget(self.title)

        self.abbr = AnimatedLabel("— MBCT —")
        self.abbr.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.abbr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.abbr.setStyleSheet(f"color:{abbr_c}; letter-spacing:7px;")
        outer.addWidget(self.abbr)

        outer.addSpacing(14)

        self.subtitle = AnimatedLabel(
            "Integrating functional, molecular, and transcriptomic brain architectures")
        self.subtitle.setFont(QFont("Segoe UI", 17))
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setStyleSheet(f"color:{sub_c};")
        outer.addWidget(self.subtitle)

        outer.addSpacing(42)

        
        row = QHBoxLayout()
        row.setSpacing(22)
        row.addStretch()
        features = [
            ("Functional", "Network correspondence\n& meta-analytic decoding", "#3b82f6"),
            ("Molecular",  "PET receptor density\nmapping (neuromaps)", "#c084fc"),
            ("Transcriptomic", "Gene expression\nprofiles (AHBA)", "#34d399"),
            ("Convergence", "Cross-modal\nassociation analysis", "#f0a93b"),
        ]
        self.feature_cards = []
        for icon, title, desc, color in features:
            c = self._create_feature_card(icon, title, desc, color, dark)
            self.feature_cards.append(c)
            row.addWidget(c)
        row.addStretch()
        outer.addLayout(row)

        outer.addSpacing(36)

        self.hint = AnimatedLabel(
            "Open the  Analysis  tab to begin, or visit  Help → Manual  for a full walkthrough.")
        self.hint.setFont(QFont("Segoe UI", 13))
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet(f"color:{hint_c};")
        outer.addWidget(self.hint)

        outer.addStretch(2)
        layout.addWidget(bg)

    def _load_corner_logos(self):
        """Place logo1 in the two upper corners of the welcome page."""
        try:
            import theme_manager as _tm
            path = _tm.asset_path('logo1.png')
        except Exception:
            path = None
        if not path:
            return
        pix = QPixmap(path)
        if pix.isNull():
            return
        scaled = pix.scaledToHeight(96, Qt.TransformationMode.SmoothTransformation)
        self.logo_left.setPixmap(scaled)
        self.logo_right.setPixmap(scaled)

    def _create_feature_card(self, icon, title, desc, color, dark=True):
        card = QFrame()
        if dark:
            card_bg = "#1e2029"; card_border = "rgba(255,255,255,0.08)"; desc_c = "#aeb8c6"
        else:
            card_bg = "#ffffff"; card_border = "rgba(0,0,0,0.10)"; desc_c = "#4a5568"
        card.setStyleSheet(
            "QFrame { background-color:%s; border:0.5px solid %s;"
            " border-radius:12px; }"
            "QFrame:hover { border:1px solid %s; }" % (card_bg, card_border, color)
        )
        card.setFixedSize(210, 190)
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 20, 18, 20)
        v.setSpacing(10)

        ic = QLabel(icon)
        ic.setFont(QFont("Segoe UI", 44))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet(f"color:{color};")
        v.addWidget(ic)

        t = QLabel(title)
        t.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"color:{color};")
        v.addWidget(t)

        d = QLabel(desc)
        d.setFont(QFont("Segoe UI", 10))
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setStyleSheet(f"color:{desc_c};")
        d.setWordWrap(True)
        v.addWidget(d)
        return card

    def start_animations(self):
        QTimer.singleShot(120, lambda: self.badge.animate_in(500))
        QTimer.singleShot(260, lambda: self.title.animate_in(650))
        QTimer.singleShot(520, lambda: self.abbr.animate_in(500))
        QTimer.singleShot(680, lambda: self.subtitle.animate_in(600))
        QTimer.singleShot(1500, lambda: self.hint.animate_in(700))
        for i, card in enumerate(self.feature_cards):
            QTimer.singleShot(900 + i * 160, lambda c=card: self._animate_card(c))

    def _animate_card(self, card):
        anim = QPropertyAnimation(card, b"geometry")
        anim.setDuration(480)
        g = card.geometry()
        anim.setStartValue(QRect(g.x(), g.y() + 26, g.width(), g.height()))
        anim.setEndValue(g)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start()
        self._last_anim = anim 


class FeaturesTab(QWidget):
    """Professional features tab with cards."""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Title
        title = QLabel("Key Features")
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title.setStyleSheet("color: #38b6ff;")
        layout.addWidget(title)
        
        # Scroll area for features grid
        scroll = QScrollArea()
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        scroll.setWidgetResizable(True)
        
        features_widget = QWidget()
        features_layout = QVBoxLayout(features_widget)
        features_layout.setSpacing(15)
        
        # Feature data: (emoji, title, description, color)
        features = [
            ("🧠", "Network Correspondence",
             "Quantify how your brain map aligns with established functional networks using the CBIG "
             "Network Correspondence Toolbox, with Dice/Jaccard overlap and spatial-null significance",
             "#38b6ff"),
            ("📊", "Functional Decoding (Neurosynth)",
             "Decode networks and locations against the Neurosynth meta-analytic corpus (14,000+ studies) "
             "with FDR-corrected term associations",
             "#4ade80"),
            ("⚛", "Neurotransmitter Mapping",
             "Relate networks to PET receptor/transporter density maps spanning nine neurotransmitter "
             "systems via neuromaps",
             "#c084fc"),
            ("🧬", "Receptor-Gene Expression",
             "Compare networks to receptor-gene expression from the Allen Human Brain Atlas (abagen), "
             "for convergent molecular evidence",
             "#34d399"),
            ("🎯", "Interactive Brain Viewer",
             "Single, triplanar and glass-brain views with an accurate draggable crosshair, MNI 'go-to' "
             "entry, live thresholding, and a true rotatable 3D surface",
             "#ffd43b"),
            ("📍", "Live Anatomical Labels",
             "Click anywhere to read the Harvard-Oxford cortical/subcortical region and Brodmann area at "
             "the crosshair, in both Results and Brain Viewer",
             "#ff922b"),
            ("🔧", "Utilities Toolbox",
             "Space converter, threshold & binarize, ROI builder + signal extractor, map combiner, and "
             "meta-analytic Term→Map / Coordinate→Terms / coactivation (MACM) tools",
             "#a78bfa"),
            ("💾", "Flexible Export",
             "Save tables as CSV, brain maps as NIfTI, and figures as PNG/TIF/JPEG; save and reload full "
             "analysis sessions for later review",
             "#51cf66"),
            ("🌗", "Light & Dark Themes",
             "Switch between a clean light theme and a focused dark theme at any time; the app icon and "
             "all plots follow the active theme",
             "#60a5fa"),
        ]
        
        for emoji, title, desc, color in features:
            card = self._create_feature_card(emoji, title, desc, color)
            features_layout.addWidget(card)
        
        features_layout.addStretch()
        scroll.setWidget(features_widget)
        layout.addWidget(scroll)
        
        self.setLayout(layout)
    
    def _create_feature_card(self, emoji, title, desc, color):
        """Create a professional feature card."""
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ "
            f"background-color: #1a2a3a; "
            f"border-left: 4px solid {color}; "
            f"border-radius: 4px; "
            f"padding: 5px; "
            f"}}"
        )
        card.setMinimumHeight(100)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(20)
        
        # Icon
        icon_label = QLabel(emoji)
        icon_label.setFont(QFont("Segoe UI", 32))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        icon_label.setFixedSize(50, 50)
        layout.addWidget(icon_label)
        
        # Text area
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {color};")
        text_layout.addWidget(title_label)
        
        desc_label = QLabel(desc)
        desc_label.setFont(QFont("Segoe UI", 10))
        desc_label.setStyleSheet("color: #a0b8d4;")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout, 1)
        return card


class WalkthroughTab(QWidget):
    """Professional interactive walkthrough with navigation."""
    
    def __init__(self):
        super().__init__()
        self.current_step = 0
        self.steps = [
            {
                "title": "Step 1: Load Your Map (Analysis)",
                "description": "Bring a statistical or parcellation map into the analysis pipeline",
                "details": [
                    "• Open the Analysis tab and click 'Browse…' to pick a NIfTI (.nii/.nii.gz)",
                    "• The app detects the brain space; choose the matching space",
                    "  (FSLMNI2mm, fs_LR_32k, or fsaverage6)",
                    "• Pick an atlas via Space → Author → Atlas, then set Data Type",
                    "  (Metric, Hard, or Soft) and any threshold",
                ],
                "icon": "📁"
            },
            {
                "title": "Step 2: Run the Correspondence Analysis",
                "description": "Quantify how your map overlaps established networks",
                "details": [
                    "• Set permutations, p-threshold and metric (Dice or Jaccard)",
                    "• Click 'Run Analysis' — a timer and ETA show progress",
                    "• Results open automatically when the run completes",
                ],
                "icon": "🔬"
            },
            {
                "title": "Step 3: Explore Networks (Results)",
                "description": "Inspect each network's overlap, location and properties",
                "details": [
                    "• Click any network in the table to select it",
                    "• The brain map highlights it; the bar chart ranks overlaps",
                    "• Drag the crosshair on the brain — single or triplanar",
                    "• Read the network, Harvard-Oxford region and Brodmann area live",
                    "• Drag the divider to resize the subregion panel",
                ],
                "icon": "🧠"
            },
            {
                "title": "Step 4: Read the Multimodal Annotations",
                "description": "Understand the function, chemistry and genetics of a network",
                "details": [
                    "• Functional (Neurosynth): meta-analytic cognitive terms",
                    "• Neurotransmitters (PET): receptor/transporter associations",
                    "• Transcriptomics (AHBA): receptor-gene expression",
                    "• Bold green marks spatial-null significant associations",
                ],
                "icon": "📊"
            },
            {
                "title": "Step 5: Use the Brain Viewer",
                "description": "Visualize any map with full interactive controls",
                "details": [
                    "• Load an underlay and up to three overlays",
                    "• Switch Single / Triplanar / Glass Brain views",
                    "• Drag the crosshair (linked across planes) or type MNI to jump",
                    "• Adjust the threshold and minimum cluster size with sliders",
                    "• Open a true rotatable 3D surface in your browser",
                ],
                "icon": "🎯"
            },
            {
                "title": "Step 6: Work in the Utilities Toolbox",
                "description": "Prepare maps and run meta-analytic lookups",
                "details": [
                    "• Converter: resample a map to a standard MNI grid",
                    "• Threshold & Binarize; ROI Tool (build sphere/atlas + extract signal)",
                    "• Combine Maps: arithmetic or logical (conjunction/contrast)",
                    "• Term → Map and Coordinate → Terms (with MACM coactivation)",
                    "• Use 'Open in Viewer' to send any result to the Brain Viewer",
                ],
                "icon": "🔧"
            },
            {
                "title": "Step 7: Export & Save",
                "description": "Preserve results for reports, figures and later review",
                "details": [
                    "• In Results, use the Export buttons:",
                    "  CSV (tables), NIfTI (maps), PNG / TIF / JPEG (figures)",
                    "• 'Sig. NIfTIs' saves one mask per significant network",
                    "• 'Save Results' stores a full session you can reload later",
                ],
                "icon": "💾"
            },
        ]
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        
        header_layout = QHBoxLayout()
        self.title_label = QLabel()
        self.title_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #38b6ff;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        
        self.step_indicator = QLabel()
        self.step_indicator.setFont(QFont("Segoe UI", 12))
        self.step_indicator.setStyleSheet("color: #a0b8d4;")
        header_layout.addWidget(self.step_indicator)
        layout.addLayout(header_layout)
        
        
        self.progress = QProgressBar()
        self.progress.setMaximum(len(self.steps) - 1)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #1a2a3a;
                border: 1px solid #2a3a5a;
                border-radius: 4px;
                height: 6px;
            }
            QProgressBar::chunk {
                background-color: #38b6ff;
            }
        """)
        layout.addWidget(self.progress)
        
       
        content_frame = QFrame()
        content_frame.setStyleSheet(
            "QFrame { background-color: #1a2a3a; border: 1px solid #2a3a5a; "
            "border-radius: 8px; padding: 30px; }"
        )
        content_layout = QVBoxLayout(content_frame)
        content_layout.setSpacing(15)
        
        
        desc_layout = QHBoxLayout()
        self.icon_label = QLabel()
        self.icon_label.setFont(QFont("Segoe UI", 48))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(80, 80)
        desc_layout.addWidget(self.icon_label)
        
        self.description_label = QLabel()
        self.description_label.setFont(QFont("Segoe UI", 13))
        self.description_label.setStyleSheet("color: #dde6f0;")
        self.description_label.setWordWrap(True)
        desc_layout.addWidget(self.description_label)
        
        content_layout.addLayout(desc_layout)
        
       
        self.details_label = QLabel()
        self.details_label.setFont(QFont("Segoe UI", 11))
        self.details_label.setStyleSheet("color: #a0b8d4; line-height: 1.8;")
        self.details_label.setWordWrap(True)
        content_layout.addWidget(self.details_label)
        
        layout.addWidget(content_frame)
        
        
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(10)
        
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a2a3a;
                color: #38b6ff;
                border: 1px solid #38b6ff;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2a3a4a; }
            QPushButton:disabled {
                color: #5a6a7a;
                border-color: #2a3a5a;
            }
        """)
        self.prev_btn.clicked.connect(self.prev_step)
        nav_layout.addWidget(self.prev_btn)
        
        nav_layout.addStretch()
        
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a3a5a;
                color: #38b6ff;
                border: 1px solid #38b6ff;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2a4a6a; }
        """)
        self.next_btn.clicked.connect(self.next_step)
        nav_layout.addWidget(self.next_btn)
        
        layout.addLayout(nav_layout)
        
        self.setLayout(layout)
        self.show_step(0)
    
    def show_step(self, index):
        """Display a specific step."""
        if 0 <= index < len(self.steps):
            self.current_step = index
            step = self.steps[index]
            
            self.title_label.setText(step["title"])
            self.icon_label.setText(step["icon"])
            self.description_label.setText(step["description"])
            self.details_label.setText("\n".join(step["details"]))
            self.step_indicator.setText(f"{index + 1} of {len(self.steps)}")
            self.progress.setValue(index)
            
           
            self.prev_btn.setEnabled(index > 0)
            self.next_btn.setEnabled(index < len(self.steps) - 1)
    
    def next_step(self):
        """Go to next step."""
        if self.current_step < len(self.steps) - 1:
            self.show_step(self.current_step + 1)
    
    def prev_step(self):
        """Go to previous step."""
        if self.current_step > 0:
            self.show_step(self.current_step - 1)


class QuickStartTab(QWidget):
    """Quick start guide based on actual workflow."""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        
        title = QLabel("🚀 Get Started in 5 Minutes")
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title.setStyleSheet("color: #38b6ff;")
        layout.addWidget(title)
        
        
        scroll = QScrollArea()
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        scroll.setWidgetResizable(True)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(15)
        
        steps = [
            ("1. Launch the App", [
                "✓ Windows: open MBCT from the Start menu (or desktop shortcut)",
                "✓ macOS: open MBCT from Applications (or Launchpad)",
                "✓ Linux: launch MBCT from your applications menu or the CLI",
                "✓ A splash screen appears, then the main window opens on Home",
            ]),
            ("2. Load a Map (Analysis Tab)", [
                "✓ Open the Analysis tab and click 'Browse…' to select a NIfTI",
                "✓ Confirm the detected space (FSLMNI2mm, fs_LR_32k, fsaverage6)",
                "✓ Choose the atlas via Space → Author → Atlas",
                "✓ Set Data Type (Metric / Hard / Soft) and threshold if needed",
            ]),
            ("3. Run the Analysis", [
                "✓ Set permutations, p-threshold and metric (Dice or Jaccard)",
                "✓ Click 'Run Analysis' and watch the timer / ETA",
                "✓ Results open automatically when finished",
            ]),
            ("4. Explore Results", [
                "✓ Click a network in the table to select and highlight it",
                "✓ Drag the crosshair on the brain (single or triplanar)",
                "✓ Read the live region + Brodmann label under the crosshair",
                "✓ Review the Functional / Neurotransmitter / Transcriptomic tabs",
            ]),
            ("5. Visualize in the Brain Viewer", [
                "✓ Load an underlay and up to three overlays",
                "✓ Switch Single / Triplanar / Glass Brain; or open a 3D surface",
                "✓ Type MNI coordinates to jump the crosshair to a location",
                "✓ Use the threshold and cluster-size sliders to refine the map",
            ]),
            ("6. Use the Utilities Toolbox", [
                "✓ Convert a map to a standard MNI grid",
                "✓ Threshold/binarize, build ROIs, extract signal, combine maps",
                "✓ Generate a Neurosynth map from a term (Term → Map)",
                "✓ Decode a coordinate to terms, or build a coactivation (MACM) map",
                "✓ Click 'Open in Viewer' to inspect any result",
            ]),
            ("7. Export & Save", [
                "✓ Results → Export: CSV (tables), NIfTI (maps), PNG/TIF/JPEG (figures)",
                "✓ 'Sig. NIfTIs' writes one mask per significant network",
                "✓ 'Save Results' stores a session you can reload later",
            ]),
        ]
        
        for step_title, step_items in steps:
            card = self._create_step_card(step_title, step_items)
            scroll_layout.addWidget(card)
        
        
        tips_card = self._create_tips_card()
        scroll_layout.addWidget(tips_card)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        self.setLayout(layout)
    
    def _create_step_card(self, title, items):
        """Create a step card."""
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #1a2a3a; border: 1px solid #2a3a5a; "
            "border-radius: 6px; padding: 15px; }"
        )
        
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #38b6ff;")
        layout.addWidget(title_label)
        
        for item in items:
            item_label = QLabel(item)
            item_label.setFont(QFont("Segoe UI", 10))
            item_label.setStyleSheet("color: #a0b8d4;")
            item_label.setWordWrap(True)
            layout.addWidget(item_label)
        
        return card
    
    def _create_tips_card(self):
        """Create tips card."""
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #1a3a2a; border: 1px solid #2a5a4a; "
            "border-left: 4px solid #34d399; border-radius: 6px; padding: 15px; }"
        )
        
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        
        title = QLabel("💡 Pro Tips")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #34d399;")
        layout.addWidget(title)
        
        tips = [
            "• Use the Walkthrough for guided, step-by-step instructions",
            "• Crosshairs are draggable in Results and the Brain Viewer; triplanar planes stay linked",
            "• Click any location to read its Harvard-Oxford region and Brodmann area",
            "• Convergent evidence is strongest when PET receptors and AHBA genes agree",
            "• Meta-analysis tools read a local Neurosynth corpus — no internet needed once installed",
            "• Switch light/dark themes anytime from the top-right toggle",
            "• Save a session ('Save Results') to reload your analysis later without recomputing",
        ]
        
        for tip in tips:
            tip_label = QLabel(tip)
            tip_label.setFont(QFont("Segoe UI", 10))
            tip_label.setStyleSheet("color: #a0b8d4;")
            tip_label.setWordWrap(True)
            layout.addWidget(tip_label)
        
        return card


class HomeTab(QWidget):
    """Home tab — now just the redesigned Welcome screen.
    (Features, Walkthrough and Quick Start moved to the Help → Manual tab.)"""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(WelcomeTab())
        self.setLayout(layout)
