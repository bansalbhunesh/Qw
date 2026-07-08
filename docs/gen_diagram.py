"""Generate the architecture diagram as a high-quality PNG for the hackathon submission.

Run: python docs/gen_diagram.py -> docs/architecture.png

Uses Pillow (no external diagram tool dependency) so it works everywhere.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

W, H = 1800, 1200
BG = "#0a0a14"
CARD = "#1a1a2e"
CARD_BORDER = "#2d2d4a"
ACCENT = "#6366f1"    # indigo
ACCENT2 = "#f59e0b"   # amber
GREEN = "#22c55e"
WHITE = "#e2e2ef"
DIM = "#8888a0"
QWEN_BLUE = "#3b82f6"
WAN_PURPLE = "#a855f7"

OUT = Path(__file__).parent / "architecture.png"


def _ttf(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a real TrueType font on Linux/Windows/macOS so glyphs like —, •, ·
    render everywhere (the Linux-only DejaVu path used to fall back to a bitmap
    font on Windows, drawing those glyphs as tofu boxes)."""
    bold_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    regular_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for p in (bold_paths if bold else regular_paths):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def rounded_rect(draw, xy, fill, outline=None, radius=12):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=2)


def box(draw, x, y, w, h, label, sublabel="", fill=CARD, outline=CARD_BORDER,
        label_color=WHITE, accent_line=None):
    rounded_rect(draw, (x, y, x + w, y + h), fill=fill, outline=outline)
    if accent_line:
        draw.line([(x, y + 4), (x, y + h - 4)], fill=accent_line, width=4)
    # Label
    font = _ttf(18, bold=True)
    sfont = _ttf(13)
    draw.text((x + 16, y + 14), label, fill=label_color, font=font)
    if sublabel:
        draw.text((x + 16, y + 38), sublabel, fill=DIM, font=sfont)


def arrow(draw, x1, y1, x2, y2, color=DIM, label=""):
    draw.line([(x1, y1), (x2, y2)], fill=color, width=2)
    # arrowhead
    dx, dy = x2 - x1, y2 - y1
    length = (dx ** 2 + dy ** 2) ** 0.5
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    size = 8
    px, py = x2 - ux * size, y2 - uy * size
    draw.polygon([
        (x2, y2),
        (int(px - uy * size / 2), int(py + ux * size / 2)),
        (int(px + uy * size / 2), int(py - ux * size / 2)),
    ], fill=color)
    if label:
        lfont = _ttf(11)
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        draw.text((mx + 4, my - 12), label, fill=DIM, font=lfont)


def main():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    title_font = _ttf(28, bold=True)
    sub_font = _ttf(14)

    # Title
    draw.text((40, 25), "Auteur — Architecture", fill=WHITE, font=title_font)
    draw.text((40, 60), "Budget-aware AI showrunner  |  Track 2: AI Showrunner  |  Qwen Cloud Global AI Hackathon",
              fill=DIM, font=sub_font)

    # --- Input ---
    box(draw, 40, 110, 200, 60, "Premise", "one-line input", accent_line=ACCENT)

    # --- Showrunner (big container) ---
    rounded_rect(draw, (280, 95, 1760, 720), fill="#0f0f1a", outline=ACCENT)
    draw.text((300, 102), "SHOWRUNNER  (orchestrator + Budget Governor)", fill=ACCENT, font=sub_font)

    # --- Writer ---
    box(draw, 310, 140, 280, 80, "Writer", "qwen-max  |  structured script", accent_line=QWEN_BLUE)
    arrow(draw, 240, 140, 310, 165, ACCENT, "premise")

    # --- Art Director ---
    box(draw, 310, 250, 280, 80, "Art Director", "qwen-max  |  Style Bible (cached)", accent_line=QWEN_BLUE)
    arrow(draw, 450, 220, 450, 250, DIM, "script")

    # --- Cinematographer ---
    box(draw, 660, 140, 300, 80, "Cinematographer", "wan t2v/i2v/r2v/kf2v ladder", accent_line=WAN_PURPLE)
    arrow(draw, 590, 180, 660, 180, DIM, "bible + prompt")

    # --- Critic ---
    box(draw, 660, 280, 300, 80, "Editor / Critic", "qwen-vl-max  |  4-axis scoring", accent_line=GREEN)
    arrow(draw, 810, 220, 810, 280, DIM, "clip frames")

    # Retake loop
    draw.arc((960, 160, 1040, 340), start=270, end=90, fill=ACCENT2, width=2)
    draw.text((1050, 230), "retake?", fill=ACCENT2, font=sub_font)
    arrow(draw, 1020, 180, 960, 180, ACCENT2, "fix prompt")

    # --- Sound ---
    box(draw, 660, 400, 300, 80, "Sound", "CosyVoice TTS  |  per-character voice", accent_line=QWEN_BLUE)
    arrow(draw, 810, 360, 810, 400, DIM, "dialogue")

    # --- Assembly ---
    box(draw, 660, 520, 300, 80, "Assembly", "ffmpeg  |  crossfade + audio overlay", accent_line=GREEN)
    arrow(draw, 810, 480, 810, 520, DIM, "clips + audio")

    # --- Budget Governor (sidebar) ---
    box(draw, 1120, 140, 280, 180, "Budget Governor", fill="#1a1420",
        outline=ACCENT2, accent_line=ACCENT2)
    bfont = _ttf(13)
    budget_items = [
        "Token metering (per-tier)",
        "Clip render cap + USD ceiling",
        "Importance-weighted retakes",
        "Early-exit on pass",
        "Pre-flight gating",
        "Token ledger (ledger.json)",
    ]
    for i, item in enumerate(budget_items):
        draw.text((1138, 175 + i * 22), f"• {item}", fill=DIM, font=bfont)

    # --- Output ---
    box(draw, 660, 640, 300, 60, "Final Cut", "vertical short (.mp4)", fill="#142014",
        outline=GREEN, accent_line=GREEN)
    arrow(draw, 810, 600, 810, 640, GREEN)

    # --- Deliverables ---
    box(draw, 1020, 640, 200, 60, "ledger.json", "token economy proof", accent_line=ACCENT2)
    box(draw, 1260, 640, 200, 60, "manifest.json", "full production state", accent_line=DIM)

    # --- Alibaba Cloud section ---
    rounded_rect(draw, (40, 760, 1760, 1060), fill="#0f1520", outline="#1e3a5f")
    draw.text((60, 770), "ALIBABA CLOUD", fill=QWEN_BLUE, font=sub_font)

    box(draw, 80, 810, 280, 80, "DashScope", "Model Studio (intl endpoint)",
        fill="#0f1520", outline=QWEN_BLUE, accent_line=QWEN_BLUE)

    model_items = ["qwen-max (creative)", "qwen-flash (grunt)", "qwen-vl-max (vision)",
                   "wan2.2-t2v-plus (video)", "CosyVoice v3-plus (TTS)"]
    for i, m in enumerate(model_items):
        draw.text((98, 905 + i * 18), f"  {m}", fill=DIM, font=bfont)

    box(draw, 440, 810, 280, 80, "OSS", "Object Storage Service",
        fill="#0f1520", outline=QWEN_BLUE, accent_line=QWEN_BLUE)
    draw.text((458, 860), "clips, frames, final cut", fill=DIM, font=bfont)

    box(draw, 800, 810, 280, 80, "ECS", "Elastic Compute Service",
        fill="#0f1520", outline=QWEN_BLUE, accent_line=QWEN_BLUE)
    draw.text((818, 860), "FastAPI backend + Docker", fill=DIM, font=bfont)

    # Connection arrows
    arrow(draw, 220, 760, 220, 810, QWEN_BLUE, "API calls")
    arrow(draw, 580, 760, 580, 810, QWEN_BLUE, "assets")
    arrow(draw, 940, 760, 940, 810, QWEN_BLUE, "deploy")

    # --- Benchmark section ---
    box(draw, 1160, 810, 280, 80, "Benchmark", "Qwen-VL judge · ablation harness",
        fill="#0f1520", outline=ACCENT, accent_line=ACCENT)
    draw.text((1178, 860), "live 7.3/10 at 10.9% of budget", fill=DIM, font=bfont)

    # --- Legend ---
    draw.text((40, 1100), "Legend:", fill=WHITE, font=sub_font)
    legend = [
        (QWEN_BLUE, "Qwen LLM"), (WAN_PURPLE, "Wan Video"), (GREEN, "Review/Output"),
        (ACCENT2, "Budget Governor"), (ACCENT, "Orchestration"),
    ]
    lx = 120
    for color, label in legend:
        draw.rectangle((lx, 1103, lx + 30, 1113), fill=color)
        draw.text((lx + 36, 1098), label, fill=DIM, font=bfont)
        lx += 160

    img.save(OUT, "PNG", quality=95)
    print(f"Saved: {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
