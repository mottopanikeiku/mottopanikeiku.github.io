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
    "attention-numerics": ("attention-numerics", "911d642a5aab42f7ced2bcc7c9f13995cdeb8eb0",
                           "results/hardware/summary.json"),
    "branchpilot": ("branchpilot", "6f2ff8654aec07e806c3fcfea4f5e2514c36928d",
                    "benchmarks/gsm8k-sampling-bootstrap.json"),
    "control-clock": ("control-clock", "ee9c303de8e7698ca25569fc585e173e3e172bb8",
                      "results/summary.json"),
    "cpu-decode": ("cpu-decode", "d98ba9c9ac792f01a0969c861917e730533c88d0",
                   "results/summary.json"),
    "eval-power": ("eval-power", "ef7c451d678e7eece94344b0c87567a60e28e330",
                   "results/calibration.csv"),
    "faultline": ("faultline", "ac6ed689866de6cff18b51fc29fa1ab3c2cf2d50",
                  "artifacts/results/seed-confirmation-analysis.json"),
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
    "quantile-sampled": ("quantile-cycles", "bc0fbc5218be69f0e88acf6ff200d199cdfb4aab",
                         "results/sampled-summary.json"),
    "branchpilot-math": ("branchpilot", "1dfa8dea2c5e201b171102aadd9bf3e8883136c5",
                         "benchmarks/math500/result.json"),
    "alignmenttax": ("alignmenttax", "e8d788bc9da81833739868b407dd138e769eeff9",
                     "results/cross_family/analysis/summary.json"),
    "helios-audit": ("heliostune", "75f18ed8ee2d93e2d58935e3d5599ae95a32a46d",
                    "results/action-set-audit.json"),
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
        }
    paired = {
        name: {"estimate": p["estimate"], "ci": [p["lower"], p["upper"]]}
        for name, p in raw["paired_comparisons"].items()
    }
    protocol = raw["protocol"]
    return {"arms": arms, "paired": paired, "decision": raw["decision"],
            "seed_count": len(protocol["training_seeds"]),
            "seed_range": [protocol["training_seeds"][0], protocol["training_seeds"][-1]],
            "bootstrap_resamples": protocol["bootstrap_resamples"],
            "training_steps": protocol["training_decision_steps"],
            "evaluation_split": protocol["evaluation_split"],
            "evaluation_base_pairs": protocol["evaluation_base_pair_count"]}


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
    names = {"qwen15": "Qwen2.5-1.5B", "qwen05": "Qwen2.5-0.5B"}
    return {
        "definition": raw["definitions"]["downstream"],
        "models": [
            {"key": key, "name": name,
             "tokens": raw["downstream_fa3"][key]["bf16"]["tokens"],
             "bf16_ce": raw["downstream_fa3"][key]["bf16"]["next_token_ce"],
             "ratios": {variant: values["exp_ce_ratio"]
                        for variant, values in raw["downstream_fa3"][key].items()}}
            for key, name in names.items()
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


def quantile_sampled(raw: dict) -> dict:
    gate = raw["network_gate"]
    return {
        "endpoint": raw["endpoint"],
        "bootstrap": raw["bootstrap"],
        "material_failure_found": gate["pass"],
        "minimum_excess_regret": gate["rule"]["minimum_normalized_excess_regret"],
        "comparisons": [
            {"case": row["case"], "schedule": row["schedule"],
             "excess": row["sampled_normalized_excess"],
             "ci": row["sampled_excess_ci95"], "pass": row["pass"]}
            for row in gate["cells"]
        ],
        "rows": [
            {"case": row["case"], "method": row["method"], "schedule": row["schedule"],
             "seeds": row["seeds"], "regret": row["normalized_regret_mean"],
             "ci": row["normalized_regret_ci95"]}
            for row in raw["sampled_cells"]
            if row["case"] in ("family-8", "family-32")
            and row["method"] in ("huber", "scalar")
        ],
    }


def branchpilot_math(raw: dict) -> dict:
    test = raw["test"]
    costs = sorted(float(cost) for cost in raw["decision"]["utility_interval_lower_bounds"])
    return {
        "prompts": test["records"],
        "max_samples": test["max_samples"],
        "success": raw["decision"]["success"],
        "comparisons": [
            {"cost": row["scoring_cost"], "baseline": row["baseline_policy"],
             "utility_delta": row["utility_delta"],
             "ci": interval(row["utility_delta_interval"])}
            for row in test["comparisons"] if row["scoring_cost"] in costs
        ],
        "illustration_cost": costs[0],
        "rows": [
            {"policy": row["policy"], "accuracy": row["accuracy"],
             "samples": row["average_samples"]}
            for row in test["rows"] if row["scoring_cost"] == costs[0]
            and (row["family"] == "offline-rl"
                 or row["policy"] in ("fixed-1", "fixed-8", "agreement-2"))
        ],
    }


def alignmenttax(raw: dict) -> dict:
    names = {
        "qwen2_5_0_5b": "Qwen2.5-0.5B",
        "qwen2_5_1_5b": "Qwen2.5-1.5B",
        "qwen2_5_7b": "Qwen2.5-7B",
        "olmo2_0425_1b": "OLMo-2 1B (0425)",
        "olmo2_1124_7b": "OLMo-2 7B (1124)",
        "smollm2_1_7b": "SmolLM2-1.7B",
        "mistral_7b_v0_3": "Mistral-7B-v0.3",
    }
    by_id = {pair["pair_id"]: pair for pair in raw["pairs"]}
    rows = []
    for key, name in names.items():
        primary = by_id[key]["protocols"]["shared_plain_ab_label"]
        metrics = primary["deltas"]["metrics"]
        rows.append({
            "key": key, "name": name,
            "classification": primary["classification"]["outcome"],
            **{metric: {"delta": metrics[metric]["point"],
                        "ci": [metrics[metric]["ci_low"], metrics[metric]["ci_high"]]}
               for metric in ("accuracy", "ece")},
        })
    return {"questions": raw["question_count"], "pairs": raw["pair_count"],
            "resamples": raw["iterations"], "ece": raw["ece"],
            "protocol": "shared_plain_ab_label", "rows": rows}


def helios_audit(raw: dict) -> dict:
    return {
        "kind": raw["analysis_kind"], "configs": raw["configs"],
        "overall": raw["overall"],
        "by_m": [
            {"m": row["m"], "workloads": row["workloads"],
             "torch_wins": row["torch_wins_reference"],
             "ratio": row["reference_over_torch_geomean"],
             "saved_us": row["torch_saved_us_median"]}
            for row in raw["by_m"]
        ],
        "by_gpu": [
            {"gpu": row["gpu"], "workloads": row["workloads"],
             "torch_wins": row["torch_wins_reference"],
             "ratio": row["reference_over_torch_geomean"]}
            for row in raw["by_gpu"]
        ],
    }


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
    "quantile-sampled": quantile_sampled,
    "branchpilot-math": branchpilot_math,
    "alignmenttax": alignmenttax,
    "helios-audit": helios_audit,
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
