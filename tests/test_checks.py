import unittest

from caption_assistant.checks import evaluate_caption
from caption_assistant.models import CaptionOption, ProductBrief


class CheckTests(unittest.TestCase):
    def test_evaluate_caption_flags_banned_phrase(self):
        brief = ProductBrief(
            product_name="ClearPatch",
            key_benefits="overnight spot coverage",
            target_audience="students",
            campaign_objective="drive trials",
            platform="TikTok",
            brand_voice="playful and quick",
            required_cta="Tap to shop",
            banned_claims="instant cure",
        )
        option = CaptionOption(
            tone_label="Trendy short-form",
            caption="ClearPatch is your instant cure for surprise breakouts. Tap to shop.",
            cta="Tap to shop",
        )

        result = evaluate_caption(brief, option, [])

        self.assertIn("instant cure", result.banned_phrases_found)
        self.assertTrue(result.has_cta)

    def test_evaluate_caption_detects_missing_cta(self):
        brief = ProductBrief(
            product_name="GlowNest Serum",
            key_benefits="brightening",
            target_audience="young professionals",
            campaign_objective="drive clicks",
            platform="Instagram",
            brand_voice="polished, calm",
            required_cta="Shop now",
        )
        option = CaptionOption(
            tone_label="Premium skincare",
            caption="GlowNest Serum brings a fresh, polished start to your routine.",
            cta="",
        )

        result = evaluate_caption(brief, option, [])

        self.assertFalse(result.has_cta)
        self.assertIn("Missing a clear call to action.", result.warnings)


if __name__ == "__main__":
    unittest.main()
