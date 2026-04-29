"""
generate_flowchart_inference.py
Generates the inference pipeline flowchart for the paper appendix.
Output: results/flowchart_inference.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

OUT = Path(__file__).parent / "results" / "flowchart_inference.png"

# ── Colours ────────────────────────────────────────────────────────────────────
C_PROCESS  = "#D6E4F0"   # light blue  — process box
C_DECISION = "#FFF3CD"   # light amber — decision diamond
C_IO       = "#D5F5E3"   # light green — input/output
C_ERROR    = "#FADBD8"   # light red   — error path
C_BORDER   = "#2C3E50"   # dark border
C_ARROW    = "#2C3E50"

FIG_W, FIG_H = 9, 16
ax_w, ax_h   = FIG_W, FIG_H

fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
ax.set_xlim(0, ax_w)
ax.set_ylim(0, ax_h)
ax.axis("off")

# ── Helpers ────────────────────────────────────────────────────────────────────
def box(ax, cx, cy, w, h, text, color=C_PROCESS, fontsize=11, bold=False):
    rect = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                          boxstyle="round,pad=0.08",
                          facecolor=color, edgecolor=C_BORDER, linewidth=1.2)
    ax.add_patch(rect)
    weight = "bold" if bold else "normal"
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fontsize,
            fontweight=weight, wrap=True,
            multialignment="center")

def diamond(ax, cx, cy, w, h, text, fontsize=10.5):
    dx, dy = w/2, h/2
    pts = [(cx, cy+dy), (cx+dx, cy), (cx, cy-dy), (cx-dx, cy)]
    diamond_patch = plt.Polygon(pts, closed=True,
                                facecolor=C_DECISION, edgecolor=C_BORDER, linewidth=1.2)
    ax.add_patch(diamond_patch)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fontsize,
            multialignment="center")

def arrow(ax, x1, y1, x2, y2, label="", label_side="right"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=C_ARROW,
                                lw=1.3, mutation_scale=14))
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        offset = 0.18 if label_side == "right" else -0.18
        ax.text(mx + offset, my, label, ha="center", va="center",
                fontsize=9.5, color="#555555")

def harrow(ax, x1, y, x2, label="", label_above=True):
    ax.annotate("", xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle="-|>", color=C_ARROW,
                                lw=1.3, mutation_scale=14))
    if label:
        mx = (x1+x2)/2
        dy = 0.15 if label_above else -0.15
        ax.text(mx, y + dy, label, ha="center", va="center",
                fontsize=9.5, color="#555555")

# ── Layout constants ───────────────────────────────────────────────────────────
CX   = 4.5          # main column centre x
BW   = 3.6          # box width
BH   = 0.55         # box height
DW   = 2.8          # diamond width
DH   = 0.7          # diamond height
GAP  = 0.95         # vertical gap between centres

# y positions (top → bottom)
Y = [ax_h - 0.7 - i * GAP for i in range(13)]

# ── Nodes ──────────────────────────────────────────────────────────────────────
box(ax, CX, Y[0],  BW, BH, "User Records Audio", color=C_IO, bold=True)
box(ax, CX, Y[1],  BW, BH, "Step 1  |  Trim Silence (VAD)")
box(ax, CX, Y[2],  BW, BH, "Step 2  |  Extract F0 via Parselmouth\n(floor=75 Hz, ceiling=500 Hz)")
diamond(ax, CX, Y[3], DW, DH, "Step 3  |  Sufficient\nvoiced frames?")
box(ax, CX, Y[4],  BW, BH, "Step 4  |  Normalize F0 to Semitones\n(relative to speaker mean Hz)")
box(ax, CX, Y[5],  BW, BH, "Step 5  |  Build 27 Features\n10 contour pts + 9 deltas + 7 stats + f0_min_pos")
box(ax, CX, Y[6],  BW, BH, "Step 6  |  Scale Features (StandardScaler)")
box(ax, CX, Y[7],  BW, BH, "Step 7  |  SVM RBF Classifier\n→ Raw tone prediction (T1–T4)")
box(ax, CX, Y[8],  BW, BH, "Step 8  |  Post-processing Rules\n(T2/T3, T1/T2, T4/T2 boundary corrections)")
diamond(ax, CX, Y[9], DW, DH, "Step 9  |  Disyllabic\nmode?")
box(ax, CX, Y[10], BW, BH, "Step 10  |  Check Target Tone\n(+ T3 sandhi: accept T2 for syllable 1)")
box(ax, CX, Y[11], BW, BH, "Step 11  |  Pitch Contour Overlay\n(learner red, reference dashed blue)\n+ Confidence Bar Chart", fontsize=10.5)
box(ax, CX, Y[12], BW, BH, "Corrective Feedback Text", color=C_IO, bold=True)

# ── Error box (right of diamond at Y[3]) ──────────────────────────────────────
ERR_X = 7.5
box(ax, ERR_X, Y[3], 2.2, BH, '"Recording too\nnoisy / quiet"', color=C_ERROR, fontsize=10)

# ── Disyllabic repeat box (right of diamond at Y[9]) ──────────────────────────
REP_X = 7.6
box(ax, REP_X, Y[9], 2.0, BH*1.3, "Repeat steps 1–8\nfor syllable 2\n(separate extraction)", color=C_PROCESS, fontsize=10)

# ── Arrows (main path) ────────────────────────────────────────────────────────
for i in range(len(Y) - 1):
    # skip arrow into diamond lower edge — place arrow from diamond bottom
    if i == 3:   # after decision node (voiced frames)
        arrow(ax, CX, Y[3] - DH/2, CX, Y[4] + BH/2, label="Yes")
    elif i == 9:  # after decision node (disyllabic)
        arrow(ax, CX, Y[9] - DH/2, CX, Y[10] + BH/2, label="No")
    else:
        arrow(ax, CX, Y[i] - BH/2, CX, Y[i+1] + BH/2)

# Arrow to error box
harrow(ax, CX + DW/2, Y[3], ERR_X - 1.1, label="No", label_above=True)

# Arrow from error box downward (end / retry)
ax.annotate("", xy=(ERR_X, Y[3] - BH/2 - 0.28), xytext=(ERR_X, Y[3] - BH/2),
            arrowprops=dict(arrowstyle="-|>", color=C_ARROW, lw=1.3, mutation_scale=12))
ax.text(ERR_X, Y[3] - BH/2 - 0.42, "(stop)", ha="center", va="center",
        fontsize=9, color="#888888")

# Arrow to disyllabic repeat box — label placed below arrow, right after diamond tip
harrow(ax, CX + DW/2, Y[9], REP_X - 1.0)
ax.text(CX + DW/2 + 0.15, Y[9] - 0.18, "Yes", ha="left", va="top",
        fontsize=9.5, color="#555555")

# Arrow from repeat box back into main flow: down from bottom of repeat box,
# then left into right side of Check Target Tone box
rep_bottom_y = Y[9] - BH * 1.3 / 2
check_right_x = CX + BW / 2
ax.plot([REP_X, REP_X, check_right_x + 0.02],
        [rep_bottom_y, Y[10], Y[10]], color=C_ARROW, lw=1.3)
ax.annotate("", xy=(check_right_x, Y[10]), xytext=(check_right_x + 0.02, Y[10]),
            arrowprops=dict(arrowstyle="-|>", color=C_ARROW, lw=1.3, mutation_scale=12))

# ── Title ─────────────────────────────────────────────────────────────────────
ax.text(CX, ax_h - 0.15, "Mandarin Tone Coach — Inference Pipeline",
        ha="center", va="top", fontsize=14, fontweight="bold")

# ── Legend ────────────────────────────────────────────────────────────────────
legend_x, legend_y = 0.35, Y[12] - BH / 2 - 1.0
for color, label in [(C_IO, "Input / Output"), (C_PROCESS, "Process"),
                     (C_DECISION, "Decision"), (C_ERROR, "Error")]:
    patch = mpatches.Patch(facecolor=color, edgecolor=C_BORDER, label=label)
    ax.add_patch(mpatches.FancyBboxPatch((legend_x - 0.15, legend_y - 0.13),
                                          0.3, 0.26,
                                          boxstyle="round,pad=0.03",
                                          facecolor=color, edgecolor=C_BORDER, linewidth=1))
    ax.text(legend_x + 0.25, legend_y, label, va="center", fontsize=9.5)
    legend_x += 1.9

plt.tight_layout(pad=0.3)
plt.savefig(OUT, dpi=180, bbox_inches="tight")
plt.close()
print(f"Saved: {OUT}")
