"""Stamp the stylesheet link with a hash of site.css.

    python3 tools/stamp.py

GitHub Pages lets browsers reuse files for 10 minutes. Without a stamp, a
reload after a deploy can pair the new page with the old cached stylesheet.
Run this after every edit to site.css.
"""

import hashlib
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
LINK = re.compile(r'href="/site\.css(\?v=[0-9a-f]+)?"')


def main() -> None:
    digest = hashlib.sha256((ROOT / "site.css").read_bytes()).hexdigest()[:10]
    for name in ("index.html", "404.html"):
        path = ROOT / name
        html, count = LINK.subn(f'href="/site.css?v={digest}"', path.read_text())
        if count != 1:
            raise SystemExit(f"{name}: expected one stylesheet link, found {count}")
        path.write_text(html)
        print(f"{name}: /site.css?v={digest}")


if __name__ == "__main__":
    main()
