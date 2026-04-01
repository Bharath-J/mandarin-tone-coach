"""
generate_perception_stimuli.py
Selects 12 stimuli per form (A/B) from the Tone Perfect corpus for the
pre/post perception test and saves them to perception_test_stimuli.json.

Form A (pre-test):  Female Voice 1 (2 per tone) + Male Voice 1 (1 per tone)
Form B (post-test): Female Voice 2 (2 per tone) + Male Voice 2 (1 per tone)

Exclusion: syllables already present in word_list.json (practice words).
Seed: fixed (42) for reproducibility.

Usage:
    python generate_perception_stimuli.py
"""

import json
import random
import pandas as pd
from pathlib import Path

PROJECT_DIR  = Path(__file__).parent
METADATA     = PROJECT_DIR / "Data" / "tone_perfect_metadata.csv"
WORD_LIST    = PROJECT_DIR / "word_list.json"
OUTPUT       = PROJECT_DIR / "perception_test_stimuli.json"

TONES        = [1, 2, 3, 4]
N_FEMALE     = 2   # items per tone from female speaker
N_MALE       = 1   # items per tone from male speaker
SEED         = 42

FORM_SPEAKERS = {
    "A": {"female": "Female Voice 1", "male": "Male Voice 1"},
    "B": {"female": "Female Voice 2", "male": "Male Voice 2"},
}

# Mapping from metadata speaker name → zip filename speaker code
SPEAKER_CODE = {
    "Female Voice 1": "FV1", "Female Voice 2": "FV2", "Female Voice 3": "FV3",
    "Male Voice 1":   "MV1", "Male Voice 2":   "MV2", "Male Voice 3":   "MV3",
}

TONE_PERFECT_DIR = PROJECT_DIR / "Data" / "tone_perfect"


def strip_tone_mark(pinyin: str) -> str:
    """Remove diacritics for comparison (rough ASCII fold)."""
    replacements = {
        "ā":"a","á":"a","ǎ":"a","à":"a",
        "ē":"e","é":"e","ě":"e","è":"e",
        "ī":"i","í":"i","ǐ":"i","ì":"i",
        "ō":"o","ó":"o","ǒ":"o","ò":"o",
        "ū":"u","ú":"u","ǔ":"u","ù":"u",
        "ǖ":"v","ǘ":"v","ǚ":"v","ǜ":"v","ü":"v",
    }
    return "".join(replacements.get(c, c) for c in pinyin.lower())


def main():
    rng = random.Random(SEED)

    # Load practice words to exclude
    with open(WORD_LIST, encoding="utf-8") as f:
        practice = {strip_tone_mark(w["pinyin"]) for w in json.load(f)}

    # Load metadata and resolve filenames (metadata paths are from old machine)
    df = pd.read_csv(METADATA)
    df["filename"] = df["filepath"].apply(lambda p: Path(p).name)
    df["syllable_bare"] = df["syllable"].apply(strip_tone_mark)

    # Exclude practice words
    df = df[~df["syllable_bare"].isin(practice)].copy()

    stimuli = {}
    for form, speakers in FORM_SPEAKERS.items():
        form_items = []
        for tone in TONES:
            tone_df = df[df["tone"] == tone]

            female_pool = tone_df[tone_df["speaker"] == speakers["female"]].to_dict("records")
            male_pool   = tone_df[tone_df["speaker"] == speakers["male"]].to_dict("records")

            rng.shuffle(female_pool)
            rng.shuffle(male_pool)

            selected = female_pool[:N_FEMALE] + male_pool[:N_MALE]
            rng.shuffle(selected)   # mix genders within the tone group

            for item in selected:
                code     = SPEAKER_CODE[item["speaker"]]
                bare     = strip_tone_mark(item["syllable"])
                filename = f"{bare}{int(item['tone'])}_{code}_MP3.mp3"
                # Verify file exists before including
                if not (TONE_PERFECT_DIR / filename).exists():
                    print(f"  WARNING: {filename} not found, skipping")
                    continue
                form_items.append({
                    "syllable": item["syllable"],
                    "tone":     int(item["tone"]),
                    "speaker":  item["speaker"],
                    "gender":   item["gender"],
                    "filename": filename,
                })

        stimuli[form] = form_items
        print(f"Form {form}: {len(form_items)} items")
        for tone in TONES:
            tone_items = [x for x in form_items if x["tone"] == tone]
            print(f"  Tone {tone}: {[x['syllable'] for x in tone_items]}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(stimuli, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
