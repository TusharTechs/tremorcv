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
| `HARMONIC_MIN_SNR` | 3.0 | A harmonic below 3× the spectral noise floor is noise, not a measurement. See "Gating harmonics" below. |
| `FUNDAMENTAL_MIN_SHARE` | 0.15 | A real fundamental carries non-trivial energy at 1×. Stops the harmonic-comb estimator selecting f_true/2. |
| `CONFIDENCE_TO_REPORT` | 0.55 | Chosen so the agent escalates rather than asserting a fault it cannot support. |

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

## Shaft estimation: harmonic comb, not "lowest strong peak"

The obvious heuristic — take the lowest peak above the SNR threshold as the running
speed — is wrong, and was a major error source. For **misalignment** the 2×
component dominates and 1× can fall below the SNR floor, so the heuristic returns
*twice* the true shaft rate, reads 2× as 1×, and inverts the diagnosis to unbalance.
Measured directly at a true 4.30 Hz:

| Fault | true | harmonic comb | lowest strong peak |
|---|---|---|---|
| healthy | 4.30 | **4.30** | 0.50 |
| unbalance | 4.30 | **4.30** | 0.50 |
| misalignment | 4.30 | **4.30** | 0.50 |
| mechanical_looseness | 4.30 | **4.30** | 4.30 |

`estimate_shaft` instead scores each candidate fundamental by how much energy lands
on its harmonic comb (weights 1.0 / 0.9 / 0.6 at 1×/2×/3×). The
`FUNDAMENTAL_MIN_SHARE` guard is what stops `f_true / 2` winning: that candidate
explains the true 1× as its own 2×, but has nothing at its own fundamental.

## Gating harmonics against the noise floor

An n=80 confusion matrix localised the remaining error almost entirely to one class:

| Truth | correct when answered |
|---|---|
| mechanical_looseness | 16/16 |
| misalignment | 19/20 |
| unbalance | 9/12 |
| **healthy** | **3/12** |

`healthy` produced 9 of 13 total errors, split between "misalignment" and
"unbalance". The cause: on a quiet machine the 2× and 3× components are genuinely
around 0.02 px — far below the measurement noise floor — so whatever the spectrum
shows at those frequencies is noise. Feeding it into a ratio test **invents a fault**.

After gating (same 80 scenarios, same seed):

| Truth | before | after |
|---|---|---|
| healthy | 3/12 | **10/13** |
| mechanical_looseness | 16/16 | 16/16 |
| misalignment | 19/20 | 17/18 |
| unbalance | 9/12 | 8/12 |
| **overall, when answered** | **78.3%** | **86.4%** |

The single-shot ablation *fell* from 41.2% to 21.2% over the same change, which is
the expected direction: it operates on unusable clips, and the old lenient classifier
let it guess "unbalance" often enough to score by luck. Gating makes it admit it
cannot tell.

`diagnose` gates each harmonic at `HARMONIC_MIN_SNR × noise_floor` *before*
taking ratios, and distinguishes three cases that were previously conflated:

- **all harmonics below the floor** → `below_measurement_floor`, confidence 0. The
  machine is quiet but no signature is resolvable; the agent escalates rather than
  reporting "healthy" it cannot support.
- **only 1× above the floor** → `healthy`. This is the correct physical reading, not
  a fallback.
- **a harmonic above Nyquist** → recorded as *unobservable*, distinct from
  "measured ≈ 0", and confidence is multiplied by 0.6. Looseness needs 3×; if 3×
  sits above Nyquist it cannot be ruled out, and the agent should not pretend it can.

## Trend outranks absolute amplitude

`compare_baseline` is wired into the decision, not just reported. A machine whose
absolute level reads healthy but which is >50% above its own baseline is returned as
`healthy_but_degrading`. Analysts trend each asset against itself rather than a
global threshold, because a permanently noisy machine is less interesting than a
quiet one that just got worse.

## A note on the ablation

`eval_agent.py` reports a single-shot baseline, and that number is unstable by
construction. Across the phaseCorrelate fix, the texture recalibration and the
Nyquist routing it read 21.2%, then 70.0%, then 27.5% -- while the agent held at
86-88% correct-when-answered throughout. Most of that swing came from one choice:
the contrast of the surface the operator initially aims at.

Do not quote the ratio. `sensitivity.py` sweeps that variable and reports the curve,
which shows the agent flat at 79.2% across the full range while single-shot spans
8.3-75%. The defensible claim is invariance to a bad first acquisition, not a
multiple.

## Nyquist routing

Mechanical looseness is only separable from unbalance via its 3x harmonic. At 30 fps
that harmonic sits above Nyquist for any shaft above 5 Hz, so the agent was declining
half that class. It now re-acquires at 240 fps -- but only when confidence is low
*specifically because* a needed harmonic is unobservable, so misalignment and
unbalance (which need only 1x and 2x) still resolve in one 30 fps clip.

| n=80 | before routing | after |
|---|---|---|
| looseness correct / escalated | 13 / 13 | **19 / 7** |
| all scenarios | 62.5% | **71.2%** |
| correct when answered | 86.2% | **87.7%** |
| escalated | 27.5% | **18.8%** |
| mean acquisitions | 1.79 | 1.86 |

## Two failures from the first Graviton run

Recorded because both produced confident, wrong output rather than an error.

**The baseline measured COOL, not stock.** COOL's `activate` exports
`PYTHONPATH=/opt/cool/python_3.12/site-packages/cv2/python-3.12`, and Python's
`deactivate` restores `PATH` and `VIRTUAL_ENV` but **does not unset `PYTHONPATH`**.
It therefore leaked into the baseline venv and took precedence over its own
`site-packages`. Both legs loaded `cv2 4.14.0-pre` from `/opt/cool` and came out
0.4% apart — a number that looks like a result and means nothing.

The isolation assert *did* fire; the driver script ignored it, because the
hand-written cloud-init re-implemented `run_all.sh` without `set -e`. Fixes:
`setup_stock.sh` unsets `PYTHONPATH` and `LD_LIBRARY_PATH`; `run_all.sh` now gates
the baseline leg as well as the COOL leg; and `make-userdata.sh` generates
cloud-init that *calls* `run_all.sh` so there is one implementation of the sequence
rather than two.

**`cool_verified` was true for the stock run.** The check tested
`isdir("/opt/cool")`, which is true on that machine no matter which library the
interpreter imported. It now requires `"/opt/cool" in os.path.realpath(cv2.__file__)`
— the loaded library, not the installed one. Provenance also records `PYTHONPATH`
and `opencv_major`, so a leak or a version mismatch is visible in every result file
instead of buried in a log.

**Resolved: pick the COOL AMI by measured version, not by name.** The AMI whose
name matches the subscription title ships OpenCV 4, which would fail the competition's
OpenCV 5 requirement. Probed every venv on each image:

| AMI | Name | OpenCV | KleidiCV |
|---|---|---|---|
| `ami-01db31139bc5615d8` | COOL-Graviton4-v2 | 4.14.0-pre (all venvs) | yes |
| `ami-033e481a24f94c8cb` | Graviton5-COOL-v3 | **5.1.0-dev** (all venvs) | yes |

Both share product code `aajkmdd4qo3r7yhqg61a7aah9`, so a single subscription covers
both, and the "Graviton5" image boots and runs on Graviton4 (`c8g`) hardware. It needs
a 60 GB root volume rather than 50. The graviton2/graviton3 COOL listings are separate
products (`OptInRequired` without their own subscription).

Note the version is `5.1.0-dev`, a development build rather than a tagged 5.0.0
release. It is OpenCV 5 and satisfies the requirement, but the report states the exact
string rather than rounding it.

Probing cost about $0.02 and ten minutes — considerably less than waiting on an
answer.

**Deadlock: `fork` plus OpenCV's thread pool.** `process_scaling` used the default
`ProcessPoolExecutor`. On Linux that means `fork`, which copies only the calling
thread — OpenCV holds locks in its internal thread pool, and a child inheriting one
held, with no thread alive to release it, deadlocks. Observed on Graviton as **0% CPU
for 15 minutes** while the run appeared alive. macOS defaults to `spawn`, so this
passed locally every time and hung only in the cloud.

Fixed by forcing a `spawn` context, calling `cv2.setNumThreads(1)` before the pool,
and adding a per-batch timeout so any residual hang is reported as a failure rather
than idling. The cloud-init wrapper now also `tee`s to `/dev/console` (a plain
redirect hid all progress from `get-console-output`, and with no SSH there was no
other way to see where it stopped) and carries a watchdog that uploads and terminates
after 30 minutes.

**Four deployment failures, all Linux-only.** Each was correct on the development
machine and fatal on the target, which is the pattern worth recording:

| failure | cause | how it presented |
|---|---|---|
| benchmark hung at 0% CPU | `ProcessPoolExecutor` defaults to `fork` on Linux; OpenCV's thread pool holds locks a forked child inherits held | apparently alive, 15 min of flat 0% CPU |
| baseline aborted | cloud-init runs user-data as root with no `HOME`, fatal under `set -u` | run died before the second leg |
| endpoint crash-looped | `opencv-python` links `libGL`, absent on servers | `active` then restarting, looked like slow startup |
| uploads failed | every frame decoded to float32: 5.03 GB against a 1.70 GB cgroup | "Failed to fetch" in the browser |

macOS defaults to `spawn`, provides `HOME`, ships `libGL`, and had the RAM to absorb
5 GB. `tests/test_deploy_scripts.sh` now runs the deploy scripts under `env -i` with
`set -u` and asserts the headless wheel, the pre-flight import check and the streaming
endpoint, so this class is caught locally rather than on a billing instance.

## Reproducing

```bash
python run_gate.py            # thresholds in rows A-D
python run_machine_eval.py    # texture and degradation-stack thresholds
python eval_agent.py 80       # end-to-end task effectiveness
python sensitivity.py 24      # agent vs single-shot across acquisition quality
python -m pytest tests/       # phaseCorrelate mutation regression
```
