#!/usr/bin/env python3
"""
mbct_cli.py — command-line interface to the MBCT annotation pipeline.

Runs exactly the analysis the desktop application performs, without a GUI:
network correspondence against a reference atlas, followed by the meta-analytic,
molecular and transcriptomic annotations of the matched networks.

Designed for batch processing, scripted pipelines and headless/HPC use, and to
make an analysis reproducible from a single citable command.

Examples
--------
List the atlases available in a given space:

    python mbct_cli.py atlases --space FSLMNI2mm

Annotate one map:

    python mbct_cli.py analyze --input map.nii.gz --atlas EG17 \\
        --out results/

Batch-annotate a directory of maps:

    python mbct_cli.py analyze --input "maps/*.nii.gz" --atlas EG17 \\
        --out results/ --format csv

Look up the anatomy at a coordinate:

    python mbct_cli.py label --coord 28 -8 8

Exit codes:  0 success · 1 usage/input error · 2 analysis failure
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

__version__ = "1.0.0"

# Keep matplotlib headless — the CLI must run without a display.
os.environ.setdefault("MPLBACKEND", "Agg")


# ---------------------------------------------------------------------------
# small output helpers
# ---------------------------------------------------------------------------
def info(msg):
    print(msg, file=sys.stderr)


def warn(msg):
    print(f"WARNING: {msg}", file=sys.stderr)


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# annotation bundles
# ---------------------------------------------------------------------------
def _bundle_path(name):
    """Locate a precomputed annotation bundle."""
    cands = []
    try:
        from paths import resource_dir, user_data_dir
        for base in (resource_dir(), user_data_dir()):
            cands += [Path(base) / "data" / name, Path(base) / name]
    except Exception:
        pass
    here = Path(__file__).resolve().parent
    cands += [here / "data" / name, here / name]
    for c in cands:
        if c.exists():
            return c
    return None


def load_bundle(name):
    """Load a bundle, returning (data, is_sample). Never fabricates values."""
    p = _bundle_path(name)
    if p is None:
        return None, False
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        warn(f"could not read {name}: {e}")
        return None, False

    # Detect the shipped placeholder bundles so we never present them as results.
    is_sample = False
    meta = data.get("_meta", {}) if isinstance(data, dict) else {}
    if isinstance(meta, dict) and meta.get("sample"):
        is_sample = True
    else:
        for k, v in (data.items() if isinstance(data, dict) else []):
            if k != "_meta" and isinstance(v, dict) and v.get("sample"):
                is_sample = True
            break
    return data, is_sample


def annotations_for(bundle, atlas, network):
    """Return the annotation entry for one network, or None."""
    if not bundle:
        return None
    entry = bundle.get(atlas)
    if not isinstance(entry, dict):
        return None
    for key in (network, str(network)):
        if key in entry:
            return entry[key]
    nets = entry.get("networks")
    if isinstance(nets, dict):
        return nets.get(str(network))
    return None


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_atlases(args):
    """List reference atlases available for a space."""
    try:
        from nct_application.cbig_config import CBIGConfig
    except Exception as e:
        die(f"could not import the analysis engine: {e}", 2)

    atlas_dir = CBIGConfig.get_atlas_dir()
    if not atlas_dir:
        die("no atlas directory found. Install the reference data "
            "(see BUILD.md) or set it in the desktop application.", 2)

    root = Path(atlas_dir) / "atlases"
    if not root.is_dir():
        die(f"atlas folder not found under {atlas_dir}", 2)

    spaces = sorted(p.name for p in root.iterdir() if p.is_dir())
    if args.space:
        if args.space not in spaces:
            die(f"unknown space '{args.space}'. Available: {', '.join(spaces)}")
        spaces = [args.space]

    for sp in spaces:
        print(f"\n{sp}")
        for group in sorted((root / sp).iterdir()):
            if not group.is_dir():
                continue
            codes = sorted(f.name.split(".")[0]
                           for f in group.glob("*.nii*"))
            if codes:
                print(f"  {group.name:<14} {', '.join(codes)}")
    return 0


def cmd_label(args):
    """Report the anatomical labels at an MNI coordinate."""
    x, y, z = args.coord
    out = {"x": x, "y": y, "z": z}

    try:
        import anatomy_lookup as anat
        gm = anat.label_at_mni(x, y, z) or {}
        out["gray_matter"] = gm.get("region", "—")
        out["brodmann"] = gm.get("brodmann", "—")
    except Exception as e:
        warn(f"gray-matter lookup unavailable: {e}")

    try:
        import whitematter_lookup as wml
        wm = wml.wm_label_at_mni(x, y, z) or {}
        out["white_matter_region"] = wm.get("region", "—")
        out["white_matter_tract"] = wm.get("tract", "—")
        probs = wml.wm_tract_probs_at_mni(x, y, z, top=3)
        out["tract_probabilities"] = [
            {"tract": n, "percent": p} for n, p in probs]
    except Exception as e:
        warn(f"white-matter lookup unavailable: {e}")

    if args.format == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"MNI ({x}, {y}, {z})")
        print(f"  Gray matter    : {out.get('gray_matter', '—')}"
              f"  [{out.get('brodmann', '—')}]")
        print(f"  White matter   : {out.get('white_matter_region', '—')}")
        if out.get("tract_probabilities"):
            for t in out["tract_probabilities"]:
                print(f"    {t['tract']} ({t['percent']:.0f}%)")
    return 0


def _format_annotation(ann, top):
    """Render one network's annotation entry as a compact string.

    Bundles store a list of records per network:
        neurosynth        ['memory', 0.61]              -> term (r)
        neurotransmitter  ['5HT1a', 0.31, 0.018]        -> system (r, p=...)
        transcriptomics   ['DRD2 (dopamine)', r, p]
    Dict-shaped records are also accepted so the format can evolve.
    """
    if isinstance(ann, dict):
        ann = (ann.get("terms") or ann.get("top")
               or ann.get("items") or ann.get("values") or [])
    if not isinstance(ann, list):
        return str(ann)

    out = []
    for rec in ann[:top]:
        if isinstance(rec, dict):
            name = rec.get("name") or rec.get("term") or rec.get("gene") or "?"
            r = rec.get("r", rec.get("value"))
            p = rec.get("p", rec.get("p_spin"))
        elif isinstance(rec, (list, tuple)):
            name = rec[0] if rec else "?"
            r = rec[1] if len(rec) > 1 else None
            p = rec[2] if len(rec) > 2 else None
        else:
            out.append(str(rec)); continue

        try:
            part = f"{name} ({float(r):+.2f}" if r is not None else f"{name}"
        except (TypeError, ValueError):
            out.append(str(name)); continue
        if r is not None:
            try:
                part += f", p={float(p):.3g})" if p is not None else ")"
            except (TypeError, ValueError):
                part += ")"
        out.append(part)
    return "; ".join(out)


def _analyze_one(path, args, bundles):
    """Run the pipeline on a single input map. Returns a result dict."""
    from nct_application.application import NCTApplication

    info(f"→ {Path(path).name}")
    app = NCTApplication()
    app.set_input_file(str(path))

    data_config = {
        "Data_Name": Path(path).stem.replace(".nii", ""),
        "Data_Type": args.data_type,
        "Data_Threshold": args.threshold,
    }

    # Inject the config directly onto the CBIG analyser. This works regardless
    # of which application.py version is installed, because cbig_analysis.analyze()
    # reads this attribute as a fallback.
    try:
        if getattr(app, "cbig", None) is not None:
            app.cbig._ui_data_config = data_config
    except Exception as e:
        warn(f"could not inject data_config: {e}")

    # Call analyze_gray_matter, adapting to whichever signature is present.
    import inspect
    try:
        supports_cfg = "data_config" in inspect.signature(
            app.analyze_gray_matter).parameters
    except (ValueError, TypeError):
        supports_cfg = False

    if supports_cfg:
        res = app.analyze_gray_matter(selected_atlas=args.atlas,
                                      data_config=data_config)
    else:
        res = app.analyze_gray_matter(selected_atlas=args.atlas)
    if res.get("status") != "success":
        return {"input": str(path), "status": "error",
                "message": res.get("message", "analysis failed")}

    networks = res.get("networks", [])
    overlaps = list(res.get("overlaps", []))
    pvals = list(res.get("p_values", []))
    metric = res.get("overlap_metric", "overlap")

    rows = []
    for i, net in enumerate(networks):
        row = {
            "input": Path(path).name,
            "atlas": args.atlas,
            "network": net,
            metric: (round(float(overlaps[i]), 4)
                     if i < len(overlaps) else None),
            "p_value": (round(float(pvals[i]), 4)
                        if i < len(pvals) and pvals[i] is not None else None),
        }
        if not args.no_annotations:
            for label, (bundle, is_sample) in bundles.items():
                ann = annotations_for(bundle, args.atlas, net)
                if ann is None:
                    continue
                row[f"{label}_source"] = "SAMPLE" if is_sample else "precomputed"
                row[label] = _format_annotation(ann, args.top)
        rows.append(row)

    rows.sort(key=lambda r: (r.get(metric) is None, -(r.get(metric) or 0)))
    return {"input": str(path), "status": "success",
            "metric": metric, "rows": rows}


def cmd_analyze(args):
    """Run the correspondence analysis and annotation on one or more maps."""
    paths = sorted(glob.glob(args.input)) if any(
        c in args.input for c in "*?[") else [args.input]
    paths = [p for p in paths if Path(p).exists()]
    if not paths:
        die(f"no input files matched '{args.input}'")

    bundles = {}
    if not args.no_annotations:
        for label, fname in (("neurosynth", "neurosynth_decoding.json"),
                             ("neurotransmitter", "neurotransmitter_mapping.json"),
                             ("transcriptomics", "transcriptomics_mapping.json")):
            data, is_sample = load_bundle(fname)
            if data is None:
                warn(f"{fname} not found — {label} annotations omitted.")
            elif is_sample:
                warn(f"{fname} contains SAMPLE placeholder values, not real "
                     f"results. {label} columns are marked 'SAMPLE' and must "
                     f"not be reported as findings. Regenerate with "
                     f"precompute_{label}.py.")
            bundles[label] = (data, is_sample)

    outdir = Path(args.out) if args.out else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)

    all_rows, failures = [], []
    for p in paths:
        r = _analyze_one(p, args, bundles)
        if r["status"] != "success":
            failures.append(r)
            warn(f"{Path(p).name}: {r['message']}")
            continue
        all_rows.extend(r["rows"])

    if not all_rows:
        die("no successful analyses", 2)

    provenance = {
        "tool": "MBCT CLI",
        "version": __version__,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "atlas": args.atlas,
        "data_type": args.data_type,
        "threshold": args.threshold,
        "n_inputs": len(paths),
        "n_failed": len(failures),
    }

    if args.format == "json":
        payload = {"_provenance": provenance, "results": all_rows}
        text = json.dumps(payload, indent=2)
        if outdir:
            (outdir / "mbct_results.json").write_text(text, encoding="utf-8")
            info(f"wrote {outdir / 'mbct_results.json'}")
        else:
            print(text)
    else:
        cols = list(dict.fromkeys(k for r in all_rows for k in r))
        if outdir:
            fp = outdir / "mbct_results.csv"
            with open(fp, "w", newline="", encoding="utf-8") as fh:
                fh.write("# " + json.dumps(provenance) + "\n")
                w = csv.DictWriter(fh, fieldnames=cols)
                w.writeheader()
                w.writerows(all_rows)
            info(f"wrote {fp}")
        else:
            w = csv.DictWriter(sys.stdout, fieldnames=cols)
            w.writeheader()
            w.writerows(all_rows)

    info(f"done: {len(paths) - len(failures)}/{len(paths)} succeeded")
    return 2 if failures and not all_rows else 0


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        prog="mbct",
        description="MBCT — multimodal annotation of brain maps (CLI).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[-1])
    p.add_argument("--version", action="version",
                   version=f"MBCT CLI {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="annotate one or more brain maps")
    a.add_argument("--input", required=True,
                   help="NIfTI file, or a glob such as 'maps/*.nii.gz'")
    a.add_argument("--atlas", required=True,
                   help="reference atlas code (see the 'atlases' command)")
    a.add_argument("--data-type", default="Metric",
                   choices=["Metric", "Hard", "Soft"],
                   help="how the input map should be interpreted")
    a.add_argument("--threshold", default="[0, Inf]",
                   help="supra-threshold range for Metric data")
    a.add_argument("--top", type=int, default=10,
                   help="annotation terms to report per network")
    a.add_argument("--no-annotations", action="store_true",
                   help="report correspondence only")
    a.add_argument("--format", default="csv", choices=["csv", "json"])
    a.add_argument("--out", help="output directory (default: stdout)")
    a.set_defaults(func=cmd_analyze)

    l = sub.add_parser("atlases", help="list available reference atlases")
    l.add_argument("--space", help="restrict to one stereotaxic space")
    l.set_defaults(func=cmd_atlases)

    c = sub.add_parser("label", help="anatomical labels at an MNI coordinate")
    c.add_argument("--coord", nargs=3, type=float, required=True,
                   metavar=("X", "Y", "Z"))
    c.add_argument("--format", default="text", choices=["text", "json"])
    c.set_defaults(func=cmd_label)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        die("interrupted", 1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        die(str(e), 2)


if __name__ == "__main__":
    sys.exit(main())
