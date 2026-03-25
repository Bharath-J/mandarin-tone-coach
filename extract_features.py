"""
extract_features.py
Task 9.1 — Extract F0-based acoustic features from Tone Perfect corpus.

For each MP3 file, extracts:
  - f0_01 ... f0_10   : time-normalised F0 at 10 equally spaced points (semitones)
  - d0_01 ... d0_09   : first-order delta (difference between consecutive points)
  - f0_mean           : mean F0 (semitones)
  - f0_std            : std of F0 contour (flatness measure)
  - f0_min            : minimum F0 value
  - f0_max            : maximum F0 value
  - f0_slope          : linear regression slope across contour
  - duration          : utterance duration in seconds
  - voiced_ratio      : fraction of frames that are voiced

Total: 10 + 9 + 7 = 26 features per utterance

Output: Data/features.csv
"""

import csv
import collections
import numpy as np
import parselmouth
from pathlib import Path
from tqdm import tqdm

# ── Config ─────────────────────────────────────────────────────────────────────
PROJECT_DIR  = Path(__file__).parent
METADATA_CSV = PROJECT_DIR / "Data" / "tone_perfect_metadata.csv"
OUTPUT_CSV   = PROJECT_DIR / "Data" / "features.csv"
N_POINTS     = 10
PITCH_FLOOR  = 75
PITCH_CEIL   = 500

# ── Feature extraction for one file ───────────────────────────────────────────
def extract_features(filepath: str):
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

        # Interpolate unvoiced frames
        indices     = np.arange(len(f0))
        voiced_mask = f0 > 0
        f0_interp   = np.interp(indices, indices[voiced_mask], f0[voiced_mask])
        f0_st       = 12 * np.log2(f0_interp / mean_hz)

        # Time-normalise to N_POINTS
        x_orig  = np.linspace(0, 1, len(f0_st))
        x_norm  = np.linspace(0, 1, N_POINTS)
        f0_norm = np.interp(x_norm, x_orig, f0_st)

        # Delta features
        delta = np.diff(f0_norm)

        # Summary statistics
        f0_mean = float(np.mean(f0_st))
        f0_std  = float(np.std(f0_st))
        f0_min  = float(np.min(f0_st))
        f0_max  = float(np.max(f0_st))
        x_idx   = np.arange(len(f0_st))
        slope   = float(np.polyfit(x_idx, f0_st, 1)[0] * len(f0_st))

        features = {}
        for i, val in enumerate(f0_norm):
            features[f"f0_{i+1:02d}"] = round(float(val), 4)
        for i, val in enumerate(delta):
            features[f"d0_{i+1:02d}"] = round(float(val), 4)
        features["f0_mean"]      = round(f0_mean, 4)
        features["f0_std"]       = round(f0_std, 4)
        features["f0_min"]       = round(f0_min, 4)
        features["f0_max"]       = round(f0_max, 4)
        features["f0_slope"]     = round(slope, 4)
        features["duration"]     = round(float(snd.duration), 4)
        features["voiced_ratio"] = round(voiced_ratio, 4)
        # Position of F0 minimum — key T2/T3 discriminator (T2≈0.39, T3≈0.57)
        features["f0_min_pos"]   = round(float(np.argmin(f0_norm) / (N_POINTS - 1)), 4)

        return features

    except Exception:
        return None


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    print("Loading metadata...")
    rows = []
    with open(METADATA_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    print(f"  {len(rows):,} files to process")

    f0_cols      = [f"f0_{i+1:02d}" for i in range(N_POINTS)]
    delta_cols   = [f"d0_{i+1:02d}" for i in range(N_POINTS - 1)]
    stat_cols    = ["f0_mean", "f0_std", "f0_min", "f0_max", "f0_slope",
                    "duration", "voiced_ratio", "f0_min_pos"]
    feature_cols = f0_cols + delta_cols + stat_cols
    all_cols     = ["id", "syllable", "tone", "speaker", "gender"] + feature_cols

    skipped = 0
    written = 0

    print(f"Extracting features -> {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=all_cols)
        writer.writeheader()

        for row in tqdm(rows, desc="Extracting"):
            features = extract_features(row["filepath"])
            if features is None:
                skipped += 1
                continue
            out_row = {
                "id":       row["id"],
                "syllable": row["syllable"],
                "tone":     int(row["tone"]),
                "speaker":  row["speaker"],
                "gender":   row["gender"],
                **features
            }
            writer.writerow(out_row)
            written += 1

    print(f"\n{'='*50}")
    print(f"FEATURE EXTRACTION COMPLETE")
    print(f"{'='*50}")
    print(f"Written:  {written:,}")
    print(f"Skipped:  {skipped:,}")
    print(f"Features: {len(feature_cols)} per utterance")

    tone_counts = collections.Counter()
    with open(OUTPUT_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tone_counts[int(row["tone"])] += 1
    print("\nPer-tone breakdown:")
    for t in [1, 2, 3, 4]:
        print(f"  T{t}: {tone_counts[t]:,} samples")
    print(f"\nSaved to: {OUTPUT_CSV}")
