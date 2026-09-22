"""TREMOR core measurement: sub-pixel displacement -> spectrum -> frequency + amplitude.

Pipeline (all OpenCV 5 classical imgproc/core -- the COOL-accelerated path):
  phaseCorrelate  : sub-pixel displacement of a ROI, frame-to-reference
  static ref ROI  : measures camera motion, subtracted -> stabilization
  Hann + cv2.dft  : temporal spectrum of the displacement trace
  peak + noise flr: frequency, amplitude, SNR -> quality gate
"""
import numpy as np, cv2


def roi_trace(frames, roi, return_response=False):
    """Displacement (px) of `roi` in every frame, relative to frame 0, sub-pixel.

    Also returns phaseCorrelate's `response` -- the normalised correlation-peak
    strength. It is easy to discard (the 3rd tuple element) but it is the library
    telling you how much it trusts each estimate, and a small fraction of frames
    fail catastrophically (tens of pixels on a sub-pixel signal). See clean_trace.
    """
    x, y, w, h = roi
    win = cv2.createHanningWindow((w, h), cv2.CV_32F)
    base = np.ascontiguousarray(frames[0][y:y + h, x:x + w], np.float32)
    out = np.zeros((len(frames), 2))
    resp = np.zeros(len(frames))
    for i, f in enumerate(frames):
        cur = np.ascontiguousarray(f[y:y + h, x:x + w], np.float32)
        (dx, dy), r = cv2.phaseCorrelate(base, cur, win)
        out[i] = (dx, dy)
        resp[i] = r
    return (out, resp) if return_response else out


def clean_trace(dx, response=None, mad_k=6.0, resp_frac=0.55, max_reject=0.35):
    """Reject catastrophic phaseCorrelate failures and interpolate across them.

    Two independent detectors, because neither alone is sufficient:
      * MAD  -- true vibration is bounded and smooth, so a sample many robust
                deviations from the median is not physical.
      * response -- OpenCV's own confidence; failures correlate with low values.

    Returns (cleaned, reject_fraction). A high reject fraction is itself a signal:
    the agent treats it as a reason to re-acquire rather than silently patching.
    """
    dx = np.asarray(dx, float).copy()
    n = len(dx)
    med = np.median(dx)
    mad = np.median(np.abs(dx - med)) * 1.4826
    bad = np.abs(dx - med) > mad_k * max(mad, 1e-6)
    if response is not None:
        r = np.asarray(response, float)
        good_med = np.median(r[~bad]) if (~bad).any() else np.median(r)
        bad |= r < resp_frac * good_med
    frac = float(bad.mean())
    if frac > max_reject:          # too broken to repair -- let the caller see it
        return dx, frac
    if bad.any() and (~bad).any():
        idx = np.arange(n)
        dx[bad] = np.interp(idx[bad], idx[~bad], dx[~bad])
    return dx, frac


def spectrum(trace, fps):
    """One-sided amplitude spectrum of a 1-D displacement trace."""
    x = np.asarray(trace, np.float64)
    x = x - x.mean()
    n = len(x)
    w = np.hanning(n)
    # coherent gain correction so peak height == true sine amplitude
    X = np.fft.rfft(x * w) * 2.0 / w.sum()
    return np.fft.rfftfreq(n, 1 / fps), np.abs(X)


def analyze(frames, fps, target_roi, static_roi=None, fmin=0.5):
    """Measure the dominant vibration. Returns freq (Hz), amplitude (px), SNR, quality."""
    tgt = roi_trace(frames, target_roi)[:, 0]
    cam = roi_trace(frames, static_roi)[:, 0] if static_roi else np.zeros_like(tgt)

    # Stabilization is NOT free: both ROIs carry independent measurement noise,
    # so subtracting a near-zero reference just adds sqrt(2)x noise. Only
    # subtract when the camera is actually moving. (This becomes an agent decision.)
    cam_rms = float(np.std(cam))
    stabilized = cam_rms > 0.5 * float(np.std(tgt))
    sig = tgt - cam if stabilized else tgt

    f, A = spectrum(sig, fps)
    band = f >= fmin
    k = np.argmax(A[band]) + np.flatnonzero(band)[0]

    # noise floor = median amplitude excluding a window around the peak
    mask = band.copy()
    mask[max(0, k - 3):k + 4] = False
    floor = np.median(A[mask]) if mask.any() else 0.0
    snr = A[k] / floor if floor > 0 else np.inf

    # how much of the motion was the camera, not the target
    sig_rms = np.std(sig)
    shake_ratio = cam_rms / sig_rms if sig_rms > 0 else np.inf

    # Noise adds in quadrature to the peak bin, biasing small amplitudes high.
    # |X_peak|^2 ~ A^2 + E[|noise|^2]; for Rayleigh noise E[|n|^2] = 1.44 * median^2.
    amp = float(np.sqrt(max(A[k] ** 2 - 1.44 * floor ** 2, 0.0)))

    return dict(
        freq_hz=float(f[k]), amp_px=amp, amp_raw_px=float(A[k]), snr=float(snr),
        noise_floor_px=float(floor), cam_rms_px=cam_rms, stabilized=stabilized,
        shake_ratio=float(shake_ratio), bin_hz=float(f[1]),
        # the agent's quality gate -- this is what triggers "re-shoot"
        trust=bool(snr >= 6.0 and shake_ratio < 3.0),
        freqs=f, amps=A, trace=sig,
    )
