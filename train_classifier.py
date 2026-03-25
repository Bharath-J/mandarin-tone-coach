"""
train_classifier.py
Task 9.2 — Train and evaluate SVM and MLP tone classifiers on Tone Perfect features.

Split strategy:
  - 4 speakers (2F, 2M) for training
  - 2 speakers (1F, 1M) for testing
  This ensures the test set contains unseen speakers, measuring generalisation.

Models:
  - SVM with RBF kernel (C=10, gamma='scale')
  - MLP with two hidden layers (256, 128)

Output:
  - models/svm_classifier.pkl
  - models/mlp_classifier.pkl
  - models/scaler.pkl
  - models/classification_report.txt
"""

import csv
import pickle
import numpy as np
from pathlib import Path
from collections import defaultdict

from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# ── Config ─────────────────────────────────────────────────────────────────────
PROJECT_DIR  = Path(__file__).parent
FEATURES_CSV = PROJECT_DIR / "Data" / "features.csv"
MODELS_DIR   = PROJECT_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Speaker split — held out for testing
TEST_SPEAKERS  = {"Female Voice 3", "Male Voice 3"}
TRAIN_SPEAKERS = {"Female Voice 1", "Female Voice 2", "Male Voice 1", "Male Voice 2"}

FEATURE_COLS = (
    [f"f0_{i+1:02d}" for i in range(10)] +
    [f"d0_{i+1:02d}" for i in range(9)]  +
    ["f0_mean", "f0_std", "f0_min", "f0_max", "f0_slope",
     "duration", "voiced_ratio", "f0_min_pos"]
)

# ── Load features ──────────────────────────────────────────────────────────────
print("Loading features...")
train_X, train_y = [], []
test_X,  test_y  = [], []
train_meta, test_meta = [], []

with open(FEATURES_CSV, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        features = [float(row[c]) for c in FEATURE_COLS]
        label    = int(row["tone"])
        speaker  = row["speaker"]
        if speaker in TEST_SPEAKERS:
            test_X.append(features)
            test_y.append(label)
            test_meta.append(row)
        else:
            train_X.append(features)
            train_y.append(label)
            train_meta.append(row)

train_X = np.array(train_X)
train_y = np.array(train_y)
test_X  = np.array(test_X)
test_y  = np.array(test_y)

print(f"  Train: {len(train_y):,} samples ({', '.join(sorted(TRAIN_SPEAKERS))})")
print(f"  Test:  {len(test_y):,}  samples ({', '.join(sorted(TEST_SPEAKERS))})")

# Per-tone counts
from collections import Counter
print(f"\n  Train tone distribution: { {k: v for k,v in sorted(Counter(train_y).items())} }")
print(f"  Test  tone distribution: { {k: v for k,v in sorted(Counter(test_y).items())} }")

# ── Feature scaling ────────────────────────────────────────────────────────────
print("\nScaling features...")
scaler  = StandardScaler()
train_X_scaled = scaler.fit_transform(train_X)
test_X_scaled  = scaler.transform(test_X)

# ── Train SVM ─────────────────────────────────────────────────────────────────
print("\nTraining SVM (RBF kernel, C=10)...")
svm = SVC(kernel="rbf", C=10, gamma="scale", decision_function_shape="ovr",
          random_state=42, verbose=False)
svm.fit(train_X_scaled, train_y)
svm_train_acc = accuracy_score(train_y, svm.predict(train_X_scaled))
svm_test_acc  = accuracy_score(test_y,  svm.predict(test_X_scaled))
print(f"  Train accuracy: {svm_train_acc:.4f}")
print(f"  Test  accuracy: {svm_test_acc:.4f}")

# ── Train MLP ─────────────────────────────────────────────────────────────────
print("\nTraining MLP (256→128)...")
mlp = MLPClassifier(
    hidden_layer_sizes=(256, 128),
    activation="relu",
    solver="adam",
    max_iter=500,
    random_state=42,
    early_stopping=True,
    validation_fraction=0.1,
    verbose=False
)
mlp.fit(train_X_scaled, train_y)
mlp_train_acc = accuracy_score(train_y, mlp.predict(train_X_scaled))
mlp_test_acc  = accuracy_score(test_y,  mlp.predict(test_X_scaled))
print(f"  Train accuracy: {mlp_train_acc:.4f}")
print(f"  Test  accuracy: {mlp_test_acc:.4f}")

# ── Detailed evaluation ────────────────────────────────────────────────────────
tone_names = {1: "T1(flat)", 2: "T2(rise)", 3: "T3(dip)", 4: "T4(fall)"}
target_names = [tone_names[t] for t in [1,2,3,4]]

best_model      = svm if svm_test_acc >= mlp_test_acc else mlp
best_name       = "SVM" if svm_test_acc >= mlp_test_acc else "MLP"
best_pred       = best_model.predict(test_X_scaled)

report = classification_report(test_y, best_pred,
                                labels=[1,2,3,4],
                                target_names=target_names)
cm     = confusion_matrix(test_y, best_pred, labels=[1,2,3,4])

print(f"\n{'='*60}")
print(f"BEST MODEL: {best_name} (test accuracy: {max(svm_test_acc, mlp_test_acc):.4f})")
print(f"{'='*60}")
print("\nClassification Report:")
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

# ── Save models ───────────────────────────────────────────────────────────────
print(f"\nSaving models to {MODELS_DIR}/")
with open(MODELS_DIR / "svm_classifier.pkl", "wb") as f:
    pickle.dump(svm, f)
with open(MODELS_DIR / "mlp_classifier.pkl", "wb") as f:
    pickle.dump(mlp, f)
with open(MODELS_DIR / "scaler.pkl", "wb") as f:
    pickle.dump(scaler, f)

# Save report
report_text = f"""TONE CLASSIFIER EVALUATION REPORT
==================================

Train speakers: {', '.join(sorted(TRAIN_SPEAKERS))}
Test  speakers: {', '.join(sorted(TEST_SPEAKERS))}

Train samples: {len(train_y)}
Test  samples: {len(test_y)}

SVM  train accuracy: {svm_train_acc:.4f}
SVM  test  accuracy: {svm_test_acc:.4f}

MLP  train accuracy: {mlp_train_acc:.4f}
MLP  test  accuracy: {mlp_test_acc:.4f}

Best model: {best_name}

Classification Report ({best_name}):
{report}

Confusion Matrix ({best_name}):
     T1    T2    T3    T4
{chr(10).join(f"T{i+1}  {'  '.join(f'{v:4d}' for v in cm[i])}" for i in range(4))}
"""

with open(MODELS_DIR / "classification_report.txt", "w") as f:
    f.write(report_text)

with open(MODELS_DIR / "feature_cols.pkl", "wb") as f:
    pickle.dump(list(FEATURE_COLS), f)

print(f"  svm_classifier.pkl")
print(f"  mlp_classifier.pkl")
print(f"  scaler.pkl")
print(f"  feature_cols.pkl")
print(f"  classification_report.txt")
print("\nDone.")
