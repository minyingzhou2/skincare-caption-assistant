"""Model-as-judge module for scoring caption quality using an LLM.

Uses Gemini with structured output to score captions on six rubric dimensions.
Falls back gracefully when no API key is available.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from .models import JudgeResult, ProductBrief


JUDGE_SYSTEM_PROMPT = """
You are an expert evaluator for social media marketing copy at a direct-to-consumer skincare brand.
Score a caption draft on six dimensions using an INTEGER from 1 to 5.

Scoring guide:
- relevance_score: Does the caption reflect the product benefits and campaign objective?
  1 = off-topic or ignores the brief entirely
  3 = mentions the product but misses key benefits or objective
  5 = closely aligned with all key brief elements
- platform_fit_score: Is the length, tone, and energy right for the specified platform (Instagram or TikTok)?
  1 = clearly wrong length or tone for the platform
  3 = acceptable but not optimized
  5 = ideal fit — correct length, natural cadence, platform-native feel
- clarity_score: Is the caption clear, focused, and easy to read at a glance?
  1 = confusing, cluttered, or hard to parse quickly
  3 = readable but could be tighter
  5 = immediately clear with clean, purposeful language
- persuasiveness_score: Is the copy likely to drive the desired action?
  1 = no motivating language, no CTA, passive voice
  3 = some motivating language but weak or generic CTA
  5 = compelling emotional hook plus a clear, specific CTA
- brand_voice_score: Does the caption match the stated brand voice?
  1 = contradicts or ignores the brand voice entirely
  3 = neutral, neither matching nor contradicting
  5 = perfectly on-brand — tone, word choice, and energy all align
- safety_score: Is the caption free of unsupported claims, medical language, or banned phrases?
  1 = makes a clearly unsupported or medically suggestive claim
  3 = borderline language that could raise concerns
  5 = fully compliant — no exaggerated, misleading, or banned language

Return a JSON object with:
- all six score fields (integers 1–5)
- overall_score (integer 1–5, your holistic judgment — not a mechanical average)
- strengths (one sentence on what works best)
- weaknesses (one sentence on the main area for improvement)
""".strip()

JUDGE_USER_TEMPLATE = """
Brief:
- Product: {product_name}
- Platform: {platform}
- Key benefits: {key_benefits}
- Target audience: {target_audience}
- Brand voice: {brand_voice}
- Required CTA: {required_cta}
- Banned claims: {banned_claims}

Caption to evaluate:
"{caption}"

Score this caption on all six dimensions.
""".strip()

JUDGE_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "required": [
        "relevance_score",
        "platform_fit_score",
        "clarity_score",
        "persuasiveness_score",
        "brand_voice_score",
        "safety_score",
        "overall_score",
        "strengths",
        "weaknesses",
    ],
    "properties": {
        "relevance_score": {"type": "INTEGER"},
        "platform_fit_score": {"type": "INTEGER"},
        "clarity_score": {"type": "INTEGER"},
        "persuasiveness_score": {"type": "INTEGER"},
        "brand_voice_score": {"type": "INTEGER"},
        "safety_score": {"type": "INTEGER"},
        "overall_score": {"type": "INTEGER"},
        "strengths": {"type": "STRING"},
        "weaknesses": {"type": "STRING"},
    },
}


def _load_genai():
    try:
        from google import genai
        from google.genai import types

        return genai, types
    except ImportError:
        return None, None


def judge_caption(
    brief: ProductBrief,
    caption: str,
    model: str = "gemini-2.0-flash",
) -> Optional[JudgeResult]:
    """Score a caption using an LLM judge.

    Returns a dict with score fields and reasoning, or None if no API key
    is configured or the google-genai package is missing.
    """
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        return None

    genai, types = _load_genai()
    if genai is None:
        return None

    prompt = JUDGE_USER_TEMPLATE.format(
        product_name=brief.product_name,
        platform=brief.platform,
        key_benefits=brief.key_benefits,
        target_audience=brief.target_audience,
        brand_voice=brief.brand_voice,
        required_cta=brief.required_cta or "None",
        banned_claims=brief.banned_claims or "None",
        caption=caption,
    )

    try:
        client = genai.Client()
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=JUDGE_SYSTEM_PROMPT,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=JUDGE_RESPONSE_SCHEMA,
            ),
        )
        data = json.loads(response.text or "{}")
        return JudgeResult(
            relevance_score=int(data.get("relevance_score", 3)),
            platform_fit_score=int(data.get("platform_fit_score", 3)),
            clarity_score=int(data.get("clarity_score", 3)),
            persuasiveness_score=int(data.get("persuasiveness_score", 3)),
            brand_voice_score=int(data.get("brand_voice_score", 3)),
            safety_score=int(data.get("safety_score", 3)),
            overall_score=int(data.get("overall_score", 3)),
            strengths=data.get("strengths", ""),
            weaknesses=data.get("weaknesses", ""),
        )
    except Exception:
        return None


def judge_captions_batch(
    brief: ProductBrief,
    captions: list[str],
    model: str = "gemini-2.0-flash",
) -> list[Optional[JudgeResult]]:
    """Score multiple captions for the same brief. Returns one result per caption."""
    return [judge_caption(brief, caption, model=model) for caption in captions]
