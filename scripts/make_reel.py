#!/usr/bin/env python3
"""make_reel — turn any Auteur production into a shareable demo reel.

Reads a production directory (its manifest.json + final.mp4) and renders a polished
sizzle reel: a title card, the premise, the real footage with each shot's live Qwen-VL
critic score captioned, and a closing stats card with the budget economy — over a
procedural music bed. Works in landscape (16:9) or vertical (9:16) for mobile.

Usage:
    python scripts/make_reel.py out_live                 # landscape -> out_live/reel.mp4
    python scripts/make_reel.py out_live --vertical      # 9:16 mobile cut
    python scripts/make_reel.py out_live --out promo.mp4

Pure-offline: needs only ffmpeg (bundled via imageio-ffmpeg) + Pillow. No network, no spend.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auteur import media  # noqa: E402

BLUE = (110, 168, 254); GREEN = (92, 200, 119); GREY = (150, 150, 165)
AMBER = (240, 173, 78); RED = (217, 83, 79); WHITE = (245, 245, 250); BG = (8, 8, 14)


def _font_path(bold: bool) -> str | None:
    names_b = ["DejaVuSans-Bold.ttf", "arialbd.ttf", "segoeuib.ttf", "Arial Bold.ttf", "Helvetica.ttc"]
    names_r = ["DejaVuSans.ttf", "arial.ttf", "segoeui.ttf", "Arial.ttf", "Helvetica.ttc"]
    dirs = [
        "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation",
        "C:/Windows/Fonts", "/Library/Fonts", "/System/Library/Fonts/Supplemental",
    ]
    for n in (names_b if bold else names_r):
        for d in dirs:
            p = Path(d) / n
            if p.exists():
                return str(p)
    return None


def _score_color(s: float):
    return GREEN if s >= 8 else BLUE if s >= 7 else AMBER if s >= 5 else RED


class Reel:
    def __init__(self, vertical: bool):
        from PIL import ImageFont
        self._IF = ImageFont
        self.W, self.H = (1080, 1920) if vertical else (1920, 1080)
        self.vertical = vertical
        self.FF = media.ffmpeg_exe()
        self._fb = _font_path(True)
        self._fr = _font_path(False)

    def font(self, sz, bold=True):
        path = self._fb if bold else self._fr
        try:
            return self._IF.truetype(path, sz) if path else self._IF.load_default()
        except Exception:
            return self._IF.load_default()

    def _center(self, d, cy, text, sz, color, bold=True):
        f = self.font(sz, bold)
        bb = d.textbbox((0, 0), text, font=f)
        d.text(((self.W - (bb[2] - bb[0])) / 2, cy), text, font=f, fill=color)

    def run(self, args, out):
        r = subprocess.run([self.FF, "-y", *args, str(out)], capture_output=True, text=True)
        if r.returncode != 0:
            print("ffmpeg error:\n", r.stderr[-700:]); raise SystemExit(1)
        return out

    def card(self, out, lines, seconds):
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (self.W, self.H), BG); d = ImageDraw.Draw(img)
        d.rectangle([(self.W/2-60, 0), (self.W/2+60, 8)], fill=BLUE)
        for text, sz, color, cy in lines:
            self._center(d, cy, text, sz, color)
        png = Path(out).with_suffix(".png"); img.save(png)
        return self.run(["-loop", "1", "-i", str(png), "-f", "lavfi", "-i",
                         "anullsrc=channel_layout=stereo:sample_rate=44100", "-t", str(seconds),
                         "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast",
                         "-c:a", "aac", "-r", "30", "-shortest"], out)

    def overlay_png(self, draw_fn):
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(img))
        return img

    def footage(self, sc, footage, premise, captions):
        """Frame the footage and overlay branding + per-shot score captions (timed)."""
        W, H = self.W, self.H
        top = self.overlay_png(lambda d: self._draw_top(d, premise))
        top.save(sc / "top.png")
        for i, (label, score, color) in enumerate(captions):
            self.overlay_png(lambda d, l=label, s=score, c=color: self._draw_cap(d, l, s, c)) \
                .save(sc / f"cap{i}.png")

        inputs = ["-i", str(footage), "-i", str(sc / "top.png")]
        for i in range(len(captions)):
            inputs += ["-i", str(sc / f"cap{i}.png")]

        if self.vertical:
            base = f"[0:v]scale={W}:-2[s];[s]pad={W}:{H}:-1:-1:color=0x080810[bg];[bg][1:v]overlay=0:0[v1]"
        else:
            base = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,setsar=1[s];" \
                   f"[s]pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x080810[bg];[bg][1:v]overlay=0:0[v1]"
        fc, prev = base, "[v1]"
        n = len(captions)
        total = media.probe_duration(footage)
        win = total / max(1, n)
        for i in range(n):
            t0, t1 = i * win, (i + 1) * win
            out = f"[v{i+2}]" if i < n - 1 else "[vout]"
            fc += f";{prev}[{i+2}:v]overlay=0:0:enable='between(t,{t0:.2f},{t1:.2f})'{out}"
            prev = out
        args_to_run = inputs + ["-filter_complex", fc, "-map", "[vout]", "-an", "-pix_fmt",
                           "yuv420p", "-c:v", "libx264", "-preset", "fast", "-r", "30"]
        self.run(args_to_run, sc / "f_nv.mp4")
        return self.run(["-i", str(sc / "f_nv.mp4"), "-f", "lavfi", "-i",
                         "anullsrc=channel_layout=stereo:sample_rate=44100", "-c:v", "copy",
                         "-c:a", "aac", "-shortest"], sc / "f.mp4")

    def _draw_top(self, d, premise):
        if self.vertical:
            self._center(d, 150, "AUTEUR", 64, (255, 255, 255, 255))
            self._center(d, 235, "live Wan render", 38, BLUE + (255,), False)
            for j, line in enumerate(_wrap(premise, 30)[:2]):
                self._center(d, 430 + j * 55, line, 38, (220, 220, 230, 255), False)
        else:
            f = self.font(38, False)
            d.text((60, 45), "AUTEUR  ·  live Wan render", font=f, fill=(255, 255, 255, 220))

    def _draw_cap(self, d, label, score, color):
        if self.vertical:
            self._center(d, 1430, label, 46, (255, 255, 255, 255))
            self._center(d, 1505, f"Qwen-VL critic   {score}/10", 58, color + (255,))
        else:
            d.text((60, self.H - 185), label, font=self.font(48), fill=(255, 255, 255, 255))
            d.text((60, self.H - 120), f"Qwen-VL critic   {score}/10", font=self.font(56),
                   fill=color + (255,))


def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def build(workdir: Path, out: Path, vertical: bool):
    manifest = json.loads((workdir / "manifest.json").read_text())
    footage = workdir / "final.mp4"
    if not footage.exists():
        print(f"error: {footage} not found — run a production first."); raise SystemExit(1)

    premise = manifest.get("premise", "")
    logline = manifest.get("logline", premise)
    rc = manifest.get("report_card", {})
    b = manifest.get("budget", {})
    eff = rc.get("efficiency", {})
    shots = manifest.get("shots", [])
    beats = manifest.get("beats", [])
    scored = [s for s in shots if s.get("critic_score") is not None]

    captions = []
    for s in scored:
        bi = s.get("beat", 0)
        beat = beats[bi]["label"] if bi < len(beats) else "Shot"
        sc = float(s["critic_score"])
        captions.append((f"Shot {s.get('index', '?')} · {beat}", f"{sc:.1f}", _score_color(sc)))
    if not captions:
        captions = [("Live render", "—", BLUE)]

    r = Reel(vertical)
    from tempfile import mkdtemp
    sc = Path(mkdtemp())

    avg = rc.get("avg_critic_score", 0) or 0
    util = rc.get("budget_utilization_pct", 0) or 0
    save = eff.get("routing_savings_pct", 0) or 0
    cost = b.get("estimated_cost_usd", 0) or 0
    toks = b.get("tokens_used", 0) or 0

    V = vertical
    print("title..."); r.card(sc / "01.mp4", (
        [("AUTEUR", 140, WHITE, 640), ("The Budget-Aware", 56, BLUE, 830),
         ("AI Showrunner", 56, BLUE, 905), ("Live on Alibaba Cloud · Qwen", 34, GREY, 1090)]
        if V else
        [("AUTEUR", 150, WHITE, 360), ("The Budget-Aware AI Showrunner", 56, BLUE, 540),
         ("Live on Alibaba Cloud DashScope", 32, GREEN, 660)]), 2.8)

    print("premise..."); prem_lines = _wrap("“" + logline + "”", 24 if V else 40)[:3]
    pl = [("THE PREMISE", 40, BLUE, 560 if V else 320)]
    for j, line in enumerate(prem_lines):
        pl.append((line, 56 if V else 58, WHITE, (700 if V else 430) + j * (80 if V else 80)))
    r.card(sc / "02.mp4", pl, 3.3)

    print("footage..."); r.footage(sc, footage, logline, captions)
    # copy footage segment out (already at sc/f.mp4)

    print("stats..."); r.card(sc / "04.mp4", (
        [("MEASURED LIVE", 44, BLUE, 470), (f"{avg:.1f} / 10", 130, WHITE, 580),
         ("avg Qwen-VL critic score", 38, GREY, 740),
         (f"{util:.1f}%  of token budget used", 48, WHITE, 900),
         (f"~{save:.0f}%  est. routing saving", 48, GREEN, 985),
         (f"${cost:.2f} est.  ·  {toks:,} tokens", 48, WHITE, 1070),
         ("Budget Governor · 4-axis critic loop", 32, GREY, 1240)]
        if V else
        [("MEASURED LIVE", 42, BLUE, 250), (f"{avg:.1f} / 10   avg Qwen-VL critic score", 56, WHITE, 380),
         (f"{util:.1f}%   of the token budget used", 50, WHITE, 480),
         (f"~{save:.0f}%   est. token-routing saving", 50, GREEN, 575),
         (f"${cost:.2f} est. spend  ·  {toks:,} tokens", 50, WHITE, 670),
         ("Budget Governor · 4-axis critic · 7 agents", 32, GREY, 780)]), 4.2)

    print("assembling...")
    segs = [sc / f for f in ["01.mp4", "02.mp4", "f.mp4", "04.mp4"]]
    (sc / "c.txt").write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in segs))
    r.run(["-f", "concat", "-safe", "0", "-i", str(sc / "c.txt"), "-c:v", "libx264",
           "-preset", "medium", "-crf", "20", "-c:a", "aac", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart"], sc / "silent.mp4")

    from auteur.agents.sound import Sound
    from auteur.budget import BudgetGovernor
    from auteur.config import BudgetConfig
    total = media.probe_duration(sc / "silent.mp4")
    mood = (manifest.get("score", {}) or {}).get("mood", "bittersweet")
    Sound(BudgetGovernor(BudgetConfig())).score(mood, total, str(sc / "score.wav"), intensity=0.6)
    r.run(["-i", str(sc / "silent.mp4"), "-i", str(sc / "score.wav"), "-filter_complex",
           "[1:a]volume=0.6[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
           "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest"], out)

    dur = media.probe_duration(out)
    print(f"\nreel -> {out}  ({dur:.1f}s, {r.W}x{r.H})")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a demo reel from an Auteur production")
    ap.add_argument("workdir", help="production directory (contains manifest.json + final.mp4)")
    ap.add_argument("--vertical", action="store_true", help="9:16 mobile cut (default 16:9)")
    ap.add_argument("--out", default=None, help="output path (default: <workdir>/reel.mp4)")
    args = ap.parse_args(argv)
    wd = Path(args.workdir)
    out = Path(args.out) if args.out else wd / ("reel_vertical.mp4" if args.vertical else "reel.mp4")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("error: Pillow required — pip install Pillow"); return 1
    build(wd, out, args.vertical)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
