#Klugah-Brown 2026
"""
patch_abagen.py — make the installed abagen compatible with pandas >= 2.0.

abagen 0.1.x predates pandas 2.0, which removed several APIs it still uses.
This is a known upstream issue (rmarkello/abagen #225, #233). Rather than
downgrade pandas — which the rest of MBCT depends on — this script rewrites
the handful of incompatible calls in the installed package.

Every modified file is backed up alongside itself as <name>.bak, so the
changes can be reverted.

Run from the project root with the virtual environment active:

    python patch_abagen.py
"""

import re
import shutil
from pathlib import Path


def patch_file(path: Path) -> int:
    """Apply the pandas>=2.0 fixes to one file. Returns the number of changes."""
    src = original = path.read_text(encoding="utf-8")

    
    src = re.sub(r"\.set_axis\(([^()]*?),\s*inplace\s*=\s*False\s*\)",
                 r".set_axis(\1)", src)
    src = re.sub(r"\.set_axis\(([^()]*?),\s*inplace\s*=\s*True\s*\)",
                 r".set_axis(\1)", src)

    
    src = src.replace(".groupby(sid, axis=1).mean()",
                      ".T.groupby(sid).mean().T")
    src = re.sub(r"\.groupby\(([^()]*?),\s*axis=1\)\.mean\(\)",
                 r".T.groupby(\1).mean().T", src)

   
    _df_like = (r"(?:df|frame|micro|microarray|expression|expr|annot|annotation|"
                r"probes|pacall|ontology|counts|data|out|res|result|samples|"
                r"[A-Za-z_]*_df|[A-Za-z_]*_frame)")
    src = re.sub(rf"\b({_df_like})\.append\((?!\s*\))([^()]*?)\)",
                 r"pd.concat([\1, \2])", src)

    if src == original:
        return 0

    
    if "pd.concat" in src and not re.search(r"^\s*import pandas as pd", src, re.M):
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                lines.insert(i, "import pandas as pd")
                break
        src = "\n".join(lines) + "\n"

    backup = Path(str(path) + ".bak")
    if not backup.exists():
        shutil.copy(path, backup)
    path.write_text(src, encoding="utf-8")
    return 1


def main():
    try:
        import abagen
    except ImportError:
        raise SystemExit("abagen is not installed in this environment.")

    root = Path(abagen.__file__).resolve().parent
    print(f"abagen package: {root}")

    changed = []
    for py in sorted(root.rglob("*.py")):
        if py.name.endswith(".bak"):
            continue
        try:
            if patch_file(py):
                changed.append(py.relative_to(root))
        except Exception as e:                       #
            print(f"  ! skipped {py.name}: {e}")

    if changed:
        print(f"\npatched {len(changed)} file(s):")
        for c in changed:
            print(f"   {c}")
    else:
        print("\nnothing to patch — abagen already looks pandas>=2.0 compatible.")

    
    leftovers = []
    for py in sorted(root.rglob("*.py")):
        if py.name.endswith(".bak"):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"inplace\s*=\s*(True|False)\s*\)", text) and "set_axis" in text:
            leftovers.append((py.name, "set_axis inplace"))
        if re.search(r"\.append\(", text) and "pd.concat" not in text:
            leftovers.append((py.name, "DataFrame.append"))
        if "axis=1)" in text and ".groupby(" in text and "axis=1).mean()" in text:
            leftovers.append((py.name, "groupby(axis=1)"))
    if leftovers:
        print("\npossible remaining issues (check if a new error appears):")
        for name, what in dict.fromkeys(leftovers):
            print(f"   {name}: {what}")

    print("\nBackups written as <file>.bak — restore by copying them back.")
    print("Now re-run:")
    print("   python precompute_transcriptomics.py --n-perm 1000 "
          "--cache C:\\Users\\pc\\abagen-data")


if __name__ == "__main__":
    main()
