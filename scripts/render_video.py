"""Render <draft_dir>/edit_plan.json into a platform-ready MP4 (+ thumbnail and preview sheet).

Usage: python scripts/render_video.py <draft_dir>

edit_plan.json (only "source" is required):
{
  "source": "C:/Users/me/Videos/raw.mp4",
  "segments": [{"start": 2.0, "end": 14.5}, {"start": 20.0, "end": 31.2}],  // keep-ranges, source seconds, in order
  "aspect": "9:16",                 // 9:16 | 4:5 | 1:1 | 16:9
  "reframe": "crop",                // crop (fill, cut sides) | blur (fit on blurred copy) | fit (black bars)
  "focus_x": 0.5, "focus_y": 0.5,   // crop focus: 0 = left/top, 1 = right/bottom
  "fps": 30,
  "captions": {"enabled": true, "words_per_line": 3, "position": "lower", "uppercase": false,
               "font": "Arial", "size": 78, "color": "#FFFFFF", "highlight": "#FFD400",
               "replace": {"misheardword": "correctword"}},
  "hook_text": {"text": "Stop editing like this", "start": 0, "end": 3, "color": "#111111", "box": "#FFFFFF"},
  "brand": "main",                  // fonts come from brands/<brand>/fonts (else Windows fonts)
  "logo": {"file": "brands/main/logo.png", "position": "top-right", "width_pct": 0.16, "opacity": 0.9},
  "music": {"file": "brands/main/music/track.mp3", "volume": 0.12},
  "normalize_audio": true,
  "thumbnail_at": 1.0,
  "output": "final.mp4"
}
Captions need transcript.json in the draft folder (python scripts/transcribe.py ...).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from common import BRANDS, ROOT, find_tool, print_json, probe, run, system_fonts_dir
from frames import contact_sheet

SIZES = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080), "16:9": (1920, 1080)}


def project_path(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (ROOT / path)


# ---------- captions (ASS subtitles) ----------

def style_color(hex_: str, alpha: int = 0) -> str:
    h = hex_.lstrip("#")
    return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def inline_color(hex_: str) -> str:
    h = hex_.lstrip("#").upper()
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&"


def ass_time(t: float) -> str:
    cs = int(round(max(t, 0) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def ass_text(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def remap_words(transcript: dict, segments: list[dict], replace: dict[str, str]) -> list[dict]:
    """Move word timestamps from the source timeline onto the edited (cut) timeline."""
    fixes = {k.lower(): v for k, v in (replace or {}).items()}
    words = [w for s in transcript.get("segments", []) for w in s.get("words", [])]
    out, offset = [], 0.0
    for seg in segments:
        s, e = seg["start"], seg["end"]
        for w in words:
            if s <= (w["start"] + w["end"]) / 2 < e:
                token = w["word"]
                core = re.sub(r"[^\w']", "", token).lower()
                if core in fixes:
                    token = re.sub(re.escape(core), lambda _: fixes[core], token, count=1, flags=re.I)
                out.append({"start": offset + max(w["start"], s) - s,
                            "end": offset + min(w["end"], e) - s, "word": token})
        offset += e - s
    return out


def chunk_words(words: list[dict], per_line: int) -> list[list[dict]]:
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= per_line or w["start"] - cur[-1]["end"] > 0.6):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if w["word"][-1:] in ".?!":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def write_ass(path: Path, W: int, H: int, words: list[dict], cap: dict, hook: dict | None) -> None:
    size = int(cap.get("size") or min(W, H) * 0.072)
    font = cap.get("font", "Arial")
    base, hl = cap.get("color", "#FFFFFF"), cap.get("highlight")
    if cap.get("position", "lower") == "middle":
        align, margin_v = 5, 0
    else:
        align, margin_v = 2, int(H * (0.22 if H > W else 0.08))
    hook = hook or {}
    hook_size = int(hook.get("size") or size * 1.05)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{font},{size},{style_color(base)},&H000000FF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{max(3, size // 14)},2,{align},80,80,{margin_v},1",
        f"Style: Hook,{hook.get('font', font)},{hook_size},{style_color(hook.get('color', '#111111'))},"
        f"&H000000FF,{style_color(hook.get('box', '#FFFFFF'))},&H00000000,"
        f"-1,0,0,0,100,100,0,0,3,{max(10, hook_size // 5)},0,8,90,90,{int(H * 0.11)},1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if hook.get("text"):
        lines.append(f"Dialogue: 1,{ass_time(hook.get('start', 0))},{ass_time(hook.get('end', 3))},"
                     f"Hook,,0,0,0,,{ass_text(hook['text'])}")
    chunks = chunk_words(words, int(cap.get("words_per_line", 3))) if cap.get("enabled", True) else []
    for ci, ch in enumerate(chunks):
        end = ch[-1]["end"]
        nxt = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else None
        end = nxt if nxt is not None and nxt - end < 0.35 else end + 0.15
        tokens = [ass_text(w["word"].upper() if cap.get("uppercase") else w["word"]) for w in ch]
        if hl:
            for wi, w in enumerate(ch):
                st = ch[0]["start"] if wi == 0 else w["start"]
                en = ch[wi + 1]["start"] if wi + 1 < len(ch) else end
                if en <= st:
                    continue
                text = " ".join(f"{{\\c{inline_color(hl)}}}{t}{{\\c{inline_color(base)}}}" if j == wi else t
                                for j, t in enumerate(tokens))
                lines.append(f"Dialogue: 0,{ass_time(st)},{ass_time(en)},Caption,,0,0,0,,{text}")
        else:
            lines.append(f"Dialogue: 0,{ass_time(ch[0]['start'])},{ass_time(end)},Caption,,0,0,0,,{' '.join(tokens)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- render ----------

def platform_warnings(duration: float, size_mb: float, W: int, H: int) -> list[str]:
    w = []
    if duration < 3:
        w.append("Video is under 3 s - Instagram, Facebook and LinkedIn will reject it.")
    if duration > 90:
        w.append("Over 90 s - Facebook Reels will reject it (max 90 s). Drop facebook or cut it shorter.")
    if duration > 180 or W > H:
        w.append("YouTube will treat this as a regular video, not a Short (Shorts = vertical/square and <= 3 min).")
    if duration > 900:
        w.append("Over 15 min - Instagram Reels will reject it.")
    if size_mb > 300:
        w.append(f"{size_mb} MB - over Instagram's 300 MB limit.")
    return w


def render(draft_dir: Path) -> dict:
    plan = json.loads((draft_dir / "edit_plan.json").read_text(encoding="utf-8"))
    src = project_path(plan["source"])
    info = probe(src)
    dur = info["duration"]
    segs = plan.get("segments") or [{"start": 0.0, "end": dur}]
    segs = [{"start": max(0.0, float(s["start"])), "end": min(dur, float(s["end"]))} for s in segs]
    segs = [s for s in segs if s["end"] - s["start"] > 0.05]
    if not segs:
        sys.exit("edit_plan.json has no valid segments")
    total = sum(s["end"] - s["start"] for s in segs)
    W, H = SIZES.get(plan.get("aspect", "9:16"), SIZES["9:16"])
    fps = int(plan.get("fps", 30))
    has_audio = info["has_audio"]

    inputs: list[str] = ["-i", str(src)]
    next_idx = 1
    logo_cfg, music_cfg = plan.get("logo"), plan.get("music")
    logo_idx = music_idx = silence_idx = None
    if logo_cfg and logo_cfg.get("file") and project_path(logo_cfg["file"]).exists():
        inputs += ["-i", str(project_path(logo_cfg["file"]))]
        logo_idx, next_idx = next_idx, next_idx + 1
    elif logo_cfg:
        print(f"Note: logo file not found ({logo_cfg.get('file')}), skipping logo.")
    if music_cfg and music_cfg.get("file") and project_path(music_cfg["file"]).exists():
        inputs += ["-stream_loop", "-1", "-i", str(project_path(music_cfg["file"]))]
        music_idx, next_idx = next_idx, next_idx + 1
    if not has_audio:
        inputs += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        silence_idx, next_idx = next_idx, next_idx + 1

    f: list[str] = []
    for i, s in enumerate(segs):
        f.append(f"[0:v]trim=start={s['start']:.3f}:end={s['end']:.3f},setpts=PTS-STARTPTS[v{i}]")
        if has_audio:
            f.append(f"[0:a]atrim=start={s['start']:.3f}:end={s['end']:.3f},asetpts=PTS-STARTPTS[a{i}]")
    n = len(segs)
    if has_audio:
        f.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")
    else:
        f.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc]")

    mode = plan.get("reframe", "crop")
    fx, fy = float(plan.get("focus_x", 0.5)), float(plan.get("focus_y", 0.5))
    if mode == "blur":
        f.append(f"[vc]split=2[bg][fg];"
                 f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:2,eq=brightness=-0.08[bgb];"
                 f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease:force_divisible_by=2[fgs];"
                 f"[bgb][fgs]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2,setsar=1,fps={fps}[vr]")
    elif mode == "fit":
        f.append(f"[vc]scale={W}:{H}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
                 f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps}[vr]")
    else:
        f.append(f"[vc]scale={W}:{H}:force_original_aspect_ratio=increase,"
                 f"crop={W}:{H}:(iw-ow)*{fx}:(ih-oh)*{fy},setsar=1,fps={fps}[vr]")
    last = "vr"

    cap = plan.get("captions") or {"enabled": False}
    hook = plan.get("hook_text")
    words: list[dict] = []
    transcript_file = draft_dir / "transcript.json"
    if cap.get("enabled", True) and transcript_file.exists():
        words = remap_words(json.loads(transcript_file.read_text(encoding="utf-8")), segs, cap.get("replace"))
    elif cap.get("enabled") and not transcript_file.exists():
        print("Note: captions enabled but transcript.json missing - run transcribe.py first. Skipping captions.")
    if words or (hook and hook.get("text")):
        write_ass(draft_dir / "captions.ass", W, H, words, cap, hook)
        sub = "subtitles=captions.ass"
        fonts = BRANDS / plan.get("brand", "main") / "fonts"
        if not (fonts.exists() and any(fonts.iterdir())):
            fonts = system_fonts_dir()
        if fonts:
            sub += ":fontsdir=" + os.path.relpath(fonts, draft_dir).replace("\\", "/")
        f.append(f"[{last}]{sub}[vs]")
        last = "vs"

    if logo_idx is not None:
        lw = int(W * float(logo_cfg.get("width_pct", 0.16))) // 2 * 2
        m = int(W * 0.045)
        pos = {"top-left": f"{m}:{m}", "top-right": f"main_w-overlay_w-{m}:{m}",
               "bottom-left": f"{m}:main_h-overlay_h-{m}",
               "bottom-right": f"main_w-overlay_w-{m}:main_h-overlay_h-{m}"}[logo_cfg.get("position", "top-right")]
        f.append(f"[{logo_idx}:v]scale={lw}:-1,format=rgba,colorchannelmixer=aa={float(logo_cfg.get('opacity', 0.9))}[lg]")
        f.append(f"[{last}][lg]overlay={pos}[vl]")
        last = "vl"
    f.append(f"[{last}]format=yuv420p[vout]")

    a = "ac" if has_audio else f"{silence_idx}:a"
    if has_audio and plan.get("normalize_audio", True):
        f.append(f"[{a}]loudnorm=I=-14:TP=-1.5:LRA=11[an]")
        a = "an"
    if music_idx is not None:
        f.append(f"[{music_idx}:a]volume={float(music_cfg.get('volume', 0.12))}[mu]")
        f.append(f"[{a}][mu]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[am]")
        a = "am"
    f.append(f"[{a}]aresample=48000,aformat=channel_layouts=stereo[aout]")

    out = draft_dir / plan.get("output", "final.mp4")
    ffmpeg = find_tool("ffmpeg")
    run([ffmpeg, "-y", "-v", "error", *inputs, "-filter_complex", ";".join(f),
         "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-g", str(fps * 2), "-keyint_min", str(fps * 2), "-sc_threshold", "0",
         "-maxrate", "12M", "-bufsize", "24M",
         "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
         "-movflags", "+faststart", "-t", f"{total:.3f}", out.name], cwd=draft_dir)

    thumb_t = min(float(plan.get("thumbnail_at", 1.0)), max(total - 0.1, 0))
    run([ffmpeg, "-y", "-v", "error", "-ss", f"{thumb_t:.2f}", "-i", str(out), "-frames:v", "1",
         "-q:v", "2", str(draft_dir / "thumbnail.jpg")])
    vertical = H > W
    contact_sheet(str(out), str(draft_dir / "preview.jpg"), count=8 if vertical else 9,
                  cols=4 if vertical else 3, thumb_w=270 if vertical else 400)
    result = probe(out)
    return {"output": str(out), "duration": round(result["duration"], 2), "size_mb": result["size_mb"],
            "resolution": f"{result['width']}x{result['height']}", "captions_words": len(words),
            "thumbnail": str(draft_dir / "thumbnail.jpg"), "preview": str(draft_dir / "preview.jpg"),
            "warnings": platform_warnings(result["duration"], result["size_mb"], W, H)}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    d = Path(sys.argv[1])
    d = d if d.is_absolute() else ROOT / d
    print_json(render(d.resolve()))
