"""Launch ColorLab Pro with pywebview (lightweight, no PySide6)."""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

from colorlab_pro.ui.app_pywebview import main

if __name__ == "__main__":
    sys.exit(main())
