"""
results_extras.py
Shared helpers for the Results tab:
  - per-network voxel masks (works for 'labels', 'metric', '4d' atlas modes)
  - voxel statistics (count per network, peak location)
  - per-network NIfTI export
  - session save / load (review results without recomputing)

All functions are deliberately defensive: they accept the ResultsTab-style
data model (atlas volume + affine + mode + label map) and never assume a
particular nibabel/nilearn version.
"""

from pathlib import Path
import json
import numpy as np
import nibabel as nib


# ---------------------------------------------------------------------------
# Per-network voxel masks
# ---------------------------------------------------------------------------

def network_mask(net_idx, atlas_vol, atlas_mode, label_map, threshold=0.0):
    """
    Return a boolean 3D mask (in atlas/analysis space) for one network.

    atlas_mode:
      'labels' -> integer parcellation; a network = union of its label values
      'metric' -> single 3D metric map; network 0 = voxels above threshold
      '4d'     -> 4D probability stack; network i = volume i above threshold
    Returns None if a mask cannot be built.
    """
    if atlas_vol is None:
        return None
    try:
        if atlas_mode == '4d':
            if net_idx >= atlas_vol.shape[3]:
                return None
            vol = atlas_vol[..., net_idx]
            return vol > threshold
        if atlas_mode == 'metric':
            if net_idx != 0:
                return None
            return atlas_vol > threshold
        # 'labels'
        labs = [lab for lab, idx in (label_map or {}).items() if idx == net_idx]
        if not labs:
            return None
        mask = np.isin(atlas_vol, labs)
        return mask if mask.any() else None
    except Exception:
        return None


def voxel_to_mni(i, j, k, affine):
    v = affine @ np.array([i, j, k, 1.0], dtype=float)
    return float(v[0]), float(v[1]), float(v[2])


# ---------------------------------------------------------------------------
# Voxel statistics (feature 2)
# ---------------------------------------------------------------------------

def network_voxel_stats(net_idx, atlas_vol, atlas_aff, atlas_mode, label_map,
                        threshold=0.0):
    """
    For one network, return a dict:
      { 'n_voxels': int,
        'volume_mm3': float,
        'peak_voxel': (i,j,k) or None,
        'peak_mni': (x,y,z) or None }
    Peak = voxel with the highest value within the mask (for 'metric'/'4d');
    for 'labels' (no intensity), peak = centroid-nearest voxel of the mask.
    """
    mask = network_mask(net_idx, atlas_vol, atlas_mode, label_map, threshold)
    if mask is None or not mask.any():
        return {'n_voxels': 0, 'volume_mm3': 0.0,
                'peak_voxel': None, 'peak_mni': None}

    n_vox = int(mask.sum())

    # voxel volume from affine (|det| of the 3x3 spatial part)
    try:
        vox_vol = abs(np.linalg.det(atlas_aff[:3, :3]))
    except Exception:
        vox_vol = 1.0

    # peak location
    peak_ijk = None
    if atlas_mode in ('metric', '4d'):
        if atlas_mode == '4d':
            vol = atlas_vol[..., net_idx]
        else:
            vol = atlas_vol
        vals = np.where(mask, vol, -np.inf)
        idx_flat = int(np.argmax(vals))
        peak_ijk = np.unravel_index(idx_flat, vals.shape)
    else:
        # labels: use the voxel closest to the mask centroid
        coords = np.argwhere(mask)
        centroid = coords.mean(axis=0)
        d = np.linalg.norm(coords - centroid, axis=1)
        peak_ijk = tuple(int(c) for c in coords[int(np.argmin(d))])

    peak_ijk = tuple(int(c) for c in peak_ijk)
    peak_mni = voxel_to_mni(*peak_ijk, atlas_aff)

    return {'n_voxels': n_vox,
            'volume_mm3': float(n_vox * vox_vol),
            'peak_voxel': peak_ijk,
            'peak_mni': peak_mni}


def all_network_voxel_stats(network_names, atlas_vol, atlas_aff, atlas_mode,
                            label_map, threshold=0.0):
    """List of (name, stats-dict) for every network, plus the index of the
    network with the most voxels."""
    rows = []
    best_idx, best_n = None, -1
    for i, name in enumerate(network_names):
        st = network_voxel_stats(i, atlas_vol, atlas_aff, atlas_mode,
                                 label_map, threshold)
        rows.append((name, st))
        if st['n_voxels'] > best_n:
            best_n, best_idx = st['n_voxels'], i
    return rows, best_idx


# ---------------------------------------------------------------------------
# Per-network NIfTI export (feature 3)
# ---------------------------------------------------------------------------

def export_network_niftis(out_dir, network_names, p_values,
                          atlas_vol, atlas_aff, atlas_mode, label_map,
                          significant_only=True, alpha=0.05, threshold=0.0):
    """
    Save one .nii.gz per (significant) network into out_dir.
    Each file is a binary mask of that network in analysis space.
    Returns (saved_paths, skipped) where skipped is a list of (name, reason).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved, skipped = [], []

    for i, name in enumerate(network_names):
        pv = float(p_values[i]) if (p_values is not None and i < len(p_values)) else 1.0
        if significant_only and not (pv < alpha):
            skipped.append((name, f"not significant (p={pv:.4f})"))
            continue
        mask = network_mask(i, atlas_vol, atlas_mode, label_map, threshold)
        if mask is None or not mask.any():
            skipped.append((name, "no voxels"))
            continue
        safe = _safe_filename(name)
        fname = out_dir / f"network_{i:02d}_{safe}.nii.gz"
        img = nib.Nifti1Image(mask.astype(np.uint8), atlas_aff)
        nib.save(img, str(fname))
        saved.append(str(fname))
    return saved, skipped


def _safe_filename(name):
    keep = "-_.() "
    s = "".join(c if (c.isalnum() or c in keep) else "_" for c in str(name))
    return s.strip().replace(" ", "_") or "network"


# ---------------------------------------------------------------------------
# Session save / load (feature 4)
# ---------------------------------------------------------------------------

SESSION_VERSION = 1


def _to_jsonable(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, dict):
        return {str(k): _to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(v) for v in x]
    return x


def save_session(path, *, results, space, atlas_code,
                 network_names, overlaps, p_values, centroids,
                 atlas_mode=None, label_map=None, extra=None):
    """
    Write a .nctresult JSON file capturing everything needed to redisplay
    results without recomputing. Heavy volumes are NOT stored; instead we
    store the atlas identity so the volume can be re-resolved on load.
    """
    payload = {
        'version': SESSION_VERSION,
        'space': space,
        'atlas_code': atlas_code,
        'network_names': list(network_names),
        'overlaps': _to_jsonable(list(overlaps)),
        'p_values': _to_jsonable(list(p_values)),
        'centroids': _to_jsonable([
            (list(c) if c is not None else None) for c in centroids
        ]),
        'atlas_mode': atlas_mode,
        'label_map': _to_jsonable(label_map) if label_map else None,
        'results': _to_jsonable(results) if results else None,
        'extra': _to_jsonable(extra) if extra else None,
    }
    path = Path(path)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, indent=2)
    return str(path)


def load_session(path):
    """Read a .nctresult JSON file -> dict. Restores label_map keys to int
    where possible (JSON keys are strings)."""
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    lm = data.get('label_map')
    if isinstance(lm, dict):
        fixed = {}
        for k, v in lm.items():
            try:
                fixed[int(float(k))] = int(v)
            except Exception:
                fixed[k] = v
        data['label_map'] = fixed
    return data
