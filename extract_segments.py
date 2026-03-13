"""
extract_segments.py
Task 3 — Build tone-labelled dataset from AISHELL-1.

For each matched utterance this script produces one CSV row:
    utt_id | speaker | wav_path | transcript | pinyin | tones | n_syllables

Output: Data/tone_dataset.csv
"""

import csv
from pathlib import Path
from collections import Counter
from tqdm import tqdm
from pypinyin import pinyin, Style

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent
DATA_DIR    = PROJECT_DIR / "Data" / "data_aishell"
WAV_TRAIN   = DATA_DIR / "wav" / "train" / "train"
TRANSCRIPT  = DATA_DIR / "transcript" / "aishell_transcript_v0.8.txt"
OUTPUT_CSV  = PROJECT_DIR / "Data" / "tone_dataset.csv"

# ── Helper: convert Chinese characters to tone numbers ────────────────────────
def get_tones(text: str) -> tuple[list[str], list[int]]:
    """
    Given a space-separated Chinese character string, return:
      - pinyin list  e.g. ['er2', 'dui4', 'lou2', ...]
      - tone list    e.g. [2, 4, 2, ...]   (0 = neutral/unknown)
    Only T1-T4 syllables are included; neutral (T5) and punctuation are skipped.
    """
    chars = text.replace(" ", "")
    py_list, tone_list = [], []
    for char in chars:
        result = pinyin(char, style=Style.TONE3, heteronym=False)
        if not result or not result[0]:
            continue
        syllable = result[0][0]
        if not syllable:
            continue
        if syllable[-1].isdigit():
            tone_num = int(syllable[-1])
            if 1 <= tone_num <= 4:          # skip neutral tone 5
                py_list.append(syllable)
                tone_list.append(tone_num)
    return py_list, tone_list


# ── Step 1: load transcript ────────────────────────────────────────────────────
print("Loading transcript...")
transcript = {}
with open(TRANSCRIPT, encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            transcript[parts[0]] = parts[1]
print(f"  {len(transcript):,} entries loaded")

# ── Step 2: index all WAV files ────────────────────────────────────────────────
print("Indexing WAV files...")
wav_index = {}
for spkr_dir in WAV_TRAIN.iterdir():
    if spkr_dir.is_dir():
        for wav in spkr_dir.glob("*.wav"):
            wav_index[wav.stem] = wav
print(f"  {len(wav_index):,} WAV files indexed")

# ── Step 3: find matched utterances ───────────────────────────────────────────
matched_ids = sorted(set(transcript.keys()) & set(wav_index.keys()))
print(f"  {len(matched_ids):,} matched utterances")

# ── Step 4: build CSV ──────────────────────────────────────────────────────────
print(f"\nExtracting tone labels → {OUTPUT_CSV}")
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

tone_counter  = Counter()
skipped       = 0
rows_written  = 0

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "utt_id", "speaker", "wav_path",
        "transcript", "pinyin", "tones", "n_syllables"
    ])

    for utt_id in tqdm(matched_ids, desc="Processing"):
        text = transcript[utt_id]
        py_list, tone_list = get_tones(text)

        if len(tone_list) == 0:
            skipped += 1
            continue

        # Extract speaker ID from utterance ID e.g. BAC009S0002W0122 → S0002
        speaker = utt_id[6:11] if len(utt_id) >= 11 else "unknown"

        writer.writerow([
            utt_id,
            speaker,
            str(wav_index[utt_id]),
            text,
            " ".join(py_list),
            " ".join(str(t) for t in tone_list),
            len(tone_list)
        ])

        tone_counter.update(tone_list)
        rows_written += 1

# ── Step 5: summary ───────────────────────────────────────────────────────────
total_syllables = sum(tone_counter.values())
print(f"\n{'='*50}")
print(f"EXTRACTION COMPLETE")
print(f"{'='*50}")
print(f"Rows written:      {rows_written:,}")
print(f"Utterances skipped:{skipped:,}")
print(f"Total syllables:   {total_syllables:,}")
print(f"\nTone distribution (full corpus):")
for t in [1, 2, 3, 4]:
    c = tone_counter[t]
    pct = 100 * c / total_syllables if total_syllables else 0
    bar = "+" * int(pct / 2)
    print(f"  T{t}: {c:8,}  ({pct:5.1f}%)  {bar}")
print(f"\nSaved to: {OUTPUT_CSV}")
