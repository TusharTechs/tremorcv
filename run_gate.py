"""DAY 1-3 GO/NO-GO GATE. No camera, no hardware. Ground truth is exact by construction."""
import numpy as np
from tremor.synth import make_clip
from tremor.measure import analyze

FPS, SECS, SIZE = 30, 10, (480, 640)
TGT = (40, 40, 256, 400)    # ROI on the moving half
REF = (330, 40, 256, 400)   # ROI on the static half

def run(freq, amp, shake=0.0, noise=2.0):
    fr, _ = make_clip(freq, amp, FPS, SECS, SIZE, noise_dn=noise, shake_px=shake)
    return analyze(fr, FPS, TGT, REF)

print(f"\n{'='*78}\nTREMOR gate  |  {FPS} fps, {SECS}s, bin = {FPS/(FPS*SECS):.2f} Hz, "
      f"sensor noise 2 DN\n{'='*78}")

print("\nA. FREQUENCY ACCURACY  (amplitude fixed at 0.30 px -- invisible to the eye)")
print(f"{'true Hz':>9}{'meas Hz':>10}{'err Hz':>9}{'SNR':>8}{'trust':>8}")
for f in [1.7, 3.3, 7.3, 11.9, 14.2]:
    r = run(f, 0.30)
    print(f"{f:9.2f}{r['freq_hz']:10.2f}{r['freq_hz']-f:+9.2f}{r['snr']:8.1f}{str(r['trust']):>8}")

print("\nB. AMPLITUDE FLOOR  (7.3 Hz -- how small a motion can we still measure?)")
print(f"{'true px':>9}{'meas px':>10}{'err %':>9}{'SNR':>8}{'trust':>8}")
for a in [1.0, 0.30, 0.10, 0.03, 0.01, 0.003]:
    r = run(7.3, a)
    e = (r['amp_px']-a)/a*100
    print(f"{a:9.3f}{r['amp_px']:10.4f}{e:+9.1f}{r['snr']:8.1f}{str(r['trust']):>8}")

print("\nC. CAMERA SHAKE REJECTION  (7.3 Hz @ 0.10 px, handheld with NO tripod)")
print(f"{'shake px':>9}{'meas Hz':>10}{'meas px':>10}{'shake/sig':>11}{'SNR':>8}{'trust':>8}")
for s in [0.0, 0.5, 2.0, 10.0, 50.0]:
    r = run(7.3, 0.10, shake=s)
    print(f"{s:9.1f}{r['freq_hz']:10.2f}{r['amp_px']:10.4f}"
          f"{r['shake_ratio']:11.1f}{r['snr']:8.1f}{str(r['trust']):>8}")

print("\nD. NO STABILIZATION  (same clips, static-reference subtraction turned OFF)")
from tremor.synth import make_clip as mk
from tremor.measure import analyze as an
print(f"{'shake px':>9}{'meas Hz':>10}{'meas px':>10}{'verdict':>28}")
for s in [0.0, 2.0, 10.0]:
    fr, _ = mk(7.3, 0.10, FPS, SECS, SIZE, noise_dn=2.0, shake_px=s)
    r = an(fr, FPS, TGT, None)
    ok = abs(r['freq_hz']-7.3) < 0.2
    print(f"{s:9.1f}{r['freq_hz']:10.2f}{r['amp_px']:10.4f}"
          f"{'recovered' if ok else 'WRONG -- shake wins':>28}")
print()
