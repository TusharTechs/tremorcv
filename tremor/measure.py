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
    strength, which is useful as a per-frame confidence. See clean_trace.

    IMPORTANT -- cv2.phaseCorrelate MUTATES BOTH SOURCE ARRAYS.
    It multiplies each src by the window in place. Reusing one array as the
    reference across calls therefore decays it as `base * window**N`: with a
    Hanning window (0.99992 at centre, 0.0078 at the edge) the edges vanish after
    ~2 calls and the usable aperture collapses by ~700, after which the
    correlation fails catastrophically -- tens of pixels of error on a sub-pixel
    signal. Verified against OpenCV 5.0.0: observed base matched
    `orig * window**N` to 7 significant figures at N = 1, 2, 10, 100, 700.

    Hence `base.copy()` below. `cur` is rebuilt every iteration, so letting the
    call consume it is harmless. Covered by tests/test_phasecorrelate_mutation.py.
    """
    x, y, w, h = roi
    win = cv2.createHanningWindow((w, h), cv2.CV_32F)
    base = np.ascontiguousarray(frames[0][y:y + h, x:x + w], np.float32)
    out = np.zeros((len(frames), 2))
    resp = np.zeros(len(frames))
    for i, f in enumerate(frames):
        cur = np.ascontiguousarray(f[y:y + h, x:x + w], np.float32)
        (dx, dy), r = cv2.phaseCorrelate(base.copy(), cur, win)
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


def auto_rois(frames, fps, box_frac=0.30, n_probe=150, min_texture=6.0,
              hp_cut_hz=2.5):
    """Find what is VIBRATING, and something rigid to reference it against.

    Splitting a frame in half is a bad default: on real footage the machine may
    occupy a fraction of the shot, and averaging it with static background dilutes
    the signal (measured on one clip: SNR 196 with hand-placed ROIs, 4.1 with a
    half-split).

    But raw temporal energy is also wrong, and fails in an instructive way. With a
    handheld camera everything moves, so the highest-energy region is wherever
    contrast x camera-shake is largest -- on a real test clip that selected the
    laptop keyboard as the "machine" and the actually-oscillating target as the
    "static" reference.

    Hand motion is overwhelmingly slow: measured on real iPhone footage, 78.6% of
    its energy sits below 1 Hz and only 0.7% lands in the 5-15 Hz band where
    machine vibration lives. So temporally high-pass each pixel first -- subtract a
    moving average over ~1/hp_cut_hz seconds -- and the remaining energy is
    vibration rather than sway.

    Returns (target_roi, static_roi, diagnostics).
    """
    n, H, W = len(frames), frames[0].shape[0], frames[0].shape[1]
    scale = min(1.0, 320.0 / max(W, 1))
    # contiguous window: the high-pass needs real temporal adjacency, not a
    # sparse sample across the clip
    take = min(n_probe, n)
    start = max(0, (n - take) // 2)
    small = np.stack([cv2.resize(np.asarray(frames[i], np.float32), (0, 0),
                                 fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                      for i in range(start, start + take)])
    h, w = small.shape[1:]

    k = max(3, int(round(fps / max(hp_cut_hz, 0.1))) | 1)      # odd kernel
    if k < take:
        pad = k // 2
        padded = np.pad(small, ((pad, pad), (0, 0), (0, 0)), mode="edge")
        kern = np.ones(k, np.float32) / k
        baseline = np.apply_along_axis(
            lambda col: np.convolve(col, kern, mode="valid"), 0, padded)
        hp = small - baseline[:take]
    else:
        hp = small - small.mean(axis=0, keepdims=True)

    motion = cv2.GaussianBlur(hp.std(axis=0), (0, 0), 2.0)
    mean_f = small.mean(axis=0)
    mu = cv2.blur(mean_f, (9, 9))
    texture = np.sqrt(np.maximum(cv2.blur(mean_f * mean_f, (9, 9)) - mu * mu, 0))

    bw, bh = max(int(w * box_frac), 16), max(int(h * box_frac), 16)
    m_box = cv2.boxFilter(motion, -1, (bw, bh), normalize=True)
    t_box = cv2.boxFilter(texture, -1, (bw, bh), normalize=True)
    usable = t_box >= min_texture
    if not usable.any():
        usable = t_box >= np.percentile(t_box, 75)

    half_w, half_h = bw // 2, bh // 2
    valid = np.zeros_like(usable)
    valid[half_h:h - half_h, half_w:w - half_w] = True
    ok = usable & valid
    if not ok.any():
        ok = valid

    tgt_c = np.unravel_index(np.argmax(np.where(ok, m_box, -np.inf)), m_box.shape)
    away = np.ones_like(ok)
    y0, y1 = max(0, tgt_c[0] - bh), min(h, tgt_c[0] + bh)
    x0, x1 = max(0, tgt_c[1] - bw), min(w, tgt_c[1] + bw)
    away[y0:y1, x0:x1] = False
    ref_ok = ok & away
    if not ref_ok.any():
        ref_ok = valid & away
    ref_c = np.unravel_index(np.argmin(np.where(ref_ok, m_box, np.inf)), m_box.shape)

    def to_full(cy, cx):
        x = int((cx - half_w) / scale); y = int((cy - half_h) / scale)
        ww = int(bw / scale); hh = int(bh / scale)
        x = max(0, min(x, W - ww)); y = max(0, min(y, H - hh))
        return (x, y, ww, hh)

    diag = {"vibration_target": float(m_box[tgt_c]),
            "vibration_reference": float(m_box[ref_c]),
            "texture_target": float(t_box[tgt_c]),
            "texture_reference": float(t_box[ref_c]),
            "highpass_cut_hz": hp_cut_hz, "probe_frames": int(take)}
    return to_full(*tgt_c), to_full(*ref_c), diag
