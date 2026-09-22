# TREMOR — video vibration measurement

Measures machine vibration from ordinary video. Sub-pixel displacement via
OpenCV 5 phase correlation, temporal spectrum, fault frequencies.

```
tremor/     measurement core (measure.py) + validation generators (synth.py, machine.py)
bench/      COOL/Graviton benchmark harness (core, suite, cost, pricing)
deploy/     Graviton + COOL deployment and baseline scripts
run_gate.py           day 1-3 physics gate on synthetic video
run_machine_eval.py   realistic fault-signature evaluation
analyze_video.py      measure a real video file
run_bench.py          benchmark one environment -> results/<label>.json
compare.py            merge results -> report tables
agent/      perception-decision-action loop + MCP server
run_agent.py          single agent run with full decision trace
eval_agent.py         task effectiveness vs a single-shot ablation
test_mcp.py           exercise the MCP tool surface, no client needed
docs/THRESHOLDS.md    empirical basis for every threshold
docs/MCP.md           MCP server and the two-orchestrator design
```

## Validated so far

- Real iPhone clip, fully handheld (20.5 px rms camera motion, 72 px p2p):
  **7.276 Hz measured vs 7.30 Hz ground truth — 0.33% error, SNR 196.**
- Simulated 3-component fault signature through real handheld motion + rolling
  shutter + specular glare + H.264: **0.000 Hz error on 1x, 2x and 3x.**
- Known limit: smooth/glossy surfaces fail (SNR 1.6 at 15% surface contrast).
- Known limit: 30 fps caps measurement at 15 Hz (900 RPM); 240 fps -> 120 Hz.

Agent task effectiveness (n=80), against a single-shot ablation that takes one
acquisition and diagnoses whatever comes out:

| | agent | single-shot |
|---|---|---|
| fault correct (all scenarios) | **63.7%** | 21.2% |
| fault correct **when it answered** | **86.4%** | 21.2% |
| escalated instead of guessing | 26.2% | 0.0% |
| median shaft-frequency error | **0.000 Hz** | 3.200 Hz |
| 95% CI (all scenarios) | 53-73% | 14-31% |

Per class, correct when answered: looseness 16/16, misalignment 17/18,
healthy 10/13, unbalance 8/12.

## Setup

```bash
python3 -m venv .venv && ./.venv/bin/pip install opencv-python numpy matplotlib
./.venv/bin/python run_gate.py
```
