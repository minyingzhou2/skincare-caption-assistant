from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from typing import Iterable, List

from .models import CaptionOption, CheckResult, ProductBrief


DEFAULT_BANNED_PHRASES = [
    "cure",
    "guaranteed",
    "miracle",
    "instantly erase",
    "permanent results",
    "doctor approved",
    "clinically proven",
]

CTA_PATTERNS = [
    "shop now",
    "learn more",
    "tap to shop",
    "try it",
    "discover",
    "grab yours",
    "click the link",
    "add to cart",
]

PLATFORM_LENGTH_TARGETS = {
    "Instagram": (90, 180),
    "TikTok": (60, 140),
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def keyword_overlap_score(brief: ProductBrief, caption: str) -> float:
    caption_tokens = set(re.findall(r"[a-zA-Z]+", normalize_text(caption)))
    source_text = " ".join(
        [
            brief.product_name,
            brief.key_benefits,
            brief.target_audience,
            brief.campaign_objective,
            brief.brand_voice,
            brief.extra_context,
        ]
    )
    source_tokens = {
        token
        for token in re.findall(r"[a-zA-Z]+", normalize_text(source_text))
        if len(token) > 3
    }
    if not source_tokens:
        return 3.0

    overlap = len(source_tokens & caption_tokens)
    coverage = overlap / max(len(source_tokens), 1)
    return round(min(5.0, 1.5 + coverage * 8), 2)


def platform_fit_score(platform: str, character_count: int) -> float:
    lower, upper = PLATFORM_LENGTH_TARGETS.get(platform, (70, 180))
    if lower <= character_count <= upper:
        return 5.0

    midpoint = (lower + upper) / 2
    distance = abs(character_count - midpoint)
    spread = max(upper - lower, 1)
    penalty = min(4.0, distance / spread * 4.5)
    return round(max(1.0, 5.0 - penalty), 2)


def clarity_score(caption: str) -> float:
    sentences = [part for part in re.split(r"[.!?]+", caption) if part.strip()]
    words = re.findall(r"\b\w+\b", caption)
    if not words:
        return 1.0

    avg_words = len(words) / max(len(sentences), 1)
    hashtag_count = len(re.findall(r"#\w+", caption))
    emoji_count = len(re.findall(r"[\U0001F300-\U0001FAFF]", caption))
    penalty = max(0.0, (avg_words - 18) * 0.1) + hashtag_count * 0.1 + emoji_count * 0.05
    return round(max(1.0, min(5.0, 4.8 - penalty)), 2)


def persuasiveness_score(caption: str, required_cta: str) -> float:
    score = 2.8
    lowered = normalize_text(caption)
    if any(pattern in lowered for pattern in CTA_PATTERNS):
        score += 1.0
    if required_cta and normalize_text(required_cta) in lowered:
        score += 0.8
    if re.search(r"\b(glow|calm|smooth|bright|fresh|soft|hydrated|confidence)\b", lowered):
        score += 0.6
    if "?" in caption:
        score += 0.2
    return round(min(5.0, score), 2)


def brand_voice_score(brand_voice: str, caption: str) -> float:
    voice_tokens = [
        token
        for token in re.findall(r"[a-zA-Z]+", normalize_text(brand_voice))
        if len(token) > 3
    ]
    if not voice_tokens:
        return 3.5

    caption_tokens = set(re.findall(r"[a-zA-Z]+", normalize_text(caption)))
    overlap = len(caption_tokens & set(voice_tokens))
    raw = 2.8 + overlap * 0.7
    return round(min(5.0, raw), 2)


def find_banned_phrases(brief: ProductBrief, caption: str) -> List[str]:
    lowered = normalize_text(caption)
    banned_phrases = DEFAULT_BANNED_PHRASES + brief.banned_phrases()
    found = []
    for phrase in banned_phrases:
        if phrase and normalize_text(phrase) in lowered:
            found.append(phrase)
    return found


def has_cta(caption: str, required_cta: str) -> bool:
    lowered = normalize_text(caption)
    if required_cta and normalize_text(required_cta) in lowered:
        return True
    return any(pattern in lowered for pattern in CTA_PATTERNS)


def compute_similarity(text: str, others: Iterable[str]) -> float:
    scores = [
        SequenceMatcher(None, normalize_text(text), normalize_text(other)).ratio()
        for other in others
        if other.strip()
    ]
    if not scores:
        return 0.0
    return round(max(scores), 2)


def warnings_for_result(
    character_count: int,
    platform_score: float,
    similarity_score: float,
    banned_found: List[str],
    cta_present: bool,
) -> List[str]:
    warnings: List[str] = []
    if platform_score < 3.0:
        warnings.append("Length may not fit the target platform.")
    if similarity_score >= 0.72:
        warnings.append("This option is too similar to another draft.")
    if banned_found:
        warnings.append("Potentially unsafe claim language detected.")
    if not cta_present:
        warnings.append("Missing a clear call to action.")
    if character_count < 40:
        warnings.append("Caption may be too short to carry enough context.")
    return warnings


def overall_score(result: CheckResult) -> float:
    weighted = (
        result.platform_fit_score * 0.15
        + result.relevance_score * 0.25
        + result.clarity_score * 0.2
        + result.persuasiveness_score * 0.2
        + result.brand_voice_score * 0.2
    )
    penalty = len(result.banned_phrases_found) * 0.6 + len(result.warnings) * 0.25
    return round(max(1.0, min(5.0, weighted - penalty)), 2)


def evaluate_caption(
    brief: ProductBrief,
    option: CaptionOption,
    other_captions: Iterable[str],
) -> CheckResult:
    count = len(option.caption)
    platform_score = platform_fit_score(brief.platform, count)
    relevance = keyword_overlap_score(brief, option.caption)
    clarity = clarity_score(option.caption)
    persuasiveness = persuasiveness_score(option.caption, brief.required_cta)
    voice = brand_voice_score(brief.brand_voice, option.caption)
    banned_found = find_banned_phrases(brief, option.caption)
    cta_present = has_cta(option.caption, brief.required_cta)
    similarity = compute_similarity(option.caption, other_captions)
    warnings = warnings_for_result(count, platform_score, similarity, banned_found, cta_present)

    result = CheckResult(
        character_count=count,
        platform_fit_score=platform_score,
        relevance_score=relevance,
        clarity_score=clarity,
        persuasiveness_score=persuasiveness,
        brand_voice_score=voice,
        has_cta=cta_present,
        banned_phrases_found=banned_found,
        warnings=warnings,
        similarity_to_others=similarity,
    )
    result.overall_score = overall_score(result)
    return result

