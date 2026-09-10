#Klugah-Brown
"""
theme_manager.py
Central theming for the whole app. Two themes:
  - 'win11'  : Windows 11 / Fluent light theme (default)
  - 'dark'   : the original dark-navy theme

apply_theme(app, name) sets the global QApplication stylesheet + palette and
configures matplotlib defaults so plots match. Widgets that render figures
should call theme_manager.figure_colors() to get the right facecolors and
re-render after a theme change.
"""

import matplotlib
from PyQt6.QtGui import QPalette, QColor

import os
from pathlib import Path

LOGO_LIGHT = 'logo1.png'
LOGO_DARK = 'logo2.png'


def asset_path(filename):
    """Resolve an asset file across the likely locations, returning a str path
    or None if not found."""
    candidates = [
        Path(__file__).parent / 'assets' / filename,
        Path(__file__).parent / filename,
        Path(__file__).parent.parent / 'assets' / filename,
        Path(os.getcwd()) / 'assets' / filename,
        Path(os.getcwd()) / 'NeuroSynthesis_NCT_Complete' / 'assets' / filename,
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def logo_for_theme(name=None, variant='full'):
    """Return the logo path appropriate for the given (or current) theme.

    variant: 'full'  -> the large original logo (logo1.png / logo2.png)
             'small' -> 256px version for in-app display (logo*_small.png)
             'icon'  -> 256px square for the window/taskbar icon (logo*_icon.png)
    Dark theme uses logo2; light theme (internally 'win11') uses logo1.
    Falls back to the full logo if a prescaled variant is missing.
    """
    name = name or CURRENT
    is_dark = (name == 'dark')
    base = LOGO_DARK if is_dark else LOGO_LIGHT          
    stem = base[:-4]                                     
    if variant in ('small', 'icon'):
        cand = asset_path(f"{stem}_{variant}.png")
        if cand and os.path.exists(cand):
            return cand
    return asset_path(base)


CURRENT = 'win11'   



UI_FONT = ("'Segoe UI Variable','Segoe UI','SF Pro Text','-apple-system',"
           "'Helvetica Neue','Inter','Ubuntu','Cantarell',sans-serif")

WIN11_QSS = """
QMainWindow, QWidget {
    background:#f3f3f3; color:#1a1a1a;
    font-family:__FONT__;
    font-size:9.5pt;
}
QSplitter::handle { background:#e2e2e2; width:2px; }

QTabWidget::pane { border:0.5px solid rgba(0,0,0,0.10); background:#ffffff;
                   border-radius:8px; top:-1px; }
QTabBar::tab { background:transparent; color:#444444; padding:9px 22px;
               margin-right:4px; border-radius:7px 7px 0 0; font-size:9.5pt; }
QTabBar::tab:selected { background:#ffffff; color:#1a4fb0; font-weight:500;
                        border:0.5px solid rgba(0,0,0,0.10); border-bottom:none; }
QTabBar::tab:hover:!selected { background:#eaeaea; color:#1a1a1a; }

QLabel { color:#1a1a1a; background:transparent; }
QLabel#section { color:#2563eb; font-size:9pt; font-weight:500; letter-spacing:0.5px; }
QLabel#ok  { color:#107c10; }
QLabel#err { color:#c42b1c; }

QLineEdit, QTextEdit { background:#ffffff; color:#1a1a1a;
    border:0.5px solid rgba(0,0,0,0.18); border-radius:6px; padding:6px 8px;
    selection-background-color:#dce9fb; selection-color:#1a4fb0; }
QLineEdit:focus, QTextEdit:focus { border:1px solid #2563eb; }

QSpinBox, QDoubleSpinBox { background:#ffffff; color:#1a1a1a;
    border:0.5px solid rgba(0,0,0,0.18); border-radius:6px; padding:5px 6px; }
QSpinBox:focus, QDoubleSpinBox:focus { border:1px solid #2563eb; }

QComboBox { background:#ffffff; color:#1a1a1a;
    border:0.5px solid rgba(0,0,0,0.18); border-radius:6px; padding:5px 8px; }
QComboBox:hover { border:0.5px solid rgba(0,0,0,0.30); }
QComboBox::drop-down { border:none; width:22px; }
QComboBox::down-arrow { image:none; border-left:5px solid transparent;
    border-right:5px solid transparent; border-top:6px solid #6a6a6a; margin-right:6px; }
QComboBox QAbstractItemView { background:#ffffff; color:#1a1a1a;
    selection-background-color:#dce9fb; selection-color:#1a4fb0;
    border:0.5px solid rgba(0,0,0,0.18); border-radius:6px; outline:none; }

QTableWidget { background:#ffffff; gridline-color:#ececec; color:#1a1a1a;
    alternate-background-color:#fafafa; border:0.5px solid rgba(0,0,0,0.10);
    border-radius:8px; }
QTableWidget::item { padding:7px 10px; }
QTableWidget::item:selected { background:#dce9fb; color:#1a4fb0; }
QHeaderView::section { background:#f6f6f6; color:#333333; padding:7px 10px;
    border:none; border-bottom:0.5px solid #e2e2e2; font-weight:500; }

QProgressBar { background:#eaeaea; border:none; border-radius:6px;
    text-align:center; color:#333333; height:14px; }
QProgressBar::chunk { background:#2563eb; border-radius:6px; }

QPushButton { background:#ffffff; color:#1a1a1a;
    border:0.5px solid rgba(0,0,0,0.18); padding:7px 18px; border-radius:6px; }
QPushButton:hover { background:#f0f0f0; border:0.5px solid rgba(0,0,0,0.28); }
QPushButton:pressed { background:#e6e6e6; }
QPushButton:disabled { background:#f3f3f3; color:#a8a8a8; border-color:rgba(0,0,0,0.08); }

QPushButton#primaryBtn, QPushButton#analyze_btn {
    background:#2563eb; color:#ffffff; border:none; font-weight:500; }
QPushButton#primaryBtn:hover, QPushButton#analyze_btn:hover { background:#3b82f6; }
QPushButton#analyze_btn { font-size:11pt; padding:10px 28px; min-height:44px; }
QPushButton#export_btn { background:#ffffff; color:#1a4fb0;
    border:0.5px solid #c4d8f5; font-size:8.5pt; padding:5px 10px; }
QPushButton#export_btn:hover { background:#eef4fe; }

QCheckBox, QRadioButton { color:#333333; spacing:6px; }
QCheckBox::indicator, QRadioButton::indicator { width:15px; height:15px; }

QSlider::groove:horizontal { background:#dcdcdc; height:5px; border-radius:2px; }
QSlider::handle:horizontal { background:#2563eb; width:16px; height:16px;
    margin:-6px 0; border-radius:8px; }
QSlider::sub-page:horizontal { background:#93c0f5; border-radius:2px; }

QScrollBar:vertical { background:transparent; width:10px; }
QScrollBar::handle:vertical { background:#c4c4c4; border-radius:5px; min-height:24px; }
QScrollBar::handle:vertical:hover { background:#a8a8a8; }
QScrollBar:horizontal { background:transparent; height:10px; }
QScrollBar::handle:horizontal { background:#c4c4c4; border-radius:5px; min-width:24px; }
QScrollBar::add-line, QScrollBar::sub-line { height:0; width:0; }

QStatusBar { background:#eaeaea; color:#555555; }
QMenuBar { background:#f3f3f3; color:#1a1a1a; }
QMenuBar::item:selected { background:#e2e2e2; }
QMenu { background:#ffffff; color:#1a1a1a; border:0.5px solid rgba(0,0,0,0.15); }
QMenu::item:selected { background:#dce9fb; color:#1a4fb0; }

QPushButton#themeToggle { background:#ffffff; color:#1a4fb0; font-weight:500;
    border:0.5px solid #c4d8f5; border-radius:14px; padding:5px 14px; }
QPushButton#themeToggle:hover { background:#eef4fe; }
"""

WIN11_PALETTE = {
    'Window': '#f3f3f3', 'WindowText': '#1a1a1a',
    'Base': '#ffffff', 'Text': '#1a1a1a',
    'Button': '#ffffff', 'ButtonText': '#1a1a1a',
    'Highlight': '#2563eb', 'HighlightedText': '#ffffff',
}



DARK_QSS = """
QMainWindow, QWidget         { background:#16171f; color:#e6e9ef; font-family:__FONT__;
                               font-size:9.5pt; }
QSplitter::handle            { background:#26263a; width:2px; }

QTabWidget::pane             { border:0.5px solid #2a2d3a; background:#1e2029;
                               border-radius:8px; top:-1px; }
QTabBar::tab                 { background:transparent; color:#8b95a5; padding:9px 22px;
                               margin-right:4px; border-radius:8px 8px 0 0; font-size:9.5pt; }
QTabBar::tab:selected        { background:#1e2029; color:#60a5fa; font-weight:500;
                               border:0.5px solid rgba(255,255,255,0.08); border-bottom:none; }
QTabBar::tab:hover:!selected { background:#20222c; color:#c4ccd6; }

QLabel                       { color:#e6e9ef; background:transparent; }
QLabel#section               { color:#60a5fa; font-size:9pt; font-weight:500;
                               letter-spacing:0.6px; }
QLabel#ok                    { color:#4ade80; }
QLabel#err                   { color:#f87171; }

QLineEdit, QTextEdit         { background:#141520; color:#e6e9ef;
                               border:0.5px solid rgba(255,255,255,0.12); border-radius:8px;
                               padding:6px 8px; selection-background-color:#2f5a94;
                               selection-color:#ffffff; }
QLineEdit:focus, QTextEdit:focus { border:1px solid #3b82f6; }

QSpinBox, QDoubleSpinBox     { background:#141520; color:#e6e9ef;
                               border:0.5px solid rgba(255,255,255,0.12); border-radius:8px;
                               padding:5px 6px; }
QSpinBox:focus, QDoubleSpinBox:focus { border:1px solid #3b82f6; }

QComboBox                    { background:#141520; color:#e6e9ef;
                               border:0.5px solid rgba(255,255,255,0.12); border-radius:8px;
                               padding:5px 8px; }
QComboBox:hover              { border:0.5px solid rgba(255,255,255,0.22); }
QComboBox::drop-down         { border:none; width:22px; }
QComboBox::down-arrow        { image:none; border-left:5px solid transparent;
                               border-right:5px solid transparent; border-top:6px solid #8b95a5;
                               margin-right:6px; }
QComboBox QAbstractItemView  { background:#1e2029; color:#e6e9ef;
                               selection-background-color:#2f5a94; selection-color:#ffffff;
                               border:0.5px solid rgba(255,255,255,0.12); border-radius:8px;
                               outline:none; }

QTableWidget                 { background:#141520; gridline-color:#262838;
                               color:#e6e9ef; alternate-background-color:#1a1c26;
                               border:0.5px solid #2a2d3a; border-radius:8px; }
QTableWidget::item           { padding:7px 10px; }
QTableWidget::item:selected  { background:#2f5a94; color:#ffffff; }
QHeaderView::section         { background:#1e2029; color:#c4ccd6; padding:7px 10px;
                               border:none; border-bottom:0.5px solid #2a2d3a; font-weight:500; }

QProgressBar                 { background:#2a2d3a; border:none; border-radius:6px;
                               text-align:center; color:#c4ccd6; height:14px; }
QProgressBar::chunk          { background:#3b82f6; border-radius:6px; }

QPushButton                  { background:#232530; color:#e6e9ef;
                               border:0.5px solid rgba(255,255,255,0.14); padding:7px 18px;
                               border-radius:8px; }
QPushButton:hover            { background:#2b2e3b; border:0.5px solid rgba(255,255,255,0.22); }
QPushButton:pressed          { background:#1c1e28; }
QPushButton:disabled         { background:#1a1c24; color:#565f6e;
                               border-color:rgba(255,255,255,0.06); }

QPushButton#primaryBtn, QPushButton#analyze_btn {
                               background:#3b82f6; color:#ffffff; border:none; font-weight:500; }
QPushButton#primaryBtn:hover, QPushButton#analyze_btn:hover { background:#4b8ef8; }
QPushButton#primaryBtn:pressed, QPushButton#analyze_btn:pressed { background:#2f6fe0; }
QPushButton#analyze_btn      { font-size:11pt; padding:10px 28px; min-height:44px; }
QPushButton#export_btn       { background:#232530; color:#8fc3ff;
                               border:0.5px solid rgba(59,130,246,0.35);
                               font-size:8.5pt; padding:5px 10px; }
QPushButton#export_btn:hover { background:#2b2e3b; }

QCheckBox, QRadioButton      { color:#c4ccd6; spacing:6px; }
QCheckBox::indicator, QRadioButton::indicator { width:15px; height:15px; }

QSlider::groove:horizontal   { background:#2a2d3a; height:5px; border-radius:2px; }
QSlider::handle:horizontal   { background:#3b82f6; width:16px; height:16px;
                               margin:-6px 0; border-radius:8px; }
QSlider::sub-page:horizontal { background:#2f5a94; border-radius:2px; }

QScrollBar:vertical          { background:transparent; width:10px; }
QScrollBar::handle:vertical  { background:#3a3d4d; border-radius:5px; min-height:24px; }
QScrollBar::handle:vertical:hover { background:#4a4e60; }
QScrollBar:horizontal        { background:transparent; height:10px; }
QScrollBar::handle:horizontal{ background:#3a3d4d; border-radius:5px; min-width:24px; }
QScrollBar::add-line, QScrollBar::sub-line { height:0; width:0; }

QStatusBar { background:#14151d; color:#8b95a5; }
QMenuBar { background:#16171f; color:#e6e9ef; }
QMenuBar::item:selected { background:#20222c; }
QMenu { background:#1e2029; color:#e6e9ef; border:0.5px solid rgba(255,255,255,0.10); }
QMenu::item:selected { background:#2f5a94; color:#ffffff; }

QPushButton#themeToggle { background:#232530; color:#8fc3ff; font-weight:500;
    border:0.5px solid rgba(59,130,246,0.35); border-radius:14px; padding:5px 14px; }
QPushButton#themeToggle:hover { background:#2b2e3b; }
"""

DARK_PALETTE = {
    'Window': '#16171f', 'WindowText': '#e6e9ef',
    'Base': '#141520', 'Text': '#e6e9ef',
    'Button': '#232530', 'ButtonText': '#e6e9ef',
    'Highlight': '#3b82f6', 'HighlightedText': '#ffffff',
}



def figure_colors(name=None):
    """Return a dict of colors for matplotlib figures used in tabs.
    Brain slice canvases should always pass black; charts use 'fig'/'ax'."""
    name = name or CURRENT
    if name == 'win11':
        return {
            'fig': '#ffffff',     
            'ax':  '#ffffff',     
            'text': '#1a1a1a',
            'grid': '#e2e2e2',
            'spine': '#cccccc',
            'accent': '#2563eb',
            'brain_bg': '#000000',   
        }
    return {
        'fig': '#1e2029',
        'ax':  '#141520',
        'text': '#e6e9ef',
        'grid': '#2a2d3a',
        'spine': '#3a3d4d',
        'accent': '#3b82f6',
        'brain_bg': '#000000',
    }


def apply_matplotlib(name=None):
    name = name or CURRENT
    c = figure_colors(name)
    matplotlib.rcParams.update({
        'figure.facecolor': c['fig'],
        'axes.facecolor':   c['ax'],
        'axes.edgecolor':   c['spine'],
        'axes.labelcolor':  c['text'],
        'text.color':       c['text'],
        'xtick.color':      c['text'],
        'ytick.color':      c['text'],
        'grid.color':       c['grid'],
    })




def detect_os_theme():
    """Best-effort detection of the OS light/dark preference.
    Returns 'win11' (light) or 'dark'. Falls back to 'win11'."""
    import sys
    try:
        if sys.platform.startswith('win'):
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return 'win11' if val == 1 else 'dark'
    except Exception:
        pass
    try:
        # Qt 6.5+ exposes the OS color scheme
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt as _Qt
        app = QApplication.instance()
        if app is not None:
            scheme = app.styleHints().colorScheme()
            if int(scheme) == 2:   # Dark
                return 'dark'
            if int(scheme) == 1:   # Light
                return 'win11'
    except Exception:
        pass
    return 'win11'


def apply_theme(app, name):
    """Apply a theme to the whole QApplication. Returns the active name."""
    global CURRENT
    name = name if name in ('win11', 'dark') else 'win11'
    CURRENT = name

    qss = WIN11_QSS if name == 'win11' else DARK_QSS
    qss = qss.replace('__FONT__', UI_FONT)
    pal_def = WIN11_PALETTE if name == 'win11' else DARK_PALETTE

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(pal_def['Window']))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(pal_def['WindowText']))
    pal.setColor(QPalette.ColorRole.Base,            QColor(pal_def['Base']))
    pal.setColor(QPalette.ColorRole.Text,            QColor(pal_def['Text']))
    pal.setColor(QPalette.ColorRole.Button,          QColor(pal_def['Button']))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(pal_def['ButtonText']))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(pal_def['Highlight']))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(pal_def['HighlightedText']))
    app.setPalette(pal)
    app.setStyleSheet(qss)
    apply_matplotlib(name)
    return name


def toggle(app):
    """Switch to the other theme. Returns the new active name."""
    return apply_theme(app, 'dark' if CURRENT == 'win11' else 'win11')
