"""
perception_test.py
Mandarin Tone Perception Test — Pre/Post Assessment
CS6460 Educational Technology, Georgia Tech, 2026

20 audio clips per session (5 per tone). No feedback given during the test.
Responses saved to results/perception_<participant_id>_<form>.csv

Usage:
    streamlit run perception_test.py
"""

import csv
import json
import random
from datetime import datetime
from pathlib import Path

import streamlit as st

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_DIR   = Path(__file__).parent
STIMULI_FILE  = PROJECT_DIR / "perception_test_stimuli.json"
AUDIO_DIR     = PROJECT_DIR / "Data" / "perception_audio"
RESULTS_DIR   = PROJECT_DIR / "results"

# ── Config ─────────────────────────────────────────────────────────────────────
TONE_LABELS = {
    1: "Tone 1 — flat (ā)",
    2: "Tone 2 — rising (á)",
    3: "Tone 3 — dipping (ǎ)",
    4: "Tone 4 — falling (à)",
}

# ── Helpers ────────────────────────────────────────────────────────────────────
@st.cache_data
def load_stimuli():
    with open(STIMULI_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_response(participant_id: str, form: str, item_num: int,
                  item: dict, response: int) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    out_file   = RESULTS_DIR / f"perception_{participant_id}_{form}.csv"
    fieldnames = ["participant_id", "form", "item_num", "syllable",
                  "speaker", "gender", "target_tone", "response",
                  "correct", "timestamp"]
    write_header = not out_file.exists()
    with open(out_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "participant_id": participant_id,
            "form":           form,
            "item_num":       item_num,
            "syllable":       item["syllable"],
            "speaker":        item["speaker"],
            "gender":         item["gender"],
            "target_tone":    item["tone"],
            "response":       response,
            "correct":        int(response == item["tone"]),
            "timestamp":      datetime.now().isoformat(),
        })


# ── Screens ────────────────────────────────────────────────────────────────────
def show_intro():
    st.markdown(
        "Listen to each audio clip and select the Mandarin tone you hear. "
        "**No feedback will be given during the test.** "
        "There are **20 items** in total."
    )
    st.info(
        "**Tone reminder:**\n"
        "- **Tone 1** — high and flat (ā)\n"
        "- **Tone 2** — rising, like a question (á)\n"
        "- **Tone 3** — dips low then rises (ǎ)\n"
        "- **Tone 4** — falls sharply from high to low (à)"
    )
    st.divider()

    participant_id = st.text_input("Participant ID (e.g. P01)")
    form_choice    = st.radio("Test form", ["Form A  (pre-test)", "Form B  (post-test)"],
                               horizontal=True)
    form_key       = "A" if form_choice.startswith("Form A") else "B"

    if st.button("▶ Start test", disabled=not participant_id.strip(),
                 use_container_width=True, type="primary"):
        stimuli   = load_stimuli()
        items     = list(stimuli[form_key])          # copy so shuffle is safe
        rng       = random.Random(participant_id.strip())
        rng.shuffle(items)

        st.session_state.participant_id = participant_id.strip()
        st.session_state.form           = form_key
        st.session_state.items          = items
        st.session_state.item_idx       = 0
        st.session_state.phase          = "test"
        st.rerun()


def show_test():
    idx   = st.session_state.item_idx
    items = st.session_state.items
    total = len(items)
    item  = items[idx]

    # Progress
    st.progress(idx / total, text=f"Item {idx + 1} of {total}")
    st.divider()

    # Audio
    audio_path = AUDIO_DIR / item["filename"]
    if audio_path.exists():
        st.markdown("#### 🎧 Listen to the audio clip")
        with open(audio_path, "rb") as f:
            st.audio(f.read(), format="audio/mp3")
    else:
        st.error(f"Audio file not found: {audio_path.name}")
        st.stop()

    st.markdown("#### Which tone did you hear?")

    cols = st.columns(4)
    for i, (tone_num, label) in enumerate(TONE_LABELS.items()):
        if cols[i].button(label, key=f"btn_{tone_num}_{idx}",
                          use_container_width=True):
            save_response(st.session_state.participant_id,
                          st.session_state.form,
                          idx + 1, item, tone_num)
            st.session_state.item_idx += 1
            if st.session_state.item_idx >= total:
                st.session_state.phase = "done"
            st.rerun()


def show_done():
    st.success("✅ Test complete — thank you for participating!")
    st.markdown(
        f"Your responses have been recorded for participant "
        f"**{st.session_state.participant_id}** (Form **{st.session_state.form}**)."
    )
    st.balloons()
    if st.button("Start a new session"):
        for key in ["participant_id", "form", "items", "item_idx", "phase"]:
            st.session_state.pop(key, None)
        st.rerun()


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="Tone Perception Test", page_icon="🎧",
                       layout="centered")
    st.title("🎧 Mandarin Tone Perception Test")

    if "phase" not in st.session_state:
        st.session_state.phase = "intro"

    if st.session_state.phase == "intro":
        show_intro()
    elif st.session_state.phase == "test":
        show_test()
    else:
        show_done()


if __name__ == "__main__":
    main()
