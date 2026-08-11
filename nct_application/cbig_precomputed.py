"""
Use precomputed CBIG overlap results from overlap_results/ folder.
These are 2.2MB of .mat files with atlas-vs-atlas overlaps already computed.
"""

import numpy as np
import scipy.io as sio
from pathlib import Path


class PrecomputedCBIGAnalysis:
    """Load and parse precomputed CBIG overlap matrices"""
    
    def __init__(self, atlas_data_dir):
        """
        Initialize with path to atlas data directory.
        Expects overlap_results/ subfolder with precomputed matrices.
        """
        self.atlas_data_dir = Path(atlas_data_dir)
        self.overlap_results_dir = self.atlas_data_dir / 'overlap_results'
        
        if not self.overlap_results_dir.exists():
            raise FileNotFoundError(f"overlap_results/ not found at {self.overlap_results_dir}")
        
        print(f"✅ Precomputed results directory: {self.overlap_results_dir}")
    
    def get_precomputed_overlap(self, ref_atlas, test_atlas):
        """
        Load precomputed overlap between ref_atlas and test_atlas.
        
        Format: overlap_results/ref_atlas/test_atlas.mat
        Inside: {'overlap': numpy array (n_ref_networks, n_test_networks)}
        
        Returns:
            overlaps: 1D numpy array of overlap values (max per ref network)
            OR None if file not found
        """
        mat_file = self.overlap_results_dir / ref_atlas / f"{test_atlas}.mat"
        
        if not mat_file.exists():
            print(f"  ⚠️ Precomputed file not found: {mat_file}")
            return None
        
        try:
            print(f"  📂 Loading: {mat_file.name}")
            data = sio.loadmat(str(mat_file))
            
            # Extract 'overlap' key
            if 'overlap' in data:
                overlap_matrix = data['overlap']
            else:
                # Try first non-metadata key
                keys = [k for k in data.keys() if not k.startswith('__')]
                if not keys:
                    return None
                overlap_matrix = data[keys[0]]
            
            overlap_matrix = np.array(overlap_matrix, dtype=float)
            print(f"    Shape: {overlap_matrix.shape}")
            
            # If 2D, take max per row (overlap per ref network)
            if overlap_matrix.ndim == 2:
                overlaps = np.max(overlap_matrix, axis=1)
            elif overlap_matrix.ndim == 1:
                overlaps = overlap_matrix
            else:
                overlaps = np.ravel(overlap_matrix)
            
            print(f"    Overlaps: {len(overlaps)} networks, mean={np.mean(overlaps):.3f}")
            return overlaps
        
        except Exception as e:
            print(f"  ❌ Error loading {mat_file.name}: {e}")
            return None
    
    def analyze_with_precomputed(self, ref_atlas, test_atlases):
        """
        Get precomputed overlaps for ref_atlas vs multiple test_atlases.
        
        Args:
            ref_atlas: Reference atlas (e.g., 'TY7')
            test_atlases: List of atlases to compare (e.g., ['MG360J12'])
        
        Returns:
            dict with status, results
        """
        results = {}
        
        for test_atlas in test_atlases:
            overlaps = self.get_precomputed_overlap(ref_atlas, test_atlas)
            
            if overlaps is not None and len(overlaps) > 0:
                results[test_atlas] = {
                    'overlaps': overlaps.tolist(),
                    'n_networks': len(overlaps),
                    'mean_overlap': float(np.mean(overlaps)),
                    'source': 'precomputed',
                }
            else:
                results[test_atlas] = {
                    'overlaps': [],
                    'n_networks': 0,
                    'mean_overlap': 0,
                    'error': 'Precomputed file not found',
                }
        
        return {
            'status': 'success' if any(r['n_networks'] > 0 for r in results.values()) else 'error',
            'results': results
        }
    
    def list_available_overlaps(self):
        """List all available precomputed overlap combinations"""
        available = {}
        
        if not self.overlap_results_dir.exists():
            return available
        
        for ref_dir in self.overlap_results_dir.iterdir():
            if ref_dir.is_dir():
                ref_atlas = ref_dir.name
                mat_files = list(ref_dir.glob('*.mat'))
                test_atlases = [f.stem for f in mat_files]
                available[ref_atlas] = test_atlases
        
        return available
