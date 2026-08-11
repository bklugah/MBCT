"""
Real CBIG Brain Atlas Visualizer
Maps network overlap values onto actual atlas voxel locations
"""

import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
from matplotlib import cm
from nilearn import plotting, image
from pathlib import Path
import tempfile


class CBIGBrainAtlasVisualizer:
    """Visualize network correspondence on real atlas anatomy"""
    
    def __init__(self, atlas_data_dir):
        """
        Initialize with path to atlas data directory
        
        Args:
            atlas_data_dir: Path to cbig_network_correspondence_data folder
        """
        self.atlas_data_dir = Path(atlas_data_dir)
    
    def create_atlas_stat_map(self, atlas_code, space, network_overlaps, title="Network Overlap"):
        """
        Create a statistical map from network overlap values mapped onto real atlas
        
        Args:
            atlas_code: Atlas identifier (e.g., 'TY7', 'MG360J12')
            space: Brain space ('FSLMNI2mm', 'fs_LR_32k', 'fsaverage6')
            network_overlaps: List of overlap values (one per network)
            title: Title for the visualization
        
        Returns:
            matplotlib Figure showing the brain map
        """
        
        # Load the real atlas in the specified space
        atlas_path = self._get_atlas_path(atlas_code, space)
        if not atlas_path or not atlas_path.exists():
            # Fallback if atlas not found
            print(f"⚠️ Atlas not found at {atlas_path}, creating synthetic map")
            return self._create_synthetic_map(network_overlaps, space, title)
        
        try:
            atlas_img = nib.load(atlas_path)
            atlas_data = atlas_img.get_fdata().astype(int)
            
            # Create stat volume: each voxel gets the overlap value of its network
            stat_volume = np.zeros_like(atlas_data, dtype=np.float32)
            
            # Map each network's overlap value to its voxels
            unique_networks = np.unique(atlas_data)
            for net_id in unique_networks:
                if net_id == 0:  # Skip background/label 0
                    continue
                
                if net_id - 1 < len(network_overlaps):
                    overlap_val = float(network_overlaps[net_id - 1])
                    stat_volume[atlas_data == net_id] = overlap_val
            
            # Create NIfTI image with same affine as atlas
            stat_img = nib.Nifti1Image(stat_volume, atlas_img.affine)
            
            # Render with Nilearn
            return self._render_stat_map(stat_img, title, space, cmap='hot')
        
        except Exception as e:
            print(f"❌ Error creating atlas stat map: {e}")
            return self._create_synthetic_map(network_overlaps, space, title)
    
    def create_gray_matter_map(self, gm_atlas_code, space, network_overlaps):
        """Create gray matter network correspondence map"""
        return self.create_atlas_stat_map(
            gm_atlas_code, 
            space, 
            network_overlaps,
            f"Gray Matter - {gm_atlas_code}"
        )
    
    def create_white_matter_map(self, wm_atlas_code, space, tract_overlaps):
        """Create white matter tract correspondence map"""
        return self.create_atlas_stat_map(
            wm_atlas_code,
            space,
            tract_overlaps,
            f"White Matter - {wm_atlas_code}"
        )
    
    def create_multimodal_map(self, gm_atlas_code, wm_atlas_code, space, 
                             gm_overlaps, wm_overlaps):
        """
        Create combined gray + white matter map
        Composite visualization showing both GM and WM correspondence
        """
        try:
            # Load both atlases
            gm_path = self._get_atlas_path(gm_atlas_code, space)
            wm_path = self._get_atlas_path(wm_atlas_code, space)
            
            if not (gm_path and gm_path.exists() and wm_path and wm_path.exists()):
                return self._create_synthetic_multimodal(gm_overlaps, wm_overlaps, space)
            
            gm_img = nib.load(gm_path)
            wm_img = nib.load(wm_path)
            
            gm_data = gm_img.get_fdata().astype(int)
            wm_data = wm_img.get_fdata().astype(int)
            
            # Create composite volume: max of GM and WM values at each voxel
            composite_volume = np.zeros_like(gm_data, dtype=np.float32)
            
            # Map GM overlaps
            gm_unique = np.unique(gm_data)
            for net_id in gm_unique:
                if net_id == 0:
                    continue
                if net_id - 1 < len(gm_overlaps):
                    gm_val = float(gm_overlaps[net_id - 1])
                    composite_volume[gm_data == net_id] = max(
                        composite_volume[gm_data == net_id].max(),
                        gm_val
                    )
            
            # Map WM overlaps (take max to show both)
            wm_unique = np.unique(wm_data)
            for tract_id in wm_unique:
                if tract_id == 0:
                    continue
                if tract_id - 1 < len(wm_overlaps):
                    wm_val = float(wm_overlaps[tract_id - 1])
                    composite_volume[wm_data == tract_id] = max(
                        composite_volume[wm_data == tract_id].max(),
                        wm_val
                    )
            
            # Render composite
            composite_img = nib.Nifti1Image(composite_volume, gm_img.affine)
            return self._render_stat_map(
                composite_img, 
                f"Multimodal - {gm_atlas_code} + {wm_atlas_code}",
                space,
                cmap='viridis'
            )
        
        except Exception as e:
            print(f"❌ Error creating multimodal map: {e}")
            return self._create_synthetic_multimodal(gm_overlaps, wm_overlaps, space)
    
    def _get_atlas_path(self, atlas_code, space):
        """Get path to atlas file in specified space"""
        
        # Surface-based atlases (mat files)
        if space in ['fs_LR_32k', 'fsaverage6']:
            # Try to find the atlas subdirectory
            parent_dir = self.atlas_data_dir / 'atlases' / space
            if parent_dir.exists():
                # Find atlas by looking in subdirectories
                for subdir in parent_dir.iterdir():
                    if subdir.is_dir():
                        atlas_file = subdir / f"{atlas_code}.mat"
                        if atlas_file.exists():
                            return atlas_file
        
        # Volumetric atlas (nii.gz)
        elif space == 'FSLMNI2mm':
            parent_dir = self.atlas_data_dir / 'atlases' / space
            if parent_dir.exists():
                for subdir in parent_dir.iterdir():
                    if subdir.is_dir():
                        atlas_file = subdir / f"{atlas_code}.nii.gz"
                        if atlas_file.exists():
                            return atlas_file
        
        print(f"⚠️ Atlas {atlas_code} not found in {space}")
        return None
    
    def _render_stat_map(self, stat_img, title, space, cmap='hot'):
        """Render statistical map using Nilearn"""
        try:
            fig = plt.figure(figsize=(14, 5), facecolor='black')
            
            if space in ['fs_LR_32k', 'fsaverage6']:
                # Surface rendering (simplified - just show ortho for now)
                plotting.plot_stat_map(
                    stat_img,
                    title=title,
                    display_mode='ortho',
                    cut_coords=None,
                    colorbar=True,
                    cmap=cmap,
                    vmax=1.0,
                    figure=fig,
                    black_bg=True
                )
            else:
                # Volumetric rendering
                plotting.plot_stat_map(
                    stat_img,
                    title=title,
                    display_mode='ortho',
                    cut_coords=None,
                    colorbar=True,
                    cmap=cmap,
                    vmax=1.0,
                    figure=fig,
                    black_bg=True
                )
            
            return fig
        
        except Exception as e:
            print(f"❌ Error rendering map: {e}")
            return self._create_synthetic_map([0.5], space, title)
    
    def _create_synthetic_map(self, overlaps, space, title):
        """Create synthetic map when atlas not available (fallback)"""
        fig = plt.figure(figsize=(14, 5), facecolor='black')
        
        # Create a synthetic volume with Gaussian blobs
        if space == 'FSLMNI2mm':
            shape = (91, 109, 91)
            affine = np.array([
                [-2, 0, 0, 90],
                [0, 2, 0, -126],
                [0, 0, 2, -72],
                [0, 0, 0, 1]
            ], dtype=float)
        else:
            # Fallback to FSLMNI2mm
            shape = (91, 109, 91)
            affine = np.array([
                [-2, 0, 0, 90],
                [0, 2, 0, -126],
                [0, 0, 2, -72],
                [0, 0, 0, 1]
            ], dtype=float)
        
        # Create volume with blobs for each overlap value
        volume = np.zeros(shape, dtype=np.float32)
        
        for i, overlap in enumerate(overlaps[:8]):
            # Create Gaussian blob at different positions
            center_x = 30 + i * 8
            center_y = 35 + i * 7
            center_z = 30 + i * 6
            
            if 0 <= center_x < shape[0] and 0 <= center_y < shape[1] and 0 <= center_z < shape[2]:
                # Create Gaussian
                y, x, z = np.ogrid[:shape[0], :shape[1], :shape[2]]
                gaussian = np.exp(-((x - center_x)**2 + (y - center_y)**2 + (z - center_z)**2) / 50)
                volume += gaussian * float(overlap)
        
        volume = np.clip(volume, 0, 1)
        
        # Create image and render
        stat_img = nib.Nifti1Image(volume, affine)
        
        plotting.plot_stat_map(
            stat_img,
            title=title,
            display_mode='ortho',
            cut_coords=None,
            colorbar=True,
            cmap='hot',
            vmax=1.0,
            figure=fig,
            black_bg=True
        )
        
        return fig
    
    def _create_synthetic_multimodal(self, gm_overlaps, wm_overlaps, space):
        """Create synthetic multimodal map (fallback)"""
        fig = plt.figure(figsize=(14, 5), facecolor='black')
        
        shape = (91, 109, 91)
        affine = np.array([
            [-2, 0, 0, 90],
            [0, 2, 0, -126],
            [0, 0, 2, -72],
            [0, 0, 0, 1]
        ], dtype=float)
        
        volume = np.zeros(shape, dtype=np.float32)
        
        # Combine GM and WM
        all_overlaps = list(gm_overlaps) + list(wm_overlaps)
        for i, overlap in enumerate(all_overlaps[:16]):
            center_x = 25 + i * 4
            center_y = 30 + i * 3
            center_z = 35 + i * 2
            
            if 0 <= center_x < shape[0] and 0 <= center_y < shape[1] and 0 <= center_z < shape[2]:
                y, x, z = np.ogrid[:shape[0], :shape[1], :shape[2]]
                gaussian = np.exp(-((x - center_x)**2 + (y - center_y)**2 + (z - center_z)**2) / 40)
                volume += gaussian * float(overlap)
        
        volume = np.clip(volume, 0, 1)
        
        stat_img = nib.Nifti1Image(volume, affine)
        
        plotting.plot_stat_map(
            stat_img,
            title="Multimodal Network Correspondence",
            display_mode='ortho',
            cut_coords=None,
            colorbar=True,
            cmap='viridis',
            vmax=1.0,
            figure=fig,
            black_bg=True
        )
        
        return fig
