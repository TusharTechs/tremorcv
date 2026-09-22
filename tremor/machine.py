"""Realistic machine-vibration video: multi-component faults, real handheld shake,
rolling shutter, specular glare, controllable surface texture, H.264 round-trip."""
import numpy as np, cv2, os, tempfile

REAL_SHAKE = "out/real_shake.npy"


def surface(h, w, contrast=1.0, seed=0):
    """contrast 1.0 = detailed casting; 0.15 = smooth painted/glossy metal."""
    rng = np.random.default_rng(seed)
    t = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 0.8)
    t /= max(t.std(), 1e-9)
    return np.clip(128 + t * 45 * contrast, 0, 255)


def _shake(n, rms, seed):
    if rms <= 0:
        return np.zeros(n)
    s = np.load(REAL_SHAKE) if os.path.exists(REAL_SHAKE) else None
    if s is None:
        rng = np.random.default_rng(seed)
        s = cv2.GaussianBlur(np.cumsum(rng.normal(0, 1, n)).astype(np.float32),
                             (0, 0), 6).ravel()
    s = np.interp(np.linspace(0, len(s) - 1, n), np.arange(len(s)), s)
    s = s - s.mean()
    return s * (rms / max(s.std(), 1e-9))


def make_machine_clip(components, fps=30, seconds=20, size=(480, 760),
                      contrast=1.0, noise_dn=2.0, shake_rms=0.0,
                      rolling=False, glare=False, compress=False, seed=0):
    """
    components: [(freq_hz, amplitude_px), ...]  e.g. 1x unbalance + 2x misalignment.
    Left half = vibrating machine, right half = rigid background (static reference).
    """
    h, w = size
    hw = w // 2
    mach = surface(h, hw, contrast, seed)
    bg = surface(h, w - hw, 1.0, seed + 50)
    rng = np.random.default_rng(seed + 3)
    n = int(fps * seconds)
    sh = _shake(n, shake_rms, seed)
    t_ro = 0.8 / fps if rolling else 0.0
    rows = (np.arange(h) / h)[:, None]
    xs = np.arange(hw, dtype=np.float32)[None, :]
    ymap = np.repeat(np.arange(h, dtype=np.float32)[:, None], hw, 1)
    frames = np.empty((n, h, w), np.float32)

    for i in range(n):
        t = i / fps
        tt = t + rows * t_ro                      # per-row sample time (rolling shutter)
        d = sum(a * np.sin(2 * np.pi * f * tt) for f, a in components)
        d = np.broadcast_to(d, (h, 1))
        xm = (xs - (d + sh[i])).astype(np.float32)
        f_ = np.empty((h, w), np.float32)
        f_[:, :hw] = cv2.remap(mach, xm, ymap, cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REFLECT)
        bx = (np.arange(w - hw, dtype=np.float32)[None, :] - sh[i]).astype(np.float32)
        f_[:, hw:] = cv2.remap(bg, np.repeat(bx, h, 0),
                               np.repeat(np.arange(h, dtype=np.float32)[:, None], w - hw, 1),
                               cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        if glare:   # specular highlight fixed to the CAMERA, not the machine
            gy, gx = np.ogrid[:h, :w]
            f_ += 110 * np.exp(-(((gx - (hw * .55 + sh[i])) ** 2) / (2 * 70. ** 2)
                                 + ((gy - h * .4) ** 2) / (2 * 70. ** 2)))
        if noise_dn:
            f_ += rng.normal(0, noise_dn, (h, w)).astype(np.float32)
        frames[i] = np.clip(f_, 0, 255)

    if compress:                                   # H.264 round-trip like a phone
        p = os.path.join(tempfile.gettempdir(), f"tc_{seed}_{n}.mp4")
        vw = cv2.VideoWriter(p, cv2.VideoWriter_fourcc(*"avc1"), fps, (w, h), False)
        for f_ in frames:
            vw.write(f_.astype(np.uint8))
        vw.release()
        cap = cv2.VideoCapture(p); out = []
        while True:
            ok, fr = cap.read()
            if not ok: break
            out.append(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32))
        cap.release(); os.remove(p)
        if len(out) >= n * 0.9:
            frames = np.array(out[:n])
    return frames
