"""
train_classifier_v2.py
Task 9.4 — Retrain classifier with v2 features and compare against v1.
"""

import csv
import pickle
import numpy as np
from pathlib import Path
from collections import Counter
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

PROJECT_DIR   = Path(__file__).parent
FEATURES_CSV  = PROJECT_DIR / "Data" / "features_v2.csv"
MODELS_DIR    = PROJECT_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

TEST_SPEAKERS  = {"Female Voice 3", "Male Voice 3"}
TRAIN_SPEAKERS = {"Female Voice 1", "Female Voice 2", "Male Voice 1", "Male Voice 2"}

FEATURE_COLS = (
    [f"f0_{i+1:02d}" for i in range(10)] +
    [f"d0_{i+1:02d}" for i in range(9)]  +
    ["f0_mean", "f0_std", "f0_min", "f0_max", "f0_slope",
     "duration", "voiced_ratio",
     "f0_min_pos", "f0_curve", "f0_slope_first", "f0_slope_second"]
)

# Load features
print("Loading v2 features...")
train_X, train_y = [], []
test_X,  test_y  = [], []

with open(FEATURES_CSV, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        features = [float(row[c]) for c in FEATURE_COLS]
        label    = int(row["tone"])
        if row["speaker"] in TEST_SPEAKERS:
            test_X.append(features)
            test_y.append(label)
        else:
            train_X.append(features)
            train_y.append(label)

train_X = np.array(train_X)
train_y = np.array(train_y)
test_X  = np.array(test_X)
test_y  = np.array(test_y)
print(f"  Train: {len(train_y):,}  Test: {len(test_y):,}")

# Scale
scaler         = StandardScaler()
train_X_scaled = scaler.fit_transform(train_X)
test_X_scaled  = scaler.transform(test_X)

# Train SVM
print("\nTraining SVM v2...")
svm = SVC(kernel="rbf", C=10, gamma="scale", random_state=42)
svm.fit(train_X_scaled, train_y)
svm_train = accuracy_score(train_y, svm.predict(train_X_scaled))
svm_test  = accuracy_score(test_y,  svm.predict(test_X_scaled))
print(f"  Train: {svm_train:.4f}  Test: {svm_test:.4f}")

# Train MLP
print("\nTraining MLP v2...")
mlp = MLPClassifier(hidden_layer_sizes=(256, 128), activation="relu",
                    solver="adam", max_iter=500, random_state=42,
                    early_stopping=True, validation_fraction=0.1)
mlp.fit(train_X_scaled, train_y)
mlp_train = accuracy_score(train_y, mlp.predict(train_X_scaled))
mlp_test  = accuracy_score(test_y,  mlp.predict(test_X_scaled))
print(f"  Train: {mlp_train:.4f}  Test: {mlp_test:.4f}")

# Best model evaluation
best_model = svm if svm_test >= mlp_test else mlp
best_name  = "SVM" if svm_test >= mlp_test else "MLP"
best_pred  = best_model.predict(test_X_scaled)
tone_names = ["T1(flat)", "T2(rise)", "T3(dip)", "T4(fall)"]
report     = classification_report(test_y, best_pred, labels=[1,2,3,4], target_names=tone_names)
cm         = confusion_matrix(test_y, best_pred, labels=[1,2,3,4])

print(f"\n{'='*60}")
print(f"V2 RESULTS — Best model: {best_name} ({max(svm_test, mlp_test):.4f})")
print(f"V1 baseline: SVM 0.9195")
print(f"Improvement: {max(svm_test, mlp_test) - 0.9195:+.4f}")
print(f"{'='*60}")
print(report)
print("Confusion Matrix:")
print(f"{'':12}", end="")
for n in tone_names: print(f"{n:>12}", end="")
print()
for i, n in enumerate(tone_names):
    print(f"{n:12}", end="")
    for v in cm[i]: print(f"{v:>12}", end="")
    print()

# T2/T3 specific improvement
t2_errors_v1 = 132
t3_errors_v1 = 66
t2_errors_v2 = cm[1][2]   # T2 predicted as T3
t3_errors_v2 = cm[2][1]   # T3 predicted as T2
print(f"\nT2/T3 confusion improvement:")
print(f"  T2->T3 errors: {t2_errors_v1} (v1) -> {t2_errors_v2} (v2)  ({t2_errors_v1 - t2_errors_v2:+d})")
print(f"  T3->T2 errors: {t3_errors_v1} (v1) -> {t3_errors_v2} (v2)  ({t3_errors_v1 - t3_errors_v2:+d})")

# Save updated models
print(f"\nSaving v2 models...")
with open(MODELS_DIR / "svm_classifier.pkl", "wb") as f: pickle.dump(svm, f)
with open(MODELS_DIR / "mlp_classifier.pkl", "wb") as f: pickle.dump(mlp, f)
with open(MODELS_DIR / "scaler.pkl",         "wb") as f: pickle.dump(scaler, f)
with open(MODELS_DIR / "feature_cols.pkl",   "wb") as f: pickle.dump(FEATURE_COLS, f)

# Save full report
with open(MODELS_DIR / "classification_report_v2.txt", "w") as f:
    f.write(f"V2 CLASSIFICATION REPORT\n{'='*40}\n")
    f.write(f"Best model: {best_name}\n")
    f.write(f"SVM test accuracy: {svm_test:.4f}\n")
    f.write(f"MLP test accuracy: {mlp_test:.4f}\n\n")
    f.write(report + "\n")
    f.write(f"Confusion Matrix:\n")
    f.write(f"     T1    T2    T3    T4\n")
    for i in range(4):
        f.write(f"T{i+1}  {'  '.join(f'{v:4d}' for v in cm[i])}\n")

print("Done. Models saved to models/")
