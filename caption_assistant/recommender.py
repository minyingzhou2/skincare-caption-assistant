from __future__ import annotations

from typing import List

from .checks import evaluate_caption
from .models import CaptionOption, EvaluatedOption, ProductBrief


def evaluate_options(brief: ProductBrief, options: List[CaptionOption]) -> List[EvaluatedOption]:
    evaluated: List[EvaluatedOption] = []
    for index, option in enumerate(options):
        others = [item.caption for pos, item in enumerate(options) if pos != index]
        result = evaluate_caption(brief, option, others)
        evaluated.append(EvaluatedOption(option=option, checks=result))

    evaluated.sort(key=lambda item: item.checks.overall_score, reverse=True)
    return evaluated

