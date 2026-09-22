"""Measure vibration from a real video file. Streams ROIs -- never loads the whole clip."""
import sys, numpy as np, cv2
from tremor.measure import spectrum

def trace_rois(path, rois):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    wins, bases, out = {}, {}, {k: [] for k in rois}
    while True:
        ok, fr = cap.read()
        if not ok: break
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        for k, (x, y, w, h) in rois.items():
            cur = np.ascontiguousarray(g[y:y+h, x:x+w])
            if k not in bases:
                bases[k] = cur.copy()
                wins[k] = cv2.createHanningWindow((w, h), cv2.CV_32F)
            (dx, dy), _ = cv2.phaseCorrelate(bases[k], cur, wins[k])
            out[k].append((dx, dy))
    cap.release()
    return fps, {k: np.array(v) for k, v in out.items()}

if __name__ == "__main__":
    path = sys.argv[1]
    ROIS = dict(target=(610, 120, 330, 310), static=(1010, 120, 330, 310))
    fps, tr = trace_rois(path, ROIS)
    tgt, cam = tr["target"][:, 0], tr["static"][:, 0]
    n = len(tgt)
    print(f"\n{path.split('/')[-1]}  |  {n} frames @ {fps:.3f} fps = {n/fps:.1f}s  "
          f"| bin = {fps/n:.3f} Hz\n")

    for name, sig in [("RAW target (no stabilization)", tgt),
                      ("STATIC reference (camera motion)", cam),
                      ("STABILIZED  target - reference", tgt - cam)]:
        f, A = spectrum(sig, fps)
        band = f >= 0.5
        k = np.argmax(A[band]) + np.flatnonzero(band)[0]
        mask = band.copy(); mask[max(0, k-3):k+4] = False
        floor = np.median(A[mask])
        print(f"{name:34s} rms={np.std(sig):7.3f} px   peak={f[k]:6.2f} Hz   "
              f"amp={A[k]:6.3f} px   SNR={A[k]/floor:6.1f}")

    f, A = spectrum(tgt - cam, fps)
    band = (f >= 0.5)
    top = sorted(zip(A[band], f[band]), reverse=True)[:5]
    print("\n  top 5 peaks (stabilized):  " +
          "   ".join(f"{fr:.2f} Hz ({a:.3f} px)" for a, fr in top))
