# Mandarin Tone Coach — Project Context
## CS6460 Educational Technology, Georgia Tech, 2026
## Student: Bharath Jagadish (bjagadish3@gatech.edu)
## Last updated: Week 11 in progress

---

## 1. PROJECT OVERVIEW

**What we are building:** A Streamlit web app that helps English-speaking learners of Mandarin Chinese practice the four lexical tones (T1 flat, T2 rising, T3 dipping, T4 falling). The learner records themselves saying a word, the app extracts pitch (F0) using Parselmouth/Praat, classifies the tone using a trained SVM classifier, displays a pitch contour overlay (learner vs native reference), and gives plain-language corrective feedback.

**Track:** Development track
**Repository:** https://github.gatech.edu/bjagadish3/mandarin-tone-coach

---

## 2. PROJECT DIRECTORY

```
/Users/bharath/Documents/Old_Desktop/Apps/Coursera/GTech/EdTech/Assignments/Project/
├── app.py                          ← Main Streamlit app (Tasks 10.1–10.4, 11.2–11.3)
├── word_list.json                  ← 40 monosyllabic practice words (10 per tone)
├── word_list_disyllabic.json       ← 20 disyllabic practice words (Task 11.2)
├── extract_features.py             ← Feature extraction from Tone Perfect corpus
├── train_classifier.py             ← SVM + MLP classifier training
├── generate_reference_contours.py  ← Canonical T1-T4 pitch contours (Chao 1968)
├── explore_aishell.py              ← AISHELL-1 exploration (not used in final pipeline)
├── extract_segments.py             ← AISHELL-1 segment extraction (not used)
├── scrape_tone_perfect.py          ← Scraped Tone Perfect corpus from MSU website
├── train_classifier_v2.py          ← Feature iteration attempt (no improvement)
├── train_classifier_v3.py          ← Grid search iteration (no improvement)
├── extract_features_v2.py          ← Feature v2 with extra features
├── requirements.txt
├── venv/                           ← Python 3.14 virtual environment
├── models/
│   ├── svm_classifier.pkl          ← ACTIVE MODEL (27 features, 91.95% accuracy)
│   ├── mlp_classifier.pkl          ← MLP model (90.52%, not used)
│   ├── scaler.pkl                  ← StandardScaler fitted on training data
│   ├── feature_cols.pkl            ← List of 27 feature column names
│   ├── classification_report.txt   ← Full eval report with confusion matrix
│   └── iteration_summary.txt       ← Summary of v1/v2/v3 iterations
└── Data/
    ├── tone_perfect_metadata.csv   ← Metadata for 9,838 Tone Perfect MP3 files
    ├── features.csv                ← 9,837 rows × 27 features (training data)
    ├── tone_dataset.csv            ← AISHELL-1 derived CSV — NOT USED in pipeline
    ├── tone_perfect/               ← 9,838 MP3 files (gitignored, ~300MB)
    │   ├── tone_1/                 ← T1 MP3s
    │   ├── tone_2/                 ← T2 MP3s
    │   ├── tone_3/                 ← T3 MP3s
    │   └── tone_4/                 ← T4 MP3s
    ├── reference_contours/
    │   ├── tone_1.npz              ← Canonical T1 pitch contour (Chao 1968)
    │   ├── tone_2.npz              ← Canonical T2 pitch contour
    │   ├── tone_3.npz              ← Canonical T3 pitch contour
    │   └── tone_4.npz              ← Canonical T4 pitch contour
    └── data_aishell/               ← AISHELL-1 corpus (gitignored, ~15GB, NOT USED)
```

---

## 3. DATA PIPELINE (what's actually used)

```
Tone Perfect corpus (MSU)
  → scrape_tone_perfect.py
  → Data/tone_perfect/ (9,838 MP3s)
  → Data/tone_perfect_metadata.csv

  → extract_features.py
  → Data/features.csv (9,837 rows × 27 features)

  → train_classifier.py
  → models/svm_classifier.pkl  ← ACTIVE
  → models/scaler.pkl
  → models/feature_cols.pkl

Chao (1968) tone letter system (55, 35, 214, 51)
  → generate_reference_contours.py
  → Data/reference_contours/tone_{1,2,3,4}.npz

app.py uses:
  - svm_classifier.pkl + scaler.pkl + feature_cols.pkl → classify learner recording
  - reference_contours/ → draw native reference pitch curve
  - word_list.json / word_list_disyllabic.json → word selection UI

AISHELL-1: Downloaded and explored in Week 8 but NOT used in final pipeline.
  Reason: sentence-level F0 has declination artifacts that corrupt tone shape.
  tone_dataset.csv exists but is unused.
```

---

## 4. CLASSIFIER DETAILS

**Model:** SVM with RBF kernel (C=10, gamma=scale)
**Training data:** Tone Perfect corpus — 4 speakers (FV1, FV2, MV1, MV2), 6,557 samples
**Test data:** 2 held-out speakers (FV3, MV3), 3,280 samples
**Test accuracy:** 91.95%

**27 features per utterance:**
- f0_01 ... f0_10: time-normalised F0 at 10 points (semitones, speaker-normalised)
- d0_01 ... d0_09: first-order delta (consecutive differences)
- f0_mean, f0_std, f0_min, f0_max, f0_slope: summary statistics
- duration: utterance length in seconds
- voiced_ratio: fraction of voiced frames
- f0_min_pos: normalised position of F0 minimum (KEY for T2/T3 separation)
  - T2 mean: 0.387 (minimum early = starts low then rises)
  - T3 mean: 0.570 (minimum mid-contour = dips then recovers)

**Confusion matrix (test set):**
```
     T1    T2    T3    T4
T1   810     6     2     2
T2     2   684   134     0
T3    15    69   732     4
T4     1     1    36   782
```
Main confusion: T2→T3 (134 errors, 16.3%) and T3→T2 (69 errors, 8.4%)

**Rule-based T2/T3 override in app.py:**
After SVM classification, if predicted=T2 AND f0_min_pos >= 0.40 AND f0_min < -1.5,
override to T3. This catches cases where strong recovery rise makes T3 look like T2.

**Why SVM over MLP:** MLP tested at 90.52%. With only 6,557 training samples, SVM
outperforms MLP. Would need larger monosyllabic corpus for MLP to win.

---

## 5. APP ARCHITECTURE (app.py)

**Mode 1: Monosyllabic** (40 words, 10 per tone)
- 3-column layout: Target word | Mic button | Reference pitch shape
- Records audio → trim_silence() → extract_features() → classify() → plot_contour()
- Shows: pitch overlay chart, detected tone badge, confidence bars, feedback text

**Mode 2: Disyllabic** (20 words, NEW in Week 11)
- Same 3-column layout but shows both syllable tone labels
- Tone sandhi note shown for T3+T3 words
- Records full word → extract_features_disyllabic() splits at energy minimum
  in middle 40% of recording → classifies each half independently
- Shows: two result panels side by side (one per syllable)

**Key functions:**
- trim_silence(snd): finds first/last voiced frames, extracts ±50ms window
- extract_features_from_sound(snd, feature_cols): extracts 27 features from Sound object
- extract_features(wav_bytes, feature_cols): entry point for monosyllabic (bytes → Sound)
- extract_features_disyllabic(wav_bytes, feature_cols): splits word, returns (f1,c1,f2,c2)
- classify(features, feature_cols, clf, scaler): SVM + T2/T3 rule override
- plot_contour(...): matplotlib figure with red learner + blue reference curves
- render_syllable_result(...): renders chart + badge + feedback for one syllable
- get_feedback(predicted, target): returns plain-language correction message

**Known issue:** T3 words with semivowel onset (e.g. wǔ) have distorted f0_min_pos
due to 'w' glide. Removed wǔ from word list, replaced with yuǎn.

---

## 6. WORD LISTS

**word_list.json** — 40 monosyllabic words (10 per tone T1-T4)
Format: {"pinyin": "māo", "tone": 1, "character": "猫", "meaning": "cat"}

**word_list_disyllabic.json** — 20 disyllabic words
Format: {"pinyin": "nǐhǎo", "tones": [3,3], "syllables": ["nǐ","hǎo"],
         "character": "你好", "meaning": "hello", "tone_combo": "T3+T3", "sandhi": true}
Tone 5 = neutral tone (no classification target, app shows info message)

---

## 7. REFERENCE CONTOURS

Generated by generate_reference_contours.py using Chao (1968) 5-level tone letter system:
- T1: 55 (high level) → flat at +3 semitones
- T2: 35 (high rising) → rises from 0 to +3
- T3: 214 (low dipping) → starts mid, dips to -3, rises to -0.84
- T4: 51 (high falling) → falls from +3 to -3

Saved as .npz with keys: mean (shape 100,), std (zeros), n_samples (0=canonical), n_points (100)
Referenced in app.py via: reference_contours[tone_num] → loaded from Data/reference_contours/

---

## 8. WEEK STATUS

| Week | Tasks | Status |
|------|-------|--------|
| 8 | Environment setup, AISHELL-1 exploration, Tone Perfect corpus download, reference contours | ✅ Complete |
| 9 | Feature extraction (27 features), SVM+MLP training (91.95%), confusion matrix, T2/T3 iteration | ✅ Complete |
| 10 | Streamlit app (monosyllabic), silence trimming, T2/T3 rule fix, word list (40 words), Milestone 1 slides | ✅ Complete (video pending) |
| 11 | Disyllabic word list (20 words), disyllabic mode in app | 🔄 In progress |
| 11 remaining | Plain-language cues for all T1-T4 pairs (awaiting mentor feedback), UI polish, Status Check 4 | ⏳ Pending |
| 12 | Pre/post perception test design, TAM survey, consent materials, recruitment | ⏳ Pending |
| 13 | Run 6-10 evaluation sessions, data collection, Milestone 2 | ⏳ Pending |
| 14-16 | Analysis, paper writing, final submission | ⏳ Pending |

---

## 9. PENDING DECISIONS / OPEN QUESTIONS

1. **Task 11.1 (feedback cues):** Waiting for mentor/peer feedback from Milestone 1 before
   finalising all 12 T→T error message pairs. Currently only 8 of 12 pairs have specific messages.

2. **Task 11.4 (UI polish):** Waiting for Milestone 1 feedback to know what to change.

3. **Disyllabic syllable splitting:** Currently uses energy minimum in middle 40% of recording.
   This is a heuristic — may not work perfectly for all words. If issues arise, consider
   asking learner to pause briefly between syllables or record each syllable separately.

4. **Bu et al. (2025) corpus:** Author was contacted but no response. Not blocking anything —
   AISHELL-1 dev/test splits used for generalisation testing instead.

---

## 10. ENVIRONMENT SETUP

```bash
cd "/Users/bharath/Documents/Old_Desktop/Apps/Coursera/GTech/EdTech/Assignments/Project"
source venv/bin/activate
streamlit run app.py
```

Python 3.14, venv at Project/venv/
Key packages: streamlit, praat-parselmouth, scikit-learn, numpy, matplotlib,
              audio-recorder-streamlit, pypinyin, scipy, tqdm, requests

---

## 11. IMPORTANT ARCHITECTURAL DECISIONS (for paper/defence)

1. **Tone Perfect over AISHELL-1 for training:** Monosyllabic isolated recordings
   match inference context. Sentence-level F0 has declination artifacts.

2. **SVM over deep learning:** 9,838 samples too small for reliable deep learning.
   SVM achieves 91.95% speaker-independent accuracy.

3. **Canonical contours over corpus-derived:** Sentence-level F0 extraction gave
   wrong shapes (all tones showed falling pattern due to declination). Chao (1968)
   canonical templates are theoretically grounded and match textbook descriptions.

4. **f0_min_pos feature:** Key T2/T3 discriminator. Position of F0 minimum:
   T2 ≈ 0.387 (early), T3 ≈ 0.570 (mid-contour). Added after live testing showed
   T3 misclassification despite correct production.

5. **Rule-based T2/T3 override:** SVM over-relies on slope; strong T3 recovery rise
   triggers T2 prediction. Rule: if predicted=T2 AND min_pos≥0.40 AND f0_min<-1.5 → T3.

---

## 12. CITATIONS USED SO FAR

Key citations for methods:
- Chao, Y.R. (1968). A grammar of spoken Chinese. UC Press. [tone letter system]
- Van Heuven et al. (2003). Tone Perfect corpus. Behavior Research Methods. [training data]
- Amrate & Tsai (2025). CAPT systematic review. ReCALL. [CAPT context]
- Davis (1989). TAM model. MIS Quarterly. [evaluation framework]
- Schmidt (1990). Noticing hypothesis. Applied Linguistics. [SLA theory]
- Li et al. (2019). Mandarin tone mispronunciation detection. IEEE/ACM TASLP. [classifier]
- Rogerson-Revell (2021). CAPT current issues. RELC Journal. [feedback design]

Full reference list in Project_Proposal_bjagadish3.docx

---

## 13. HOW TO RESUME IN A NEW CLAUDE SESSION

1. Read this file first (PROJECT_CONTEXT.md)
2. Read app.py to understand current app state
3. Check what week task we are on and what's pending
4. Current focus: Week 11 tasks
   - 11.1: Plain-language correction cues (waiting for mentor feedback)
   - 11.2/11.3: Disyllabic words DONE — test app.py disyllabic mode
   - 11.4: UI polish (waiting for Milestone 1 feedback)
   - 11.5: Status Check 4 (Bharath writes this)
5. Next major milestone: Week 12 — evaluation design (perception test, TAM survey)
