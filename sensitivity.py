"""How much is the agentic loop actually worth, as a function of acquisition quality?

A single agent-vs-single-shot number is not a defensible claim: across three of my
own changes the single-shot baseline moved 21% -> 70% -> 27.5% while the agent stayed
flat at 86-88%. The ablation was mostly measuring how hard the starting conditions
were made, which is a knob the author controls.

So sweep the knob instead and report the curve. The honest question is not "is the
loop better" but "under what conditions does it earn its keep".

Axis: texture contrast of the surface the operator initially aims at, from a
mirror-finish housing (0.010, below the measured correlation floor) to a cast grille
(1.00). Everything else is held fixed.
"""
import sys, numpy as np
from agent import env as E
from agent.env import MachineEnv, Acquisition, random_scenario, TARGET_ROI, STATIC_ROI
from agent.loop import run
from agent import tools

N = int(sys.argv[1]) if len(sys.argv) > 1 else 24
CONTRASTS = [0.010, 0.04, 0.15, 0.55, 1.00]
LABELS = {0.010: "mirror housing", 0.04: "glossy paint", 0.15: "worn paint",
          0.55: "printed label", 1.00: "cast grille"}


def single_shot(env):
    req = Acquisition(aim=env.s.default_aim, fps=30, seconds=10, braced=False)
    m = tools.measure(env.capture(req), 30, TARGET_ROI, STATIC_ROI)
    shaft = tools.estimate_shaft(m)
    if shaft is None:
        return None
    return tools.diagnose(m, shaft)["fault"]


print(f"\n{'='*86}")
print(f"SENSITIVITY: agent vs single-shot vs initial aim quality   (n={N} per point)")
print(f"{'='*86}")
print(f"{'initial surface':>18}{'contrast':>10}{'agent all':>12}{'agent|ans':>11}"
      f"{'single-shot':>13}{'escalated':>11}{'acqs':>7}")
print("-"*86)

rows = []
for c in CONTRASTS:
    E.AIM_POINTS["start"] = c
    rng = np.random.default_rng(7)          # same machines at every sweep point
    ok_a = ok_s = esc = 0
    acqs = []
    for _ in range(N):
        s = random_scenario(rng)
        s.default_aim = "start"
        a = run(MachineEnv(s), verbose=False)
        b = single_shot(MachineEnv(s))
        if a.escalated:
            esc += 1
        elif a.fault == s.fault:
            ok_a += 1
        if b == s.fault:
            ok_s += 1
        acqs.append(a.acquisitions)
    answered = N - esc
    rows.append((c, ok_a/N*100, (ok_a/answered*100 if answered else float('nan')),
                 ok_s/N*100, esc/N*100, float(np.mean(acqs))))
    print(f"{LABELS[c]:>18}{c:10.3f}{rows[-1][1]:11.1f}%{rows[-1][2]:10.1f}%"
          f"{rows[-1][3]:12.1f}%{rows[-1][4]:10.1f}%{rows[-1][5]:7.2f}", flush=True)
    E.AIM_POINTS.pop("start", None)

print("-"*86)
gaps = [r[1]-r[3] for r in rows]
print(f"\nAgent advantage (all scenarios): {gaps[0]:+.1f} pts at the worst surface -> "
      f"{gaps[-1]:+.1f} pts at the best.")
print(f"Agent accuracy when it answers stays in "
      f"{min(r[2] for r in rows):.0f}-{max(r[2] for r in rows):.0f}% across the whole "
      f"range; single-shot spans {min(r[3] for r in rows):.0f}-{max(r[3] for r in rows):.0f}%.")
print("\nRead: the loop buys robustness to a bad first acquisition, not raw accuracy.")
print("Where the operator already aims well and holds steady, it converges on")
print("single-shot and costs an extra acquisition. Its value is bounded by how often")
print("the first clip is inadequate -- which is an operational question, not a")
print("property of the algorithm.\n")
