"""
check_monosyllabic.py
Count utterances with exactly 1 tone-labelled syllable per tone.
"""
import csv
from pathlib import Path
from collections import defaultdict, Counter

DATASET_CSV = Path(__file__).parent / "Data" / "tone_dataset.csv"

tone_counts  = defaultdict(int)   # tone → count of mono utterances
tone_samples = defaultdict(list)  # tone → sample rows

with open(DATASET_CSV, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        tones = list(map(int, row["tones"].split()))
        if len(tones) == 1:
            t = tones[0]
            tone_counts[t] += 1
            if len(tone_samples[t]) < 3:
                tone_samples[t].append((row["utt_id"], row["transcript"], row["pinyin"]))

print("Single-syllable utterances per tone:")
for t in [1,2,3,4]:
    print(f"  T{t}: {tone_counts[t]:,}")
    for uid, text, py in tone_samples[t]:
        print(f"    {uid}  {text}  ({py})")
