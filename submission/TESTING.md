# Testing instructions

Live endpoint: **http://50.19.247.214**
Repository: **https://github.com/TusharTechs/tremorcv**
Demo video: **https://youtu.be/vS2g5MvfPmo**

The endpoint is plain HTTP on an Elastic IP, so a browser will say "not secure".
There is no login, nothing is stored, and no personal data is collected.

## 1. Sixty seconds, nothing to install

Open **http://50.19.247.214** and press **Run agent**. Nothing else is needed:
the Simulated tab synthesises a machine, and the agent is not told the fault, the
shaft speed, or whether its first clip is usable.

Watch the **Agent decision trace** on the right. With the default aim point
(`housing`, contrast 0.010, the worst surface on the machine) it will normally
measure, find signal to noise below its threshold, **refuse to answer**, ask the
operator to brace or re aim, and only then commit to a fault. The ground truth is
printed under the verdict so you can check it immediately.

To see the refusal behaviour clearly, set **Severity** to its minimum and press
Run agent again: it should escalate to a human rather than guess.

## 2. Real footage, which is the claim that matters

Switch to the **Upload clip** tab and upload any video of a rotating machine.

To reproduce the exact result in the video and in section 6.2 of the report, use
this clip, which is free to download and not ours:

**https://pixabay.com/videos/id-39861/** (`39861-424022822_medium.mp4`)

Leave frame rate at `0` so it is read from the file, and press **Measure**.
Expect, in about eight seconds:

| | |
|---|---|
| Peak | **2.41 Hz** |
| Shaft rate | **2.406 Hz**, which is 144 RPM |
| Diagnosis | **Unbalance**, confidence 1.00 |
| Camera motion | 7.6 px, cancelled |
| Rejected frames | 0.0% |

**The independent check.** The same spectrum contains the blade pass peak at
12.18 Hz. Count five blades in the preview image. 12.18 divided by 5 is
2.436 Hz, against a measured 2.406 Hz, so two unrelated features of the same
footage agree to **1.2 percent**.

Your own footage works too. Ten seconds, handheld is fine, no tripod. It needs
visible surface texture and something rigid in frame to reference against.

## 3. Run it locally

**Needs Python 3.12 or newer.** numpy 2.5.3 publishes no wheel below cp312, so
on 3.11 or older pip tries to build it from source and usually fails. Check with
`python3 --version`.

Wheels exist for every platform we pin: Windows 64 and 32 bit, Linux x86_64 and
arm64, macOS Intel and Apple silicon.

**macOS and Linux**

```bash
git clone https://github.com/TusharTechs/tremorcv && cd tremorcv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn webapp.server:app --port 8000
```

**Windows, PowerShell**

```powershell
git clone https://github.com/TusharTechs/tremorcv
cd tremorcv
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn webapp.server:app --port 8000
```

If PowerShell blocks the activate script, either run
`Set-ExecutionPolicy -Scope Process RemoteSigned` first, or use
`.venv\Scripts\activate.bat` from cmd.exe instead.

Then open http://localhost:8000.

`requirements.txt` pins **opencv-python-headless** on purpose. Nothing in this
project calls cv2's GUI functions, and the full wheel links libGL, which a
server, a container or WSL without desktop libraries does not have. Using the
full wheel is what broke our own first deployment.

## 4. The test suite

```bash
python -m pytest -q
```

38 tests, about a minute. Pure Python, so it runs the same on all three
platforms. Two are worth reading rather than just running:

* `tests/test_phasecorrelate_mutation.py` fails without `base.copy()`, which is
  the upstream OpenCV behaviour described in section 6.5 of the report.
* `tests/test_agent_loop.py::test_shaft_estimate_stays_out_of_the_hand_motion_band`
  pins a real regression: the harmonic comb used to pick a fundamental inside
  the band where the operator's own hand dominates.

There is one **Unix only** extra, because it exercises the deployment scripts:

```bash
bash tests/test_deploy_scripts.sh
```

It runs them under `env -i`, since four of our deployment failures were things
that work on macOS and break on Linux. On Windows, run it under WSL or skip it.

## 5. Reproduce the agent evaluation

```bash
python eval_agent.py 80
```

About twelve minutes. Expect **83.8 percent** fault correct across all scenarios,
**90.5 percent** when the agent committed, and a confusion matrix. The seed is
fixed, so the numbers should match the report.

## 6. Reproduce the COOL and Graviton benchmark

Needs an AWS account and costs roughly two dollars.

```bash
bash deploy/make-userdata.sh       # writes cloud init for a c8g.2xlarge
# launch the COOL AMI ami-033e481a24f94c8cb with that user data
```

Results land in `results/` as JSON. **Check the provenance block first.** Each
file records `cv2_loaded_from_cool`, the resolved `cv2.__file__` and the
`PYTHONPATH`. An earlier run of ours produced a plausible 0.4 percent difference
because COOL's activate script exports `PYTHONPATH` and a virtualenv deactivate
does not unset it, so both legs had loaded COOL. The gate exists because we were
caught by exactly that.

The three JSON files from our own run are included in the repository and in this
bundle, so the numbers in section 7.3 can be checked without spending anything.

## 7. Drive it over MCP

```bash
python -m agent.mcp_server
```

Eight tools: `start_session`, `capture_clip`, `assess_surface`, `measure`, `assess_quality`,
`diagnose`, `compare_baseline`, `reveal_ground_truth`. Every guard rail lives in a tool rather than in a
prompt, which is why they can be tested independently.
See `docs/MCP.md`.

## What it cannot do

Stated so nothing here surprises you. 30 fps caps the measurable band at 15 Hz,
which is why the agent asks for a faster capture when it needs a third harmonic.
It needs visible surface texture, so a clean painted housing gives it nothing to
lock onto. The COOL figure compares OpenCV 5.1.0 dev against 5.0.0, so it
conflates KleidiCV with upstream changes. It is a screening tool: it tells you
which machine deserves a real accelerometer.
