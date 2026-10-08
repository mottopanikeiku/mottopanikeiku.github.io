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
    rows = (("random", "Random (50/50 mix)"), ("difficulty", "Difficulty-adaptive"),
            ("epistemic", "All ambiguous"))
    desc = "; ".join(f'{label}: {data["arms"][key]["mean"] * 100:.1f}%'
                     for key, label in rows)
    s = SVG("faultline", 560, 258,
            f'Diagnostic success in the independent {data["seed_count"]}-seed confirmation',
            f'{data["seed_count"]} matched training seeds per curriculum. Means: {desc}. '
            "Bars are separate 95% bootstrap intervals over training seeds. Ambiguous-only "
            "training beats random sampling but loses to difficulty-adaptive sampling.")
    L, R, top, bottom = 174, 16, 52, 200
    x = scale(0, 1, L, 560 - R)
    s.text(0, 18, f'{data["seed_count"]} matched seeds; 95% seed-bootstrap intervals')
    for value in (0, 0.25, 0.5, 0.75, 1):
        s.line(x(value), top, x(value), bottom, "grid")
        s.text(x(value), bottom + 21, f"{value * 100:.0f}%", anchor="middle")
    for index, (key, label) in enumerate(rows):
        row = data["arms"][key]
        y = 68 + index * 50
        cls = "em" if key == "epistemic" else "strong"
        s.text(L - 12, y + 4, label, anchor="end")
        s.line(x(row["ci"][0]), y, x(row["ci"][1]), y, f"ci {cls}")
        s.circle(x(row["mean"]), y, 4, f"dot {cls}")
        s.text(x(row["mean"]), y + 21, f'{row["mean"] * 100:.1f}%', cls, "middle")
    s.text((L + 560 - R) / 2, 252, "diagnostic success on validation pairs", anchor="middle")
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
            "Score is bank-1-selected curated-reference latency divided by selected latency; "
            "higher is better, not a fraction of a hardware ceiling. Cold-start Thompson "
            "sampling and Parhelion both reach 0.997 by eight "
            f"probes; reuse and retrieval baselines stay lower. torch.matmul scores {torch:.2f} on "
            "the same scale, off the top of the chart.")
    for i, (key, cls, label) in enumerate(series):
        lx = L + (i % 2) * 250
        ly = 18 + (i // 2) * 20
        s.line(lx, ly - 4, lx + 22, ly - 4, cls)
        s.text(lx + 30, ly, label, "em" if "em" in cls else ("strong" if "strong" in cls else ""))
    s.text(W - R, 70, f"torch.matmul: {torch:.2f} \u2191", "strong", "end")
    s.text(L - 8, T - 12, "curated-reference latency / selected latency")
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
    variants = (("tile", "unrotated"), ("rotate", "rotate Q/K"),
                ("smooth_k", "center K"), ("rotate_smooth_k", "rotate + center K"))
    s = SVG("attention-numerics", 560, 352,
            "FA3 batch exp-CE ratio versus native GPU BF16 in both Qwen models",
            "Real FA3 E4M3 attention in every layer on H100, log scale. Qwen2.5-1.5B: "
            "unrotated 4.808, rotated 12.560, center K 1.014, rotate plus center K 1.004. "
            "Qwen2.5-0.5B: 1.071, 2.032, 1.018 and 1.056 respectively. Each uses 3,072 "
            "held-out next-token labels. This is batch teacher forcing, not streaming perplexity.")
    L, R = 168, 64
    x = lambda ratio: L + math.log2(ratio) / 4 * (560 - R - L)
    s.text(0, 18, "FA3 E4M3 · H100 · all layers · 3,072 labels/model")
    for value in (1, 2, 4, 8, 16):
        s.line(x(value), 50, x(value), 296, "axis" if value == 1 else "grid")
        s.text(x(value), 324, f"{value}×", anchor="middle")
    for index, model in enumerate(data["models"]):
        top = 64 + index * 143
        s.text(0, top - 22, model["name"], "strong")
        for row, (key, label) in enumerate(variants):
            y = top + row * 26
            ratio = model["ratios"][key]
            cls = "em" if key == "rotate" else "strong"
            s.text(L - 12, y + 4, label, anchor="end")
            s.circle(x(ratio), y, 3.7, f"dot {cls}")
            s.text(x(ratio) + 9, y + 4, f"{ratio:.3f}×", cls)
    s.text((L + 560 - R) / 2, 347, "exp(CE variant − CE BF16), log scale", anchor="middle")
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


def detection_rates(name: str, title: str, desc: str) -> str:
    data = load(name)
    s = SVG(name, 560, 250, title, desc)
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


def seed_power() -> str:
    return detection_rates(
        "seed-power",
        "Detection rates of fresh-seed RL studies planned for 80% power",
        "All executable plans detected 67 of 119 differences, 56.3%. CartPole detected "
        "30 of 60, 50.0%; Acrobot detected 37 of 59, 62.7%. Bars are Wilson 95% intervals. "
        "The dashed line is the 80% planning target.")


def seed_power_neural() -> str:
    return detection_rates(
        "seed-power-neural",
        "Detection rates of fresh-seed neural PPO studies planned for 80% power",
        "All executable plans detected 139 of 307 differences, 45.3%. CartPole detected "
        "109 of 175, 62.3%; Acrobot detected 30 of 132, 22.7%. Bars are Wilson 95% intervals. "
        "The dashed line is the 80% planning target.")


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


def verge_dpo() -> str:
    data = load("verge-dpo")
    diff = data["pareto_minus_gap"]
    s = SVG("verge-dpo", 560, 304,
            "DPO on Pareto pairs versus helpfulness-gap pairs: no clear difference",
            "Mean reward-model logit on 192 held-out HelpSteer2 prompts: untrained start 0.550, "
            "Pareto 0.620, helpfulness gap 0.731, human reference 0.651, each trained row over "
            "three seeds. Pareto minus gap is -0.112 with a crossed prompt and seed bootstrap "
            "95% interval of -0.257 to +0.032; seed means are -0.027, -0.118 and -0.190.")
    s.text(0, 18, f'mean reward-model logit; {data["prompts"]} held-out prompts × '
                  f'{len(data["seeds"])} seeds')
    x = scale(0.5, 0.8, 170, 544)
    for value in (0.5, 0.6, 0.7, 0.8):
        s.line(x(value), 34, x(value), 150, "grid")
        s.text(x(value), 168, f"{value:.1f}", anchor="middle")
    styles = {"start": "", "pareto": "em", "gap": "strong", "human": "strong"}
    for index, row in enumerate(data["conditions"]):
        y = 50 + index * 28
        cls = styles[row["key"]]
        s.text(158, y + 4, row["name"], cls, "end")
        s.circle(x(row["mean_reward"]), y, 4, f"dot {cls}".strip())
        s.text(x(row["mean_reward"]) + 10, y + 4, f'{row["mean_reward"]:.3f}', cls)
    s.text(0, 200, "Pareto − gap; crossed prompt/seed bootstrap 95% interval")
    x = scale(-0.3, 0.1, 170, 544)
    for value in (-0.3, -0.2, -0.1, 0, 0.1):
        s.line(x(value), 214, x(value), 262, "axis" if value == 0 else "grid")
        s.text(x(value), 280, f"{value:+.1f}" if value else "0", anchor="middle")
    s.text(158, 232, "Pareto − gap", "em", "end")
    s.line(x(diff["ci"][0]), 228, x(diff["ci"][1]), 228, "ci em")
    s.circle(x(diff["mean"]), 228, 4, "dot em")
    s.text(158, 254, "seed means", anchor="end")
    for value in diff["per_seed"]:
        s.circle(x(value), 250, 3.2, "dot hollow strong")
    s.text(357, 300, "reward difference (logit)", anchor="middle")
    return s.render()


def quantile_sampled() -> str:
    data = load("quantile-sampled")
    s = SVG("quantile-sampled", 560, 284,
            "Sampled Huber regret minus scalar regret in four specified comparisons",
            "All four comparisons fail the material-failure rule. At K=8, both schedules "
            "have zero observed excess regret. At K=32, excess is -0.0740 with constant "
            "steps and -0.0023 with decaying steps. Bars are paired-seed 95% bootstrap "
            "intervals. Regret is normalized by the loss of always choosing the bad action.")
    x = scale(-0.1, 0.3, 178, 544)
    for value in (-0.1, 0, 0.1, 0.2, 0.3):
        s.line(x(value), 42, x(value), 224, "grid")
        s.text(x(value), 247, f"{value:.1f}", anchor="middle")
    s.line(x(0), 42, x(0), 224, "axis")
    threshold = data["minimum_excess_regret"]
    s.line(x(threshold), 42, x(threshold), 224, "line dash")
    s.text(544, 18, f"material-failure threshold: {threshold:g}", "strong", "end")
    for index, row in enumerate(data["comparisons"]):
        y = 64 + index * 48
        k = row["case"].removeprefix("family-")
        s.text(166, y + 4, f'K={k}, {row["schedule"]}', anchor="end")
        s.line(x(row["ci"][0]), y, x(row["ci"][1]), y, "ci em")
        s.circle(x(row["excess"]), y, 3.5, "dot em")
        s.text(x(row["excess"]), y + 20, f'{row["excess"]:.4f}', "em", "middle")
    s.text(361, 277, "normalized regret difference: Huber − scalar", anchor="middle")
    return s.render()


def branchpilot_math() -> str:
    data = load("branchpilot-math")
    s = SVG("branchpilot-math", 560, 228,
            "Learned stopping loses utility on an internal 200-problem MATH-500 holdout",
            "At sample penalties 0.05, 0.075 and 0.10, learned-minus-comparator utility "
            "is -0.0825, -0.1048 and -0.0955. All paired 95% intervals lie below zero. "
            "Validation selected the fixed-one comparator at all three penalties.")
    x = scale(-0.16, 0.02, 114, 544)
    s.text(114, 18, "utility = accuracy − cost × (samples − 1)")
    for value in (-0.15, -0.1, -0.05, 0):
        s.line(x(value), 38, x(value), 176, "grid")
        s.text(x(value), 200, f"{value:.2f}", anchor="middle")
    s.line(x(0), 38, x(0), 176, "axis")
    for index, row in enumerate(data["comparisons"]):
        y = 61 + index * 48
        s.text(102, y + 4, f'cost {row["cost"]:g}', anchor="end")
        s.line(x(row["ci"][0]), y, x(row["ci"][1]), y, "ci em")
        s.circle(x(row["utility_delta"]), y, 3.5, "dot em")
        s.text(x(row["utility_delta"]), y + 20,
               f'{row["utility_delta"]:.4f}', "em", "middle")
    s.text(329, 224, "paired utility difference: learned − fixed one", anchor="middle")
    return s.render()


def alignmenttax() -> str:
    data = load("alignmenttax")
    s = SVG("alignmenttax", 560, 356,
            "Instruction tuning worsens binary-derivative ECE but not standard MC1 ECE",
            "Expected calibration error change, instruct minus base, for nine pairs under shared "
            "prompts. On the 790-question binary derivative, six pairs gain accuracy while ECE "
            "worsens and two lose accuracy while ECE worsens; Qwen2.5-0.5B is uncertain. On "
            "817-question standard MC1, four pairs improve both accuracy and ECE and five are "
            "uncertain. Bars are separate 95% question-bootstrap intervals.")
    styles = {
        "truth_gain_ece_worse": ("dot em", "ci em", "accuracy up, ECE worse"),
        "truth_and_calibration_improve": ("dot strong", "ci strong", "both better"),
        "truth_and_calibration_worsen": ("dot hollow em", "ci em", "both worse"),
        "uncertain": ("dot", "ci", "uncertain"),
    }
    for index, (dot, _, label) in enumerate(styles.values()):
        lx = (0, 168, 272, 376)[index]
        s.circle(lx + 4, 14, 3.4, dot)
        s.text(lx + 13, 18, label)
    s.text(0, 42, "ECE change (points), instruct − base; higher is worse; 95% intervals")
    top, bottom, label_right = 82, 298, 112
    panels = (("binary", "Binary A/B derivative", scale(-6, 36, 126, 330), (0, 10, 20, 30)),
              ("standard", "Standard MC1", scale(-10, 4, 360, 544), (-10, -5, 0)))
    for benchmark, title, x, ticks in panels:
        s.text((x(ticks[0]) + x(ticks[-1])) / 2, 70,
               f'{title} ({data["questions"][benchmark]})', "strong", "middle")
        for value in ticks:
            s.line(x(value), top, x(value), bottom, "axis" if value == 0 else "grid")
            s.text(x(value), bottom + 20, str(value), anchor="middle")
    for index, row in enumerate(data["rows"]):
        y = top + 12 + index * 24
        s.text(label_right, y + 4, row["name"], anchor="end")
        for benchmark, _, x, _ in panels:
            ece = row[benchmark]["ece"]
            dot, ci, _ = styles[row[benchmark]["classification"]]
            s.line(x(ece["ci"][0] * 100), y, x(ece["ci"][1] * 100), y, ci)
            s.circle(x(ece["delta"] * 100), y, 3.4, dot)
    s.text(335, 346, "shared prompts; separate scales per panel", anchor="middle")
    return s.render()


def helios_audit() -> str:
    data = load("helios-audit")
    s = SVG("helios-audit", 560, 280,
            "Stored H100 reference-to-torch latency ratios by matrix row count",
            "In each of six row-count groups, torch.matmul has lower stored median latency "
            "than the bank-1-selected Triton reference on all 16 workloads. Geometric-mean "
            "reference-to-torch ratios range from 1.404 to 1.680. These are old measurements "
            "reanalyzed, without uncertainty estimates or new timings.")
    L, R, top, bottom = 70, 16, 52, 212
    y = scale(0.95, 1.8, bottom, top)
    x = scale(0, 5, L, 560 - R)
    s.text(0, 18, "reference latency / torch latency; higher favors torch")
    s.text(0, 38, "stored H100 medians; 16 torch wins / 16 workloads per group")
    for value in (1, 1.2, 1.4, 1.6, 1.8):
        s.line(L, y(value), 560 - R, y(value), "axis" if value == 1 else "grid")
        s.text(L - 8, y(value) + 4, f"{value:.1f}×", anchor="end")
    for index, row in enumerate(data["by_m"]):
        px, py = x(index), y(row["ratio"])
        s.circle(px, py, 4, "dot em")
        s.text(px, py - 12, f'{row["ratio"]:.3f}×', "em", "middle")
        s.text(px, bottom + 20, str(row["m"]), anchor="middle")
    s.text((L + 560 - R) / 2, 274, "M in A[M,K] × B[K,N]; geometric-mean ratio", anchor="middle")
    return s.render()


def helios_expansion() -> str:
    data = load("helios-expansion")
    s = SVG("helios-expansion", 560, 300,
            "Ten new Triton actions narrow, but rarely close, the H100 gap to torch.matmul",
            "Geometric-mean bank-2 latency relative to torch by row count M, 16 workloads per "
            "group. The old 36 actions range from 1.401 to 1.676 times torch. With the new "
            "actions selected on bank 1, ratios range from 1.045 at M=1 to 1.378 at M=96. New "
            "actions beat torch on 5, 3, 0, 1, 0 and 0 workloads and tie on one.")
    L, R, top, bottom = 70, 16, 56, 222
    y = scale(0.95, 1.8, bottom, top)
    x = scale(0, 5, L + 20, 560 - R - 30)
    s.text(0, 18, "bank-2 latency / torch latency; below 1 favors Triton")
    s.circle(4, 34, 3.6, "dot strong")
    s.text(13, 38, f'old {data["action_counts"]["old"]} actions', "strong")
    s.circle(124, 34, 3.6, "dot em")
    s.text(133, 38, f'new {data["action_counts"]["new"]} actions, selected on bank 1', "em")
    for value in (1, 1.2, 1.4, 1.6, 1.8):
        s.line(L, y(value), 560 - R, y(value), "axis" if value == 1 else "grid")
        s.text(L - 8, y(value) + 4, f"{value:.1f}×", anchor="end")
    s.text(L - 8, 262, "wins", anchor="end")
    for index, row in enumerate(data["by_m"]):
        old, new = row["arms"]["old"], row["arms"]["new"]
        px = x(index)
        s.line(px, y(old["ratio"]), px, y(new["ratio"]), "line faint")
        s.circle(px, y(old["ratio"]), 4, "dot strong")
        s.circle(px, y(new["ratio"]), 4, "dot em")
        s.text(px + 8, y(new["ratio"]) + 4, f'{new["ratio"]:.2f}×', "em")
        s.text(px, bottom + 20, str(row["m"]), anchor="middle")
        s.text(px, 262, f'{new["wins"]}/{row["workloads"]}', "em", "middle")
    s.text((L + 560 - R) / 2, 292, "M in A[M,K] × B[K,N]; new-action wins against torch",
           anchor="middle")
    return s.render()


def eval_prospective() -> str:
    data = load("eval-prospective")
    s = SVG("eval-prospective", 560, 250,
            "Decoding-noise share differs sharply between GSM8K and direct-choice ARC",
            "Estimated decoding contribution to paired item-mean variance with five stochastic "
            "answers per question. Fifteen model pairs per benchmark; median share is 33.2% "
            "on GSM8K and 4.6% on guided direct-choice ARC. These finite-pilot estimates are "
            "descriptive, not known population variance components.")
    L, R, top, bottom = 170, 20, 48, 184
    x = scale(0, 0.65, L, 560 - R)
    s.text(0, 18, "five stochastic answers/question; 15 model pairs/benchmark")
    s.text(0, 38, "small dots: pairs; large dots: median")
    for value in (0, 0.2, 0.4, 0.6):
        s.line(x(value), top, x(value), bottom, "grid")
        s.text(x(value), bottom + 21, f"{value * 100:.0f}%", anchor="middle")
    for index, row in enumerate(data["rows"]):
        y = 72 + index * 64
        s.text(L - 12, y + 4, row["name"], anchor="end")
        for point, share in enumerate(row["shares"]):
            s.circle(x(share), y + (point % 3 - 1) * 4, 2.3, "dot")
        s.circle(x(row["median_share"]), y, 4.3, "dot em")
        s.text(x(row["median_share"]), y + 25, f'{row["median_share"] * 100:.1f}%',
               "em", "middle")
    s.text((L + 560 - R) / 2, 244, "estimated decoding share of total variance at k=5", anchor="middle")
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
    "verge-dpo": verge_dpo,
    "helios-expansion": helios_expansion,
    "quantile-sampled": quantile_sampled,
    "branchpilot-math": branchpilot_math,
    "alignmenttax": alignmenttax,
    "helios-audit": helios_audit,
    "eval-prospective": eval_prospective,
    "seed-power-neural": seed_power_neural,
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
