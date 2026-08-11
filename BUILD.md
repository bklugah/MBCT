# Building the MBCT applications

Four editions are built from **one codebase**. Each has its own PyInstaller
spec that bundles only the data and dependencies that edition needs.

| Edition | Spec | Entry point | Contains |
|---|---|---|---|
| **MBCT** (full) | `MBCT.spec` | `nct_desktop_app_IMPROVED.py` | Everything |
| **MBCT Core** | `MBCT_Core.spec` | `mbct_core.py` | Home, Analysis, Results, Help (the manuscript edition) |
| **MBCT Brain Viewer** | `MBCT_BrainViewer.spec` | `mbct_brain_viewer.py` | Viewer, Connectivity, Map Tools |
| **MBCT Meta-Analysis Tool** | `MBCT_MetaAnalysis.spec` | `mbct_meta_analysis.py` | Term→Map, Coordinate→Terms, MACM |

## What each edition ships

| | heavy stack | CBIG atlases | JHU white matter | Neurosynth corpus | precomputed JSON |
|---|---|---|---|---|---|
| MBCT (full) | yes | yes | yes | yes | yes |
| MBCT Core | yes | yes | yes | — | yes |
| Brain Viewer | light | — | yes | — | — |
| Meta-Analysis | NiMARE | — | — | yes | — |

## Prerequisites

PyInstaller must run **on the target OS** — you cannot cross-compile a macOS
app from Windows or vice versa.

```bash
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

Install `cbig_network_correspondence` **first** if you hit dependency
conflicts, then the rest.

### One-time patch (required for offline use)

The `cbig_network_correspondence` package tries to `git pull` its reference
data at import time, which fails on a machine with no network. Replace its
`__init__.py` with the patched, offline-safe version:

```
copy cbig_init_patched.py venv\Lib\site-packages\cbig_network_correspondence\__init__.py
```

Verify it landed:

```
findstr /C:"Offline-safe" venv\Lib\site-packages\cbig_network_correspondence\__init__.py
```

## Building

Always clear both `build/` and `dist/` first — PyInstaller reuses cached
pieces, and a partially-deleted `dist/` produces a corrupted bundle.

```
taskkill /F /IM MBCT.exe          # Windows: make sure nothing is running
rmdir /s /q build
rmdir /s /q dist
pyinstaller --clean MBCT.spec --noconfirm
```

Repeat per edition:

```
pyinstaller --clean MBCT_Core.spec --noconfirm
pyinstaller --clean MBCT_BrainViewer.spec --noconfirm
pyinstaller --clean MBCT_MetaAnalysis.spec --noconfirm
```

Each writes to `dist/<Name>/`.

### Watch the build output

Every spec prints what it bundled:

```
[MBCT] assets: 8 files
[MBCT] cbig_network_correspondence_data: 4823 files
[MBCT] collect_all(vtk): 120 data, 45 bin, 380 submodules
[MBCT] TOTAL: ... data, ... bin, ... hiddenimports
```

A folder reporting **0 files**, or a package reporting **0 submodules**, means
it is missing from the project or the venv — fix that before shipping.

## Verifying a build

Before distributing, confirm the data actually landed:

```
dir dist\MBCT\_internal\cbig_network_correspondence_data\atlases\FSLMNI2mm\YeoLab
dir dist\MBCT\_internal\data
dir dist\MBCT\_internal\neurosynth_cache\corpus
```

Then run the executable **from a terminal** so console diagnostics are visible:

```
cd dist\MBCT
MBCT.exe
```

Look for `[atlas] ... FOUND`, `[wm] atlas dir: ...` and the three
`✅ Loaded ... bundle` lines.

### Test on a clean machine

This is the step that catches everything else. Copy the whole `dist/<Name>/`
folder to a computer that has never had Python or these libraries installed and
run it there. A build that works only on the development machine is usually
reading data from the developer's own paths or config files.

## Distributing

Ship the **entire `dist/<Name>/` folder** — the executable will not run without
the `_internal/` folder beside it. Either zip that folder, or wrap it:

* Windows — Inno Setup or NSIS
* macOS — the `.app` bundle produced by the spec, packaged into a `.dmg`
* Linux — AppImage or a tarball

Do **not** distribute `build/`; it is scratch space and can be deleted.
