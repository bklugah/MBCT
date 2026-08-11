"""
NIfTI Dimension Converter & Resampler
Converts NIfTI files to standard dimensions
Handles both .nii and .nii.gz files (with auto-detection)
"""

import numpy as np
import nibabel as nib
from pathlib import Path
from scipy.ndimage import map_coordinates
import gzip
import shutil
import tempfile
import os

class NiftiConverter:
    """Convert NIfTI files to standard dimensions."""
    
    @staticmethod
    def _ensure_readable_nifti(file_path):
        """
        Ensure file can be read as NIfTI.
        If .gz file is not actually gzipped, decompress or copy to temp location.
        
        Returns:
        --------
        str : Path to readable NIfTI file (may be temp file)
        str : Original path (for cleanup reference)
        """
        file_path = str(file_path)
        
        # Try to load directly first
        try:
            nib.load(file_path)
            return file_path, None  # No temp file needed
        except Exception as e:
            error_msg = str(e).lower()
            
            # If .gz file but not actually gzipped, handle it
            if file_path.endswith('.gz') and 'gzip' in error_msg:
                print(f"⚠️  File has .gz extension but is not actually gzipped")
                print(f"📝 Attempting to handle as plain .nii file...")
                
                # Create temp directory
                temp_dir = tempfile.gettempdir()
                
                # Try 1: File might already be uncompressed, just misnamed
                # Try to load without .gz
                try:
                    base_path = file_path.replace('.gz', '')
                    if os.path.exists(base_path):
                        nib.load(base_path)
                        return base_path, None
                except:
                    pass
                
                # Try 2: Copy file to temp without .gz extension
                try:
                    temp_file = os.path.join(temp_dir, Path(file_path).stem + '_temp.nii')
                    shutil.copy(file_path, temp_file)
                    nib.load(temp_file)
                    print(f"✅ Successfully loaded as plain NIfTI file")
                    return temp_file, temp_file  # Return temp path for cleanup
                except Exception as copy_error:
                    print(f"❌ Failed to handle file: {copy_error}")
                    raise
        
        raise Exception(f"Cannot read NIfTI file: {file_path}")
    
    @staticmethod
    def get_dimensions(nifti_path):
        """Get dimensions of a NIfTI file."""
        try:
            readable_path, temp_file = NiftiConverter._ensure_readable_nifti(nifti_path)
            img = nib.load(readable_path)
            
            # Cleanup temp if created
            if temp_file:
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            return img.shape
        except Exception as e:
            return None
    
    @staticmethod
    def resample_to_target(input_path, output_path, target_shape, interpolation='linear'):
        """
        Resample NIfTI to target dimensions using proper MNI coordinate transformation.
        
        Parameters:
        -----------
        input_path : str
            Path to input NIfTI file
        output_path : str
            Path to save resampled NIfTI
        target_shape : tuple
            Target dimensions (x, y, z)
        interpolation : str
            'linear' or 'nearest'
        
        Returns:
        --------
        bool : True if successful, False otherwise
        str : Status message
        
        CRITICAL: Uses proper affine-based coordinate transformation to preserve MNI accuracy
        """
        temp_file = None
        try:
            from scipy.ndimage import map_coordinates
            from scipy.interpolate import RegularGridInterpolator
            
            # Ensure file is readable
            readable_path, temp_file = NiftiConverter._ensure_readable_nifti(input_path)
            
            # Load input
            img = nib.load(readable_path)
            data = img.get_fdata()
            affine = img.affine
            
            # Get current shape
            current_shape = data.shape
            target_x, target_y, target_z = target_shape
            
            print(f"📊 Current shape: {current_shape}")
            print(f"🎯 Target shape: {target_shape}")
            
            # Calculate voxel size ratios
            scale_x = current_shape[0] / target_x
            scale_y = current_shape[1] / target_y
            scale_z = current_shape[2] / target_z
            
            print(f"📐 Voxel scale factors: x={scale_x:.4f}, y={scale_y:.4f}, z={scale_z:.4f}")
            
            # PROPER AFFINE TRANSFORMATION
            # Create affine matrix for target space
            # Multiply diagonal by scale factors to account for voxel size change
            new_affine = affine.copy()
            new_affine[0, 0] *= scale_x
            new_affine[1, 1] *= scale_y
            new_affine[2, 2] *= scale_z
            
            # Create inverse affine for coordinate mapping
            inv_affine = np.linalg.inv(affine)
            
            # Create output array
            output_data = np.zeros(target_shape, dtype=data.dtype)
            
            print(f"🔄 Resampling with MNI coordinate preservation...")
            total_voxels = target_x * target_y * target_z
            
            # Resample using proper world-to-voxel coordinate transformation
            for idx, (i, j, k) in enumerate(np.ndindex(target_shape)):
                # Create world coordinates in target space
                world_coords = new_affine @ np.array([i, j, k, 1.0])[:, np.newaxis]
                
                # Convert to source voxel coordinates using inverse affine
                src_coords = inv_affine @ world_coords
                src_i, src_j, src_k = src_coords[0, 0], src_coords[1, 0], src_coords[2, 0]
                
                # Check if in bounds
                if (0 <= src_i < current_shape[0] and 
                    0 <= src_j < current_shape[1] and 
                    0 <= src_k < current_shape[2]):
                    
                    # Interpolate value
                    coords = np.array([[src_i], [src_j], [src_k]])
                    try:
                        if interpolation == 'linear':
                            value = map_coordinates(data, coords, order=1, mode='constant', cval=0.0)
                        else:
                            value = map_coordinates(data, coords, order=0, mode='constant', cval=0.0)
                        output_data[i, j, k] = value[0]
                    except:
                        output_data[i, j, k] = 0
                else:
                    output_data[i, j, k] = 0
                
                # Progress
                if (idx + 1) % max(1, total_voxels // 10) == 0:
                    progress = ((idx + 1) / total_voxels) * 100
                    print(f"  {progress:.0f}% complete...")
            
            # Save output - ensure directory exists
            print(f"💾 Saving resampled file with proper MNI coordinates...")
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create output NIfTI with corrected affine
            output_img = nib.Nifti1Image(output_data, new_affine)
            nib.save(output_img, output_path)
            
            print(f"✅ Resampled {current_shape} → {target_shape}")
            print(f"✅ MNI coordinates preserved with affine transformation")
            return True, f"✅ Resampled {current_shape} → {target_shape} (MNI coordinates accurate)"
            
        except Exception as e:
            print(f"❌ Error during resampling: {str(e)}")
            return False, f"❌ Resampling error: {str(e)}"
        finally:
            # Cleanup temp file if created
            if temp_file:
                try:
                    os.remove(temp_file)
                    print(f"🗑️  Cleaned up temporary file")
                except:
                    pass
    
    @staticmethod
    def check_dimension_match(file_path, expected_shape):
        """
        Check if file matches expected dimensions.
        
        Returns:
        --------
        bool : True if matches, False otherwise
        tuple : Actual shape
        str : Message
        """
        try:
            readable_path, temp_file = NiftiConverter._ensure_readable_nifti(file_path)
            img = nib.load(readable_path)
            actual_shape = img.shape[:3]
            
            # Cleanup temp if created
            if temp_file:
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            if actual_shape == expected_shape:
                return True, actual_shape, "✅ Dimensions match"
            else:
                return False, actual_shape, f"⚠️  Dimension mismatch: expected {expected_shape}, got {actual_shape}"
        except Exception as e:
            return False, None, f"❌ Error reading file: {str(e)}"
    
    @staticmethod
    def auto_convert_if_needed(input_path, target_shape, output_dir=None):
        """
        Auto-convert file if dimensions don't match.
        
        Returns:
        --------
        str : Path to file (original or converted)
        str : Message
        bool : Whether conversion was performed
        """
        matches, actual_shape, msg = NiftiConverter.check_dimension_match(input_path, target_shape)
        
        if matches:
            return input_path, "✅ File dimensions match target", False
        
        # Need conversion
        if output_dir is None:
            output_dir = Path(input_path).parent
        else:
            output_dir = Path(output_dir)
        
        output_path = output_dir / f"{Path(input_path).stem}_converted_{target_shape[0]}x{target_shape[1]}x{target_shape[2]}.nii.gz"
        
        success, msg = NiftiConverter.resample_to_target(
            input_path, 
            str(output_path), 
            target_shape,
            interpolation='linear'
        )
        
        if success:
            return str(output_path), msg, True
        else:
            return None, f"❌ Conversion failed: {msg}", False
