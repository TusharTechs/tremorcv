"""Demo: one machine, agent drives the whole diagnosis."""
import json, sys
from agent.env import MachineEnv, Scenario
from agent.loop import run

s = Scenario(shaft_hz=4.3, fault="misalignment", severity_px=0.6, default_aim="housing")
print(f"\nHIDDEN TRUTH: shaft {s.shaft_hz} Hz, fault = {s.fault}\n"
      f"Agent starts aimed at '{s.default_aim}' (smooth housing), handheld, 30 fps.\n")
env = MachineEnv(s)
out = run(env)
print(f"\nRESULT: resolved={out.resolved} escalated={out.escalated} "
      f"fault={out.fault} conf={out.confidence} shaft={out.shaft_hz} "
      f"acquisitions={out.acquisitions} ({out.wall_s:.1f}s)")
json.dump(out.json(), open("out/agent_trace.json", "w"), indent=2)
print("trace -> out/agent_trace.json")
