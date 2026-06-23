"""Channel and category constants for spectrum classification.

Channel: R, G, B (the color of the primary)
Category: LED, CF, QD, 白光 (the type of light source)
"""

from __future__ import annotations

# Channel constants — only R, G, B
CHANNEL_R: str = "R"
CHANNEL_G: str = "G"
CHANNEL_B: str = "B"

# Category constants
CATEGORY_LED: str = "LED"
CATEGORY_CF: str = "CF"
CATEGORY_QD: str = "QD"
CATEGORY_WHITE: str = "白光"

# All valid categories
ALL_CATEGORIES: list[str] = [CATEGORY_LED, CATEGORY_CF, CATEGORY_QD, CATEGORY_WHITE]

# Channel options for UI dropdowns
CHANNEL_OPTIONS: list[tuple[str, str | None]] = [
    ("Auto-detect", None),
    ("R", CHANNEL_R),
    ("G", CHANNEL_G),
    ("B", CHANNEL_B),
]

# Category options for UI dropdowns
CATEGORY_OPTIONS: list[tuple[str, str | None]] = [
    ("Auto-detect", None),
    ("LED", CATEGORY_LED),
    ("CF", CATEGORY_CF),
    ("QD", CATEGORY_QD),
    ("白光", CATEGORY_WHITE),
]
