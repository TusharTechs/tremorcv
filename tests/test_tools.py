"""Agent tool surface: the decisions that were wrong before, pinned so they stay right."""
import numpy as np, pytest
from agent import tools as T
from tremor.machine import make_machine_clip
from agent.env import TARGET_ROI, STATIC_ROI, SIZE, FAULT_SIGNATURES


def clip(components, **kw):
    kw.setdefault("contrast", 1.0); kw.setdefault("noise_dn", 2.0)
    kw.setdefault("shake_rms", 0.0); kw.setdefault("rolling", False)
    return make_machine_clip(components, fps=30, seconds=10, size=SIZE, **kw)


def measure(components, **kw):
    return T.measure(clip(components, **kw), 30, TARGET_ROI, STATIC_ROI)


@pytest.mark.parametrize("fault", list(FAULT_SIGNATURES))
def test_shaft_estimate_is_the_fundamental_not_a_harmonic(fault):
    """The bug this pins: 'lowest strong peak' returned 2x the true rate for
    misalignment, inverting the diagnosis. The harmonic comb must return f0."""
    f0, sev = 4.3, 0.8
    r1, r2, r3 = FAULT_SIGNATURES[fault]
    m = measure([(f0, sev * r1), (2 * f0, sev * r2), (3 * f0, sev * r3)])
    est = T.estimate_shaft(m)
    assert est is not None
    assert abs(est - f0) < 0.2, f"{fault}: estimated {est} Hz, true {f0} Hz"


def test_diagnose_separates_healthy_from_unbalance_by_amplitude():
    """They share a harmonic signature (both 1x-dominant); only magnitude differs."""
    f0 = 4.3
    quiet = measure([(f0, 0.20), (2 * f0, 0.02), (3 * f0, 0.01)])
    loud = measure([(f0, 0.80), (2 * f0, 0.12), (3 * f0, 0.04)])
    assert T.diagnose(quiet, f0)["fault"] == "healthy"
    assert T.diagnose(loud, f0)["fault"] == "unbalance"


def test_diagnose_calls_misalignment_when_2x_dominates():
    f0 = 4.3
    m = measure([(f0, 0.40), (2 * f0, 0.80), (3 * f0, 0.20)])
    d = T.diagnose(m, f0)
    assert d["fault"] == "misalignment", d
    assert d["ratios"]["2x"] > d["ratios"]["1x"]


def test_diagnose_refuses_below_the_noise_floor():
    """Ratios of noise invent faults. Below the floor it must decline, not guess."""
    m = measure([(4.3, 0.002)])
    d = T.diagnose(m, 4.3)
    assert d["fault"] in ("below_measurement_floor", "healthy"), d
    assert d["confidence"] <= 0.8


def test_diagnose_marks_harmonics_above_nyquist_unobservable():
    f0 = 6.5                      # 3x = 19.5 Hz, above the 15 Hz Nyquist at 30 fps
    m = measure([(f0, 0.6), (2 * f0, 0.4)])
    d = T.diagnose(m, f0)
    assert 3 in d.get("unobservable_harmonics", []), d


def test_assess_quality_flags_a_featureless_surface():
    """Measured boundary: contrast 0.004 (texture std ~2.0, at the sensor-noise floor)
    fails; 0.01 with a still camera still succeeds. The texture metric saturates, so
    the gate has to catch this via SNR and correlation stability too."""
    fr = clip([(4.3, 0.6)], contrast=0.004)
    m = T.measure(fr, 30, TARGET_ROI, STATIC_ROI)
    q = T.assess_quality(m, T.assess_surface(fr, TARGET_ROI))
    assert not q["trustworthy"]
    assert {"low_texture", "low_snr", "unstable_correlation"} & set(q["reasons"]), q


def test_marginal_texture_passes_when_the_camera_is_steady_and_fails_handheld():
    """The same surface is usable or not depending on camera motion. A gate keyed only
    on texture would get this wrong in both directions."""
    still = clip([(4.3, 0.6)], contrast=0.01, shake_rms=0.0)
    hand = clip([(4.3, 0.6)], contrast=0.01, shake_rms=4.06, rolling=True)
    qs = T.assess_quality(T.measure(still, 30, TARGET_ROI, STATIC_ROI),
                          T.assess_surface(still, TARGET_ROI))
    qh = T.assess_quality(T.measure(hand, 30, TARGET_ROI, STATIC_ROI),
                          T.assess_surface(hand, TARGET_ROI))
    assert qs["trustworthy"], qs
    assert not qh["trustworthy"], qh


def test_assess_quality_passes_a_clean_strong_signal():
    fr = clip([(4.3, 0.8)])
    m = T.measure(fr, 30, TARGET_ROI, STATIC_ROI)
    q = T.assess_quality(m, T.assess_surface(fr, TARGET_ROI))
    assert q["trustworthy"], q


def test_measurement_dict_is_json_safe():
    """The MCP surface serialises this; numpy arrays must not leak into it."""
    import json
    m = measure([(4.3, 0.6)])
    d = m.dict()
    json.dumps(d)
    assert not any(k.startswith("_") for k in d)


def test_streaming_and_in_memory_measurement_agree():
    """measure_streaming exists because the in-memory path OOM-kills the service.
    They must not drift apart."""
    import cv2, tempfile, os
    fr = clip([(5.0, 0.7)])
    p = os.path.join(tempfile.gettempdir(), "tremor_stream_test.mp4")
    vw = cv2.VideoWriter(p, cv2.VideoWriter_fourcc(*"avc1"), 30, (SIZE[1], SIZE[0]), False)
    for f in fr:
        vw.write(f.astype(np.uint8))
    vw.release()
    try:
        a = T.measure(fr, 30, TARGET_ROI, STATIC_ROI)
        b = T.measure_streaming(p, 30, TARGET_ROI, STATIC_ROI)
        assert abs(a.peaks[0].freq_hz - b.peaks[0].freq_hz) < 0.3
    finally:
        os.path.exists(p) and os.unlink(p)
