from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from caption_assistant.generator import generate_captions
from caption_assistant.judge import judge_caption
from caption_assistant.logging_utils import append_live_experiment
from caption_assistant.models import ProductBrief
from caption_assistant.recommender import evaluate_options


DATA_DIR = Path(__file__).parent / "data"
SAMPLE_FILE = DATA_DIR / "sample_briefs.json"


def load_sample_briefs():
    return json.loads(SAMPLE_FILE.read_text())


def brief_from_sample(sample: dict) -> ProductBrief:
    return ProductBrief(
        product_name=sample["product_name"],
        key_benefits=sample["key_benefits"],
        target_audience=sample["target_audience"],
        campaign_objective=sample["campaign_objective"],
        platform=sample["platform"],
        brand_voice=sample["brand_voice"],
        required_cta=sample.get("required_cta", ""),
        banned_claims=sample.get("banned_claims", ""),
        extra_context=sample.get("extra_context", ""),
    )


st.set_page_config(
    page_title="Skincare Caption Drafting Assistant",
    page_icon="✨",
    layout="wide",
)

st.title("Skincare Launch Caption Drafting Assistant")
st.caption("Generate three caption drafts, run deterministic checks, and compare the best starting point.")

with st.sidebar:
    st.subheader("Demo Settings")
    sample_briefs = load_sample_briefs()
    sample_names = ["Custom brief"] + [sample["name"] for sample in sample_briefs]
    selected_name = st.selectbox("Load example brief", sample_names)
    use_mock = st.toggle("Use mock generator", value=True)
    run_judge = st.toggle(
        "Run model-as-judge on recommendation",
        value=False,
        help="Uses Gemini to score the recommended caption on 6 rubric dimensions. Requires an API key.",
    )
    model_name = st.text_input("Model name", value="gemini-2.5-flash")
    session_api_key = st.text_input(
        "Gemini API key (session only)",
        type="password",
        help="Optional. This stays in the current Streamlit session and is not written to disk.",
    )
    if session_api_key:
        os.environ["GEMINI_API_KEY"] = session_api_key
    st.markdown(
        "Mock mode keeps the app runnable without a `GEMINI_API_KEY`/`GOOGLE_API_KEY` or the `google-genai` package."
    )
    st.caption(
        "If `gemini-2.5-flash` is busy, try `gemini-2.0-flash` or `gemini-1.5-flash`."
    )

selected_sample = next((item for item in load_sample_briefs() if item["name"] == selected_name), None)

if selected_sample:
    initial = brief_from_sample(selected_sample)
else:
    initial = ProductBrief(
        product_name="GlowNest Vitamin C Serum",
        key_benefits="brightening, lightweight hydration, morning-routine glow",
        target_audience="busy professionals in their mid-20s to late-30s",
        campaign_objective="drive clicks to the new product launch page",
        platform="Instagram",
        brand_voice="polished, calm, modern, trustworthy",
        required_cta="Shop now",
        banned_claims="cure acne, miracle, guaranteed results",
        extra_context="launch week, premium but approachable positioning",
    )

left, right = st.columns([1, 1.25], gap="large")

with left:
    st.subheader("Campaign Brief")
    with st.form("brief-form"):
        product_name = st.text_input("Product name", value=initial.product_name)
        key_benefits = st.text_area("Key benefits", value=initial.key_benefits, height=90)
        target_audience = st.text_input("Target audience", value=initial.target_audience)
        campaign_objective = st.text_input("Campaign objective", value=initial.campaign_objective)
        platform = st.selectbox("Platform", ["Instagram", "TikTok"], index=0 if initial.platform == "Instagram" else 1)
        brand_voice = st.text_input("Brand voice", value=initial.brand_voice)
        required_cta = st.text_input("Required CTA", value=initial.required_cta)
        banned_claims = st.text_input("Banned claims or phrases", value=initial.banned_claims)
        extra_context = st.text_area("Extra context", value=initial.extra_context, height=90)
        submitted = st.form_submit_button("Generate caption options", type="primary")

brief = ProductBrief(
    product_name=product_name,
    key_benefits=key_benefits,
    target_audience=target_audience,
    campaign_objective=campaign_objective,
    platform=platform,
    brand_voice=brand_voice,
    required_cta=required_cta,
    banned_claims=banned_claims,
    extra_context=extra_context,
)

with right:
    st.subheader("Results")
    if submitted:
        with st.spinner("Generating caption drafts and running checks..."):
            options, generation_meta = generate_captions(
                brief, model=model_name, use_mock=use_mock
            )
            evaluated = evaluate_options(brief, options)

        if generation_meta.mode == "live":
            st.success(
                f"Live Gemini generation succeeded with model `{generation_meta.model}`."
            )
            st.caption(f"Latency: {generation_meta.latency_ms} ms")
        elif generation_meta.used_fallback:
            st.warning(
                "The app fell back to mock generation.\n\n"
                f"Reason: {generation_meta.fallback_reason}"
            )
        else:
            st.info("Mock mode is enabled for deterministic demo output.")

        best = evaluated[0]
        if generation_meta.mode == "live" and not generation_meta.used_fallback:
            append_live_experiment(brief, generation_meta, best)
        st.success(f"Recommended draft: {best.option.tone_label} (rule score {best.checks.overall_score}/5)")

        # Model-as-judge panel for the recommended caption
        if run_judge:
            with st.spinner("Running model-as-judge evaluation on the recommended draft..."):
                judge_result = judge_caption(brief, best.option.caption, model="gemini-2.0-flash")
            if judge_result is None:
                st.warning(
                    "Model-as-judge requires a Gemini API key. "
                    "Set GEMINI_API_KEY or enter it in the sidebar."
                )
            else:
                with st.expander("Model-as-judge scores (recommended draft)", expanded=True):
                    jcols = st.columns(7)
                    jcols[0].metric("Overall", f"{judge_result.overall_score}/5")
                    jcols[1].metric("Relevance", judge_result.relevance_score)
                    jcols[2].metric("Platform", judge_result.platform_fit_score)
                    jcols[3].metric("Clarity", judge_result.clarity_score)
                    jcols[4].metric("Persuasive", judge_result.persuasiveness_score)
                    jcols[5].metric("Voice", judge_result.brand_voice_score)
                    jcols[6].metric("Safety", judge_result.safety_score)
                    if judge_result.strengths:
                        st.caption(f"Strengths: {judge_result.strengths}")
                    if judge_result.weaknesses:
                        st.caption(f"Weaknesses: {judge_result.weaknesses}")

        for item in evaluated:
            with st.container(border=True):
                st.markdown(f"### {item.option.tone_label}")
                st.write(item.option.caption)
                if item.option.rationale:
                    st.caption(item.option.rationale)

                metric_cols = st.columns(6)
                metric_cols[0].metric("Overall", item.checks.overall_score)
                metric_cols[1].metric("Relevance", item.checks.relevance_score)
                metric_cols[2].metric("Platform Fit", item.checks.platform_fit_score)
                metric_cols[3].metric("Clarity", item.checks.clarity_score)
                metric_cols[4].metric("Persuasive", item.checks.persuasiveness_score)
                metric_cols[5].metric("Voice", item.checks.brand_voice_score)

                details = st.columns(3)
                details[0].write(f"Characters: {item.checks.character_count}")
                details[1].write(f"CTA detected: {'Yes' if item.checks.has_cta else 'No'}")
                details[2].write(f"Similarity: {item.checks.similarity_to_others}")

                if item.checks.banned_phrases_found:
                    st.warning(
                        "Banned or risky phrases found: "
                        + ", ".join(item.checks.banned_phrases_found)
                    )
                if item.checks.warnings:
                    for warning in item.checks.warnings:
                        st.write(f"- {warning}")
                else:
                    st.write("- No warnings triggered.")

    else:
        st.write("Submit a campaign brief to generate caption options.")
        st.write("The app will produce three variants, run rule-based checks, and recommend a best starting draft.")
