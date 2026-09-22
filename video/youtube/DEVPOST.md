# Devpost submission fields

No hyphens anywhere below.

## Project name (limit 60)

**Use this** (47 characters)

```
TREMOR: vibration diagnosis from ordinary video
```

A judge scanning a gallery of a thousand entries reads the name before anything
else, so it should say what the thing is rather than only what it is called.

Alternatives: `TREMOR` (6), or
`TREMOR: machine vibration diagnosis from ordinary video` (55).

## Elevator pitch (limit 200)

**Use this** (167 characters)

```
Machine vibration diagnosis from ordinary handheld video. A real ceiling fan read at 144 RPM, no contact sensor. OpenCV 5 plus an agent that decides what to film next.
```

It states the category, gives a concrete verified result, and names the agentic
angle, in that order.

Alternatives:

```
Condition monitoring without the accelerometer. Point a phone at a machine and get its shaft rate and a named fault, from OpenCV 5 subpixel motion on AWS Graviton.
```
(163)

```
Your phone can already hear a bearing failing. TREMOR reads machine vibration from ordinary handheld video, names the fault, and asks for a better shot when it needs one.
```
(170)

Avoid the longest draft: it comes to exactly 200, and a field that counts
whitespace differently would truncate it.

## Cover image, 3:2

`devpost_cover_a.png` (recommended) and `devpost_cover_b.png`, both 1920x1280,
around 1 MB, inside Devpost's 5 MB limit.

* **A** puts the fan across the top with the measurement and reference boxes
  visible, then the claim and the verified numbers below. Reads well shrunk to a
  gallery card.
* **B** is full bleed with 144 RPM as the headline.

Regenerate with `python video/youtube/shoot_devpost.py` after editing
`devpost.html`.

## Other fields

| Field | Value |
|---|---|
| Video demo link | https://youtu.be/vS2g5MvfPmo |
| Try it out link | http://50.19.247.214 |
| Repository | https://github.com/TusharTechs/tremorcv |
| Built with | opencv, python, fastapi, aws, ec2, graviton, cool, kleidicv, mcp, numpy |

For the long "About the project" body, `REPORT.md` is already written to that
shape: problem, what it does, architecture, the OpenCV 5 implementation, the
agentic layer, evaluation, AWS and COOL, limitations, reproducibility. Paste it
and trim, rather than writing something new that then disagrees with the report.


## About the project

See `ABOUT.md` in this folder. Paste it whole.

## Built with (limit 25)

```
opencv, opencv5, python, fastapi, numpy, pytest, mcp, aws, ec2, graviton, ssm, cool, kleidicv, arm, linux, systemd, javascript, html, css, matplotlib, ffmpeg, playwright, mermaid, git, fft
```

Only what is actually used. No S3, Lambda, DynamoDB or CloudWatch: those
appear in the architecture diagram as planned, not built, and the diagram
marks them as such.

## Image gallery captions (limit 140 each)

Upload in this order. The cover doubles as the first gallery image.

| Chars | File | Caption |
|---|---|---|
| 134 ok  | `devpost_cover_a.png` | TREMOR reads machine vibration from ordinary handheld video. A real ceiling fan at 2.406 Hz, which is 144 RPM, with no contact sensor. |
| 133 ok  | `02_problem.png` | The pain point. Vibration analysis needs a contact sensor, a technician and a site visit, so most machines are never measured at all. |
| 122 ok  | `03_why_hard.png` | Why you cannot just film it. The vibration is about 2.9 px while a handheld phone moves 72.3 px, twenty five times larger. |
| 122 ok  | `04_what_opencv_does.png` | The insight. Hand shake is 78.6 percent below 1 Hz and machines live at 5 to 15 Hz, giving 131 times separation at 7.3 Hz. |
| 137 ok  | `05_roi_located.png` | The vibrating region and a rigid reference are found automatically by highpass filtering every pixel in time. No model, no training data. |
| 127 ok  | `06_fan_result.png` | A real ceiling fan filmed handheld: 2.406 Hz and 144 RPM, unbalance at confidence 1.00, with 7.6 px of camera motion cancelled. |
| 132 ok  | `07_agent_running.png` | The agent is aimed at the worst surface on the machine and is never told the fault. It has to find out, and change what it asks for. |
| 136 ok  | `08_agent_trace.png` | Signal to noise too low, so it refuses to guess and asks for a better shot. Second acquisition: mechanical looseness at 0.77 confidence. |
| 134 ok  | `09_architecture.png` | Camera in, six OpenCV 5 stages on Graviton, an agent that can send you back for another clip, and a verdict that reports or escalates. |
| 118 ok  | `10_pipeline.png` | Six OpenCV 5 stages and no neural network anywhere. Every threshold is a number we measured rather than one we picked. |
| 133 ok  | `11_the_bug.png` | A real bug in our own hot path. cv2.phaseCorrelate multiplies its inputs by the window in place, destroying 11 percent of our frames. |
| 137 ok  | `12_evidence.png` | Checked against answers we already knew: an oscillator to 0.33 percent, and a ceiling fan to 1.2 percent against its own blade pass rate. |
| 129 ok  | `13_cool_graviton.png` | COOL gives 1.26 times end to end. Graviton4 holds 92 percent parallel efficiency at eight workers against 37 percent on a laptop. |
| 134 ok  | `14_limitations.png` | Stated plainly. 30 fps caps the band at 15 Hz, it needs visible surface texture, and it is a screening tool rather than a replacement. |
