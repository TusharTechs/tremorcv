"""Render REPORT.md to a print ready PDF via Chromium."""
import pathlib, re
import markdown
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "submission" / "TREMOR_technical_report.pdf"

CSS = """
@page { size: A4; margin: 17mm 16mm 18mm; }
body { font: 10.5pt/1.55 "Charter","Georgia",serif; color:#16202b; max-width:none }
h1 { font-size:22pt; line-height:1.15; margin:0 0 4pt; letter-spacing:-.01em }
h2 { font-size:14pt; margin:20pt 0 6pt; padding-bottom:3pt;
     border-bottom:1px solid #cfd8e3; page-break-after:avoid }
h3 { font-size:11.5pt; margin:14pt 0 4pt; page-break-after:avoid }
h1,h2,h3 { font-family:"Helvetica Neue",Helvetica,Arial,sans-serif; font-weight:650 }
p, li { orphans:3; widows:3 }
code, pre { font-family:"SF Mono",Menlo,monospace; font-size:8.8pt }
code { background:#eef2f7; padding:1px 4px; border-radius:3px }
pre { background:#f5f8fb; border:1px solid #dde5ee; border-left:3px solid #14b8a6;
      border-radius:5px; padding:8pt 10pt; overflow:hidden; page-break-inside:avoid }
pre code { background:none; padding:0 }
table { border-collapse:collapse; width:100%; margin:8pt 0; font-size:9pt;
        page-break-inside:avoid }
th,td { border:1px solid #d5dee8; padding:4pt 7pt; text-align:left; vertical-align:top }
th { background:#eef3f8; font-weight:650 }
blockquote { margin:8pt 0; padding:4pt 12pt; border-left:3px solid #14b8a6;
             color:#44515f }
img { max-width:100%; }
a { color:#0f766e; text-decoration:none }
hr { border:none; border-top:1px solid #d5dee8; margin:14pt 0 }
"""


def main():
    md = (ROOT / "REPORT.md").read_text()
    # inline the architecture diagram where the report references it
    html_body = markdown.markdown(
        md, extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists"])
    html = (f"<!doctype html><meta charset='utf-8'><style>{CSS}</style>"
            f"<body>{html_body}</body>")
    # image srcs in REPORT.md are relative to the repo root, but the temp html
    # lives in submission/, so make them absolute or they render as alt text
    html = re.sub(r'src="(?!https?:|file:|data:)([^"]+)"',
                  lambda m: f'src="{(ROOT / m.group(1)).as_uri()}"', html)
    tmp = ROOT / "submission" / "_report.html"
    tmp.write_text(html)

    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page()
        pg.goto(tmp.as_uri(), wait_until="networkidle")
        pg.pdf(path=str(OUT), format="A4", print_background=True,
               display_header_footer=True,
               header_template="<div></div>",
               footer_template="<div style='width:100%;font:8pt Helvetica;"
                               "color:#8a99ad;padding:0 16mm;display:flex;"
                               "justify-content:space-between'>"
                               "<span>TREMOR &middot; technical report</span>"
                               "<span class='pageNumber'></span></div>")
        br.close()
    tmp.unlink()
    print(f"{OUT.name}  {OUT.stat().st_size/1e6:.2f} MB")


if __name__ == "__main__":
    main()
