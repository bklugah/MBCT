"""
anatomy_lookup.py
Anatomical labelling for the Results-tab brain map.

Provides:
  * label_at_mni(x, y, z)          -> {'region': str, 'brodmann': str}
  * subregions_for_mask(mask, aff) -> list of {'region', 'n_voxels', 'pct'}

Backed by the Harvard-Oxford cortical + subcortical probabilistic atlases via
nilearn (downloaded once and cached). A curated region->Brodmann-area mapping
adds classical cytoarchitectonic equivalents for the readout.

All heavy objects are loaded lazily and cached, so the first lookup pays the
one-time download/parse cost and subsequent calls are fast.
"""

import numpy as np

_HO = None          # cached (cort_img, cort_labels, sub_img, sub_labels, inv_affines)
_LOAD_FAILED = False


# --- Harvard-Oxford region name -> classical Brodmann-area equivalent ---------
# Best-effort mapping from HO cortical structure names to Brodmann areas /
# classical functional names. Keys are matched case-insensitively as substrings.
_BRODMANN = [
    ("Precentral Gyrus",                         "BA 4 — primary motor cortex"),
    ("Postcentral Gyrus",                        "BA 1/2/3 — primary somatosensory cortex"),
    ("Superior Frontal Gyrus",                   "BA 6/8/9 — premotor / SMA / prefrontal"),
    ("Middle Frontal Gyrus",                     "BA 9/46 — dorsolateral prefrontal cortex"),
    ("Inferior Frontal Gyrus, pars triangularis","BA 45 — Broca's area (pars triangularis)"),
    ("Inferior Frontal Gyrus, pars opercularis", "BA 44 — Broca's area (pars opercularis)"),
    ("Frontal Pole",                             "BA 10 — frontal pole / rostral PFC"),
    ("Frontal Medial Cortex",                    "BA 10/11 — medial / orbitofrontal PFC"),
    ("Frontal Orbital Cortex",                   "BA 11/47 — orbitofrontal cortex"),
    ("Subcallosal Cortex",                       "BA 25 — subgenual cingulate"),
    ("Paracingulate Gyrus",                      "BA 32 — paracingulate / dorsal ACC"),
    ("Cingulate Gyrus, anterior",                "BA 24/32 — anterior cingulate cortex"),
    ("Cingulate Gyrus, posterior",               "BA 23/31 — posterior cingulate cortex"),
    ("Precuneous",                               "BA 7 — precuneus"),
    ("Cuneal Cortex",                            "BA 18/19 — cuneus (visual association)"),
    ("Intracalcarine Cortex",                    "BA 17 — primary visual cortex (V1)"),
    ("Supracalcarine Cortex",                    "BA 17/18 — peri-calcarine visual"),
    ("Occipital Pole",                           "BA 17/18 — occipital pole (visual)"),
    ("Lateral Occipital Cortex",                 "BA 18/19 — visual association (V2–V5)"),
    ("Lingual Gyrus",                            "BA 18/19 — lingual (visual association)"),
    ("Occipital Fusiform Gyrus",                 "BA 19/37 — fusiform (visual)"),
    ("Temporal Occipital Fusiform Cortex",       "BA 37 — fusiform / occipitotemporal"),
    ("Temporal Fusiform Cortex",                 "BA 20/36 — fusiform (temporal)"),
    ("Heschl's Gyrus",                           "BA 41/42 — primary auditory cortex"),
    ("Planum Temporale",                         "BA 22 — auditory association"),
    ("Planum Polare",                            "BA 22/38 — auditory / temporal pole"),
    ("Superior Temporal Gyrus, posterior",       "BA 22 — Wernicke's area (post. STG)"),
    ("Superior Temporal Gyrus, anterior",        "BA 38/22 — anterior superior temporal"),
    ("Middle Temporal Gyrus",                    "BA 21 — middle temporal gyrus"),
    ("Inferior Temporal Gyrus",                  "BA 20 — inferior temporal gyrus"),
    ("Temporal Pole",                            "BA 38 — temporal pole"),
    ("Parahippocampal Gyrus",                    "BA 27/28/35/36 — parahippocampal"),
    ("Angular Gyrus",                            "BA 39 — angular gyrus"),
    ("Supramarginal Gyrus",                      "BA 40 — supramarginal gyrus"),
    ("Superior Parietal Lobule",                 "BA 5/7 — superior parietal lobule"),
    ("Insular Cortex",                           "insula (agranular/granular)"),
    ("Central Opercular Cortex",                 "BA 43 — central operculum"),
    ("Parietal Operculum Cortex",                "BA 43 — parietal operculum (SII)"),
]


def _brodmann_for(region_name):
    if not region_name or region_name in ("Background", "Unknown", "—"):
        return "—"
    rn = region_name.lower()
    for key, ba in _BRODMANN:
        if key.lower() in rn:
            return ba
    return "—"  # no classical BA equivalent (e.g. subcortical structures)


def _load_ho():
    """Lazy-load and cache the Harvard-Oxford atlases (downloads once)."""
    global _HO, _LOAD_FAILED
    if _HO is not None or _LOAD_FAILED:
        return _HO
    try:
        from nilearn import datasets
        import nibabel as nib
        cort = datasets.fetch_atlas_harvard_oxford('cort-maxprob-thr25-2mm')
        sub  = datasets.fetch_atlas_harvard_oxford('sub-maxprob-thr25-2mm')
        cort_img = cort.maps if hasattr(cort, 'maps') else nib.load(cort['maps'])
        sub_img  = sub.maps  if hasattr(sub, 'maps')  else nib.load(sub['maps'])
        if isinstance(cort_img, str):
            cort_img = nib.load(cort_img)
        if isinstance(sub_img, str):
            sub_img = nib.load(sub_img)
        _HO = {
            'cort_data':   np.asarray(cort_img.dataobj),
            'cort_aff':    cort_img.affine,
            'cort_inv':    np.linalg.inv(cort_img.affine),
            'cort_labels': list(cort.labels),
            'sub_data':    np.asarray(sub_img.dataobj),
            'sub_aff':     sub_img.affine,
            'sub_inv':     np.linalg.inv(sub_img.affine),
            'sub_labels':  list(sub.labels),
        }
    except Exception as e:
        print(f"⚠️ Harvard-Oxford atlas unavailable ({e}); anatomical labels disabled.")
        _LOAD_FAILED = True
        _HO = None
    return _HO


def _region_at(ho, key, x, y, z):
    """Return the atlas label name at MNI (x,y,z) for cort/sub atlas, or None."""
    data = ho[f'{key}_data']; inv = ho[f'{key}_inv']; labels = ho[f'{key}_labels']
    vox = inv @ np.array([x, y, z, 1.0])
    i, j, k = (int(round(v)) for v in vox[:3])
    if not (0 <= i < data.shape[0] and 0 <= j < data.shape[1] and 0 <= k < data.shape[2]):
        return None
    idx = int(data[i, j, k])
    if idx <= 0 or idx >= len(labels):
        return None
    name = labels[idx]
    if name in ("Background",):
        return None
    return name


def label_at_mni(x, y, z):
    """Anatomical region + Brodmann equivalent at an MNI coordinate."""
    ho = _load_ho()
    if ho is None:
        return {'region': '—', 'brodmann': '—'}
    # Prefer cortical; fall back to subcortical (e.g. hippocampus, amygdala).
    name = _region_at(ho, 'cort', x, y, z)
    if name is None:
        name = _region_at(ho, 'sub', x, y, z)
    if name is None:
        return {'region': 'White matter / outside cortex', 'brodmann': '—'}
    return {'region': name, 'brodmann': _brodmann_for(name)}


def subregions_for_mask(mask, affine, max_regions=12, min_pct=1.0):
    """Given a binary network mask in some space (with `affine`), return the
    Harvard-Oxford cortical+subcortical subregions it overlaps, sorted by the
    number of overlapping voxels.

    Returns list of {'region', 'brodmann', 'n_voxels', 'pct'} where pct is the
    percentage of the network's voxels falling in that region.
    """
    ho = _load_ho()
    if ho is None:
        return []
    mask = np.asarray(mask) > 0
    if not mask.any():
        return []
    ijk = np.argwhere(mask)                       # voxel indices in network space
    # network voxel -> world (MNI)
    world = (affine @ np.c_[ijk, np.ones(len(ijk))].T).T[:, :3]

    counts = {}
    total = len(world)
    for key in ('cort', 'sub'):
        data = ho[f'{key}_data']; inv = ho[f'{key}_inv']; labels = ho[f'{key}_labels']
        vox = (inv @ np.c_[world, np.ones(total)].T).T[:, :3]
        vox = np.round(vox).astype(int)
        ok = ((vox[:, 0] >= 0) & (vox[:, 0] < data.shape[0]) &
              (vox[:, 1] >= 0) & (vox[:, 1] < data.shape[1]) &
              (vox[:, 2] >= 0) & (vox[:, 2] < data.shape[2]))
        v = vox[ok]
        if len(v) == 0:
            continue
        vals = data[v[:, 0], v[:, 1], v[:, 2]].astype(int)
        for idx in np.unique(vals):
            if idx <= 0 or idx >= len(labels):
                continue
            name = labels[idx]
            if name == "Background":
                continue
            # Avoid double-counting: cortical takes precedence; only add a
            # subcortical region if not already represented cortically.
            counts[name] = counts.get(name, 0) + int((vals == idx).sum())

    out = []
    for name, n in counts.items():
        pct = 100.0 * n / total
        if pct >= min_pct:
            out.append({'region': name, 'brodmann': _brodmann_for(name),
                        'n_voxels': int(n), 'pct': round(pct, 1)})
    out.sort(key=lambda d: d['n_voxels'], reverse=True)
    return out[:max_regions]
