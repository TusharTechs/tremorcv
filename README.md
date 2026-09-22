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
```

## Validated so far

- Real iPhone clip, fully handheld (20.5 px rms camera motion, 72 px p2p):
  **7.276 Hz measured vs 7.30 Hz ground truth — 0.33% error, SNR 196.**
- Simulated 3-component fault signature through real handheld motion + rolling
  shutter + specular glare + H.264: **0.000 Hz error on 1x, 2x and 3x.**
- Known limit: smooth/glossy surfaces fail (SNR 1.6 at 15% surface contrast).
- Known limit: 30 fps caps measurement at 15 Hz (900 RPM); 240 fps -> 120 Hz.

## Setup

```bash
python3 -m venv .venv && ./.venv/bin/pip install opencv-python numpy matplotlib
./.venv/bin/python run_gate.py
```
