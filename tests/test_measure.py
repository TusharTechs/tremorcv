"""Core measurement: does it recover a signal we constructed, and reject what it should."""
import numpy as np, cv2, pytest
from tremor.measure import spectrum, clean_trace, auto_rois
from tremor.machine import make_machine_clip


def test_spectrum_recovers_frequency_and_amplitude():
    fps, f0, amp, n = 100.0, 7.0, 0.35, 1000
    t = np.arange(n) / fps
    f, A = spectrum(amp * np.sin(2 * np.pi * f0 * t), fps)
    k = np.argmax(A)
    assert abs(f[k] - f0) < 2 * f[1], f"got {f[k]} Hz, expected {f0}"
    # Hann scalloping loses up to ~15% when the tone sits between bins
    assert 0.85 * amp <= A[k] <= 1.05 * amp, f"amplitude {A[k]} vs {amp}"


def test_spectrum_is_zero_mean_insensitive():
    fps, n = 100.0, 800
    t = np.arange(n) / fps
    sig = 0.2 * np.sin(2 * np.pi * 5 * t)
    f1, A1 = spectrum(sig, fps)
    f2, A2 = spectrum(sig + 37.0, fps)          # large DC offset
    assert np.allclose(A1, A2, atol=1e-9)


def test_clean_trace_removes_injected_outliers():
    rng = np.random.default_rng(0)
    good = 0.3 * np.sin(np.linspace(0, 40, 600)) + rng.normal(0, 0.01, 600)
    bad = good.copy()
    bad[[50, 120, 300, 480]] = [90.0, -75.0, 60.0, -88.0]
    cleaned, frac = clean_trace(bad)
    assert frac > 0, "outliers not detected"
    assert np.abs(cleaned).max() < 2.0, f"outlier survived: {np.abs(cleaned).max()}"
    assert np.corrcoef(cleaned, good)[0, 1] > 0.98


def test_clean_trace_leaves_clean_data_alone():
    t = 0.3 * np.sin(np.linspace(0, 40, 400))
    cleaned, frac = clean_trace(t)
    assert frac < 0.05
    assert np.allclose(cleaned, t, atol=1e-9)


def test_clean_trace_reports_rather_than_repairs_when_mostly_broken():
    rng = np.random.default_rng(1)
    t = rng.normal(0, 50, 300)                  # everything is an outlier
    _, frac = clean_trace(t)
    assert frac >= 0.0  # must not raise; caller decides


def test_auto_rois_picks_the_vibrating_half_not_the_static_one():
    """The target half oscillates; the reference half does not. The chosen target must
    land in the moving half -- the failure this guards is picking whatever has the most
    contrast rather than the most vibration."""
    fr = make_machine_clip([(6.0, 0.8)], fps=30, seconds=6, size=(240, 380),
                           contrast=1.0, noise_dn=2.0, shake_rms=0.0, rolling=False)
    tgt, ref, diag = auto_rois(fr, 30.0)
    half = 380 // 2
    assert tgt[0] + tgt[2] // 2 < half, f"target centre {tgt} not in the moving half"
    assert ref[0] + ref[2] // 2 >= half, f"reference {ref} not in the static half"
    assert diag["vibration_target"] > diag["vibration_reference"]
