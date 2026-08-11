"""
Diagnostic: find which addWidget(None) triggers
'QLayout: Cannot add a null widget to QHBoxLayout'.

Run this INSTEAD of the normal app:
    python diagnose_null_widget.py

It monkey-patches QBoxLayout.addWidget so that whenever a None
(or non-QWidget) is passed, it prints a full Python traceback
pointing at the exact file and line in your code, then continues.
"""

import sys
import traceback
from PyQt6.QtWidgets import QApplication, QBoxLayout, QWidget

# --- install the probe BEFORE building any UI ---
_orig_addWidget = QBoxLayout.addWidget

def _patched_addWidget(self, w, *args, **kwargs):
    if w is None or not isinstance(w, QWidget):
        print("\n" + "=" * 70)
        print(f"NULL/INVALID widget passed to addWidget: {w!r}")
        print("Layout:", self)
        print("-" * 70)
        traceback.print_stack()      # shows YOUR code path to this call
        print("=" * 70 + "\n")
        return  # skip the bad add so Qt's own warning is suppressed
    return _orig_addWidget(self, w, *args, **kwargs)

QBoxLayout.addWidget = _patched_addWidget
# -------------------------------------------------

# Now launch the real application
import runpy
runpy.run_path("nct_desktop_app_IMPROVED.py", run_name="__main__")
