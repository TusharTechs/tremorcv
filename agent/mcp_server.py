"""TREMOR as an MCP server.

The competition rules name MCP explicitly: "The agent may use any framework or
model and may invoke OpenCV 5 and, where applicable, COOL through APIs, tools, or
Model Context Protocol (MCP)."

Exposing the OpenCV tool surface over MCP means any MCP-capable client can be the
orchestrator -- no vendor lock-in, no LLM API key required to run the deterministic
reference policy, and the same tools serve both paths.

Clips live in a session store keyed by clip_id so large frame arrays never cross
the protocol boundary; the model passes handles, not pixels.

Run:  python -m agent.mcp_server
"""
from typing import Literal
import json, numpy as np
from mcp.server.mcpserver import MCPServer

from agent import tools as T
from agent.env import (MachineEnv, Scenario, Acquisition, AIM_POINTS,
                       TARGET_ROI, STATIC_ROI, FAULT_SIGNATURES)

mcp = MCPServer(
    name="tremor",
    instructions=(
        "TREMOR measures machine vibration from video using OpenCV 5 phase "
        "correlation. Typical loop: capture_clip -> assess_surface -> measure -> "
        "assess_quality. If quality is not trustworthy, act on the returned "
        "reasons (re-aim for low_texture, brace for low_snr, raise fps for "
        "aliasing) and capture again. Only call diagnose once quality is "
        "trustworthy. Escalate rather than asserting a low-confidence fault."
    ),
)

_CLIPS: dict[str, dict] = {}
_ENVS: dict[str, MachineEnv] = {}
_BASELINES: dict[str, dict] = {}


@mcp.tool()
def start_session(session_id: str, shaft_hz: float = 4.3,
                  fault: str = "misalignment", severity_px: float = 0.6,
                  start_aim: str = "housing") -> str:
    """Open a simulated machine for evaluation. The fault is hidden from the caller.

    In production this is replaced by a real camera; the tool surface is identical.
    """
    if fault not in FAULT_SIGNATURES:
        return json.dumps({"error": f"unknown fault; choose from {list(FAULT_SIGNATURES)}"})
    _ENVS[session_id] = MachineEnv(Scenario(shaft_hz=shaft_hz, fault=fault,
                                            severity_px=severity_px,
                                            default_aim=start_aim))
    return json.dumps({"session_id": session_id, "aim_points": list(AIM_POINTS),
                       "start_aim": start_aim,
                       "note": "ground truth hidden; call capture_clip to begin"})


@mcp.tool()
def capture_clip(session_id: str, aim: str = "housing",
                 fps: Literal[30, 60, 240] = 30, seconds: float = 10.0,
                 braced: bool = False) -> str:
    """Request a new acquisition. THIS IS THE AGENT'S ACTION.

    Changing aim/fps/braced genuinely changes what the camera records, so a later
    measurement differs because of what was decided here. 240 fps lifts the
    Nyquist ceiling to 120 Hz but is capped at 4 s (see docs/THRESHOLDS.md).
    """
    env = _ENVS.get(session_id)
    if env is None:
        return json.dumps({"error": "no such session; call start_session first"})
    if fps >= 240:
        seconds = min(seconds, 4.0)
    frames = env.capture(Acquisition(aim=aim, fps=fps, seconds=seconds, braced=braced))
    clip_id = f"{session_id}:{env.n_acquisitions}"
    _CLIPS[clip_id] = {"frames": frames, "fps": fps}
    return json.dumps({"clip_id": clip_id, "frames": len(frames), "fps": fps,
                       "seconds": round(len(frames) / fps, 2),
                       "nyquist_hz": fps / 2.0,
                       "freq_resolution_hz": round(fps / len(frames), 3),
                       "acquisitions_used": env.n_acquisitions})


@mcp.tool()
def assess_surface(clip_id: str) -> str:
    """Check whether the surface has enough texture to phase-correlate. Call first --
    it is cheap, and a failure here makes every later number meaningless."""
    c = _CLIPS.get(clip_id)
    if c is None:
        return json.dumps({"error": "no such clip"})
    return json.dumps(T.assess_surface(c["frames"], TARGET_ROI))


@mcp.tool()
def measure(clip_id: str) -> str:
    """Core OpenCV 5 workload: sub-pixel displacement -> spectrum -> ranked peaks.

    Uses cv2.phaseCorrelate against a static reference ROI to cancel camera motion,
    with outlier rejection on the correlation response.
    """
    c = _CLIPS.get(clip_id)
    if c is None:
        return json.dumps({"error": "no such clip"})
    m = T.measure(c["frames"], c["fps"], TARGET_ROI, STATIC_ROI)
    _CLIPS[clip_id]["measurement"] = m
    return json.dumps(m.dict())


@mcp.tool()
def assess_quality(clip_id: str) -> str:
    """Can this measurement be trusted? Returns machine-readable `reasons`:
    low_texture -> re-aim; low_snr -> brace; possible_aliasing -> raise fps;
    unstable_correlation -> discard the clip."""
    c = _CLIPS.get(clip_id)
    if c is None or "measurement" not in c:
        return json.dumps({"error": "call measure first"})
    return json.dumps(T.assess_quality(c["measurement"],
                                       T.assess_surface(c["frames"], TARGET_ROI)))


@mcp.tool()
def diagnose(clip_id: str, shaft_hz: float) -> str:
    """Classify the fault from 1x/2x/3x harmonics. Only meaningful once quality is
    trustworthy AND 2x fits under Nyquist. Amplitude is checked before shape:
    healthy and unbalance share a harmonic signature and differ only in magnitude."""
    c = _CLIPS.get(clip_id)
    if c is None or "measurement" not in c:
        return json.dumps({"error": "call measure first"})
    m = c["measurement"]
    if 2 * shaft_hz > m.nyquist_hz:
        return json.dumps({"error": "2x exceeds Nyquist; harmonics are aliasing. "
                                    "Re-capture at a higher fps before diagnosing.",
                           "shaft_hz": shaft_hz, "nyquist_hz": m.nyquist_hz})
    return json.dumps(T.diagnose(m, shaft_hz))


@mcp.tool()
def compare_baseline(session_id: str, clip_id: str, shaft_hz: float,
                     store_as_baseline: bool = False) -> str:
    """Trend against this asset's own history. Absolute amplitude means little;
    a 50%+ rise at a harmonic is what matters."""
    c = _CLIPS.get(clip_id)
    if c is None or "measurement" not in c:
        return json.dumps({"error": "call measure first"})
    m = c["measurement"]
    out = T.compare_baseline(_BASELINES.get(session_id, {}), m, shaft_hz)
    if store_as_baseline:
        tol = max(3 * m.bin_hz, 0.25)
        _BASELINES[session_id] = {
            f"{k}x": max((p.amp_px for p in m.peaks
                          if abs(p.freq_hz - shaft_hz * k) <= tol), default=0.0)
            for k in (1, 2, 3)}
        out["stored"] = True
    return json.dumps(out)


@mcp.tool()
def reveal_ground_truth(session_id: str) -> str:
    """Evaluation only -- reveals the hidden fault so a run can be scored.
    Never call this before committing to a diagnosis."""
    env = _ENVS.get(session_id)
    return json.dumps(env.truth() if env else {"error": "no such session"})


if __name__ == "__main__":
    mcp.run(transport="stdio")
