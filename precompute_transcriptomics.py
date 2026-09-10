#Klugah-Brown 2026
"""
precompute_transcriptomics.py  —  DEVELOPER-SIDE, RUN ONCE.

For every network footprint of every CBIG atlas, computes its spatial
association with the regional expression of NEUROTRANSMITTER RECEPTOR GENES
(Allen Human Brain Atlas, via abagen) and writes:

        data/transcriptomics_mapping.json

Why receptor genes only
-----------------------
A raw "top genes" list over all ~20,000 AHBA genes is a 20k-way multiple
comparison, hard to interpret, and notoriously pipeline-sensitive (abagen's
own paper shows processing choices can swing gene-imaging correlations by
rho >= 1.0). Scoping to receptor genes keeps it interpretable AND lets the app
pair each gene with its PET receptor map for convergent cross-validation:
e.g. D2 receptor *density* (raclopride PET) vs DRD2 *mRNA* (AHBA) for a network.

Why the Desikan-Killiany atlas
------------------------------
The AHBA has only ~3,700 tissue samples across six donors, so a fine cubic
parcellation would leave most parcels with no samples. DK's 83 regions are the
standard, well-sampled choice for imaging transcriptomics; abagen ships it.

Statistic & significance
-------------------------
Per (network, gene): point-biserial r between the network's regional profile
(fraction of each DK region inside the network) and the gene's regional
expression. Significance is a spatial-autocorrelation-preserving p_spin from
variogram-matched surrogates (brainsmash) over DK region centroids.

Output structure
----------------
    { "_meta": {...},
      "EG17": {"Default": [["DRD2 (D2)", 0.21, 0.04], ...]}, ... }
    (each row = ["GENE (SYSTEM)", r, p_spin], sorted by |r| desc)

Requirements (developer machine only):
    pip install abagen brainsmash nilearn nibabel numpy scipy pandas
    # abagen downloads the Allen Human Brain Atlas (~4 GB) on first run.

Usage:
    
    # Simple: compute transcriptomics from cached AHBA data
    # (assumes AHBA donor zips are already in ahba_cache/microarray/)
    python precompute_transcriptomics.py --only EG17,TY17 --n-perm 0
    
    # Full run with p_spin:
    python precompute_transcriptomics.py --n-perm 1000
    
    # Single atlas for testing:
    python precompute_transcriptomics.py --only EG17 --n-perm 0
"""

import argparse
import json
import os
import sys
from pathlib import Path


project_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_dir))

import numpy as np
import nibabel as nib

from precompute_neurosynth import autodetect_atlas_dir, network_masks  


RECEPTOR_GENES = [
    ("GABAa",  "GABRA1"),
    ("D1",     "DRD1"),
    ("D2",     "DRD2"),
    ("SERT",   "SLC6A4"),
    ("5HT1a",  "HTR1A"),
    ("5HT4",   "HTR4"),
    ("NET",    "SLC6A2"),
    ("mGluR5", "GRM5"),
    ("CB1",    "CNR1"),
    ("MOR",    "OPRM1"),
    ("VAChT",  "SLC18A3"),
    ("SV2A",   "SV2A"),
]


def _pearson(a, b):
    """Compute Pearson correlation coefficient."""
    a = a - a.mean()
    b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def _load_ahba_from_cache(cache_dir):
    """Load AHBA microarray data with proper regional aggregation via DK atlas."""
    import zipfile
    import pandas as pd
    from scipy.spatial.distance import cdist as scipy_cdist
    
    cache_path = Path(cache_dir) / "microarray"
    zips = sorted(cache_path.glob("normalized_microarray_donor*.zip"))
    
    if not zips:
        raise OSError(f"No AHBA zips found in {cache_path}")
    
    print(f"Loading {len(zips)} donors with regional aggregation...")
    all_donor_data = {}  
    
    for zf in zips:
        donor = zf.stem.replace("normalized_microarray_", "")
        print(f"  Processing {donor}...")
        
        with zipfile.ZipFile(zf, 'r') as z:
            # Load probe mapping
            try:
                with z.open('Probes.csv') as f:
                    probes_df = pd.read_csv(f)
                probe_to_gene = dict(zip(probes_df['probe_id'], probes_df['gene_symbol']))
            except Exception as e:
                print(f"     Could not load Probes.csv: {e}")
                continue
            
            # Load expression data (probes × samples)
            try:
                with z.open('MicroarrayExpression.csv') as f:
                    expr_df = pd.read_csv(f, index_col=0, header=None)
            except Exception as e:
                print(f"     Could not load MicroarrayExpression.csv: {e}")
                continue
            
            
            try:
                with z.open('SampleAnnot.csv') as f:
                    annot_df = pd.read_csv(f)
                
                mni_coords = annot_df[['mni_x', 'mni_y', 'mni_z']].values  
            except Exception as e:
                print(f"     Could not load SampleAnnot.csv: {e}")
                continue
            
            if len(mni_coords) != expr_df.shape[1]:
                print(f"     Sample count mismatch: expr={expr_df.shape[1]}, annot={len(mni_coords)}")
                continue
            
            print(f"     Loaded: {expr_df.shape[0]} probes × {expr_df.shape[1]} samples")
            
            
            all_donor_data[donor] = {
                'expr': expr_df,
                'mni': mni_coords,
                'probe_to_gene': probe_to_gene
            }
    
    if not all_donor_data:
        raise OSError("Could not load any donor data from zips")
    
    return all_donor_data


def _aggregate_to_dk_regions(ahba_donor_data, dk_img, ref_shape, aff, region_ids):
    """Map AHBA samples to DK regions via coordinates, aggregate gene expression."""
    import pandas as pd
    from scipy.spatial.distance import cdist as scipy_cdist
    
    dk_lab = np.asarray(dk_img.get_fdata()).astype(int)
    
    
    region_centroids = {}
    for rid in region_ids:
        vox = np.argwhere(dk_lab == rid)
        if len(vox) > 0:
            c = (aff @ np.append(vox.mean(axis=0), 1.0))[:3]
            region_centroids[rid] = c
    
    print(f"  DK atlas: {len(region_centroids)} regions")
    
    
    all_genes = set()
    gene_region_data = {}  
    
    for donor, data in sorted(ahba_donor_data.items()):
        expr_df = data['expr']  
        mni_coords = data['mni']  
        probe_to_gene = data['probe_to_gene']
        
        
        region_centroids_array = np.array([region_centroids[rid] for rid in region_ids])
        distances = scipy_cdist(mni_coords, region_centroids_array)  
        sample_to_region = np.argmin(distances, axis=1)  
        
        
        expr_df['gene_symbol'] = expr_df.index.map(probe_to_gene)
        expr_df = expr_df[expr_df['gene_symbol'].notna()]  
        
        
        for gene in expr_df['gene_symbol'].unique():
            all_genes.add(gene)
            probe_rows = expr_df[expr_df['gene_symbol'] == gene].iloc[:, :-1]  
            
            for ri, rid in enumerate(region_ids):
                sample_mask = (sample_to_region == ri)
                if sample_mask.sum() > 0:
                    
                    expr_val = probe_rows.iloc[:, sample_mask].values.mean()
                    key = (gene, ri)
                    if key not in gene_region_data:
                        gene_region_data[key] = []
                    gene_region_data[key].append(expr_val)
        
        print(f"     {donor}: {len(expr_df['gene_symbol'].unique())} genes mapped")
    
    
    genes_sorted = sorted(all_genes)
    gene_expr_matrix = np.zeros((len(genes_sorted), len(region_ids)))
    
    for gi, gene in enumerate(genes_sorted):
        for ri in range(len(region_ids)):
            key = (gene, ri)
            if key in gene_region_data:
                gene_expr_matrix[gi, ri] = np.mean(gene_region_data[key])
    
    expr_df = pd.DataFrame(gene_expr_matrix, index=genes_sorted, 
                           columns=[f'region_{i}' for i in range(len(region_ids))])
    
    print(f"\n   Final: {expr_df.shape[0]} genes × {expr_df.shape[1]} regions")
    return expr_df




    a = a - a.mean(); b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas-dir", default=None,
                    help="cbig_network_correspondence_data/atlases (auto-detected if omitted)")
    ap.add_argument("--names-dir", default=None)
    ap.add_argument("--out", default="data/transcriptomics_mapping.json")
    ap.add_argument("--cache", default="ahba_cache",
                    help="where abagen downloads/caches the Allen Human Brain Atlas")
    ap.add_argument("--space", default="FSLMNI2mm")
    ap.add_argument("--n-perm", type=int, default=1000,
                    help="variogram-null permutations for p_spin (0 = r only)")
    ap.add_argument("--only", default=None)
    ap.add_argument("--resume", action="store_true",
                    help="resume partial AHBA download and skip completed atlases")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--n-proc", type=int, default=1,
                    help="parallel processes for abagen")
    ap.add_argument("--use-atlas-info", action="store_true",
                    help="pass the DK info CSV to abagen (constrains "
                         "sample matching; currently trips an abagen "
                         "pandas>=2.0 bug)")
    ap.add_argument("--legacy-aggregation", action="store_true",
                    help="use the old unnormalized regional means "
                         "(smoke-testing only; NOT reportable)")
    args = ap.parse_args()

    atlas_dir = Path(args.atlas_dir) if args.atlas_dir else autodetect_atlas_dir()
    if atlas_dir is None or not atlas_dir.is_dir():
        sys.exit("Could not find atlases dir; pass --atlas-dir explicitly.")
    names_dir = Path(args.names_dir) if args.names_dir else atlas_dir.parent / "network_names"
    only = set(s.strip() for s in args.only.split(",")) if args.only else None
    print(f"Atlas dir: {atlas_dir}")

    
    try:
        from nilearn.image import resample_to_img
        import pandas as pd
    except ImportError as e:
        sys.exit(f"Missing dependency: {e}\n  pip install nilearn pandas")
    Base = None
    if args.n_perm > 0:
        try:
            from brainsmash.mapgen.base import Base
        except ImportError:
            sys.exit("brainsmash required for p_spin (or use --n-perm 0): pip install brainsmash")

    
    spdir = atlas_dir / args.space
    sample_atlas = next(spdir.glob("*/*.nii.gz"), None)
    if sample_atlas is None:
        sys.exit(f"No atlases under {spdir}")
    ra = nib.load(str(sample_atlas))
    ref_shape = ra.shape[:3]
    aff = ra.affine
    ref_img = nib.Nifti1Image(np.zeros(ref_shape), aff)

    
    print("Loading Desikan-Killiany atlas (83 regions)...")
    
    dk_atlas_path = None
    dk_info_path = None

    try:
        import abagen as _abg
        _fetched = _abg.fetch_desikan_killiany()
        _img = _fetched.get('image') if isinstance(_fetched, dict) else _fetched
        _inf = _fetched.get('info') if isinstance(_fetched, dict) else None
        if _img:
            dk_atlas_path = Path(str(_img))
            if _inf:
                dk_info_path = Path(str(_inf))
            print("  DK atlas via abagen.fetch_desikan_killiany()")
    except Exception as _e:
        print(f"  (abagen fetcher unavailable: {_e})")

    if dk_atlas_path is None or not dk_atlas_path.exists():
        candidates = []
        try:
            import abagen as _abg
            candidates.append(Path(_abg.__file__).resolve().parent
                              / "data" / "atlas-desikankilliany.nii.gz")
        except Exception:
            pass
        candidates.append(Path(__file__).resolve().parent / "abagen"
                          / "data" / "atlas-desikankilliany.nii.gz")
        for c in candidates:
            if c.exists():
                dk_atlas_path = c
                break

    if dk_atlas_path is None or not dk_atlas_path.exists():
        sys.exit("Desikan-Killiany atlas not found.\n"
                 "Install abagen ('pip install abagen') so that\n"
                 "  <site-packages>/abagen/data/atlas-desikankilliany.nii.gz\n"
                 "is available, or place that file in an 'abagen/data' folder "
                 "next to this script.")
    
    dk_img = nib.load(str(dk_atlas_path))
    print(f"   Loaded from {dk_atlas_path}")
    
    dk_lab = np.asarray(resample_to_img(
        dk_img, ref_img, interpolation='nearest').get_fdata()).astype(int)
    region_ids = sorted(int(x) for x in np.unique(dk_lab) if x > 0)
    region_vox = {rid: np.flatnonzero((dk_lab == rid).ravel()) for rid in region_ids}

    
    from scipy.spatial.distance import cdist
    cent = np.zeros((len(region_ids), 3))
    for i, rid in enumerate(region_ids):
        vi, vj, vk = np.unravel_index(region_vox[rid], ref_shape)
        cent[i] = (aff @ np.array([vi.mean(), vj.mean(), vk.mean(), 1.0]))[:3]
    D = cdist(cent, cent)

    
    expr = None
    if not args.legacy_aggregation:
        try:
            import abagen
            _cache_abs = str(Path(args.cache).expanduser().resolve())
            print(f"   AHBA cache: {_cache_abs}")
            print("Building regional expression matrix with abagen "
                  "(probe_selection='diff_stability', gene_norm='srs')...")
            df = abagen.get_expression_data(
                str(dk_atlas_path),            
                
                atlas_info=(str(dk_info_path)
                            if (args.use_atlas_info and dk_info_path
                                and Path(dk_info_path).exists()) else None),
                probe_selection='diff_stability',
                donor_probes='aggregate',
                sample_norm='srs',
                gene_norm='srs',
                region_agg='donors',
                agg_metric='mean',
                missing='centroids',           
                data_dir=str(Path(args.cache).expanduser().resolve()),
                verbose=1,
                n_proc=args.n_proc,
            )
            
            expr = df.transpose()
            expr.columns = list(df.index)
            print(f"    abagen matrix: {expr.shape[0]} genes x "
                  f"{expr.shape[1]} regions (normalized)")
        except ImportError:
            print("     abagen is not installed. Install it with "
                  "'pip install abagen', or pass --legacy-aggregation to use "
                  "the unnormalized fallback (NOT suitable for reporting).")
            sys.exit(1)
        except Exception as e:
            print(f"     abagen failed: {e}")
            print("   Re-run with --legacy-aggregation only for smoke-testing; "
                  "its values must not be reported as results.")
            sys.exit(1)
    else:
        print("  LEGACY aggregation requested: raw regional means, NO "
              "normalization.\n"
              "    Gene-specific signal is confounded by the shared regional "
              "component;\n"
              "    these values must NOT be reported as results.")
        ahba_donor_data = _load_ahba_from_cache(args.cache)
        print("\nAggregating samples to DK regions via MNI coordinates...")
        expr = _aggregate_to_dk_regions(
            ahba_donor_data, dk_img, ref_shape, aff, region_ids)

    
    want = [(s, g) for s, g in RECEPTOR_GENES if g in expr.index]
    missing = [g for _, g in RECEPTOR_GENES if g not in expr.index]

    if missing:
        print(f"     genes not found: {', '.join(missing[:5])}... ({len(missing)} total)")
    if not want:
        sys.exit(f"None of the {len(RECEPTOR_GENES)} receptor genes found in AHBA data.")

    print(f"    {len(want)} receptor genes found")

    # expr is now: genes × regions
    gene_vec = {}
    for _, g in want:
        v = np.asarray(expr.loc[g].values, dtype=float)
        
        if np.isnan(v).any():
            finite = np.isfinite(v)
            v = np.where(finite, v, v[finite].mean() if finite.any() else 0.0)
        gene_vec[g] = v
    sys_of = {g: s for s, g in want}

    
    _stack = np.vstack([gene_vec[g] for _, g in want])
    if _stack.shape[0] > 1:
        _z = (_stack - _stack.mean(axis=1, keepdims=True)) / (
            _stack.std(axis=1, keepdims=True) + 1e-12)
        _cc = np.corrcoef(_z)
        _off = _cc[~np.eye(len(_cc), dtype=bool)]
        _median_r = float(np.median(np.abs(_off)))
        print(f"   median |r| between gene profiles: {_median_r:.2f}")
        if _median_r > 0.95:
            print("     WARNING: gene expression profiles are nearly "
                  "identical to one another.\n"
                  "       The matrix is dominated by a shared regional "
                  "component and per-gene\n"
                  "       associations will not be interpretable. Check that "
                  "normalization ran.")

    
    gene_surr = {}
    if args.n_perm > 0:
        print(f"Generating {args.n_perm} variogram surrogates per gene...")
        for _, g in want:
            gene_surr[g] = np.asarray(Base(x=gene_vec[g], D=D, seed=args.seed)(n=args.n_perm))

    # --- Discover atlas jobs ----------------------------------------------
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
        "source": "Allen Human Brain Atlas via abagen; Desikan-Killiany (83 regions)",
        "statistic": "point-biserial r between network profile and regional gene expression",
        "null": (f"variogram-matched surrogates (brainsmash), p_spin two-sided, "
                 f"n_perm={args.n_perm}") if args.n_perm > 0 else "none (r only)",
        "genes": [g for _, g in want],
        "gene_receptor_pairs": {g: s for s, g in want},
        "abagen_options": "DK atlas, lr_mirror=bidirectional, missing=interpolate, "
                          "diff_stability probes, srs norm",
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
                print(f"Resume: skipping {len(done)} completed atlases")
        except Exception:
            pass

    def _save():
        json.dump(output, open(out_path, "w", encoding="utf-8"), indent=2)

    print(f"Mapping {len(jobs)} atlases against {len(want)} receptor genes...")
    for ai, (abbr, apath, names) in enumerate(jobs, 1):
        if args.resume and abbr in done:
            print(f"  [{ai}/{len(jobs)}] {abbr} - done, skip")
            continue
        print(f"  [{ai}/{len(jobs)}] {abbr} ({len(names)} networks)...")
        atlas_entry = {}
        for net_idx, net_name, mask_img in network_masks(apath, names):
            m = np.asarray(mask_img.get_fdata(), float)
            if m.shape != ref_shape:
                m = np.asarray(resample_to_img(
                    mask_img, ref_img, interpolation='nearest').get_fdata(), float)
            mflat = (m.ravel() > 0)
            net_vec = np.array([mflat[region_vox[rid]].mean() for rid in region_ids])
            if net_vec.sum() == 0:
                continue
            rows = []
            for _, g in want:
                r_obs = _pearson(net_vec, gene_vec[g])
                if args.n_perm > 0:
                    rn = np.array([_pearson(net_vec, s) for s in gene_surr[g]])
                    p = (np.sum(np.abs(rn) >= abs(r_obs)) + 1) / (len(rn) + 1)
                else:
                    p = None
                rows.append([f"{g} ({sys_of[g]})", round(r_obs, 4),
                             (round(float(p), 4) if p is not None else None)])
            rows.sort(key=lambda x: abs(x[1]), reverse=True)
            atlas_entry[net_name] = rows
            top = rows[0]
            print(f"      {net_name:14} top: {top[0]} r={top[1]:+.2f}"
                  + (f" p={top[2]}" if top[2] is not None else ""))
        output[abbr] = atlas_entry
        _save()

    _save()
    print(f"\nWrote {out_path}  ({out_path.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
