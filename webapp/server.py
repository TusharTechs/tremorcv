"""TREMOR web endpoint.

Two surfaces, matching the two orchestrators:

  POST /api/measure       one clip in, spectrum + peaks out (the OpenCV core)
  GET  /api/agent/stream  the perception-decision-action loop, streamed step by step

The agent stream is the point. A static "here is a diagnosis" page would show the
vision result; streaming each decision shows the visual evidence CHANGING what the
system does next, which is the thing the Agentic Vision rubric asks to see.
"""
from __future__ import annotations
import asyncio, json, os, sys, tempfile, time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import tools as T
from tremor.measure import auto_rois
from agent.env import (MachineEnv, Scenario, Acquisition, FAULT_SIGNATURES,
                       AIM_POINTS, TARGET_ROI, STATIC_ROI)
from agent.loop import (MAX_ACQUISITIONS, CONFIDENCE_TO_REPORT, FAST_FPS,
                        FAST_SECONDS, _better_aim, _estimate_shaft)

HERE = Path(__file__).resolve().parent
app = FastAPI(title="TREMOR", docs_url="/api/docs")
MAX_UPLOAD_MB = int(os.environ.get("TREMOR_MAX_UPLOAD_MB", "200"))
PROBE_FRAMES = int(os.environ.get("TREMOR_PROBE_FRAMES", "150"))


@app.get("/api/health")
def health():
    import bench.core as bc
    p = bc.provenance()
    return {"ok": True, "opencv": cv2.__version__,
            "cool_verified": p["cool_verified"], "arch": p["arch"],
            "instance": p["ec2_instance_type"] or "local"}


@app.get("/api/config")
def config():
    return {"faults": list(FAULT_SIGNATURES), "aim_points": AIM_POINTS,
            "max_acquisitions": MAX_ACQUISITIONS,
            "confidence_to_report": CONFIDENCE_TO_REPORT,
            "snr_trust": T.SNR_TRUST, "fast_fps": FAST_FPS}


def _downsample(xs, n=600):
    xs = np.asarray(xs, float)
    if len(xs) <= n:
        return [round(float(v), 6) for v in xs]
    idx = np.linspace(0, len(xs) - 1, n).astype(int)
    return [round(float(v), 6) for v in xs[idx]]


def _preview(frame, tgt, ref, width=760):
    """First frame with the chosen ROIs drawn, so the operator can see what the
    system decided to measure and what it is referencing against."""
    import base64
    img = cv2.cvtColor(np.clip(frame, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    for (x, y, w, h), colour, label in ((tgt, (196, 212, 77), "MEASURING"),
                                        (ref, (127, 153, 138), "REFERENCE")):
        cv2.rectangle(img, (x, y), (x + w, y + h), colour, 4)
        cv2.putText(img, label, (x + 8, y + 34), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, colour, 2, cv2.LINE_AA)
    sc = width / img.shape[1]
    img = cv2.resize(img, (0, 0), fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode() if ok else None


def _payload(meas: T.Measurement, surface: dict, quality: dict, fmax=None):
    f, A = meas._freqs, meas._amps
    if fmax is None:
        fmax = meas.nyquist_hz
    m = (f >= 0.0) & (f <= fmax)
    return {"measurement": meas.dict(), "surface": surface, "quality": quality,
            "spectrum": {"freqs": _downsample(f[m]), "amps": _downsample(A[m]),
                         "nyquist_hz": meas.nyquist_hz},
            "trace": _downsample(meas._trace if hasattr(meas, "_trace") else [])}


@app.post("/api/measure")
async def measure(file: UploadFile = File(...), fps: float = Form(0.0),
                  target: str = Form(""), static: str = Form("")):
    """Measure a real uploaded clip. ROIs are 'x,y,w,h'; omitted = split the frame."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"file exceeds {MAX_UPLOAD_MB} MB")
    suffix = Path(file.filename or "clip.mp4").suffix or ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(data); tmp.close()
    del data
    try:
        cap = cv2.VideoCapture(tmp.name)
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        use_fps = fps or src_fps
        if use_fps <= 0:
            cap.release(); raise HTTPException(400, "frame rate unknown; pass fps explicitly")
        if n < 32:
            cap.release(); raise HTTPException(400, f"only {n} frames; need at least 32")

        # Pass 1 -- a downsampled window is enough to LOCATE the regions. Decoding the
        # whole clip at full resolution as float32 costs frames x w x h x 4 bytes:
        # 5.03 GB for a 606-frame 1080p clip, which OOM-kills the service inside its
        # 1.7 GB cgroup and surfaces in the browser as "Failed to fetch".
        sc = min(1.0, 480.0 / max(w, 1))
        probe = []
        start = max(0, (n - PROBE_FRAMES) // 2)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        for _ in range(min(PROBE_FRAMES, n)):
            ok, fr = cap.read()
            if not ok:
                break
            probe.append(cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (0, 0),
                                    fx=sc, fy=sc).astype(np.float32))
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, first = cap.read()
        cap.release()
        if not probe or not ok:
            raise HTTPException(400, "could not decode frames from this file")

        auto_t, auto_r, roi_diag = auto_rois(np.asarray(probe), use_fps)
        del probe
        auto_t = tuple(int(v / sc) for v in auto_t)
        auto_r = tuple(int(v / sc) for v in auto_r)

        def parse(spec, default):
            if not spec:
                return default
            try:
                x, y, ww, hh = (int(v) for v in spec.split(","))
                return (x, y, ww, hh)
            except Exception:
                raise HTTPException(400, f"bad ROI '{spec}', expected x,y,w,h")

        tgt = parse(target, auto_t); ref = parse(static, auto_r)
        auto_used = not (target or static)

        first_g = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY).astype(np.float32)
        surface = T.assess_surface(first_g[None, ...], tgt)

        # Pass 2 -- stream, correlating each frame as it arrives and discarding it.
        meas = T.measure_streaming(tmp.name, use_fps, tgt, ref)
        quality = T.assess_quality(meas, surface)
        shaft = T.estimate_shaft(meas)

        out = _payload(meas, surface, quality)
        out.update({"source": {"filename": file.filename, "frames": len(meas._trace),
                               "fps": round(use_fps, 3), "width": w, "height": h,
                               "target_roi": list(tgt), "static_roi": list(ref),
                               "rois_auto": auto_used},
                    "roi_diagnostics": roi_diag,
                    "shaft_hz": shaft,
                    "preview": _preview(first_g, tgt, ref),
                    "diagnosis": T.diagnose(meas, shaft) if shaft else None})
        return JSONResponse(out)
    finally:
        os.unlink(tmp.name)


def _agent_steps(env: MachineEnv, baseline: dict | None = None):
    """The loop from agent/loop.py, yielding each step so the UI can render it live.

    Kept structurally identical to agent/loop.run() -- same thresholds, same ladder,
    same order. Divergence here would mean the demo shows something the evaluated
    agent does not do.
    """
    req = Acquisition(aim=env.s.default_aim, fps=30, seconds=10, braced=False)
    tried, t0 = set(), time.perf_counter()

    for n in range(1, MAX_ACQUISITIONS + 1):
        yield {"type": "acquiring", "n": n, "acquisition": asdict(req),
               "describe": req.describe()}
        frames = env.capture(req)
        tried.add(req.aim)

        surface = T.assess_surface(frames, TARGET_ROI)
        meas = T.measure(frames, req.fps, TARGET_ROI, STATIC_ROI)
        quality = T.assess_quality(meas, surface)
        best_aim = _better_aim(req.aim, tried)

        decision = why = None
        nxt = None
        dx = None

        if "low_texture" in quality["reasons"] and best_aim:
            decision, nxt = "re_acquire", Acquisition(best_aim, req.fps, req.seconds, req.braced)
            why = (f"surface texture {surface['texture_std']:.1f} < {surface['threshold']:.0f}; "
                   f"phase correlation has nothing to lock onto. Re-aiming at '{best_aim}'.")
        elif "possible_aliasing" in quality["reasons"] and req.fps < FAST_FPS:
            decision, nxt = "re_acquire", Acquisition(req.aim, FAST_FPS, FAST_SECONDS, req.braced)
            why = (f"peak {meas.peaks[0].freq_hz:.1f} Hz sits near Nyquist "
                   f"({meas.nyquist_hz:.1f} Hz); cannot rule out aliasing. Requesting {FAST_FPS} fps.")
        elif "low_snr" in quality["reasons"] and not req.braced:
            decision, nxt = "re_acquire", Acquisition(req.aim, req.fps, req.seconds, True)
            why = (f"SNR {quality['top_snr']:.1f} < {T.SNR_TRUST}; camera motion "
                   f"{meas.cam_rms_px:.1f} px vs signal {meas.signal_rms_px:.2f} px. "
                   f"Asking the operator to brace.")
        elif "low_snr" in quality["reasons"] and best_aim:
            decision, nxt = "re_acquire", Acquisition(best_aim, req.fps, req.seconds, True)
            why = (f"SNR {quality['top_snr']:.1f} still low after bracing; trying a more "
                   f"textured aim point '{best_aim}'.")
        elif "low_snr" in quality["reasons"]:
            decision = "escalate"
            why = (f"SNR {quality['top_snr']:.1f} below threshold after bracing and re-aiming. "
                   f"Not trustworthy; handing to a human.")
        else:
            shaft = _estimate_shaft(meas)
            if shaft is None:
                decision, why = "escalate", "no peak above the SNR threshold."
            elif 2 * shaft > meas.nyquist_hz and req.fps < FAST_FPS:
                decision, nxt = "re_acquire", Acquisition(req.aim, FAST_FPS, FAST_SECONDS, req.braced)
                why = (f"shaft {shaft:.2f} Hz, so 2x = {2*shaft:.2f} Hz exceeds Nyquist "
                       f"({meas.nyquist_hz:.1f} Hz). No diagnosis is possible at {req.fps} fps.")
            else:
                dx = T.diagnose(meas, shaft)
                trend = T.compare_baseline(baseline or {}, meas, shaft)
                if dx["fault"] == "healthy" and trend.get("trending_worse"):
                    dx = {**dx, "fault": "healthy_but_degrading",
                          "confidence": max(dx["confidence"], 0.60)}
                missing = dx.get("unobservable_harmonics") or []
                if dx["confidence"] >= CONFIDENCE_TO_REPORT:
                    decision = "report"
                    why = (f"shaft {shaft:.2f} Hz; harmonics 1x/2x/3x = "
                           f"{dx['ratios']['1x']:.2f}/{dx['ratios']['2x']:.2f}/"
                           f"{dx['ratios']['3x']:.2f} -> {dx['fault']} "
                           f"(confidence {dx['confidence']:.2f}).")
                elif missing and req.fps < FAST_FPS:
                    need = ", ".join(f"{k}x = {k*shaft:.1f} Hz" for k in missing)
                    decision, nxt = "re_acquire", Acquisition(req.aim, FAST_FPS, FAST_SECONDS, req.braced)
                    why = (f"'{dx['fault']}' at confidence {dx['confidence']:.2f}, limited by "
                           f"{need} above Nyquist ({meas.nyquist_hz:.1f} Hz). Re-acquiring at "
                           f"{FAST_FPS} fps to resolve the missing harmonic rather than declining.")
                else:
                    decision = "escalate"
                    why = (f"'{dx['fault']}' confidence {dx['confidence']:.2f} < "
                           f"{CONFIDENCE_TO_REPORT}; not asserting a fault.")

        step = _payload(meas, surface, quality, fmax=min(meas.nyquist_hz, 40))
        step.update({"type": "step", "n": n, "acquisition": asdict(req),
                     "shaft_hz": T.estimate_shaft(meas),
                     "describe": req.describe(), "decision": decision, "why": why,
                     "diagnosis": dx,
                     "next_acquisition": asdict(nxt) if nxt else None})
        yield step

        if decision in ("report", "escalate"):
            yield {"type": "done", "decision": decision, "diagnosis": dx,
                   "acquisitions": env.n_acquisitions,
                   "elapsed_s": round(time.perf_counter() - t0, 2),
                   "truth": env.truth()}
            return
        req = nxt

    yield {"type": "done", "decision": "escalate", "diagnosis": None,
           "acquisitions": env.n_acquisitions,
           "elapsed_s": round(time.perf_counter() - t0, 2),
           "reason": f"acquisition budget ({MAX_ACQUISITIONS}) exhausted",
           "truth": env.truth()}


@app.get("/api/agent/stream")
async def agent_stream(shaft_hz: float = 4.3, fault: str = "misalignment",
                       severity_px: float = 0.6, start_aim: str = "housing"):
    if fault not in FAULT_SIGNATURES:
        raise HTTPException(400, f"unknown fault; choose from {list(FAULT_SIGNATURES)}")
    if start_aim not in AIM_POINTS:
        raise HTTPException(400, f"unknown aim point; choose from {list(AIM_POINTS)}")
    env = MachineEnv(Scenario(shaft_hz=shaft_hz, fault=fault,
                              severity_px=severity_px, default_aim=start_aim))

    async def gen():
        loop = asyncio.get_running_loop()
        it = _agent_steps(env)
        while True:
            # the OpenCV work is blocking and CPU-bound; keep the event loop free
            ev = await loop.run_in_executor(None, lambda: next(it, None))
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


app.mount("/", StaticFiles(directory=HERE / "static", html=True), name="static")
