"""
explore_aishell.py
Corpus structure and tone distribution overview.
"""
from pathlib import Path
from collections import Counter
from pypinyin import pinyin, Style

PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR/ "Data" / "data_aishell"
WAV_TRAIN = DATA_DIR / "wav" / "train" / "train"
TRANSCRIPT = DATA_DIR / "transcript" /"aishell_transcript_v0.8.txt"

#1. Speakers and utterances
speakers  = sorted([d for d in WAV_TRAIN.iterdir() if d.is_dir()])
total_wavs = sum(len(list(s.glob("*.wav"))) for s in speakers)
print(f"Speakers: {len(speakers)}")
print(f"Total WAVs: {total_wavs}")
print(f"Avg utterances/speaker: {total_wavs / max(len(speakers),1):.0f}")

# 2. Parse transcript
transcript = {}
with open(TRANSCRIPT, encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            transcript[parts[0]] = parts[1]
print(f"\nTranscript entries: {len(transcript)}")
for uid, text in list(transcript.items())[:3]:
    print(f"  {uid}: {text}")

# 3. Tone distribution (first 500 utterances)
tone_counter  = Counter()
neutral_count = 0
for uid, text in list(transcript.items())[:500]:
    for char in text.replace(" ", ""):
        py = pinyin(char, style=Style.TONE3, heteronym=False)
        if py and py[0] and py[0][0] and py[0][0][-1].isdigit():
            t = py[0][0][-1]
            if t == "5": neutral_count += 1
            else: tone_counter[f"T{t}"] += 1

total = sum(tone_counter.values()) + neutral_count
print("\nTone distribution (sample):")
for t in ["T1","T2","T3","T4"]:
    c = tone_counter.get(t, 0)
    print(f"  {t}: {c} ({100*c/total:.1f}%)")
print(f"  T5 neutral: {neutral_count} ({100*neutral_count/total:.1f}%)")

# 4. WAV/transcript alignment
wav_ids        = {w.stem for s in speakers for w in s.glob("*.wav")}
transcript_ids = set(transcript.keys())
print(f"\nMatched (WAV + transcript): {len(wav_ids & transcript_ids)}")
print(f"WAV only (no transcript):   {len(wav_ids - transcript_ids)}")
print(f"Transcript only (no WAV):   {len(transcript_ids - wav_ids)}")
print("\nDone.")
