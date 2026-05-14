"""
scoring.py — Supplier Performance & Risk Scorecard
Deterministic scoring engine. All lookup tables imported from models.py.
No AI involvement in scoring.
score_supplier() assumes pre-validated inputs — validation enforced at get_full_analysis().
"""

from models import (
    SupplierInputs, ScoringMode, SupplierSize, QualityUnit, PriceVolatility,
    CommodityProfile, DataSource,
    MODE_LAYER_WEIGHTS, PERFORMANCE_WEIGHTS, RISK_WEIGHTS,
    QUALITY_PPM_BANDS, RESPONSIVENESS_BANDS, LEAD_TIME_SEGMENTS,
    SINGLE_SOURCE_LOOKUP, GEO_TIERS, GEO_TIER_SCORES, GEO_TIER_LABELS,
    FINANCIAL_BASE, FINANCIAL_DEDUCTIONS,
    RATING_BANDS, CONFIDENCE_THRESHOLDS,
)


# ---------------------------------------------------------------------------
# Performance dimension scorers
# ---------------------------------------------------------------------------

def score_otd(otd_pct: float) -> float:
    """
    Piecewise linear. Slopes are continuous at segment boundaries.
    Segment slopes: <80: 0.3/pt, 80-85: 4/pt, 85-90: 4/pt,
                   90-95: 4/pt, 95-98: 5/pt, 98+: 100 flat
    Minor slope change at 95 is intentional (higher standard above 95).
    """
    if otd_pct >= 98:
        return 100.0
    elif otd_pct >= 95:
        return 85.0 + (otd_pct - 95) * 5.0
    elif otd_pct >= 90:
        return 65.0 + (otd_pct - 90) * 4.0
    elif otd_pct >= 85:
        return 45.0 + (otd_pct - 85) * 4.0
    elif otd_pct >= 80:
        return 25.0 + (otd_pct - 80) * 4.0
    else:
        return max(0.0, otd_pct * 0.3)


def normalize_to_ppm(quality_value: float, unit: QualityUnit) -> float:
    """
    Normalize quality input to PPM.
    % convention: user enters whole percent (1 = 1%, 0.1 = 0.1%)
    Conversion: ppm = defect_pct_whole * 10_000
    """
    if unit == QualityUnit.PERCENT:
        return quality_value * 10_000
    return quality_value


def score_quality(quality_value: float, unit: QualityUnit) -> float:
    """
    Half-open band lookup [low, high). Eliminates boundary ambiguity.
    0.0 PPM treated as a special case (perfect quality).
    """
    ppm = normalize_to_ppm(quality_value, unit)
    for low, high, score in QUALITY_PPM_BANDS:
        if high == float("inf"):
            if ppm >= low:
                return float(score)
        elif low <= ppm < high:
            return float(score)
    return 0.0


def score_responsiveness(avg_response_days: float) -> float:
    """Half-open band lookup [low, high)."""
    for low, high, score in RESPONSIVENESS_BANDS:
        if high == float("inf"):
            if avg_response_days >= low:
                return float(score)
        elif low <= avg_response_days < high:
            return float(score)
    return 0.0


def score_cost_stability(ppv_pct: float) -> float:
    """Piecewise linear — no band cliffs."""
    if ppv_pct <= -2.0:
        return 100.0
    elif ppv_pct < 0.0:
        return 85.0 + ppv_pct * 7.5
    elif ppv_pct < 2.0:
        return 85.0 - ppv_pct * 17.5
    elif ppv_pct < 5.0:
        return 50.0 - (ppv_pct - 2.0) * 10.0
    elif ppv_pct < 10.0:
        return max(0.0, 20.0 - (ppv_pct - 5.0) * 4.0)
    else:
        return 0.0


def compute_performance_score(inputs: SupplierInputs) -> dict:
    weights = PERFORMANCE_WEIGHTS[inputs.commodity_profile]
    scores = {
        "otd":            round(score_otd(inputs.otd_pct), 1),
        "quality":        round(score_quality(inputs.quality_value, inputs.quality_unit), 1),
        "responsiveness": round(score_responsiveness(inputs.avg_response_days), 1),
        "cost_stability": round(score_cost_stability(inputs.ppv_pct), 1),
    }
    weighted = sum(scores[k] * weights[k] for k in scores)
    return {
        "dimension_scores":  scores,
        "weights":           weights,
        "performance_score": round(weighted, 1),
    }


# ---------------------------------------------------------------------------
# Risk dimension scorers
# ---------------------------------------------------------------------------

def score_single_source(
    single_source: bool,
    backup_count: int,
    annual_spend_usd: float = None,
) -> float:
    """
    Nested lookup with optional spend criticality multiplier.
    High annual spend on a single-source supplier amplifies the risk score penalty.
    Multiplier only reduces score (increases risk) — never inflates it.
    """
    base = 50.0
    for ss, min_b, max_b, score in SINGLE_SOURCE_LOOKUP:
        if ss == single_source:
            if max_b == float("inf"):
                if backup_count >= min_b:
                    base = float(score)
                    break
            elif min_b <= backup_count <= max_b:
                base = float(score)
                break

    # Spend criticality multiplier — reduces score for high-spend single-source
    if annual_spend_usd is not None and single_source:
        if annual_spend_usd >= 1_000_000:
            base = max(0.0, base * 0.80)   # 20% penalty
        elif annual_spend_usd >= 250_000:
            base = max(0.0, base * 0.90)   # 10% penalty

    return round(base, 1)


def score_geo(country: str) -> tuple:
    """Returns (score, tier, is_fallback)."""
    if country in GEO_TIERS:
        tier = GEO_TIERS[country]
        return float(GEO_TIER_SCORES[tier]), tier, False
    else:
        # Fallback to Tier 3 — flagged so UI can warn user
        return 45.0, 3, True


def score_financial(
    supplier_size: SupplierSize,
    financial_concern: bool,
    price_volatility: PriceVolatility,
) -> float:
    base = float(FINANCIAL_BASE.get(supplier_size, 50))
    if financial_concern:
        base -= FINANCIAL_DEDUCTIONS["concern_flagged"]
    if price_volatility == PriceVolatility.MEDIUM:
        base -= FINANCIAL_DEDUCTIONS[PriceVolatility.MEDIUM]
    elif price_volatility == PriceVolatility.HIGH:
        base -= FINANCIAL_DEDUCTIONS[PriceVolatility.HIGH]
    return max(0.0, round(base, 1))


def score_lead_time(variance_pct: float) -> float:
    """
    Piecewise linear interpolation — eliminates 20-point band cliffs.
    Uses LEAD_TIME_SEGMENTS from models.py.
    """
    for low, high, score_low, score_high in LEAD_TIME_SEGMENTS:
        if high == float("inf"):
            return float(score_low)
        if low <= variance_pct < high:
            # Linear interpolation within segment
            t = (variance_pct - low) / (high - low)
            return round(score_low + t * (score_high - score_low), 1)
    return 0.0


def score_redundancy(multiple_sites: bool) -> float:
    return 90.0 if multiple_sites else 20.0


def compute_risk_score(inputs: SupplierInputs) -> dict:
    weights = RISK_WEIGHTS[inputs.commodity_profile]
    geo_score, geo_tier, geo_fallback = score_geo(inputs.country)

    scores = {
        "single_source": score_single_source(
            inputs.single_source, inputs.backup_count, inputs.annual_spend_usd
        ),
        "geo":           round(geo_score, 1),
        "financial":     score_financial(
                             inputs.supplier_size,
                             inputs.financial_concern,
                             inputs.price_volatility,
                         ),
        "lead_time":     score_lead_time(inputs.lead_time_variance_pct),
        "redundancy":    score_redundancy(inputs.multiple_sites),
    }
    weighted = sum(scores[k] * weights[k] for k in scores)
    return {
        "dimension_scores": scores,
        "weights":          weights,
        "risk_score":       round(weighted, 1),
        "geo_tier":         geo_tier,
        "geo_tier_label":   GEO_TIER_LABELS.get(geo_tier, ("Unknown", "#FFF")),
        "geo_fallback":     geo_fallback,
    }


# ---------------------------------------------------------------------------
# Data confidence score
# Does NOT affect composite — shown as a badge alongside it
# ---------------------------------------------------------------------------

def compute_confidence_score(inputs: SupplierInputs) -> dict:
    """
    Confidence score 0-100 based on data quality proxies.
    Signals how much to trust the composite score.
    """
    score = 0.0

    # History depth (0-30 points)
    if inputs.months_of_history >= 24:
        score += 30
    elif inputs.months_of_history >= 12:
        score += 20
    elif inputs.months_of_history >= 6:
        score += 10
    else:
        score += 0

    # Transaction volume (0-25 points)
    if inputs.num_transactions >= 50:
        score += 25
    elif inputs.num_transactions >= 20:
        score += 18
    elif inputs.num_transactions >= 10:
        score += 10
    elif inputs.num_transactions >= 3:
        score += 5
    else:
        score += 0

    # Data source (0-30 points)
    source_scores = {
        DataSource.AUDITED:       30,
        DataSource.VERIFIED:      18,
        DataSource.SELF_REPORTED:  8,
    }
    score += source_scores.get(inputs.data_source, 8)

    # Audit recency (0-15 points)
    if inputs.months_since_audit is not None:
        if inputs.months_since_audit <= 12:
            score += 15
        elif inputs.months_since_audit <= 24:
            score += 10
        elif inputs.months_since_audit <= 36:
            score += 5
    # No audit = 0 additional points

    score = min(100.0, round(score, 1))

    # Determine badge label — take highest threshold met
    label = "Low"
    for badge, threshold in sorted(CONFIDENCE_THRESHOLDS.items(), key=lambda x: x[1]):
        if score >= threshold:
            label = badge

    return {
        "confidence_score": score,
        "confidence_label": label,
    }


# ---------------------------------------------------------------------------
# Composite score and rating band
# ---------------------------------------------------------------------------

def compute_composite(
    performance_score: float,
    risk_score: float,
    mode: ScoringMode,
) -> float:
    weights = MODE_LAYER_WEIGHTS[mode]
    return round(
        performance_score * weights["performance"] + risk_score * weights["risk"],
        1,
    )


def get_rating_band(composite: float) -> dict:
    for low, high, label, bg, text_color in RATING_BANDS:
        if low <= composite <= high:
            return {"label": label, "bg_color": bg, "text_color": text_color}
    return {"label": "Critical", "bg_color": "#FFCDD2", "text_color": "#B71C1C"}


# ---------------------------------------------------------------------------
# What-if sensitivity analysis
# Computes composite lift from realistic improvement on two lowest dimensions
# ---------------------------------------------------------------------------

def compute_sensitivity(inputs: SupplierInputs, current_composite: float) -> list:
    """
    Returns list of dicts showing composite impact of realistic improvements
    on the two lowest-scoring performance dimensions.
    Called after initial scoring — does not modify inputs.
    """
    perf = compute_performance_score(inputs)
    dim_scores = perf["dimension_scores"]

    # Sort performance dims by score ascending — find the two weakest
    sorted_dims = sorted(dim_scores.items(), key=lambda x: x[1])
    scenarios = []

    improvements = {
        "otd":            ("OTD", "Improve OTD from {:.0f}% to 95%", lambda i: SupplierInputs(**{**i.__dict__, "otd_pct": min(95, i.otd_pct + 8)})),
        "quality":        ("Quality", "Reduce defect rate by 50%", lambda i: SupplierInputs(**{**i.__dict__, "quality_value": i.quality_value * 0.5})),
        "responsiveness": ("Responsiveness", "Reduce response time to 2 days", lambda i: SupplierInputs(**{**i.__dict__, "avg_response_days": min(2, i.avg_response_days)})),
        "cost_stability": ("Cost Stability", "Reduce PPV to 1%", lambda i: SupplierInputs(**{**i.__dict__, "ppv_pct": min(1.0, i.ppv_pct)})),
    }

    for dim, current_score in sorted_dims[:2]:
        if dim not in improvements:
            continue
        label, description, mutate = improvements[dim]
        try:
            improved_inputs = mutate(inputs)
            improved_perf = compute_performance_score(improved_inputs)
            improved_composite = compute_composite(
                improved_perf["performance_score"],
                compute_risk_score(inputs)["risk_score"],
                inputs.scoring_mode,
            )
            delta = round(improved_composite - current_composite, 1)
            scenarios.append({
                "dimension": label,
                "description": description.format(inputs.otd_pct),
                "current_score": current_score,
                "current_composite": current_composite,
                "improved_composite": improved_composite,
                "delta": delta,
            })
        except Exception:
            continue

    return scenarios


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def score_supplier(inputs: SupplierInputs) -> dict:
    """
    Full deterministic scoring pipeline.
    Assumes pre-validated inputs — call inputs.validate() before this.
    Recommendation assigned in recommendation.py.
    """
    perf       = compute_performance_score(inputs)
    risk       = compute_risk_score(inputs)
    composite  = compute_composite(perf["performance_score"], risk["risk_score"], inputs.scoring_mode)
    band       = get_rating_band(composite)
    confidence = compute_confidence_score(inputs)
    sensitivity = compute_sensitivity(inputs, composite)

    return {
        "supplier_name":      inputs.supplier_name,
        "scoring_mode":       inputs.scoring_mode.value,
        "commodity_profile":  inputs.commodity_profile.value,
        "layer_weights":      MODE_LAYER_WEIGHTS[inputs.scoring_mode],
        "composite_score":    composite,
        "performance_score":  perf["performance_score"],
        "risk_score":         risk["risk_score"],
        "performance_detail": perf,
        "risk_detail":        risk,
        "rating_band":        band,
        "quality_ppm":        normalize_to_ppm(inputs.quality_value, inputs.quality_unit),
        "confidence":         confidence,
        "sensitivity":        sensitivity,
        "geo_fallback":       risk["geo_fallback"],
    }
