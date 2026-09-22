# Where the agent's numbers come from

Every threshold in `agent/tools.py` is a measurement, not a guess. This file records
what was run and what it showed, so each one can be re-derived or challenged.

| Constant | Value | Basis |
|---|---|---|
| `SNR_TRUST` | 6.0 | `run_gate.py` §B: frequency recovery was exact down to 0.03 px amplitude at SNR 7.0 and failed at SNR 3.1 (0.01 px). 6.0 sits at the knee. |
| `TEXTURE_MIN_STD` | 15.0 | `run_machine_eval.py`: at surface contrast 0.15 (texture std ≈ 7) SNR collapsed to 1.6 and all three harmonics shifted +0.25 Hz. At contrast 1.0 (std ≈ 44) SNR was 21.8 through every degradation. |
| `ALIAS_FRACTION` | 0.40 | Peaks above 0.4·fps are close enough to Nyquist that a folded harmonic cannot be excluded. Backstop only — the primary aliasing check is in `agent/loop.py` and derives from the estimated shaft rate. |
| `STABILIZE_WHEN` | 0.5 | Stabilisation is not free: subtracting a near-zero reference adds √2× noise. Measured in `run_gate.py` §C/§D — above ~0.5 px signal the unstabilised SNR was *higher* (36.8 vs 20.9); between 0.2 and 0.5 px stabilisation was essential. |
| `REJECT_FRAC_MAX` | 0.15 | See below. |
| `HEALTHY_TOTAL_PX` | 0.42 | A healthy machine and an unbalanced one have near-identical harmonic ratios (0.87/0.09/0.04 vs 0.83/0.12/0.04) — only amplitude separates them. Real analysts use ISO 10816 velocity bands for the same reason. |
| `CONFIDENCE_TO_REPORT` | 0.55 | Chosen so the agent escalates rather than asserting a fault it cannot support. At n=30 it answered 79% correctly and escalated 20% instead of guessing. |

## Camera shake is resolution-dependent

The real iPhone clip measured **20.5 px rms** camera motion on a **1920-wide** frame.
The scale-free quantity is the *fraction of frame width* (1.07%), because a hand
rotating by a fixed angle displaces more pixels on a higher-resolution sensor.
`agent/env.py` uses the fraction. Hard-coding 20.5 px into the smaller simulation
frames modelled roughly 5× more hand motion than was actually observed, and made
every scenario unsolvable.

## phaseCorrelate fails catastrophically on a minority of frames

Measured on a clean synthetic clip (pure 11.3 Hz at 0.8 px, good texture, no shake):
**11% of frames returned displacements up to ±92 px** on a ±0.8 px true signal, in
time-clustered bursts. Residual RMS grew with clip length — 0.39 px at 2 s, 6.3 px at
4 s, 59.7 px at 10 s (240 fps) — which is backwards for white noise and confirms
outliers rather than drift.

`tremor.measure.clean_trace` rejects them with two independent detectors:

- **MAD** — real vibration is bounded and smooth, so a sample many robust deviations
  from the median is not physical.
- **`response`** — `cv2.phaseCorrelate` returns a correlation-peak strength as its
  third value. It is easy to discard, but failures correlate with low values
  (median 0.063 on bad frames vs 0.095 on good ones).

Effect at 240 fps / 4 s: SNR **8.4 → 39.2**.

**Known limitation, not yet root-caused:** 240 fps clips of ~10 s still degrade
(40% of frames rejected). The detector catches it and the agent refuses the
measurement rather than reporting a wrong answer, but the underlying cause is
uncharacterised. Acquisitions at 240 fps are therefore capped at 4 s.

## Reproducing

```bash
python run_gate.py            # thresholds in rows A-D
python run_machine_eval.py    # texture and degradation-stack thresholds
python eval_agent.py 30       # end-to-end task effectiveness + ablation
```
