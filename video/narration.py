"""
Narration cues for TREMOR_demo.mp4, as (start_seconds, text).

Spelled for a speech synthesiser: "hertz" not "Hz", "phase correlate" not
"phaseCorrelate". video/SCRIPT.md carries the same content written for a human,
which can be read more naturally and a little faster.

Each line is sized to the gap before the next cue. voiceover.py prints an
OVERRUN warning if one runs long, so re-check after editing.
"""

NARRATION = [
 (1.4,   "TREMOR turns ordinary video into a vibration diagnosis."),
 (7.2,   "Machines announce failure by vibrating. Unbalance, misalignment, looseness, "
         "weeks ahead. But reading it needs a contact sensor, a technician, a site "
         "visit. So it is bought for turbines, and never for the extractor fan."),
 (21.2,  "So why not just point a phone at it? The vibration is three pixels. "
         "Your hand moves seventy two."),
 (30.2,  "Open C V five solves this. Phase correlate measures far below one pixel. "
         "Hand shake sits below one hertz, the machine at five to fifteen. "
         "Separate them, and the signal survives."),
 (41.3,  "Here it is, live. A real ceiling fan, filmed handheld, nothing touching it."),
 (50.4,  "Two point four zero six hertz. One hundred forty four R P M, agreeing to "
         "one percent with the fan's own blade pass rate."),
 (62.5,  "Now the agent. I aim it at the worst surface on the machine, and never "
         "tell it what the fault is."),
 (76.3,  "It sees the signal to noise is too low, and refuses to guess. It asks for a "
         "better shot. Then it reads the harmonics and calls mechanical looseness. "
         "Two acquisitions, three seconds, correct."),
 (88.0,  "That is the shape. Camera in, six Open C V stages on Graviton, an agent that "
         "sends you back for another clip."),
 (98.2,  "Six stages, no neural network. Locate the vibration. Measure sub pixel "
         "displacement. Reject failures. Cancel camera motion. Take a spectrum, "
         "and read the harmonic ratios."),
 (113.2, "We found a real bug in our own hot path. Phase correlate multiplies its "
         "inputs by the window, in place. Eleven percent of our frames were being "
         "destroyed."),
 (127.2, "We checked against answers we already knew. An oscillator, to a third of a "
         "percent. A real fan at one hundred forty four R P M, against its own "
         "blade pass rate."),
 (141.2, "The loop closes on the physical world, not a prompt. Low texture, it re aims. "
         "Aliasing, it asks for more frames per second."),
 (154.2, "We chose Graviton, then measured it. COOL gives one point two six times end "
         "to end. And Graviton's uniform cores hold ninety two percent parallel "
         "efficiency at eight workers, against thirty seven on a laptop."),
 (170.2, "What it cannot do. Thirty frames per second caps you at fifteen hertz. "
         "It needs visible texture. It is a screening tool."),
 (183.0, "Every machine you own, measurable from your pocket."),
]
