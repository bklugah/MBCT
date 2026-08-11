"""Data management for NCT"""

import numpy as np


class DataManager:
    """Manages data loading and processing"""
    
    def __init__(self):
        self.data = None
        self.metadata = {}
    
    def load_nifti(self, file_path):
        """Load NIfTI file"""
        try:
            import nibabel as nib
            img = nib.load(file_path)
            self.data = img.get_fdata()
            self.metadata['shape'] = self.data.shape
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False
    
    def get_data(self):
        """Get loaded data"""
        return self.data
