"""Make a short video (Reel / Short) from designed slides - no camera footage needed.

Usage: ./sa slideshow <draft_dir> [--seconds 3.5] [--music FILE] [--volume 0.25] [--size 1080x1920]

Put slides in <draft_dir>/slides/ as 01.html, 02.html, ... (or ready-made .png/.jpg).
Each HTML slide must be a fixed-size page matching --size. Writes final.mp4, thumbnail.jpg, preview.jpg.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common import ROOT, find_tool, print_json, probe, run
from frames import contact_sheet
from render_image import render

FADE = 0.5


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft_dir")
    ap.add_argument("--seconds", type=float, default=3.5, help="time each slide stays on screen")
    ap.add_argument("--music", help="background track (mp3/m4a/wav), e.g. brands/main/music/track.mp3")
    ap.add_argument("--volume", type=float, default=0.25)
    ap.add_argument("--size", default="1080x1920")
    a = ap.parse_args()

    d = Path(a.draft_dir)
    d = (d if d.is_absolute() else ROOT / d).resolve()
    W, H = (int(x) for x in a.size.lower().split("x"))
    slide_dir = d / "slides"
    images = []
    for f in sorted(slide_dir.iterdir()) if slide_dir.exists() else []:
        if f.suffix == ".html":
            images.append(render(f, W, H)[0])
        elif f.suffix.lower() in (".png", ".jpg", ".jpeg") and not (slide_dir / (f.stem + ".html")).exists():
            images.append(f)
    if not images:
        raise SystemExit(f"No slides found in {slide_dir}")

    n, sec = len(images), max(a.seconds, FADE + 0.5)
    total = n * sec - (n - 1) * FADE
    inputs, f = [], []
    for i, img in enumerate(images):
        inputs += ["-loop", "1", "-framerate", "30", "-t", f"{sec:.3f}", "-i", str(img)]
        f.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
                 f"setsar=1,fps=30,format=yuv420p[s{i}]")
    last = "s0"
    for i in range(1, n):
        f.append(f"[{last}][s{i}]xfade=transition=fade:duration={FADE}:offset={i * (sec - FADE):.3f}[x{i}]")
        last = f"x{i}"
    f.append(f"[{last}]format=yuv420p[vout]")
    music = Path(a.music) if a.music else None
    if music and not music.is_absolute():
        music = ROOT / music
    if music and music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        f.append(f"[{n}:a]atrim=0:{total:.3f},afade=t=out:st={max(total - 1.5, 0):.3f}:d=1.5,"
                 f"volume={a.volume},aresample=48000,aformat=channel_layouts=stereo[aout]")
    else:
        inputs += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        f.append(f"[{n}:a]anull[aout]")

    out = d / "final.mp4"
    ffmpeg = find_tool("ffmpeg")
    run([ffmpeg, "-y", "-v", "error", *inputs, "-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
         "-movflags", "+faststart", "-t", f"{total:.3f}", str(out)])
    run([ffmpeg, "-y", "-v", "error", "-ss", "0.5", "-i", str(out), "-frames:v", "1", "-q:v", "2",
         str(d / "thumbnail.jpg")])
    contact_sheet(str(out), str(d / "preview.jpg"), count=min(8, n * 2), cols=4, thumb_w=270)
    info = probe(out)
    print_json({"output": str(out), "slides": n, "duration": info["duration"], "size_mb": info["size_mb"],
                "resolution": f"{info['width']}x{info['height']}", "preview": str(d / "preview.jpg")})


if __name__ == "__main__":
    main()
