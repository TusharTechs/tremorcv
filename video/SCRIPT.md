# TREMOR demo video

**`TREMOR_demo_final.mp4`** is the one to submit: **3:09**, 1920x1080, 30 fps,
narration and a background bed, normalised to -16.7 LUFS. Everything in it was
recorded against the live endpoint at http://50.19.247.214.

Three stages, each leaving a usable file:

```bash
pip install playwright && playwright install chromium
python video/record_demo.py     # -> video/raw/*.webm + marks.json
python video/build_video.py     # -> TREMOR_demo.mp4        (silent)
python video/voiceover.py       # -> TREMOR_demo_vo.mp4     (+ narration)
python video/music.py           # -> TREMOR_demo_final.mp4  (+ bed)
```

Needs `ffmpeg`, `pillow` and `numpy`.

## Audio

The narration is the macOS speech synthesiser, as a stand-in. **Record the same
lines in your own voice and it will sound markedly better**: put the wavs in
`video/vo/` as `00.wav`, `01.wav` and so on, matching the order in
`narration.py`, and re-run `voiceover.py` and `music.py`.

The bed is synthesised in `music.py`, not sourced, so there is no licence
question on a submission. It is an open Dsus2 voicing from D3 to A5, pure sines,
no percussion and no melody, side-chained against the narration so it opens up
in the gaps and stays out of the way under speech. Speech sits at -18.6 dB
against a bed at -33.1 dB. Change `BED_DB` to taste, or skip `music.py`
entirely and ship `TREMOR_demo_vo.mp4`.

**No sound effects.** With narration this dense they read as clutter, and a
whoosh on every scene change makes a technical demo look like an advert.

## What you still have to add

The competition rules ask for a video that shows **the team**, the application
working, its architecture, and its principal results. The last three are in the
cut. The first one is you, and nothing here can record it.

Shoot roughly 15 seconds of yourself, to camera, and put it at the very front.
Total then lands near **3:25**, comfortably inside the five minute limit.

> Hi, I am Tushar. This is TREMOR. It turns an ordinary phone video of a
> machine into a vibration diagnosis, using OpenCV 5 and an agent that decides
> what to film next.

Then read the narration below over the cut.

## Narration

Timecodes are for the assembled file **before** your intro is prepended. Add
your intro length to every number once it is in front.

| Time | On screen | Say |
|---|---|---|
| 0:00 | Title | TREMOR turns ordinary video of a machine into a vibration diagnosis. |
| 0:06 | The problem | Rotating machines announce failure by vibrating. Unbalance, misalignment and looseness are visible weeks ahead. But reading that needs a contact accelerometer, a trained technician and a site visit. So it gets bought for turbines and refinery pumps, and never for the extractor fan or the workshop lathe. Those just run until they break. |
| 0:20 | Why it is hard | So why not point a phone at it? Because the vibration you want is about 2.9 pixels, and your hand moves 72. The signal is twenty five times smaller than the thing you are standing on. |
| 0:29 | What OpenCV does | OpenCV 5 solves exactly this. phaseCorrelate measures displacement far below one pixel. Highpass every pixel in time and the vibrating region finds itself. And hand shake is almost entirely below 1 Hz, while the machine lives at 5 to 15. Separate them in frequency and the signal survives, by a factor of 131. |
| 0:40 | Live, real footage | Here it is on the live endpoint. This is a real clip, shot handheld on an iPhone, of an oscillator running at a known 7.30 Hz. No tripod. The measurement itself is real compute, shown here at triple speed. |
| 0:53 | Result | It recovers 7.28 Hz. Ground truth was 7.30. That is a third of a percent, through twenty pixels of hand shake that it measured and cancelled. |
| 1:04 | The agent | Now the agentic part. I am aiming the operator at the worst surface on the machine, a bare housing with almost no texture, and not telling the agent what the fault is. |
| 1:15 | Decision trace | It measures, sees the signal to noise is below its threshold, and does not guess. It asks for a different shot. On the second acquisition it reads the one, two and three times harmonics and calls mechanical looseness at 0.77 confidence. Two acquisitions, three seconds, and it was right. |
| 1:28 | Architecture | That is the whole shape. Camera in, six OpenCV stages on Graviton, an agent that can send you back for another clip, and a verdict that either reports or escalates to a human. |
| 1:39 | Pipeline | Six stages, and no neural network anywhere. Locate the vibration, measure sub pixel displacement, reject correlation failures, cancel camera motion but only when that helps, transform to a spectrum, and diagnose from the harmonic ratios. Every threshold in there is a number we measured, not one we picked. |
| 1:54 | The bug | Along the way we found a real bug in our own hot path. phaseCorrelate multiplies its source arrays by the window in place. Reuse one as a reference and it decays to nothing. Eleven percent of our frames were being destroyed. Two things we had already written up as limitations were this bug, and there is now a test that fails without the fix. |
| 2:08 | Evidence | We checked it against things whose answer we already knew. An oscillator at a known frequency, to a third of a percent. A real ceiling fan, handheld, at 144 RPM, cross checked against its own blade pass rate to 1.2 percent. That is a closed loop on the same footage. |
| 2:22 | Agentic | The loop closes on the physical world, not on a prompt. Low texture and it re aims. Suspected aliasing and it asks for 240 frames per second. Every guard rail lives in a tool, so it is testable, and the whole surface is exposed over MCP. |
| 2:35 | AWS and COOL | We chose Graviton for a reason and then measured it. COOL gives 1.26 times end to end, and 1.87 on the 2D transform. And the prediction that mattered: Graviton's uniform cores hold 92 percent parallel efficiency at eight workers, against 37 percent on a heterogeneous laptop. Fifty times realtime. |
| 2:51 | Limitations | What it cannot do, plainly. Thirty frames per second caps you at 15 Hz, which is why the agent asks for 240. It needs visible texture. And our COOL number compares two OpenCV versions, so it conflates KleidiCV with upstream changes. We say so in the report. It is a screening tool: it tells you which machine deserves a real accelerometer. |
| 3:03 | Logo | (silence, or) Every machine you own, measurable from your pocket. |

## Notes on the cut

- The upload scene contains about 25 seconds of genuine computation, shown at
  3x with an on screen label saying so. Speeding it up silently would have
  misstated how fast it is.
- Callouts are burned in at the four moments where a number matters.
- The closing shot is the site mark and wordmark alone, with no URL.
- There is a silent stereo audio track so editors and upload pipelines that
  expect one do not choke.

## Files

| File | What it is |
|---|---|
| `record_demo.py` | Drives a clean browser through the demo, records each scene, writes `raw/marks.json` |
| `slides.html` | The twelve slides, a fixed 1280x720 canvas scaled to the recording size |
| `build_video.py` | Trims on the recorded marks, applies the speed ramp and callouts, concatenates |
| `raw/` | Per scene webm plus the timing marks |
| `work/` | Intermediates |
| `TREMOR_demo.mp4` | The cut |

`record_demo.py --headed` shows the browser while it works.
`--only pain|real|agent|how|close` re records a single scene; the marks file merges.
