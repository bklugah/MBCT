#!/usr/bin/env python3
"""
precompute_neurotransmitter.py  —  DEVELOPER-SIDE, RUN ONCE.

For every network footprint of every CBIG atlas, computes its spatial
association with PET-derived neurotransmitter receptor/transporter maps
(from the neuromaps collection, i.e. the Hansen et al. 2022 set) and writes:

        data/neurotransmitter_mapping.json

Statistic
---------
For each (network, receptor): the point-biserial correlation r between the
network's regional profile and the receptor density profile, evaluated on a
coarse common parcellation. r > 0 => the receptor is enriched in the network.

Significance
------------
Spatial-autocorrelation-preserving p-value (p_spin). Variogram-matched
surrogate receptor maps are generated with brainsmash (the engine neuromaps'
burt2020 null wraps) on the same coarse parcellation, and r is recomputed
against each surrogate. This is MANDATORY — a naive Pearson p on two smooth
brain maps is badly inflated.

Output structure
----------------
    {
      "_meta": {...},
      "EG17": {
         "Default": [["MOR", 0.34, 0.012], ["5HT1a", 0.28, 0.041], ...],
         ...
      },
      ...
    }
    (each row = [receptor_system, r, p_spin], sorted by |r| desc)

Requirements (developer machine only):
    pip install neuromaps brainsmash nilearn nibabel numpy scipy
    # note: neuromaps fetches maps from OSF (internet needed, one-time);
    #       if you hit a scipy import error in neuromaps.stats, it is unused here.

Usage:
    python precompute_neurotransmitter.py            # auto-detects atlases
    python precompute_neurotransmitter.py --only EG17,TY17 --n-perm 1000
    python precompute_neurotransmitter.py --n-perm 0  # fast: r only, skip p_spin
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import nibabel as nib

# Reuse the atlas discovery + network-mask logic from the Neurosynth script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from precompute_neurosynth import autodetect_atlas_dir, network_masks  # noqa: E402

# ---------------------------------------------------------------------------
#  Curated receptor / transporter maps (all verified present in neuromaps).
#  (system_label, source, desc, resolution)
# ---------------------------------------------------------------------------
RECEPTOR_MAPS = [
    ("GABAa",  "dukart2018",   "flumazenil", "3mm"),
    ("D1",     "kaller2017",   "sch23390",   "3mm"),
    ("D2",     "alarkurtti2015","raclopride","3mm"),
    ("SERT",   "savli2012",    "dasb",       "3mm"),
    ("5HT1a",  "savli2012",    "way100635",  "3mm"),
    ("5HT4",   "beliveau2017", "sb207145",   "1mm"),
    ("NET",    "ding2010",     "mrb",        "1mm"),
    ("mGluR5", "smart2019",    "abp688",     "1mm"),
    ("CB1",    "laurikainen2018","fmpepd2",  "1mm"),
    ("MOR",    "kantonen2020", "carfentanil","3mm"),
    ("VAChT",  "aghourian2017","feobv",      "1mm"),
    ("SV2A",   "finnema2016",  "ucbj",       "1mm"),
]


def _pearson(a, b):
    a = a - a.mean(); b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas-dir", default=None,
                    help="cbig_network_correspondence_data/atlases (auto-detected if omitted)")
    ap.add_argument("--names-dir", default=None)
    ap.add_argument("--out", default="data/neurotransmitter_mapping.json")
    ap.add_argument("--cache", default="neuromaps_cache")
    ap.add_argument("--space", default="FSLMNI2mm",
                    help="atlas space to decode (must be MNI152; FSLMNI2mm is exact)")
    ap.add_argument("--block", type=int, default=4,
                    help="coarse-parcel size in voxels (4 => ~8mm parcels; "
                         "smaller = finer but much more RAM for the null)")
    ap.add_argument("--min-vox", type=int, default=6,
                    help="minimum brain voxels for a parcel to be kept")
    ap.add_argument("--n-perm", type=int, default=1000,
                    help="variogram-null permutations for p_spin (0 = skip, r only)")
    ap.add_argument("--only", default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    atlas_dir = Path(args.atlas_dir) if args.atlas_dir else autodetect_atlas_dir()
    if atlas_dir is None or not atlas_dir.is_dir():
        sys.exit("Could not find atlases dir; pass --atlas-dir explicitly.")
    names_dir = Path(args.names_dir) if args.names_dir else atlas_dir.parent / "network_names"
    only = set(s.strip() for s in args.only.split(",")) if args.only else None
    print(f"🔎 Atlas dir: {atlas_dir}")

    # --- Heavy imports (developer machine only) ---------------------------
    try:
        from neuromaps.datasets import fetch_annotation
        from nilearn.image import resample_to_img
    except ImportError as e:
        sys.exit(f"Missing dependency: {e}\n  pip install neuromaps brainsmash nilearn")
    Base = None
    if args.n_perm > 0:
        try:
            from brainsmash.mapgen.base import Base
        except ImportError:
            sys.exit("brainsmash is required for p_spin (or pass --n-perm 0):\n"
                     "  pip install brainsmash")

    # --- A reference grid: use the first atlas's grid (FSLMNI2mm) ----------
    spdir = atlas_dir / args.space
    if not spdir.is_dir():
        sys.exit(f"Space dir not found: {spdir}")
    sample_atlas = next(spdir.glob("*/*.nii.gz"), None)
    if sample_atlas is None:
        sys.exit(f"No atlases found under {spdir}")
    ref_img = nib.load(str(sample_atlas))
    ref_img = nib.Nifti1Image(np.zeros(ref_img.shape[:3]), ref_img.affine)

    # --- Fetch + resample receptor maps to the reference grid -------------
    print("⬇️  Fetching neuromaps receptor maps (one-time, internet/OSF)…")
    os.makedirs(args.cache, exist_ok=True)
    rec_data = {}   # system -> flat array over ref grid
    for system, src, desc, res in RECEPTOR_MAPS:
        try:
            p = fetch_annotation(source=src, desc=desc, space="MNI152", res=res,
                                 data_dir=args.cache, verbose=0)
            img = nib.load(p) if isinstance(p, (str, os.PathLike)) else p
            img = resample_to_img(img, ref_img, interpolation="linear")
            rec_data[system] = np.asarray(img.get_fdata(), float).ravel()
            print(f"   ✅ {system:7} ({src}/{desc})")
        except Exception as e:
            print(f"   ⚠️ {system}: fetch failed ({str(e)[:80]}); skipping")
    if not rec_data:
        sys.exit("No receptor maps could be fetched — check internet/OSF access.")

    # --- Common analysis mask + coarse parcellation -----------------------
    ref_shape = ref_img.shape[:3]
    finite_nonzero = np.ones(int(np.prod(ref_shape)), bool)
    for v in rec_data.values():
        finite_nonzero &= np.isfinite(v) & (v != 0)
    brain = finite_nonzero.reshape(ref_shape)
    B = args.block
    ii, jj, kk = np.indices(ref_shape)
    pidx = ((ii // B).astype(np.int64) * 10_000_000
            + (jj // B) * 10_000 + (kk // B))
    pidx_flat = pidx.ravel()
    brain_flat = brain.ravel()

    # group voxels by parcel id, keep parcels with enough brain voxels
    order = np.argsort(pidx_flat)
    sp = pidx_flat[order]
    boundaries = np.where(np.diff(sp) != 0)[0] + 1
    groups = np.split(order, boundaries)
    parcels = []  # list of (voxel_indices_in_brain,)
    for g in groups:
        gb = g[brain_flat[g]]
        if gb.size >= args.min_vox:
            parcels.append(gb)
    n_par = len(parcels)
    print(f"🧩 Coarse parcellation: {n_par} parcels (~{2*B}mm) over the brain mask")

    # parcel centroids (world coords) and distance matrix
    from scipy.spatial.distance import cdist
    aff = ref_img.affine
    cent = np.zeros((n_par, 3))
    for pi, gb in enumerate(parcels):
        vi, vj, vk = np.unravel_index(gb, ref_shape)
        m = np.array([vi.mean(), vj.mean(), vk.mean(), 1.0])
        cent[pi] = (aff @ m)[:3]
    if n_par > 12000:
        print(f"⚠️ {n_par} parcels is large; consider a bigger --block for speed/RAM.")
    D = cdist(cent, cent)   # (n_par, n_par), computed directly (no 3-D intermediate)

    # parcel-mean receptor vectors
    rec_parcel = {}
    for system, v in rec_data.items():
        rec_parcel[system] = np.array([v[gb].mean() for gb in parcels])

    # pre-generate surrogate receptor maps once per receptor (reused for all nets)
    rec_surrogates = {}
    if args.n_perm > 0:
        print(f"🎲 Generating {args.n_perm} variogram surrogates per receptor "
              f"(spatial null)…")
        for system, vec in rec_parcel.items():
            gen = Base(x=vec, D=D, seed=args.seed)
            rec_surrogates[system] = np.asarray(gen(n=args.n_perm))  # (n_perm, n_par)

    # --- Discover atlas jobs ---------------------------------------------
    jobs = []
    for author in sorted(os.listdir(spdir)):
        adir = spdir / author
        if not adir.is_dir():
            continue
        for f in sorted(adir.glob("*.nii.gz")):
            abbr = f.name.replace(".nii.gz", "")
            if only and abbr not in only:
                continue
            nmf = names_dir / abbr
            names = nmf.read_text().split() if nmf.exists() else [abbr]
            jobs.append((abbr, f, names))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output = {"_meta": {
        "source": "neuromaps PET receptor/transporter maps (Hansen et al. 2022 collection)",
        "statistic": "point-biserial r between network profile and receptor density "
                     "on a coarse parcellation",
        "null": f"variogram-matched surrogates (brainsmash), p_spin two-sided, "
                f"n_perm={args.n_perm}" if args.n_perm > 0 else "none (r only)",
        "receptors": [s for s, *_ in RECEPTOR_MAPS if s in rec_data],
        "parcels": n_par,
        "space": args.space,
    }}
    done = set()
    if args.resume and out_path.exists():
        try:
            existing = json.load(open(out_path, encoding="utf-8"))
            if not existing.get("_meta", {}).get("sample"):
                for k, v in existing.items():
                    if k != "_meta":
                        output[k] = v
                        if v:
                            done.add(k)
                print(f"↩️  Resume: skipping {len(done)} completed atlases")
        except Exception:
            pass

    def _save():
        json.dump(output, open(out_path, "w", encoding="utf-8"), indent=2)

    rng = np.random.default_rng(args.seed)
    print(f"🧠 Mapping {len(jobs)} atlases against {len(rec_data)} receptor systems…")
    for ai, (abbr, apath, names) in enumerate(jobs, 1):
        if args.resume and abbr in done:
            print(f"  [{ai}/{len(jobs)}] {abbr} — done, skip")
            continue
        print(f"  [{ai}/{len(jobs)}] {abbr} ({len(names)} networks)…")
        atlas_entry = {}
        for net_idx, net_name, mask_img in network_masks(apath, names):
            # resample/align network mask to the reference grid, then parcel-fraction
            m = np.asarray(mask_img.get_fdata(), float)
            if m.shape != ref_shape:
                m = np.asarray(resample_to_img(
                    mask_img, ref_img, interpolation="nearest").get_fdata(), float)
            mflat = (m.ravel() > 0)
            net_vec = np.array([mflat[gb].mean() for gb in parcels])
            if net_vec.sum() == 0:
                continue
            rows = []
            for system in rec_data:
                rvec = rec_parcel[system]
                r_obs = _pearson(net_vec, rvec)
                if args.n_perm > 0:
                    surr = rec_surrogates[system]
                    r_null = np.array([_pearson(net_vec, s) for s in surr])
                    p = (np.sum(np.abs(r_null) >= abs(r_obs)) + 1) / (len(r_null) + 1)
                else:
                    p = None
                rows.append([system, round(r_obs, 4),
                             (round(float(p), 4) if p is not None else None)])
            rows.sort(key=lambda x: abs(x[1]), reverse=True)
            atlas_entry[net_name] = rows
            top = rows[0]
            print(f"      {net_name:14} top: {top[0]} r={top[1]:+.2f}"
                  + (f" p={top[2]}" if top[2] is not None else ""))
        output[abbr] = atlas_entry
        _save()

    _save()
    print(f"\n✅ Wrote {out_path}  ({out_path.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
