from __future__ import annotations

import json
import os
import time
from typing import List, Tuple

from .checks import has_cta
from .models import CaptionOption, GenerationMetadata, ProductBrief


SYSTEM_PROMPT = """
You are a careful marketing copy assistant for skincare startups.
Generate social media captions that are persuasive, platform-aware, and compliant.
Never make medical, guaranteed, or unsupported treatment claims.
Keep captions short and natural for the target platform.
For Instagram, aim for about 90-160 characters.
For TikTok, aim for about 60-120 characters.
Return strict JSON with a top-level key named "options".
Each option must include: tone_label, caption, cta, rationale, risk_flags.
Produce exactly three distinct options.

Few-shot examples of high-quality captions:

Example 1 — Instagram, Vitamin C Serum, polished/calm brand voice:
Trendy: "Your morning, brighter. GlowNest Vitamin C Serum — lightweight glow for the daily rush. Shop now."
Premium: "Crafted for mornings that move fast. GlowNest delivers brightening hydration with a polished, effortless finish. Shop now."
Emotional: "Start the day feeling like yourself. GlowNest Vitamin C Serum brings a soft, radiant reset to your routine. Shop now."

Example 2 — TikTok, Acne Patches, playful/relatable brand voice:
Trendy: "Finals week called. ClearPatch answered. Stick on, sleep on, wake up. Tap to shop."
Premium: "One patch. One less thing to stress about tonight. ClearPatch keeps your overnight routine simple. Tap to shop."
Emotional: "When your skin needs a break as much as you do, ClearPatch is there. Low effort, low drama. Tap to shop."

These examples show the expected quality: short, natural, on-brand, and platform-appropriate.
Do NOT copy these examples directly. Use them as a quality benchmark.
""".strip()


USER_PROMPT_TEMPLATE = """
Create three caption drafts for this skincare campaign.

Product name: {product_name}
Key benefits: {key_benefits}
Target audience: {target_audience}
Campaign objective: {campaign_objective}
Platform: {platform}
Brand voice: {brand_voice}
Required CTA: {required_cta}
Banned claims or phrases: {banned_claims}
Extra context: {extra_context}

Make the three options distinct in tone:
1. Trendy short-form
2. Premium skincare
3. Emotional self-care

Use concise language and include a CTA in each option when appropriate.
Every caption must include the required CTA exactly or a very close CTA equivalent.
Do not restate every input field. Sound like a real social caption, not a summary of the brief.
""".strip()


GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "required": ["options"],
    "properties": {
        "options": {
            "type": "ARRAY",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "OBJECT",
                "required": ["tone_label", "caption", "cta", "rationale", "risk_flags"],
                "properties": {
                    "tone_label": {"type": "STRING"},
                    "caption": {"type": "STRING"},
                    "cta": {"type": "STRING"},
                    "rationale": {"type": "STRING"},
                    "risk_flags": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                    },
                },
            },
        }
    },
}

RETRYABLE_ERROR_MARKERS = [
    "503",
    "UNAVAILABLE",
    "high demand",
    "temporarily unavailable",
]


def _load_gemini_modules():
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None, None
    return genai, types


def _mock_options(brief: ProductBrief) -> List[CaptionOption]:
    product = brief.product_name.strip()
    primary_benefit = brief.key_benefits.split(",")[0].strip()
    cta = brief.required_cta.strip() or "Shop now"

    return [
        CaptionOption(
            tone_label="Trendy short-form",
            caption=(
                f"{product} is your shortcut to {primary_benefit.lower()}. "
                f"Easy, quick, and made to fit the scroll. {cta}."
            ),
            cta=cta,
            rationale="Short, punchy copy designed for fast social attention.",
        ),
        CaptionOption(
            tone_label="Premium skincare",
            caption=(
                f"Meet {product}, a polished essential for {primary_benefit.lower()} "
                f"and a more elevated daily ritual. {cta}."
            ),
            cta=cta,
            rationale="More polished language with a premium positioning angle.",
        ),
        CaptionOption(
            tone_label="Emotional self-care",
            caption=(
                f"Some routines feel like a reset. {product} brings {primary_benefit.lower()} "
                f"to the moments when your skin needs a softer touch. {cta}."
            ),
            cta=cta,
            rationale="Soft, emotionally resonant language for self-care framing.",
        ),
    ]


def _parse_options(payload: str) -> List[CaptionOption]:
    data = json.loads(payload)
    raw_options = data.get("options", [])
    options: List[CaptionOption] = []
    for item in raw_options[:3]:
        options.append(
            CaptionOption(
                tone_label=item.get("tone_label", "Variant"),
                caption=item.get("caption", "").strip(),
                cta=item.get("cta", "").strip(),
                rationale=item.get("rationale", "").strip(),
                risk_flags=item.get("risk_flags", []),
            )
        )
    return options


def _ensure_cta(brief: ProductBrief, options: List[CaptionOption]) -> List[CaptionOption]:
    required_cta = brief.required_cta.strip()
    if not required_cta:
        return options

    fixed_options: List[CaptionOption] = []
    for option in options:
        caption = option.caption.strip()
        cta = option.cta.strip() or required_cta
        if not has_cta(caption, required_cta):
            punctuation = "" if caption.endswith((".", "!", "?")) else "."
            caption = f"{caption}{punctuation} {required_cta}."
        fixed_options.append(
            CaptionOption(
                tone_label=option.tone_label,
                caption=caption,
                cta=cta,
                rationale=option.rationale,
                risk_flags=option.risk_flags,
            )
        )
    return fixed_options


def _is_retryable_error(exc: Exception) -> bool:
    message = str(exc)
    return any(marker.lower() in message.lower() for marker in RETRYABLE_ERROR_MARKERS)


def generate_captions(
    brief: ProductBrief,
    model: str = "gemini-2.5-flash",
    use_mock: bool = False,
) -> Tuple[List[CaptionOption], GenerationMetadata]:
    if use_mock:
        return _mock_options(brief), GenerationMetadata(
            mode="mock",
            provider="mock",
            model="mock-template",
            used_fallback=False,
        )

    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        return _mock_options(brief), GenerationMetadata(
            mode="mock",
            provider="mock",
            model="mock-template",
            used_fallback=True,
            fallback_reason="No GEMINI_API_KEY or GOOGLE_API_KEY was available.",
        )

    genai, types = _load_gemini_modules()
    if genai is None or types is None:
        return _mock_options(brief), GenerationMetadata(
            mode="mock",
            provider="mock",
            model="mock-template",
            used_fallback=True,
            fallback_reason="The google-genai package is not installed or could not be imported.",
        )

    prompt = USER_PROMPT_TEMPLATE.format(
        product_name=brief.product_name,
        key_benefits=brief.key_benefits,
        target_audience=brief.target_audience,
        campaign_objective=brief.campaign_objective,
        platform=brief.platform,
        brand_voice=brief.brand_voice,
        required_cta=brief.required_cta or "None",
        banned_claims=brief.banned_claims or "None",
        extra_context=brief.extra_context or "None",
    )

    try:
        client = genai.Client()
        started = time.perf_counter()
        retries = 2
        response = None
        for attempt in range(retries + 1):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.6,
                        response_mime_type="application/json",
                        response_schema=GEMINI_RESPONSE_SCHEMA,
                    ),
                )
                break
            except Exception as exc:
                if attempt >= retries or not _is_retryable_error(exc):
                    raise
                time.sleep(1.2 * (attempt + 1))
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        content = response.text or '{"options": []}'
        options = _ensure_cta(brief, _parse_options(content))
    except Exception as exc:
        return _mock_options(brief), GenerationMetadata(
            mode="mock",
            provider="mock",
            model="mock-template",
            used_fallback=True,
            fallback_reason=f"Gemini API call failed after retrying: {exc}",
        )

    if len(options) < 3:
        return _mock_options(brief), GenerationMetadata(
            mode="mock",
            provider="mock",
            model="mock-template",
            used_fallback=True,
            fallback_reason="Gemini returned fewer than three valid options.",
        )
    return options, GenerationMetadata(
        mode="live",
        provider="gemini",
        model=model,
        used_fallback=False,
        raw_text_available=bool(content),
        latency_ms=latency_ms,
    )
