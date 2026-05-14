"""
compliance.py — Supplier Performance & Risk Scorecard
Compliance flag evaluation. Flags drive UI display.
COMPLIANCE_CAPS in models.py drives recommendation action.
These are intentionally separate: flags = display, caps = action.
"""

from dataclasses import dataclass
from models import SupplierInputs, Recommendation, COMPLIANCE_CAPS


@dataclass
class ComplianceFlag:
    cert:    str
    status:  str    # "pass" | "warning" | "critical" | "info"
    label:   str
    detail:  str
    color:   str
    icon:    str
    tag:     str = ""   # Optional badge: "DISQUALIFYING", "BASELINE EXPECTATION", etc.


def evaluate_compliance(inputs: SupplierInputs) -> list:
    flags = []

    # AS9100 — always evaluated
    if inputs.as9100:
        flags.append(ComplianceFlag(
            cert="AS9100", status="pass",
            label="AS9100 Certified",
            detail="Quality management system meets aerospace standard.",
            color="#2E7D32", icon="✓",
        ))
    else:
        flags.append(ComplianceFlag(
            cert="AS9100", status="warning",
            label="AS9100 Not Certified",
            detail="Supplier does not hold AS9100 certification. This is a baseline expectation in aerospace and defense sourcing.",
            color="#F57F17", icon="⚠",
            tag="BASELINE EXPECTATION",
        ))

    # ITAR — only when applicable
    if inputs.itar_applicable:
        if inputs.itar:
            flags.append(ComplianceFlag(
                cert="ITAR", status="pass",
                label="ITAR Registered",
                detail="Supplier is registered with the U.S. State Department for defense-related articles and services.",
                color="#2E7D32", icon="✓",
            ))
        else:
            flags.append(ComplianceFlag(
                cert="ITAR", status="critical",
                label="ITAR Not Registered",
                detail="Supplier is not ITAR registered. This is a disqualifying condition for most defense programs. Do not award ITAR-relevant work without resolving this gap.",
                color="#B71C1C", icon="✗",
                tag="DISQUALIFYING",
            ))
    else:
        flags.append(ComplianceFlag(
            cert="ITAR", status="info",
            label="ITAR — Not Applicable",
            detail="ITAR registration not required for this scope of work.",
            color="#9E9E9E", icon="—",
        ))

    # CMMC — only when DoD work applicable
    if inputs.dod_applicable:
        if inputs.cmmc_level >= 3:
            flags.append(ComplianceFlag(
                cert="CMMC", status="pass",
                label="CMMC Level 3",
                detail="Supplier meets the highest DoD cybersecurity maturity tier. Qualified for most-sensitive program work.",
                color="#2E7D32", icon="✓",
                tag="HIGHEST TIER",
            ))
        elif inputs.cmmc_level == 2:
            flags.append(ComplianceFlag(
                cert="CMMC", status="pass",
                label="CMMC Level 2",
                detail="Supplier meets DoD cybersecurity requirements for controlled unclassified information (CUI).",
                color="#2E7D32", icon="✓",
            ))
        elif inputs.cmmc_level == 1:
            flags.append(ComplianceFlag(
                cert="CMMC", status="warning",
                label="CMMC Level 1 Only",
                detail="Level 2 is required for programs involving CUI. Level 1 is insufficient for most DoD subcontract work.",
                color="#F57F17", icon="⚠",
            ))
        else:
            flags.append(ComplianceFlag(
                cert="CMMC", status="warning",
                label="No CMMC Certification",
                detail="Supplier has no CMMC certification. This limits eligibility for DoD contract work involving CUI.",
                color="#F57F17", icon="⚠",
            ))
    else:
        flags.append(ComplianceFlag(
            cert="CMMC", status="info",
            label="CMMC — Not Applicable",
            detail="DoD cybersecurity requirements not applicable to this scope of work.",
            color="#9E9E9E", icon="—",
        ))

    # NADCAP — only when applicable
    if inputs.nadcap_applicable:
        if inputs.nadcap:
            flags.append(ComplianceFlag(
                cert="NADCAP", status="pass",
                label="NADCAP Accredited",
                detail="Supplier holds NADCAP accreditation for applicable special processes.",
                color="#2E7D32", icon="✓",
            ))
        else:
            flags.append(ComplianceFlag(
                cert="NADCAP", status="warning",
                label="NADCAP Not Accredited",
                detail="Supplier performs special processes but does not hold NADCAP accreditation. Verify whether program requirements mandate it.",
                color="#E65100", icon="⚠",
            ))
    else:
        # Supplier holds NADCAP but it's not required — show as positive capability signal
        if inputs.nadcap:
            flags.append(ComplianceFlag(
                cert="NADCAP", status="pass",
                label="NADCAP Held (Not Required)",
                detail="Supplier holds NADCAP accreditation beyond the requirements of this scope. Indicates broader process capability.",
                color="#2E7D32", icon="✓",
                tag="ADDITIONAL CAPABILITY",
            ))
        else:
            flags.append(ComplianceFlag(
                cert="NADCAP", status="info",
                label="NADCAP — Not Applicable",
                detail="No special process accreditation required for this scope of work.",
                color="#9E9E9E", icon="—",
            ))

    return flags


def get_active_caps(inputs: SupplierInputs, flags: list) -> list:
    """
    Returns active compliance caps as dicts with cert_key and cap Recommendation.
    Applicability is checked before triggering any cap.
    Display (flags) and action (caps) are intentionally separate systems.
    """
    caps = []
    for cert_key, applicability_key, cap_rec in COMPLIANCE_CAPS:
        if applicability_key is not None:
            if not getattr(inputs, applicability_key, False):
                continue

        triggered = False
        if cert_key == "itar" and not inputs.itar and inputs.itar_applicable:
            triggered = True
        elif cert_key == "as9100" and not inputs.as9100:
            triggered = True
        elif cert_key == "cmmc_below_2" and inputs.cmmc_level < 2 and inputs.dod_applicable:
            triggered = True
        elif cert_key == "nadcap_missing" and not inputs.nadcap and inputs.nadcap_applicable:
            triggered = True

        if triggered:
            caps.append({"cert": cert_key, "cap": cap_rec})

    return caps


def has_critical_flags(flags: list) -> bool:
    """Used by UI for display logic. Does not drive recommendation caps."""
    return any(f.status == "critical" for f in flags)


def has_warning_flags(flags: list) -> bool:
    return any(f.status == "warning" for f in flags)


def compliance_summary(flags: list) -> str:
    critical = [f for f in flags if f.status == "critical"]
    warnings = [f for f in flags if f.status == "warning"]
    if critical:
        certs = ", ".join(f.cert for f in critical)
        return f"Critical compliance gap(s): {certs}. Resolve before awarding work."
    elif warnings:
        certs = ", ".join(f.cert for f in warnings)
        return f"Compliance warning(s): {certs}. Review before program award."
    return "All applicable compliance requirements met."
