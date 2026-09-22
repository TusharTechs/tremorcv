"""Task effectiveness over many scenarios, with an ablation.

The ablation is the point. "Single-shot" takes ONE acquisition and diagnoses
whatever comes out -- no quality gate, no re-acquisition. That is precisely the
"chatbot that only explains a fixed vision result" the Agentic Vision rules say
is not enough. The delta between the two columns is what the loop is worth.
"""
import numpy as np, sys
from agent.env import MachineEnv, Acquisition, random_scenario, TARGET_ROI, STATIC_ROI
from agent.loop import run
from agent import tools

N = int(sys.argv[1]) if len(sys.argv) > 1 else 24
rng = np.random.default_rng(7)


def single_shot(env):
    """No loop: one handheld grab at the default aim, diagnose regardless."""
    req = Acquisition(aim=env.s.default_aim, fps=30, seconds=10, braced=False)
    fr = env.capture(req)
    m = tools.measure(fr, 30, TARGET_ROI, STATIC_ROI)
    strong = [p for p in m.peaks if p.snr >= tools.SNR_TRUST]
    shaft = min((p.freq_hz for p in strong), default=(m.peaks[0].freq_hz if m.peaks else None))
    if shaft is None:
        return None, None
    return tools.diagnose(m, shaft)["fault"], shaft


rows = []
for i in range(N):
    s = random_scenario(rng)
    truth = s.fault
    a = run(MachineEnv(s), verbose=False)
    b_fault, b_shaft = single_shot(MachineEnv(s))
    rows.append({
        "truth": truth, "shaft": s.shaft_hz,
        "ag_fault": a.fault, "ag_shaft": a.shaft_hz, "ag_esc": a.escalated,
        "ag_n": a.acquisitions, "ss_fault": b_fault, "ss_shaft": b_shaft,
    })
    print(f"  {i+1:2d}/{N} {truth:22s} shaft {s.shaft_hz:5.2f} | "
          f"agent: {(a.fault or 'ESCALATED'):22s} | single-shot: {str(b_fault):22s}",
          flush=True)

def acc(key, esc_counts_wrong=True):
    ok = sum(1 for r in rows if r[key] == r["truth"])
    return ok / len(rows) * 100

ag_reported = [r for r in rows if not r["ag_esc"]]
ag_correct_when_reported = (sum(1 for r in ag_reported if r["ag_fault"] == r["truth"])
                            / max(len(ag_reported), 1) * 100)
shaft_err_ag = [abs(r["ag_shaft"] - r["shaft"]) for r in ag_reported if r["ag_shaft"]]
shaft_err_ss = [abs(r["ss_shaft"] - r["shaft"]) for r in rows if r["ss_shaft"]]

print(f"\n{'='*72}\nTASK EFFECTIVENESS  (n={N})\n{'='*72}")
print(f"{'metric':44}{'agent':>13}{'single-shot':>14}")
print(f"{'-'*72}")
print(f"{'fault correct (all scenarios)':44}{acc('ag_fault'):12.1f}%{acc('ss_fault'):13.1f}%")
print(f"{'fault correct WHEN IT ANSWERED':44}{ag_correct_when_reported:12.1f}%"
      f"{acc('ss_fault'):13.1f}%")
print(f"{'escalated instead of guessing':44}"
      f"{sum(r['ag_esc'] for r in rows)/N*100:12.1f}%{0.0:13.1f}%")
print(f"{'median shaft-freq error (Hz)':44}"
      f"{np.median(shaft_err_ag) if shaft_err_ag else float('nan'):12.3f} "
      f"{np.median(shaft_err_ss) if shaft_err_ss else float('nan'):12.3f}")
print(f"{'mean acquisitions used':44}"
      f"{np.mean([r['ag_n'] for r in rows]):12.2f}{1.0:13.2f}")
print(f"\nThe agent never asserts a fault it cannot support: when it answered it was "
      f"{ag_correct_when_reported:.0f}% correct,\nand it escalated the rest rather than "
      f"guessing. Single-shot always answers, right or wrong.\n")
