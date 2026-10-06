"""Pull the numbers behind the site's figures from pinned commits.

    python3 tools/extract_data.py

Each file in data/ records the repository, commit and path it came from.
Change a commit below to update a figure, then run tools/figures.py.
"""

import csv
import io
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OWNER = "mottopanikeiku"

SOURCES = {
    "branchpilot": ("branchpilot", "6f2ff8654aec07e806c3fcfea4f5e2514c36928d",
                    "benchmarks/gsm8k-sampling-bootstrap.json"),
    "eval-power": ("eval-power", "ef7c451d678e7eece94344b0c87567a60e28e330",
                   "results/calibration.csv"),
    "faultline": ("faultline", "d8dcf021e434d64adf06659ff0e1e0d61b70acf0",
                  "artifacts/results/small-kill-v1-analysis.json"),
    "heliostune": ("heliostune", "d1f5ab6fb6ff8b1862baf635dc8abd9241052809",
                   "benchmarks/results/parhelion-h100-final.json"),
    "verge-lab": ("verge-lab", "0e42e8ca557e38e91863cc8b64ba8dd64be6009a",
                  "results/public-preferences/summary.json"),
}


def fetch(repo: str, commit: str, path: str):
    url = f"https://raw.githubusercontent.com/{OWNER}/{repo}/{commit}/{path}"
    with urllib.request.urlopen(url, timeout=60) as response:
        body = response.read().decode()
    if path.endswith(".csv"):
        return list(csv.DictReader(io.StringIO(body)))
    return json.loads(body)


def source(repo: str, commit: str, path: str) -> dict:
    return {
        "repo": f"{OWNER}/{repo}",
        "commit": commit,
        "path": path,
        "url": f"https://github.com/{OWNER}/{repo}/blob/{commit}/{path}",
    }


def interval(value: dict) -> list[float]:
    return [value["lower"], value["upper"]]


def branchpilot(raw: dict) -> dict:
    test = raw["splits"]["test"]
    rows = [
        {
            "policy": row["policy"],
            "family": row["family"],
            "accuracy": row["accuracy"],
            "accuracy_ci": interval(row["accuracy_interval"]),
            "samples": row["average_samples"],
            "samples_ci": interval(row["average_samples_interval"]),
        }
        for row in test["rows"]
    ]
    paired = [
        {
            "cost": item["cost"],
            "learned": item["learned"],
            "baseline": item["baseline"],
            "utility_delta": item["utility_delta"],
            "utility_delta_ci": interval(item["utility_delta_interval"]),
        }
        for item in test["paired_comparisons"]
    ]
    return {"prompts": test["prompts"], "rows": rows, "paired": paired}


def faultline(raw: dict) -> dict:
    arms = {}
    for name, arm in raw["arms"].items():
        primary = arm["primary"]
        arms[name] = {
            "mean": primary["estimate"],
            "ci": [primary["lower"], primary["upper"]],
            "seeds": {str(s["seed"]): s["value"] for s in arm["individual_seeds"]},
        }
    paired = {
        name: {"estimate": p["estimate"], "ci": [p["lower"], p["upper"]]}
        for name, p in raw["paired_comparisons"].items()
    }
    return {"arms": arms, "paired": paired, "decision": raw["decision"]}


def heliostune(raw: dict) -> dict:
    methods = {}
    for key, points in raw["methods"].items():
        methods[key] = {
            "label": raw["method_labels"].get(key, key),
            "points": [
                {
                    "budget": p["budget"],
                    "mean": p["mean_fraction_oracle"],
                    "ci": [p["ci95_low"], p["ci95_high"]],
                }
                for p in sorted(points, key=lambda p: p["budget"])
            ],
        }
    return {"auc": raw["auc"], "methods": methods}


def verge_lab(raw: dict) -> dict:
    base = raw["baseline"]
    stricter = next(
        (s for s in raw["sensitivity"] if s.get("assumed_confidence") == 0.9
         and s.get("uncertainty_scale") == 0.05),
        None,
    )
    return {
        "prompts": raw["prompt_count"],
        "responses": raw["candidate_count"],
        "pairs": base["all_pairs"],
        "defended": base["defended"],
        "abstained": base["abstained"],
        "abstention_reasons": base["abstention_reasons"],
        "defended_vs_overall": base["defended_vs_overall"],
        "disagreement_fraction": base["disagreement_fraction_of_comparable_defended"],
        "stricter": None if stricter is None else {
            "assumed_confidence": stricter["assumed_confidence"],
            "uncertainty_scale": stricter["uncertainty_scale"],
            "defended": stricter["defended"],
            "abstained": stricter["abstained"],
        },
    }


def eval_power(rows: list[dict]) -> dict:
    names = {"arc": "ARC-Challenge", "gsm8k": "GSM8K", "winogrande": "WinoGrande",
             "hellaswag": "HellaSwag", "mmlu": "MMLU"}
    return {
        "target_power": 0.8,
        "benchmarks": [
            {
                "key": row["benchmark"],
                "name": names.get(row["benchmark"], row["benchmark"]),
                "pilot_items": int(row["pilot_n"]),
                "median": float(row["iid_power_median"]),
                "q25": float(row["iid_power_q25"]),
                "q75": float(row["iid_power_q75"]),
                "below_target": float(row["iid_below_target_95mc_fraction"]),
            }
            for row in rows
        ],
    }


TRANSFORMS = {
    "branchpilot": branchpilot,
    "eval-power": eval_power,
    "faultline": faultline,
    "heliostune": heliostune,
    "verge-lab": verge_lab,
}


def main() -> None:
    out_dir = ROOT / "data"
    out_dir.mkdir(exist_ok=True)
    for name, (repo, commit, path) in SOURCES.items():
        data = TRANSFORMS[name](fetch(repo, commit, path))
        data = {"source": source(repo, commit, path), **data}
        target = out_dir / f"{name}.json"
        target.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        print(f"{target.relative_to(ROOT)}: {target.stat().st_size} bytes")


if __name__ == "__main__":
    main()
