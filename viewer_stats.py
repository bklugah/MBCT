#Klugah-Brown 2026

"""
viewer_stats.py
Statistical engine for the standalone Brain Viewer tab.

Provides SPM/FSL/MRIcroGL-style analyses on a loaded NIfTI volume:
  - intensity thresholding (positive / negative / two-tailed)
  - connected-component CLUSTER extent analysis (6/18/26 connectivity)
  - per-cluster size (voxels + mm^3), peak intensity, peak voxel + MNI
  - whole-image / in-mask intensity statistics
  - histogram data for the intensity distribution
  - per-cluster NIfTI export

Pure numpy/scipy/nibabel; no Qt, no version-specific APIs.
"""

from pathlib import Path
import numpy as np
import nibabel as nib
from scipy import ndimage




def voxel_to_mni(ijk, affine):
    v = affine @ np.array([ijk[0], ijk[1], ijk[2], 1.0], dtype=float)
    return (float(v[0]), float(v[1]), float(v[2]))


def voxel_volume_mm3(affine):
    try:
        return float(abs(np.linalg.det(affine[:3, :3])))
    except Exception:
        return 1.0




def threshold_mask(data, thr_pos=None, thr_neg=None):
    """
    Build a boolean mask of supra-threshold voxels.
      thr_pos: keep voxels >= thr_pos (positive tail)
      thr_neg: keep voxels <= thr_neg (negative tail)
    If both are None, returns all finite non-zero voxels.
    """
    finite = np.isfinite(data)
    if thr_pos is None and thr_neg is None:
        return finite & (data != 0)
    mask = np.zeros(data.shape, dtype=bool)
    if thr_pos is not None:
        mask |= finite & (data >= thr_pos)
    if thr_neg is not None:
        mask |= finite & (data <= thr_neg)
    return mask


_STRUCT = {
    6:  ndimage.generate_binary_structure(3, 1),
    18: ndimage.generate_binary_structure(3, 2),
    26: ndimage.generate_binary_structure(3, 3),
}



def cluster_analysis(data, affine, thr_pos=None, thr_neg=None,
                     connectivity=18, min_extent=0):
    """
    Label connected supra-threshold clusters and summarize each.

    Returns (clusters, label_volume) where:
      clusters = list of dicts sorted by descending voxel count:
        { 'id': int (1-based, matches label_volume),
          'n_voxels': int,
          'volume_mm3': float,
          'peak_value': float,          # max |value| signed
          'peak_voxel': (i,j,k),
          'peak_mni': (x,y,z),
          'com_voxel': (i,j,k),         # center of mass
          'com_mni': (x,y,z),
          'mean': float, 'max': float, 'min': float }
      label_volume = int array, 0 = background, k = cluster id (after extent filter)
    """
    mask = threshold_mask(data, thr_pos, thr_neg)
    struct = _STRUCT.get(connectivity, _STRUCT[18])
    labels, n = ndimage.label(mask, structure=struct)
    vox_vol = voxel_volume_mm3(affine)

    clusters = []
    out_labels = np.zeros_like(labels)
    next_id = 0
    if n > 0:
        sizes = ndimage.sum(np.ones_like(labels), labels, index=range(1, n + 1))
        for old_id in range(1, n + 1):
            n_vox = int(sizes[old_id - 1])
            if n_vox < min_extent:
                continue
            next_id += 1
            cmask = labels == old_id
            out_labels[cmask] = next_id

            vals = data[cmask]
            
            peak_local = int(np.argmax(np.abs(vals)))
            coords = np.argwhere(cmask)
            peak_ijk = tuple(int(c) for c in coords[peak_local])

            com = ndimage.center_of_mass(cmask)
            com_ijk = tuple(int(round(c)) for c in com)

            clusters.append({
                'id': next_id,
                'n_voxels': n_vox,
                'volume_mm3': float(n_vox * vox_vol),
                'peak_value': float(vals[peak_local]),
                'peak_voxel': peak_ijk,
                'peak_mni': voxel_to_mni(peak_ijk, affine),
                'com_voxel': com_ijk,
                'com_mni': voxel_to_mni(com_ijk, affine),
                'mean': float(vals.mean()),
                'max': float(vals.max()),
                'min': float(vals.min()),
            })

    clusters.sort(key=lambda c: c['n_voxels'], reverse=True)
    
    remap = {c['id']: i + 1 for i, c in enumerate(clusters)}
    if remap:
        relabeled = np.zeros_like(out_labels)
        for old, new in remap.items():
            relabeled[out_labels == old] = new
        out_labels = relabeled
        for c in clusters:
            c['id'] = remap[c['id']]
    return clusters, out_labels




def intensity_stats(data, mask=None):
    """
    Summary statistics over the whole image, or within mask if given.
    Zeros are treated as background and excluded from whole-image stats
    (matches typical statistical-map behaviour).
    """
    if mask is not None:
        vals = data[mask & np.isfinite(data)]
    else:
        vals = data[np.isfinite(data) & (data != 0)]
    if vals.size == 0:
        return {'n': 0, 'min': 0, 'max': 0, 'mean': 0, 'median': 0,
                'std': 0, 'sum': 0, 'n_pos': 0, 'n_neg': 0}
    return {
        'n': int(vals.size),
        'min': float(vals.min()),
        'max': float(vals.max()),
        'mean': float(vals.mean()),
        'median': float(np.median(vals)),
        'std': float(vals.std()),
        'sum': float(vals.sum()),
        'n_pos': int((vals > 0).sum()),
        'n_neg': int((vals < 0).sum()),
    }


def histogram(data, bins=60, exclude_zero=True):
    """Return (counts, bin_edges) for the intensity distribution."""
    vals = data[np.isfinite(data)]
    if exclude_zero:
        vals = vals[vals != 0]
    if vals.size == 0:
        return np.zeros(bins), np.linspace(0, 1, bins + 1)
    counts, edges = np.histogram(vals, bins=bins)
    return counts, edges


def value_at_voxel(data, ijk):
    """Intensity at a voxel, or None if out of bounds."""
    try:
        i, j, k = int(ijk[0]), int(ijk[1]), int(ijk[2])
        if 0 <= i < data.shape[0] and 0 <= j < data.shape[1] and 0 <= k < data.shape[2]:
            return float(data[i, j, k])
    except Exception:
        pass
    return None




def export_clusters(out_dir, clusters, label_volume, affine,
                    data=None, masked_values=True):
    """
    Save one NIfTI per cluster into out_dir.
    If masked_values and data given -> file holds the original intensities
    inside the cluster (else a binary mask).
    Returns list of saved paths.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for c in clusters:
        cid = c['id']
        cmask = label_volume == cid
        if not cmask.any():
            continue
        if masked_values and data is not None:
            vol = np.where(cmask, data, 0).astype(np.float32)
        else:
            vol = cmask.astype(np.uint8)
        pm = c['peak_mni']
        tag = f"x{pm[0]:+.0f}_y{pm[1]:+.0f}_z{pm[2]:+.0f}".replace("+", "p").replace("-", "m")
        fname = out_dir / f"cluster_{cid:02d}_{c['n_voxels']}vox_{tag}.nii.gz"
        nib.save(nib.Nifti1Image(vol, affine), str(fname))
        saved.append(str(fname))
    return saved
