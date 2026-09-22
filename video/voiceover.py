"""
Generate a narration track and lay it under the cut.

Uses the macOS speech synthesiser. This is a stand-in so the video is watchable
with sound: record the same lines in your own voice and drop them in instead.

  python video/voiceover.py            -> video/TREMOR_demo_vo.mp4

Lines live in NARRATION as (start_seconds, text). Start times are cues into the
assembled TREMOR_demo.mp4, so re-run this after any rebuild that moves them.
"""
import pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent
VO = ROOT / "vo"
SRC = ROOT / "TREMOR_demo.mp4"
OUT = ROOT / "TREMOR_demo_vo.mp4"
VOICE = "Ava (Premium)"
RATE = 192          # words per minute


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"failed: {' '.join(str(c) for c in cmd[:10])}\n{r.stderr[-1200:]}")


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=nw=1:nk=1", str(p)],
        capture_output=True, text=True).stdout or 0)


def build(narration, src=SRC, out=OUT):
    VO.mkdir(exist_ok=True)
    total = dur(src)
    clips = []
    for i, (start, text) in enumerate(narration):
        aiff, wav = VO / f"{i:02d}.aiff", VO / f"{i:02d}.wav"
        run(["say", "-v", VOICE, "-r", str(RATE), "-o", str(aiff), text])
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(aiff),
             "-ar", "48000", "-ac", "2", "-y", str(wav)])
        d = dur(wav)
        clips.append((start, wav, d))
        print(f"  {start:6.1f}s  {d:5.1f}s  {text[:58]}...")

    over = [(s, s + d, w) for s, w, d in clips]
    for (s1, e1, _), (s2, _, _) in zip(over, over[1:]):
        if e1 > s2 + 0.05:
            print(f"  OVERRUN: line ending {e1:.1f}s runs into the next at {s2:.1f}s")
    if over and over[-1][1] > total:
        print(f"  OVERRUN: last line ends {over[-1][1]:.1f}s, video is {total:.1f}s")

    ins, filt = [], []
    for i, (start, wav, _) in enumerate(clips):
        ins += ["-i", str(wav)]
        filt.append(f"[{i + 1}:a]adelay={int(start * 1000)}|{int(start * 1000)},"
                    f"volume=1.0[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(clips)))
    filt.append(f"{mix}amix=inputs={len(clips)}:normalize=0:dropout_transition=0,apad[vo]")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(src), *ins,
         "-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[vo]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
         "-movflags", "+faststart", "-y", str(out)])
    print(f"\n{out}  {dur(out):.1f}s")


if __name__ == "__main__":
    from narration import NARRATION
    build(NARRATION)
