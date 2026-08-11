"""
patch_abagen2.py — fix the remaining pandas>=2.0 incompatibility in abagen's
samples_.groupby_index().

pandas 2.0 removed DataFrame.append(). abagen still calls it in a multi-line
chained expression, which the first patch script's single-line rules did not
match:

    ...
        .aggregate(metric)
        .append(labels)          <-- here
    ...

pandas kept the identical behaviour as the private method ``_append``, so the
minimal, behaviour-preserving fix is to call that instead. This is what pandas
itself recommends in the error message ("Did you mean: '_append'?").

Run from the project root with the virtual environment active:

    python patch_abagen2.py
"""

import re
import shutil
from pathlib import Path


def main():
    try:
        import abagen
    except ImportError:
        raise SystemExit("abagen is not installed in this environment.")

    root = Path(abagen.__file__).resolve().parent
    print(f"abagen package: {root}")

    total = 0
    for path in sorted(root.rglob("*.py")):
        if path.name.endswith(".bak"):
            continue
        src = original = path.read_text(encoding="utf-8")

        # Match `.append(` that is chained on its own line (leading dot),
        # which is the DataFrame/Series form abagen uses. A list append is
        # never written this way, so lists are unaffected.
        src = re.sub(r"(\n\s*)\.append\(", r"\1._append(", src)

        if src != original:
            backup = Path(str(path) + ".bak2")
            if not backup.exists():
                shutil.copy(path, backup)
            path.write_text(src, encoding="utf-8")
            n = len(re.findall(r"\n\s*\._append\(", src))
            print(f"  patched {path.relative_to(root)}  ({n} call(s))")
            total += 1

    if total == 0:
        print("\nNothing matched — the chained .append() may already be fixed.")
    else:
        print(f"\npatched {total} file(s); backups saved as *.bak2")

    # Show any remaining bare `.append(` on a chained line, for visibility.
    remaining = []
    for path in sorted(root.rglob("*.py")):
        if path.name.endswith((".bak", ".bak2")):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            if re.match(r"\s*\.append\(", line):
                remaining.append(f"{path.relative_to(root)}:{i}")
    if remaining:
        print("\nstill present (chained .append):")
        for r in remaining:
            print(f"   {r}")

    print("\nNow re-run:")
    print("   python precompute_transcriptomics.py --n-perm 1000 "
          "--cache C:\\Users\\pc\\abagen-data")


if __name__ == "__main__":
    main()
