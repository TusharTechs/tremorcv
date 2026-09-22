# YouTube publishing pack

Nothing below contains a hyphen, including the chapter titles and tags.

## Thumbnail

`thumbnail_a.png` (recommended) and `thumbnail_b.png`, both 1280x720 PNG, well
under YouTube's 2 MB limit. Both use a real frame from the video: the ceiling
fan with the automatically located measurement and reference boxes drawn on it.

* **A** leads with the claim, "NO SENSOR. JUST VIDEO.", and carries the proof as
  a chip underneath. Strongest at sidebar size, which is where most clicks come
  from.
* **B** leads with the number, "144 RPM". Use it if you would rather the fan be
  the first thing read.

Regenerate either with `python video/youtube/shoot.py` after editing
`thumb.html`.

## Title

**Primary**

```
TREMOR: machine vibration diagnosis from ordinary video
```

**Alternatives**

```
No sensor, just video: machine vibration diagnosis with OpenCV 5
I diagnosed a ceiling fan with a phone camera and OpenCV 5
```

The primary is 54 characters, so it survives truncation on mobile and matches
the wordmark a judge will also see on the site and the repo.

## Description

```
A machine tells you it is failing by vibrating. Reading that today needs a contact accelerometer, a trained technician and a site visit, so it gets bought for turbines and refinery pumps and never for the extractor fan, the workshop lathe or the rooftop HVAC unit. Those machines run until something breaks.

TREMOR measures the vibration from ordinary video. No contact sensor, no tripod. In this demo it reads a real ceiling fan, filmed handheld, at 2.406 Hz, which is 144 RPM, and cross checks that against the fan's own blade pass rate in the same footage to within 1.2 percent.

The hard part is that the signal is smaller than your hand. The vibration is about 3 pixels; hand movement on a real clip measured 72 pixels peak to peak. They do not overlap in frequency: 78.6 percent of hand energy sits below 1 Hz while the machine lives at 5 to 15 Hz, which gives 131 times separation at 7.3 Hz. OpenCV 5 does the rest, with cv2.phaseCorrelate measuring displacement far below one pixel.

It is also agentic in a way that matters. The loop closes on the physical world rather than on a prompt: when signal to noise is too low the system does not guess, it asks the operator for a different shot, and when a harmonic sits above Nyquist it asks for 240 frames per second. Every guard rail lives in a tool rather than a prompt, so all of it is testable, and the whole surface is exposed over MCP.

Built on OpenCV 5 and benchmarked on AWS Graviton with COOL, the Cloud Optimized OpenCV Library. COOL gives 1.26 times end to end and 1.87 times on the 2D transform, and Graviton4's uniform cores hold 92 percent parallel efficiency at eight workers against 37 percent on an Apple M series laptop.

Live demo: http://50.19.247.214
Source and technical report: https://github.com/TusharTechs/tremorcv

Built for the OpenCV AI Competition 2026, powered by AWS.

CHAPTERS
0:00 The problem
0:20 Why you cannot just film it, and what OpenCV 5 does
0:40 Live demo: a real ceiling fan, handheld
1:01 The agent asks for a better shot
1:26 Architecture
1:37 Six stages, no neural network
1:52 A bug we found in our own hot path
2:06 Evidence
2:20 The agentic layer
2:33 COOL on AWS Graviton
2:49 What it cannot do
3:02 Close

WHAT IT CANNOT DO
30 fps caps the measurable band at 15 Hz, which is why the agent asks for a faster capture. It needs visible surface texture. The COOL figure compares OpenCV 5.1.0 dev against 5.0.0, so it conflates KleidiCV with upstream changes, and the report says so. It is a screening tool: it tells you which machine deserves a real accelerometer.

Stack: OpenCV 5, Python, FastAPI, AWS EC2 Graviton, COOL, KleidiCV, MCP.
Licence: MIT.
```

**If you prepend your intro, every chapter timestamp shifts by its length.**
A 15 second intro makes the first chapter `0:00 Introduction`, then add 15
seconds to each of the rest.

## Tags

Paste as a comma separated list. This is 381 characters, inside YouTube's 500.

```
opencv, opencv 5, computer vision, vibration analysis, predictive maintenance, condition monitoring, phase correlation, subpixel motion, camera vibrometry, aws graviton, kleidicv, agentic ai, mcp, model context protocol, signal processing, spectral analysis, fft, python, opencv ai competition, ceiling fan rpm, machine health monitoring, motion magnification, computer vision project
```

## Category and settings

| Field | Value |
|---|---|
| Category | Science & Technology |
| Visibility | Public, or Unlisted if you prefer. The rules require only that judges can reach it |
| Language | English |
| Licence | Standard YouTube Licence |
| Audience | Not made for kids |
| Comments | On. Public voting runs alongside judging, and engagement helps |
| Shorts remix | Allow |
| Captions | Upload one. `narration.py` already holds the exact script, and captions help both judges and reach |

Put the same link in the Devpost submission and pin a comment with the live
demo URL.
