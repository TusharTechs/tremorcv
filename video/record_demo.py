"""
Drive the live TREMOR endpoint through the full demo and record it.

Runs a clean browser -- its own profile, no tabs, no extensions, nothing of
yours on screen -- so the footage contains only the app.

  python video/record_demo.py                 # headless, records segments
  python video/record_demo.py --headed        # watch it happen
  python video/record_demo.py --url http://localhost:8000

Segments land in video/raw/ as webm, one per scene.
"""
import argparse, json, pathlib, shutil, sys, time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
RAW = ROOT / "raw"

# A soft dot that follows the mouse, so a viewer can see what is being clicked.
CURSOR = """
(() => {
  const d = document.createElement('div');
  d.id = '__cur';
  d.style.cssText = 'position:fixed;z-index:99999;width:18px;height:18px;'
    + 'border-radius:50%;background:rgba(255,120,60,.55);'
    + 'border:2px solid rgba(255,255,255,.9);pointer-events:none;'
    + 'transform:translate(-50%,-50%);transition:transform .08s;left:-99px;top:-99px';
  document.body.appendChild(d);
  // the dot lives inside the zoomed root, so undo the zoom on its coordinates
  const z = () => parseFloat(document.documentElement.style.zoom) || 1;
  addEventListener('mousemove', e => {
    d.style.left = (e.clientX/z())+'px'; d.style.top = (e.clientY/z())+'px'; }, true);
  addEventListener('mousedown', () => d.style.transform = 'translate(-50%,-50%) scale(.6)', true);
  addEventListener('mouseup',   () => d.style.transform = 'translate(-50%,-50%) scale(1)', true);
})();
"""


def glide(page, sel, steps=22):
    """Move the pointer to an element the way a hand would, then click."""
    el = page.locator(sel).first
    el.scroll_into_view_if_needed()
    b = el.bounding_box()
    if not b:
        raise RuntimeError(f"no bounding box for {sel}")
    page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=steps)
    page.wait_for_timeout(260)
    page.mouse.click(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    page.wait_for_timeout(260)


def pick(page, host, value):
    """Open one of the custom listboxes and choose an option by its value."""
    glide(page, host)
    page.wait_for_timeout(420)
    glide(page, f'{host} [role="option"][data-v="{value}"]')
    page.wait_for_timeout(420)


# A magenta bar flashed across the top of the page at the "start" mark.
# Playwright's video does not begin at page creation, and the lead-in varies by
# a few seconds between file:// and http pages, so wall-clock marks cannot be
# mapped into the video timeline by subtraction. build_video.py finds this bar
# and anchors every other mark to the frame it lands on.
SYNC = """
(() => {
  const b = document.createElement('div');
  b.style.cssText = 'position:fixed;left:0;top:0;width:100%;height:12px;'
    + 'background:#ff00ff;z-index:2147483647;pointer-events:none';
  document.body.appendChild(b);
  setTimeout(() => b.remove(), 300);
})();
"""

MARKS = {}


def scene(ctx, name, url, body, out, zoom=None):
    page = ctx.new_page()
    t0 = time.time()                       # video starts about here
    page.set_default_timeout(180_000)
    page.goto(url, wait_until="networkidle")
    if zoom:
        # The app is laid out for a ~1280 column. Recording at 1920 keeps the
        # frame a true 1080p, so zoom the page to keep the layout dense.
        page.evaluate(f"document.documentElement.style.zoom = '{zoom}'")
        page.wait_for_timeout(500)
    page.add_init_script(CURSOR)
    page.evaluate(CURSOR)
    page.wait_for_timeout(900)
    marks = []
    page.__mark = lambda tag: marks.append({"tag": tag, "t": round(time.time() - t0, 2)})
    page.evaluate(SYNC)
    page.__mark("start")
    page.wait_for_timeout(700)
    try:
        body(page)
    finally:
        page.__mark("end")
        MARKS[out.name] = marks
        page.wait_for_timeout(1200)
        vid = page.video
        page.close()
        if vid:
            src = pathlib.Path(vid.path())
            shutil.move(src, out)
            print(f"  wrote {out.name}  ({out.stat().st_size/1e6:.1f} MB)")


# ---------------------------------------------------------------- scenes

def scene_real(clip):
    """Real handheld footage of a ceiling fan in, 144 RPM out."""
    def body(page):
        glide(page, "#tabUp")
        page.wait_for_timeout(700)
        page.set_input_files("#file", str(clip))
        page.wait_for_timeout(1400)
        glide(page, "#analyze")
        page.__mark("crunch_start")
        # the real measurement takes a while -- let it
        page.wait_for_selector("#previewCard:not([hidden])", timeout=180_000)
        page.__mark("crunch_end")
        page.wait_for_timeout(1600)
        # let the eye settle on each result in turn
        for sel in ("#previewCard", "#specCard, #spec", "#stats"):
            try:
                page.locator(sel).first.scroll_into_view_if_needed()
                page.wait_for_timeout(2600)
            except Exception:
                pass
        page.mouse.wheel(0, 260)
        page.wait_for_timeout(2400)
    return body


def scene_agent(fault, shaft, aim):
    """Deliberately aim at the worst surface and let the agent recover."""
    def body(page):
        glide(page, "#tabSim")
        page.wait_for_timeout(600)
        pick(page, "#faultSel", fault)
        page.locator("#shaft").evaluate(
            "(el,v)=>{el.value=v;el.dispatchEvent(new Event('input'))}", str(shaft))
        page.wait_for_timeout(600)
        pick(page, "#aimSel", aim)
        page.wait_for_timeout(700)
        glide(page, "#run")
        page.__mark("crunch_start")
        # each step appears as the agent decides -- hold on the trace
        page.wait_for_selector("#verdict > *", timeout=180_000)
        page.__mark("crunch_end")
        page.wait_for_timeout(2200)
        page.locator("#steps").scroll_into_view_if_needed()
        page.wait_for_timeout(1000)
        for _ in range(6):
            page.mouse.wheel(0, 200)
            page.wait_for_timeout(900)
        page.wait_for_timeout(2000)
    return body



# Seconds to hold each slide, matched to the narration in video/SCRIPT.md.
DWELL = [6, 14, 9, 11, 11, 15, 14, 14, 13, 16, 12, 7]


def scene_slides(first, last):
    """Step through slides [first, last] inclusive, 1-based."""
    def body(page):
        page.wait_for_function("() => window.__count > 0")
        page.evaluate(f"window.__go({first - 1})")
        for n in range(first, last + 1):
            page.__mark(f"slide{n}")
            page.wait_for_timeout(int(DWELL[n - 1] * 1000))
            if n < last:
                page.evaluate("window.__n()")
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://50.19.247.214")
    ap.add_argument("--clip", default=str(pathlib.Path.home()
                    / "Downloads/39861-424022822_medium.mp4"))
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--only", default="", help="pain|real|agent|how|close")
    a = ap.parse_args()

    clip = pathlib.Path(a.clip).expanduser()
    if not clip.exists():
        sys.exit(f"clip not found: {clip}")

    RAW.mkdir(parents=True, exist_ok=True)
    # The app is laid out for a ~1280 column; at a 1920 viewport it goes sparse.
    # So render the dense layout at 2x and let Playwright scale it to 1080p.
    size = {"width": 1920, "height": 1080}
    ZOOM = 1.5

    with sync_playwright() as p:
        br = p.chromium.launch(headless=not a.headed, args=["--force-color-profile=srgb"])
        ctx = br.new_context(viewport=size, record_video_dir=str(RAW),
                             record_video_size=size, device_scale_factor=2)
        slides = (ROOT / "slides.html").as_uri()
        print(f"recording against {a.url}")
        if a.only in ("", "pain"):
            print(" scene: pain point (slides 1-4)")
            scene(ctx, "pain", slides, scene_slides(1, 4), RAW / "01_pain.webm")
        if a.only in ("", "real"):
            print(" scene: real footage")
            scene(ctx, "real", a.url, scene_real(clip), RAW / "02_real.webm", ZOOM)
        if a.only in ("", "agent"):
            print(" scene: agent loop")
            scene(ctx, "agent", a.url, scene_agent("mechanical_looseness", 4.3, "housing"),
                  RAW / "03_agent.webm", ZOOM)
        if a.only in ("", "how"):
            print(" scene: how it works (slides 5-11)")
            scene(ctx, "how", slides, scene_slides(5, 11), RAW / "04_how.webm")
        if a.only in ("", "close"):
            print(" scene: close (slide 12)")
            scene(ctx, "close", slides, scene_slides(12, 12), RAW / "05_close.webm")
        ctx.close()
        br.close()
    # merge, so re-recording one scene with --only keeps the others' marks
    mf = RAW / "marks.json"
    prev = json.loads(mf.read_text()) if mf.exists() else {}
    prev.update(MARKS)
    mf.write_text(json.dumps(prev, indent=2))
    print("done ->", RAW)


if __name__ == "__main__":
    main()
