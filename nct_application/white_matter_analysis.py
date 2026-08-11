"""
White Matter Atlas Analysis
Analyzes white matter tracts using white matter atlases (ICBM_Wmpm, JHU-ICBM)
"""

import numpy as np
import nibabel as nib
from pathlib import Path
from scipy.ndimage import label as ndimage_label

class WhiteMatterAnalysis:
    """White matter analysis using white matter atlases."""
    
    @staticmethod
    def compute_white_matter_overlap(wm_image_path, atlas_path, metric='dice'):
        """
        Compute overlap between white matter image and atlas.
        Automatically resamples atlas to match input dimensions if needed.
        
        Parameters:
        -----------
        wm_image_path : str
            Path to white matter image (FA, MD, etc.)
        atlas_path : str
            Path to white matter atlas
        metric : str
            'dice' or 'jaccard'
        
        Returns:
        --------
        dict : Results with tract names and overlap values
        """
        try:
            # Load white matter image
            wm_img = nib.load(wm_image_path)
            wm_data = wm_img.get_fdata()
            wm_affine = wm_img.affine
            
            # Load atlas
            atlas_img = nib.load(atlas_path)
            atlas_data = atlas_img.get_fdata()
            atlas_affine = atlas_img.affine
            
            # Handle shape mismatch by resampling atlas if needed
            if wm_data.shape != atlas_data.shape[:3]:
                print(f"    ⚠️ Shape mismatch: Input {wm_data.shape} vs Atlas {atlas_data.shape[:3]}")
                print(f"    🔄 Resampling atlas to match input dimensions...")
                
                # Resample atlas to input dimensions
                from scipy.ndimage import zoom
                
                # Calculate zoom factors
                if len(atlas_data.shape) == 4:  # Has label dimension
                    # For 4D data (with labels), resample each label separately
                    zoom_factors = [
                        wm_data.shape[0] / atlas_data.shape[0],
                        wm_data.shape[1] / atlas_data.shape[1],
                        wm_data.shape[2] / atlas_data.shape[2],
                        1.0  # Don't zoom the label dimension
                    ]
                    atlas_resampled = np.zeros((*wm_data.shape, atlas_data.shape[3]), dtype=atlas_data.dtype)
                    for label_idx in range(atlas_data.shape[3]):
                        atlas_resampled[:,:,:,label_idx] = zoom(
                            atlas_data[:,:,:,label_idx],
                            zoom_factors[:3],
                            order=0  # Nearest neighbor for labels
                        )
                    atlas_data = atlas_resampled
                else:
                    # For 3D data, resample with nearest neighbor
                    zoom_factors = [
                        wm_data.shape[0] / atlas_data.shape[0],
                        wm_data.shape[1] / atlas_data.shape[1],
                        wm_data.shape[2] / atlas_data.shape[2]
                    ]
                    atlas_data = zoom(atlas_data, zoom_factors, order=0)
                
                print(f"    ✅ Atlas resampled to {atlas_data.shape}")
            
            # Get unique tract labels
            if len(atlas_data.shape) == 4:
                # 4D atlas: iterate over last dimension
                tract_labels = np.arange(1, atlas_data.shape[3] + 1)
            else:
                # 3D atlas: unique values in the data
                tract_labels = np.unique(atlas_data)[1:]  # Skip 0 (background)
            
            results = {
                'tracts': [],
                'overlaps': [],
                'metric': metric,
            }
            
            # Threshold white matter image
            wm_binary = wm_data > np.mean(wm_data)
            
            # Compute overlap for each tract
            for tract_id in sorted(tract_labels):
                if len(atlas_data.shape) == 4:
                    tract_mask = (atlas_data[:,:,:,int(tract_id)-1] > 0)
                else:
                    tract_mask = (atlas_data == tract_id)
                
                if metric == 'dice':
                    overlap = WhiteMatterAnalysis._dice_coefficient(wm_binary, tract_mask)
                elif metric == 'jaccard':
                    overlap = WhiteMatterAnalysis._jaccard_index(wm_binary, tract_mask)
                else:
                    overlap = WhiteMatterAnalysis._dice_coefficient(wm_binary, tract_mask)
                
                # Get tract name (placeholder)
                tract_name = f"Tract_{int(tract_id)}"
                
                results['tracts'].append(tract_name)
                results['overlaps'].append(float(overlap))
            
            return results
            
        except Exception as e:
            import traceback
            print(f"    💥 Exception in white matter analysis: {e}")
            traceback.print_exc()
            return {'error': str(e)}
    
    @staticmethod
    def _dice_coefficient(mask1, mask2):
        """Compute Dice coefficient between two masks."""
        intersection = np.logical_and(mask1, mask2).sum()
        union = mask1.sum() + mask2.sum()
        
        if union == 0:
            return 0.0
        
        dice = (2.0 * intersection) / union
        return np.clip(dice, 0.0, 1.0)
    
    @staticmethod
    def _jaccard_index(mask1, mask2):
        """Compute Jaccard index between two masks."""
        intersection = np.logical_and(mask1, mask2).sum()
        union = np.logical_or(mask1, mask2).sum()
        
        if union == 0:
            return 0.0
        
        jaccard = intersection / union
        return np.clip(jaccard, 0.0, 1.0)
    
    @staticmethod
    def load_atlas_labels(atlas_code):
        """
        Load tract labels from white matter atlas.
        
        Parameters:
        -----------
        atlas_code : str
            'ICBM_Wmpm' or 'JHU-ICBM'
        
        Returns:
        --------
        dict : {tract_id: tract_name}
        """
        from nct_application.white_matter_config import WhiteMatterConfig
        
        atlas_dir = WhiteMatterConfig.get_atlas_dir()
        if not atlas_dir:
            return {}
        
        labels = {}
        
        if atlas_code == 'ICBM_Wmpm':
            # Load ICBM labels from lookup table
            label_file = Path(atlas_dir) / 'ICBM_Wmpm' / 'MniLabelLookupTable.txt'
            if label_file.exists():
                try:
                    with open(label_file) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                parts = line.split()
                                if len(parts) >= 2:
                                    try:
                                        tract_id = int(parts[0])
                                        tract_name = ' '.join(parts[1:])
                                        labels[tract_id] = tract_name
                                    except:
                                        pass
                except:
                    pass
        
        elif atlas_code == 'JHU-ICBM':
            # Load JHU labels from XML or mat file
            label_file = Path(atlas_dir) / 'JHU-ICBM' / 'JHU-tracts.xml'
            if label_file.exists():
                try:
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(label_file)
                    root = tree.getroot()
                    for elem in root.findall('.//label'):
                        tract_id = int(elem.get('id', 0))
                        tract_name = elem.text or f"Tract_{tract_id}"
                        labels[tract_id] = tract_name
                except:
                    pass
        
        return labels
    
    @staticmethod
    def compute_centroid(tract_mask, affine):
        """
        Compute centroid of a tract in MNI coordinates.
        
        Parameters:
        -----------
        tract_mask : ndarray
            Binary mask of tract
        affine : ndarray
            Affine transformation matrix
        
        Returns:
        --------
        tuple : (x, y, z) in MNI space
        """
        indices = np.argwhere(tract_mask)
        
        if len(indices) == 0:
            return (0, 0, 0)
        
        # Compute centroid in voxel space
        centroid_voxel = indices.mean(axis=0)
        
        # Convert to MNI space
        centroid_mni = affine @ np.append(centroid_voxel, 1)
        
        return tuple(centroid_mni[:3])
