"""
Render the Devpost image gallery: real frames from the cut, placed on a 3:2
canvas so nothing is cropped and the set reads as one piece.

  python video/youtube/gallery.py     -> video/youtube/gallery/*.png
"""
import pathlib, subprocess, sys
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "gallery"
VIDEO = HERE.parent / "TREMOR_demo_final.mp4"

# (seconds into the cut, output name). Times sit late inside each beat so the
# entry animations have finished.
SHOTS = [
    (14.0,  "02_problem"),
    (27.0,  "03_why_hard"),
    (38.0,  "04_what_opencv_does"),
    (50.0,  "05_roi_located"),
    (58.0,  "06_fan_result"),
    (74.0,  "07_agent_running"),
    (82.0,  "08_agent_trace"),
    (95.0,  "09_architecture"),
    (110.0, "10_pipeline"),
    (124.0, "11_the_bug"),
    (138.0, "12_evidence"),
    (167.0, "13_cool_graviton"),
    (179.0, "14_limitations"),
]

FRAME = """<!doctype html><meta charset="utf-8">
<style>
  *{box-sizing:border-box;margin:0}
  html,body{width:1920px;height:1280px;overflow:hidden;background:#0c0f14}
  .shot{position:absolute;left:48px;top:74px;width:1824px;height:1026px;
    border:1px solid #22303f;border-radius:14px;overflow:hidden;
    box-shadow:0 30px 90px rgba(0,0,0,.55)}
  .shot img{width:100%;height:100%;display:block;object-fit:cover}
  .brand{position:absolute;left:52px;bottom:52px;display:flex;
    align-items:center;gap:16px}
  .brand img{width:44px;height:44px}
  .brand span{font:700 28px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
    letter-spacing:.17em;color:#4dd4c4}
  .url{position:absolute;right:56px;bottom:62px;
    font:500 24px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:#5d6b7f}
</style>
<div class="shot"><img src="SRC"></div>
<div class="brand"><img src="../favicon.svg"><span>TREMOR</span></div>
<div class="url">github.com/TusharTechs/tremorcv</div>
"""


def main():
    if not VIDEO.exists():
        sys.exit(f"missing {VIDEO}")
    OUT.mkdir(exist_ok=True)
    raw = OUT / "_frames"
    raw.mkdir(exist_ok=True)

    for t, name in SHOTS:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-ss", str(t), "-i", str(VIDEO), "-frames:v", "1",
                        "-y", str(raw / f"{name}.png")], check=True)

    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_context(viewport={"width": 1920, "height": 1280},
                            device_scale_factor=1).new_page()
        for _, name in SHOTS:
            html = HERE / "_frame.html"
            html.write_text(FRAME.replace("SRC", f"gallery/_frames/{name}.png"))
            pg.goto(html.as_uri(), wait_until="networkidle")
            pg.wait_for_timeout(200)
            dst = OUT / f"{name}.png"
            pg.screenshot(path=str(dst))
            print(f"  {dst.name:28s} {dst.stat().st_size/1000:6.0f} kB")
            html.unlink()
        br.close()


if __name__ == "__main__":
    main()
