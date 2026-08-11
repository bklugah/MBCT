"""
Professional Brain Viewer
Interactive 3D/2D brain visualization with MNI templates
Supports multiple views (Axial, Coronal, Sagittal) and zoom/pan
"""

import numpy as np
import nibabel as nib
from pathlib import Path
from typing import Dict, Optional, Tuple
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.colors import Normalize


class BrainViewer:
    """Professional brain visualization with MNI templates"""
    
    def __init__(self, template_path: str):
        """
        Initialize brain viewer with a template
        
        Parameters
        ----------
        template_path : str
            Path to NIfTI file
        """
        self.template_path = Path(template_path)
        self.img = None
        self.data = None
        self.affine = None
        self.voxel_coords = None
        self.current_view = 'axial'
        self.current_slice = None
        
        self._load_template()
    
    def _load_template(self):
        """Load and validate NIfTI template"""
        try:
            self.img = nib.load(str(self.template_path))
            self.data = self.img.get_fdata()
            self.affine = self.img.affine
            
            # Normalize data to 0-1 range
            data_min = np.percentile(self.data, 1)
            data_max = np.percentile(self.data, 99)
            self.data = np.clip(self.data, data_min, data_max)
            self.data = (self.data - self.data.min()) / (self.data.max() - self.data.min())
            
            # Set default slice to center
            shape = self.data.shape
            self.current_slice = {
                'axial': shape[2] // 2,
                'coronal': shape[1] // 2,
                'sagittal': shape[0] // 2
            }
            
            print(f"✅ Loaded template: {self.template_path.name}")
            print(f"   Shape: {self.data.shape}")
            print(f"   Voxel size: {np.diagonal(self.affine[:3, :3])}")
            
        except Exception as e:
            print(f"❌ Error loading template: {e}")
            raise
    
    def get_slice(self, view: str = 'axial', slice_idx: Optional[int] = None) -> np.ndarray:
        """
        Get a 2D slice from the 3D volume
        
        Parameters
        ----------
        view : str
            View orientation: 'axial', 'coronal', or 'sagittal'
        slice_idx : int, optional
            Slice index. If None, uses current_slice
        
        Returns
        -------
        np.ndarray
            2D slice data
        """
        if slice_idx is None:
            slice_idx = self.current_slice[view]
        
        if view == 'axial':
            return self.data[:, :, slice_idx]
        elif view == 'coronal':
            return self.data[:, slice_idx, :]
        elif view == 'sagittal':
            return self.data[slice_idx, :, :]
        else:
            raise ValueError(f"Unknown view: {view}")
    
    def get_template_info(self) -> Dict:
        """Get template information"""
        shape = self.data.shape
        voxel_size = np.diagonal(self.affine[:3, :3])
        
        return {
            'name': self.template_path.stem,
            'shape': shape,
            'voxel_size': voxel_size,
            'voxel_size_mm': f"{abs(voxel_size[0]):.1f}×{abs(voxel_size[1]):.1f}×{abs(voxel_size[2]):.1f} mm",
            'num_voxels': np.prod(shape),
        }
    
    def get_slices_range(self, view: str) -> Tuple[int, int]:
        """Get the valid slice range for a view"""
        shape = self.data.shape
        if view == 'axial':
            return (0, shape[2] - 1)
        elif view == 'coronal':
            return (0, shape[1] - 1)
        elif view == 'sagittal':
            return (0, shape[0] - 1)
        else:
            raise ValueError(f"Unknown view: {view}")


class BrainVisualizerFactory:
    """Factory to manage multiple brain templates"""
    
    # Template configurations
    TEMPLATES = {
        'MNI_T1_Standard': {
            'description': 'MNI T1 Standard Template - High Resolution',
            'display_name': 'MNI T1 (Standard)'
        },
        'MNI_ICBM152_Asym': {
            'description': 'ICBM 152 Non-linear Asymmetric - Full Brain',
            'display_name': 'ICBM 152 (Asymmetric)'
        },
        'CH2_Better': {
            'description': 'Colin 27 T1 - High Quality Brain Template',
            'display_name': 'Colin 27 (Better)'
        },
        'CH2_BET': {
            'description': 'Colin 27 T1 - Brain Extracted',
            'display_name': 'Colin 27 (Brain Extracted)'
        },
        'CH2_Original': {
            'description': 'Colin 27 T1 - Original',
            'display_name': 'Colin 27 (Original)'
        },
        'AAL3_Atlas': {
            'description': 'AAL3 Anatomical Atlas - 170 Regions',
            'display_name': 'AAL3 Atlas'
        }
    }
    
    def __init__(self, template_dir: str = None):
        """
        Initialize factory with template directory
        
        Parameters
        ----------
        template_dir : str
            Directory containing template files
        """
        self.template_dir = Path(template_dir) if template_dir else None
        self.viewers: Dict[str, BrainViewer] = {}
        self._available_templates = {}
        
        if self.template_dir:
            self._scan_templates()
    
    def _scan_templates(self):
        """Scan directory for available templates"""
        if not self.template_dir.exists():
            print(f"⚠️  Template directory not found: {self.template_dir}")
            return
        
        # Get all .nii files
        all_nii_files = list(self.template_dir.glob('*.nii'))
        print(f"📂 Found {len(all_nii_files)} NIfTI files in {self.template_dir}")
        
        # Map filenames to template keys
        file_to_template = {
            'mni_icbm152_t1_tal_nlin_asym_09c.nii': 'MNI_ICBM152_Asym',
            'ch2better.nii': 'CH2_Better',
            'ch2bet.nii': 'CH2_BET',
            'ch2.nii': 'CH2_Original',
            'AAL3v1_1mm.nii': 'AAL3_Atlas',
            'mni_t1_standard.nii': 'MNI_T1_Standard',
            'MNI_T1.nii': 'MNI_T1_Standard',
        }
        
        # Also support files with timestamp prefixes
        for nii_file in all_nii_files:
            filename = nii_file.name
            
            # Check direct mapping first
            for pattern, template_key in file_to_template.items():
                if pattern in filename or filename == pattern:
                    self._available_templates[template_key] = str(nii_file)
                    print(f"   ✅ Found: {template_key} → {filename}")
                    break
    
    def load_template(self, template_key: str) -> Optional[BrainViewer]:
        """
        Load a template by key
        
        Parameters
        ----------
        template_key : str
            Key of template to load
        
        Returns
        -------
        BrainViewer or None
            Loaded viewer, or None if template not found
        """
        if template_key in self.viewers:
            return self.viewers[template_key]
        
        if template_key not in self._available_templates:
            print(f"⚠️  Template not available: {template_key}")
            return None
        
        try:
            viewer = BrainViewer(self._available_templates[template_key])
            self.viewers[template_key] = viewer
            return viewer
        except Exception as e:
            print(f"❌ Error loading template: {e}")
            return None
    
    def get_available_templates(self) -> Dict[str, Dict]:
        """Get list of available templates with metadata"""
        available = {}
        for key in self._available_templates.keys():
            if key in self.TEMPLATES:
                available[key] = self.TEMPLATES[key].copy()
        return available
    
    def get_template_display_name(self, template_key: str) -> str:
        """Get display name for template"""
        if template_key in self.TEMPLATES:
            return self.TEMPLATES[template_key]['display_name']
        return template_key
    
    def get_template_description(self, template_key: str) -> str:
        """Get description for template"""
        if template_key in self.TEMPLATES:
            return self.TEMPLATES[template_key]['description']
        return ''
