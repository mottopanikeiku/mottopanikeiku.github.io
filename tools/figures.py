"""Draw the site's figures as inline SVG.

    python3 tools/figures.py

Reads data/*.json (written by tools/extract_data.py) and replaces whatever sits
between <!-- figure:NAME --> and <!-- /figure:NAME --> in the site's HTML.
Colors and type come from site.css, so figures follow light and dark mode.
"""

import html
import json
import math
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


def eval_power() -> str:
    data = load("eval-power")
    target = data["target_power"]
    names = []
    for b in data["benchmarks"]:
        if b["name"] not in names:
            names.append(b["name"])
    rows = {(b["name"], b["pilot_items"]): b for b in data["benchmarks"]}
    W, L, R, T = 560, 112, 24, 70
    band = 46
    H = T + band * len(names) + 52
    x = scale(0, 1, L, W - R)
    s = SVG("eval-power", W, H,
            "Detection rate delivered by pilot-based plans that target 80% power",
            "For each benchmark, plans sized from the gap seen in a 128-item or 256-item pilot "
            "were checked on held-out items. Median detection ranged from 49% to 81%, mostly "
            "below the 80% target, with wide spread between model pairs.")
    s.circle(L + 4, 14, 3.2, "dot em")
    s.text(L + 14, 18, "pilot of 128 items", "em")
    s.circle(L + 164, 14, 3.2, "dot strong")
    s.text(L + 174, 18, "pilot of 256 items", "strong")
    s.text(L, 38, "dots: median over model pairs; bars: middle half")
    bottom = T + band * len(names)
    for v in (0, 0.2, 0.4, 0.6, 0.8, 1.0):
        s.line(x(v), T - 6, x(v), bottom, "grid")
        s.text(x(v), bottom + 18, f"{v * 100:.0f}%", anchor="middle")
    s.line(x(target), T - 12, x(target), bottom, "axis")
    s.text(x(target), T - 16, "80% target", "strong", "middle")
    s.text((L + W - R) / 2, H - 6, "detection rate on held-out items", anchor="middle")
    for i, name in enumerate(names):
        y0 = T + i * band + 6
        s.text(L - 12, y0 + 14, name, anchor="end")
        for j, (size, cls) in enumerate(((128, "em"), (256, "strong"))):
            b = rows.get((name, size))
            if b is None:
                continue
            yy = y0 + 6 + j * 16
            s.line(x(b["q25"]), yy, x(b["q75"]), yy, f"ci {cls}")
            s.circle(x(b["median"]), yy, 3.4, f"dot {cls}")
    return s.render()


def attention_numerics() -> str:
    data = load("attention-numerics")
    models = sorted(data["models"], key=lambda m: -m["perplexity_increase"]["rotate"])
    marks = (("tile", "FP8 per tile", "dot hollow strong"),
             ("rotate", "with rotation", "dot em"),
             ("rotate_smooth_k", "keys centered, then rotated", "dot strong"))
    W, L, R, band, top = 560, 116, 20, 34, 58
    floor, ceiling = 0.05, 1000
    lo, hi = math.log10(floor), math.log10(ceiling)
    x = lambda pct: L + (math.log10(max(pct, floor)) - lo) / (hi - lo) * (W - R - L)
    bottom = top + band * len(models)
    H = bottom + 48
    pct = lambda m, v: 100 * m["perplexity_increase"][v]
    desc = "; ".join(
        f"{m['name']}: per tile {pct(m, 'tile'):.1f}%, rotated {pct(m, 'rotate'):.1f}%, "
        f"centered then rotated {pct(m, 'rotate_smooth_k'):.2f}%" for m in models)
    s = SVG("attention-numerics", W, H,
            "Whole-model perplexity increase with emulated FP8 attention in every layer",
            "Increase over BF16 attention, log scale. " + desc + ".")
    lx = L
    for _, label, cls in marks:
        s.circle(lx + 4, 14, 3.6, cls)
        s.text(lx + 13, 18, label, "em" if "em" in cls else "strong")
        lx += 22 + len(label) * 6.4
    for v in (0.1, 1, 10, 100, 1000):
        s.line(x(v), top - 18, x(v), bottom - 10, "grid")
        s.text(x(v), bottom + 8, f"{v:g}%", anchor="middle")
    for i, m in enumerate(models):
        y = top + i * band
        s.text(L - 12, y + 4, m["name"], anchor="end")
        s.line(x(pct(m, "tile")), y, x(pct(m, "rotate")), y, "ci em")
        for variant, _, cls in marks:
            s.circle(x(pct(m, variant)), y, 4, cls)
    s.text((L + W - R) / 2, H - 6, "increase in perplexity over BF16 attention, log scale",
           anchor="middle")
    return s.render()


def control_clock() -> str:
    data = load("control-clock")
    names = {"ars": "ARS, linear policy", "cem": "CEM, linear policy",
             "ppo-cpu": "batched PPO (this repo)", "sb3-zoo": "SB3 PPO, Zoo settings",
             "cleanrl": "CleanRL PPO"}
    short = {"ars": "ARS", "cem": "CEM", "ppo-cpu": "batched PPO",
             "sb3-zoo": "Stable-Baselines3 PPO", "cleanrl": "CleanRL PPO"}
    tasks = (("CartPole-v1", "CartPole-v1, pass at mean return 475"),
             ("Acrobot-v1", "Acrobot-v1, pass at mean return −100"))
    groups = []
    for task, heading in tasks:
        rows = sorted((c for c in data["cohorts"] if c["task"] == task), key=lambda c: c["median"])
        groups.append((task, heading, rows))
    W, L, R, band = 560, 168, 52, 22
    lo, hi = math.log10(0.3), math.log10(120)
    x = lambda sec: L + (math.log10(sec) - lo) / (hi - lo) * (W - R - L)
    top = 44
    bottom = top + sum(24 + band * len(rows) + 8 for _, _, rows in groups)
    H = bottom + 40
    passed = sum(c["successes"] for c in data["cohorts"])
    runs = sum(c["seeds"] for c in data["cohorts"])
    desc = " ".join(
        f"{task}: " + "; ".join(f"{short[c['method']]} {c['median']:.2f} s" for c in rows) + "."
        for task, _, rows in groups
    ) + f" {passed} of {runs} runs passed."
    s = SVG("control-clock", W, H, "Seconds from process start to a passing policy, per seed",
            "Median seconds by method. " + desc)
    s.text(L, 16, "one dot per seed; the bar is the median")
    s.text(W, 16, "passed", anchor="end")
    ticks = (0.5, 1, 2, 5, 10, 20, 50, 100)
    y = top
    for _, heading, rows in groups:
        s.text(0, y, heading, "strong")
        y += 24
        span = band * len(rows)
        for v in ticks:
            s.line(x(v), y - 14, x(v), y + span - 12, "grid")
        for c in rows:
            cls = "em" if c["method"] == "ppo-cpu" else ""
            s.text(L - 12, y, names[c["method"]], cls, "end")
            for r in c["records"]:
                yy = y - 4 + ((r["seed"] % 5) - 2) * 1.8
                dot = f"dot {cls}" if r["solved"] else f"dot hollow {cls}"
                s.circle(x(r["seconds"]), yy, 2.3, dot.strip())
            s.line(x(c["median"]), y - 12, x(c["median"]), y + 4, "mean")
            s.text(W, y, f"{c['successes']}/{c['seeds']}", anchor="end")
            y += band
        y += 8
    for v in ticks:
        s.text(x(v), bottom + 6, f"{v:g}", anchor="middle")
    s.text((L + W - R) / 2, H - 6, "seconds from process start, log scale", anchor="middle")
    return s.render()


def cpu_decode() -> str:
    data = load("cpu-decode")
    contexts = sorted({p["context"] for p in data["points"]})
    threads = sorted({p["threads"] for p in data["points"]})
    at = {(p["context"], p["threads"]): p for p in data["points"]}
    W, L, T, gap, ph = 560, 34, 76, 18, 190
    pw = (W - L - gap * (len(contexts) - 1) - 4) / len(contexts)
    H = T + ph + 50
    y = scale(0, 90, T + ph, T)
    short, long_ = at[(contexts[0], 2)], at[(contexts[-1], 6)]
    s = SVG("cpu-decode", W, H, "Decoding speed against thread count at three context lengths",
            f"With {contexts[0]} tokens of context and 2 threads, the engine decodes "
            f"{short['engine']:.1f} tokens per second, {short['percent_of_ceiling']:.0f}% of the read "
            f"ceiling, against {short['llama']:.1f} for llama.cpp. With {contexts[-1]:,} tokens and "
            f"6 threads, it decodes {long_['engine']:.1f} against {long_['llama']:.1f}. "
            "Every method slows sharply at 12 threads.")
    legend = (("this engine", "line em", "em"), ("llama.cpp Q8_0", "line strong", "strong"),
              ("PyTorch BF16", "line", ""), ("read ceiling", "line dash", ""))
    lx = L
    for label, line_cls, text_cls in legend:
        s.line(lx, 14, lx + 20, 14, line_cls)
        s.text(lx + 27, 18, label, text_cls)
        lx += 27 + len(label) * 6.6 + 22
    s.text(0, 42, "tokens per second")
    for v in (0, 20, 40, 60, 80):
        s.line(L, y(v), W - 4, y(v), "grid")
        s.text(L - 6, y(v) + 4, f"{v}", anchor="end")
    for i, context in enumerate(contexts):
        x0 = L + i * (pw + gap)
        xs = lambda k, x0=x0: x0 + 10 + k * (pw - 20) / (len(threads) - 1)
        s.text(x0 + pw / 2, T - 10, f"{context:,} tokens of context", "strong", "middle")
        for key, line_cls, dot_cls in (("ceiling", "line dash", None), ("eager", "line", "dot"),
                                       ("llama", "line strong", "dot strong"),
                                       ("engine", "line em", "dot em")):
            points = [(xs(k), y(at[(context, t)][key])) for k, t in enumerate(threads)]
            s.path(points, line_cls)
            if dot_cls:
                for px, py in points:
                    s.circle(px, py, 2.4, dot_cls)
        for k, t in enumerate(threads):
            s.text(xs(k), T + ph + 18, str(t), anchor="middle")
    s.text(L + (W - L) / 2, H - 6, "threads", anchor="middle")
    return s.render()


def seed_power() -> str:
    data = load("seed-power")
    s = SVG("seed-power", 560, 250,
            "Detection rates of fresh-seed RL studies planned for 80% power",
            "All executable plans detected 67 of 119 differences, 56.3%. CartPole detected "
            "30 of 60, 50.0%; Acrobot detected 37 of 59, 62.7%. Bars are Wilson 95% intervals. "
            "The dashed line is the 80% planning target.")
    x = scale(0, 1, 160, 544)
    for value in (0, 0.2, 0.4, 0.6, 0.8, 1):
        s.line(x(value), 42, x(value), 188, "grid")
        s.text(x(value), 211, f"{value * 100:.0f}%", anchor="middle")
    s.line(x(data["target_power"]), 40, x(data["target_power"]), 188, "line dash")
    s.text(x(data["target_power"]), 22, "80% target", "strong", "middle")
    for index, row in enumerate(data["rows"]):
        y = 65 + index * 52
        cls = "em" if index == 0 else "strong"
        s.text(148, y + 4, row["name"], anchor="end")
        s.line(x(row["ci"][0]), y, x(row["ci"][1]), y, f"ci {cls}")
        s.circle(x(row["rate"]), y, 4, f"dot {cls}")
        s.text(x(row["rate"]), y + 22,
               f'{row["detections"]}/{row["plans"]} ({row["rate"] * 100:.1f}%)',
               cls, "middle")
    s.text(352, 243, "detection rate; Wilson 95% intervals", anchor="middle")
    return s.render()


def verge_human() -> str:
    data = load("verge-human")
    s = SVG("verge-human", 560, 220,
            "Agreement with strict human preferences at matched yield",
            "At 310 selected pairs each, Pareto selection agreed with 281 of 286 strict "
            "preferences, 98.25%, and the overall-score-gap baseline with 277 of 282, 98.23%. "
            "Wilson 95% intervals overlap. Human ties are excluded from agreement.")
    x = scale(0.95, 1, 170, 544)
    for value in (0.95, 0.96, 0.97, 0.98, 0.99, 1):
        s.line(x(value), 40, x(value), 158, "grid")
        s.text(x(value), 183, f"{value * 100:.0f}%", anchor="middle")
    for index, row in enumerate(data["rows"]):
        y = 65 + index * 65
        cls = "em" if index == 0 else "strong"
        s.text(158, y + 4, row["name"], anchor="end")
        s.line(x(row["ci"][0]), y, x(row["ci"][1]), y, f"ci {cls}")
        s.circle(x(row["rate"]), y, 4, f"dot {cls}")
        s.text(x(row["rate"]), y + 22,
               f'{row["agree"]}/{row["strict_pairs"]} ({row["rate"] * 100:.2f}%)',
               cls, "middle")
    s.text(357, 212, "strict agreement; Wilson 95% intervals", anchor="middle")
    return s.render()


FIGURES = {
    "attention-numerics": attention_numerics,
    "branchpilot": branchpilot,
    "control-clock": control_clock,
    "cpu-decode": cpu_decode,
    "eval-power": eval_power,
    "faultline": faultline,
    "heliostune": heliostune,
    "verge-lab": verge_lab,
    "seed-power": seed_power,
    "verge-human": verge_human,
}


def main() -> None:
    pages = [ROOT / "index.html", *sorted((ROOT / "projects").glob("*/index.html")),
             ROOT / "tools" / "cards.html"]
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
