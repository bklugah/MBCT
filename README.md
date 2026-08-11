# MBCT — Multimodal Brain Network Characterization Tool

**MBCT** takes a volumetric brain map — a group activation contrast, an
independent component, a lesion or ROI mask, a data-driven cluster — and
returns a reproducible, multi-scale annotation of what that location *means*:

1. **Functional network correspondence** — spatial overlap with canonical
   network parcellations, via the Network Correspondence Toolbox, with
   Dice/Jaccard overlap and spin-test significance.
2. **Meta-analytic cognitive decoding** — the cognitive terms most consistently
   reported at those coordinates across the Neurosynth database.
3. **Molecular association** — correspondence with PET-derived neurotransmitter
   receptor and transporter density maps (19 receptors, nine systems).
4. **Transcriptomic association** — correspondence with receptor-gene expression
   from the Allen Human Brain Atlas.

All cross-modal associations are evaluated against spatial-autocorrelation-
preserving null models, and receptor density is paired with the homologous
receptor gene to give a cross-modal convergence read-out.

> **Status.** The software is functional and installable. The manuscript
> describing it is in preparation; quantitative results and figures are being
> generated. Treat outputs as research-grade and validate against your own
> expectations.

---

## Editions

MBCT is distributed as four applications built from this single codebase.
Download the one that fits your need from the [Releases](../../releases) page.

| Edition | What it does |
|---|---|
| **MBCT** | Everything, in one application |
| **MBCT Core** | The annotation pipeline: Analysis + Results |
| **MBCT Brain Viewer** | Map viewer, connectivity view, map-preparation tools |
| **MBCT Meta-Analysis Tool** | Term→Map, Coordinate→Terms, coactivation (MACM) |

Each is a self-contained folder — no Python installation required. Download,
unzip, and run the executable inside.

### MBCT Core

The annotation pipeline described in the manuscript.

* Load a NIfTI map; the stereotaxic space is detected automatically.
* Choose a reference atlas (space → author → atlas) and run the correspondence
  analysis with a configurable number of spin permutations.
* Inspect ranked networks with their overlap statistics and spin-test p-values.
* Read each network's cognitive, molecular and transcriptomic annotations.
* Click anywhere on the map for live anatomical labelling — Harvard–Oxford
  gray-matter regions with Brodmann areas, and JHU-ICBM white-matter regions
  and tracts with tract probabilities.
* Export tables (CSV), maps (NIfTI) and figures (PNG/TIF/JPEG); save and reload
  complete sessions.

### MBCT Brain Viewer

* Single, triplanar and glass-brain views; interactive rotatable 3-D surface.
* Draggable crosshair with linked triplanar navigation and direct MNI entry.
* Live gray- and white-matter anatomical labelling at the cursor.
* Interactive threshold and cluster-extent controls.
* **Connectivity view** — visualise an already-computed seed-based FC map as a
  connectome: cluster peaks become anatomically labelled nodes, shown as an
  overview glass brain plus one panel per connection.
* **Map tools** — resample to a standard grid, threshold and binarize, build
  ROIs and extract signal, combine maps arithmetically or logically.

### MBCT Meta-Analysis Tool

* **Term → Map** — generate a Neurosynth meta-analytic map for any term.
* **Coordinate → Terms** — decode an MNI coordinate to associated terms, with
  Benjamini–Hochberg FDR correction and full CSV export.
* **MACM** — meta-analytic coactivation mapping for a seed coordinate.

Reads a local Neurosynth corpus; no internet connection required at run time.

---

## Command-line interface

The same pipeline is available without a GUI, for batch processing, scripted workflows and headless or HPC use:

```bash
python mbct_cli.py atlases --space FSLMNI2mm
python mbct_cli.py analyze --input map.nii.gz --atlas EG17 --out results/
python mbct_cli.py label --coord 28 -8 8
```

Results are written as CSV or JSON with a provenance record of the tool version, atlas, data type, threshold and timestamp, so an analysis can be reported as a single reproducible command. See [`CLI.md`](CLI.md).

## Installation

Download an edition from [Releases](../../releases), unzip, and run the
executable. Keep the whole folder together — the executable needs the files
alongside it.

* **Windows** — run the `.exe`.
* **macOS** — open the `.app`. Unsigned builds may need right-click → *Open*
  the first time.
* **Linux** — run the executable, or the AppImage if provided.

---

## Building from source

See [`BUILD.md`](BUILD.md) for full instructions.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
pyinstaller --clean MBCT_Core.spec --noconfirm
```

PyInstaller must run **on the target operating system**; builds cannot be
cross-compiled.

### Reference data

Reference datasets are **not** included in this repository — they are
third-party resources with their own distribution channels, and several files
exceed GitHub's size limits. To build from source you need:

| Folder | Contents | Source |
|---|---|---|
| `cbig_network_correspondence_data/` | Reference network atlases | Network Correspondence Toolbox (CBIG) |
| `white_matter_atlases/` | JHU-ICBM labels, tracts, probabilistic atlas | FSL |
| `mni_templates/` | MNI152 underlay templates | standard MNI templates |
| `neurosynth_cache/corpus/` | Neurosynth v7 coordinates, metadata, vocabulary | Neurosynth |
| `data/` | Precomputed annotation bundles | generated by `precompute_*.py` |

The released binaries bundle all of these, so end users need none of it.

To check what you have and download what can be automated:

```bash
python fetch_reference_data.py            # report status
python fetch_reference_data.py --fetch    # download what it can
```

It prints, for each dataset, whether it is present and — for the ones that must be obtained manually (CBIG, JHU, MNI) — exactly which files to copy and where from.

### One-time patch for offline use

The `cbig_network_correspondence` package attempts to `git pull` its reference
data when imported, which fails on a machine without network access. Replace
its `__init__.py` with the offline-safe version in this repository:

```bash
cp cbig_init_patched.py venv/lib/python3.X/site-packages/cbig_network_correspondence/__init__.py
```

---

## How the annotations are produced

The three annotation modules with heavy dependencies (NiMARE, neuromaps,
abagen) are executed **once, at development time** by the `precompute_*.py`
scripts, which write compact JSON bundles. The shipped application reads those
bundles, so users get instant annotation without installing large reference
stacks. The meta-analysis tools run live against a local Neurosynth corpus.

---

## Citing

MBCT integrates the following resources; it does not re-implement them. Please
cite them alongside MBCT.

* **Network correspondence** — Kong, R., et al. (2025). A network
  correspondence toolbox for quantitative evaluation of novel neuroimaging
  results. *Nature Communications*, 16, 2930.
* **Meta-analytic decoding** — Yarkoni, T., et al. (2011). *Nature Methods*,
  8(8), 665–670. · Salo, T., et al. (2023). NiMARE. *Aperture Neuro*, 3, 1–32.
* **Receptor maps** — Hansen, J. Y., et al. (2022). *Nature Neuroscience*,
  25(11), 1569–1581. · Markello, R. D., et al. (2022). neuromaps.
  *Nature Methods*, 19(11), 1472–1479.
* **Transcriptomics** — Hawrylycz, M. J., et al. (2012). *Nature*, 489,
  391–399. · Markello, R. D., et al. (2021). abagen. *eLife*, 10, e72129.
* **Spatial nulls** — Burt, J. B., et al. (2020). *NeuroImage*, 220, 117038. ·
  Alexander-Bloch, A. F., et al. (2018). *NeuroImage*, 178, 540–551.

A citation for MBCT itself will be added when the manuscript is available.

---

## Author

**Benjamin Klugah-Brown** — bklugah@gmail.com

## Licence

GNU General Public License v3.0 — see [`LICENSE`](LICENSE).

In short: you may use, study, modify and redistribute this software, but any
distributed work derived from it must also be released under the GPL-3.0 with
its source made available. This keeps MBCT and everything built on it open.

Third-party reference datasets and toolboxes retain their own licences and
terms of use.
