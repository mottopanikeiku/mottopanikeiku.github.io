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
    "attention-numerics": ("attention-numerics", "54fd549b3d8d7f0b0fb1a82032143952e8b4d72c",
                           "results/v2/summary.json"),
    "branchpilot": ("branchpilot", "6f2ff8654aec07e806c3fcfea4f5e2514c36928d",
                    "benchmarks/gsm8k-sampling-bootstrap.json"),
    "control-clock": ("control-clock", "ee9c303de8e7698ca25569fc585e173e3e172bb8",
                      "results/summary.json"),
    "cpu-decode": ("cpu-decode", "d98ba9c9ac792f01a0969c861917e730533c88d0",
                   "results/summary.json"),
    "eval-power": ("eval-power", "ef7c451d678e7eece94344b0c87567a60e28e330",
                   "results/calibration.csv"),
    "faultline": ("faultline", "d8dcf021e434d64adf06659ff0e1e0d61b70acf0",
                  "artifacts/results/small-kill-v1-analysis.json"),
    "heliostune": ("heliostune", "d1f5ab6fb6ff8b1862baf635dc8abd9241052809",
                   "benchmarks/results/parhelion-h100-final.json"),
    "verge-lab": ("verge-lab", "efa08d133f22501b2dedcb7a7aa636bf37bbc826",
                  "results/public-preferences/summary.json"),
    "seed-power": ("seed-power", "71ce487eac1eafc9481eec7427ea83340e23569a",
                   "results/summary.json"),
    "verge-human": ("verge-lab", "efa08d133f22501b2dedcb7a7aa636bf37bbc826",
                    "results/human-preferences/summary.json"),
    "control-clock-gpu": ("control-clock", "b090dad8a3b53f937782676c6033ba3557cedfa1",
                          "results/gpu/summary.json"),
    "control-clock-cost": ("control-clock", "b090dad8a3b53f937782676c6033ba3557cedfa1",
                           "results/gpu/cost.json"),
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


def attention_numerics(raw: dict) -> dict:
    names = {"qwen05": "Qwen2.5-0.5B", "qwen15": "Qwen2.5-1.5B", "smol036": "SmolLM2-360M",
             "smol17": "SmolLM2-1.7B", "tiny11": "TinyLlama-1.1B", "olmo1": "OLMo-2-1B"}
    return {
        "models": [
            {
                "key": key,
                "name": names.get(key, key),
                "tokens": model["variants"]["bf16"]["tokens"],
                "perplexity_increase": {
                    variant: values["exp_ce_relative_change_from_bf16"]
                    for variant, values in model["variants"].items()
                },
            }
            for key, model in raw["downstream"].items()
        ],
    }


def control_clock(raw: dict) -> dict:
    cohorts = []
    for key, cohort in raw.items():
        task, method, variant = key.split("/")
        cohorts.append({
            "task": task,
            "method": method,
            "variant": variant,
            "seeds": cohort["seeds"],
            "successes": cohort["successes"],
            "median": cohort["conditional_median_seconds"],
            "q25": cohort["conditional_q25_seconds"],
            "q75": cohort["conditional_q75_seconds"],
            "limit": max(cohort["limit_seconds"]),
            "records": cohort["records"],
        })
    return {"cohorts": cohorts}


def cpu_decode(raw: dict) -> dict:
    return {
        "points": [
            {
                "threads": r["threads"],
                "context": r["context"],
                "engine": r["engine_tps"]["median"],
                "engine_min": r["engine_tps"]["min"],
                "engine_max": r["engine_tps"]["max"],
                "llama": r["llama_tps"]["median"],
                "eager": r["eager_tps"]["median"],
                "ceiling": r["bandwidth_ceiling_tps"],
                "percent_of_ceiling": r["percent_of_ceiling"],
            }
            for r in raw["results"]
        ],
    }


def seed_power(raw: dict) -> dict:
    def row(name: str, values: dict) -> dict:
        return {
            "name": name,
            "plans": values["plans"],
            "detections": values["detections"],
            "rate": values["detection_rate"],
            "ci": [values["wilson_95_low"], values["wilson_95_high"]],
        }
    return {
        "target_power": raw["target_power"],
        "fresh_seeds": raw["training_seeds_confirmation"],
        "attempted_plans": raw["attempted_nonnull_plans"],
        "over_budget": raw["nonnull_status_counts"]["over_budget"],
        "rows": [row("All executable plans", raw["nonnull"]),
                 *(row(task.removesuffix("-v1"), values)
                   for task, values in raw["per_task"].items())],
    }


def verge_human(raw: dict) -> dict:
    result = raw["configurations"]["correctness_coherence"]["validation"]["matched"]
    return {
        "yield": result["yield_pairs_each"],
        "rows": [
            {"name": name, "agree": result[key]["agree"],
             "strict_pairs": result[key]["strict_human_pairs"],
             "human_ties": result[key]["human_tie"],
             "rate": result[key]["strict_agreement"],
             "ci": result[key]["wilson_95"]}
            for key, name in (("pareto", "Pareto selection"),
                              ("helpfulness_gap", "Overall-score gap"))
        ],
    }


def control_clock_gpu(raw: dict) -> dict:
    return {"hardware": raw["hardware"], "protocol": raw["protocol"],
            "groups": [{key: group[key] for key in ("task", "runs", "solved", "median_seconds")}
                       for group in raw["groups"]]}


def control_clock_cost(raw: dict) -> dict:
    return {key: raw[key] for key in ("hardware", "total_all_in_cost_estimate_usd", "method")}


TRANSFORMS = {
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
    "control-clock-gpu": control_clock_gpu,
    "control-clock-cost": control_clock_cost,
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
