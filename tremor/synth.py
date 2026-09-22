"""Generate video with EXACTLY known sub-pixel motion, for validating the measurement."""
import numpy as np, cv2


def texture(h, w, seed=0):
    """Blurred noise: ideal texture for phase correlation (broadband, no dominant edge)."""
    rng = np.random.default_rng(seed)
    t = rng.normal(0.5, 0.25, (h, w)).astype(np.float32)
    t = cv2.GaussianBlur(t, (0, 0), 0.8)   # sharp: phase corr needs high-freq content
    t -= t.min(); t /= max(t.max(), 1e-9)
    return (t * 200 + 25).astype(np.float32)


def make_clip(freq_hz, amp_px, fps=30, seconds=10, size=(480, 640),
              noise_dn=2.0, shake_px=0.0, seed=0):
    """
    Frame = [ moving target (left half) | static reference (right half) ].

    The target oscillates horizontally at exactly `freq_hz` with amplitude
    `amp_px` pixels. The reference never moves. `shake_px` adds whole-frame
    camera motion on top of both, simulating handheld.
    """
    h, w = size
    tgt = texture(h, w // 2, seed)
    ref = texture(h, w - w // 2, seed + 99)
    rng = np.random.default_rng(seed + 7)
    n = int(fps * seconds)
    frames = np.empty((n, h, w), np.float32)
    truth = np.empty(n, np.float64)

    # camera shake: low-frequency random walk, like a braced hand
    shake = np.cumsum(rng.normal(0, 1, n)) if shake_px else np.zeros(n)
    if shake_px:
        shake = cv2.GaussianBlur(shake.astype(np.float32), (0, 0), 6).ravel()
        shake *= shake_px / max(np.std(shake), 1e-9)

    for i in range(n):
        t = i / fps
        dx = amp_px * np.sin(2 * np.pi * freq_hz * t)
        truth[i] = dx
        a = np.float32([[1, 0, dx + shake[i]], [0, 1, 0]])
        b = np.float32([[1, 0, shake[i]], [0, 1, 0]])
        f = np.empty((h, w), np.float32)
        f[:, :w // 2] = cv2.warpAffine(tgt, a, (w // 2, h),
                                       flags=cv2.INTER_CUBIC,
                                       borderMode=cv2.BORDER_REFLECT)
        f[:, w // 2:] = cv2.warpAffine(ref, b, (w - w // 2, h),
                                       flags=cv2.INTER_CUBIC,
                                       borderMode=cv2.BORDER_REFLECT)
        if noise_dn:
            f += rng.normal(0, noise_dn, (h, w)).astype(np.float32)
        frames[i] = f

    return np.clip(frames, 0, 255), truth


def write_mp4(frames, path, fps):
    """Round-trip through H.264 to measure what phone compression costs you."""
    h, w = frames.shape[1:]
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h), False)
    for f in frames:
        vw.write(f.astype(np.uint8))
    vw.release()
