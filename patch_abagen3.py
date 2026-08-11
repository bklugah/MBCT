"""
patch_abagen3.py — fix the remaining DataFrame.append() calls in abagen.

pandas 2.0 removed DataFrame.append(); pandas kept identical behaviour as the
private ``_append``, which is what its own error message suggests. Only the
five genuine DataFrame/Series calls are rewritten:

    allen.py:505   microarray[subj].append(exp)
    allen.py:506   labels.append(lab)
    allen.py:544   microarray[subj].append(exp)
    allen.py:813   exp.append(pd.DataFrame(...))
    utils.py:180   info.append(...)

Ordinary list appends (data.append, labs.append, errors.append, ...) and
numpy calls (np.append) are deliberately left alone — rewriting those would
break the package.

Backups are written as <file>.bak3.

Run from the project root with the virtual environment active:

    python patch_abagen3.py
"""

import re
import shutil
from pathlib import Path

# (filename, exact receiver expression) pairs that are DataFrames/Series.
TARGETS = {
    "allen.py": [
        "microarray[subj]",
        "labels",
        "exp",
    ],
    "utils.py": [
        "info",
    ],
}

# Never touch these, whatever else matches.
NEVER = ("np.append", "data.append", "labs.append", "errors.append",
         "files_.append", "normexp.append", "hemispheres.append",
         "imgs.append", "triangles.append", "adata.append",
         "labeltable.labels.append", "inds.append")


def patch(path: Path, receivers) -> int:
    src = original = path.read_text(encoding="utf-8")
    changed = 0

    for recv in receivers:
        # Escape regex metacharacters in receivers like microarray[subj]
        r = re.escape(recv)
        # Only rewrite `<recv>.append(` — not np.append, not other receivers.
        pattern = re.compile(rf"(?<![\w.]){r}\.append\(")
        new, n = pattern.subn(f"{recv}._append(", src)
        if n:
            src = new
            changed += n

    # Safety: make sure we didn't touch anything on the never-list.
    for bad in NEVER:
        if f"{bad.split('.')[0]}._append(" in src and bad not in original:
            print(f"  ! refusing to write {path.name}: would have altered {bad}")
            return 0

    if src != original:
        backup = Path(str(path) + ".bak3")
        if not backup.exists():
            shutil.copy(path, backup)
        path.write_text(src, encoding="utf-8")
    return changed


def main():
    try:
        import abagen
    except ImportError:
        raise SystemExit("abagen is not installed in this environment.")

    root = Path(abagen.__file__).resolve().parent
    print(f"abagen package: {root}\n")

    total = 0
    for fname, receivers in TARGETS.items():
        path = root / fname
        if not path.exists():
            print(f"  {fname}: not found, skipped")
            continue
        n = patch(path, receivers)
        total += n
        print(f"  {fname}: {n} DataFrame append(s) rewritten")

    print(f"\ntotal rewritten: {total}")

    # Report what remains, so nothing is fixed silently or missed.
    print("\nremaining '.append(' occurrences (these should all be lists/numpy):")
    for p in sorted(root.rglob("*.py")):
        if p.name.endswith((".bak", ".bak2", ".bak3")) or "tests" in p.parts:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8",
                                             errors="ignore").splitlines(), 1):
            if ".append(" in line and "._append(" not in line:
                print(f"   {p.relative_to(root)}:{i}: {line.strip()[:80]}")

    print("\nBackups saved as *.bak3.")
    print("Now re-run:")
    print("   python precompute_transcriptomics.py --n-perm 1000 "
          "--cache C:\\Users\\pc\\abagen-data --use-atlas-info")


if __name__ == "__main__":
    main()
