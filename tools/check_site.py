"""Check every page with axe in both themes and print the one-page A4 CV.

Requires playwright, pypdf and an axe-core script supplied through AXE_PATH.
Screenshots, the CV and the results JSON go outside the published site.
"""

import argparse
import functools
import http.server
import json
import os
import pathlib
import subprocess
import threading

from playwright.sync_api import sync_playwright
from pypdf import PdfReader

ROOT = pathlib.Path(__file__).resolve().parent.parent


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--cards", action="store_true", help="Render project social cards")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    axe = pathlib.Path(os.environ["AXE_PATH"]).read_text()
    pages = [ROOT / "index.html", ROOT / "404.html", *sorted((ROOT / "projects").glob("*/index.html"))]
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    report = {"axe": [], "print": {}}
    try:
        with sync_playwright() as playwright:
            options = {"headless": True, "args": ["--renderer-process-limit=1"]}
            if os.environ.get("CHROMIUM_PATH"):
                options["executable_path"] = os.environ["CHROMIUM_PATH"]
            browser = playwright.chromium.launch(**options)
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            for path in pages:
                relative = path.relative_to(ROOT).as_posix()
                for theme in ("light", "dark"):
                    page.emulate_media(color_scheme=theme)
                    response = page.goto(f"{base}/{relative}")
                    if response.status != 200:
                        raise RuntimeError(f"{relative}: HTTP {response.status}")
                    if page.locator("script").count():
                        raise RuntimeError(f"{relative}: authored scripts are not allowed")
                    page.evaluate("document.fonts.ready")
                    page.add_script_tag(content=axe)
                    result = page.evaluate("async () => { const r = await axe.run(); return r.violations; }")
                    report["axe"].append({"page": relative, "theme": theme, "violations": result})
                    if theme == "light":
                        name = "homepage-desktop" if relative == "index.html" else relative.replace("/index.html", "").replace("/", "-").replace(".html", "")
                        page.screenshot(path=str(args.output / f"{name}.png"), full_page=True)
            page.emulate_media(color_scheme="light")
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(base)
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(args.output / "homepage-phone.png"), full_page=True)
            pdf = args.output / "cv.pdf"
            page.pdf(path=str(pdf), format="A4", prefer_css_page_size=True, print_background=True)
            document = PdfReader(pdf)
            size = document.pages[0].mediabox
            report["print"] = {"pages": len(document.pages), "width_points": float(size.width), "height_points": float(size.height)}
            subprocess.run(
                ["pdftoppm", "-f", "1", "-singlefile", "-scale-to", "1600", "-png",
                 str(pdf), str(args.output / "cv-first-page")], check=True)
            if args.cards:
                page.emulate_media(media="screen")
                page.set_viewport_size({"width": 1280, "height": 800})
                page.goto(f"{base}/tools/cards.html")
                page.evaluate("document.fonts.ready")
                for card in page.locator(".card.project").all():
                    name = card.get_attribute("id").removeprefix("og-")
                    box = card.bounding_box()
                    if box["width"] != 1200 or box["height"] != 630:
                        raise RuntimeError(f"{name}: card must be 1200 by 630 pixels")
                    card.screenshot(path=str(ROOT / "og" / f"{name}.png"))
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    (args.output / "checks.json").write_text(json.dumps(report, indent=2) + "\n")
    failures = sum(len(row["violations"]) for row in report["axe"])
    print(f"axe: {len(report['axe'])} page/theme checks, {failures} violations")
    print(f"print: {report['print']['pages']} A4 page(s)")
    if failures or report["print"]["pages"] != 1:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
