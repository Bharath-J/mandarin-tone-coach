"""
perception_test.py
Mandarin Tone Perception Test — Pre/Post Assessment
CS6460 Educational Technology, Georgia Tech, 2026

12 audio clips per session (3 per tone). No feedback given during the test.
Participants navigate freely with Previous/Next, can change answers, and
submit only when all 12 items are answered.
Responses saved to results/perception_<participant_id>_<form>.csv

Usage:
    streamlit run perception_test.py
"""

import csv
import json
import random
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_DIR   = Path(__file__).parent
STIMULI_FILE  = PROJECT_DIR / "perception_test_stimuli.json"
AUDIO_DIR     = PROJECT_DIR / "Data" / "perception_audio"
RESULTS_DIR   = PROJECT_DIR / "results"

SHEET_ID = "1Tsmcof8GaDHV11roUZrxXGYk7yk43cJHhosnzdocvbs"
SCOPES   = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]

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


def _get_sheet():
    """Return the first worksheet of the results Google Sheet."""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1


def _ensure_header(ws) -> None:
    """Add header row if the sheet is empty."""
    if ws.row_count == 0 or not ws.row_values(1):
        ws.append_row(
            ["participant_id", "form", "item_num", "syllable",
             "speaker", "gender", "target_tone", "response",
             "correct", "timestamp"],
            value_input_option="RAW"
        )


def save_all_responses(participant_id: str, form: str,
                        test_items: list, answers: dict) -> None:
    timestamp = datetime.now().isoformat()
    rows = []
    for i, item in enumerate(test_items):
        response = answers.get(i)
        rows.append([
            participant_id,
            form,
            i + 1,
            item["syllable"],
            item["speaker"],
            item["gender"],
            item["tone"],
            response,
            int(response == item["tone"]) if response else 0,
            timestamp,
        ])

    # ── Primary: Google Sheets ──────────────────────────────────────────────
    try:
        ws = _get_sheet()
        _ensure_header(ws)
        ws.append_rows(rows, value_input_option="RAW")
        return
    except Exception as e:
        st.warning(f"Could not write to Google Sheets ({e}). Saving locally instead.")

    # ── Fallback: local CSV ─────────────────────────────────────────────────
    RESULTS_DIR.mkdir(exist_ok=True)
    out_file   = RESULTS_DIR / f"perception_{participant_id}_{form}.csv"
    fieldnames = ["participant_id", "form", "item_num", "syllable",
                  "speaker", "gender", "target_tone", "response",
                  "correct", "timestamp"]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(zip(fieldnames, row)))


# ── Screens ────────────────────────────────────────────────────────────────────
def show_intro():
    st.markdown(
        "Listen to each audio clip and select the Mandarin tone you hear. "
        "**No feedback will be given during the test.** "
        "There are **12 items** in total. You can go back and change answers before submitting."
    )
    st.info(
        "**Tone reminder:**\n"
        "- **Tone 1** — high and flat (ā)\n"
        "- **Tone 2** — rising, like a question (á)\n"
        "- **Tone 3** — dips low then rises (ǎ)\n"
        "- **Tone 4** — falls sharply from high to low (à)"
    )
    st.divider()

    # Determine form from URL query parameter (?form=A or ?form=B).
    # When locked by the URL the radio is hidden so participants cannot switch forms.
    url_form = st.query_params.get("form", "").upper()
    if url_form in ("A", "B"):
        form_key = url_form
        label    = "Pre-test (Form A)" if form_key == "A" else "Post-test (Form B)"
        st.markdown(f"**{label}**")
    else:
        # Fallback for direct access without a query parameter
        form_choice = st.radio("Test form", ["Form A  (pre-test)", "Form B  (post-test)"],
                                horizontal=True)
        form_key    = "A" if form_choice.startswith("Form A") else "B"

    if form_key == "A":
        if "auto_id" not in st.session_state:
            st.session_state["auto_id"] = uuid.uuid4().hex[:8].upper()
        participant_id = st.session_state["auto_id"]
    else:
        participant_id = st.text_input("Enter your participant ID from the pre-test (Form A)")
        if not participant_id.strip():
            st.warning("Please enter your Form A participant ID to continue.")

    if st.button("▶ Start test",
                 disabled=(form_key == "B" and not participant_id.strip()),
                 use_container_width=True, type="primary"):
        stimuli    = load_stimuli()
        test_items = list(stimuli[form_key])
        rng        = random.Random(participant_id.strip())
        rng.shuffle(test_items)

        st.session_state["participant_id"] = participant_id.strip()
        st.session_state["form"]           = form_key
        st.session_state["test_items"]     = test_items
        st.session_state["test_idx"]       = 0
        st.session_state["answers"]        = {}
        st.session_state["phase"]          = "test"
        st.rerun()


def show_test():
    if not st.session_state.get("test_items"):
        st.session_state["phase"] = "intro"
        st.rerun()
        return

    test_items = st.session_state["test_items"]
    answers    = st.session_state["answers"]
    total      = len(test_items)
    answered   = len(answers)

    st.progress(answered / total,
                text=f"{answered} of {total} answered")

    for idx, item in enumerate(test_items):
        st.divider()
        current    = answers.get(idx)
        status     = "✅" if current is not None else "⬜"
        st.markdown(f"**{status} Clip {idx + 1}**")

        audio_path = AUDIO_DIR / item["filename"]
        if audio_path.exists():
            with open(audio_path, "rb") as f:
                st.audio(f.read(), format="audio/mp3")
        else:
            st.error(f"Audio file not found: {audio_path.name}")
            st.stop()

        cols = st.columns(4)
        for i, (tone_num, label) in enumerate(TONE_LABELS.items()):
            btn_label = f"✓ {label}" if current == tone_num else label
            if cols[i].button(btn_label, key=f"btn_{tone_num}_{idx}",
                              use_container_width=True, type="secondary"):
                st.session_state["answers"][idx] = tone_num
                st.rerun()

    st.divider()
    all_done = answered == total
    if not all_done:
        st.caption(f"Please answer all {total} clips before submitting.")
    if st.button("Submit ✓", disabled=not all_done,
                 use_container_width=True, type="primary"):
        if not st.session_state.get("saved"):
            st.session_state["saved"] = True
            save_all_responses(st.session_state["participant_id"],
                               st.session_state["form"],
                               test_items, answers)
        st.session_state["phase"] = "done"
        st.rerun()


def show_done():
    st.success("✅ Test complete — thank you for participating!")
    st.markdown(
        f"Your responses have been recorded for participant "
        f"**{st.session_state['participant_id']}** (Form **{st.session_state['form']}**)."
    )
    st.balloons()

    if st.session_state["form"] == "A":
        pid = st.session_state["participant_id"]
        st.divider()
        st.markdown("### ⚠️ Save your participant ID before continuing")
        st.markdown("You will need this ID when you take the post-test (Form B):")
        st.code(pid, language=None)
        st.markdown(
            "**Next steps:**\n"
            "1. Copy the ID above.\n"
            "2. Use the **Mandarin Tone Coach** practice app.\n"
            "3. Open the post-test (Form B) link and paste your ID when asked."
        )

    if st.button("Start a new session"):
        for key in ["participant_id", "form", "test_items", "test_idx",
                    "answers", "phase", "auto_id", "saved"]:
            st.session_state.pop(key, None)
        st.rerun()


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="Tone Perception Test", page_icon="🎧",
                       layout="centered")
    st.title("🎧 Mandarin Tone Perception Test")

    if "phase" not in st.session_state:
        st.session_state["phase"] = "intro"

    if st.session_state["phase"] == "intro":
        show_intro()
    elif st.session_state["phase"] == "test":
        show_test()
    else:
        show_done()


if __name__ == "__main__":
    main()
