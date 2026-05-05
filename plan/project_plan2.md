# Project Plan

## 1. Project Title

Skincare Launch Caption Drafting Assistant

## 2. Target User, Workflow, and Business Value

The target user is a junior social media coordinator at a direct-to-consumer skincare startup. This user regularly receives structured launch briefs for new products and must turn those briefs into short marketing captions for Instagram and TikTok.

The workflow begins when the coordinator receives a product brief containing the product name, key benefits, target audience, campaign goal, and platform. The workflow ends when the coordinator has a small set of draft captions that a manager can review and approve for publishing.

Improving this workflow matters because early-stage skincare brands often have small marketing teams, fast launch cycles, and strong pressure to produce platform-specific copy quickly. Better performance on this task can reduce drafting time, improve consistency of brand voice, and increase the chance that campaign copy is clear, persuasive, and appropriate for the platform.

## 3. Problem Statement and GenAI Fit

This system will take one structured skincare product brief and generate several platform-appropriate caption drafts, then recommend which draft is strongest based on predefined quality criteria and rule-based checks.

This task is a good fit for language models because it requires transforming structured inputs into persuasive, audience-aware marketing language, varying tone across multiple options, and adapting style to different social platforms. A simpler non-GenAI tool such as fixed templates is not enough because templates tend to sound repetitive, generic, and inflexible when the product, audience, and campaign objective change.

## 4. Planned System Design and Baseline

The planned system is a small Streamlit app. The user will paste or enter a structured product brief with fields such as product name, benefits, target audience, campaign objective, platform, and any banned claims. The app will send this information to an LLM with a prompt that asks for three caption variants with different tones appropriate to the business context. After generation, the app will run deterministic checks on each output, such as character count, banned-phrase detection, CTA detection, and similarity checking across the three options. The app will then display the captions, show warnings from the checks, and recommend one option as the best starting draft for manager review.

The two course concepts I plan to integrate are:

1. Anatomy of an LLM call: I will use a system prompt and structured output constraints to control audience, tone, CTA style, and restricted claims. The model output will be formatted into clear fields such as caption text, CTA, and risk flags so the app can display and evaluate results consistently.
2. Tool use or function calling: I will use deterministic tools for tasks that should not rely on language-model judgment alone, including character counting, banned-phrase checking, and similarity checks between outputs. This follows the principle that rule-based validation should be handled by tools rather than by the model itself.

The simpler baseline will be the current status quo workflow: a person manually drafts three captions from the same brief and a manager reviews them. I will compare the proposed system against this manual process in terms of output quality, time required, and number of revisions needed.

The planned app will have a simple interface with a brief-input form on the left and generated results on the right. The user will submit a brief, review three caption options, inspect automatic warnings and simple scores, and see which caption the system recommends as the best draft. The user will still make the final decision; the app is meant to support drafting and review, not publish automatically.

## 5. Evaluation Plan

Success for this workflow means producing caption drafts that are at least as strong as the manual baseline while reducing the time needed to create a usable first draft. A successful system should also reduce obvious quality and compliance problems such as repetitive phrasing, missing calls to action, or exaggerated claims.

I plan to measure:

- relevance to the brief
- platform fit
- clarity
- persuasiveness
- brand-tone consistency
- number of warnings triggered by rule-based checks
- time to produce a usable draft
- number of revisions required before approval

Each quality dimension will be scored on a 1-5 rubric. I expect to build a test set of about 15-20 synthetic skincare launch briefs, covering a range of product types such as acne patches, vitamin C serum, SPF mist, moisturizer, and night cream. I will compare the app against the manual baseline by running both workflows on the same set of briefs and comparing average rubric scores, revision counts, and drafting time. If time allows, I will also use a model-as-judge pass for consistency and then spot-check the results manually.

## 6. Example Inputs and Failure Cases

Example inputs or use cases:

- A TikTok launch brief for acne patches targeted at college students during finals week
- An Instagram caption request for a premium night cream aimed at women ages 30-45
- A summer sunscreen mist campaign focused on convenience and reapplication
- A vitamin C serum brief emphasizing brightening and morning-routine use
- A sensitive-skin moisturizer campaign with a calm, trustworthy brand voice

Likely failure cases or edge cases:

- The model may generate unrealistic or non-compliant skincare claims
- The captions may become too generic or too similar to one another
- A trendy TikTok tone may sound forced or mismatched to the brand
- The system may overemphasize persuasion and underemphasize accuracy or restraint

## 7. Risks and Governance

The main risks are overstated product benefits, medically suggestive language, and captions that sound persuasive but are not appropriate for brand or compliance standards. The system should not be trusted to make medical, legal, or regulatory decisions, and it should not be trusted to publish content without human review.

To manage these risks, I plan to include banned-phrase and warning checks, require human review before any caption is used, and add refusal or warning behavior when the input asks for unsupported treatment claims or unsafe promises. The app will function as a drafting assistant only, not an autonomous publishing tool.

The project will use only synthetic or public data. No customer data, private business information, or API secrets will be stored in the repository. To limit cost, I will keep the workflow narrow and restrict each request to a small number of generations.

## 8. Plan for the Week 6 Check-in

By the Week 6 check-in, I expect to have a working first-pass Streamlit app that accepts a skincare brief and generates three caption options. I also expect the deterministic validation tools to be running, including at least character count, banned-phrase detection, and similarity checking.

For evaluation, I expect to have a draft rubric and at least 10 test cases prepared. I also expect to be able to run one initial comparison against the baseline manual workflow, focusing on time to first draft and a first-pass quality comparison on a small subset of cases.
