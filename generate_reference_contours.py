"""
generate_reference_contours.py
Task 5 (revised) — Generate canonical reference pitch contours for T1-T4.

Uses theoretically-grounded tone templates from Mandarin phonetics literature
(Chao 1968 tone letter system, adapted to semitone scale) rather than
sentence-level corpus extraction, which is unreliable due to F0 declination.

The five-level tone letter system (Chao 1968):
  T1: 55   — high level
  T2: 35   — high rising
  T3: 214  — low dipping
  T4: 51   — high falling

These are converted to semitone contours and smoothed.
Output: Data/reference_contours/tone_{1,2,3,4}.npz  (overwrites previous)
"""

import numpy as np
from pathlib import Path
from scipy.ndimage import gaussian_filter1d

OUTPUT_DIR = Path(__file__).parent / "Data" / "reference_contours"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

N_POINTS = 100

# ── Tone level → semitone mapping ─────────────────────────────────────────────
# Chao's 5-level system: level 5 = highest, level 1 = lowest
# We map linearly to semitones: level 5 → +3 st, level 1 → -3 st
def level_to_st(level: float) -> float:
    return (level - 3) * 1.5   # centres at level 3 = 0 semitones

# ── Define canonical contours as (time, level) keypoints ──────────────────────
# Each list is (normalised_time, Chao_level) pairs
canonical = {
    1: [(0.0, 5.0), (0.5, 5.0), (1.0, 5.0)],          # high level: 55
    2: [(0.0, 3.0), (0.3, 3.5), (0.7, 4.5), (1.0, 5.0)],  # high rising: 35
    3: [(0.0, 2.0), (0.2, 2.0), (0.5, 1.0), (0.8, 1.5), (1.0, 2.5)],  # dipping: 214
    4: [(0.0, 5.0), (0.3, 4.0), (0.7, 2.0), (1.0, 1.0)],  # high falling: 51
}

x_norm = np.linspace(0, 1, N_POINTS)

print("Generating canonical reference contours (Chao 1968 tone letter system)\n")

for tone, keypoints in canonical.items():
    times  = np.array([p[0] for p in keypoints])
    levels = np.array([p[1] for p in keypoints])

    # Interpolate keypoints to N_POINTS
    contour_levels = np.interp(x_norm, times, levels)

    # Convert Chao levels to semitones
    contour_st = level_to_st(contour_levels)

    # Light smoothing
    contour_smooth = gaussian_filter1d(contour_st, sigma=2)

    # Save with zero std (canonical template, not empirical)
    std = np.zeros(N_POINTS)
    np.savez(
        OUTPUT_DIR / f"tone_{tone}.npz",
        mean=contour_smooth,
        std=std,
        n_samples=0,      # 0 = indicates canonical template
        n_points=N_POINTS
    )

    start = contour_smooth[0]
    mid   = contour_smooth[50]
    end   = contour_smooth[-1]
    print(f"T{tone}: start={start:+.2f}  mid={mid:+.2f}  end={end:+.2f} semitones")

print("\nSaved to Data/reference_contours/")
print("\nVerifying shapes are linguistically correct:")
print("  T1 should be: flat near +3")
print("  T2 should be: low→high (rising)")
print("  T3 should be: mid→low→mid (dipping)")
print("  T4 should be: high→low (falling)")
