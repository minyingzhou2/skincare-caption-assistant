# Skincare Launch Caption Drafting Assistant

A Streamlit app for a junior social media coordinator at a direct-to-consumer skincare startup.
The user submits a structured product brief, the app generates three caption variants with distinct tones, runs deterministic quality checks, and recommends the strongest draft for manager review.

Human review is required before any caption is used. The app is a drafting assistant, not an autonomous publisher.

---

## What the app does

1. Accepts a structured product brief (product name, benefits, audience, platform, brand voice, CTA, banned claims)
2. Calls Gemini with a system prompt + few-shot examples to generate three caption options
3. Runs rule-based checks on each option: character count, banned-phrase detection, CTA detection, similarity across drafts, and five weighted quality scores
4. Ranks options by overall rule score and recommends the best starting draft
5. Optionally runs a **model-as-judge** pass on the recommended caption to score it on six rubric dimensions with qualitative reasoning

---

## Course concepts integrated

### 1. Context engineering — few-shot examples (`caption_assistant/generator.py`)

The generation prompt includes two annotated examples of high-quality captions (one Instagram, one TikTok) directly inside the system prompt. This gives the model a concrete quality benchmark and reduces generic or off-brand outputs.
The examples cover tone variety (trendy, premium, emotional) and both target platforms, so the model has seen what "good" looks like before it writes anything.

### 2. Evaluation design — model-as-judge (`caption_assistant/judge.py`, `evaluate.py`)

A separate Gemini call acts as an independent evaluator. Given the brief and a caption, the judge scores six rubric dimensions (relevance, platform fit, clarity, persuasiveness, brand voice, safety) and returns structured JSON with overall score, strengths, and weaknesses.
The judge uses `temperature=0.1` to produce consistent, conservative scores and a different, lower-cost model (`gemini-2.0-flash`) than the generator to decouple evaluation from generation.
`evaluate.py` runs both rule-based and model-as-judge scoring side by side on the full test set, so the comparison against the manual baseline uses two independent signal types.

---

## Run locally

```bash
# 1. Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Optional: set API key for live generation and judge evaluation
export GEMINI_API_KEY=your_key_here

# 4. Start the app
streamlit run app.py
```

The app defaults to mock mode and runs without an API key or the `google-genai` package.

---

## Sidebar options

| Setting | Default | Description |
|---|---|---|
| Load example brief | Custom | Pre-fills the form with a sample skincare brief |
| Use mock generator | On | Toggle off to use live Gemini generation |
| Run model-as-judge | Off | Scores the recommended caption via a separate LLM call (requires API key) |
| Model name | `gemini-2.5-flash` | Override the generation model |
| Gemini API key | — | Session-only key, never written to disk |

---

## Evaluation

### Running the evaluation script

```bash
python evaluate.py                      # rule-based only, no API key needed
GEMINI_API_KEY=... python evaluate.py   # rule-based + model-as-judge
```

The script runs over all 10 test cases, compares the app's recommended caption against the manually-selected baseline caption, and writes three output files:

| File | Contents |
|---|---|
| `outputs/automatic_comparison.csv` | Rule-based scores for app vs. baseline, side by side |
| `outputs/judge_comparison.csv` | Model-as-judge scores for app vs. baseline (empty columns if no API key) |
| `outputs/manual_scoring_template.csv` | Human evaluation sheet with empty score columns |

### Test set

10 synthetic skincare briefs covering:
- Product types: vitamin C serum, acne patches, SPF mist, moisture cream, night cream, retinol serum, toner mist, eye cream, glow mask, body lotion
- Platforms: Instagram (7), TikTok (3)
- Brand voices: polished, playful, gentle, luxurious, reassuring, energetic, bold, warm

Each case has a status-quo baseline (three manual drafts with one selected by a simulated manager review).

### What counts as a good output

A strong caption scores at least 4/5 on relevance and platform fit, includes the required CTA, avoids all banned phrases, and reads naturally for the target platform. The model-as-judge adds a safety dimension and qualitative reasoning that rule-based checks cannot capture.

### Baseline comparison

The baseline is the status quo workflow: a coordinator manually writes three drafts from the same brief and a manager picks one. The selected baseline caption is scored through the same rule-based checks and model-as-judge as the app output, so the comparison is apples-to-apples.

### Where the system fails

- **Generic mock output**: The mock generator uses a fixed template. All mock captions follow the same structure regardless of brand voice, which makes mock-mode evaluation scores less meaningful than live Gemini output.
- **Rule-based relevance is shallow**: The keyword-overlap relevance score counts token matches but cannot detect paraphrasing or semantic misalignment. A caption can score well on relevance while missing the actual campaign message.
- **Judge consistency is not guaranteed**: The model-as-judge uses low temperature but can still vary across runs. A single judge score per caption is not a reliable ground truth — it is one signal to triangulate with, not a final verdict.
- **Platform fit is length-only**: The rule check scores platform fit based on character count alone. A 120-character caption that uses formal language on TikTok will still score 5/5 for platform fit.
- **No test for refusal behavior**: The app does not actively refuse briefs that request unsafe claims — it only adds warnings after generation. A brief that demands "guaranteed results" will still produce captions, just with warning flags attached.

### Governance and trust boundaries

- A human manager must review and approve every caption before it is published.
- The app does not post or schedule content.
- No customer data or real business briefs are committed to the repository — all test data is synthetic.
- API keys are never stored; they live only in the current session environment.

---

## Project structure

```
app.py                               Streamlit app entry point
evaluate.py                          Evaluation script (rule-based + model-as-judge)
caption_assistant/
  generator.py                       Gemini caption generation with few-shot examples
  judge.py                           Model-as-judge scoring module
  checks.py                          Rule-based quality and compliance checks
  recommender.py                     Ranks options by rule-based overall score
  models.py                          Data classes (ProductBrief, CaptionOption, etc.)
  logging_utils.py                   CSV logging for live experiment runs
data/
  sample_briefs.json                 3 sample briefs for the app demo
  evaluation_cases.json              10 test cases for evaluation
  manual_baseline_captions.json      Baseline captions (status quo workflow)
docs/
  evaluation_rubric.md               Rubric definitions and comparison procedure
outputs/
  automatic_comparison.csv           Rule-based comparison table (generated)
  judge_comparison.csv               Model-as-judge comparison table (generated)
  manual_scoring_template.csv        Human scoring sheet (generated)
```

---

## Model and provider

| Role | Model | Reason |
|---|---|---|
| Caption generation | `gemini-2.5-flash` (default) | Best balance of quality, speed, and structured output support |
| Model-as-judge | `gemini-2.0-flash` | Lower cost for evaluation; judge needs consistency over creativity |

Both models support the `google-genai` SDK's structured output (`response_mime_type="application/json"` + `response_schema`), which enforces the output format without post-processing.
