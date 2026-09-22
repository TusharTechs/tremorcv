"""Evaluation on realistic simulated machines. Ground truth exact by construction."""
import numpy as np
from tremor.machine import make_machine_clip
from tremor.measure import roi_trace, spectrum

FPS, SECS = 30, 20
TGT, REF = (30, 40, 320, 400), (410, 40, 320, 400)

def measure(frames, stabilize=True):
    tgt = roi_trace(frames, TGT)[:, 0]
    cam = roi_trace(frames, REF)[:, 0]
    sig = tgt - cam if stabilize else tgt
    return spectrum(sig, FPS)

def peaks_near(f, A, targets, tol=0.35):
    """Amplitude at each expected fault frequency (max within tol Hz)."""
    out = []
    for ft in targets:
        m = np.abs(f - ft) <= tol
        k = np.flatnonzero(m)[np.argmax(A[m])]
        out.append((f[k], A[k]))
    return out

def floor_of(f, A, exclude, tol=0.5):
    m = f >= 0.5
    for ft in exclude: m &= np.abs(f - ft) > tol
    return np.median(A[m])

# Classic misalignment signature: 1x unbalance + dominant 2x + small 3x
SIG = [(7.3, 0.40), (14.6, 0.60), (21.9, 0.15)]   # note 21.9 Hz > Nyquist(15) -> aliases
SIG = [(3.1, 0.40), (6.2, 0.60), (9.3, 0.15)]     # keep all components under Nyquist
TRUE = [f for f, _ in SIG]

CASES = [
    ("baseline (tripod, detailed surface)", dict()),
    ("+ real handheld shake (20.5 px rms)", dict(shake_rms=20.5)),
    ("+ rolling shutter",                   dict(shake_rms=20.5, rolling=True)),
    ("+ specular glare",                    dict(shake_rms=20.5, rolling=True, glare=True)),
    ("+ H.264 compression",                 dict(shake_rms=20.5, rolling=True, glare=True, compress=True)),
    ("SMOOTH surface (contrast 0.15)",      dict(shake_rms=20.5, rolling=True, glare=True,
                                                 compress=True, contrast=0.15)),
]

print(f"\n{'='*94}\nSimulated machine  |  true components: "
      + ", ".join(f"{f} Hz @ {a} px" for f, a in SIG)
      + f"\n{FPS} fps, {SECS}s, bin {FPS/(FPS*SECS):.3f} Hz, real handheld motion replayed "
        f"from your iPhone clip\n{'='*94}")
print(f"{'condition':38}{'1x err':>9}{'2x err':>9}{'3x err':>9}{'amp err 2x':>12}{'SNR':>8}{'verdict':>9}")

for name, kw in CASES:
    fr = make_machine_clip(SIG, FPS, SECS, **kw)
    f, A = measure(fr)
    pk = peaks_near(f, A, TRUE)
    fl = floor_of(f, A, TRUE)
    errs = [p[0] - t for p, t in zip(pk, TRUE)]
    amp2 = (pk[1][1] - SIG[1][1]) / SIG[1][1] * 100
    snr = pk[1][1] / fl
    ok = all(abs(e) < 0.15 for e in errs) and snr > 6
    print(f"{name:38}{errs[0]:+9.3f}{errs[1]:+9.3f}{errs[2]:+9.3f}"
          f"{amp2:+11.1f}%{snr:8.1f}{'PASS' if ok else 'FAIL':>9}")

print(f"\n{'-'*94}\nSTABILIZATION ABLATION (hardest case: shake+rolling+glare+H.264)")
fr = make_machine_clip(SIG, FPS, SECS, shake_rms=20.5, rolling=True, glare=True, compress=True)
for lbl, st in [("stabilized", True), ("NOT stabilized", False)]:
    f, A = measure(fr, st)
    pk = peaks_near(f, A, TRUE)
    print(f"  {lbl:16} 1x={pk[0][0]:6.2f} Hz  2x={pk[1][0]:6.2f} Hz  3x={pk[2][0]:6.2f} Hz   "
          f"(true {TRUE[0]}/{TRUE[1]}/{TRUE[2]})")
print()
