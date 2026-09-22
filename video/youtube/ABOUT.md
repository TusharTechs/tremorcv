## Inspiration

Every rotating machine tells you it is failing before it fails. It vibrates, and
the vibration has a grammar. Energy at exactly the shaft rate means unbalance.
Energy at twice the shaft rate means misalignment. A ladder at one, two and three
times means something has gone loose. Industry has read that grammar for fifty
years, and ISO 10816 puts numbers on it.

Reading it requires an accelerometer bolted to the housing, a trained analyst,
and a site visit. So it is bought exactly where an hour of downtime costs
thousands: turbines, refinery pumps, large compressors.

**Everything else runs until it breaks.** The extractor fan over a restaurant
kitchen. The lathe in a school workshop. The rooftop HVAC on a small office. The
water pump in an apartment block. The conveyor in a small factory. The people
responsible for those machines are not vibration analysts. They are a facilities
manager, a shop teacher, a building superintendent, a plant operator covering
four jobs. They have no sensor, no training, and no budget to fly one in. They
learn a bearing was dying when it seizes, usually at the worst possible moment.

The gap is not knowledge. The physics has been settled for decades. The gap is
that the **instrument** costs more than the machine it would protect.

What every one of those people already has is a phone.

**So our plan is simple: make the phone the instrument.** Not to replace the
accelerometer, but to answer the question nobody can afford to answer today,
which is *which of my machines deserves one*. Turn condition monitoring from a
scheduled service you buy into something anybody can do in ten seconds, on any
machine, for free.

## What it does

Point a phone at a machine. Hold it in your hand. Ten seconds of ordinary video.

TREMOR returns the **shaft rate** and a **named fault** with a confidence you can
argue with, and shows its working: which region it measured, the displacement
trace, the spectrum, and the harmonic ratios the diagnosis came from.

On the real ceiling fan in the demo, filmed handheld with nothing touching it, it
reports **2.406 Hz, which is 144 RPM, unbalance at confidence 1.00**. That number
is checked against the fan's own blade pass rate in the same footage, 12.18 Hz
over five blades, and the two agree to **1.2 percent**.

The hard part is that **the signal is smaller than your hand**. The vibration is
about 2.9 px. Hand movement on a real clip measured 72.3 px peak to peak. The
thing you want is twenty five times smaller than the thing you are standing on.

It works because the two do not overlap in frequency. We measured a real handheld
clip and found **78.6 percent of hand energy below 1 Hz**, while machines live at
5 to 15 Hz. At 7.3 Hz the hand contributed 0.022 px against 2.885 px of signal:

$$\text{separation} = \frac{2.885\ \text{px}}{0.022\ \text{px}} \approx 131\times$$

It is also **agentic in a way that matters**. The loop closes on the physical
world, not on a prompt. When signal to noise falls below its threshold the system
does not guess: it tells the operator to brace or re aim and takes another clip.
When a harmonic it needs sits above Nyquist, it asks for 240 fps. The whole tool
surface is exposed over **MCP**, so any model can drive it.

## How we built it

Six OpenCV 5 stages, and **no neural network anywhere**.

| Stage | What it does |
|---|---|
| Locate | Highpass every pixel in time, then `cv2.boxFilter` for energy and texture, so the vibrating region finds itself |
| Measure | `cv2.phaseCorrelate` with a Hann window for displacement far below one pixel. 68 percent of all compute |
| Reject | Throw out correlation failures on MAD and on OpenCV's own response strength |
| Cancel | Subtract camera motion against a static reference, and **only when that helps**, since stabilising a still camera adds \\(\sqrt{2}\\) noise |
| Transform | `cv2.dft` to a spectrum, Hann corrected for coherent gain |
| Diagnose | Harmonic comb for the shaft rate, then classic rules on the 1x, 2x and 3x ratios, each gated against the noise floor first |

The agent sits on top as a deterministic policy over those tools. Every guard
rail lives **in a tool rather than in a prompt**, which is the only reason any of
it is testable. There are 37 regression tests.

It runs on **AWS Graviton** with **COOL**, the Cloud Optimized OpenCV Library. We
picked Graviton on a prediction and then measured it. COOL gives **1.26x** end to
end and **1.87x** on the 2D transform. The prediction that mattered was about
scaling: Graviton4's uniform cores held **92 percent parallel efficiency at eight
workers**, against 37 percent on an Apple M series laptop. Fifty times realtime,
against 22.8.

The live endpoint is a FastAPI app streaming the agent trace over SSE, deployed
with SSM so a redeploy takes 11 seconds instead of taking the site down for 320.

## Challenges we ran into

**`cv2.phaseCorrelate` mutates its inputs.** It multiplies each source array by
the window *in place*, so reusing one array as a reference across calls decays it
as \\(\text{base}\times\text{window}^N\\). Eleven percent of our frames were
being quietly destroyed. Two behaviours we had already written up as documented
limitations turned out to be this one bug. The fix is `base.copy()`, and there is
now a test that fails without it.

**A benchmark that measured nothing.** Our first COOL run showed a suspiciously
tidy 0.4 percent difference. COOL's activate script exports `PYTHONPATH`, and a
virtualenv `deactivate` does not unset it, so *both* legs of the comparison had
loaded COOL. We added a provenance gate that resolves `cv2.__file__` and refuses
to report numbers until the two legs are proven different.

**The ceiling fan caught a second real bug, during this submission.** The clip
measured correctly at 2.406 Hz but was *reported* as 0.73 Hz. `amp_at` used an
absolute tolerance, and at a low candidate fundamental that is a large slice of
the harmonic spacing, so adjacent comb slots blurred: the candidate 0.729 Hz put
its 3x slot within 0.219 Hz of the genuine 2.406 Hz peak and scored that peak as
its own evidence. Capping each slot at a quarter of the spacing was still not
enough, because \\(0.802 \times 3 = 2.406\\) exactly. The comb also had to have a
plausible **shape**: no standard signature is dominated by 3x with 1x and 2x both
weak. Fixing it moved agent accuracy from 71.2 to **83.8 percent**.

**Four deployment failures that were all the same failure.** Correct on macOS,
fatal on Linux: a fork versus spawn deadlock, `HOME` unset under cloud init,
`libGL` missing, and a 5 GB allocation that a laptop hid and a 1.7 GB cgroup did
not. There is now a test that runs the deploy scripts under `env -i`.

## Accomplishments that we're proud of

* It works on a **real machine**, handheld, and the number is checked against an
  independent feature of the same footage to 1.2 percent.
* We found and fixed a genuine bug in our own hot path, and **dissolved two
  limitations we had already published** rather than leaving them standing.
* Every threshold in the system is a number we measured. The report says where
  each came from, and says plainly what the tool cannot do.
* The agent **refuses to answer** when it cannot support an answer: 89.3 percent
  correct when it committed, across 80 scenarios.
* We deliberately shipped a **failing** provenance check into the benchmark to
  prove the gate works.

## What we learned

That the honest version is the stronger version. Every time we went looking for
why a result was too good, or too convenient, we found a bug, and the project
came out better each time.

That an ablation can measure the wrong thing. Ours turned out to be measuring
scenario difficulty rather than the value of the loop, so we replaced it with a
sensitivity curve.

And that **hardware choices should be predictions you then test**. We said
Graviton's uniform cores would scale where heterogeneous cores do not, wrote it
down first, and then measured 92 percent against 37.

## What's next for TREMOR: vibration diagnosis from ordinary video

* **Trend over time.** One reading tells you a machine is unbalanced. A baseline
  and a month of readings tell you it is getting worse, which is the number a
  maintenance team can actually act on.
* **Calibrated units.** Converting pixels to millimetres per second with a known
  reference length would let readings be compared against ISO 10816 bands
  directly instead of relatively.
* **On device.** The pipeline is small and has no neural network, so it should
  run on the phone that shot the clip.
* **Rolling element bearing defects.** Those signatures sit at frequencies far
  above 15 Hz, which needs high speed capture and is a genuinely harder problem.
* **Put it in the hands of the people in the first paragraph.** A facilities
  manager with twelve rooftop units and no budget is the user we built this for,
  and the next real test is whether it survives contact with their building.
