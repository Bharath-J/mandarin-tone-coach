"""
analyze_results.py
Mandarin Tone Coach — Study Data Analysis
CS6460 Educational Technology, Georgia Tech, 2026

Analyzes:
1. Pre/post perception test accuracy (mandarin_pre_post_training_test_results.csv)
2. App feedback survey (peersurvey_results.txt)

Output: prints summary tables + saves plots to results/
"""

import csv
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats

PROJECT_DIR = Path(__file__).parent
RESULTS_DIR = PROJECT_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

TONE_NAMES = {1: "T1 (flat)", 2: "T2 (rising)", 3: "T3 (dipping)", 4: "T4 (falling)"}

# ── 1. Load pre/post CSV ───────────────────────────────────────────────────────

def load_perception_data(path):
    """Returns dict: participant_id -> {A: [correct,...], B: [correct,...],
                                         A_by_tone: {1:[],2:[],3:[],4:[]},
                                         B_by_tone: ...}"""
    data = defaultdict(lambda: {"A": [], "B": [], "A_by_tone": defaultdict(list),
                                 "B_by_tone": defaultdict(list)})
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid   = row["participant_id"]
            form  = row["form"]
            tone  = int(row["target_tone"])
            correct = int(row["correct"])
            data[pid][form].append(correct)
            data[pid][f"{form}_by_tone"][tone].append(correct)
    return data

# ── 2. Pre/Post paired analysis ────────────────────────────────────────────────

def analyze_prepost(data):
    paired = {pid: d for pid, d in data.items() if d["A"] and d["B"]}
    pre_scores  = [sum(d["A"]) / len(d["A"]) * 100 for d in paired.values()]
    post_scores = [sum(d["B"]) / len(d["B"]) * 100 for d in paired.values()]
    pids        = list(paired.keys())

    print("=" * 60)
    print("PRE/POST PERCEPTION TEST RESULTS")
    print("=" * 60)
    print(f"Participants with both forms (paired): {len(paired)}")
    print(f"Participants with Form A only:         {len(data) - len(paired)}")
    print()

    print(f"{'Participant':<12} {'Pre':>6} {'Post':>6} {'Δ':>6}")
    print("-" * 35)
    for pid, pre, post in zip(pids, pre_scores, post_scores):
        print(f"{pid:<12} {pre:>5.1f}% {post:>5.1f}% {post-pre:>+5.1f}%")
    print("-" * 35)
    print(f"{'Mean':<12} {np.mean(pre_scores):>5.1f}% {np.mean(post_scores):>5.1f}% "
          f"{np.mean(post_scores)-np.mean(pre_scores):>+5.1f}%")
    print(f"{'SD':<12} {np.std(pre_scores, ddof=1):>5.1f}  {np.std(post_scores, ddof=1):>5.1f}")
    print()

    # Wilcoxon signed-rank test (non-parametric, small n)
    stat, p = stats.wilcoxon(pre_scores, post_scores, alternative="two-sided")
    print(f"Wilcoxon signed-rank test: W={stat:.1f}, p={p:.4f}")
    if p < 0.05:
        print("  → Statistically significant difference (p < 0.05)")
    else:
        print("  → No statistically significant difference (p ≥ 0.05)")
    print()

    # Paired t-test for reference
    t, pt = stats.ttest_rel(pre_scores, post_scores)
    print(f"Paired t-test (reference): t={t:.3f}, p={pt:.4f}")
    print()

    return paired, pre_scores, post_scores, pids

# ── 3. Per-tone accuracy ───────────────────────────────────────────────────────

def analyze_by_tone(paired):
    print("-" * 60)
    print("PER-TONE ACCURACY (paired participants)")
    print("-" * 60)
    print(f"{'Tone':<14} {'Pre Acc':>8} {'Post Acc':>9} {'Δ':>7} {'n items':>8}")
    print("-" * 50)

    tone_results = {}
    for tone in [1, 2, 3, 4]:
        pre_correct  = sum(sum(d["A_by_tone"][tone]) for d in paired.values())
        pre_total    = sum(len(d["A_by_tone"][tone]) for d in paired.values())
        post_correct = sum(sum(d["B_by_tone"][tone]) for d in paired.values())
        post_total   = sum(len(d["B_by_tone"][tone]) for d in paired.values())

        pre_acc  = pre_correct  / pre_total  * 100 if pre_total  else 0
        post_acc = post_correct / post_total * 100 if post_total else 0
        tone_results[tone] = (pre_acc, post_acc, pre_total, post_total)
        print(f"{TONE_NAMES[tone]:<14} {pre_acc:>7.1f}% {post_acc:>8.1f}% "
              f"{post_acc-pre_acc:>+6.1f}%  {pre_total:>4}/{post_total}")
    print()
    return tone_results

# ── 4. Parse survey ────────────────────────────────────────────────────────────

LIKERT_QUESTIONS = [
    "Using the app helped me better understand the four Mandarin tones.",
    "The pitch contour visualization helped me identify errors in my pronunciation.",
    "The corrective feedback helped me understand how to improve.",
    "Overall, I found the app useful for learning Mandarin tones.",
    "I found the app easy to navigate.",
    "Recording my voice and getting feedback was straightforward.",
    "I would use this app again to practice Mandarin tones.",
    "I would recommend this app to other Mandarin learners.",
]

# Respondents excluded from TAM: both Step 1 AND Step 3 are blank → survey-only
SURVEY_ONLY_RESPONDENTS = {2, 5}

def parse_survey(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    def extract_section(header):
        """Return list of (respondent_num, value) for a given section header."""
        results = []
        in_section = False
        for line in lines:
            if line.strip().startswith(header):
                in_section = True
                continue
            if in_section:
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped and not stripped[0].isdigit():
                    break
                if "." in stripped:
                    parts = stripped.split(".", 1)
                    try:
                        num = int(parts[0].strip())
                        val = parts[1].strip()
                        results.append((num, val))
                    except ValueError:
                        pass
        return results

    # Native language and prior experience (filter out survey-only respondents)
    native = {n: v for n, v in extract_section("What is your native language?")
              if n not in SURVEY_ONLY_RESPONDENTS}
    prior  = {n: v for n, v in extract_section("How long have you been studying Mandarin?")
              if n not in SURVEY_ONLY_RESPONDENTS}

    # Likert items (filter out survey-only respondents)
    likert = {}
    for q in LIKERT_QUESTIONS:
        short = q[:40]
        items = extract_section(short)
        scores = []
        for num, val in items:
            if num in SURVEY_ONLY_RESPONDENTS:
                continue
            try:
                scores.append((num, int(val)))
            except ValueError:
                pass
        likert[q] = scores

    return native, prior, likert

def analyze_survey(path):
    native, prior, likert = parse_survey(path)

    n_tam = next(len(v) for v in likert.values() if v)

    print("=" * 60)
    print("PARTICIPANT BACKGROUND")
    print("=" * 60)
    print(f"Survey-only respondents excluded: {sorted(SURVEY_ONLY_RESPONDENTS)}")
    print(f"TAM respondents included: {n_tam}")
    print()

    # Native language groups
    lang_counts = defaultdict(int)
    for v in native.values():
        lang_counts[v] += 1
    print("Native languages:")
    for lang, cnt in sorted(lang_counts.items(), key=lambda x: -x[1]):
        print(f"  {lang}: {cnt}")
    print()

    # Prior Mandarin experience
    exp_counts = defaultdict(int)
    for v in prior.values():
        exp_counts[v] += 1
    print("Prior Mandarin experience:")
    order = ["Never studied before this session", "Less than 6 months",
             "6 months – 2 years", "More than 2 years"]
    for exp in order:
        if exp in exp_counts:
            print(f"  {exp}: {exp_counts[exp]}")
    print()

    mandarin_native = [n for n, v in native.items()
                       if "mandarin" in v.lower() or "chinese" in v.lower()]
    print(f"Native/heritage Mandarin speakers (respondents {mandarin_native}): "
          f"flagged — may skew usability scores")
    print()

    print("=" * 60)
    print(f"TAM / USABILITY SURVEY (1–5 Likert scale, n={n_tam})")
    print("=" * 60)
    print(f"{'Question (abbreviated)':<52} {'Mean':>5} {'SD':>5} {'Min':>4} {'Max':>4}")
    print("-" * 72)

    short_labels = [
        "App helped understand tones",
        "Pitch contour helped identify errors",
        "Corrective feedback helped improve",
        "Overall app useful for learning",
        "App easy to navigate",
        "Recording & feedback straightforward",
        "Would use app again",
        "Would recommend to others",
    ]

    means, sds = [], []
    for q, label in zip(LIKERT_QUESTIONS, short_labels):
        scores = [s for _, s in likert[q]]
        if not scores:
            continue
        m = np.mean(scores)
        sd = np.std(scores, ddof=1)
        means.append(m)
        sds.append(sd)
        print(f"{label:<52} {m:>5.2f} {sd:>5.2f} {min(scores):>4} {max(scores):>4}")

    print("-" * 72)
    print(f"{'Overall mean across all items':<52} {np.mean(means):>5.2f} {np.mean(sds):>5.2f}")
    print()

    return likert, short_labels, means, sds, n_tam

# ── 5. Plots ───────────────────────────────────────────────────────────────────

def plot_prepost(pids, pre_scores, post_scores):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Left: per-participant paired lines
    ax = axes[0]
    for i, (pre, post) in enumerate(zip(pre_scores, post_scores)):
        color = "steelblue" if post >= pre else "tomato"
        ax.plot([0, 1], [pre, post], "o-", color=color, alpha=0.7, linewidth=1.5)
    ax.plot([0, 1], [np.mean(pre_scores), np.mean(post_scores)],
            "s--", color="black", linewidth=2.5, markersize=8, label="Mean", zorder=5)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Pre-test\n(Form A)", "Post-test\n(Form B)"], fontsize=12)
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_ylim(0, 105)
    ax.set_title("Individual Pre/Post Accuracy", fontsize=13)
    improved = mpatches.Patch(color="steelblue", label="Improved / same")
    declined = mpatches.Patch(color="tomato",    label="Declined")
    ax.legend(handles=[improved, declined, mpatches.Patch(color="black", label="Mean")],
              fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    # Right: per-tone pre vs post bar chart (using all paired participants)
    ax2 = axes[1]
    tones = [1, 2, 3, 4]
    x = np.arange(len(tones))
    width = 0.35
    # Recompute per-tone from paired (passed via closure trick — just call again)
    tone_pre, tone_post = [], []
    for tone in tones:
        pre_acc  = np.mean([sum(d["A_by_tone"][tone]) / max(len(d["A_by_tone"][tone]), 1) * 100
                            for d in paired_data.values()])
        post_acc = np.mean([sum(d["B_by_tone"][tone]) / max(len(d["B_by_tone"][tone]), 1) * 100
                            for d in paired_data.values()])
        tone_pre.append(pre_acc)
        tone_post.append(post_acc)

    bars1 = ax2.bar(x - width/2, tone_pre,  width, label="Pre",  color="steelblue", alpha=0.8)
    bars2 = ax2.bar(x + width/2, tone_post, width, label="Post", color="darkorange", alpha=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels([TONE_NAMES[t] for t in tones], fontsize=10)
    ax2.set_ylabel("Accuracy (%)", fontsize=12)
    ax2.set_ylim(0, 110)
    ax2.set_title("Per-Tone Accuracy: Pre vs Post", fontsize=13)
    ax2.legend(fontsize=10)
    ax2.grid(axis="y", alpha=0.3)
    for bar in list(bars1) + list(bars2):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                 f"{bar.get_height():.0f}%", ha="center", va="bottom", fontsize=8)

    fig.suptitle("Mandarin Tone Perception: Pre vs Post Training", fontsize=14, fontweight="bold")
    plt.tight_layout()
    out = RESULTS_DIR / "prepost_accuracy.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out}")


def plot_survey(short_labels, means, sds, n_tam):
    fig, ax = plt.subplots(figsize=(10, 6))
    y = np.arange(len(short_labels))
    bars = ax.barh(y, means, xerr=sds, color="steelblue", alpha=0.8,
                   capsize=5, error_kw={"elinewidth": 1.5})
    ax.set_yticks(y)
    ax.set_yticklabels(short_labels, fontsize=11)
    ax.set_xlim(0, 5.5)
    ax.set_xlabel("Mean Rating (1–5)", fontsize=12)
    ax.set_title(f"App Feedback Survey Results (n={n_tam}, mean ± SD)", fontsize=13)
    ax.axvline(x=3, color="gray", linestyle="--", alpha=0.5, label="Neutral (3)")
    ax.axvline(x=4, color="green", linestyle="--", alpha=0.4, label="Agree (4)")
    ax.legend(fontsize=9)
    for bar, m in zip(bars, means):
        ax.text(m + 0.08, bar.get_y() + bar.get_height()/2,
                f"{m:.2f}", va="center", fontsize=10)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    out = RESULTS_DIR / "survey_results.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out}")


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    csv_path    = PROJECT_DIR / "mandarin_pre_post_training_test_results.csv"
    survey_path = PROJECT_DIR / "peersurvey_results.txt"

    data = load_perception_data(csv_path)
    paired_data, pre_scores, post_scores, pids = analyze_prepost(data)
    tone_results = analyze_by_tone(paired_data)

    likert, short_labels, means, sds, n_tam = analyze_survey(survey_path)

    plot_prepost(pids, pre_scores, post_scores)
    plot_survey(short_labels, means, sds, n_tam)

    print()
    print("=" * 60)
    print("OPEN-ENDED FEEDBACK THEMES")
    print("=" * 60)
    print("""Key themes from participant comments:
  + App well-designed, easy to learn from (respondents 9, 17)
  + Pitch contour visualization appreciated
  + Interest in more words to practice (respondent 3)
  - Rising (T2) vs dipping (T3) distinction hard to hear (respondent 1)
  - No example audio of target word before recording (respondent 5)
  - 'Too noisy/quiet' error not specific enough (respondent 12)
  - Stale results when switching words/filters (respondent 1 — already fixed)
  - Native Mandarin speaker misclassified (respondents 6, 13)
  - Feedback heading with no text below it (respondent 1 — already fixed)
""")
