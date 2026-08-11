"""
CBIG Atlas Loader - Complete Implementation
Handles all 455 atlases across 5 spaces and 10 authors
"""

import nibabel as nib
import scipy.io as sio
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np


class CBIGAtlasLoader:
    """Load and manage CBIG atlases from local repository"""
    
    # All atlases organized by space and author
    ATLASES_STRUCTURE = {
        'FSLMNI2mm': {
            'Du': ['DU15NET'],
            'Glasser': ['MG360J12'],
            'HCPICA': [f'HCPICA_thresh_zstat{i}' for i in range(1, 21)],  # 20 components
            'Laird': [f'AL20_zstat{i}' for i in range(1, 21)],             # 20 components
            'Shen': ['XS268_8', 'XS368_8'],
            'Shirer': ['WS90_14'],
            'UKBICA': [f'UKBICA_thresh_zstat{i}' for i in range(1, 21)],   # 20 components
            'WashU': ['EG5', 'EG17', 'EG286_12', 'TL12'],
            'Woodward': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                        'TW_TASK_NETS_1RESP', 'TW_TASK_NETS_2RESP', 'TW_TASK_NETS_AAR',
                        'TW_TASK_NETS_AUD', 'TW_TASK_NETS_DMNA', 'TW_TASK_NETS_DMNB',
                        'TW_TASK_NETS_FoVF', 'TW_TASK_NETS_INIT'],  # 12 variants (expanded from zip analysis)
            'YeoLab': ['AS200K17', 'AS200Y17', 'AS400K17', 'AS400Y17',
                       'XY200K17', 'XY200Y17', 'XY400K17', 'XY400Y17',
                       'TY7', 'TY17'],  # 10 files
        },
        'LairdColin2mm': {},  # Same structure as FSLMNI2mm
        'ShenColin1mm': {},   # Same structure as FSLMNI2mm
        'fs_LR_32k': {},      # Same structure, .mat format
        'fsaverage6': {},     # Same structure, .mat format
    }
    
    # Copy structure to other spaces
    for space in ['LairdColin2mm', 'ShenColin1mm', 'fs_LR_32k', 'fsaverage6']:
        ATLASES_STRUCTURE[space] = ATLASES_STRUCTURE['FSLMNI2mm'].copy()
    
    # File extensions by space type
    SPACE_FILE_TYPES = {
        'FSLMNI2mm': '.nii.gz',
        'LairdColin2mm': '.nii.gz',
        'ShenColin1mm': '.nii.gz',
        'fs_LR_32k': '.mat',
        'fsaverage6': '.mat',
    }
    
    def __init__(self, atlas_data_path: str):
        """
        Initialize CBIG atlas loader
        
        Parameters:
        -----------
        atlas_data_path : str
            Path to cbig_network_correspondence_data/ or cbig_network_correspondence_data/atlases/
        """
        atlas_root = Path(atlas_data_path)
        
        # If path doesn't exist, try looking for atlases subfolder
        if not atlas_root.exists():
            raise FileNotFoundError(f"Atlas directory not found: {atlas_root}")
        
        # Check if this is the parent directory containing an 'atlases' subfolder
        atlases_subfolder = atlas_root / "atlases"
        if atlases_subfolder.exists() and not (atlas_root / "FSLMNI2mm").exists():
            # Use the atlases subfolder
            self.atlas_root = atlases_subfolder
            print(f"✅ Found atlases subfolder, using: {self.atlas_root}")
        else:
            # Use the provided path directly
            self.atlas_root = atlas_root
        
        if not self.atlas_root.exists():
            raise FileNotFoundError(f"Atlas directory not found: {self.atlas_root}")
        
        print(f"✅ CBIG Atlas Loader initialized: {self.atlas_root}")
        self._verify_structure()
    
    def _verify_structure(self):
        """Verify atlas directory structure"""
        for space in self.ATLASES_STRUCTURE.keys():
            space_dir = self.atlas_root / space
            if not space_dir.exists():
                print(f"⚠️  Missing space directory: {space}")
            else:
                print(f"✅ Found space: {space}")
    
    def get_spaces(self) -> List[str]:
        """Return list of available spaces"""
        return list(self.ATLASES_STRUCTURE.keys())
    
    def get_authors(self) -> List[str]:
        """Return list of all authors"""
        return list(self.ATLASES_STRUCTURE['FSLMNI2mm'].keys())
    
    def get_atlases_for_author(self, author: str) -> List[str]:
        """Get all atlases for a specific author (same across all spaces)"""
        if author in self.ATLASES_STRUCTURE['FSLMNI2mm']:
            return self.ATLASES_STRUCTURE['FSLMNI2mm'][author]
        return []
    
    def get_atlas_path(self, space: str, author: str, atlas_name: str) -> Optional[Path]:
        """Get full file path for an atlas"""
        ext = self.SPACE_FILE_TYPES[space]
        filepath = self.atlas_root / space / author / f"{atlas_name}{ext}"
        
        if filepath.exists():
            return filepath
        else:
            print(f"❌ Atlas file not found: {filepath}")
            return None
    
    def load_atlas_data(self, space: str, author: str, atlas_name: str) -> Optional[np.ndarray]:
        """
        Load atlas data from file
        
        Returns:
        --------
        np.ndarray : Atlas data (voxel or surface labels)
        """
        filepath = self.get_atlas_path(space, author, atlas_name)
        if not filepath:
            return None
        
        try:
            if str(filepath).endswith('.nii.gz'):
                # Load NIfTI file
                img = nib.load(filepath)
                data = img.get_fdata()
                print(f"✅ Loaded atlas: {author}/{atlas_name} (shape: {data.shape})")
                return data
            
            elif str(filepath).endswith('.mat'):
                # Load MATLAB file
                mat_data = sio.loadmat(filepath)
                # Extract the atlas array (usually in a specific variable)
                # CBIG .mat files typically have structure, need to handle appropriately
                if 'atlas' in mat_data:
                    data = mat_data['atlas']
                else:
                    # Get the first non-metadata variable
                    data = [v for k, v in mat_data.items() if not k.startswith('__')][0]
                print(f"✅ Loaded atlas: {author}/{atlas_name} (shape: {data.shape})")
                return data
        
        except Exception as e:
            print(f"❌ Error loading atlas {author}/{atlas_name}: {e}")
            return None
    
    def list_all_atlases(self) -> Dict[str, List[Tuple[str, str]]]:
        """
        List all available atlases
        
        Returns:
        --------
        dict : Organized by space: {space: [(author, atlas_name), ...]}
        """
        all_atlases = {}
        for space in self.get_spaces():
            atlases = []
            for author in self.get_authors():
                for atlas_name in self.get_atlases_for_author(author):
                    atlases.append((author, atlas_name))
            all_atlases[space] = atlases
        
        return all_atlases
    
    def get_total_atlas_count(self) -> int:
        """Get total number of atlases across all spaces"""
        return sum(len(atlases) for atlases in self.list_all_atlases().values())
    
    def get_atlas_info(self, space: str, author: str, atlas_name: str) -> Dict[str, any]:
        """
        Get information about an atlas including dimensions and number of regions
        
        Returns:
        --------
        dict : {'status': 'success', 'shape': (x,y,z), 'num_regions': n, ...}
        """
        try:
            atlas_data = self.load_atlas_data(space, author, atlas_name)
            if atlas_data is None:
                return {'status': 'error', 'message': 'Could not load atlas data'}
            
            shape = atlas_data.shape
            
            # Count unique regions (exclude 0)
            import numpy as np
            unique_regions = len(np.unique(atlas_data[atlas_data > 0]))
            
            return {
                'status': 'success',
                'shape': shape,
                'dimensions': f"{shape[0]}×{shape[1]}×{shape[2]}",
                'num_regions': unique_regions,
                'voxel_size': '1mm' if shape == (182, 218, 182) else ('2mm' if shape in [(91, 109, 91)] else 'unknown'),
            }
        
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        
        all_atlases = self.list_all_atlases()
        
        for space in self.get_spaces():
            atlases = all_atlases[space]
            print(f"\n🌐 {space}: {len(atlases)} atlases")
            
            author_counts = {}
            for author, _ in atlases:
                author_counts[author] = author_counts.get(author, 0) + 1
            
            for author, count in sorted(author_counts.items()):
                print(f"   {author}: {count} files")
        
        total = sum(len(atlases) for atlases in all_atlases.values())
        print(f"\n✅ TOTAL: {total} atlases across {len(self.get_spaces())} spaces")
        print("="*70 + "\n")


class CBIGAtlasAnalysis:
    """Perform overlap analysis with CBIG atlases"""
    
    @staticmethod
    def compute_dice(mask1: np.ndarray, mask2: np.ndarray) -> float:
        """
        Compute Dice similarity coefficient
        
        Parameters:
        -----------
        mask1, mask2 : np.ndarray
            Binary masks
        
        Returns:
        --------
        float : Dice coefficient (0 to 1)
        """
        intersection = np.sum(mask1 & mask2)
        if intersection == 0:
            return 0.0
        
        dice = 2.0 * intersection / (np.sum(mask1) + np.sum(mask2))
        return float(np.clip(dice, 0, 1))
    
    @staticmethod
    def compute_jaccard(mask1: np.ndarray, mask2: np.ndarray) -> float:
        """Compute Jaccard similarity coefficient"""
        intersection = np.sum(mask1 & mask2)
        union = np.sum(mask1 | mask2)
        
        if union == 0:
            return 0.0
        
        jaccard = intersection / union
        return float(np.clip(jaccard, 0, 1))
    
    @staticmethod
    def compute_overlap(mask1: np.ndarray, mask2: np.ndarray) -> float:
        """Compute overlap percentage"""
        if np.sum(mask1) == 0:
            return 0.0
        
        overlap = np.sum(mask1 & mask2) / np.sum(mask1)
        return float(np.clip(overlap, 0, 1))
    
    @staticmethod
    def compute_metrics(user_data: np.ndarray, atlas_data: np.ndarray) -> Dict[str, float]:
        """
        Compute multiple overlap metrics
        
        Returns:
        --------
        dict : {'dice': float, 'jaccard': float, 'overlap': float}
        """
        # Create binary masks
        user_binary = user_data > (np.max(user_data) * 0.1)
        atlas_binary = atlas_data > 0
        
        return {
            'dice': CBIGAtlasAnalysis.compute_dice(user_binary, atlas_binary),
            'jaccard': CBIGAtlasAnalysis.compute_jaccard(user_binary, atlas_binary),
            'overlap': CBIGAtlasAnalysis.compute_overlap(user_binary, atlas_binary),
        }
