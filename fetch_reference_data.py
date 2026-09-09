#Klugah-Brown
"""
fetch_reference_data.py — obtain the reference datasets MBCT needs.

These datasets are third-party resources with their own distribution channels
and licences, so they are not stored in this repository. End users do not need
them: the released applications already bundle everything. This script is for
people building MBCT from source, or regenerating the annotation bundles.

    python fetch_reference_data.py            # report what is present/missing
    python fetch_reference_data.py --fetch    # download what can be automated

What can be automated:
    Neurosynth corpus       via NiMARE
    AHBA microarray         via abagen        (~4 GB, precomputation only)
    PET receptor maps       via neuromaps     (precomputation only)

What must be obtained manually (licence terms require you to accept them):
    CBIG network atlases    github.com/rubykong/cbig_network_correspondence_data
    JHU white-matter atlas  ships with FSL
    MNI152 templates        ships with FSL, or via nilearn

Nothing is overwritten: anything already present is reported and skipped.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"
if sys.platform.startswith("win"):
    try:                                   
        import colorama; colorama.just_fix_windows_console()
    except Exception:
        GREEN = RED = YELLOW = RESET = ""


def ok(msg):    print(f"  {GREEN}present{RESET}  {msg}")
def miss(msg):  print(f"  {RED}missing{RESET}  {msg}")
def note(msg):  print(f"  {YELLOW}note{RESET}     {msg}")


def check_corpus() -> bool:
    """Neurosynth v7 corpus: four files in neurosynth_cache/corpus/."""
    d = ROOT / "neurosynth_cache" / "corpus"
    needed = {
        "coordinates": "*version-7_coordinates.tsv.gz",
        "metadata":    "*version-7_metadata.tsv.gz",
        "features":    "*vocab-terms_source-abstract_type-tfidf_features.npz",
        "vocabulary":  "*vocab-terms_vocabulary.txt",
    }
    if not d.is_dir():
        miss(f"Neurosynth corpus — {d} does not exist")
        return False
    absent = [name for name, pat in needed.items() if not list(d.glob(pat))]
    if absent:
        miss(f"Neurosynth corpus — missing: {', '.join(absent)}")
        return False
    ok(f"Neurosynth corpus ({d})")
    return True


def check_cbig() -> bool:
    """CBIG reference atlases: four subdirectories must exist."""
    d = ROOT / "cbig_network_correspondence_data"
    required = ["atlases", "network_names", "atlas_config", "network_assignment"]
    if not d.is_dir():
        miss(f"CBIG atlases — {d} does not exist")
        return False
    absent = [sub for sub in required if not (d / sub).is_dir()]
    if absent:
        miss(f"CBIG atlases — missing subfolder(s): {', '.join(absent)}")
        return False
    
    n = len(list((d / "atlases").rglob("*.nii*")))
    if n == 0:
        miss(f"CBIG atlases — {d/'atlases'} contains no NIfTI files "
             f"(is atlases.zip still unextracted?)")
        return False
    ok(f"CBIG atlases ({n} atlas images)")
    return True


def check_whitematter() -> bool:
    """JHU-ICBM atlases used for white-matter labelling."""
    roots = [ROOT / "white_matter_atlases" / "whitematteratlasses" / "JHU-ICBM",
             ROOT / "white_matter_atlases" / "JHU-ICBM",
             ROOT / "white_matter_atlases"]
    for d in roots:
        if not d.is_dir():
            continue
        names = [p.name.lower() for p in d.iterdir() if p.is_file()]
        has_lab = any("labels" in n and "1mm" in n for n in names)
        has_trk = any("tracts" in n and "maxprob" in n for n in names)
        has_xml = any(n.endswith(".xml") for n in names)
        if has_lab and has_trk:
            ok(f"JHU white-matter atlases ({d})"
               + ("" if has_xml else "  — but no .xml label files found"))
            return True
    miss("JHU white-matter atlases — JHU-ICBM labels/tracts not found")
    return False


def check_templates() -> bool:
    d = ROOT / "mni_templates"
    if d.is_dir() and list(d.glob("*.nii*")):
        ok(f"MNI templates ({len(list(d.glob('*.nii*')))} files)")
        return True
    miss(f"MNI templates — no NIfTI files in {d}")
    return False


def check_bundles() -> bool:
    """Precomputed annotation bundles read by the application."""
    d = ROOT / "data"
    names = ["neurosynth_decoding.json", "neurotransmitter_mapping.json",
             "transcriptomics_mapping.json"]
    absent = [n for n in names if not (d / n).exists()]
    if absent:
        miss(f"annotation bundles — missing: {', '.join(absent)}")
        return False
    
    import json
    sampled = []
    for n in names:
        try:
            obj = json.load(open(d / n, encoding="utf-8"))
            meta = obj.get("_meta", {}) if isinstance(obj, dict) else {}
            if isinstance(meta, dict) and meta.get("sample"):
                sampled.append(n)
        except Exception:
            pass
    ok("annotation bundles (data/)")
    if sampled:
        note(f"these are SAMPLE placeholders, not real results: "
             f"{', '.join(sampled)} — regenerate with the precompute_*.py scripts")
    return True



def fetch_corpus() -> bool:
    """Download the Neurosynth v7 corpus with NiMARE."""
    dest = ROOT / "neurosynth_cache" / "corpus"
    dest.mkdir(parents=True, exist_ok=True)
    try:
        from nimare.extract import fetch_neurosynth
    except ImportError:
        print("    NiMARE is not installed — 'pip install nimare'")
        return False
    print(f"    downloading Neurosynth v7 into {dest} ...")
    try:
        fetch_neurosynth(data_dir=str(dest), version="7",
                         source="abstract", vocab="terms", overwrite=False)
        return check_corpus()
    except Exception as e:
        print(f"    download failed: {e}")
        print("    The Neurosynth files can also be downloaded by hand from")
        print("    https://github.com/neurosynth/neurosynth-data")
        return False


def fetch_ahba() -> bool:
    """Download the AHBA microarray data with abagen (precomputation only)."""
    try:
        import abagen
    except ImportError:
        print("    abagen is not installed — 'pip install abagen'")
        return False
    print("    downloading AHBA microarray data (~4 GB, six donors) ...")
    try:
        abagen.fetch_microarray(donors="all", verbose=1)
        return True
    except Exception as e:
        print(f"    download failed: {e}")
        return False


def fetch_neuromaps() -> bool:
    """Confirm neuromaps is available (maps download on first use)."""
    try:
        import neuromaps  # noqa: F401
    except ImportError:
        print("    neuromaps is not installed — 'pip install neuromaps'")
        return False
    print("    neuromaps is installed; PET maps download on first use.")
    return True


# ---------------------------------------------------------------------------
def manual_instructions():
    print("\nDatasets that must be obtained manually")
    print("-" * 70)
    print("""
CBIG network atlases  ->  cbig_network_correspondence_data/
    git clone https://github.com/rubykong/cbig_network_correspondence_data
    Extract atlases.zip inside it, so that atlases/<space>/<group>/*.nii.gz
    exist. Required subfolders: atlases, network_names, atlas_config,
    network_assignment.

JHU white-matter atlases  ->  white_matter_atlases/whitematteratlasses/JHU-ICBM/
    Ships with FSL, in $FSLDIR/data/atlases/. Copy:
        JHU-ICBM-labels-1mm.nii.gz
        JHU-ICBM-tracts-maxprob-thr25-1mm.nii.gz
        JHU-ICBM-tracts-prob-1mm.nii.gz
        JHU-labels.xml   JHU-tracts.xml
    FSL: https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Atlases

MNI152 templates  ->  mni_templates/
    Ships with FSL ($FSLDIR/data/standard/), or fetch via nilearn:
        from nilearn import datasets; datasets.load_mni152_template()
""")


def main():
    ap = argparse.ArgumentParser(
        description="Check for, and optionally download, MBCT's reference data.")
    ap.add_argument("--fetch", action="store_true",
                    help="download the datasets that can be automated")
    ap.add_argument("--ahba", action="store_true",
                    help="also download the AHBA microarray data (~4 GB)")
    args = ap.parse_args()

    print(f"MBCT reference data\nproject: {ROOT}\n")
    print("Required to run the application")
    print("-" * 70)
    results = {
        "CBIG atlases": check_cbig(),
        "MNI templates": check_templates(),
        "annotation bundles": check_bundles(),
        "JHU white matter": check_whitematter(),
        "Neurosynth corpus": check_corpus(),
    }

    if args.fetch:
        print("\nFetching what can be automated")
        print("-" * 70)
        if not results["Neurosynth corpus"]:
            results["Neurosynth corpus"] = fetch_corpus()
        fetch_neuromaps()
        if args.ahba:
            fetch_ahba()
        else:
            note("AHBA microarray not fetched — add --ahba if you intend to "
                 "regenerate the transcriptomics bundle (~4 GB)")

    missing = [k for k, v in results.items() if not v]
    print("\nSummary")
    print("-" * 70)
    if missing:
        print(f"  {len(missing)} dataset(s) still needed: {', '.join(missing)}")
        manual_instructions()
        return 1
    print(f"  {GREEN}all reference data present — MBCT can be built and run{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
