"""
test_engine.py — Supplier Performance & Risk Scorecard
Assert-based test suite. Exits nonzero on failure.
Run: python test_engine.py
"""

import sys
from models import (
    SupplierInputs, ScoringMode, SupplierSize, QualityUnit,
    PriceVolatility, Recommendation, CommodityProfile, DataSource
)
from scoring import (
    score_supplier, normalize_to_ppm, score_quality, score_responsiveness,
    score_lead_time, score_financial, compute_confidence_score
)
from compliance import evaluate_compliance, compliance_summary, has_critical_flags
from recommendation import get_recommendation

PASS = 0
FAIL = 0


def check(label, actual, expected):
    global PASS, FAIL
    if actual == expected:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}")
        print(f"        expected: {expected!r}")
        print(f"        got:      {actual!r}")
        FAIL += 1


def check_approx(label, actual, expected, tol=0.5):
    global PASS, FAIL
    if abs(actual - expected) <= tol:
        print(f"  PASS  {label} ({actual})")
        PASS += 1
    else:
        print(f"  FAIL  {label}")
        print(f"        expected ~{expected}, got {actual}")
        FAIL += 1


def section(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print('='*65)


def base_inputs(**overrides):
    defaults = dict(
        supplier_name="Test Supplier",
        commodity="Machined Parts",
        commodity_profile=CommodityProfile.MACHINED_PARTS,
        country="United States",
        supplier_size=SupplierSize.MID,
        scoring_mode=ScoringMode.BALANCED,
        otd_pct=97,
        quality_value=50,
        quality_unit=QualityUnit.PPM,
        avg_response_days=1.5,
        ppv_pct=-0.5,
        single_source=False,
        backup_count=2,
        lead_time_variance_pct=8,
        multiple_sites=True,
        financial_concern=False,
        price_volatility=PriceVolatility.LOW,
        annual_spend_usd=None,
        as9100=True,
        itar=True,
        cmmc_level=2,
        nadcap=True,
        itar_applicable=True,
        dod_applicable=True,
        nadcap_applicable=True,
        months_of_history=24,
        num_transactions=30,
        data_source=DataSource.VERIFIED,
        months_since_audit=12,
        analyst_notes="",
    )
    defaults.update(overrides)
    return SupplierInputs(**defaults)


# ---------------------------------------------------------------------------
# TEST 1: PPM band boundary fixes — fractional PPM no longer falls through
# ---------------------------------------------------------------------------
section("TEST 1 — PPM band boundary fixes (Issue 1)")
check("0 PPM = 100",          score_quality(0, QualityUnit.PPM), 100.0)
check("0.5 PPM = 90",         score_quality(0.5, QualityUnit.PPM), 90.0)
check("99.9 PPM = 90",        score_quality(99.9, QualityUnit.PPM), 90.0)
check("100 PPM = 75",         score_quality(100, QualityUnit.PPM), 75.0)
check("100.5 PPM = 75",       score_quality(100.5, QualityUnit.PPM), 75.0)
check("500 PPM = 55",         score_quality(500, QualityUnit.PPM), 55.0)
check("10000 PPM = 0",        score_quality(10000, QualityUnit.PPM), 0.0)
check("0.005% = 50 PPM = 90", score_quality(0.005, QualityUnit.PERCENT), 90.0)
check("1% = 10000 PPM = 0",   score_quality(1.0, QualityUnit.PERCENT), 0.0)


# ---------------------------------------------------------------------------
# TEST 2: Lead time piecewise — no 20-point cliffs (Issue 2)
# ---------------------------------------------------------------------------
section("TEST 2 — Lead time piecewise interpolation (Issue 2)")
lt_4  = score_lead_time(4.0)
lt_5  = score_lead_time(5.0)
lt_6  = score_lead_time(6.0)
lt_10 = score_lead_time(10.0)
lt_11 = score_lead_time(11.0)

check("4% < 5% score",  lt_4 > lt_5, True)
check("5% > 6% score",  lt_5 > lt_6, True)
# Cliff check: difference between adjacent points should be < 5
check("No cliff at 5%",  abs(lt_5 - lt_6) <= 5, True)  # 5pt max step is the designed segment boundary
check("No cliff at 10%", abs(lt_10 - lt_11) < 5, True)
check_approx("5% ~ 80",  lt_5, 80, tol=1)
check_approx("10% ~ 55", lt_10, 55, tol=1)


# ---------------------------------------------------------------------------
# TEST 3: Responsiveness half-open bands (Issue 2)
# ---------------------------------------------------------------------------
section("TEST 3 — Responsiveness half-open bands")
check("0 days = 100",    score_responsiveness(0), 100.0)
check("0.9 days = 100",  score_responsiveness(0.9), 100.0)
check("1.0 days = 85",   score_responsiveness(1.0), 85.0)
check("1.9 days = 85",   score_responsiveness(1.9), 85.0)
check("2.0 days = 70",   score_responsiveness(2.0), 70.0)
check("14.0 days = 0",   score_responsiveness(14.0), 0.0)


# ---------------------------------------------------------------------------
# TEST 4: Validation bounds (Issue 4)
# ---------------------------------------------------------------------------
section("TEST 4 — Validation catches out-of-bounds inputs (Issue 4)")
bad = base_inputs(
    supplier_name="",
    otd_pct=110,
    avg_response_days=-1,
    backup_count=-2,
    cmmc_level=9,
    ppv_pct=150,
    quality_value=2_000_000,
    quality_unit=QualityUnit.PPM,
    lead_time_variance_pct=600,
)
errors = bad.validate()
check("Catches empty name",          any("name" in e.lower() for e in errors), True)
check("Catches OTD > 100",           any("OTD" in e for e in errors), True)
check("Catches negative response",   any("Response" in e for e in errors), True)
check("Catches negative backup",     any("Backup" in e for e in errors), True)
check("Catches bad CMMC",            any("CMMC" in e for e in errors), True)
check("Catches PPV > 100",           any("PPV" in e for e in errors), True)
check("Catches PPM > 1,000,000",     any("PPM" in e for e in errors), True)
check("Catches lead time > 500",     any("Lead time" in e for e in errors), True)


# ---------------------------------------------------------------------------
# TEST 5: Commodity unvalidated (Issue 5)
# ---------------------------------------------------------------------------
section("TEST 5 — Commodity field validation (Issue 5)")
bad2 = base_inputs(commodity="")
errors2 = bad2.validate()
check("Catches empty commodity", any("Commodity" in e for e in errors2), True)


# ---------------------------------------------------------------------------
# TEST 6: Preferred supplier full run
# ---------------------------------------------------------------------------
section("TEST 6 — Preferred supplier, all compliance, Balanced mode")
inp = base_inputs()
result = score_supplier(inp)
flags  = evaluate_compliance(inp)
rec    = get_recommendation(result["composite_score"], inp, flags)

check("Rating band", result["rating_band"]["label"], "Preferred")
check("Recommendation", rec["final_recommendation"], "Expand relationship")
check("cap_triggered", rec["cap_triggered"], False)
check("cap_escalated", rec["cap_escalated"], False)


# ---------------------------------------------------------------------------
# TEST 7: AS9100 missing — cap escalates Expand → Maintain
# ---------------------------------------------------------------------------
section("TEST 7 — High score, AS9100 missing, cap escalates to Maintain")
inp = base_inputs(
    otd_pct=99, quality_value=10, avg_response_days=0.5,
    ppv_pct=-1.5, backup_count=3, lead_time_variance_pct=3,
    as9100=False,
)
result = score_supplier(inp)
flags  = evaluate_compliance(inp)
rec    = get_recommendation(result["composite_score"], inp, flags)

check("cap_triggered", rec["cap_triggered"], True)
check("cap_escalated", rec["cap_escalated"], True)
check("Final rec", rec["final_recommendation"], "Maintain with monitoring")
check("Base rec was Expand", rec["base_recommendation"], "Expand relationship")


# ---------------------------------------------------------------------------
# TEST 8: Same-severity compliance trigger — triggered but not escalated
# ---------------------------------------------------------------------------
section("TEST 8 — Score = Maintain, AS9100 missing; cap_triggered not escalated")
inp = base_inputs(
    otd_pct=95, quality_value=200, avg_response_days=2,
    ppv_pct=0.5, backup_count=1, lead_time_variance_pct=12,
    multiple_sites=False, as9100=False,
)
result = score_supplier(inp)
flags  = evaluate_compliance(inp)
rec    = get_recommendation(result["composite_score"], inp, flags)

assert 70 <= result["composite_score"] <= 84, \
    f"Expected Acceptable band, got {result['composite_score']}"
check("cap_triggered", rec["cap_triggered"], True)
check("cap_escalated", rec["cap_escalated"], False)
check("Final rec", rec["final_recommendation"], "Maintain with monitoring")
check("AS9100 reason present", any("AS9100" in r for r in rec["cap_reasons"]), True)


# ---------------------------------------------------------------------------
# TEST 9: ITAR not applicable — no cap, no critical flag
# ---------------------------------------------------------------------------
section("TEST 9 — ITAR not applicable, missing ITAR should not cap")
inp = base_inputs(itar=False, itar_applicable=False)
flags  = evaluate_compliance(inp)
rec    = get_recommendation(score_supplier(inp)["composite_score"], inp, flags)
check("No ITAR critical flag", has_critical_flags(flags), False)
check("cap_triggered", rec["cap_triggered"], False)


# ---------------------------------------------------------------------------
# TEST 10: ITAR applicable and missing — critical flag, cap to corrective action
# ---------------------------------------------------------------------------
section("TEST 10 — ITAR applicable, missing → cap to Corrective Action")
inp = base_inputs(itar=False, itar_applicable=True)
result = score_supplier(inp)
flags  = evaluate_compliance(inp)
rec    = get_recommendation(result["composite_score"], inp, flags)

check("ITAR critical flag", has_critical_flags(flags), True)
check("cap_triggered", rec["cap_triggered"], True)
check("cap_escalated", rec["cap_escalated"], True)
check("Final rec", rec["final_recommendation"], "Issue corrective action plan")


# ---------------------------------------------------------------------------
# TEST 11: Mode effect — Risk Reduction shifts composite vs Balanced
# ---------------------------------------------------------------------------
section("TEST 11 — Mode effect: Risk Reduction lowers composite vs Balanced")
inp_bal  = base_inputs(
    scoring_mode=ScoringMode.BALANCED,
    single_source=True, backup_count=0, country="China",
    multiple_sites=False, financial_concern=True,
    price_volatility=PriceVolatility.HIGH,
)
inp_risk = base_inputs(
    scoring_mode=ScoringMode.RISK_REDUCTION,
    single_source=True, backup_count=0, country="China",
    multiple_sites=False, financial_concern=True,
    price_volatility=PriceVolatility.HIGH,
)
res_bal  = score_supplier(inp_bal)
res_risk = score_supplier(inp_risk)
check("Risk Reduction < Balanced composite",
      res_risk["composite_score"] < res_bal["composite_score"], True)


# ---------------------------------------------------------------------------
# TEST 12: Commodity profile shifts dimension weights
# ---------------------------------------------------------------------------
section("TEST 12 — Electronics profile weights geo more than Machined Parts")
from models import RISK_WEIGHTS
elec_geo_w    = RISK_WEIGHTS[CommodityProfile.ELECTRONICS]["geo"]
machined_geo_w = RISK_WEIGHTS[CommodityProfile.MACHINED_PARTS]["geo"]
check("Electronics weights geo more", elec_geo_w > machined_geo_w, True)


# ---------------------------------------------------------------------------
# TEST 13: PPM normalization
# ---------------------------------------------------------------------------
section("TEST 13 — Quality % to PPM normalization")
check("1.0% = 10,000 PPM",    normalize_to_ppm(1.0, QualityUnit.PERCENT), 10_000)
check("0.1% = 1,000 PPM",     normalize_to_ppm(0.1, QualityUnit.PERCENT),  1_000)
check("5000 PPM passthrough",  normalize_to_ppm(5000, QualityUnit.PPM), 5000)


# ---------------------------------------------------------------------------
# TEST 14: Financial fragility scoring
# ---------------------------------------------------------------------------
section("TEST 14 — Financial fragility explicit scoring")
check("Large/no concern/low = 85",    score_financial(SupplierSize.LARGE, False, PriceVolatility.LOW), 85.0)
check("Small/concern/high = 0",       score_financial(SupplierSize.SMALL, True, PriceVolatility.HIGH), 0.0)
check("Mid/no concern/medium = 60",   score_financial(SupplierSize.MID, False, PriceVolatility.MEDIUM), 60.0)
check("Large/concern/low = 60",       score_financial(SupplierSize.LARGE, True, PriceVolatility.LOW), 60.0)


# ---------------------------------------------------------------------------
# TEST 15: Geo fallback flagged for unknown country
# ---------------------------------------------------------------------------
section("TEST 15 — Unknown country triggers geo_fallback flag")
inp = base_inputs(country="Atlantis")
result = score_supplier(inp)
check("geo_fallback = True", result["geo_fallback"], True)
check("Fallback tier = 3",   result["risk_detail"]["geo_tier"], 3)

# Czechia now mapped (was missing before)
inp2 = base_inputs(country="Czechia")
result2 = score_supplier(inp2)
check("Czechia mapped (no fallback)", result2["geo_fallback"], False)


# ---------------------------------------------------------------------------
# TEST 16: Confidence score logic
# ---------------------------------------------------------------------------
section("TEST 16 — Data confidence scoring")
inp_high = base_inputs(
    months_of_history=36, num_transactions=60,
    data_source=DataSource.AUDITED, months_since_audit=6,
)
inp_low = base_inputs(
    months_of_history=2, num_transactions=2,
    data_source=DataSource.SELF_REPORTED, months_since_audit=None,
)
conf_high = compute_confidence_score(inp_high)
conf_low  = compute_confidence_score(inp_low)
check("High confidence label", conf_high["confidence_label"], "High")
check("Low confidence label",  conf_low["confidence_label"], "Low")
check("High > Low score", conf_high["confidence_score"] > conf_low["confidence_score"], True)


# ---------------------------------------------------------------------------
# TEST 17: Spend criticality multiplier on single-source
# ---------------------------------------------------------------------------
section("TEST 17 — Spend criticality multiplier reduces single-source score")
from scoring import score_single_source
no_spend  = score_single_source(True, 0, annual_spend_usd=None)
low_spend = score_single_source(True, 0, annual_spend_usd=100_000)
high_spend = score_single_source(True, 0, annual_spend_usd=1_500_000)
check("No spend = base",          no_spend, 5.0)
check("High spend < no spend",    high_spend < no_spend, True)
check("Low spend >= high spend",  low_spend >= high_spend, True)


# ---------------------------------------------------------------------------
# TEST 18: NADCAP held but not required = positive signal
# ---------------------------------------------------------------------------
section("TEST 18 — NADCAP held but not applicable = positive capability flag")
inp = base_inputs(nadcap=True, nadcap_applicable=False)
flags = evaluate_compliance(inp)
nadcap_flag = next(f for f in flags if f.cert == "NADCAP")
check("NADCAP tag = ADDITIONAL CAPABILITY", nadcap_flag.tag, "ADDITIONAL CAPABILITY")
check("NADCAP status = pass", nadcap_flag.status, "pass")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*65}")
print(f"  Results: {PASS} passed, {FAIL} failed")
print('='*65)

if FAIL > 0:
    sys.exit(1)
