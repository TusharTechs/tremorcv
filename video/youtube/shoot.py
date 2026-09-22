"""Render the thumbnail variants to PNG at YouTube's 1280x720."""
import pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_context(viewport={"width": 1280, "height": 720},
                        device_scale_factor=1).new_page()
    pg.goto((HERE / "thumb.html").as_uri(), wait_until="networkidle")
    for i, name in enumerate("ab"):
        pg.evaluate(f"""() => {{
            document.querySelectorAll('.t').forEach((s, j) =>
                s.classList.toggle('on', j === {i}));
        }}""")
        pg.wait_for_timeout(350)
        out = HERE / f"thumbnail_{name}.png"
        pg.screenshot(path=str(out))
        print(f"  {out.name}  {out.stat().st_size/1000:.0f} kB")
    br.close()
