"""The OpenCV 5 tool surface the agent can call.

Every tool returns plain JSON-serialisable data so each call can be logged to the
decision trace. The agent never touches pixels directly -- it reasons over these
measurements, and its decisions change which tool it calls next.
"""
from dataclasses import dataclass, asdict, field
import numpy as np, cv2
from tremor.measure import roi_trace, clean_trace, spectrum

# Thresholds below are not guesses: each was measured empirically in
# run_gate.py / run_machine_eval.py. See docs/THRESHOLDS.md.
SNR_TRUST = 6.0           # below this, frequency estimates were unreliable
TEXTURE_MIN_STD = 15.0    # contrast 0.15 -> std ~7 -> SNR collapsed to 1.6
ALIAS_FRACTION = 0.40     # peak above 0.4*fps is suspiciously near Nyquist
STABILIZE_WHEN = 0.5      # stabilize if cam_rms > 0.5 * target_rms
REJECT_FRAC_MAX = 0.15    # >15% of frames failing correlation = unusable clip


@dataclass
class Peak:
    freq_hz: float
    amp_px: float
    snr: float


@dataclass
class Measurement:
    peaks: list = field(default_factory=list)
    fps: float = 0.0
    duration_s: float = 0.0
    bin_hz: float = 0.0
    stabilized: bool = False
    cam_rms_px: float = 0.0
    signal_rms_px: float = 0.0
    nyquist_hz: float = 0.0
    reject_frac: float = 0.0
    noise_floor_px: float = 0.0

    # Full spectrum, kept for harmonic queries at arbitrary frequencies. Excluded
    # from dict() so large arrays never cross the MCP boundary.
    _freqs: object = None
    _amps: object = None

    def dict(self):
        d = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        d["peaks"] = [asdict(p) if not isinstance(p, dict) else p for p in self.peaks]
        return d

    def amp_at(self, hz, tol_hz=None):
        """Spectral amplitude near `hz`. Queries the SPECTRUM, not the peak list --
        a harmonic can carry real energy while ranking outside the top peaks."""
        if self._freqs is None or hz <= 0 or hz > self.nyquist_hz:
            return 0.0
        tol = tol_hz or max(3 * self.bin_hz, 0.25)
        m = np.abs(self._freqs - hz) <= tol
        return float(self._amps[m].max()) if m.any() else 0.0


def assess_surface(frames, roi):
    """Is there enough visual texture to phase-correlate? Cheap, runs first."""
    x, y, w, h = roi
    p = frames[0][y:y+h, x:x+w].astype(np.float32)
    m = cv2.blur(p, (15, 15))
    std = float(np.sqrt(max(cv2.blur(p * p, (15, 15)).mean() - (m * m).mean(), 0)))
    return {"texture_std": std, "sufficient": std >= TEXTURE_MIN_STD,
            "threshold": TEXTURE_MIN_STD}


def measure(frames, fps, target_roi, static_roi, n_peaks=4, fmin=0.5):
    """Sub-pixel displacement -> spectrum -> ranked peaks. The core OpenCV workload."""
    t_raw, t_resp = roi_trace(frames, target_roi, return_response=True)
    c_raw, c_resp = roi_trace(frames, static_roi, return_response=True)
    tgt, rej_t = clean_trace(t_raw[:, 0], t_resp)
    cam, rej_c = clean_trace(c_raw[:, 0], c_resp)
    reject_frac = max(rej_t, rej_c)
    cam_rms, tgt_rms = float(np.std(cam)), float(np.std(tgt))
    stabilized = cam_rms > STABILIZE_WHEN * tgt_rms
    sig = tgt - cam if stabilized else tgt

    f, A = spectrum(sig, fps)
    band = f >= fmin
    fb, Ab = f[band], A[band]
    floor_global = float(np.median(Ab)) if Ab.size else 0.0
    order = np.argsort(Ab)[::-1]

    picked, peaks = [], []
    for k in order:
        if any(abs(fb[k] - p) < 3 * (f[1] - f[0]) for p in picked):
            continue
        picked.append(fb[k])
        mask = np.ones_like(Ab, bool)
        mask[max(0, k - 3):k + 4] = False
        floor = float(np.median(Ab[mask]))
        peaks.append(Peak(float(fb[k]), float(Ab[k]), float(Ab[k] / floor) if floor else 0.0))
        if len(peaks) >= n_peaks:
            break

    return Measurement(peaks=peaks, fps=float(fps), duration_s=len(frames) / fps,
                       bin_hz=float(f[1]), stabilized=stabilized, cam_rms_px=cam_rms,
                       signal_rms_px=float(np.std(sig)), nyquist_hz=fps / 2.0,
                       reject_frac=reject_frac, noise_floor_px=floor_global,
                       _freqs=f, _amps=A)


def assess_quality(meas: Measurement, surface: dict):
    """Decide whether this measurement can be trusted, and if not, precisely why.

    The `reasons` are what the agent acts on -- each maps to a different remedy.
    """
    problems, top = [], (meas.peaks[0] if meas.peaks else None)
    if not surface["sufficient"]:
        problems.append("low_texture")
    if top is None or top.snr < SNR_TRUST:
        problems.append("low_snr")
    if top and top.freq_hz > ALIAS_FRACTION * meas.fps:
        problems.append("possible_aliasing")
    if meas.cam_rms_px > 8 * max(meas.signal_rms_px, 1e-6):
        problems.append("excessive_camera_motion")
    if meas.reject_frac > REJECT_FRAC_MAX:
        problems.append("unstable_correlation")
    return {"trustworthy": not problems, "reasons": problems,
            "top_snr": (top.snr if top else 0.0)}


HARMONIC_WEIGHTS = ((1, 1.0), (2, 0.9), (3, 0.6))
FUNDAMENTAL_MIN_SHARE = 0.15   # a real fundamental carries non-trivial energy itself


def estimate_shaft(meas: Measurement, fmin=0.5):
    """Harmonic-comb scoring over candidate fundamentals.

    Taking "the lowest strong peak" is wrong and was the dominant error source:
    for misalignment the 2x component dominates and 1x can sit below the SNR
    floor, so that heuristic returns twice the true shaft rate -- which then
    reads 2x as 1x and inverts the diagnosis to unbalance.

    Instead, score each candidate f0 by how much energy lands on its harmonic
    comb. The FUNDAMENTAL_MIN_SHARE guard is what stops f_true/2 winning: that
    candidate explains the true 1x as its own 2x, but has nothing at its own
    fundamental.
    """
    if not meas.peaks:
        return None
    cands = set()
    for p in meas.peaks:
        for div in (1, 2, 3):
            f0 = p.freq_hz / div
            if f0 >= fmin:
                cands.add(round(f0, 3))

    best, best_score = None, 0.0
    for f0 in sorted(cands):
        amps = {k: meas.amp_at(f0 * k) for k, _ in HARMONIC_WEIGHTS}
        peak = max(amps.values())
        if peak <= 0 or amps[1] < FUNDAMENTAL_MIN_SHARE * peak:
            continue
        score = sum(w * amps[k] for k, w in HARMONIC_WEIGHTS)
        if score > best_score:
            best, best_score = f0, score
    return best


HEALTHY_TOTAL_PX = 0.42    # below this, 1x-dominance is residual, not a fault
HARMONIC_MIN_SNR = 3.0     # a harmonic below 3x the noise floor is not measured, it is noise


def diagnose(meas: Measurement, shaft_hz: float, tol_hz=None,
             healthy_below=HEALTHY_TOTAL_PX):
    """Classic vibration rules over 1x/2x/3x amplitudes.

    Order matters: amplitude is checked BEFORE shape. A healthy machine and an
    unbalanced one have nearly identical harmonic ratios (both 1x-dominant); only
    the magnitude distinguishes them. Real analysts use ISO 10816 velocity bands
    for the same reason.
    """
    raw = [meas.amp_at(shaft_hz * k, tol_hz) for k in (1, 2, 3)]
    floor = meas.noise_floor_px

    # Gate each harmonic against the noise floor BEFORE taking ratios. On a quiet
    # machine 2x and 3x are genuinely ~0.02 px, far below the floor, so whatever
    # the spectrum shows there is noise. Feeding that into a ratio test invents a
    # fault: this was the single largest error source (healthy was 25% correct,
    # with 8/12 misread as misalignment or unbalance).
    gated = [a if a > HARMONIC_MIN_SNR * floor else 0.0 for a in raw]
    # Harmonics above Nyquist were never observable -- distinct from "measured ~0".
    unobservable = [k for k in (1, 2, 3) if shaft_hz * k > meas.nyquist_hz]
    a1, a2, a3 = gated
    tot = a1 + a2 + a3

    if a1 <= 0 and tot <= 0:
        return {"fault": "below_measurement_floor", "confidence": 0.0,
                "harmonics": {"1x": raw[0], "2x": raw[1], "3x": raw[2]},
                "noise_floor_px": round(floor, 4),
                "note": "all harmonics below the noise floor; machine is quiet but "
                        "no fault signature is resolvable at this SNR"}

    # 1x present, higher harmonics genuinely unresolvable -> that IS a quiet machine.
    if a1 > 0 and a2 <= 0 and a3 <= 0:
        return {"fault": "healthy", "confidence": 0.80,
                "harmonics": {"1x": round(a1, 4), "2x": 0.0, "3x": 0.0},
                "ratios": {"1x": 1.0, "2x": 0.0, "3x": 0.0},
                "total_px": round(tot, 4), "noise_floor_px": round(floor, 4),
                "note": "only 1x rises above the noise floor"}

    if unobservable:
        pass  # confidence is reduced below

    r1, r2, r3 = a1 / tot, a2 / tot, a3 / tot
    if tot < healthy_below and r1 > 0.6:
        return {"fault": "healthy", "confidence": round(float(min(1.0, (healthy_below - tot)
                                                                  / healthy_below + 0.55)), 3),
                "harmonics": {"1x": round(a1, 4), "2x": round(a2, 4), "3x": round(a3, 4)},
                "ratios": {"1x": round(r1, 3), "2x": round(r2, 3), "3x": round(r3, 3)},
                "total_px": round(tot, 4)}
    if r2 > 0.45 and a1 > 0:
        fault, conf = "misalignment", min(1.0, r2 / 0.45 * 0.8)
    elif r1 > 0.65:
        fault, conf = "unbalance", min(1.0, r1 / 0.65 * 0.8)
    elif r3 > 0.20 and r1 > 0.25:
        fault, conf = "mechanical_looseness", min(1.0, (r3 / 0.20) * 0.6)
    else:
        fault, conf = "indeterminate", 0.3
    if unobservable:
        # e.g. looseness needs 3x; if 3x sits above Nyquist we cannot rule it out.
        conf *= 0.6
    return {"fault": fault, "confidence": round(float(conf), 3),
            "harmonics": {"1x": round(a1, 4), "2x": round(a2, 4), "3x": round(a3, 4)},
            "ratios": {"1x": round(r1, 3), "2x": round(r2, 3), "3x": round(r3, 3)},
            "total_px": round(tot, 4), "noise_floor_px": round(floor, 4),
            "unobservable_harmonics": unobservable}


def compare_baseline(baseline: dict, meas: Measurement, shaft_hz: float):
    """Trend against this asset's own history -- absolute amplitude means little."""
    if not baseline:
        return {"has_baseline": False, "note": "first observation; stored as baseline"}
    out, tol = {}, max(3 * meas.bin_hz, 0.25)
    for mult in (1, 2, 3):
        key = f"{mult}x"
        prev = baseline.get(key, 0.0)
        cur = max((p.amp_px for p in meas.peaks
                   if abs(p.freq_hz - shaft_hz * mult) <= tol), default=0.0)
        out[key] = {"baseline_px": round(prev, 4), "current_px": round(cur, 4),
                    "change_pct": (round((cur - prev) / prev * 100, 1) if prev > 1e-6 else None)}
    worst = max((v["change_pct"] or 0) for v in out.values())
    return {"has_baseline": True, "harmonics": out, "max_increase_pct": worst,
            "trending_worse": worst > 50}
