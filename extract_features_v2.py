"""
extract_features_v2.py
Task 9.4 — Re-extract features with additional T2/T3 discriminating features.

New features added on top of v1:
  - f0_min_pos      : normalised time position of F0 minimum (0=start, 1=end)
  - f0_curve        : mean second derivative (curvature)
  - f0_slope_first  : slope of first half of contour
  - f0_slope_second : slope of second half of contour

Total features: 26 (v1) + 4 (new) = 30

Output: Data/features_v2.csv
"""

import csv
import collections
import numpy as np
import parselmouth
from pathlib import Path
from tqdm import tqdm

PROJECT_DIR  = Path(__file__).parent
METADATA_CSV = PROJECT_DIR / "Data" / "tone_perfect_metadata.csv"
OUTPUT_CSV   = PROJECT_DIR / "Data" / "features_v2.csv"
N_POINTS     = 10
PITCH_FLOOR  = 75
PITCH_CEIL   = 500

def extract_features_v2(filepath: str):
    try:
        snd   = parselmouth.Sound(filepath)
        pitch = snd.to_pitch(pitch_floor=PITCH_FLOOR, pitch_ceiling=PITCH_CEIL)
        f0    = pitch.selected_array["frequency"]

        voiced       = f0[f0 > 0]
        voiced_ratio = len(voiced) / max(len(f0), 1)
        if len(voiced) < 5:
            return None

        mean_hz = np.mean(voiced)
        if mean_hz <= 0:
            return None

        indices     = np.arange(len(f0))
        voiced_mask = f0 > 0
        f0_interp   = np.interp(indices, indices[voiced_mask], f0[voiced_mask])
        f0_st       = 12 * np.log2(f0_interp / mean_hz)

        x_orig  = np.linspace(0, 1, len(f0_st))
        x_norm  = np.linspace(0, 1, N_POINTS)
        f0_norm = np.interp(x_norm, x_orig, f0_st)
        delta   = np.diff(f0_norm)

        f0_mean = float(np.mean(f0_st))
        f0_std  = float(np.std(f0_st))
        f0_min  = float(np.min(f0_st))
        f0_max  = float(np.max(f0_st))
        x_idx   = np.arange(len(f0_st))
        slope   = float(np.polyfit(x_idx, f0_st, 1)[0] * len(f0_st))

        # New T2/T3 discriminating features
        min_pos      = float(np.argmin(f0_norm) / (N_POINTS - 1))
        curvature    = float(np.mean(np.diff(delta)))
        half         = N_POINTS // 2
        slope_first  = float(np.polyfit(np.arange(half), f0_norm[:half], 1)[0] * half)
        slope_second = float(np.polyfit(np.arange(N_POINTS - half), f0_norm[half:], 1)[0] * (N_POINTS - half))

        features = {}
        for i, val in enumerate(f0_norm):
            features[f"f0_{i+1:02d}"] = round(float(val), 4)
        for i, val in enumerate(delta):
            features[f"d0_{i+1:02d}"] = round(float(val), 4)
        features["f0_mean"]         = round(f0_mean, 4)
        features["f0_std"]          = round(f0_std, 4)
        features["f0_min"]          = round(f0_min, 4)
        features["f0_max"]          = round(f0_max, 4)
        features["f0_slope"]        = round(slope, 4)
        features["duration"]        = round(float(snd.duration), 4)
        features["voiced_ratio"]    = round(voiced_ratio, 4)
        features["f0_min_pos"]      = round(min_pos, 4)
        features["f0_curve"]        = round(curvature, 4)
        features["f0_slope_first"]  = round(slope_first, 4)
        features["f0_slope_second"] = round(slope_second, 4)
        return features

    except Exception:
        return None


if __name__ == "__main__":
    print("Loading metadata...")
    with open(METADATA_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"  {len(rows):,} files to process")

    f0_cols      = [f"f0_{i+1:02d}" for i in range(N_POINTS)]
    delta_cols   = [f"d0_{i+1:02d}" for i in range(N_POINTS - 1)]
    stat_cols    = ["f0_mean", "f0_std", "f0_min", "f0_max", "f0_slope",
                    "duration", "voiced_ratio"]
    new_cols     = ["f0_min_pos", "f0_curve", "f0_slope_first", "f0_slope_second"]
    feature_cols = f0_cols + delta_cols + stat_cols + new_cols
    all_cols     = ["id", "syllable", "tone", "speaker", "gender"] + feature_cols

    skipped = 0
    written = 0

    print(f"Extracting features -> {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=all_cols)
        writer.writeheader()
        for row in tqdm(rows, desc="Extracting"):
            features = extract_features_v2(row["filepath"])
            if features is None:
                skipped += 1
                continue
            writer.writerow({
                "id": row["id"], "syllable": row["syllable"],
                "tone": int(row["tone"]), "speaker": row["speaker"],
                "gender": row["gender"], **features
            })
            written += 1

    print(f"\nWritten: {written:,}  Skipped: {skipped:,}")
    print(f"Features: {len(feature_cols)} per utterance (26 original + 4 new)")

    print("\nNew feature means per tone (T2 vs T3 should differ clearly):")
    print(f"{'Tone':<6} {'f0_min_pos':>12} {'f0_curve':>10} {'slope_first':>12} {'slope_second':>13}")
    print("-" * 55)
    tone_data = collections.defaultdict(list)
    with open(OUTPUT_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tone_data[int(row["tone"])].append(row)
    for t in [1, 2, 3, 4]:
        d  = tone_data[t]
        mp = np.mean([float(r["f0_min_pos"])      for r in d])
        cv = np.mean([float(r["f0_curve"])         for r in d])
        sf = np.mean([float(r["f0_slope_first"])   for r in d])
        ss = np.mean([float(r["f0_slope_second"])  for r in d])
        print(f"T{t}     {mp:>12.3f} {cv:>10.3f} {sf:>12.3f} {ss:>13.3f}")
    print(f"\nSaved to: {OUTPUT_CSV}")
