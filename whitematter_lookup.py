"""
whitematter_lookup.py — JHU-ICBM white-matter anatomical lookup.

Mirrors anatomy_lookup.py (gray-matter Harvard-Oxford) but for white matter:

  * wm_label_at_mni(x, y, z)        -> {'region': str, 'tract': str}
        #1  ICBM-DTI-81 region (e.g. "Body of corpus callosum") + maxprob tract
  * wm_tract_probs_at_mni(x, y, z)  -> [(tract_name, prob_percent), ...]
        #3  ranked tracts from the probabilistic 4D atlas
  * tract_atlas_img()               -> nibabel image of the maxprob tract atlas
        #2  for a toggleable viewer overlay
  * wm_status()                     -> short human-readable load status

Files are discovered by PATTERN (not exact name) because real-world copies of
the JHU atlas often have mangled extensions (e.g. "..._nii.gz" instead of
"....nii.gz"), and are loaded in a way that tolerates those names.
"""

import io
import os
import glob
import gzip
import xml.etree.ElementTree as ET
import numpy as np

_CACHE = None
_LOAD_FAILED = False
_STATUS = "not loaded"


# --------------------------------------------------------------------------
# file discovery
# --------------------------------------------------------------------------
def _looks_like_nifti(p):
    low = p.lower()
    return (low.endswith('.nii') or low.endswith('.nii.gz')
            or low.endswith('_nii') or low.endswith('_nii.gz'))


def _find(d, *substr_sets):
    """Return the first file in d whose lowercase name contains ALL substrings
    of any one set, and looks like a NIfTI (or matches exactly for .xml)."""
    try:
        entries = os.listdir(d)
    except Exception:
        return None
    for subs in substr_sets:
        for name in sorted(entries):
            low = name.lower()
            if all(s in low for s in subs):
                full = os.path.join(d, name)
                if low.endswith('.xml') or _looks_like_nifti(name):
                    return full
    return None


def _atlas_dir():
    """Locate the JHU atlas folder across source and packaged runs."""
    cands = []
    try:
        from paths import resource_dir, user_data_dir
        for base in (resource_dir(), user_data_dir()):
            b = str(base)
            cands += [
                os.path.join(b, "white_matter_atlases", "whitematteratlasses", "JHU-ICBM"),
                os.path.join(b, "white_matter_atlases", "JHU-ICBM"),
                os.path.join(b, "white_matter_atlases"),
            ]
    except Exception:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    cands += [
        os.path.join(here, "white_matter_atlases", "whitematteratlasses", "JHU-ICBM"),
        os.path.join(here, "white_matter_atlases", "JHU-ICBM"),
        os.path.join(here, "white_matter_atlases"),
    ]
    for c in cands:
        if os.path.isdir(c) and _find(c, ('jhu', 'labels', '1mm'), ('jhu', 'tracts')):
            return c
    return None


# --------------------------------------------------------------------------
# robust NIfTI loading (handles "_nii.gz" style names nibabel can't infer)
# --------------------------------------------------------------------------
def _load_nifti(path):
    import nibabel as nib
    try:
        return nib.load(path)
    except Exception:
        pass
    # Fall back: read bytes ourselves, gunzip if needed, build from file map.
    with open(path, 'rb') as fh:
        raw = fh.read()
    if raw[:2] == b'\x1f\x8b':                    # gzip magic
        raw = gzip.decompress(raw)
    fh_obj = nib.FileHolder(fileobj=io.BytesIO(raw))
    return nib.Nifti1Image.from_file_map({'header': fh_obj, 'image': fh_obj})


# --------------------------------------------------------------------------
# XML label dictionaries
# --------------------------------------------------------------------------
def _parse_xml_names(xml_path):
    """FSL atlas XML -> list addressable by atlas voxel value (0 = Background)."""
    if not xml_path or not os.path.exists(xml_path):
        return None
    names = {}
    try:
        for lab in ET.parse(xml_path).getroot().iter('label'):
            idx = lab.get('index')
            if idx is not None:
                names[int(idx)] = (lab.text or '').strip()
    except Exception as e:
        print(f"[wm] could not parse {os.path.basename(xml_path)}: {e}")
        return None
    if not names:
        return None
    hi = max(names)
    # FSL XML index is 0-based over labels; maxprob voxel value v -> XML index v-1
    return ['Background'] + [names.get(i, f'label_{i}') for i in range(hi + 1)]


# --------------------------------------------------------------------------
# loading / caching
# --------------------------------------------------------------------------
def _load():
    global _CACHE, _LOAD_FAILED, _STATUS
    if _CACHE is not None or _LOAD_FAILED:
        return _CACHE
    d = _atlas_dir()
    if d is None:
        _STATUS = "atlas folder not found"
        print("[wm] JHU atlas folder not found; white-matter labels disabled.")
        _LOAD_FAILED = True
        return None
    try:
        lab_p = _find(d, ('labels', '1mm'), ('whitematter', 'labels'))
        tmax_p = _find(d, ('tracts', 'maxprob', 'thr25'), ('tracts', 'maxprob'))
        lab_xml = _find(d, ('labels', '.xml'))
        trk_xml = _find(d, ('tracts', '.xml'))
        print(f"[wm] atlas dir: {d}")
        print(f"[wm]   labels : {os.path.basename(lab_p) if lab_p else 'NOT FOUND'}")
        print(f"[wm]   tracts : {os.path.basename(tmax_p) if tmax_p else 'NOT FOUND'}")

        cache = {'_dir': d, 'prob_data': None, 'prob_inv': None,
                 'lab_data': None, 'lab_inv': None, 'lab_names': None,
                 'tmax_data': None, 'tmax_inv': None, 'tmax_img': None,
                 'tract_names': None}

        if lab_p:
            img = _load_nifti(lab_p)
            cache['lab_data'] = np.asarray(img.dataobj)
            cache['lab_inv'] = np.linalg.inv(img.affine)
            cache['lab_names'] = _parse_xml_names(lab_xml)
        if tmax_p:
            img = _load_nifti(tmax_p)
            cache['tmax_img'] = img
            cache['tmax_data'] = np.asarray(img.dataobj)
            cache['tmax_inv'] = np.linalg.inv(img.affine)
            cache['tract_names'] = _parse_xml_names(trk_xml)

        if cache['lab_data'] is None and cache['tmax_data'] is None:
            raise FileNotFoundError("no JHU label or tract volume found")

        _STATUS = "loaded"
        _CACHE = cache
    except Exception as e:
        _STATUS = f"load error: {e}"
        print(f"[wm] JHU white-matter atlas unavailable ({e}); WM labels disabled.")
        _LOAD_FAILED = True
        _CACHE = None
    return _CACHE


def _ensure_prob():
    """Load the probabilistic 4D tract atlas on first use (#3)."""
    c = _load()
    if c is None:
        return None
    if c['prob_data'] is not None:
        return c
    try:
        p = _find(c['_dir'], ('tracts', 'prob', '1mm'))
        # avoid picking the maxprob file
        if p and 'maxprob' in os.path.basename(p).lower():
            p = None
            for nm in sorted(os.listdir(c['_dir'])):
                low = nm.lower()
                if 'tracts' in low and 'prob' in low and 'maxprob' not in low \
                        and _looks_like_nifti(nm):
                    p = os.path.join(c['_dir'], nm); break
        if not p:
            raise FileNotFoundError("probabilistic tract atlas not found")
        print(f"[wm]   probs  : {os.path.basename(p)}")
        img = _load_nifti(p)
        c['prob_data'] = np.asarray(img.dataobj)      # 4D (x,y,z,n_tracts)
        c['prob_inv'] = np.linalg.inv(img.affine)
    except Exception as e:
        print(f"[wm] probabilistic tract atlas unavailable ({e}).")
        c['prob_data'] = False
    return c


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------
def _value_at(data, inv, x, y, z):
    vox = inv @ np.array([x, y, z, 1.0])
    i, j, k = (int(round(v)) for v in vox[:3])
    if not (0 <= i < data.shape[0] and 0 <= j < data.shape[1] and 0 <= k < data.shape[2]):
        return None
    return int(data[i, j, k])


def _name_for(names, v):
    if not names or not v or v <= 0 or v >= len(names):
        return None
    nm = names[v]
    if nm in ('Background', 'Unclassified', ''):
        return None
    return nm


def wm_label_at_mni(x, y, z):
    """#1 — ICBM-DTI-81 white-matter region + maxprob tract at a coordinate."""
    c = _load()
    if c is None:
        return {'region': '—', 'tract': '—'}
    region = tract = '—'
    if c['lab_data'] is not None:
        v = _value_at(c['lab_data'], c['lab_inv'], x, y, z)
        region = _name_for(c['lab_names'], v) or '—'
    if c['tmax_data'] is not None:
        v = _value_at(c['tmax_data'], c['tmax_inv'], x, y, z)
        tract = _name_for(c['tract_names'], v) or '—'
    return {'region': region, 'tract': tract}


def wm_tract_probs_at_mni(x, y, z, top=3, min_pct=5.0):
    """#3 — ranked (tract_name, probability%) from the probabilistic atlas."""
    c = _ensure_prob()
    if c is None or not isinstance(c.get('prob_data'), np.ndarray):
        return []
    data, inv, names = c['prob_data'], c['prob_inv'], c['tract_names']
    vox = inv @ np.array([x, y, z, 1.0])
    i, j, k = (int(round(v)) for v in vox[:3])
    if not (0 <= i < data.shape[0] and 0 <= j < data.shape[1] and 0 <= k < data.shape[2]):
        return []
    probs = np.asarray(data[i, j, k], dtype=float)
    out = []
    for t_idx, p in enumerate(probs):
        if p <= 0:
            continue
        nm = (names[t_idx + 1] if (names and t_idx + 1 < len(names))
              else f'tract_{t_idx}')
        pct = float(p) if p > 1.0 else float(p) * 100.0
        if pct >= min_pct:
            out.append((nm, round(pct, 1)))
    out.sort(key=lambda t: t[1], reverse=True)
    return out[:top]


def tract_atlas_img():
    """#2 — maxprob tract atlas image, for a viewer overlay."""
    c = _load()
    return c['tmax_img'] if c else None


def tract_names():
    c = _load()
    return c['tract_names'] if c else None


def wm_status():
    _load()
    return _STATUS
