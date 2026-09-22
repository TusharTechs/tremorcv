"""Regression test for the cv2.phaseCorrelate in-place mutation bug.

phaseCorrelate multiplies both source arrays by the window in place. Any code that
reuses a reference array across calls silently decays it as base * window**N. This
produced up to 46% catastrophically wrong frames on long clips before it was found.
"""
import numpy as np, cv2, pytest
from tremor.measure import roi_trace

H, W = 200, 160


def _texture(seed=0):
    rng = np.random.default_rng(seed)
    t = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.8)
    return np.clip(128 + t / t.std() * 45, 0, 255).astype(np.float32)


def test_phasecorrelate_still_mutates_its_inputs():
    """Documents the upstream behaviour. If this ever fails, OpenCV fixed it and
    the defensive copy in roi_trace can be reconsidered."""
    a, b = _texture(0), _texture(1)
    win = cv2.createHanningWindow((W, H), cv2.CV_32F)
    a0, b0 = a.copy(), b.copy()
    cv2.phaseCorrelate(a, b, win)
    assert not np.array_equal(a, a0), "src1 no longer mutated - revisit roi_trace"
    assert not np.array_equal(b, b0), "src2 no longer mutated - revisit roi_trace"


def test_repeated_calls_are_deterministic_with_copies():
    a, b = _texture(0), _texture(1)
    win = cv2.createHanningWindow((W, H), cv2.CV_32F)
    vals = [cv2.phaseCorrelate(a.copy(), b.copy(), win)[0][0] for _ in range(200)]
    assert len(set(np.round(vals, 9))) == 1


def test_roi_trace_recovers_known_shift_on_a_long_clip():
    """The actual regression: a long clip must not degrade. Pre-fix this produced
    ~46% outliers beyond frame ~700."""
    base = _texture(0)
    n, amp, period = 1500, 0.8, 25.0
    frames = np.empty((n, H, W), np.float32)
    truth = np.empty(n)
    for i in range(n):
        dx = amp * np.sin(2 * np.pi * i / period)
        truth[i] = dx
        M = np.float32([[1, 0, dx], [0, 1, 0]])
        frames[i] = cv2.warpAffine(base, M, (W, H), flags=cv2.INTER_CUBIC,
                                   borderMode=cv2.BORDER_REFLECT)
    meas = roi_trace(frames, (10, 10, W - 20, H - 20))[:, 0]
    resid = meas - (truth - truth[0])

    assert np.abs(meas).max() < 3 * amp, (
        f"catastrophic outliers returned (max |dx| = {np.abs(meas).max():.1f} px "
        f"on a {amp} px signal) - phaseCorrelate input mutation has regressed")
    assert np.std(resid) < 0.15, f"residual rms {np.std(resid):.3f} px too high"
    # second half must be no worse than the first: that is what decay looked like
    h = n // 2
    assert np.std(resid[h:]) < 3 * np.std(resid[:h]) + 0.05, (
        "accuracy degrades over the clip - reference array is decaying again")
