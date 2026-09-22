"""
Synthesise a background bed and mix it under the narration.

Written rather than sourced, so there is no licence question on a competition
submission. It is a slow pad, no percussion and no melody, because the video is
dense with speech and anything rhythmic fights the read.

The chord is built from the 1x, 2x and 3x partials of a low fundamental, which
is the same harmonic structure the tool diagnoses machines with.

  python video/music.py            -> video/TREMOR_demo_final.mp4
"""
import pathlib, subprocess, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "TREMOR_demo_vo.mp4"          # video + narration
OUT = ROOT / "TREMOR_demo_final.mp4"
BED = ROOT / "vo" / "bed.wav"
SR = 48000
BED_DB = -23.0                              # under speech, felt more than heard

# An open Dsus2 voicing, spread wide and starting in the middle register rather
# than on a sub bass. Pure sines, so there is nothing harsh to filter out, and
# no third, which keeps it from reading as either happy or sad underneath a
# technical narration.
VOICES = [
    (146.83, 0.30),   # D3
    (220.00, 0.26),   # A3
    (293.66, 0.24),   # D4
    (329.63, 0.20),   # E4
    (440.00, 0.14),   # A4
    (587.33, 0.09),   # D5
    (880.00, 0.045),  # A5, air only
]

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"failed: {' '.join(str(c) for c in cmd[:10])}\n{r.stderr[-1200:]}")


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=nw=1:nk=1", str(p)],
        capture_output=True, text=True).stdout or 0)


def pad(seconds):
    t = np.arange(int(seconds * SR)) / SR
    rng = np.random.default_rng(11)
    left = np.zeros_like(t)
    right = np.zeros_like(t)
    for hz, amp in VOICES:
        # Each voice breathes on its own slow cycle and never fully closes, so
        # the bed drifts instead of pulsing.
        period = rng.uniform(19.0, 44.0)
        env = 0.66 + 0.34 * np.sin(2 * np.pi * t / period + rng.uniform(0, 6.28))
        det = hz * 0.0006                    # a few cents of detune for width
        left += amp * env * np.sin(2 * np.pi * (hz - det) * t + rng.uniform(0, 6.28))
        right += amp * env * np.sin(2 * np.pi * (hz + det) * t + rng.uniform(0, 6.28))

    swell = 0.84 + 0.16 * np.sin(2 * np.pi * t / 67.0)
    left *= swell
    right *= swell
    n_f = int(5.0 * SR)
    ramp = np.sin(np.linspace(0, np.pi / 2, n_f)) ** 2
    for ch in (left, right):
        ch[:n_f] *= ramp
        ch[-n_f:] *= ramp[::-1]

    st = np.stack([left, right], 1)
    st /= np.abs(st).max() + 1e-9
    return (st * 0.9 * 32767).astype(np.int16)


def main():
    if not SRC.exists():
        sys.exit("run video/voiceover.py first")
    BED.parent.mkdir(exist_ok=True)
    total = dur(SRC)

    import wave
    with wave.open(str(BED), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pad(total + 1).tobytes())
    print(f"  bed: {dur(BED):.1f}s")

    # Duck the bed against the narration rather than picking one fixed level, so
    # it opens up in the gaps between lines and stays out of the way under them.
    run(["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", str(SRC), "-i", str(BED),
         "-filter_complex",
         f"[1:a]highpass=f=90,lowpass=f=6500,volume={BED_DB}dB,alimiter=limit=0.9[bed];"
         "[0:a]asplit=2[vo][key];"
         "[bed][key]sidechaincompress=threshold=0.030:ratio=8:attack=14:"
         "release=620:makeup=1[duck];"
         "[vo][duck]amix=inputs=2:normalize=0:dropout_transition=0,"
         "loudnorm=I=-16:TP=-1.5:LRA=11[out]",
         "-map", "0:v", "-map", "[out]", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
         "-y", str(OUT)])
    print(f"\n{OUT}  {dur(OUT):.1f}s  {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
