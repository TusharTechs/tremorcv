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
