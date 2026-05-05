from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .models import EvaluatedOption, GenerationMetadata, ProductBrief


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
LIVE_EXPERIMENTS_FILE = OUTPUT_DIR / "live_experiments.csv"


def append_live_experiment(
    brief: ProductBrief,
    generation_meta: GenerationMetadata,
    best_option: EvaluatedOption,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    exists = LIVE_EXPERIMENTS_FILE.exists()
    row = {
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "provider": generation_meta.provider,
        "mode": generation_meta.mode,
        "model": generation_meta.model,
        "latency_ms": generation_meta.latency_ms,
        "used_fallback": generation_meta.used_fallback,
        "fallback_reason": generation_meta.fallback_reason,
        "platform": brief.platform,
        "product_name": brief.product_name,
        "campaign_objective": brief.campaign_objective,
        "brand_voice": brief.brand_voice,
        "required_cta": brief.required_cta,
        "recommended_tone": best_option.option.tone_label,
        "recommended_caption": best_option.option.caption,
        "overall_score": best_option.checks.overall_score,
        "relevance_score": best_option.checks.relevance_score,
        "platform_fit_score": best_option.checks.platform_fit_score,
        "clarity_score": best_option.checks.clarity_score,
        "persuasiveness_score": best_option.checks.persuasiveness_score,
        "brand_voice_score": best_option.checks.brand_voice_score,
        "character_count": best_option.checks.character_count,
        "cta_detected": best_option.checks.has_cta,
        "warnings_count": len(best_option.checks.warnings),
        "warnings": " | ".join(best_option.checks.warnings),
    }

    with LIVE_EXPERIMENTS_FILE.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)
