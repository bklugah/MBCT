# MBCT command-line interface

`mbct_cli.py` runs the MBCT annotation pipeline without a graphical interface.
It performs the same analysis as the desktop application — network
correspondence against a reference atlas, followed by meta-analytic, molecular
and transcriptomic annotation of the matched networks — and is intended for
batch processing, scripted pipelines, headless servers and HPC jobs.

Because an entire analysis is expressed as one command, it can be pasted
directly into a methods section, which makes a result straightforward to
reproduce.

---

## Requirements

The CLI needs the same Python environment as the desktop application, minus the
GUI toolkit. Install from the repository root:

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

It also needs the reference data described in [`README.md`](README.md) —
at minimum `cbig_network_correspondence_data/` for the correspondence
analysis, and `data/` for the annotation bundles. Anatomical labelling
additionally uses `white_matter_atlases/`.

Apply the one-time offline patch described in `README.md` before first use.

---

## Commands

### `analyze` — annotate brain maps

```bash
python mbct_cli.py analyze --input MAP --atlas CODE [options]
```

| Option | Default | Meaning |
|---|---|---|
| `--input` | *required* | A NIfTI file, or a glob such as `"maps/*.nii.gz"` |
| `--atlas` | *required* | Reference atlas code (see `atlases`) |
| `--data-type` | `Metric` | `Metric`, `Hard` or `Soft` — how the map is interpreted |
| `--threshold` | `[0, Inf]` | Supra-threshold range for `Metric` data |
| `--top` | `10` | Annotation terms reported per network |
| `--no-annotations` | off | Report correspondence only |
| `--format` | `csv` | `csv` or `json` |
| `--out` | stdout | Output directory |

Networks are reported in descending order of overlap, each with its overlap
statistic and spin-test p-value.

**Single map, results to screen**

```bash
python mbct_cli.py analyze --input contrast.nii.gz --atlas EG17
```

**Batch, written to a directory**

```bash
python mbct_cli.py analyze --input "derivatives/*_zstat.nii.gz" \
    --atlas EG17 --out results/ --format csv
```

Every input is processed independently; a failure on one map is reported and
the run continues. The exit status is non-zero only if nothing succeeded.

**Machine-readable output**

```bash
python mbct_cli.py analyze --input map.nii.gz --atlas EG17 --format json
```

JSON output carries a `_provenance` block recording the tool version,
timestamp, atlas, data type and threshold. CSV output carries the same block as
a leading comment line, so a results file always records how it was produced.

---

### `atlases` — list reference atlases

```bash
python mbct_cli.py atlases
python mbct_cli.py atlases --space FSLMNI2mm
```

Prints the atlas codes available in each stereotaxic space, grouped by the
research group that produced them. Use a listed code with `--atlas`.

---

### `label` — anatomy at a coordinate

```bash
python mbct_cli.py label --coord 28 -8 8
python mbct_cli.py label --coord 28 -8 8 --format json
```

Reports the Harvard–Oxford gray-matter region and Brodmann area, the JHU-ICBM
white-matter region and tract, and the probabilistic tract assignments at an
MNI coordinate.

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Usage or input error (bad arguments, no matching files) |
| `2` | Analysis failure (engine unavailable, no results produced) |

Suitable for use in shell pipelines and job schedulers:

```bash
if python mbct_cli.py analyze --input map.nii.gz --atlas EG17 --out out/; then
    echo "annotation complete"
fi
```

---

## A note on the annotation bundles

The molecular, transcriptomic and meta-analytic annotations are read from
precomputed JSON bundles. The repository ships **placeholder** bundles so the
software runs before the expensive precomputation has been performed.

If a placeholder bundle is loaded, the CLI prints a warning and marks the
affected columns `SAMPLE`:

```
WARNING: neurotransmitter_mapping.json contains SAMPLE placeholder values,
not real results. neurotransmitter columns are marked 'SAMPLE' and must not be
reported as findings. Regenerate with precompute_neurotransmitter.py.
```

**Values marked `SAMPLE` are placeholders and must not be reported.** Generate
real bundles with the `precompute_*.py` scripts, which require the heavier
reference stack (NiMARE, neuromaps, abagen, BrainSMASH).

Correspondence results — the overlap statistics and spin-test p-values — are
computed live and are never placeholders.

---

## Reproducibility

For a methods section, record the exact command and the tool version:

```bash
python mbct_cli.py --version
python mbct_cli.py analyze --input sub-01_zstat.nii.gz --atlas EG17 \
    --data-type Metric --threshold "[0, Inf]" --out results/
```

The provenance block written into each results file captures the same
information, so an output can be traced back to the run that produced it.
