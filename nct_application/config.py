"""
Configuration management for NCT
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class DataConfig:
    """Data configuration"""
    data_name: str = "MyAnalysis"
    data_space: str = "FSLMNI2mm"
    data_type: str = "Soft"
    data_threshold: Tuple[float, float] = (0, float('inf'))


@dataclass
class AnalysisConfig:
    """Analysis configuration"""
    num_permutations: int = 1000
    p_value_threshold: float = 0.05
    overlap_metric: str = "dice"
    seed: int = 42
    n_jobs: int = 1


@dataclass
class VisualizationConfig:
    """Visualization configuration"""
    clock_map: bool = True
    heatmap: bool = True
    radar_plots: bool = True
    csv_tables: bool = True
    output_format: str = "png"
    dpi: int = 300


@dataclass
class NCTConfig:
    """Main configuration container"""
    data: DataConfig
    analysis: AnalysisConfig
    visualization: VisualizationConfig
    
    def __init__(self):
        self.data = DataConfig()
        self.analysis = AnalysisConfig()
        self.visualization = VisualizationConfig()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'data': self.data.__dict__,
            'analysis': self.analysis.__dict__,
            'visualization': self.visualization.__dict__,
        }
