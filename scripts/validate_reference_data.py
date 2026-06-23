"""Validate the bundled reference spectra. V1.1 placeholder (T-09 area)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np  # noqa: E402

from colorlab_pro.dto.spectrum import Spectrum  # noqa: E402
from colorlab_pro.engines.spectrum_normalizer import detect_channel  # noqa: E402


def load_csv(path: Path) -> Spectrum:
    arr = np.loadtxt(path, delimiter=",", skiprows=1)
    return Spectrum(wavelengths=arr[:, 0], values=arr[:, 1], unit="a.u.")


def main() -> int:
    ref_dir = ROOT / "resources" / "reference_data" / "synthetic"
    print(f"Validating spectra in: {ref_dir}")
    expected = {
        "led_r.csv": "R-LED",
        "led_g.csv": "G-LED",
        "led_b.csv": "B-LED",
    }
    failed = 0
    for fname, expected_ch in expected.items():
        path = ref_dir / fname
        if not path.exists():
            print(f"  MISSING: {fname}")
            failed += 1
            continue
        s = load_csv(path)
        ch = detect_channel(s)
        ok = ch == expected_ch
        marker = "OK" if ok else "FAIL"
        print(
            f"  [{marker}] {fname}: peak={s.wavelengths[int(np.argmax(s.values))]:.1f} nm, channel={ch} (expected {expected_ch})"
        )
        if not ok:
            failed += 1
    if failed:
        print(f"\n{failed} validation(s) failed.")
        return 1
    print("\nAll reference data validated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
