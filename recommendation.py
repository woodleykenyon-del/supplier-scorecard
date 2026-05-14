"""
recommendation.py — Supplier Performance & Risk Scorecard
Deterministic recommendation engine. Ordinal cap logic applied after
score-based recommendation. AI only explains the result.

cap_triggered: any compliance cap was active (narrative must surface this).
cap_escalated: cap actually increased severity beyond score-based result.
Intentionally separate — see Opus QC review, Issue 1.
"""

from models import Recommendation, SupplierInputs
from compliance import get_active_caps, ComplianceFlag


def recommendation_from_score(composite: float) -> Recommendation:
    """Base recommendation from composite score. Ordinal enum — never compare strings."""
    if composite >= 85:
        return Recommendation.EXPAND
    elif composite >= 70:
        return Recommendation.MAINTAIN
    elif composite >= 55:
        return Recommendation.CORRECTIVE_ACTION
    else:
        return Recommendation.RE_SOURCE


def apply_compliance_caps(
    base_rec: Recommendation,
    inputs: SupplierInputs,
    flags: list,
) -> tuple:
    """
    Apply compliance caps to base recommendation.
    Caps never reduce severity — only increase it.
    cap_reasons collected for ALL triggered caps regardless of severity change,
    so the narrative can surface compliance gaps even when they don't escalate.
    """
    active_caps = get_active_caps(inputs, flags)
    cap_reasons = []
    final_rec = base_rec

    for cap in active_caps:
        cap_rec = cap["cap"]
        # Always record the reason — used by narrative regardless of escalation
        cap_reasons.append(_cap_reason(cap["cert"]))
        # Only escalate if cap is more severe than current recommendation
        if cap_rec.value > final_rec.value:
            final_rec = cap_rec

    return final_rec, cap_reasons


def _cap_reason(cert_key: str) -> str:
    reasons = {
        "itar":           "Missing ITAR registration (applicable to this work). Caps recommendation at Issue corrective action plan.",
        "as9100":         "Missing AS9100 certification. Caps recommendation at Maintain with monitoring.",
        "cmmc_below_2":   "CMMC below Level 2 (DoD work applicable). Caps recommendation at Maintain with monitoring.",
        "nadcap_missing": "Missing NADCAP accreditation (applicable process). Caps recommendation at Issue corrective action plan.",
    }
    return reasons.get(cert_key, f"Compliance gap ({cert_key}) noted.")


def get_recommendation(
    composite: float,
    inputs: SupplierInputs,
    flags: list,
) -> dict:
    """
    Full recommendation pipeline.
    cap_triggered: use this in narrative and UI to surface compliance gaps.
    cap_escalated: use this to explain when compliance overrode score-based result.
    """
    base = recommendation_from_score(composite)
    final, cap_reasons = apply_compliance_caps(base, inputs, flags)

    return {
        "base_recommendation":  base.label(),
        "final_recommendation": final.label(),
        "cap_triggered":        len(cap_reasons) > 0,
        "cap_escalated":        final.value > base.value,
        "cap_reasons":          cap_reasons,
        "recommendation_index": final.value,
    }
