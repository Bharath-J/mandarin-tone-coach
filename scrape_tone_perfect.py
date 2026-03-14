"""
scrape_tone_perfect.py
Download Tone Perfect corpus from tone.lib.msu.edu
"""

import re
import csv
import time
import requests
from pathlib import Path
from tqdm import tqdm

BASE_URL   = "https://tone.lib.msu.edu"
OUTPUT_DIR = Path(__file__).parent / "Data" / "tone_perfect"
METADATA   = Path(__file__).parent / "Data" / "tone_perfect_metadata.csv"
DELAY      = 0.5
PAGE_SIZE  = 100

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (research use, GT CS6460 project)"})

def get_ids_for_tone(tone: int) -> list[dict]:
    items = []
    start = 0
    url   = f"{BASE_URL}/search"
    print(f"\nCollecting IDs for Tone {tone}...")
    while True:
        # Build URL manually to ensure correct fq parameter encoding
        full_url = f"{url}?fq=custom.tone%3A{tone}&rows={PAGE_SIZE}&start={start}"
        resp = SESSION.get(full_url, timeout=15)
        resp.raise_for_status()
        html = resp.text
        # Debug: print snippet of HTML to verify structure
        if start == 0 and len(items) == 0:
            # Find first occurrence of /tone/ in HTML
            snippet_idx = html.find('/tone/')
            if snippet_idx >= 0:
                print(f"  HTML snippet: ...{html[snippet_idx-20:snippet_idx+60]}...")
            else:
                print(f"  WARNING: No /tone/ found in HTML. Response length: {len(html)}")
        # Match: <a href='/tone/6304' title='gēn'>gēn</a><br/> by  Male Voice 1
        matches = re.findall(
            r"href='/tone/(\d+)'\s+title='([^']+)'[^<]*</a><br/>\s*by\s+([^<]+)",
            html
        )
        if not matches:
            break
        # Deduplicate by ID
        seen = set()
        for item_id, syllable, speaker_raw in matches:
            if item_id in seen:
                continue
            seen.add(item_id)
            speaker = speaker_raw.strip()
            gender  = "female" if "Female" in speaker else "male"
            items.append({"id": item_id, "syllable": syllable, "tone": tone,
                          "speaker": speaker, "gender": gender})
        n_this_page = len(seen)
        print(f"  Page start={start}: found {n_this_page} items (total: {len(items)})")
        start += PAGE_SIZE
        time.sleep(DELAY)
        if n_this_page < PAGE_SIZE:
            break
    return items

def download_mp3(item: dict, output_dir: Path) -> str | None:
    item_id  = item["id"]
    tone     = item["tone"]
    syllable = re.sub(r'[^\w]', '_', item["syllable"])
    speaker  = re.sub(r'\s+', '_', item["speaker"])
    tone_dir = output_dir / f"tone_{tone}"
    tone_dir.mkdir(parents=True, exist_ok=True)
    filename = tone_dir / f"{syllable}_{speaker}_{item_id}.mp3"
    if filename.exists():
        return str(filename)
    url = f"{BASE_URL}/tone/{item_id}/PROXY_MP3/download"
    try:
        resp = SESSION.get(url, timeout=20, stream=True)
        resp.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return str(filename)
    except Exception as e:
        print(f"  ERROR downloading {item_id}: {e}")
        return None

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_items = []
    for tone in [1, 2, 3, 4]:
        items = get_ids_for_tone(tone)
        all_items.extend(items)
        print(f"  T{tone}: {len(items)} items collected")
    print(f"\nTotal items: {len(all_items)}")
    metadata_rows = []
    failed = 0
    for item in tqdm(all_items, desc="Downloading"):
        filepath = download_mp3(item, OUTPUT_DIR)
        if filepath:
            metadata_rows.append({**item, "filepath": filepath})
        else:
            failed += 1
        time.sleep(DELAY)
    with open(METADATA, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id","syllable","tone","speaker","gender","filepath"])
        writer.writeheader()
        writer.writerows(metadata_rows)
    print(f"\nDownloaded: {len(metadata_rows)}  Failed: {failed}")
    for tone in [1,2,3,4]:
        count = sum(1 for r in metadata_rows if r["tone"] == tone)
        print(f"  T{tone}: {count} files")