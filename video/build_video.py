"""
Cut the recorded segments into one file, with timed text callouts.

Trim points come from video/raw/marks.json, which record_demo.py writes from
timestamps it actually took -- nothing here is eyeballed off a frame.

  python video/build_video.py            -> video/TREMOR_demo.mp4

The upload scene contains ~25 s of real computation. It is shown at 3x with a
label saying so, because silently speeding it up would misstate how fast it is.
"""
import json, pathlib, subprocess, sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
RAW, WORK = ROOT / "raw", ROOT / "work"
OUT = ROOT / "TREMOR_demo.mp4"
MONO = "/System/Library/Fonts/Supplemental/Andale Mono.ttf"

RAMP = {"02_real.webm": 3.0}          # segment -> how much to compress dead compute

# (start_s, duration_s, LABEL, value, where) -- times are in the FINAL segment
# timeline, i.e. after the speed ramp has been applied.
CALLOUTS = {
    "02_real.webm": [
        (12.8, 6.2, "GROUND TRUTH 7.30 HZ", "measured 7.28 Hz  ·  0.3% error", "bottom"),
        (19.4, 4.4, "CAMERA MOTION", "20 px of hand shake, cancelled", "bottom"),
    ],
    "03_agent.webm": [
        (13.6, 5.2, "STEP 1", "SNR too low, so it asked for a better shot", "bottom"),
        (19.2, 4.2, "STEP 2", "1x / 2x / 3x ratios  ->  mechanical looseness", "bottom"),
    ],
}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed:\n{' '.join(cmd[:12])} ...\n{r.stderr[-1800:]}")


def dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True).stdout)


def chip(path, label, value=None, pad=26):
    """A caption chip: small dim label over a bright value line."""
    fv = ImageFont.truetype(MONO, 34)
    fl = ImageFont.truetype(MONO, 20)
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    wv = int(probe.textlength(value or label, font=fv))
    wl = int(probe.textlength(label, font=fl)) if value else 0
    w = max(wv, wl) + pad * 2
    h = pad * 2 + (34 + 14 + 20 if value else 34) - 4
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 12, fill=(15, 21, 29, 238),
                        outline=(77, 212, 196, 255), width=2)
    if value:
        d.text((pad, pad - 4), label, font=fl, fill=(138, 153, 173, 255))
        d.text((pad, pad + 20), value, font=fv, fill=(77, 212, 196, 255))
    else:
        d.text((pad, pad - 4), label, font=fv, fill=(77, 212, 196, 255))
    img.save(path)
    return path


def main():
    if not (RAW / "marks.json").exists():
        sys.exit("run video/record_demo.py first")
    m = json.loads((RAW / "marks.json").read_text())
    WORK.mkdir(exist_ok=True)
    ramp_chip = chip(WORK / "chip_ramp.png", "real compute  ·  25 s shown at 3x")

    parts = []
    for seg in sorted(m):
        src = RAW / seg
        dst = WORK / seg.replace(".webm", ".mp4")
        t = {x["tag"]: x["t"] for x in m[seg]}
        z = t["start"]
        t = {k: round(v - z, 2) for k, v in t.items()}
        end = t["end"]
        base = "fps=30,scale=1920:1080:flags=lanczos,setsar=1"

        inputs = ["-i", str(src)]
        if seg in RAMP and "crunch_start" in t:
            a, b, k = t["crunch_start"], t["crunch_end"], RAMP[seg]
            inputs += ["-i", str(ramp_chip)]
            fc = (f"[0:v]{base}[v];[v]split=3[p1][p2][p3];"
                  f"[p1]trim=0:{a},setpts=PTS-STARTPTS[a];"
                  f"[p2]trim={a}:{b},setpts=(PTS-STARTPTS)/{k}[b0];"
                  f"[b0][1:v]overlay=W-w-46:H-h-46[b];"
                  f"[p3]trim={b}:{end},setpts=PTS-STARTPTS[c];"
                  f"[a][b][c]concat=n=3:v=1:a=0[cur]")
            nxt = 2
        else:
            fc = f"[0:v]trim=0:{end},setpts=PTS-STARTPTS,{base}[cur]"
            nxt = 1

        cur = "[cur]"
        for i, (st, du, lab, val, where) in enumerate(CALLOUTS.get(seg, [])):
            inputs += ["-i", str(chip(WORK / f"chip_{seg[:2]}_{i}.png", lab, val))]
            y = "H-h-58" if where == "bottom" else "58"
            tag = f"[c{i}]"
            fc += (f";{cur}[{nxt}:v]overlay=(W-w)/2:{y}:"
                   f"enable='between(t,{st},{round(st + du, 2)})'{tag}")
            cur, nxt = tag, nxt + 1

        run(["ffmpeg", "-hide_banner", "-loglevel", "error", *inputs,
             "-filter_complex", fc, "-map", cur,
             "-c:v", "libx264", "-preset", "slow", "-crf", "19",
             "-pix_fmt", "yuv420p", "-y", str(dst)])
        print(f"  {seg:16s} -> {dur(dst):6.2f}s"
              f"{'  +' + str(len(CALLOUTS[seg])) + ' callouts' if seg in CALLOUTS else ''}")
        parts.append(dst)

    lst = WORK / "concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run(["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", str(lst),
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p",
         "-vf", "fade=in:0:12", "-c:a", "aac", "-b:a", "128k", "-shortest",
         "-movflags", "+faststart", "-y", str(OUT)])

    d = dur(OUT)
    print(f"\n{OUT}  {int(d // 60)}:{d % 60:04.1f}  {OUT.stat().st_size / 1e6:.1f} MB")
    if d > 300:
        print("  WARNING: over the five minute limit")


if __name__ == "__main__":
    main()
