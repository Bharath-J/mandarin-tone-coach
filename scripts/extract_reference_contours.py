"""
extract_reference_contours.py
Task 5 — Pre-extract native speaker reference pitch contours using Parselmouth.

For each tone T1-T4:
  - Sample up to MAX_SAMPLES utterances that contain at least one syllable of that tone
  - Extract F0 contour from the full utterance using Parselmouth
  - Time-normalise to N_POINTS points
  - Compute mean + std contour across all samples
  - Save to Data/reference_contours/tone_{1,2,3,4}.npz

These reference contours are used by the Streamlit app to overlay
native speaker pitch curves against learner recordings.
"""

import csv
import random
import numpy as np
import parselmouth
from parselmouth.praat import call
from pathlib import Path
from tqdm import tqdm
from collections import defaultdict

# ── Config ─────────────────────────────────────────────────────────────────────
PROJECT_DIR  = Path(__file__).parent
DATASET_CSV  = PROJECT_DIR / "Data" / "tone_dataset.csv"
OUTPUT_DIR   = PROJECT_DIR / "Data" / "reference_contours"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_SAMPLES  = 200      # utterances per tone to average over
N_POINTS     = 100      # time-normalised points per contour
PITCH_FLOOR  = 75       # Hz  (covers male and female speakers)
PITCH_CEIL   = 500      # Hz
RANDOM_SEED  = 42

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# ── Step 1: group utterances by dominant tone ──────────────────────────────────
print("Loading dataset...")
tone_utterances = defaultdict(list)   # tone_num → list of wav_paths

with open(DATASET_CSV, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        tones = list(map(int, row["tones"].split()))
        if not tones:
            continue
        # assign utterance to the tone that appears most in it
        dominant = max(set(tones), key=tones.count)
        tone_utterances[dominant].append(row["wav_path"])

for t in [1,2,3,4]:
    print(f"  T{t}: {len(tone_utterances[t]):,} candidate utterances")

# ── Helper: extract and normalise F0 contour ──────────────────────────────────
def extract_f0_contour(wav_path: str, n_points: int = N_POINTS) -> np.ndarray | None:
    """
    Load WAV, extract F0 using Praat autocorrelation, interpolate unvoiced frames,
    time-normalise to n_points, semitone-normalise to speaker mean.
    Returns array of shape (n_points,) or None if extraction fails.
    """
    try:
        snd = parselmouth.Sound(wav_path)
        pitch = snd.to_pitch(pitch_floor=PITCH_FLOOR, pitch_ceiling=PITCH_CEIL)
        f0_values = pitch.selected_array["frequency"]   # Hz, 0 = unvoiced

        # Keep only voiced frames
        voiced = f0_values[f0_values > 0]
        if len(voiced) < 10:    # too few voiced frames — skip
            return None

        # Interpolate over unvoiced frames for a smooth contour
        indices = np.arange(len(f0_values))
        voiced_mask = f0_values > 0
        f0_interp = np.interp(
            indices,
            indices[voiced_mask],
            f0_values[voiced_mask]
        )

        # Convert to semitones relative to speaker mean (removes speaker-level differences)
        mean_hz = np.mean(f0_interp)
        if mean_hz <= 0:
            return None
        f0_st = 12 * np.log2(f0_interp / mean_hz)

        # Time-normalise to n_points via linear interpolation
        x_orig = np.linspace(0, 1, len(f0_st))
        x_norm = np.linspace(0, 1, n_points)
        f0_norm = np.interp(x_norm, x_orig, f0_st)

        return f0_norm

    except Exception:
        return None


# ── Step 2: extract contours per tone ─────────────────────────────────────────
for tone in [1, 2, 3, 4]:
    candidates = tone_utterances[tone]
    sample = random.sample(candidates, min(MAX_SAMPLES, len(candidates)))

    contours = []
    for wav_path in tqdm(sample, desc=f"T{tone} ({len(sample)} utterances)"):
        contour = extract_f0_contour(wav_path)
        if contour is not None:
            contours.append(contour)

    if len(contours) < 5:
        print(f"  WARNING: only {len(contours)} valid contours for T{tone}, skipping")
        continue

    contours_arr = np.array(contours)          # shape: (n_valid, N_POINTS)
    mean_contour = np.mean(contours_arr, axis=0)
    std_contour  = np.std(contours_arr, axis=0)

    out_path = OUTPUT_DIR / f"tone_{tone}.npz"
    np.savez(out_path,
             mean=mean_contour,
             std=std_contour,
             n_samples=len(contours),
             n_points=N_POINTS)

    print(f"  T{tone}: {len(contours)} contours averaged → {out_path.name}")
    print(f"    F0 range: {mean_contour.min():.2f} to {mean_contour.max():.2f} semitones")

# ── Step 3: quick visual check ────────────────────────────────────────────────
print("\nVerifying saved files:")
for tone in [1, 2, 3, 4]:
    path = OUTPUT_DIR / f"tone_{tone}.npz"
    if path.exists():
        data = np.load(path)
        print(f"  tone_{tone}.npz — mean shape: {data['mean'].shape}, "
              f"n_samples: {data['n_samples']}")

print("\nDone. Reference contours saved to Data/reference_contours/")
