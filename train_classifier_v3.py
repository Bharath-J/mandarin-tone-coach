"""
train_classifier_v3.py
Task 9.4 — Iteration 2: finer contour resolution (20 points) + SVM grid search.

Changes from v2:
  - N_POINTS: 10 -> 20 (captures T3 mid-dip more precisely)
  - Grid search over SVM C and gamma
  - Keep only the best new feature from v2: f0_min_pos (Cohen d=1.25)
  - Drop low-value features: f0_curve, f0_slope_first, f0_slope_second

Total features: 20 (f0) + 19 (delta) + 7 (stats) + 1 (min_pos) = 47
"""

import csv
import pickle
import numpy as np
import parselmouth
from pathlib import Path
from tqdm import tqdm
from collections import defaultdict, Counter

from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.model_selection import GridSearchCV

PROJECT_DIR  = Path(__file__).parent
METADATA_CSV = PROJECT_DIR / "Data" / "tone_perfect_metadata.csv"
FEATURES_V3  = PROJECT_DIR / "Data" / "features_v3.csv"
MODELS_DIR   = PROJECT_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

N_POINTS    = 20
PITCH_FLOOR = 75
PITCH_CEIL  = 500

TEST_SPEAKERS  = {"Female Voice 3", "Male Voice 3"}
TRAIN_SPEAKERS = {"Female Voice 1", "Female Voice 2", "Male Voice 1", "Male Voice 2"}

# ── Step 1: Extract v3 features ───────────────────────────────────────────────
def extract_features_v3(filepath: str):
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

        f0_mean  = float(np.mean(f0_st))
        f0_std   = float(np.std(f0_st))
        f0_min   = float(np.min(f0_st))
        f0_max   = float(np.max(f0_st))
        x_idx    = np.arange(len(f0_st))
        slope    = float(np.polyfit(x_idx, f0_st, 1)[0] * len(f0_st))
        min_pos  = float(np.argmin(f0_norm) / (N_POINTS - 1))

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
        features["f0_min_pos"]   = round(min_pos, 4)
        return features

    except Exception:
        return None


print("=" * 60)
print("TASK 9.4 ITERATION — V3 FEATURES + GRID SEARCH")
print("=" * 60)

# Extract features
print(f"\nExtracting v3 features (N_POINTS={N_POINTS})...")
with open(METADATA_CSV, encoding="utf-8") as f:
    metadata_rows = list(csv.DictReader(f))

f0_cols      = [f"f0_{i+1:02d}" for i in range(N_POINTS)]
delta_cols   = [f"d0_{i+1:02d}" for i in range(N_POINTS - 1)]
stat_cols    = ["f0_mean", "f0_std", "f0_min", "f0_max", "f0_slope",
                "duration", "voiced_ratio", "f0_min_pos"]
feature_cols = f0_cols + delta_cols + stat_cols
all_cols     = ["id", "syllable", "tone", "speaker", "gender"] + feature_cols

with open(FEATURES_V3, "w", newline="", encoding="utf-8") as out:
    writer = csv.DictWriter(out, fieldnames=all_cols)
    writer.writeheader()
    skipped = 0
    for row in tqdm(metadata_rows, desc="Extracting"):
        features = extract_features_v3(row["filepath"])
        if features is None:
            skipped += 1
            continue
        writer.writerow({
            "id": row["id"], "syllable": row["syllable"],
            "tone": int(row["tone"]), "speaker": row["speaker"],
            "gender": row["gender"], **features
        })

print(f"  Skipped: {skipped}")

# ── Step 2: Load into train/test split ────────────────────────────────────────
print("\nLoading features into train/test split...")
train_X, train_y = [], []
test_X,  test_y  = [], []

with open(FEATURES_V3, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        feats   = [float(row[c]) for c in feature_cols]
        label   = int(row["tone"])
        speaker = row["speaker"]
        if speaker in TEST_SPEAKERS:
            test_X.append(feats)
            test_y.append(label)
        else:
            train_X.append(feats)
            train_y.append(label)

train_X = np.array(train_X)
train_y = np.array(train_y)
test_X  = np.array(test_X)
test_y  = np.array(test_y)
print(f"  Train: {len(train_y):,}   Test: {len(test_y):,}")

# ── Step 3: Scale ─────────────────────────────────────────────────────────────
scaler         = StandardScaler()
train_X_scaled = scaler.fit_transform(train_X)
test_X_scaled  = scaler.transform(test_X)

# ── Step 4: Grid search ───────────────────────────────────────────────────────
print("\nRunning SVM grid search (C x gamma)...")
param_grid = {
    "C":     [1, 10, 50, 100],
    "gamma": ["scale", "auto", 0.01, 0.001],
}
grid = GridSearchCV(
    SVC(kernel="rbf", decision_function_shape="ovr", random_state=42),
    param_grid,
    cv=5,
    scoring="accuracy",
    n_jobs=-1,
    verbose=1,
)
grid.fit(train_X_scaled, train_y)

best_params = grid.best_params_
best_cv     = grid.best_score_
print(f"\n  Best params: {best_params}")
print(f"  Best CV accuracy: {best_cv:.4f}")

# ── Step 5: Evaluate best model on test set ───────────────────────────────────
best_svm   = grid.best_estimator_
test_pred  = best_svm.predict(test_X_scaled)
test_acc   = accuracy_score(test_y, test_pred)
train_acc  = accuracy_score(train_y, best_svm.predict(train_X_scaled))

tone_names   = {1: "T1(flat)", 2: "T2(rise)", 3: "T3(dip)", 4: "T4(fall)"}
target_names = [tone_names[t] for t in [1,2,3,4]]
report       = classification_report(test_y, test_pred, labels=[1,2,3,4],
                                     target_names=target_names)
cm           = confusion_matrix(test_y, test_pred, labels=[1,2,3,4])

print(f"\n{'='*60}")
print(f"V3 RESULTS (N_POINTS=20, best SVM params={best_params})")
print(f"{'='*60}")
print(f"Train accuracy: {train_acc:.4f}")
print(f"Test  accuracy: {test_acc:.4f}  (v1 baseline: 0.9195)")
print(f"\nClassification Report:")
print(report)
print("Confusion Matrix (rows=actual, cols=predicted):")
print(f"{'':12}", end="")
for name in target_names:
    print(f"{name:>12}", end="")
print()
for i, row_name in enumerate(target_names):
    print(f"{row_name:12}", end="")
    for val in cm[i]:
        print(f"{val:>12}", end="")
    print()

# ── Step 6: Save ──────────────────────────────────────────────────────────────
print(f"\nSaving v3 models...")
with open(MODELS_DIR / "svm_classifier.pkl", "wb") as f:
    pickle.dump(best_svm, f)
with open(MODELS_DIR / "scaler.pkl", "wb") as f:
    pickle.dump(scaler, f)
with open(MODELS_DIR / "feature_cols.pkl", "wb") as f:
    pickle.dump(feature_cols, f)

report_text = f"""V3 CLASSIFICATION REPORT
{'='*40}
N_POINTS: {N_POINTS}
Best SVM params: {best_params}
Best CV accuracy: {best_cv:.4f}

Train accuracy: {train_acc:.4f}
Test  accuracy: {test_acc:.4f}
V1 baseline:    0.9195

{report}

Confusion Matrix:
     T1    T2    T3    T4
{chr(10).join(f"T{i+1}  {'  '.join(f'{v:4d}' for v in cm[i])}" for i in range(4))}
"""
with open(MODELS_DIR / "classification_report_v3.txt", "w") as f:
    f.write(report_text)

print(f"  svm_classifier.pkl  (updated)")
print(f"  scaler.pkl          (updated)")
print(f"  feature_cols.pkl    (updated)")
print(f"  classification_report_v3.txt")
print("\nDone.")
