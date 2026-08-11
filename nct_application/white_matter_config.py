"""
White Matter Atlas Configuration
Manages white matter atlases (ICBM_Wmpm, JHU-ICBM, etc.)
"""

from pathlib import Path
import json

class WhiteMatterConfig:
    """Configuration for white matter atlases."""
    
    # Standard atlas definitions
    ATLASES = {
        'ICBM_Wmpm': {
            'name': 'ICBM White Matter Probability Map',
            'space': 'MNI152',
            'description': 'Probabilistic white matter atlas from ICBM DTI 81',
            'file': 'ICBM_DTI_81_WMPM',
            'labels_file': 'MniLabelLookupTable.txt',
            'n_regions': 56,
        },
        'JHU-ICBM': {
            'name': 'JHU White Matter Tracts',
            'space': 'MNI152',
            'description': 'Johns Hopkins University white matter tract atlas',
            'file': 'JHU-ICBM-tracts-prob-1mm.nii.gz',
            'labels_file': 'JHU-ICBM-labels-1mm.nii.gz',
            'labels_xml': 'JHU-tracts.xml',
            'n_regions': 20,
        },
    }
    
    # Standard dimensions for conversion
    STANDARD_DIMENSIONS = {
        'FSLMNI2mm': {
            'shape': (91, 109, 91),
            'voxel_size': 2.0,
            'description': 'FSL MNI 2mm (91×109×91)',
        },
        'FSLMNI1mm': {
            'shape': (182, 218, 182),
            'voxel_size': 1.0,
            'description': 'FSL MNI 1mm (182×218×182)',
        },
        'FSLMNI4mm': {
            'shape': (46, 55, 46),
            'voxel_size': 4.0,
            'description': 'FSL MNI 4mm (46×55×46)',
        },
        'MNI_2mm': {
            'shape': (91, 109, 91),
            'voxel_size': 2.0,
            'description': 'Standard MNI 2mm template',
        },
    }
    
    @staticmethod
    def get_atlas_dir():
        """Get white matter atlas directory."""
        project_root = Path(__file__).parent.parent
        atlas_dir = project_root / 'white_matter_atlases' / 'whitematteratlasses'
        
        if atlas_dir.exists():
            return str(atlas_dir)
        return None
    
    @staticmethod
    def get_atlas_info(atlas_code):
        """Get information about a white matter atlas."""
        return WhiteMatterConfig.ATLASES.get(atlas_code, {})
    
    @staticmethod
    def get_dimension_info(dim_code):
        """Get information about a standard dimension."""
        return WhiteMatterConfig.STANDARD_DIMENSIONS.get(dim_code, {})
    
    @staticmethod
    def list_atlases():
        """List available white matter atlases."""
        return list(WhiteMatterConfig.ATLASES.keys())
    
    @staticmethod
    def list_dimensions():
        """List available standard dimensions."""
        return list(WhiteMatterConfig.STANDARD_DIMENSIONS.keys())
    
    @staticmethod
    def validate_atlas(atlas_code):
        """Check if atlas exists and is accessible."""
        if atlas_code not in WhiteMatterConfig.ATLASES:
            return False, f"Unknown atlas: {atlas_code}"
        
        atlas_dir = WhiteMatterConfig.get_atlas_dir()
        if not atlas_dir:
            return False, "White matter atlas directory not found"
        
        atlas_path = Path(atlas_dir) / atlas_code
        if not atlas_path.exists():
            return False, f"Atlas directory not found: {atlas_path}"
        
        return True, "OK"
