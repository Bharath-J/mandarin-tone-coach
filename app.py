"""
app.py
Mandarin Tone Coach — Streamlit application
Tasks 10.1–10.4, 11.2–11.3: Monosyllabic + disyllabic word practice

Usage:
    streamlit run app.py
"""

import json
import pickle
import tempfile
import numpy as np
import parselmouth
import matplotlib.pyplot as plt
import streamlit as st
from pathlib import Path
from audio_recorder_streamlit import audio_recorder

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_DIR        = Path(__file__).parent
MODELS_DIR         = PROJECT_DIR / "models"
CONTOURS_DIR       = PROJECT_DIR / "Data" / "reference_contours"
WORD_LIST_MONO     = PROJECT_DIR / "word_list.json"
WORD_LIST_DI       = PROJECT_DIR / "word_list_disyllabic.json"

# ── Config ─────────────────────────────────────────────────────────────────────
PITCH_FLOOR  = 75
PITCH_CEIL   = 500
N_POINTS     = 10
TONE_NAMES   = {1: "Tone 1 (flat)", 2: "Tone 2 (rising)",
                3: "Tone 3 (dipping)", 4: "Tone 4 (falling)", 5: "Neutral"}
TONE_COLORS  = {1: "#2196F3", 2: "#4CAF50", 3: "#FF9800", 4: "#F44336", 5: "#9E9E9E"}
TONE_DESC    = {
    1: "High and flat — keep your pitch steady and high throughout.",
    2: "Rising — start mid and rise to high, like asking a question in English.",
    3: "Dipping — start mid, drop low, then rise back up. It takes more time than other tones.",
    4: "Falling — start high and drop sharply to low.",
    5: "Neutral — short and unstressed, no specific pitch target.",
}

# ── Load models ────────────────────────────────────────────────────────────────
@st.cache_resource
def load_models():
    with open(MODELS_DIR / "svm_classifier.pkl", "rb") as f:
        clf = pickle.load(f)
    with open(MODELS_DIR / "scaler.pkl", "rb") as f:
        scaler = pickle.load(f)
    with open(MODELS_DIR / "feature_cols.pkl", "rb") as f:
        feature_cols = pickle.load(f)
    return clf, scaler, feature_cols

@st.cache_resource
def load_reference_contours():
    contours = {}
    for tone in [1, 2, 3, 4]:
        data = np.load(CONTOURS_DIR / f"tone_{tone}.npz")
        contours[tone] = data["mean"]
    return contours

@st.cache_data
def load_word_lists():
    with open(WORD_LIST_MONO, encoding="utf-8") as f:
        mono = json.load(f)
    with open(WORD_LIST_DI, encoding="utf-8") as f:
        di = json.load(f)
    return mono, di

# ── Silence trimming ───────────────────────────────────────────────────────────
def trim_silence(snd: parselmouth.Sound) -> parselmouth.Sound:
    try:
        pitch = snd.to_pitch(pitch_floor=PITCH_FLOOR, pitch_ceiling=PITCH_CEIL)
        f0    = pitch.selected_array["frequency"]
        times = pitch.xs()
        voiced_mask  = f0 > 0
        if voiced_mask.sum() < 5:
            return snd
        voiced_times = times[voiced_mask]
        t_start = max(0.0, voiced_times[0]  - 0.05)
        t_end   = min(snd.duration, voiced_times[-1] + 0.05)
        if t_end - t_start < 0.1:
            return snd
        return snd.extract_part(from_time=t_start, to_time=t_end,
                                preserve_times=False)
    except Exception:
        return snd

# ── Feature extraction (single syllable) ──────────────────────────────────────
def extract_features_from_sound(snd: parselmouth.Sound,
                                 feature_cols: list) -> tuple[dict, np.ndarray] | tuple[None, None]:
    try:
        pitch = snd.to_pitch(pitch_floor=PITCH_FLOOR, pitch_ceiling=PITCH_CEIL)
        f0    = pitch.selected_array["frequency"]

        voiced       = f0[f0 > 0]
        voiced_ratio = len(voiced) / max(len(f0), 1)

        if len(voiced) < 5:
            return None, None

        mean_hz = np.mean(voiced)
        if mean_hz <= 0:
            return None, None

        indices     = np.arange(len(f0))
        voiced_mask = f0 > 0
        f0_interp   = np.interp(indices, indices[voiced_mask], f0[voiced_mask])
        f0_st       = 12 * np.log2(f0_interp / mean_hz)

        x_orig  = np.linspace(0, 1, len(f0_st))
        x_norm  = np.linspace(0, 1, N_POINTS)
        f0_norm = np.interp(x_norm, x_orig, f0_st)
        delta   = np.diff(f0_norm)

        features = {}
        for i, val in enumerate(f0_norm):
            features[f"f0_{i+1:02d}"] = float(val)
        for i, val in enumerate(delta):
            features[f"d0_{i+1:02d}"] = float(val)
        features["f0_mean"]      = float(np.mean(f0_st))
        features["f0_std"]       = float(np.std(f0_st))
        features["f0_min"]       = float(np.min(f0_st))
        features["f0_max"]       = float(np.max(f0_st))
        x_idx = np.arange(len(f0_st))
        features["f0_slope"]     = float(np.polyfit(x_idx, f0_st, 1)[0] * len(f0_st))
        features["duration"]     = float(snd.duration)
        features["voiced_ratio"] = float(voiced_ratio)
        features["f0_min_pos"]   = float(np.argmin(f0_norm) / (N_POINTS - 1))

        return features, f0_norm

    except Exception as e:
        st.error(f"Feature extraction error: {e}")
        return None, None

def extract_features(wav_bytes: bytes,
                     feature_cols: list) -> tuple[dict, np.ndarray] | tuple[None, None]:
    """Entry point for monosyllabic extraction from raw bytes."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name
        snd = parselmouth.Sound(tmp_path)
        snd = trim_silence(snd)
        return extract_features_from_sound(snd, feature_cols)
    except Exception as e:
        st.error(f"Feature extraction error: {e}")
        return None, None

def extract_features_disyllabic(wav_bytes: bytes,
                                  feature_cols: list,
                                  tones: list = None) -> tuple | None:
    """
    Split a disyllabic recording into two halves using energy-based
    syllable boundary detection, then extract features from each half.
    Returns (features1, f0_norm1, features2, f0_norm2) or None on failure.
    tones: list of two tone numbers (e.g. [3, 5]) — used to widen the
           boundary search window when the second syllable is neutral tone,
           which is short and sits late in the recording.
    """
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        snd = parselmouth.Sound(tmp_path)
        snd = trim_silence(snd)

        dur = snd.duration
        if dur < 0.2:
            return None

        # Find syllable boundary using energy minimum in middle third
        # This avoids cutting at the very start/end where energy is always low
        samples    = snd.values[0]
        sr         = snd.sampling_frequency
        n          = len(samples)

        # Compute RMS energy in 20ms windows
        win_size = int(0.02 * sr)
        energies = []
        for i in range(0, n - win_size, win_size // 2):
            window = samples[i:i + win_size]
            energies.append((i / sr, float(np.sqrt(np.mean(window ** 2)))))

        # When the second syllable is neutral tone (e.g. wǒmen, péngyou) it is
        # short and unstressed, so the syllable boundary sits late in the
        # recording — often at 70-80% of duration, outside the default 30-70%
        # window.  Widen the upper bound to 85% for these words.
        second_is_neutral = (tones is not None and len(tones) == 2 and tones[1] == 5)
        mid_start = dur * 0.25
        mid_end   = dur * 0.85 if second_is_neutral else dur * 0.70
        mid_energies = [(t, e) for t, e in energies if mid_start <= t <= mid_end]

        if mid_energies:
            boundary_t = min(mid_energies, key=lambda x: x[1])[0]

            # Check if the energy dip is shallow (voiced-to-voiced transition,
            # e.g. nánrén where n→r never drops in energy).
            # If so, fall back to pitch discontinuity: at a syllable boundary
            # F0 typically resets downward even when energy stays high.
            all_energies_vals = [e for _, e in energies]
            max_e = max(all_energies_vals) if all_energies_vals else 1.0
            min_e = min(e for _, e in mid_energies)
            dip_ratio = min_e / max_e if max_e > 0 else 1.0

            if dip_ratio > 0.55:   # shallow dip → try pitch reset instead
                try:
                    pitch   = snd.to_pitch(pitch_floor=PITCH_FLOOR, pitch_ceiling=PITCH_CEIL)
                    f0_arr  = pitch.selected_array["frequency"]
                    t_arr   = pitch.xs()
                    mid_mask = (t_arr >= mid_start) & (t_arr <= mid_end)
                    mid_t    = t_arr[mid_mask]
                    mid_f0   = f0_arr[mid_mask]
                    voiced   = mid_f0 > 0
                    if voiced.sum() > 4:
                        v_t  = mid_t[voiced]
                        v_f0 = mid_f0[voiced]
                        diffs = np.diff(v_f0)
                        # Largest downward F0 jump = pitch reset at syllable boundary
                        if diffs.min() < -15:   # at least 15 Hz drop
                            boundary_t = float(v_t[np.argmin(diffs)])
                except Exception:
                    pass   # keep energy-based boundary on any error
        else:
            boundary_t = dur / 2

        # Extract each syllable with small padding
        pad = 0.03
        snd1 = snd.extract_part(from_time=0, to_time=min(boundary_t + pad, dur),
                                 preserve_times=False)
        snd2 = snd.extract_part(from_time=max(0, boundary_t - pad), to_time=dur,
                                 preserve_times=False)

        # Trim voiceless onsets/offsets from each syllable so that the pitch
        # contour is anchored at actual voicing (e.g. strips the 'h-' in 好).
        snd1 = trim_silence(snd1)
        snd2 = trim_silence(snd2)

        f1, c1 = extract_features_from_sound(snd1, feature_cols)
        f2, c2 = extract_features_from_sound(snd2, feature_cols)

        if f1 is None or f2 is None:
            return None

        return f1, c1, f2, c2

    except Exception as e:
        st.error(f"Disyllabic extraction error: {e}")
        return None

# ── Classify one syllable ──────────────────────────────────────────────────────
def classify(features: dict, feature_cols: list,
             clf, scaler) -> tuple[int, np.ndarray]:
    feature_vector = np.array([[features[c] for c in feature_cols]])
    feature_scaled = scaler.transform(feature_vector)
    predicted      = int(clf.predict(feature_scaled)[0])

    # T2/T3 rule-based correction
    if predicted == 2:
        if features["f0_min_pos"] >= 0.40 and features["f0_min"] < -1.5:
            predicted = 3

    # T1/T2 correction: compressed pitch range (common in disyllabic second syllables)
    # If classified as T1 but pitch is consistently rising, likely a T2 with small range.
    if predicted == 1:
        pos_deltas = sum(1 for i in range(1, 10) if features.get(f"d0_{i:02d}", 0) > 0)
        if features["f0_slope"] > 1.0 and pos_deltas >= 7 and features["f0_min_pos"] < 0.35:
            predicted = 2

    # T4/T2 correction: rise-then-fall artefact from syllable boundary placed too late.
    # Genuine T4 starts HIGH (f0_01 > 0, minimum near end).
    # A T2 whose snd1 window accidentally includes the falling onset of the next syllable
    # looks like rise-then-fall → T4, but its first frame is LOW (f0_01 < 0) and
    # the minimum is near the start (f0_min_pos < 0.35).
    if predicted == 4:
        if features["f0_min_pos"] < 0.35 and features["f0_01"] < -0.5:
            predicted = 2

    # Confidence scores
    if hasattr(clf, "decision_function"):
        scores     = clf.decision_function(feature_scaled)[0]
        probs      = np.exp(scores) / np.sum(np.exp(scores))
    else:
        probs = np.ones(4) / 4

    # Swap T2/T3 scores if override applied
    raw = int(clf.predict(feature_scaled)[0])
    if raw != predicted:
        probs = list(probs)
        probs[raw - 1], probs[predicted - 1] = probs[predicted - 1], probs[raw - 1]
        probs = np.array(probs)

    return predicted, probs

# ── Pitch contour chart ────────────────────────────────────────────────────────
def plot_contour(learner_contour: np.ndarray, reference_contour: np.ndarray,
                 predicted_tone: int, target_tone: int,
                 title: str = "Pitch Contour") -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 3.5))
    x = np.linspace(0, 100, N_POINTS)

    ref_100 = np.interp(np.linspace(0, 1, 100),
                        np.linspace(0, 1, len(reference_contour)),
                        reference_contour)
    ax.plot(np.arange(100), ref_100, color="#2196F3", linewidth=2.5,
            linestyle="--", label=f"Reference ({TONE_NAMES[target_tone]})", alpha=0.8)

    window   = min(3, len(learner_contour))
    pad      = window // 2
    padded   = np.pad(learner_contour, pad, mode="edge")
    smoothed = np.convolve(padded, np.ones(window)/window, mode="valid")[:len(learner_contour)]
    ax.plot(x, smoothed, color="#F44336", linewidth=2.5,
            label="Your recording", alpha=0.9)

    ax.set_xlabel("Time (normalised)", fontsize=10)
    ax.set_ylabel("Pitch (semitones)", fontsize=10)
    ax.set_title(title, fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color="gray", linewidth=0.8, linestyle=":")

    correct = predicted_tone == target_tone
    fig.patch.set_facecolor("#e8f5e9" if correct else "#fce4ec")
    ax.set_facecolor("#e8f5e9" if correct else "#fce4ec")
    plt.tight_layout()
    return fig

# ── Feedback message ───────────────────────────────────────────────────────────
def get_feedback(predicted: int, target: int) -> str:
    if predicted == target:
        return f"✅ Correct! You produced {TONE_NAMES[target]} accurately."

    messages = {
        (2, 3): "Your pitch started falling before rising — try to start the rise earlier and sustain it higher.",
        (3, 2): "Your pitch dipped too low in the middle. For Tone 2, keep rising steadily without the dip.",
        (1, 4): "Your pitch fell at the end. For Tone 1, keep your pitch high and flat throughout.",
        (4, 1): "Your pitch started high but didn't fall sharply enough. For Tone 4, drop quickly from high to low.",
        (1, 2): "Your pitch was flat, but Tone 2 needs a clear rise. Start mid and push up to high.",
        (2, 1): "Your pitch rose, but Tone 1 should stay flat and high. Don't let it rise.",
        (3, 4): "Your pitch dipped but didn't fall far enough. Tone 4 needs a sharp, steep fall.",
        (4, 3): "Your pitch fell, but Tone 3 needs a dip-and-recover shape. Drop low then come back up.",
        (1, 3): "Your pitch was flat. Tone 3 needs a clear dip down then a rise back up.",
        (4, 2): "Your pitch fell, but Tone 2 needs to rise. Start mid and go up.",
        (2, 4): "Your pitch rose, but Tone 4 should fall sharply from high to low.",
        (3, 1): "Your pitch moved too much. Tone 1 stays flat and high — no dipping.",
    }

    key      = (predicted, target)
    specific = messages.get(key, "")
    general  = f"The system detected {TONE_NAMES[predicted]}, but the target is {TONE_NAMES[target]}."
    tip      = f"\n\n💡 **How {TONE_NAMES[target]} should sound:** {TONE_DESC[target]}"
    return f"❌ {general} {specific}{tip}"

# ── Render results for one syllable ───────────────────────────────────────────
def render_syllable_result(features, f0_contour, target_tone,
                            clf, scaler, feature_cols,
                            reference_contours, label: str,
                            accepted_tones: list = None):
    if target_tone == 5:
        st.info(f"**{label}:** Neutral tone — no pitch target to evaluate.")
        return

    if accepted_tones is None:
        accepted_tones = [target_tone]

    predicted, probs = classify(features, feature_cols, clf, scaler)
    correct = predicted in accepted_tones

    # If predicted is an accepted alternate tone (e.g. T2 sandhi form of T3),
    # compare the chart against that tone's reference so the overlay makes sense.
    chart_target = predicted if (correct and predicted != target_tone) else target_tone

    fig = plot_contour(f0_contour, reference_contours[chart_target],
                       predicted, chart_target, title=label)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    badge_color = "#4CAF50" if correct else "#F44336"
    st.markdown(
        f"<div style='text-align:center; margin:8px 0'>"
        f"<span style='background:{badge_color}; color:white; "
        f"padding:6px 16px; border-radius:12px; font-size:16px; font-weight:bold'>"
        f"Detected: {TONE_NAMES[predicted]}</span></div>",
        unsafe_allow_html=True
    )

    # Confidence bars (one per tone, T1–T4)
    bars_html = "<div style='margin:10px 0 14px 0'>"
    bars_html += "<div style='font-size:12px; color:#888; margin-bottom:5px'>Classifier confidence</div>"
    for tone_num in [1, 2, 3, 4]:
        pct      = float(probs[tone_num - 1]) * 100
        color    = TONE_COLORS[tone_num]
        bold     = "font-weight:bold" if tone_num == predicted else "font-weight:normal"
        bars_html += (
            f"<div style='display:flex; align-items:center; margin:3px 0'>"
            f"<span style='width:115px; font-size:12px; {bold}'>{TONE_NAMES[tone_num]}</span>"
            f"<div style='flex:1; background:#e0e0e0; border-radius:4px; height:13px; margin:0 6px'>"
            f"<div style='width:{pct:.1f}%; background:{color}; border-radius:4px; height:13px'></div>"
            f"</div>"
            f"<span style='width:38px; text-align:right; font-size:12px; {bold}'>{pct:.1f}%</span>"
            f"</div>"
        )
    bars_html += "</div>"
    st.markdown(bars_html, unsafe_allow_html=True)

    if correct and predicted != target_tone:
        feedback = (f"✅ Correct! You used the sandhi form ({TONE_NAMES[predicted]}). "
                    f"Both {TONE_NAMES[predicted]} and {TONE_NAMES[target_tone]} are accepted here.")
        st.success(feedback)
    else:
        feedback = get_feedback(predicted, target_tone)
        if correct:
            st.success(feedback)
        else:
            st.error(feedback)

# ── Main app ───────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="Mandarin Tone Coach", page_icon="🎵",
                       layout="centered")

    st.markdown(
        "<style>#MainMenu{visibility:hidden}header{visibility:hidden}</style>",
        unsafe_allow_html=True,
    )

    st.title("🎵 Mandarin Tone Coach")
    st.markdown("Practice Mandarin tones with instant pitch feedback.")

    clf, scaler, feature_cols = load_models()
    reference_contours        = load_reference_contours()
    mono_list, di_list        = load_word_lists()

    # ── Sidebar ────────────────────────────────────────────────────────────────
    st.sidebar.header("Practice Settings")

    with st.sidebar.expander("What are Mandarin tones?"):
        st.markdown(
            "Mandarin is a **tonal language** — the pitch of your voice changes the meaning "
            "of a word. There are 4 main tones:\n\n"
            "- **Tone 1 (flat)** — High and steady pitch, like holding a musical note.\n"
            "- **Tone 2 (rising)** — Pitch rises, like the end of an English question.\n"
            "- **Tone 3 (dipping)** — Pitch dips down then rises back up.\n"
            "- **Tone 4 (falling)** — Pitch falls sharply from high to low.\n\n"
            "The **Reference Shape** shown for each word is a guide to the pitch curve you "
            "should aim for. Record yourself and compare your curve to the reference."
        )

    mode = st.sidebar.radio("Word type", ["Monosyllabic", "Disyllabic"])

    if mode == "Monosyllabic":
        st.sidebar.caption(
            "Filter by tone to focus your practice. "
            "Not sure which tone to pick? Start with **All tones**."
        )
        tone_filter = st.sidebar.selectbox(
            "Filter by tone",
            ["All tones", "Tone 1 (flat)", "Tone 2 (rising)",
             "Tone 3 (dipping)", "Tone 4 (falling)"]
        )
        tone_map      = {"All tones": None, "Tone 1 (flat)": 1,
                         "Tone 2 (rising)": 2, "Tone 3 (dipping)": 3,
                         "Tone 4 (falling)": 4}
        selected_tone = tone_map[tone_filter]
        word_pool     = [w for w in mono_list
                         if selected_tone is None or w["tone"] == selected_tone]
        labels        = [f"{w['character']} {w['pinyin']} — {w['meaning']}"
                         for w in word_pool]
    else:
        combo_filter = st.sidebar.selectbox(
            "Filter by first syllable tone",
            ["All", "T1", "T2", "T3", "T4", "Sandhi (T3+T3)"]
        )
        if combo_filter == "All":
            word_pool = di_list
        elif combo_filter == "Sandhi (T3+T3)":
            word_pool = [w for w in di_list if w["sandhi"]]
        else:
            t = int(combo_filter[1])
            word_pool = [w for w in di_list if w["tones"][0] == t]
        labels = [f"{w['character']} {w['pinyin']} — {w['meaning']}"
                  for w in word_pool]

    if not word_pool:
        st.warning("No words found for this filter.")
        return

    idx  = st.sidebar.selectbox("Choose a word", range(len(labels)),
                                 format_func=lambda i: labels[i])
    word = word_pool[idx]

    # ── Main panel ─────────────────────────────────────────────────────────────
    if mode == "Monosyllabic":
        word_tone = word["tone"]
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            st.markdown("### Target Word")
            st.markdown(f"<div style='font-size:64px; text-align:center'>{word['character']}</div>",
                        unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:24px; text-align:center; color:#666'>{word['pinyin']}</div>",
                        unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:16px; text-align:center; color:#888'>{word['meaning']}</div>",
                        unsafe_allow_html=True)
            st.markdown(
                f"<div style='margin-top:12px; text-align:center'>"
                f"<span style='background:{TONE_COLORS[word_tone]}; color:white; "
                f"padding:4px 12px; border-radius:12px; font-size:14px'>"
                f"{TONE_NAMES[word_tone]}</span></div>",
                unsafe_allow_html=True
            )

        with col2:
            st.markdown("### 🎙 Record")
            st.markdown("Press the mic, say the word, press again to stop.")
            audio_bytes = audio_recorder(
                text="", recording_color="#F44336", neutral_color="#2196F3",
                icon_size="3x", pause_threshold=3.0,
                key=f"mono_{word['pinyin']}_{word_tone}",
            )
            st.caption("💡 Quiet room · speak clearly · sustain the vowel 0.5s")

        with col3:
            st.markdown("### Reference Shape")
            st.caption(TONE_DESC[word_tone])
            ref_contour  = reference_contours[word_tone]
            fig_ref, ax_ref = plt.subplots(figsize=(3, 2))
            ref_100 = np.interp(np.linspace(0, 1, 100),
                                np.linspace(0, 1, len(ref_contour)), ref_contour)
            ax_ref.plot(np.arange(100), ref_100, color=TONE_COLORS[word_tone], linewidth=2.5)
            ax_ref.set_xlabel("Time →", fontsize=8)
            ax_ref.set_ylabel("Pitch", fontsize=8)
            ax_ref.set_yticks([])
            ax_ref.set_xticks([])
            ax_ref.grid(True, alpha=0.2)
            ax_ref.set_facecolor("#f8f9fa")
            fig_ref.patch.set_facecolor("#f8f9fa")
            plt.tight_layout()
            st.pyplot(fig_ref, use_container_width=True)
            plt.close(fig_ref)

        st.divider()

        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav")
            with st.spinner("Analysing..."):
                features, f0_contour = extract_features(audio_bytes, feature_cols)

            if features is None:
                st.warning("⚠️ Could not detect enough voiced speech. Speak clearly and sustain the vowel.")
            elif features["voiced_ratio"] < 0.4:
                st.warning("⚠️ Recording too noisy or quiet. Try a quieter environment or headset mic.")
            else:
                st.divider()
                st.markdown("### 📊 Results")
                render_syllable_result(features, f0_contour, word_tone,
                                       clf, scaler, feature_cols,
                                       reference_contours, "Your recording")

    else:
        # ── Disyllabic mode ────────────────────────────────────────────────────
        tones   = word["tones"]
        syls    = word["syllables"]
        t1, t2  = tones[0], tones[1]

        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            st.markdown("### Target Word")
            st.markdown(f"<div style='font-size:56px; text-align:center'>{word['character']}</div>",
                        unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:22px; text-align:center; color:#666'>{word['pinyin']}</div>",
                        unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:14px; text-align:center; color:#888'>{word['meaning']}</div>",
                        unsafe_allow_html=True)
            st.markdown(
                f"<div style='margin-top:8px; display:flex; flex-wrap:wrap; "
                f"justify-content:center; gap:4px'>"
                f"<span style='background:{TONE_COLORS[t1]}; color:white; "
                f"padding:3px 10px; border-radius:10px; font-size:12px; white-space:nowrap'>"
                f"{syls[0]} · {TONE_NAMES[t1]}</span>"
                f"<span style='background:{TONE_COLORS[t2]}; color:white; "
                f"padding:3px 10px; border-radius:10px; font-size:12px; white-space:nowrap'>"
                f"{syls[1]} · {TONE_NAMES[t2]}</span></div>",
                unsafe_allow_html=True
            )

        with col2:
            st.markdown("### 🎙 Record")
            st.markdown("Say the **full word** — both syllables together.")
            audio_bytes = audio_recorder(
                text="", recording_color="#F44336", neutral_color="#2196F3",
                icon_size="3x", pause_threshold=3.0,
                key=f"di_{word['pinyin']}",
            )
            st.caption("💡 Say the word naturally without pausing between syllables")

        with col3:
            st.markdown("### Reference Shapes")
            for tone_num, syl in [(t1, syls[0]), (t2, syls[1])]:
                if tone_num == 5:
                    st.caption(f"{syl}: neutral tone")
                    continue
                fig_r, ax_r = plt.subplots(figsize=(3, 1.5))
                ref_c = reference_contours[tone_num]
                ref_100 = np.interp(np.linspace(0, 1, 100),
                                    np.linspace(0, 1, len(ref_c)), ref_c)
                ax_r.plot(np.arange(100), ref_100, color=TONE_COLORS[tone_num], linewidth=2)
                ax_r.set_title(f"{syl} — {TONE_NAMES[tone_num]}", fontsize=8)
                ax_r.set_yticks([])
                ax_r.set_xticks([])
                ax_r.grid(True, alpha=0.2)
                ax_r.set_facecolor("#f8f9fa")
                fig_r.patch.set_facecolor("#f8f9fa")
                plt.tight_layout()
                st.pyplot(fig_r, use_container_width=True)
                plt.close(fig_r)

        # Tone sandhi note
        if word.get("sandhi"):
            st.info(
                "🔔 **Tone sandhi:** This word is written as T3+T3, but in natural speech "
                "the first syllable is often pronounced as T2. Both T3+T3 (citation form) "
                "and T2+T3 (sandhi form) are accepted here."
            )

        st.divider()

        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav")
            with st.spinner("Analysing both syllables..."):
                result = extract_features_disyllabic(audio_bytes, feature_cols, tones=tones)

            if result is None:
                st.warning("⚠️ Could not analyse the recording. Speak clearly and say both syllables together.")
            else:
                f1, c1, f2, c2 = result
                st.divider()
                st.markdown("### 📊 Results")

                scol1, scol2 = st.columns(2)
                with scol1:
                    st.markdown(f"**Syllable 1: {syls[0]}**")
                    # For T3+T3 sandhi words, accept T2 as correct for first syllable
                    accepted_1 = [2, 3] if word.get("sandhi") and t1 == 3 else None
                    render_syllable_result(f1, c1, t1, clf, scaler,
                                           feature_cols, reference_contours,
                                           f"Syllable 1: {syls[0]}",
                                           accepted_tones=accepted_1)
                with scol2:
                    st.markdown(f"**Syllable 2: {syls[1]}**")
                    render_syllable_result(f2, c2, t2, clf, scaler,
                                           feature_cols, reference_contours,
                                           f"Syllable 2: {syls[1]}")

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown(
        "<div style='text-align:center; color:#aaa; font-size:12px'>"
        "Mandarin Tone Coach · CS6460 EdTech · Georgia Tech · 2026"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
