"""
Handle results processing, storage, and export
"""

import numpy as np
from pathlib import Path


class ResultsHandler:
    """Process and manage analysis results"""
    
    def __init__(self):
        self.current_results = None
        self.network_names = []
        self.overlap_values = []
        self.p_values = []
        self.metric_type = 'Dice'
        self.atlas_name = None
        self.brain_space = None
    
    def process_results(self, cbig_results, atlas_name, brain_space='FSLMNI2mm'):
        """
        Process CBIG analysis results
        
        Args:
            cbig_results: Results dict from analyze()
            atlas_name: Name of atlas used (e.g., 'AL20', 'TY7')
            brain_space: Brain space used (FSLMNI2mm, fsaverage6, fs_LR_32k)
        """
        self.atlas_name = atlas_name
        self.brain_space = brain_space
        
        # Extract data
        self.network_names = cbig_results.get('networks', [])
        self.overlap_values = cbig_results.get('overlaps', [])
        self.p_values = cbig_results.get('p_values', [])
        self.metric_type = cbig_results.get('overlap_metric', 'Dice')
        
        # Create comprehensive results dict
        self.current_results = {
            'atlas': atlas_name,
            'brain_space': brain_space,
            'networks': self.network_names,
            'overlaps': self.overlap_values,
            'p_values': self.p_values,
            'overlap_metric': self.metric_type,
            'num_networks': len(self.network_names),
            'mean_overlap': float(np.mean(self.overlap_values)) if self.overlap_values else 0,
            'max_overlap': float(np.max(self.overlap_values)) if self.overlap_values else 0,
            'min_overlap': float(np.min(self.overlap_values)) if self.overlap_values else 0,
        }
        
        return self.current_results
    
    def get_table_data(self):
        """Get formatted table data"""
        return {
            'networks': self.network_names,
            'overlaps': self.overlap_values,
            'p_values': self.p_values,
            'metric': self.metric_type,
        }
    
    def get_export_data(self):
        """Get data ready for export"""
        return {
            'atlas': self.atlas_name,
            'space': self.brain_space,
            'networks': self.network_names,
            'overlaps': self.overlap_values,
            'p_values': self.p_values,
            'metric': self.metric_type,
        }
    
    def validate(self):
        """Check if results are valid"""
        if not self.current_results:
            return False, "No results loaded"
        
        if len(self.network_names) == 0:
            return False, "No network names"
        
        if len(self.overlap_values) != len(self.network_names):
            return False, "Mismatch between networks and overlaps"
        
        return True, "Results valid"
