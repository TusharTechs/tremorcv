"""The agentic loop: a vision result must change the next acquisition, not just prose."""
import pytest
from agent.env import MachineEnv, Scenario, Acquisition, AIM_POINTS
from agent.loop import run, MAX_ACQUISITIONS, CONFIDENCE_TO_REPORT


def scen(**kw):
    kw.setdefault("shaft_hz", 4.3); kw.setdefault("fault", "misalignment")
    kw.setdefault("severity_px", 0.7); kw.setdefault("default_aim", "grille")
    return Scenario(**kw)


def test_diagnoses_a_clear_fault_from_a_good_first_clip():
    o = run(MachineEnv(scen()), verbose=False)
    assert o.resolved and o.fault == "misalignment", o.reason
    assert o.acquisitions == 1, "a usable first clip should not need a second"
    assert abs(o.shaft_hz - 4.3) < 0.2


def test_reacquires_rather_than_guessing_on_an_unusable_surface():
    """The whole point of the loop: a bad first acquisition changes what it asks for."""
    o = run(MachineEnv(scen(default_aim="housing")), verbose=False)
    acts = [s.decision for s in o.steps]
    assert "re_acquire" in acts, acts
    assert o.acquisitions > 1
    # and the follow-up request must actually differ from what failed
    first = o.steps[0]
    assert first.next_acquisition is not None
    assert (first.next_acquisition["aim"] != first.acquisition["aim"]
            or first.next_acquisition["braced"] != first.acquisition["braced"]
            or first.next_acquisition["fps"] != first.acquisition["fps"]), first


def test_raises_frame_rate_when_a_needed_harmonic_is_above_nyquist():
    """Looseness is separable only via 3x. At 30 fps that is above Nyquist for any
    shaft above 5 Hz, so the agent must go and get a faster clip."""
    o = run(MachineEnv(scen(shaft_hz=5.7, fault="mechanical_looseness")), verbose=False)
    fps_asked = [s.next_acquisition["fps"] for s in o.steps if s.next_acquisition]
    assert any(f >= 240 for f in fps_asked), [s.why for s in o.steps]


def test_escalates_instead_of_asserting_a_low_confidence_fault():
    o = run(MachineEnv(scen(fault="healthy", severity_px=0.02, default_aim="housing")),
            verbose=False)
    assert o.escalated, o.reason
    assert o.fault is None, "must not name a fault it cannot support"


def test_every_decision_carries_a_rationale():
    o = run(MachineEnv(scen(default_aim="housing")), verbose=False)
    for s in o.steps:
        assert s.decision and s.rationale, s
        assert len(s.rationale) > 20, f"rationale too thin: {s.rationale}"


def test_acquisition_budget_is_bounded():
    o = run(MachineEnv(scen(fault="healthy", severity_px=0.01, default_aim="housing")),
            max_acq=2, verbose=False)
    assert o.acquisitions <= 2
    assert o.resolved or o.escalated, "must terminate one way or the other"


def test_reported_confidence_clears_the_threshold():
    o = run(MachineEnv(scen()), verbose=False)
    if o.resolved:
        assert o.confidence >= CONFIDENCE_TO_REPORT


def test_trend_promotes_a_quiet_machine_that_got_worse():
    """Absolute amplitude alone would call this healthy; trending against its own
    baseline is what makes it interesting.

    Braced on purpose. Classifying a quiet machine from a handheld clip is fragile --
    with some shake realisations the residual lands near 2x and reads as misalignment
    (see the healthy row of the confusion matrix in the report). That fragility is a
    separate, documented issue; this test is about the trend promotion."""
    s = scen(fault="healthy", severity_px=0.22)
    steady = Acquisition(aim="grille", fps=30, seconds=10, braced=True)
    plain = run(MachineEnv(s), first=steady, verbose=False)
    trended = run(MachineEnv(s), first=steady,
                  baseline={"1x": 0.05, "2x": 0.01, "3x": 0.005}, verbose=False)
    assert plain.fault == "healthy", plain.fault
    assert trended.fault == "healthy_but_degrading", trended.fault
