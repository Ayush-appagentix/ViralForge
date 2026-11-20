"""Build a labelled contact sheet of frames so Claude can *see* a video.

Usage: python scripts/frames.py <video> <out.jpg> [--count 16] [--start S] [--end E] [--cols 4]
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from common import find_tool, probe, run, system_fonts_dir


def label_font(size: int = 20):
    fonts = system_fonts_dir()
    for f in ([fonts / "arial.ttf", fonts / "Arial.ttf"] if fonts else []) + [Path("arial.ttf")]:
        try:
            return ImageFont.truetype(str(f), size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def contact_sheet(video: str, out: str, count: int = 16, start: float = 0.0,
                  end: float | None = None, cols: int = 4, thumb_w: int = 360) -> list[float]:
    info = probe(video)
    end = min(end or info["duration"], info["duration"])
    span = max(end - start, 0.1)
    times = [round(start + span * (i + 0.5) / count, 2) for i in range(count)]
    ffmpeg = find_tool("ffmpeg")
    thumbs = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(times):
            f = Path(tmp) / f"f{i:03d}.jpg"
            run([ffmpeg, "-y", "-v", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                 "-vf", f"scale={thumb_w}:-2", "-q:v", "4", str(f)])
            if f.exists():
                thumbs.append((t, Image.open(f).convert("RGB")))
        if not thumbs:
            raise RuntimeError("Could not extract any frames")
        tw, th = thumbs[0][1].size
        rows = (len(thumbs) + cols - 1) // cols
        label_h = 28
        sheet = Image.new("RGB", (cols * tw, rows * (th + label_h)), "black")
        draw = ImageDraw.Draw(sheet)
        font = label_font(20)
        for i, (t, img) in enumerate(thumbs):
            x, y = (i % cols) * tw, (i // cols) * (th + label_h)
            sheet.paste(img.resize((tw, th)), (x, y + label_h))
            draw.text((x + 8, y + 4), f"{int(t // 60)}:{t % 60:05.2f}", fill="yellow", font=font)
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out, quality=85)
    return times


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--count", type=int, default=16)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--cols", type=int, default=4)
    a = ap.parse_args()
    ts = contact_sheet(a.video, a.out, a.count, a.start, a.end, a.cols)
    print(f"Wrote {a.out} with {len(ts)} frames at: {', '.join(f'{t:.1f}s' for t in ts)}")
