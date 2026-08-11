# -*- mode: python ; coding: utf-8 -*-
"""
MBCT_MetaAnalysis.spec — standalone MBCT Meta-Analysis Tool.

Contains only the Neurosynth meta-analysis tools:
    Term → Map, Coordinate → Terms (FDR-corrected), and MACM coactivation.

Ships the local Neurosynth v7 corpus so the tool works offline. Excludes the
CBIG toolbox, the network atlases and VTK, which this edition never uses.

Build on the TARGET OS:
    pyinstaller MBCT_MetaAnalysis.spec --noconfirm
Output: dist/MBCT-MetaAnalysis/
"""

import os, sys
from pathlib import Path

# ===================== inlined build helpers =====================
# (kept inside the spec so no extra module needs to be importable)

from PyInstaller.utils.hooks import collect_all

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


# ------------------------------------------------------------- package deps
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


# Packages whose data/submodules PyInstaller cannot infer statically.
DYNAMIC_PKGS_FULL = ['vtk', 'vtkmodules', 'nimare', 'pymare', 'regfusion',
                     'sympy', 'nilearn', 'nibabel', 'sklearn', 'scipy',
                     'statsmodels', 'pandas', 'matplotlib',
                     'cbig_network_correspondence']
DYNAMIC_PKGS_META = ['nimare', 'pymare', 'sympy', 'nilearn', 'nibabel',
                     'sklearn', 'scipy', 'statsmodels', 'pandas', 'matplotlib']
DYNAMIC_PKGS_LIGHT = ['nilearn', 'nibabel', 'scipy', 'matplotlib', 'pandas']

# sympy.stats is reached only through exec("from sympy.stats import *") inside
# pymare, so PyInstaller's static analysis cannot see it.
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
# =================== end inlined build helpers ===================

ROOT = Path(os.getcwd())
block_cipher = None

print("=" * 62)
print("Building MBCT Meta-Analysis Tool (standalone)")
print("=" * 62)

datas = []
add_dir(datas, ROOT, 'assets')
# The Neurosynth v7 corpus (~16 MB) — makes the tool work with no download.
add_dir(datas, ROOT, os.path.join('neurosynth_cache', 'corpus'),
        dest=os.path.join('neurosynth_cache', 'corpus'),
        label='neurosynth corpus')

pdatas, binaries, hiddenimports = collect_packages(DYNAMIC_PKGS_META)
datas += pdatas
# pymare ships expressions.json; nimare ships several data files.
for pkg in ('pymare', 'nimare'):
    collect_pkg_tree(datas, pkg)
hiddenimports += SYMPY_HIDDEN
print(f"[MBCT] TOTAL: {len(datas)} data, {len(binaries)} bin, "
      f"{len(hiddenimports)} hiddenimports")

META_EXCLUDES = EXCLUDES + ['vtk', 'vtkmodules', 'regfusion',
                            'cbig_network_correspondence', 'neuromaps',
                            'abagen', 'brainsmash']

a = Analysis(
    ['mbct_meta_analysis.py'],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=META_EXCLUDES,
    win_no_prefer_redirects=False, win_private_assemblies=False,
    cipher=block_cipher, noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='MBCT-MetaAnalysis',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=icon_for(ROOT),
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas,
               strip=False, upx=False, upx_exclude=[], name='MBCT-MetaAnalysis')

if sys.platform == 'darwin':
    app = BUNDLE(coll, name='MBCT Meta-Analysis Tool.app', icon=icon_for(ROOT),
                 bundle_identifier='com.bklugah.mbct.metaanalysis')
