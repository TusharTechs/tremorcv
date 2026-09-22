"""Simulated acquisition environment.

This is what makes the loop genuinely agentic rather than narrated: when the agent
requests a different acquisition, the environment RESPONDS -- bracing lowers shake,
re-aiming raises texture, raising fps lifts the Nyquist ceiling. The next
measurement really is different because of what the agent decided.

Ground truth is known, so task success is measurable over many scenarios.
"""
from dataclasses import dataclass, field
import numpy as np
from tremor.machine import make_machine_clip

SIZE = (240, 380)
TARGET_ROI = (15, 20, 160, 200)
STATIC_ROI = (205, 20, 160, 200)

# relative harmonic amplitudes at 1x / 2x / 3x
FAULT_SIGNATURES = {
    "healthy":             (1.00, 0.10, 0.05),
    "unbalance":           (1.00, 0.15, 0.05),
    "misalignment":        (0.50, 1.00, 0.25),
    "mechanical_looseness":(1.00, 0.60, 0.50),
}

# where the operator can aim, and how much surface texture is there
# A mirror-finish or glossy painted housing under even light genuinely has almost no
# trackable texture; grilles, cast flanges and printed labels have plenty. These are
# the contrasts an operator chooses between by aiming elsewhere on the same machine.
#
# `housing` at 0.010 is the contrast measured to genuinely fail (SNR 2.6, wrong
# frequency); 0.015 still succeeds at SNR 20.5. It is set from that measurement,
# not tuned to make the agent re-aim. After the phaseCorrelate fix the texture
# floor dropped ~7x, so most real surfaces now work on the first attempt and the
# re-aim branch fires only when it genuinely must. random_scenario starts half the
# runs on `label` (workable) and half on `housing` (not), so both paths are tested.
AIM_POINTS = {"housing": 0.010, "label": 0.55, "grille": 1.00, "bolt_flange": 0.85}

# Camera shake is RESOLUTION-DEPENDENT: a hand rotating by a fixed angle displaces
# more pixels on a higher-resolution sensor. The real iPhone clip measured 20.5 px
# rms on a 1920-wide frame, so the scale-free quantity is the FRACTION of frame
# width. Hard-coding 20.5 px into these smaller sim frames would model ~5x more
# hand motion than was actually observed.
HANDHELD_SHAKE_FRAC = 20.5 / 1920.0     # = 1.07% of frame width (measured)
BRACED_SHAKE_FRAC = HANDHELD_SHAKE_FRAC / 10.0


@dataclass
class Scenario:
    shaft_hz: float
    fault: str
    severity_px: float = 0.5          # amplitude of the 1x-equivalent component
    default_aim: str = "housing"      # deliberately the worst surface
    seed: int = 0


@dataclass
class Acquisition:
    """What the agent asks the operator (or a PTZ/robot) to do."""
    aim: str = "housing"
    fps: int = 30
    seconds: float = 10.0
    braced: bool = False

    def describe(self):
        return (f"aim={self.aim}, {self.fps} fps, {self.seconds:.0f}s, "
                f"{'braced' if self.braced else 'handheld'}")


class MachineEnv:
    def __init__(self, scen: Scenario):
        self.s = scen
        self.n_acquisitions = 0

    def capture(self, req: Acquisition):
        s = self.s
        r1, r2, r3 = FAULT_SIGNATURES[s.fault]
        comps = [(s.shaft_hz * m, s.severity_px * r)
                 for m, r in ((1, r1), (2, r2), (3, r3))]
        # Components above Nyquist alias -- the environment does NOT hide this.
        comps = [(f, a) for f, a in comps]
        contrast = AIM_POINTS.get(req.aim, 0.12)
        frac = BRACED_SHAKE_FRAC if req.braced else HANDHELD_SHAKE_FRAC
        shake = frac * SIZE[1]
        self.n_acquisitions += 1
        frames = make_machine_clip(
            comps, fps=req.fps, seconds=req.seconds, size=SIZE,
            contrast=contrast, noise_dn=2.0, shake_rms=shake,
            rolling=True, compress=False, seed=s.seed + self.n_acquisitions)
        return frames

    def truth(self):
        return {"shaft_hz": self.s.shaft_hz, "fault": self.s.fault,
                "severity_px": self.s.severity_px}


# Amplitude, not harmonic shape, is what separates a healthy machine from unbalance:
# both are 1x-dominant. Real analysts use absolute velocity against ISO 10816 bands;
# here the equivalent is total harmonic displacement in pixels.
HEALTHY_SEVERITY = (0.15, 0.28)
FAULT_SEVERITY = (0.55, 0.95)


def random_scenario(rng):
    """Mix of easy and hard cases, including some that need >30 fps."""
    fault = rng.choice(list(FAULT_SIGNATURES))
    lo, hi = HEALTHY_SEVERITY if fault == "healthy" else FAULT_SEVERITY
    # shaft rates chosen so 2x/3x sometimes exceed 30fps Nyquist (15 Hz)
    shaft = float(rng.choice([2.1, 3.1, 4.3, 5.7, 7.9, 11.3]))
    return Scenario(shaft_hz=shaft, fault=fault,
                    severity_px=float(rng.uniform(lo, hi)),
                    default_aim=rng.choice(["housing", "label"]),
                    seed=int(rng.integers(0, 10_000)))
