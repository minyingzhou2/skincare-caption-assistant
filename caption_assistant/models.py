from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ProductBrief:
    product_name: str
    key_benefits: str
    target_audience: str
    campaign_objective: str
    platform: str
    brand_voice: str
    required_cta: str = ""
    banned_claims: str = ""
    extra_context: str = ""

    def banned_phrases(self) -> List[str]:
        phrases = [part.strip() for part in self.banned_claims.split(",")]
        return [phrase for phrase in phrases if phrase]


@dataclass
class CaptionOption:
    tone_label: str
    caption: str
    cta: str
    rationale: str = ""
    risk_flags: List[str] = field(default_factory=list)


@dataclass
class CheckResult:
    character_count: int
    platform_fit_score: float
    relevance_score: float
    clarity_score: float
    persuasiveness_score: float
    brand_voice_score: float
    has_cta: bool
    banned_phrases_found: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    similarity_to_others: float = 0.0
    overall_score: float = 0.0


@dataclass
class EvaluatedOption:
    option: CaptionOption
    checks: CheckResult


@dataclass
class GenerationMetadata:
    mode: str
    provider: str
    model: str
    used_fallback: bool = False
    fallback_reason: str = ""
    raw_text_available: bool = False
    latency_ms: float = 0.0


@dataclass
class JudgeResult:
    """Scores returned by the model-as-judge for a single caption."""
    relevance_score: int
    platform_fit_score: int
    clarity_score: int
    persuasiveness_score: int
    brand_voice_score: int
    safety_score: int
    overall_score: int
    strengths: str = ""
    weaknesses: str = ""
