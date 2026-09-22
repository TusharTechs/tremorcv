# TREMOR — video vibration measurement

**[Technical report](REPORT.md)** · **[Architecture](docs/architecture.mmd)** ·
**[Thresholds and their empirical basis](docs/THRESHOLDS.md)** ·
**[MCP surface](docs/MCP.md)** · **[Graviton runbook](deploy/README.md)**

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
webapp/     FastAPI endpoint + single-page UI (no build step, no CDN)
run_agent.py          single agent run with full decision trace
eval_agent.py         task effectiveness vs a single-shot ablation
test_mcp.py           exercise the MCP tool surface, no client needed
docs/THRESHOLDS.md    empirical basis for every threshold
docs/MCP.md           MCP server and the two-orchestrator design
```

## Web endpoint

```bash
.venv/bin/uvicorn webapp.server:app --port 8077     # then open http://localhost:8077
```

Two modes. **Simulated** streams the agent loop step by step over SSE, so each
decision appears as it is made and the visual evidence that drove it is on screen
next to it. **Upload clip** measures real footage: the vibrating region and a rigid
reference are located automatically, and the chosen regions are drawn on a preview
frame so the operator can see what was measured.

Auto-ROI is not naive motion energy. With a handheld camera everything moves, and
raw energy picked a laptop keyboard as the "machine" on a real test clip. Hand motion
is almost entirely below 1 Hz, so each pixel is high-passed in time first; what
remains is vibration rather than sway. On the real iPhone clip that took SNR from
4.1 (half-split frame) to 86.9, with the quality gate passing.

## Validated so far

- Real iPhone clip, fully handheld (20.5 px rms camera motion, 72 px p2p):
  **7.276 Hz measured vs 7.30 Hz ground truth — 0.33% error, SNR 196.**
- Simulated 3-component fault signature through real handheld motion + rolling
  shutter + specular glare + H.264: **0.000 Hz error on 1x, 2x and 3x.**
- Known limit: smooth/glossy surfaces fail (SNR 1.6 at 15% surface contrast).
- Known limit: 30 fps caps measurement at 15 Hz (900 RPM); 240 fps -> 120 Hz.

Agent task effectiveness (n=80): **71.2%** of scenarios diagnosed correctly,
**87.7%** correct on the ones it committed to, 18.8% escalated to a human rather
than guessed. Median shaft-frequency error 0.000 Hz.

### What the agentic loop is actually worth

A single agent-vs-baseline ratio is not a defensible claim: across three of our own
changes the single-shot baseline moved 21% -> 70% -> 27.5% while the agent stayed
flat at 86-88%. The ablation was largely measuring how hard the starting conditions
had been made -- a knob the author controls. So we sweep it instead (`sensitivity.py`,
n=24 per point, identical machines at every point, only the surface the operator
first aims at varies):

| initial surface | contrast | agent (all) | agent (when it answered) | single-shot | escalated | acquisitions |
|---|---|---|---|---|---|---|
| mirror housing | 0.010 | **79.2%** | 95.0% | **8.3%** | 16.7% | 2.21 |
| glossy paint | 0.040 | **79.2%** | 95.0% | 75.0% | 16.7% | 1.04 |
| worn paint | 0.150 | **79.2%** | 90.5% | 75.0% | 12.5% | 1.04 |
| printed label | 0.550 | **79.2%** | 86.4% | 70.8% | 8.3% | 1.12 |
| cast grille | 1.000 | **79.2%** | 86.4% | 70.8% | 8.3% | 1.12 |

**The agent's accuracy is flat at 79.2% regardless of how badly the operator aims.**
Single-shot collapses from 75% to 8.3% once the surface drops below the correlation
floor. The agent pays for that robustness only when it needs to -- 2.21 acquisitions
on an unusable surface, 1.04 on a workable one.

The honest reading: the loop buys **invariance to a bad first acquisition**, not raw
accuracy. Where the operator already aims well and holds steady it converges toward
single-shot and costs an extra fraction of an acquisition. Its value is bounded by
how often first acquisitions are inadequate, which is an operational question about
deployment, not a property of the algorithm.

## Setup

```bash
python3 -m venv .venv && ./.venv/bin/pip install opencv-python numpy matplotlib
./.venv/bin/python run_gate.py
```
