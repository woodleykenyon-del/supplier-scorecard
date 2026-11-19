"""Evaluation briefs built from the supplier scorecard's computed results."""

from compliance import evaluate_compliance
from models import SupplierInputs
from recommendation import get_recommendation
from scoring import score_supplier


def summarize_evaluation(score: dict, recommendation: dict) -> str:
    """Explain the final recommendation and the most useful modeled improvement."""
    paragraphs = [
        f"The {score['scoring_mode']} evaluation scores "
        f"{score['composite_score']:.1f}/100 overall, with "
        f"{score['performance_score']:.1f}/100 for performance and "
        f"{score['risk_score']:.1f}/100 for risk resilience. "
        f"Data confidence is {score['confidence']['confidence_label'].lower()}."
    ]

    decision = f"Recommended action: {recommendation['final_recommendation']}."
    if recommendation["cap_escalated"]:
        decision += (
            f" Compliance raised the severity from “{recommendation['base_recommendation']}”."
        )
    if recommendation["cap_triggered"]:
        decision += " " + " ".join(recommendation["cap_reasons"])
    paragraphs.append(decision)

    improvement = max(score["sensitivity"], key=lambda scenario: scenario["delta"], default=None)
    if improvement and improvement["delta"] > 0:
        paragraphs.append(
            f"{improvement['dimension']} has the largest positive effect among the "
            f"modeled improvements, adding {improvement['delta']:.1f} points to the composite."
        )

    return "\n\n".join(paragraphs)


def summarize_comparison(suppliers: list) -> str:
    """Report the current score leaders independently of the table sort order."""
    if len(suppliers) < 2:
        return ""

    scores = [supplier["score_result"] for supplier in suppliers]
    settings = {(score["scoring_mode"], score["commodity_profile"]) for score in scores}
    if len(settings) > 1:
        return (
            "These suppliers were scored under different modes or commodity profiles. "
            "Use a common setting to compare their composite scores directly."
        )

    lines = []
    for label, key in (
        ("Composite", "composite_score"),
        ("Performance", "performance_score"),
        ("Risk resilience", "risk_score"),
    ):
        highest = max(score[key] for score in scores)
        names = sorted((score["supplier_name"] for score in scores if score[key] == highest),
                       key=lambda name: (name.casefold(), name))
        leaders = ", ".join(names)
        suffix = " (tied)" if len(names) > 1 else ""
        lines.append(f"{label}: {leaders} at {highest:.1f}/100{suffix}.")

    return "\n".join(lines)


def get_full_analysis(inputs: SupplierInputs) -> dict:
    """Validate inputs, score the supplier, and explain the computed outcome."""
    errors = inputs.validate()
    if errors:
        raise ValueError(f"Input validation failed: {'; '.join(errors)}")

    score_result = score_supplier(inputs)
    compliance_flags = evaluate_compliance(inputs)
    rec_result = get_recommendation(score_result["composite_score"], inputs, compliance_flags)

    return {
        "score_result": score_result,
        "compliance_flags": compliance_flags,
        "rec_result": rec_result,
        "narrative": summarize_evaluation(score_result, rec_result),
    }
