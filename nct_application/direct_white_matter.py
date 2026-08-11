"""
Direct White Matter Analysis - JHU-ICBM
Computes overlaps between user image and JHU-ICBM white matter atlases
No CBIG dependency - direct computation using NIfTI files
"""

import nibabel as nib
import numpy as np
from pathlib import Path
from scipy.ndimage import zoom

class DirectWhiteMatterAnalysis:
    """Direct analysis of white matter overlaps with JHU-ICBM atlases"""
    
    @staticmethod
    def compute_dice(mask1, mask2):
        """Compute Dice coefficient between two binary masks"""
        intersection = np.sum(mask1 & mask2)
        if intersection == 0:
            return 0.0
        dice = 2.0 * intersection / (np.sum(mask1) + np.sum(mask2))
        return float(dice)
    
    @staticmethod
    def compute_overlap_all_regions(user_image_path, atlas_path, atlas_type='regions'):
        """
        Compute overlap with all regions/tracts in atlas
        
        Parameters:
        -----------
        user_image_path : str
            Path to user's white matter image/mask
        atlas_path : str
            Path to JHU-ICBM atlas
        atlas_type : str
            'regions' (48 labeled) or 'tracts' (20 probabilistic)
        
        Returns:
        --------
        dict : results with overlaps for each region/tract
        """
        
        print(f"\n🧬 Direct White Matter Analysis")
        print(f"   Type: {atlas_type}")
        print(f"   User image: {Path(user_image_path).name}")
        print(f"   Atlas: {Path(atlas_path).name}")
        
        try:
            # Load user image
            print(f"   Loading user image...")
            user_img = nib.load(user_image_path)
            user_data = user_img.get_fdata()
            user_shape = user_data.shape
            
            # Threshold user image (handle both binary masks and continuous images)
            user_binary = user_data > (np.max(user_data) * 0.1)  # 10% of max
            
            print(f"   ✅ User image: {user_shape}, {np.sum(user_binary)} voxels above threshold")
            
            # Load atlas
            print(f"   Loading atlas...")
            atlas_img = nib.load(atlas_path)
            atlas_data = atlas_img.get_fdata()
            atlas_shape = atlas_data.shape
            
            print(f"   ✅ Atlas: {atlas_shape}")
            
            # Check if dimensions match
            if user_shape[:3] != atlas_shape[:3]:
                print(f"   ⚠️  Shape mismatch: User {user_shape[:3]} vs Atlas {atlas_shape[:3]}")
                print(f"   🔄 Resampling atlas...")
                
                zoom_factors = [
                    user_shape[0] / atlas_shape[0],
                    user_shape[1] / atlas_shape[1],
                    user_shape[2] / atlas_shape[2],
                ]
                
                # For 4D atlases (multiple labels), resample each slice
                if len(atlas_shape) == 4:
                    zoom_factors.append(1.0)
                    atlas_resampled = np.zeros((*user_shape, atlas_shape[3]), dtype=atlas_data.dtype)
                    for i in range(atlas_shape[3]):
                        atlas_resampled[:,:,:,i] = zoom(
                            atlas_data[:,:,:,i],
                            zoom_factors[:3],
                            order=0
                        )
                    atlas_data = atlas_resampled
                else:
                    atlas_data = zoom(atlas_data, zoom_factors, order=0)
                
                print(f"   ✅ Atlas resampled to: {atlas_data.shape}")
            
            # Determine number of regions/tracts
            if len(atlas_shape) == 4:
                n_items = atlas_shape[3]
                print(f"   Found {n_items} labeled items (4D atlas)")
            else:
                unique_labels = np.unique(atlas_data)
                n_items = len(unique_labels) - 1  # Exclude background (0)
                print(f"   Found {n_items} labeled items (3D atlas with unique values)")
            
            overlaps = []
            
            # Compute overlaps
            print(f"   Computing overlaps for {n_items} regions/tracts...")
            
            if len(atlas_data.shape) == 4:
                # 4D atlas: iterate over 4th dimension
                for i in range(n_items):
                    atlas_label = atlas_data[:,:,:,i] > 0
                    overlap = DirectWhiteMatterAnalysis.compute_dice(user_binary, atlas_label)
                    overlaps.append(overlap)
                    if (i + 1) % 5 == 0 or i == n_items - 1:
                        print(f"      {i+1}/{n_items} completed...")
            else:
                # 3D atlas: iterate over unique values
                unique_labels = sorted(np.unique(atlas_data)[1:])  # Skip 0
                for label in unique_labels:
                    atlas_label = atlas_data == label
                    overlap = DirectWhiteMatterAnalysis.compute_dice(user_binary, atlas_label)
                    overlaps.append(overlap)
            
            print(f"   ✅ Completed: {len(overlaps)} overlaps computed")
            print(f"      Min overlap: {np.min(overlaps):.5f}")
            print(f"      Max overlap: {np.max(overlaps):.5f}")
            print(f"      Mean overlap: {np.mean(overlaps):.5f}")
            
            return {
                'status': 'success',
                'overlaps': overlaps,
                'n_regions': len(overlaps),
                'mean_overlap': float(np.mean(overlaps)),
                'std_overlap': float(np.std(overlaps)),
            }
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'error',
                'message': str(e),
                'overlaps': [],
            }
