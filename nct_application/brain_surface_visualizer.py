"""
Professional Brain Surface Visualization using Nilearn
MRIcroGL-style statistical maps on actual brain anatomy
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# Define MNI152 affine matrix (standard brain coordinates)
MNI_AFFINE = np.array([
    [-2., 0., 0., 90.],
    [0., 2., 0., -126.],
    [0., 0., 2., -72.],
    [0., 0., 0., 1.]
])


class BrainSurfaceVisualizer:
    """Create professional brain surface visualizations like MRIcroGL"""
    
    @staticmethod
    def create_statistical_brain_map(networks, overlaps, p_values, title="Brain Statistical Map"):
        """Create MRIcroGL-style brain map with statistical overlay"""
        try:
            from nilearn import plotting
            
            # Create statistical map
            stat_map = BrainSurfaceVisualizer._create_stat_volume(networks, overlaps)
            
            if stat_map is None:
                return None
            
            cmap = 'hot'
            
            # Create our own figure first
            fig = plt.figure(figsize=(12, 5), facecolor='black')
            
            # Create orthogonal view, passing our figure
            plotting.plot_stat_map(
                stat_map,
                title=title,
                display_mode='ortho',
                cut_coords=None,
                colorbar=True,
                cmap=cmap,
                vmax=1.0,
                figure=fig,
                black_bg=True
            )
            
            # Add statistics text
            stats_text = (
                f"Mean Overlap: {np.mean(overlaps):.3f} ± {np.std(overlaps):.3f} | "
                f"Significant: {sum(1 for p in p_values if p < 0.05)} networks | "
                f"Color: Red=High, Blue=Low"
            )
            fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10, 
                    color='#a0a0a0', bbox=dict(boxstyle='round', facecolor='#1e1e2e', alpha=0.8))
            
            return fig
            
        except ImportError as e:
            print(f"Nilearn not installed: {e}")
            print("Install with: pip install nilearn")
            return None
        except Exception as e:
            print(f"Error creating brain surface map: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def create_white_matter_brain_map(tracts, overlaps, p_values, title="White Matter Statistical Map"):
        """Create brain map for white matter with tract overlays"""
        try:
            from nilearn import plotting
            
            stat_map = BrainSurfaceVisualizer._create_wm_stat_volume(tracts, overlaps)
            
            if stat_map is None:
                return None
            
            cmap = 'cool'
            
            # Create our own figure first
            fig = plt.figure(figsize=(12, 5), facecolor='black')
            
            # Create orthogonal view, passing our figure
            plotting.plot_stat_map(
                stat_map,
                title=title,
                display_mode='ortho',
                cut_coords=None,
                colorbar=True,
                cmap=cmap,
                vmax=1.0,
                figure=fig,
                black_bg=True
            )
            
            # Add statistics text
            stats_text = (
                f"Mean Overlap: {np.mean(overlaps):.3f} ± {np.std(overlaps):.3f} | "
                f"Significant: {sum(1 for p in p_values if p < 0.05)} tracts | "
                f"Color: Cyan=High, White=Low"
            )
            fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10,
                    color='#a0a0a0', bbox=dict(boxstyle='round', facecolor='#1e1e2e', alpha=0.8))
            
            return fig
            
        except Exception as e:
            print(f"Error creating white matter brain map: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def create_multimodal_brain_map(networks, gm_overlaps, tracts, wm_overlaps, 
                                    gm_p_values, wm_p_values, title="Multimodal Brain Map"):
        """Create combined gray matter and white matter statistical map"""
        try:
            from nilearn import plotting
            
            stat_map = BrainSurfaceVisualizer._create_multimodal_stat_volume(
                networks, gm_overlaps, tracts, wm_overlaps
            )
            
            if stat_map is None:
                return None
            
            cmap = 'viridis'
            
            # Create our own figure first
            fig = plt.figure(figsize=(12, 5), facecolor='black')
            
            # Create orthogonal view, passing our figure
            plotting.plot_stat_map(
                stat_map,
                title=title,
                display_mode='ortho',
                cut_coords=None,
                colorbar=True,
                cmap=cmap,
                vmax=1.0,
                figure=fig,
                black_bg=True
            )
            
            # Add statistics text
            stats_text = (
                f"GM: {np.mean(gm_overlaps):.3f}±{np.std(gm_overlaps):.3f} | "
                f"WM: {np.mean(wm_overlaps):.3f}±{np.std(wm_overlaps):.3f} | "
                f"Color: Purple=Low, Yellow=High"
            )
            fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10,
                    color='#a0a0a0', bbox=dict(boxstyle='round', facecolor='#1e1e2e', alpha=0.8))
            
            return fig
            
        except Exception as e:
            print(f"Error creating multimodal brain map: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def _create_stat_volume(networks, overlaps):
        """Create synthetic 3D statistical volume for gray matter"""
        try:
            import nibabel as nib
            from nibabel.nifti1 import Nifti1Image
            
            # Create synthetic brain volume
            stat_volume = np.zeros((91, 109, 91), dtype=np.float32)
            
            # Distribute network overlaps
            for i, overlap in enumerate(overlaps):
                center_y = 20 + i*7
                center_x = 35 + i*9
                center_z = 30 + i*8
                
                # Create Gaussian blob for each network
                for dy in range(-8, 8):
                    for dx in range(-8, 8):
                        for dz in range(-8, 8):
                            y = int(center_y + dy)
                            x = int(center_x + dx)
                            z = int(center_z + dz)
                            
                            if 0 <= y < 91 and 0 <= x < 109 and 0 <= z < 91:
                                dist = np.sqrt(dy**2 + dx**2 + dz**2)
                                weight = np.exp(-(dist**2) / 20)
                                stat_volume[y, x, z] = max(stat_volume[y, x, z], overlap * weight)
            
            # Create Nifti image
            stat_img = Nifti1Image(stat_volume, MNI_AFFINE)
            
            return stat_img
            
        except Exception as e:
            print(f"Error creating stat volume: {e}")
            return None
    
    @staticmethod
    def _create_wm_stat_volume(tracts, overlaps):
        """Create synthetic 3D statistical volume for white matter"""
        try:
            import nibabel as nib
            from nibabel.nifti1 import Nifti1Image
            
            stat_volume = np.zeros((91, 109, 91), dtype=np.float32)
            
            # Distribute WM tract overlaps
            for i, overlap in enumerate(overlaps):
                center_y = 25 + i*6
                center_x = 40 + i*8
                center_z = 35 + i*7
                
                for dy in range(-8, 8):
                    for dx in range(-8, 8):
                        for dz in range(-8, 8):
                            y = int(center_y + dy)
                            x = int(center_x + dx)
                            z = int(center_z + dz)
                            
                            if 0 <= y < 91 and 0 <= x < 109 and 0 <= z < 91:
                                dist = np.sqrt(dy**2 + dx**2 + dz**2)
                                weight = np.exp(-(dist**2) / 20)
                                stat_volume[y, x, z] = max(stat_volume[y, x, z], overlap * weight)
            
            stat_img = Nifti1Image(stat_volume, MNI_AFFINE)
            
            return stat_img
            
        except Exception as e:
            print(f"Error creating WM stat volume: {e}")
            return None
    
    @staticmethod
    def _create_multimodal_stat_volume(networks, gm_overlaps, tracts, wm_overlaps):
        """Create combined GM and WM statistical volume"""
        try:
            import nibabel as nib
            from nibabel.nifti1 import Nifti1Image
            
            stat_volume = np.zeros((91, 109, 91), dtype=np.float32)
            
            # Map GM networks
            for i, overlap in enumerate(gm_overlaps):
                center_y = 20 + i*7
                center_x = 35 + i*9
                center_z = 30 + i*8
                
                for dy in range(-8, 8):
                    for dx in range(-8, 8):
                        for dz in range(-8, 8):
                            y = int(center_y + dy)
                            x = int(center_x + dx)
                            z = int(center_z + dz)
                            
                            if 0 <= y < 91 and 0 <= x < 109 and 0 <= z < 91:
                                dist = np.sqrt(dy**2 + dx**2 + dz**2)
                                weight = np.exp(-(dist**2) / 20)
                                stat_volume[y, x, z] = max(stat_volume[y, x, z], overlap * weight * 0.7)
            
            # Map WM tracts
            for i, overlap in enumerate(wm_overlaps):
                center_y = 25 + i*6
                center_x = 40 + i*8
                center_z = 35 + i*7
                
                for dy in range(-8, 8):
                    for dx in range(-8, 8):
                        for dz in range(-8, 8):
                            y = int(center_y + dy)
                            x = int(center_x + dx)
                            z = int(center_z + dz)
                            
                            if 0 <= y < 91 and 0 <= x < 109 and 0 <= z < 91:
                                dist = np.sqrt(dy**2 + dx**2 + dz**2)
                                weight = np.exp(-(dist**2) / 20)
                                stat_volume[y, x, z] = max(stat_volume[y, x, z], overlap * weight * 0.7)
            
            stat_img = Nifti1Image(stat_volume, MNI_AFFINE)
            
            return stat_img
            
        except Exception as e:
            print(f"Error creating multimodal stat volume: {e}")
            return None
