"""Launch the ColorLab Pro main window.

V1.1 placeholder - simply calls the entry point in colorlab_pro.ui.app.
The real Qt main window is implemented in T-14..T-23.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make src/ importable when running directly
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from colorlab_pro.ui.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
