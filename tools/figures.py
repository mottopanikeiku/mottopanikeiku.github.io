"""Draw the site's figures as inline SVG.

    python3 tools/figures.py

Reads data/*.json (written by tools/extract_data.py) and replaces whatever sits
between <!-- figure:NAME --> and <!-- /figure:NAME --> in the site's HTML.
Colors and type come from site.css, so figures follow light and dark mode.
"""

import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKER = re.compile(r"(<!-- figure:([\w-]+) -->)(.*?)(<!-- /figure:\2 -->)", re.S)


def load(name: str) -> dict:
    return json.loads((ROOT / "data" / f"{name}.json").read_text())


def scale(d0: float, d1: float, r0: float, r1: float):
    return lambda v: r0 + (v - d0) * (r1 - r0) / (d1 - d0)


def f(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


class SVG:
    def __init__(self, name: str, width: int, height: int, title: str, desc: str):
        self.name, self.width, self.height = name, width, height
        self.title, self.desc = title, desc
        self.parts: list[str] = []

    def line(self, x1, y1, x2, y2, cls):
        self.parts.append(f'<line class="{cls}" x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}"/>')

    def path(self, points, cls):
        d = "M" + " L".join(f"{f(x)} {f(y)}" for x, y in points)
        self.parts.append(f'<path class="{cls}" d="{d}"/>')

    def circle(self, x, y, r, cls):
        self.parts.append(f'<circle class="{cls}" cx="{f(x)}" cy="{f(y)}" r="{f(r)}"/>')

    def rect(self, x, y, w, h, cls):
        self.parts.append(f'<rect class="{cls}" x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}"/>')

    def text(self, x, y, s, cls="", anchor="start"):
        c = f' class="{cls}"' if cls else ""
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.parts.append(f'<text{c}{a} x="{f(x)}" y="{f(y)}">{html.escape(s)}</text>')

    def render(self) -> str:
        t, d = f"{self.name}-title", f"{self.name}-desc"
        head = (
            f'<svg class="chart" viewBox="0 0 {self.width} {self.height}" '
            f'role="img" aria-labelledby="{t} {d}">'
            f'<title id="{t}">{html.escape(self.title)}</title>'
            f'<desc id="{d}">{html.escape(self.desc)}</desc>'
        )
        return head + "".join(self.parts) + "</svg>"


def branchpilot() -> str:
    data = load("branchpilot")
    rows = data["rows"]
    by = {fam: sorted((r for r in rows if r["family"] == fam), key=lambda r: r["samples"])
          for fam in ("fixed", "confidence", "agreement", "learned")}
    W, H, L, R, T, B = 560, 368, 50, 16, 80, 46
    x = scale(1, 8, L, W - R)
    y = scale(0.66, 0.82, H - B, T)
    s = SVG("branchpilot", W, H,
            "GSM8K test accuracy against average samples per problem",
            "Fixed sample counts from one to eight rise from 68.8% to 80.1%. Stopping after two "
            "matching answers in a row reaches 78.8% at 3.2 samples. The learned stopping rule "
            "lies between, from 72.5% at 1.5 samples to 76.3% at 3.4 samples, below the "
            "agreement rule.")

    def key(lx, ly, mark, label, cls=""):
        if mark == "line":
            s.line(lx, ly - 4, lx + 20, ly - 4, f"line {cls}".strip())
            s.circle(lx + 10, ly - 4, 3, f"dot {cls}".strip())
        else:
            s.circle(lx + 10, ly - 4, 3, mark)
        s.text(lx + 28, ly, label, cls)

    key(L, 18, "line", "learned stopping rule", "em")
    key(L + 250, 18, "dot strong", "stop at 2 or 3 matching answers", "strong")
    key(L, 40, "line", "fixed number of samples")
    key(L + 250, 40, "dot hollow", "vote-share thresholds")

    for v in (0.68, 0.72, 0.76, 0.80):
        s.line(L, y(v), W - R, y(v), "grid")
        s.text(L - 8, y(v) + 4, f"{v * 100:.0f}%", anchor="end")
    s.text(L - 8, T - 14, "test accuracy, 1,319 problems")
    s.line(L, H - B, W - R, H - B, "axis")
    for n in range(1, 9):
        s.line(x(n), H - B, x(n), H - B + 4, "axis")
        s.text(x(n), H - B + 18, str(n), anchor="middle")
    s.text((L + W - R) / 2, H - 6, "average samples per problem", anchor="middle")

    s.path([(x(r["samples"]), y(r["accuracy"])) for r in by["fixed"]], "line")
    for r in by["fixed"]:
        s.circle(x(r["samples"]), y(r["accuracy"]), 2.6, "dot")
    for r in by["confidence"]:
        s.circle(x(r["samples"]), y(r["accuracy"]), 2.6, "dot hollow")

    for fam, cls in (("learned", "em"), ("agreement", "strong")):
        for r in by[fam]:
            (alo, ahi), (slo, shi) = r["accuracy_ci"], r["samples_ci"]
            s.line(x(r["samples"]), y(alo), x(r["samples"]), y(ahi), f"ci {cls}")
            s.line(x(slo), y(r["accuracy"]), x(shi), y(r["accuracy"]), f"ci {cls}")
    s.path([(x(r["samples"]), y(r["accuracy"])) for r in by["learned"]], "line em")
    for r in by["learned"]:
        s.circle(x(r["samples"]), y(r["accuracy"]), 3.2, "dot em")
    for r in by["agreement"]:
        s.circle(x(r["samples"]), y(r["accuracy"]), 3.2, "dot strong")

    agree = {r["policy"]: r for r in by["agreement"]}
    a2, a3 = agree["agreement-2"], agree["agreement-3"]
    s.text(x(a2["samples_ci"][0]) - 6, y(a2["accuracy"]) + 4, "2 in a row", "strong", "end")
    s.text(x(a3["samples_ci"][1]) + 6, y(a3["accuracy"]) + 4, "3 in a row", "strong")
    return s.render()


def faultline() -> str:
    data = load("faultline")
    arms = data["arms"]
    cols = [("random", "50/50 mix"), ("difficulty", "difficulty-adaptive"), ("epistemic", "all ambiguous")]
    W, H, L, R, T, B = 560, 316, 50, 20, 46, 44
    xs = [L + 70, (L + W - R) / 2 + 10, W - R - 90]
    y = scale(0, 1, H - B, T)
    s = SVG("faultline", W, H,
            "Diagnostic success of each training seed under three curricula",
            "Eight paired seeds per curriculum. Means: 50/50 mix 0.81, difficulty-adaptive 0.90, "
            "all ambiguous 0.95. Most seeds reach 100% under every curriculum; the means differ "
            "because of a few poor seeds.")
    for v in (0, 0.25, 0.5, 0.75, 1.0):
        s.line(L, y(v), W - R, y(v), "grid")
        s.text(L - 8, y(v) + 4, f"{v * 100:.0f}%", anchor="end")
    s.text(L - 8, T - 14, "diagnostic success on held-out tasks, one line per seed")
    seeds = sorted(arms["random"]["seeds"], key=int)
    jitter = {seed: (i - (len(seeds) - 1) / 2) * 2.4 for i, seed in enumerate(seeds)}
    for seed in seeds:
        pts = [(xs[i] + jitter[seed], y(arms[key]["seeds"][seed])) for i, (key, _) in enumerate(cols)]
        s.path(pts, "line faint")
        for px, py in pts:
            s.circle(px, py, 2.6, "dot")
    for i, (key, label) in enumerate(cols):
        mean = arms[key]["mean"]
        s.line(xs[i] - 16, y(mean), xs[i] + 16, y(mean), "mean")
        s.text(xs[i] + 22, y(mean) + 4, f"mean {mean:.2f}", "strong")
        s.text(xs[i], H - B + 20, label, anchor="middle")
    return s.render()


def heliostune() -> str:
    data = load("heliostune")
    methods = data["methods"]
    series = [
        ("cold_thompson", "line strong", "cold-start Thompson sampling"),
        ("parhelion_thompson", "line em", "Parhelion (retrieval first)"),
        ("single_source_nearest", "line dash", "reuse the nearest measured shape"),
        ("multisource_retrieval", "line", "retrieval only"),
    ]
    W, H, L, R, T, B = 560, 330, 50, 16, 96, 46
    x = scale(1, 8, L, W - R)
    y = scale(0.76, 1.02, H - B, T)
    torch = methods["torch"]["points"][0]["mean"]
    s = SVG("heliostune", W, H,
            "H100 tuning quality against the number of configurations timed",
            "Score is the best Triton configuration found divided by the best of the 36 curated "
            "configurations. Cold-start Thompson sampling and Parhelion both reach 0.997 by eight "
            f"probes; reuse and retrieval baselines stay lower. torch.matmul scores {torch:.2f} on "
            "the same scale, off the top of the chart.")
    for i, (key, cls, label) in enumerate(series):
        lx = L + (i % 2) * 250
        ly = 18 + (i // 2) * 20
        s.line(lx, ly - 4, lx + 22, ly - 4, cls)
        s.text(lx + 30, ly, label, "em" if "em" in cls else ("strong" if "strong" in cls else ""))
    s.text(W - R, 70, f"torch.matmul: {torch:.2f} \u2191", "strong", "end")
    s.text(L - 8, T - 12, "score against the best of 36 Triton configurations")
    for v in (0.8, 0.85, 0.9, 0.95, 1.0):
        s.line(L, y(v), W - R, y(v), "grid")
        s.text(L - 8, y(v) + 4, f"{v:.2f}", anchor="end")
    s.line(L, H - B, W - R, H - B, "axis")
    for n in range(1, 9):
        s.line(x(n), H - B, x(n), H - B + 4, "axis")
        s.text(x(n), H - B + 18, str(n), anchor="middle")
    s.text((L + W - R) / 2, H - 6, "configurations timed on the H100", anchor="middle")
    for key, cls, _ in series:
        pts = [(x(p["budget"]), y(p["mean"])) for p in methods[key]["points"]]
        s.path(pts, cls)
        for px, py in pts:
            s.circle(px, py, 2.4, "dot " + cls.replace("line", "").replace("dash", "").strip())
    return s.render()


def verge_lab() -> str:
    data = load("verge-lab")
    total = data["pairs"]
    vs = data["defended_vs_overall"]
    stricter = data["stricter"]
    W, H, L = 560, 196, 0
    width = W - L
    s = SVG("verge-lab", W, H,
            "Outcomes for 1,200 response pairs from UltraFeedback",
            f"With point scores, {data['defended']} pairs are defended and {data['abstained']} "
            f"abstained. Of the defended pairs, {vs['agree']} agree with the dataset's overall "
            f"score, {vs['disagree']} disagree and {vs['overall_tie']} have tied overall scores. "
            f"Assuming judge confidence {stricter['assumed_confidence']}, "
            f"{stricter['defended']} are defended.")

    def bar(top: float, segments: list[tuple[int, str, str, str]]):
        x0 = L
        placed = []
        for count, fill, label, text_cls in segments:
            w = width * count / total
            s.rect(x0, top, w, 28, fill)
            if label:
                s.text(x0 + 8, top + 19, label, text_cls)
            placed.append((x0, w, count))
            x0 += w
        return placed

    s.text(L, 16, f"point scores, {total:,} pairs")
    placed = bar(26, [
        (vs["agree"], "seg ink", f"{vs['agree']} defended, agree with overall score", "on-dark"),
        (vs["disagree"], "seg em", f"{vs['disagree']}", "on-dark"),
        (vs["overall_tie"], "seg muted", f"{vs['overall_tie']}", "on-dark"),
        (data["abstained"], "seg light", f"{data['abstained']} abstained", "strong"),
    ])
    (dx, dw, _), (tx, tw, _) = placed[1], placed[2]
    s.line(dx + dw / 2, 56, dx + dw / 2, 66, "axis")
    s.text(dx + dw / 2, 80, "disagree", "em", "middle")
    s.line(tx + tw / 2, 56, tx + tw / 2, 86, "axis")
    s.text(tx + tw / 2, 100, "overall tie", anchor="middle")

    s.text(L, 136, f"assuming judge confidence {stricter['assumed_confidence']}, "
                   f"uncertainty penalty {stricter['uncertainty_scale']}")
    bar(146, [
        (stricter["defended"], "seg ink", f"{stricter['defended']} defended", "on-dark"),
        (stricter["abstained"], "seg light", f"{stricter['abstained']} abstained", "strong"),
    ])
    return s.render()


FIGURES = {
    "branchpilot": branchpilot,
    "faultline": faultline,
    "heliostune": heliostune,
    "verge-lab": verge_lab,
}


def main() -> None:
    pages = [ROOT / "index.html", *sorted((ROOT / "projects").glob("*/index.html"))]
    for page in pages:
        if not page.exists():
            continue
        source = page.read_text()
        used = []

        def replace(match: re.Match) -> str:
            name = match.group(2)
            if name not in FIGURES:
                raise SystemExit(f"{page.relative_to(ROOT)}: unknown figure {name!r}")
            used.append(name)
            return match.group(1) + FIGURES[name]() + match.group(4)

        updated = MARKER.sub(replace, source)
        if updated != source:
            page.write_text(updated)
        if used:
            print(f"{page.relative_to(ROOT)}: {', '.join(used)}")


if __name__ == "__main__":
    main()
