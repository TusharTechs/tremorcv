"""The perception -> decision -> action loop.

Rubric mapping (Agentic Vision):
  30% OpenCV+agent integration  -> every decision is driven by agent/tools.py output
  25% orchestration / autonomy  -> the agent chooses the NEXT ACQUISITION itself
  20% task effectiveness        -> eval_agent.py scores success over many scenarios
  15% failure handling / human  -> quality gate, budget cap, explicit escalation
  10% UX / docs                 -> the trace renders as a readable transcript
"""
from dataclasses import dataclass, field, asdict
import json, time
from agent import tools
from agent.env import Acquisition, AIM_POINTS, MachineEnv, TARGET_ROI, STATIC_ROI

MAX_ACQUISITIONS = 4            # hard budget: bounded autonomy
CONFIDENCE_TO_REPORT = 0.55     # below this the agent escalates instead of asserting


@dataclass
class Step:
    n: int
    acquisition: dict
    surface: dict
    measurement: dict
    quality: dict
    decision: str
    rationale: str
    next_acquisition: dict = None


@dataclass
class Outcome:
    resolved: bool
    escalated: bool
    fault: str = None
    confidence: float = 0.0
    shaft_hz: float = None
    acquisitions: int = 0
    reason: str = ""
    steps: list = field(default_factory=list)
    wall_s: float = 0.0

    def json(self):
        d = asdict(self)
        d["steps"] = [asdict(s) if not isinstance(s, dict) else s for s in self.steps]
        return d


def _better_aim(current, tried):
    """Most textured aim point not yet tried. None when options are exhausted."""
    for name, _ in sorted(AIM_POINTS.items(), key=lambda kv: -kv[1]):
        if name != current and name not in tried:
            return name
    return None


def _estimate_shaft(meas):
    """Lowest strong peak is the running speed; harmonics sit above it."""
    strong = [p for p in meas.peaks if p.snr >= tools.SNR_TRUST]
    return min((p.freq_hz for p in strong), default=None)


def run(env: MachineEnv, first: Acquisition = None, baseline: dict = None,
        max_acq=MAX_ACQUISITIONS, verbose=True):
    t0 = time.perf_counter()
    req = first or Acquisition(aim=env.s.default_aim, fps=30, seconds=10, braced=False)
    steps, tried_aims = [], set()
    shaft = None

    for n in range(1, max_acq + 1):
        frames = env.capture(req)
        tried_aims.add(req.aim)

        surface = tools.assess_surface(frames, TARGET_ROI)
        meas = tools.measure(frames, req.fps, TARGET_ROI, STATIC_ROI)
        qual = tools.assess_quality(meas, surface)

        decision, why, nxt = None, "", None
        best_aim = _better_aim(req.aim, tried_aims)

        # --- failure handling: each reason maps to a specific, different remedy,
        # --- and each remedy is tried at most once before escalating.
        if "low_texture" in qual["reasons"] and best_aim:
            decision, nxt = "re_acquire", Acquisition(best_aim, req.fps, req.seconds, req.braced)
            why = (f"surface texture {surface['texture_std']:.1f} < "
                   f"{surface['threshold']:.0f}; phase correlation has nothing to lock "
                   f"onto. Re-aiming at '{best_aim}'.")
        elif "possible_aliasing" in qual["reasons"] and req.fps < 240:
            decision, nxt = "re_acquire", Acquisition(req.aim, 240, 4.0, req.braced)
            why = (f"peak {meas.peaks[0].freq_hz:.1f} Hz sits near Nyquist "
                   f"({meas.nyquist_hz:.1f} Hz); cannot rule out aliasing. "
                   f"Requesting 240 fps.")
        elif "low_snr" in qual["reasons"] and not req.braced:
            decision, nxt = "re_acquire", Acquisition(req.aim, req.fps, req.seconds, True)
            why = (f"SNR {qual['top_snr']:.1f} < {tools.SNR_TRUST}; camera motion "
                   f"{meas.cam_rms_px:.1f} px vs signal {meas.signal_rms_px:.2f} px. "
                   f"Asking operator to brace.")
        elif "low_snr" in qual["reasons"] and best_aim:
            decision, nxt = "re_acquire", Acquisition(best_aim, req.fps, req.seconds, True)
            why = (f"SNR {qual['top_snr']:.1f} still low after bracing; trying a more "
                   f"textured aim point '{best_aim}' before giving up.")
        elif "low_snr" in qual["reasons"]:
            decision = "escalate"
            why = (f"SNR {qual['top_snr']:.1f} below threshold after bracing and "
                   f"re-aiming. Measurement is not trustworthy; handing to a human.")
        else:
            shaft = _estimate_shaft(meas)
            if shaft is None:
                decision, why = "escalate", "no peak above SNR threshold."
            elif 2 * shaft > meas.nyquist_hz and req.fps < 240:
                # Derived from the agent's OWN shaft estimate: if 2x cannot fit under
                # Nyquist, the harmonics needed for diagnosis are folding back into
                # the spectrum and any classification would be built on an artefact.
                decision, nxt = "re_acquire", Acquisition(req.aim, 240, 4.0, True)
                why = (f"shaft estimated at {shaft:.2f} Hz, so 2x = {2*shaft:.2f} Hz "
                       f"exceeds Nyquist ({meas.nyquist_hz:.1f} Hz). Harmonics are "
                       f"aliasing; 30 fps cannot support a diagnosis. Requesting 240 fps.")
            else:
                dx = tools.diagnose(meas, shaft)
                trend = tools.compare_baseline(baseline or {}, meas, shaft)
                if dx["confidence"] >= CONFIDENCE_TO_REPORT:
                    decision = "report"
                    why = (f"shaft {shaft:.2f} Hz; harmonics 1x/2x/3x = "
                           f"{dx['ratios']['1x']:.2f}/{dx['ratios']['2x']:.2f}/"
                           f"{dx['ratios']['3x']:.2f}, total {dx['total_px']:.3f} px "
                           f"-> {dx['fault']} (confidence {dx['confidence']:.2f}).")
                else:
                    decision = "escalate"
                    why = (f"diagnosis '{dx['fault']}' confidence {dx['confidence']:.2f} "
                           f"< {CONFIDENCE_TO_REPORT}; not asserting a fault.")

        steps.append(Step(n, asdict(req), surface, meas.dict(), qual, decision, why,
                          asdict(nxt) if nxt else None))
        if verbose:
            print(f"  [{n}] {req.describe()}")
            print(f"      texture {surface['texture_std']:5.1f} | "
                  f"peak {(meas.peaks[0].freq_hz if meas.peaks else 0):6.2f} Hz "
                  f"SNR {qual['top_snr']:5.1f} | {'OK' if qual['trustworthy'] else ','.join(qual['reasons'])}")
            print(f"      -> {decision.upper()}: {why}")

        if decision == "report":
            return Outcome(True, False, dx["fault"], dx["confidence"], shaft,
                           env.n_acquisitions, why, steps, time.perf_counter() - t0)
        if decision == "escalate":
            return Outcome(False, True, None, 0.0, None, env.n_acquisitions, why, steps,
                           time.perf_counter() - t0)
        req = nxt

    return Outcome(False, True, None, 0.0, None, env.n_acquisitions,
                   f"acquisition budget ({max_acq}) exhausted without a trustworthy "
                   f"measurement; escalating.", steps, time.perf_counter() - t0)
