from pathlib import Path

import numpy as np

wavelengths = np.arange(380, 781, 1.0)

# Gaussian: FWHM = 18nm
fwhm = 18.0
sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))

peaks = {"R": 630, "G": 530, "B": 460}

output = Path(r"D:\00000mimo\test_led_rgb.csv")
lines = ["wavelength,R,G,B"]

r_vals = np.exp(-0.5 * ((wavelengths - peaks["R"]) / sigma) ** 2)
g_vals = np.exp(-0.5 * ((wavelengths - peaks["G"]) / sigma) ** 2)
b_vals = np.exp(-0.5 * ((wavelengths - peaks["B"]) / sigma) ** 2)

for wl, r, g, b in zip(wavelengths, r_vals, g_vals, b_vals, strict=True):
    lines.append(f"{wl:.0f},{r:.6f},{g:.6f},{b:.6f}")

output.write_text("\n".join(lines), encoding="utf-8")
print(f"Created: {output}")
print(f"Points: {len(wavelengths)}")
print("R peak: 630nm, G peak: 530nm, B peak: 460nm")
print(f"FWHM: {fwhm}nm, Step: 1nm, Range: 380-780nm")
