#Klugah-Brown 2026
"""
precompute_neurosynth.py  —  DEVELOPER-SIDE, RUN ONCE.

Decodes every network footprint of every CBIG atlas against the Neurosynth
database (via NiMARE's ROIAssociationDecoder) and writes a single bundled file:

        data/neurosynth_decoding.json

That JSON is what ships inside the application. End users never run this script,
never install NiMARE, and never download the Neurosynth database — the app only
reads the finished JSON.

Output structure:
    {
      "_meta": {... provenance ...},
      "EG17": {
         "Default":  [["memory", 0.71], ["social", 0.62], ...up to 20...],
         "LatVis":   [["visual", 0.80], ...],
         ...
      },
      "TY17": {...},
      ...
    }

Requirements (developer machine only):
    pip install nimare nilearn nibabel numpy scipy

Usage:
    python precompute_neurosynth.py \
        --atlas-dir cbig_network_correspondence_data/atlases \
        --out data/neurosynth_decoding.json
    # optional: --spaces FSLMNI2mm  --top 20  --only EG17,TY17
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import nibabel as nib


TERM_BLACKLIST = {
    
    "fmri", "mri", "pet", "eeg", "meg", "bold", "voxel", "voxels", "voxelwise",
    "imaging", "image", "images", "scan", "scans", "scanner", "scanning",
    "signal", "signals", "magnetic", "resonance", "echo", "slice", "slices",
    "resolution", "acquisition", "spatial", "temporal", "smoothing", "preprocessing",
    "registration", "normalization", "segmentation", "roi", "rois", "seed",
    "connectivity", "functional", "structural", "resting", "rest", "state",
    "dti", "tractography", "diffusion", "tensor", "anisotropy", "white", "gray",
    "matter", "vbm", "morphometry", "cortical", "subcortical", "thickness",
    # statistics / analysis
    "analysis", "analyses", "correlation", "correlations", "correlated",
    "regression", "model", "models", "modeling", "anova", "significant",
    "significance", "comparison", "comparisons", "contrast", "contrasts",
    "effect", "effects", "interaction", "main", "factor", "variance",
    "threshold", "cluster", "clusters", "peak", "peaks", "coordinates",
    "activation", "activations", "activity", "activated", "deactivation",
    "increase", "increased", "increases", "decrease", "decreased", "greater",
    "higher", "lower", "positive", "negative", "differences", "difference",
    # study design / population
    "task", "tasks", "study", "studies", "experiment", "experiments",
    "condition", "conditions", "trial", "trials", "block", "blocks", "event",
    "events", "stimulus", "stimuli", "stimulation", "presentation", "paradigm",
    "performance", "performed", "subjects", "subject", "participants",
    "participant", "individuals", "individual", "healthy", "patients", "patient",
    "controls", "control", "group", "groups", "young", "older", "age", "aged",
    "adults", "adult", "children", "male", "female", "males", "females", "sex",
    "session", "sessions", "data", "results", "result", "measures", "measure",
    "measured", "measurement", "response", "responses", "responded", "rate",
    "time", "times", "duration", "onset", "period", "level", "levels",
    # anatomy (locations, not functions)
    "cortex", "cortical", "gyrus", "gyri", "sulcus", "sulci", "lobe", "lobes",
    "lobule", "lobular", "frontal", "prefrontal", "parietal", "temporal",
    "occipital", "insula", "insular", "cingulate", "precuneus", "cuneus",
    "hippocampus", "hippocampal", "amygdala", "thalamus", "thalamic",
    "striatum", "striatal", "putamen", "caudate", "pallidum", "accumbens",
    "cerebellum", "cerebellar", "brainstem", "midbrain", "pons", "medulla",
    "hemisphere", "hemispheres", "hemispheric", "lateral", "medial", "dorsal",
    "ventral", "anterior", "posterior", "superior", "inferior", "rostral",
    "caudal", "bilateral", "ipsilateral", "contralateral", "regions", "region",
    "area", "areas", "network", "networks", "circuit", "circuits", "system",
    "systems", "structures", "structure", "nucleus", "nuclei", "matter",
    "brain", "cerebral", "neural", "neuronal", "neurons", "neuron", "cells",
    # generic filler
    "associated", "association", "related", "relationship", "involved",
    "involvement", "role", "roles", "function", "functions", "processing",
    "process", "processes", "mechanism", "mechanisms", "underlying", "specific",
    "general", "common", "different", "similar", "evidence", "findings",
    "finding", "suggest", "suggests", "reported", "observed", "showed", "shown",
    "present", "current", "previous", "recent", "potential", "important",
}


def clean_feature_name(feat: str) -> str:
    """Strip NiMARE's feature prefix, e.g. 'terms_abstract_tfidf__working memory'
    -> 'working memory'."""
    if "__" in feat:
        feat = feat.split("__")[-1]
    return feat.strip().lower()


def is_functional_term(term: str) -> bool:
    """Keep multi-sense cognitive/functional terms, drop blacklisted words."""
    t = term.strip().lower()
    if not t or any(ch.isdigit() for ch in t):
        return False
    
    tokens = t.split()
    if len(tokens) > 1:
        return not all(tok in TERM_BLACKLIST for tok in tokens)
    if len(t) < 3:
        return False
    return t not in TERM_BLACKLIST



def load_network_assignment(atlas_path: Path):
    try:
        import scipy.io as sio
    except Exception:
        return None
    abbr = atlas_path.name.replace(".nii.gz", "").replace(".nii", "")
    p = atlas_path
    for _ in range(7):
        p = p.parent
        for cand in (p / "network_assignment" / f"{abbr}.mat",
                     p / "data" / "network_assignment" / f"{abbr}.mat"):
            if cand.exists():
                try:
                    return np.asarray(sio.loadmat(str(cand))["mapping"]).ravel()
                except Exception:
                    return None
    return None


def resolve_atlas_mapping(atlas_vol, atlas_path: Path, n_names):
    """Return (mode, label_map). mode in {'labels','metric','4d'}."""
    if atlas_vol.ndim == 4:
        return "4d", None
    uniq = sorted(int(v) for v in np.unique(atlas_vol) if v > 0)
    if not uniq:
        return "metric", None
    n_uniq = len(uniq)
    if n_names and n_uniq == n_names:
        return "labels", {lab: i for i, lab in enumerate(uniq)}
    if n_names and n_uniq > n_names:
        assign = load_network_assignment(atlas_path)
        if assign is not None and len(assign) >= max(uniq):
            lm = {}
            for lab in uniq:
                net = int(assign[lab - 1]) - 1
                if 0 <= net < n_names:
                    lm[lab] = net
            if lm:
                return "labels", lm
        return "metric", None
    return "labels", {lab: i for i, lab in enumerate(uniq)}


def network_masks(atlas_path: Path, network_names):
    """Yield (network_index, network_name, mask_img) for each network of an atlas.
    Masks are returned in the atlas's native grid; they're resampled to the
    Neurosynth MNI152-2mm grid by the decoder masker."""
    img = nib.load(str(atlas_path))
    data = img.get_fdata()
    aff = img.affine
    n = len(network_names)
    mode, label_map = resolve_atlas_mapping(data, atlas_path, n)

    if mode == "4d":
        for i in range(min(n, data.shape[3])):
            m = (data[..., i] > 0).astype(np.int16)
            if m.any():
                yield i, network_names[i], nib.Nifti1Image(m, aff)
    elif mode == "metric":
        m = (data > 0).astype(np.int16)
        if m.any():
            yield 0, network_names[0], nib.Nifti1Image(m, aff)
    else:  # labels
        for net_idx in range(n):
            labs = [lab for lab, idx in (label_map or {}).items() if idx == net_idx]
            if not labs:
                continue
            m = np.isin(data, labs).astype(np.int16)
            if m.any():
                yield net_idx, network_names[net_idx], nib.Nifti1Image(m, aff)


# ---------------------------------------------------------------------------
#  Main precompute
# ---------------------------------------------------------------------------
def autodetect_atlas_dir():
    """Find the CBIG atlases directory without requiring the user to pass it.

    Searches, in order: the configured CBIG atlas dir (if the app's config is
    importable), then common locations relative to this script.
    """
    candidates = []
    
    try:
        from nct_application.cbig_config import CBIGConfig
        ad = CBIGConfig.get_atlas_dir()
        if ad:
            candidates.append(Path(ad))
    except Exception:
        pass
    
    here = Path(__file__).resolve().parent
    roots = [here, Path.cwd()]
    rel = [
        Path("cbig_network_correspondence_data") / "atlases",
        Path("cbig_network_correspondence_data"),
        Path("atlases"),
    ]
    for root in roots:
        for r in rel:
            candidates.append(root / r)
        
        try:
            for hit in root.glob("**/atlases"):
                candidates.append(hit)
        except Exception:
            pass
    
    known_spaces = {"FSLMNI2mm", "LairdColin2mm", "ShenColin1mm",
                    "fs_LR_32k", "fsaverage6"}
    seen = set()
    for c in candidates:
        try:
            c = c.resolve()
        except Exception:
            continue
        if c in seen or not c.is_dir():
            continue
        seen.add(c)
        if any((c / sp).is_dir() for sp in known_spaces):
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas-dir", default=None,
                    help="path to cbig_network_correspondence_data/atlases "
                         "(auto-detected if omitted)")
    ap.add_argument("--names-dir", default=None,
                    help="path to network_names dir (default: <atlas-dir>/../network_names)")
    ap.add_argument("--out", default="data/neurosynth_decoding.json")
    ap.add_argument("--cache", default="neurosynth_cache",
                    help="where to download/cache the Neurosynth database")
    ap.add_argument("--spaces", default="FSLMNI2mm",
                    help="comma-separated atlas spaces to decode (Neurosynth is MNI152; "
                         "FSLMNI2mm is exact, others are resampled)")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--only", default=None,
                    help="comma-separated atlas abbreviations to limit to (e.g. EG17,TY17)")
    ap.add_argument("--resume", action="store_true",
                    help="skip atlases already present in the output JSON and append new "
                         "ones; the file is saved after each atlas so an interrupted run "
                         "can be continued without losing work")
    args = ap.parse_args()

    
    if args.atlas_dir:
        atlas_dir = Path(args.atlas_dir)
    else:
        atlas_dir = autodetect_atlas_dir()
        if atlas_dir is None:
            sys.exit("Could not auto-detect the atlases directory. "
                     "Pass it explicitly with --atlas-dir "
                     "cbig_network_correspondence_data\\atlases")
        print(f"🔎 Auto-detected atlas dir: {atlas_dir}")
    if not atlas_dir.is_dir():
        sys.exit(f"Atlas dir does not exist: {atlas_dir}")
    names_dir = Path(args.names_dir) if args.names_dir else atlas_dir.parent / "network_names"
    spaces = [s.strip() for s in args.spaces.split(",") if s.strip()]
    only = set(s.strip() for s in args.only.split(",")) if args.only else None

    
    try:
        from nimare.extract import fetch_neurosynth
        from nimare.decode.discrete import ROIAssociationDecoder
    except ImportError as e:
        import sys as _sys
        msg = [
            "",
            "Could not import NiMARE (or one of its dependencies).",
            f"  Python executable : {_sys.executable}",
            f"  Underlying error  : {type(e).__name__}: {e}",
            "",
            "Most common causes:",
            "  1. NiMARE is installed in a DIFFERENT environment than the one running",
            "     this script. Check that 'which python' / sys.executable above matches",
            "     the environment where you ran 'pip install nimare'.",
            "  2. A NiMARE dependency is missing or broken (the error name above tells",
            "     you which module). Reinstall with:  pip install -U nimare nilearn nibabel",
            "",
            "To see the full traceback, re-run with:  python -X importtime precompute_neurosynth.py",
        ]
        _sys.exit("\n".join(msg))

    print("⬇️  Fetching / loading Neurosynth database (one-time, ~hundreds of MB)…")
    os.makedirs(args.cache, exist_ok=True)
    dsets = fetch_neurosynth(data_dir=args.cache, version="7", overwrite=False,
                             source="abstract", vocab="terms",
                             return_type="dataset")
    dset = dsets[0]
    print(f"Neurosynth dataset: {len(dset.ids)} studies")

    
    jobs = []  
    for sp in spaces:
        spdir = atlas_dir / sp
        if not spdir.is_dir():
            print(f"space dir not found: {spdir}")
            continue
        for author in sorted(os.listdir(spdir)):
            adir = spdir / author
            if not adir.is_dir():
                continue
            for f in sorted(adir.glob("*.nii.gz")):
                abbr = f.name.replace(".nii.gz", "")
                if only and abbr not in only:
                    continue
                nmf = names_dir / abbr
                if not nmf.exists():
                    
                    network_names = [abbr]
                else:
                    network_names = nmf.read_text().split()
                jobs.append((abbr, f, network_names))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Decoding {len(jobs)} atlases…")

    
    output = {"_meta": {
        "source": "Neurosynth v7 (terms/abstract) via NiMARE ROIAssociationDecoder",
        "statistic": "Pearson r between ROI mask and term meta-analytic map",
        "n_studies": int(len(dset.ids)),
        "top_n": args.top,
        "spaces": spaces,
    }}
    already_done = set()
    if args.resume and out_path.exists():
        try:
            with open(out_path, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
            
            if existing.get("_meta", {}).get("sample"):
                print("ℹ️ Existing JSON is the SAMPLE bundle — ignoring it and "
                      "starting a real run.")
            else:
                for k, v in existing.items():
                    if k == "_meta":
                        continue
                    output[k] = v
                    if v:  
                        already_done.add(k)
                print(f"↩️  Resume: {len(already_done)} atlases already in {out_path.name}; "
                      f"they will be skipped.")
        except Exception as e:
            print(f"Could not read existing JSON for resume ({e}); starting fresh.")

    def _save():
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(output, fh, indent=2)

    for ai, (abbr, apath, network_names) in enumerate(jobs, 1):
        if args.resume and abbr in already_done:
            print(f"  [{ai}/{len(jobs)}] {abbr} — already done, skipping.")
            continue
        print(f"  [{ai}/{len(jobs)}] {abbr} ({len(network_names)} networks)…")
        atlas_entry = {}
        for net_idx, net_name, mask_img in network_masks(apath, network_names):
            try:
                decoder = ROIAssociationDecoder(masker=mask_img)
                decoder.fit(dset)
                df = decoder.transform()           
            except Exception as e:
                print(f"       {net_name}: decode failed ({e})")
                continue
            
            rows = []
            for feat, r in df["r"].items():
                term = clean_feature_name(str(feat))
                if is_functional_term(term):
                    rows.append((term, float(r)))
            rows.sort(key=lambda x: x[1], reverse=True)
            atlas_entry[net_name] = [[t, round(r, 4)] for t, r in rows[: args.top]]
            print(f"      {net_name:14} top: "
                  + ", ".join(f"{t}({r:.2f})" for t, r in rows[:3]))
        output[abbr] = atlas_entry
        _save()   

    _save()
    print(f"\n Wrote {out_path}  ({out_path.stat().st_size/1024:.0f} KB)")
    print("   This file ships with the app; users need neither NiMARE nor the database.")


if __name__ == "__main__":
    main()
