"""
ai_narrative.py — Supplier Performance & Risk Scorecard
AI generates narrative explaining deterministic scores and recommendation.
AI never generates or modifies scores or recommendations.
"""

import anthropic
from models import SupplierInputs, GEO_TIER_LABELS, MODE_LAYER_WEIGHTS
from compliance import evaluate_compliance, compliance_summary
from scoring import score_supplier, normalize_to_ppm
from recommendation import get_recommendation

AI_FALLBACK = (
    "AI narrative unavailable. Deterministic scores, compliance flags, "
    "and recommendation remain valid and are displayed above."
)


def build_prompt(
    inputs: SupplierInputs,
    score_result: dict,
    compliance_flags: list,
    rec_result: dict,
) -> str:
    perf_dims   = score_result["performance_detail"]["dimension_scores"]
    risk_dims   = score_result["risk_detail"]["dimension_scores"]
    geo_tier    = score_result["risk_detail"]["geo_tier"]
    geo_label   = GEO_TIER_LABELS.get(geo_tier, ("Unknown",))[0]
    comp_sum    = compliance_summary(compliance_flags)
    layer_w     = score_result["layer_weights"]
    mode        = score_result["scoring_mode"]
    quality_ppm = score_result["quality_ppm"]
    confidence  = score_result["confidence"]

    compliance_block = ""
    if rec_result["cap_triggered"]:
        if rec_result["cap_escalated"]:
            escalation_note = (
                f'The score-based recommendation was "{rec_result["base_recommendation"]}" '
                f'but was overridden to "{rec_result["final_recommendation"]}" due to compliance gaps. '
                f'This override is deterministic and final.'
            )
        else:
            escalation_note = (
                f'The score-based recommendation "{rec_result["final_recommendation"]}" was not changed '
                f'by compliance caps, but active compliance gaps still apply and must be foregrounded in your narrative.'
            )
        compliance_block = f"""
COMPLIANCE CAP CONTEXT — YOU MUST ADDRESS THIS:
{escalation_note}
Active compliance gaps:
{chr(10).join("- " + r for r in rec_result["cap_reasons"])}

CRITICAL INSTRUCTION: If ITAR is missing and applicable, you must state explicitly:
"This supplier is disqualified from ITAR-relevant work until registration is obtained."
Do not soften compliance language. These are program-level risks, not suggestions.
"""

    prompt = f"""You are a senior sourcing analyst writing a structured supplier evaluation brief for an aerospace and defense procurement team. Your output will be presented directly to program managers and sourcing leadership.

SCORING CONTEXT:
- Mode: {mode} (Performance weight: {int(layer_w['performance']*100)}% / Risk weight: {int(layer_w['risk']*100)}%)
- Commodity Profile: {score_result["commodity_profile"]}
- Score Confidence: {confidence["confidence_label"]} ({confidence["confidence_score"]:.0f}/100)

SUPPLIER PROFILE:
- Supplier: {inputs.supplier_name}
- Commodity: {inputs.commodity}
- Country: {inputs.country} (Geographic Risk: Tier {geo_tier} — {geo_label})
- Supplier Size: {inputs.supplier_size.value}
- Annual Spend: {"${:,.0f}".format(inputs.annual_spend_usd) if inputs.annual_spend_usd else "Not provided"}

COMPUTED SCORES — do not alter these numbers under any circumstances:
- Composite Score: {score_result["composite_score"]} / 100
- Performance Score: {score_result["performance_score"]} / 100
- Risk & Resilience Score: {score_result["risk_score"]} / 100
- Rating Band: {score_result["rating_band"]["label"]}

PERFORMANCE DIMENSION SCORES (0-100):
- On-Time Delivery ({inputs.otd_pct}% OTD): {perf_dims["otd"]}
- Quality ({quality_ppm:.0f} PPM): {perf_dims["quality"]}
- Responsiveness ({inputs.avg_response_days} day avg response): {perf_dims["responsiveness"]}
- Cost Stability ({inputs.ppv_pct:+.1f}% PPV): {perf_dims["cost_stability"]}

RISK DIMENSION SCORES (0-100):
- Single-Source Exposure (single source: {inputs.single_source}, backup sources: {inputs.backup_count}): {risk_dims["single_source"]}
- Geographic Concentration ({inputs.country}, Tier {geo_tier}): {risk_dims["geo"]}
- Financial Fragility (size: {inputs.supplier_size.value}, concern: {inputs.financial_concern}, volatility: {inputs.price_volatility.value}): {risk_dims["financial"]}
- Lead Time Volatility ({inputs.lead_time_variance_pct}% variance): {risk_dims["lead_time"]}
- Operational Redundancy (multiple sites: {inputs.multiple_sites}): {risk_dims["redundancy"]}

COMPLIANCE STATUS:
{comp_sum}
{compliance_block}
FINAL RECOMMENDATION (deterministic and final — your narrative must be consistent with this):
{rec_result["final_recommendation"]}

CRITICAL INSTRUCTION: If your narrative implies a different recommendation than the one shown above, that is a defect. The recommendation is fixed by the scoring engine. Your job is to explain it, not question it.

ANALYST NOTES:
{inputs.analyst_notes.strip() if inputs.analyst_notes.strip() else "None provided."}

---

Write a structured supplier evaluation brief with exactly these four sections.
Be specific and direct. Reference actual scores and input values. No generic filler. No em dashes.

1. SUPPLIER SUMMARY
2-3 sentences characterizing this supplier's overall profile. Reference the rating band, scoring mode, confidence level, and the single most important factor driving the composite score.

2. KEY STRENGTHS
2-3 specific strengths tied directly to the highest-scoring dimensions. Only list strengths supported by the data.

3. PRIMARY RISK FACTORS
The 2-3 highest-risk signals in order of severity. If compliance gaps were flagged, lead with them and state their program-level implications directly. Do not hedge compliance language.

4. SUGGESTED IMPROVEMENT ACTIONS
3-5 specific, actionable recommendations tied to the lowest-scoring dimensions or compliance gaps. Concrete enough to bring into a supplier review meeting. Format each as a clear directive.

Do not add a fifth "Sourcing Recommendation" section — that is rendered separately by the engine.
Keep the entire response under 420 words. Plain language. No em dashes. No bullet points — use numbered lists for improvement actions."""

    return prompt


def build_comparison_prompt(suppliers: list) -> str:
    """
    Builds a comparative analysis prompt for 2-5 suppliers in the session table.
    Each supplier is a dict from get_full_analysis().
    """
    supplier_summaries = []
    for i, s in enumerate(suppliers):
        sr = s["score_result"]
        rr = s["rec_result"]
        supplier_summaries.append(
            f"Supplier {i+1}: {sr['supplier_name']} | "
            f"Composite: {sr['composite_score']} ({sr['rating_band']['label']}) | "
            f"Performance: {sr['performance_score']} | "
            f"Risk: {sr['risk_score']} | "
            f"Recommendation: {rr['final_recommendation']} | "
            f"Geo: {sr['risk_detail']['geo_tier_label'][0]} risk"
        )

    prompt = f"""You are a senior sourcing analyst comparing {len(suppliers)} suppliers evaluated in the same session.

SUPPLIER COMPARISON DATA:
{chr(10).join(supplier_summaries)}

Write a single paragraph (4-6 sentences) that:
1. Identifies the strongest overall supplier and why
2. Calls out the most meaningful tradeoff between the top two options
3. Flags any supplier that should be disqualified or deprioritized and why
4. States which supplier represents the best long-term sourcing decision

Be direct and specific. Reference actual scores. No em dashes. No generic observations."""

    return prompt


def generate_narrative(
    inputs: SupplierInputs,
    score_result: dict,
    compliance_flags: list,
    rec_result: dict,
) -> str:
    try:
        client = anthropic.Anthropic()
        prompt = build_prompt(inputs, score_result, compliance_flags, rec_result)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception:
        return AI_FALLBACK


def generate_comparison_narrative(suppliers: list) -> str:
    """Generates one comparative paragraph for 2-5 suppliers in session table."""
    if len(suppliers) < 2:
        return ""
    try:
        client = anthropic.Anthropic()
        prompt = build_comparison_prompt(suppliers)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception:
        return ""


def get_full_analysis(inputs: SupplierInputs) -> dict:
    """
    Full pipeline: validate -> score -> compliance -> recommendation -> narrative.
    score_supplier() assumes pre-validated inputs — validation enforced here.
    """
    errors = inputs.validate()
    if errors:
        raise ValueError(f"Input validation failed: {'; '.join(errors)}")

    score_result     = score_supplier(inputs)
    compliance_flags = evaluate_compliance(inputs)
    rec_result       = get_recommendation(
                           score_result["composite_score"], inputs, compliance_flags
                       )
    narrative        = generate_narrative(inputs, score_result, compliance_flags, rec_result)

    return {
        "score_result":     score_result,
        "compliance_flags": compliance_flags,
        "rec_result":       rec_result,
        "narrative":        narrative,
    }
