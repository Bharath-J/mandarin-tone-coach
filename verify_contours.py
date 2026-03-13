"""
verify_contours.py
Quick check that reference contours have the expected shapes for T1-T4.
"""
import numpy as np
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "Data" / "reference_contours"

descriptions = {
    1: "flat/high (should be roughly flat near top)",
    2: "rising (should go up from mid to high)",
    3: "dipping (should go down then up)",
    4: "falling (should go high to low)",
}

for tone in [1, 2, 3, 4]:
    data = np.load(OUTPUT_DIR / f"tone_{tone}.npz")
    mean = data["mean"]
    n    = int(data["n_samples"])

    start = mean[0]
    mid   = mean[50]
    end   = mean[-1]
    rng   = mean.max() - mean.min()

    print(f"T{tone} ({descriptions[tone]})")
    print(f"  n_samples: {n}")
    print(f"  start={start:+.2f}  mid={mid:+.2f}  end={end:+.2f}  range={rng:.2f} semitones")
    print()
