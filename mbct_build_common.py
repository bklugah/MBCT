#Klugah-Brown
"""
mbct_build_common.py — shared PyInstaller helpers for every MBCT edition.

Imported by the .spec files so that the bundling rules live in ONE place:

    MBCT.spec                  full edition   (all tabs)
    MBCT_Core.spec             core edition   (Analysis + Results; the paper build)
    MBCT_BrainViewer.spec      standalone viewer + map tools + connectivity
    MBCT_MetaAnalysis.spec     standalone meta-analysis tools

Key lessons baked in here (each cost a debugging cycle):
  * data directories must be enumerated FILE BY FILE — handing PyInstaller a
    top-level folder recreates the tree but silently drops nested files;
  * a bundled `.git` folder makes the CBIG toolbox attempt a `git pull` at
    import time, which fails on a machine with no network — so VCS metadata is
    always excluded;
  * several packages (vtk, pymare, regfusion, sympy) load data or submodules
    dynamically and need collect_all plus explicit hidden imports.
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

EXCLUDE_PARTS = {'.git', '.github', '__pycache__', '.pytest_cache', '.idea'}


# ---------------------------------------------------------------- data files
def add_dir(datas, root, name, dest=None, label=None):
    """Recursively add every file under `root/name` to `datas`."""
    src = Path(root) / name
    if not src.exists():
        print(f"[MBCT] add_dir: '{name}' not found — skipped")
        return 0
    dest_base = dest or name
    n = 0
    for f in src.rglob('*'):
        if any(part in EXCLUDE_PARTS for part in f.parts):
            continue
        if f.is_file():
            rel = f.parent.relative_to(src)
            target = dest_base if str(rel) == '.' else os.path.join(dest_base, str(rel))
            datas.append((str(f), target))
            n += 1
    print(f"[MBCT] add_dir('{label or name}'): {n} files")
    return n


def add_json_bundles(datas, root, names):
    """Ship the precomputed annotation bundles from data/ into data/."""
    for j in names:
        src_data = Path(root) / 'data' / j
        src_root = Path(root) / j
        if src_data.exists():
            datas.append((str(src_data), 'data'))
            print(f"[MBCT] bundling REAL {j} from data/")
        elif src_root.exists():
            datas.append((str(src_root), 'data'))
            print(f"[MBCT] bundling {j} from project root "
                  f"(WARNING: not in data/ — may be a SAMPLE file)")
        else:
            print(f"[MBCT] WARNING: {j} not found — that panel will show a hint")



def collect_packages(pkgs):
    """collect_all() over a list of packages, reporting what each yielded."""
    datas, binaries, hidden = [], [], []
    for pkg in pkgs:
        try:
            d, b, h = collect_all(pkg)
            datas += d; binaries += b; hidden += h
            print(f"[MBCT] collect_all({pkg}): {len(d)} data, {len(b)} bin, "
                  f"{len(h)} submodules")
        except Exception as e:
            print(f"[MBCT] collect_all({pkg}) skipped: {e}")
    return datas, binaries, hidden


def collect_pkg_tree(datas, pkgname):
    """Copy every NON-python file from a package (catches data collect_all misses)."""
    import importlib.util
    try:
        spec = importlib.util.find_spec(pkgname)
        if not spec or not spec.origin:
            print(f"[MBCT] {pkgname}: not importable — skipped")
            return
        root = Path(spec.origin).parent
        n = 0
        for f in root.rglob('*'):
            if any(part in EXCLUDE_PARTS for part in f.parts):
                continue
            if f.is_file() and f.suffix.lower() not in ('.py', '.pyc', '.pyo'):
                rel = f.parent.relative_to(root.parent)
                datas.append((str(f), str(rel)))
                n += 1
        print(f"[MBCT] collect_pkg_tree({pkgname}): {n} data files (VCS excluded)")
    except Exception as e:
        print(f"[MBCT] collect_pkg_tree({pkgname}) failed: {e}")



DYNAMIC_PKGS_FULL = ['vtk', 'vtkmodules', 'nimare', 'pymare', 'regfusion',
                     'sympy', 'nilearn', 'nibabel', 'sklearn', 'scipy',
                     'statsmodels', 'pandas', 'matplotlib',
                     'cbig_network_correspondence']
DYNAMIC_PKGS_META = ['nimare', 'pymare', 'sympy', 'nilearn', 'nibabel',
                     'sklearn', 'scipy', 'statsmodels', 'pandas', 'matplotlib']
DYNAMIC_PKGS_LIGHT = ['nilearn', 'nibabel', 'scipy', 'matplotlib', 'pandas']


SYMPY_HIDDEN = ['sympy.stats', 'sympy.stats.rv', 'sympy.stats.crv',
                'sympy.stats.drv', 'sympy.stats.frv']
VTK_HIDDEN = ['vtk.numpy_interface', 'vtk.numpy_interface.dataset_adapter',
              'vtk.numpy_interface.algorithms', 'vtkmodules.numpy_interface',
              'vtkmodules.numpy_interface.dataset_adapter',
              'vtkmodules.util.numpy_support', 'vtkmodules.all']

EXCLUDES = ['tkinter', 'PyQt5', 'PySide2', 'PySide6']


def icon_for(root):
    """Platform-appropriate icon path, or None if not present."""
    import sys
    a = Path(root) / 'assets'
    if sys.platform.startswith('win'):
        p = a / 'logo2_icon.ico'
    elif sys.platform == 'darwin':
        p = a / 'logo2_icon.icns'
    else:
        return None
    return str(p) if p.exists() else None
