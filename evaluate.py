"""Evaluation script: compares app output against manual baseline.

Two evaluation modes run automatically:
  1. Rule-based (always available, no API key needed)
  2. Model-as-judge (runs when GEMINI_API_KEY or GOOGLE_API_KEY is set)

Usage:
    python evaluate.py                    # rule-based only
    GEMINI_API_KEY=... python evaluate.py # rule-based + model-as-judge
    EVAL_USE_LIVE=1 GEMINI_API_KEY=... python evaluate.py  # live generator + judge
"""
from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

from caption_assistant.checks import evaluate_caption
from caption_assistant.generator import generate_captions
from caption_assistant.judge import DEFAULT_JUDGE_MODEL, judge_caption
from caption_assistant.models import CaptionOption, JudgeResult, ProductBrief
from caption_assistant.recommender import evaluate_options


DATA_FILE = Path(__file__).parent / "data" / "evaluation_cases.json"
BASELINE_FILE = Path(__file__).parent / "data" / "manual_baseline_captions.json"
OUTPUT_DIR = Path(__file__).parent / "outputs"
AUTO_RESULTS_FILE = OUTPUT_DIR / "automatic_comparison.csv"
JUDGE_RESULTS_FILE = OUTPUT_DIR / "judge_comparison.csv"
MANUAL_TEMPLATE_FILE = OUTPUT_DIR / "manual_scoring_template.csv"


def load_cases():
    return json.loads(DATA_FILE.read_text())


def load_baselines():
    rows = json.loads(BASELINE_FILE.read_text())
    return {row["case_id"]: row for row in rows}


def build_brief(case: dict) -> ProductBrief:
    return ProductBrief(
        product_name=case["product_name"],
        key_benefits=case["key_benefits"],
        target_audience=case["target_audience"],
        campaign_objective=case["campaign_objective"],
        platform=case["platform"],
        brand_voice=case["brand_voice"],
        required_cta=case.get("required_cta", ""),
        banned_claims=case.get("banned_claims", ""),
        extra_context=case.get("extra_context", ""),
    )


def summarize_rule_metrics(result, prefix: str) -> dict:
    return {
        f"{prefix}_overall": result.overall_score,
        f"{prefix}_relevance": result.relevance_score,
        f"{prefix}_platform_fit": result.platform_fit_score,
        f"{prefix}_clarity": result.clarity_score,
        f"{prefix}_persuasiveness": result.persuasiveness_score,
        f"{prefix}_brand_voice": result.brand_voice_score,
        f"{prefix}_has_cta": result.has_cta,
        f"{prefix}_char_count": result.character_count,
        f"{prefix}_warnings": len(result.warnings),
        f"{prefix}_banned_found": " | ".join(result.banned_phrases_found),
    }


def summarize_judge_metrics(result: JudgeResult | None, prefix: str) -> dict:
    if result is None:
        return {
            f"{prefix}_judge_overall": "",
            f"{prefix}_judge_relevance": "",
            f"{prefix}_judge_platform_fit": "",
            f"{prefix}_judge_clarity": "",
            f"{prefix}_judge_persuasiveness": "",
            f"{prefix}_judge_brand_voice": "",
            f"{prefix}_judge_safety": "",
            f"{prefix}_judge_strengths": "",
            f"{prefix}_judge_weaknesses": "",
        }
    return {
        f"{prefix}_judge_overall": result.overall_score,
        f"{prefix}_judge_relevance": result.relevance_score,
        f"{prefix}_judge_platform_fit": result.platform_fit_score,
        f"{prefix}_judge_clarity": result.clarity_score,
        f"{prefix}_judge_persuasiveness": result.persuasiveness_score,
        f"{prefix}_judge_brand_voice": result.brand_voice_score,
        f"{prefix}_judge_safety": result.safety_score,
        f"{prefix}_judge_strengths": result.strengths,
        f"{prefix}_judge_weaknesses": result.weaknesses,
    }


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_manual_scoring_rows(case: dict, baseline_caption: str, system_caption: str) -> list[dict]:
    shared = {
        "case_id": case["case_id"],
        "product_name": case["product_name"],
        "platform": case["platform"],
    }
    return [
        {
            **shared,
            "workflow": "baseline_manual",
            "caption": baseline_caption,
            "relevance_score_human": "",
            "platform_fit_score_human": "",
            "clarity_score_human": "",
            "persuasiveness_score_human": "",
            "brand_voice_score_human": "",
            "safety_score_human": "",
            "time_to_first_draft_seconds": "",
            "revisions_needed": "",
            "evaluator_notes": "",
        },
        {
            **shared,
            "workflow": "app_recommended",
            "caption": system_caption,
            "relevance_score_human": "",
            "platform_fit_score_human": "",
            "clarity_score_human": "",
            "persuasiveness_score_human": "",
            "brand_voice_score_human": "",
            "safety_score_human": "",
            "time_to_first_draft_seconds": "",
            "revisions_needed": "",
            "evaluator_notes": "",
        },
    ]


def _safe_delta(a, b) -> str:
    if a == "" or b == "":
        return ""
    try:
        return round(float(a) - float(b), 2)
    except (TypeError, ValueError):
        return ""


def main():
    cases = load_cases()
    baselines = load_baselines()
    has_api = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    use_live_generation = os.getenv("EVAL_USE_LIVE", "").strip() in {"1", "true", "TRUE", "yes", "YES"}

    if has_api:
        print("API key found — model-as-judge evaluation will run.")
    else:
        print("No API key — running rule-based evaluation only.")
        print("Set GEMINI_API_KEY to also run model-as-judge scoring.")
    if use_live_generation:
        if has_api:
            print("Live generation enabled for evaluation cases.")
        else:
            print("EVAL_USE_LIVE is set but no API key is available, so generator will fall back to mock.")

    rule_rows: list[dict] = []
    judge_rows: list[dict] = []
    manual_rows: list[dict] = []

    total_rule_app = 0.0
    total_rule_baseline = 0.0
    total_judge_app = 0.0
    total_judge_baseline = 0.0
    judge_case_count = 0
    judge_failure_count = 0

    start = time.perf_counter()

    for case in cases:
        brief = build_brief(case)
        options, generation_meta = generate_captions(
            brief,
            use_mock=not use_live_generation,
        )
        evaluated = evaluate_options(brief, options)
        app_best = evaluated[0]

        baseline_row = baselines.get(case["case_id"])
        if not baseline_row:
            print(f"  Warning: no baseline found for {case['case_id']}, skipping.")
            continue

        baseline_caption = baseline_row["drafts"][baseline_row["selected_index"]]
        baseline_option = CaptionOption(
            tone_label="Manual baseline",
            caption=baseline_caption,
            cta=brief.required_cta,
            rationale=baseline_row.get("workflow_note", ""),
        )
        baseline_result = evaluate_caption(brief, baseline_option, [])

        total_rule_app += app_best.checks.overall_score
        total_rule_baseline += baseline_result.overall_score

        # Rule-based comparison row
        rule_rows.append(
            {
                "case_id": case["case_id"],
                "product_name": case["product_name"],
                "platform": case["platform"],
                "app_recommended_tone": app_best.option.tone_label,
                "app_caption": app_best.option.caption,
                "baseline_caption": baseline_caption,
                "generation_mode": generation_meta.mode,
                "generation_provider": generation_meta.provider,
                "generation_model": generation_meta.model,
                "generation_latency_ms": generation_meta.latency_ms,
                **summarize_rule_metrics(app_best.checks, "app"),
                **summarize_rule_metrics(baseline_result, "baseline"),
                "rule_score_delta": round(
                    app_best.checks.overall_score - baseline_result.overall_score, 2
                ),
                "warning_delta": len(app_best.checks.warnings) - len(baseline_result.warnings),
            }
        )

        # Model-as-judge row (only when API available)
        app_judge = judge_caption(brief, app_best.option.caption) if has_api else None
        baseline_judge = judge_caption(brief, baseline_caption) if has_api else None

        if app_judge is not None and baseline_judge is not None:
            total_judge_app += app_judge.overall_score
            total_judge_baseline += baseline_judge.overall_score
            judge_case_count += 1
        elif has_api:
            judge_failure_count += 1

        judge_rows.append(
            {
                "case_id": case["case_id"],
                "product_name": case["product_name"],
                "platform": case["platform"],
                "app_caption": app_best.option.caption,
                "baseline_caption": baseline_caption,
                "generation_mode": generation_meta.mode,
                "generation_provider": generation_meta.provider,
                "generation_model": generation_meta.model,
                "generation_latency_ms": generation_meta.latency_ms,
                **summarize_judge_metrics(app_judge, "app"),
                **summarize_judge_metrics(baseline_judge, "baseline"),
                "judge_overall_delta": _safe_delta(
                    app_judge.overall_score if app_judge else "",
                    baseline_judge.overall_score if baseline_judge else "",
                ),
            }
        )

        manual_rows.extend(
            build_manual_scoring_rows(case, baseline_caption, app_best.option.caption)
        )

    elapsed = time.perf_counter() - start
    n = max(len(cases), 1)

    write_csv(AUTO_RESULTS_FILE, rule_rows)
    write_csv(JUDGE_RESULTS_FILE, judge_rows)
    write_csv(MANUAL_TEMPLATE_FILE, manual_rows)

    print()
    print("=== Rule-based evaluation ===")
    print(f"Cases evaluated: {len(rule_rows)}")
    print(f"Avg app rule score:      {round(total_rule_app / n, 2)}/5")
    print(f"Avg baseline rule score: {round(total_rule_baseline / n, 2)}/5")
    print(f"Avg delta (app - baseline): {round((total_rule_app - total_rule_baseline) / n, 2)}")

    if judge_case_count > 0:
        print()
        print("=== Model-as-judge evaluation ===")
        print(f"Cases judged: {judge_case_count}")
        print(f"Avg app judge score:      {round(total_judge_app / judge_case_count, 2)}/5")
        print(f"Avg baseline judge score: {round(total_judge_baseline / judge_case_count, 2)}/5")
        print(
            f"Avg delta (app - baseline): "
            f"{round((total_judge_app - total_judge_baseline) / judge_case_count, 2)}"
        )
    elif has_api:
        print()
        print("=== Model-as-judge evaluation ===")
        print("No judge scores were returned.")

    if has_api:
        print(f"Judge failures: {judge_failure_count}")

    print()
    print(f"Total runtime: {elapsed:.2f}s")
    print(f"Rule comparison table:  {AUTO_RESULTS_FILE}")
    print(f"Judge comparison table: {JUDGE_RESULTS_FILE}")
    print(f"Manual scoring sheet:   {MANUAL_TEMPLATE_FILE}")


if __name__ == "__main__":
    main()
