"""
NeuroSynthesis NCT - Network Correspondence Toolbox
Backend module for brain network analysis
"""

__version__ = "1.0.0"
__author__ = "NeuroSynthesis"

from .application import NCTApplication
from .config import NCTConfig, DataConfig, AnalysisConfig

__all__ = [
    'NCTApplication',
    'NCTConfig',
    'DataConfig',
    'AnalysisConfig',
]
