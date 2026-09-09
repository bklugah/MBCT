"""
help_tab.py
Help tab: a detailed Manual (Features, Walkthrough, Quick Start) and an About
section (app/version, author, contact, citations).
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QTabWidget, QTextBrowser
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from home_tab import FeaturesTab, WalkthroughTab, QuickStartTab


APP_NAME = "Multimodal Brain Network Characterization Tool"
APP_ABBR = "MBCT"
APP_VERSION = "1.0.0"


class ManualTab(QWidget):
    """Detailed manual: bundles Features, Walkthrough and Quick Start."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("  📖  User Manual")
        header.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        header.setStyleSheet("padding:14px 18px;")
        layout.addWidget(header)

        inner = QTabWidget()
        inner.addTab(FeaturesTab(), "⭐ Features")
        inner.addTab(WalkthroughTab(), "🚶 Walkthrough")
        inner.addTab(QuickStartTab(), "🚀 Quick Start")
        layout.addWidget(inner, 1)


class AboutTab(QWidget):
    """About: app identity, author, contact, and citations."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QTextBrowser()
        body.setOpenExternalLinks(True)
        body.setStyleSheet("QTextBrowser{border:none; padding:8px 22px; font-size:10.5pt;}")
        body.setHtml(self._about_html())
        scroll.setWidget(body)
        layout.addWidget(scroll)

    def _about_html(self):
        return f"""
        <div style="font-family:'Segoe UI',sans-serif;">
          <h1 style="margin-bottom:2px;">{APP_NAME}</h1>
          <p style="color:#3a7bd5; font-size:12pt; margin-top:0;">
             <b>{APP_ABBR}</b> &nbsp;·&nbsp; version {APP_VERSION}</p>

          <p>A desktop application for characterizing brain networks across
          multiple modalities — functional network correspondence, meta-analytic
          functional decoding, molecular (PET receptor) mapping, and
          transcriptomic association — with an integrated statistical brain-map
          viewer and a utilities toolbox.</p>

          <p><b>Available for Windows, macOS and Linux.</b></p>

          <h2>Author</h2>
          <p><b>Benjamin Klugah-Brown</b><br>
          <a href="mailto:bklugah@gmail.com">bklugah@gmail.com</a></p>

          <h2>How to cite</h2>
          <p>If you use {APP_ABBR} in your work, please cite the underlying
          methods and resources it builds upon:</p>

          <h3>Network correspondence (CBIG)</h3>
          <p>Kong, R., et al. (2025). A network correspondence toolbox for
          quantitative evaluation of novel neuroimaging results.
          <i>Nature Communications, 16</i>.
          <a href="https://doi.org/10.1038/s41467-025-58176-9">https://doi.org/10.1038/s41467-025-58176-9</a><br>
          Toolbox: <i>cbig_network_correspondence</i>,
          Computational Brain Imaging Group (CBIG).</p>

          <h3>Meta-analytic functional decoding (Neurosynth / NiMARE)</h3>
          <p>Yarkoni, T., Poldrack, R. A., Nichols, T. E., Van Essen, D. C., &amp;
          Wager, T. D. (2011). Large-scale automated synthesis of human functional
          neuroimaging data. <i>Nature Methods, 8</i>(8), 665–670.</p>
          <p>Salo, T., et al. (2023). NiMARE: Neuroimaging Meta-Analysis Research
          Environment. <i>Aperture Neuro, 3</i>, 1–32.</p>

          <h3>Molecular / receptor maps (neuromaps)</h3>
          <p>Markello, R. D., et al. (2022). neuromaps: structural and functional
          interpretation of brain maps. <i>Nature Methods, 19</i>(11), 1472–1479.</p>

          <h3>Transcriptomics (Allen Human Brain Atlas / abagen)</h3>
          <p>Hawrylycz, M. J., et al. (2012). An anatomically comprehensive atlas
          of the adult human brain transcriptome. <i>Nature, 489</i>(7416),
          391–399.</p>
          <p>Markello, R. D., et al. (2021). Standardizing workflows in imaging
          transcriptomics with the abagen toolbox. <i>eLife, 10</i>, e72129.</p>

          <h3>Neuroimaging tooling</h3>
          <p>Abraham, A., et al. (2014). Machine learning for neuroimaging with
          scikit-learn (Nilearn). <i>Frontiers in Neuroinformatics, 8</i>, 14.</p>
          <p>Brett, M., et al. NiBabel: access a cacophony of neuroimaging file
          formats. https://nipy.org/nibabel/</p>

          <h2>License</h2>
          <p>Provided for research and academic use. The cited toolboxes and
          datasets retain their respective licenses; please consult each project
          for terms.</p>

          <p style="color:#888; margin-top:18px;">© 2026 Benjamin Klugah-Brown.
          {APP_NAME} ({APP_ABBR}).</p>
        </div>
        """


class HelpTab(QWidget):
    """Top-level Help tab containing Manual and About."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.addTab(ManualTab(), "Manual")
        tabs.addTab(AboutTab(), "About")
        layout.addWidget(tabs)
