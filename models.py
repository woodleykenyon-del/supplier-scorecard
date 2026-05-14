"""
models.py — Supplier Performance & Risk Scorecard
Central source of truth for all constants, lookup tables, and input validation.
All scoring bands, mode weights, dimension weights, and cap rankings live here.
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ScoringMode(str, Enum):
    BALANCED             = "Balanced"
    PERFORMANCE_RECOVERY = "Performance Recovery"
    RISK_REDUCTION       = "Risk Reduction"


class SupplierSize(str, Enum):
    SMALL = "Small (<50)"
    MID   = "Mid (50-500)"
    LARGE = "Large (500+)"


class PriceVolatility(str, Enum):
    LOW    = "Low"
    MEDIUM = "Medium"
    HIGH   = "High"


class QualityUnit(str, Enum):
    PERCENT = "%"
    PPM     = "PPM"


class CommodityProfile(str, Enum):
    """
    Commodity-aware dimension weight nudges within each scoring layer.
    Layer weights (performance vs risk) remain user-controlled via ScoringMode.
    Dimension weights within each layer shift based on commodity type.
    """
    STANDARD         = "Standard"
    MACHINED_PARTS   = "Machined Parts"
    ELECTRONICS      = "Electronics"
    RAW_MATERIAL     = "Raw Material"
    CASTINGS_FORGINGS = "Castings / Forgings"


class DataSource(str, Enum):
    SELF_REPORTED = "Self-reported"
    VERIFIED      = "Third-party verified"
    AUDITED       = "Audited / on-site"


class Recommendation(int, Enum):
    """
    Ordinal ranking. Higher index = more severe action.
    Cap logic compares indices numerically — never compare strings.
    """
    EXPAND            = 0
    MAINTAIN          = 1
    CORRECTIVE_ACTION = 2
    RE_SOURCE         = 3

    def label(self) -> str:
        return {
            0: "Expand relationship",
            1: "Maintain with monitoring",
            2: "Issue corrective action plan",
            3: "Initiate re-sourcing evaluation",
        }[self.value]


# ---------------------------------------------------------------------------
# Mode weights — layer weights only
# Dimension weights within each layer are commodity-profile controlled
# ---------------------------------------------------------------------------

MODE_LAYER_WEIGHTS: dict = {
    ScoringMode.BALANCED: {
        "performance": 0.50,
        "risk":        0.50,
    },
    ScoringMode.PERFORMANCE_RECOVERY: {
        "performance": 0.70,
        "risk":        0.30,
    },
    ScoringMode.RISK_REDUCTION: {
        "performance": 0.30,
        "risk":        0.70,
    },
}


# ---------------------------------------------------------------------------
# Performance dimension weights by commodity profile (fixed across modes)
# Weights must sum to 1.0 per profile
# ---------------------------------------------------------------------------

PERFORMANCE_WEIGHTS: dict = {
    CommodityProfile.STANDARD: {
        "otd": 0.35, "quality": 0.30, "responsiveness": 0.20, "cost_stability": 0.15,
    },
    CommodityProfile.MACHINED_PARTS: {
        # Quality and lead time reliability are paramount for machined parts
        "otd": 0.35, "quality": 0.35, "responsiveness": 0.15, "cost_stability": 0.15,
    },
    CommodityProfile.ELECTRONICS: {
        # OTD and quality drive most electronics risk; cost is secondary
        "otd": 0.40, "quality": 0.35, "responsiveness": 0.15, "cost_stability": 0.10,
    },
    CommodityProfile.RAW_MATERIAL: {
        # Cost stability is higher-weight for commodities; OTD still matters
        "otd": 0.30, "quality": 0.25, "responsiveness": 0.15, "cost_stability": 0.30,
    },
    CommodityProfile.CASTINGS_FORGINGS: {
        # Quality escapes are catastrophic; lead time critical for long-lead items
        "otd": 0.35, "quality": 0.40, "responsiveness": 0.15, "cost_stability": 0.10,
    },
}


# ---------------------------------------------------------------------------
# Risk dimension weights by commodity profile (fixed across modes)
# Weights must sum to 1.0 per profile
# ---------------------------------------------------------------------------

RISK_WEIGHTS: dict = {
    CommodityProfile.STANDARD: {
        "single_source": 0.30, "geo": 0.25, "financial": 0.20,
        "lead_time": 0.15, "redundancy": 0.10,
    },
    CommodityProfile.MACHINED_PARTS: {
        # Single source and lead time volatility are highest risk for machined parts
        "single_source": 0.35, "geo": 0.20, "financial": 0.15,
        "lead_time": 0.20, "redundancy": 0.10,
    },
    CommodityProfile.ELECTRONICS: {
        # Geo concentration (China/Taiwan) and single source dominate electronics risk
        "single_source": 0.30, "geo": 0.35, "financial": 0.15,
        "lead_time": 0.10, "redundancy": 0.10,
    },
    CommodityProfile.RAW_MATERIAL: {
        # Financial fragility and geo concentration drive raw material risk
        "single_source": 0.25, "geo": 0.30, "financial": 0.25,
        "lead_time": 0.10, "redundancy": 0.10,
    },
    CommodityProfile.CASTINGS_FORGINGS: {
        # Single source and redundancy are critical — few qualified casting sources
        "single_source": 0.35, "geo": 0.20, "financial": 0.15,
        "lead_time": 0.15, "redundancy": 0.15,
    },
}


# ---------------------------------------------------------------------------
# Quality scoring bands — normalized to PPM before lookup
# Convention: % input uses whole percent values (1 = 1%, 0.1 = 0.1%)
# Conversion: ppm = defect_pct_whole * 10_000
# Half-open intervals [low, high) — eliminates boundary ambiguity
# ---------------------------------------------------------------------------

QUALITY_PPM_BANDS = [
    # (low_inclusive, high_exclusive, score)
    (0,        0.001,    100),   # Effectively zero defects
    (0.001,    100,       90),   # < 100 PPM
    (100,      500,       75),
    (500,      1_000,     55),
    (1_000,    3_000,     35),
    (3_000,   10_000,     15),
    (10_000,  float("inf"), 0),
]


# ---------------------------------------------------------------------------
# Responsiveness scoring bands (business days) — half-open intervals [low, high)
# Input: avg_response_days — avg business days for supplier to respond to
# commercial inquiries (PO acknowledgment, change requests, RFQ responses)
# ---------------------------------------------------------------------------

RESPONSIVENESS_BANDS = [
    (0,   1,   100),
    (1,   2,    85),
    (2,   3,    70),
    (3,   5,    50),
    (5,   7,    30),
    (7,  14,    15),
    (14, float("inf"), 0),
]


# ---------------------------------------------------------------------------
# Single-source exposure — nested lookup
# backup_count meaning depends on single_source flag:
#   single_source=False: qualified backup sources beyond active set
#   single_source=True:  alternates currently in qualification process
# spend_criticality_multiplier applied externally in scoring.py
# ---------------------------------------------------------------------------

SINGLE_SOURCE_LOOKUP = [
    # (single_source, min_backups, max_backups_inclusive, score)
    (False, 3, float("inf"), 100),
    (False, 2, 2,             85),
    (False, 1, 1,             65),
    (False, 0, 0,             40),
    (True,  2, float("inf"),  30),
    (True,  1, 1,             20),
    (True,  0, 0,              5),
]


# ---------------------------------------------------------------------------
# Geographic risk tiers
# ---------------------------------------------------------------------------

GEO_TIERS: dict = {
    # Tier 1 — Low
    "United States": 1, "Canada": 1, "United Kingdom": 1,
    "Germany": 1, "Japan": 1, "Australia": 1, "Netherlands": 1,
    "Switzerland": 1, "Sweden": 1, "Norway": 1, "Denmark": 1, "Finland": 1,
    # Tier 2 — Moderate
    "Mexico": 2, "South Korea": 2, "Israel": 2, "France": 2,
    "Italy": 2, "Spain": 2, "Portugal": 2, "Austria": 2, "Belgium": 2,
    "New Zealand": 2, "Singapore": 2,
    # Tier 3 — Elevated
    "India": 3, "Vietnam": 3, "Malaysia": 3, "Thailand": 3,
    "Indonesia": 3, "Philippines": 3, "Bangladesh": 3, "Turkey": 3,
    "Brazil": 3, "Poland": 3, "Czech Republic": 3, "Czechia": 3,
    "Hungary": 3, "Romania": 3, "Ukraine": 3,
    # Tier 4 — High (geopolitical tension, export control friction, strategic risk)
    "China": 4, "Taiwan": 4,
}

GEO_TIER_SCORES = {1: 100, 2: 75, 3: 45, 4: 10}

GEO_TIER_LABELS = {
    1: ("Low",      "#E8F5E9"),
    2: ("Moderate", "#FFF9C4"),
    3: ("Elevated", "#FFE0B2"),
    4: ("High",     "#FFCDD2"),
}


# ---------------------------------------------------------------------------
# Financial fragility — explicit deduction model
# Base score by size; deductions applied sequentially; floor at 0
# Max = 85 intentionally (conservative proxy — not verified financials)
# ---------------------------------------------------------------------------

FINANCIAL_BASE = {
    SupplierSize.SMALL: 50,
    SupplierSize.MID:   70,
    SupplierSize.LARGE: 85,
}

FINANCIAL_DEDUCTIONS = {
    "concern_flagged":       25,
    PriceVolatility.MEDIUM:  10,
    PriceVolatility.HIGH:    25,
}


# ---------------------------------------------------------------------------
# Lead time volatility — piecewise linear (eliminates band cliffs)
# Segments defined as (low, high, score_at_low, score_at_high)
# ---------------------------------------------------------------------------

LEAD_TIME_SEGMENTS = [
    # (low, high, score_at_low, score_at_high)
    (0,   5,   100, 80),
    (5,  10,    80, 55),
    (10, 20,    55, 30),
    (20, 35,    30, 15),
    (35, 50,    15,  5),
    (50, float("inf"), 5, 5),  # Flat floor beyond 50%
]


# ---------------------------------------------------------------------------
# Composite rating bands
# ---------------------------------------------------------------------------

RATING_BANDS = [
    (85, 100, "Preferred",  "#E8F5E9", "#2E7D32"),
    (70,  84, "Acceptable", "#FFF9C4", "#F57F17"),
    (55,  69, "At Risk",    "#FFE0B2", "#E65100"),
    (0,   54, "Critical",   "#FFCDD2", "#B71C1C"),
]


# ---------------------------------------------------------------------------
# Data confidence scoring
# Drives the confidence badge — does not affect composite score
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLDS = {
    "High":   80,
    "Medium": 50,
    "Low":    0,
}


# ---------------------------------------------------------------------------
# Compliance cap rules
# cert_key: matches condition checks in compliance.py
# applicability_key: None means always applies
# cap: maximum allowed recommendation (caps never reduce severity)
# Display vs action split: flag system drives UI display,
# COMPLIANCE_CAPS drives recommendation action — intentional separation
# ---------------------------------------------------------------------------

COMPLIANCE_CAPS = [
    # (cert_key, applicability_key, cap_recommendation)
    ("itar",           "itar_applicable",  Recommendation.CORRECTIVE_ACTION),
    ("as9100",          None,              Recommendation.MAINTAIN),
    ("cmmc_below_2",   "dod_applicable",   Recommendation.MAINTAIN),
    ("nadcap_missing", "nadcap_applicable", Recommendation.CORRECTIVE_ACTION),
]


# ---------------------------------------------------------------------------
# Validated input schema
# ---------------------------------------------------------------------------

@dataclass
class SupplierInputs:
    # Identity
    supplier_name:      str
    commodity:          str
    commodity_profile:  CommodityProfile
    country:            str
    supplier_size:      SupplierSize
    scoring_mode:       ScoringMode

    # Performance inputs
    otd_pct:            float       # 0–100
    quality_value:      float       # whole % (0–100) or PPM (0–1,000,000)
    quality_unit:       QualityUnit
    avg_response_days:  float       # business days, 0–365
    ppv_pct:            float       # %, -50 to 100

    # Risk inputs
    single_source:         bool
    backup_count:          int      # 0–10
    lead_time_variance_pct: float   # 0–500
    multiple_sites:        bool
    financial_concern:     bool
    price_volatility:      PriceVolatility
    annual_spend_usd:      Optional[float]  # Optional; drives spend criticality multiplier

    # Compliance — certification status
    as9100:     bool
    itar:       bool
    cmmc_level: int     # 0, 1, 2, or 3
    nadcap:     bool

    # Compliance — applicability toggles
    itar_applicable:    bool
    dod_applicable:     bool
    nadcap_applicable:  bool

    # Data confidence inputs
    months_of_history:  int         # 0–60
    num_transactions:   int         # 0–999
    data_source:        DataSource
    months_since_audit: Optional[int]  # None = never audited

    # Optional
    analyst_notes: str = ""

    def validate(self) -> list:
        errors = []

        if not self.supplier_name.strip():
            errors.append("Supplier name is required.")

        if not self.commodity.strip():
            errors.append("Commodity is required.")

        if not (0 <= self.otd_pct <= 100):
            errors.append("OTD % must be between 0 and 100.")

        if self.quality_unit == QualityUnit.PERCENT:
            if not (0 <= self.quality_value <= 100):
                errors.append("Defect rate (%) must be between 0 and 100.")
        else:
            if not (0 <= self.quality_value <= 1_000_000):
                errors.append("Defect rate (PPM) must be between 0 and 1,000,000.")

        if not (0 <= self.avg_response_days <= 365):
            errors.append("Response time must be between 0 and 365 days.")

        if not (-50 <= self.ppv_pct <= 100):
            errors.append("PPV must be between -50% and 100%.")

        if not (0 <= self.backup_count <= 10):
            errors.append("Backup source count must be between 0 and 10.")

        if not (0 <= self.lead_time_variance_pct <= 500):
            errors.append("Lead time variance must be between 0 and 500%.")

        if self.cmmc_level not in (0, 1, 2, 3):
            errors.append("CMMC level must be 0, 1, 2, or 3.")

        if self.annual_spend_usd is not None and self.annual_spend_usd < 0:
            errors.append("Annual spend must be 0 or greater.")

        if not (0 <= self.months_of_history <= 60):
            errors.append("Months of history must be between 0 and 60.")

        if not (0 <= self.num_transactions <= 999):
            errors.append("Number of transactions must be between 0 and 999.")

        return errors
