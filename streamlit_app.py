"""
streamlit_app.py — Supplier Performance & Risk Scorecard
UI layer for the deterministic scoring engine.

Run with:
    streamlit run streamlit_app.py

Requires all backend modules in the same directory:
    models.py, scoring.py, compliance.py, recommendation.py, ai_narrative.py
"""

import re
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

from models import (
    SupplierInputs,
    CommodityProfile,
    DataSource,
    ScoringMode,
    SupplierSize,
    QualityUnit,
    PriceVolatility,
    GEO_TIERS,
    MODE_LAYER_WEIGHTS,
)
from ai_narrative import get_full_analysis, generate_comparison_narrative


# =============================================================================
# Page configuration
# =============================================================================

st.set_page_config(
    page_title="Supplier Performance & Risk Scorecard",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =============================================================================
# Design tokens
# =============================================================================

CREAM         = "#f5f4f0"
CREAM_LIGHT   = "#faf9f5"
ACCENT        = "#c94a1e"
ACCENT_DARK   = "#a33d18"
INK           = "#1a1a1a"
INK_MUTED     = "#5a5a5a"
INK_FAINT     = "#9a9a9a"
RULE          = "#e4e2dc"

GREEN         = "#2E7D32"
AMBER         = "#F57F17"
ORANGE        = "#E65100"
RED           = "#B71C1C"
GRAY          = "#9E9E9E"


# =============================================================================
# Global CSS
# =============================================================================

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: {INK};
}}

.stApp {{
    background-color: {CREAM};
}}

.main .block-container {{
    padding-top: 2rem;
    padding-bottom: 4rem;
    max-width: 1400px;
}}

/* --- Hide Streamlit chrome --- */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}

/* --- Typography --- */
h1, h2, h3, h4 {{
    font-family: 'Inter', sans-serif;
    color: {INK};
    letter-spacing: -0.01em;
}}

.mono {{
    font-family: 'Space Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 11px;
    color: {INK_MUTED};
}}

/* --- App header --- */
.app-header {{
    border-bottom: 1px solid {RULE};
    padding-bottom: 1.25rem;
    margin-bottom: 1.5rem;
}}
.app-title {{
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 28px;
    color: {INK};
    margin: 0;
    line-height: 1.2;
}}
.app-subtitle {{
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: {ACCENT};
    margin-top: 0.4rem;
}}

/* --- Mode strip --- */
.mode-strip {{
    background: {CREAM_LIGHT};
    border: 1px solid {RULE};
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.5rem;
}}
.mode-strip-label {{
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {INK_FAINT};
    margin-bottom: 0.25rem;
}}
.mode-weights {{
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    color: {INK};
    background: white;
    border: 1px solid {RULE};
    border-radius: 4px;
    padding: 0.5rem 0.75rem;
    text-align: center;
}}

/* --- Radio buttons styled as segmented pill group --- */
div[role="radiogroup"] {{
    gap: 0 !important;
}}
div[role="radiogroup"] > label {{
    background: white;
    border: 1px solid {RULE};
    border-right: none;
    padding: 0.5rem 1rem !important;
    margin: 0 !important;
    cursor: pointer;
    transition: all 0.15s ease;
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}
div[role="radiogroup"] > label:first-child {{
    border-radius: 4px 0 0 4px;
}}
div[role="radiogroup"] > label:last-child {{
    border-right: 1px solid {RULE};
    border-radius: 0 4px 4px 0;
}}
div[role="radiogroup"] > label:has(input:checked) {{
    background: {ACCENT};
    color: white;
    border-color: {ACCENT};
}}
div[role="radiogroup"] > label > div:first-child {{
    display: none;
}}

/* --- Primary action button --- */
div.stButton > button[kind="primary"] {{
    background: {ACCENT};
    color: white;
    border: none;
    padding: 0.75rem 1.5rem;
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    border-radius: 4px;
    transition: background 0.15s ease;
    width: 100%;
}}
div.stButton > button[kind="primary"]:hover {{
    background: {ACCENT_DARK};
}}

/* --- Secondary buttons --- */
div.stButton > button:not([kind="primary"]) {{
    background: white;
    color: {INK};
    border: 1px solid {RULE};
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    border-radius: 4px;
    transition: all 0.15s ease;
}}
div.stButton > button:not([kind="primary"]):hover {{
    border-color: {ACCENT};
    color: {ACCENT};
}}

/* --- Expander styling --- */
details {{
    background: white !important;
    border: 1px solid {RULE} !important;
    border-radius: 6px !important;
    margin-bottom: 0.75rem !important;
}}
details > summary {{
    font-family: 'Space Mono', monospace !important;
    text-transform: uppercase;
    font-size: 11px !important;
    letter-spacing: 0.1em;
    padding: 0.85rem 1.1rem !important;
    color: {INK} !important;
}}

/* --- Containers --- */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-color: {RULE} !important;
    border-radius: 8px !important;
}}

/* --- Metric tiles (custom rendered) --- */
.metric-tile {{
    background: white;
    border: 1px solid {RULE};
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    height: 100%;
}}
.metric-tile-hero {{
    padding: 1.5rem 1.75rem;
}}
.metric-label {{
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {INK_FAINT};
    margin-bottom: 0.5rem;
}}
.metric-value {{
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 36px;
    color: {INK};
    line-height: 1;
}}
.metric-value-hero {{
    font-size: 64px;
    line-height: 1;
}}
.metric-suffix {{
    font-size: 14px;
    color: {INK_FAINT};
    font-weight: 400;
    margin-left: 4px;
}}
.metric-sublabel {{
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: {INK_MUTED};
    margin-top: 0.5rem;
}}
.rating-pill {{
    display: inline-block;
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 4px 10px;
    border-radius: 3px;
    margin-top: 0.5rem;
}}
.action-line {{
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    font-weight: 600;
    color: {ACCENT};
    margin-top: 0.5rem;
}}

/* --- Cap callout --- */
.cap-callout {{
    background: #FFF9E6;
    border-left: 4px solid {ACCENT};
    padding: 0.85rem 1.25rem;
    margin-bottom: 1.25rem;
    border-radius: 0 4px 4px 0;
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6B4A00;
}}

/* --- Compliance flag tile --- */
.flag-tile {{
    background: white;
    border: 1px solid {RULE};
    border-left-width: 4px;
    border-radius: 4px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.6rem;
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
}}
.flag-tile-critical {{
    border: 2px solid {RED};
    border-left-width: 4px;
}}
.flag-icon {{
    font-size: 18px;
    line-height: 1.2;
    flex-shrink: 0;
    margin-top: 1px;
}}
.flag-body {{ flex: 1; }}
.flag-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}}
.flag-cert {{
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: {INK};
    font-weight: 700;
}}
.flag-tag {{
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 2px 6px;
    border-radius: 2px;
    background: rgba(0,0,0,0.06);
    color: {INK_MUTED};
}}
.flag-tag-critical {{
    background: {RED};
    color: white;
}}
.flag-detail {{
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: {INK_MUTED};
    line-height: 1.5;
}}

/* --- AI narrative card --- */
.narrative-card {{
    background: {CREAM_LIGHT};
    border: 1px solid {RULE};
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03);
    overflow: hidden;
}}
.narrative-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.85rem 1.25rem;
    border-bottom: 1px solid {RULE};
    background: white;
}}
.narrative-title {{
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {INK};
    font-weight: 700;
}}
.narrative-source {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {INK_FAINT};
}}
.narrative-source-dot {{
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: {ACCENT};
}}
.narrative-body {{
    padding: 1.5rem 1.75rem;
}}
.narrative-section {{
    margin-bottom: 1.5rem;
    padding-bottom: 1.25rem;
    border-bottom: 1px solid {RULE};
}}
.narrative-section:last-child {{
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
}}
.narrative-section-head {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
}}
.narrative-number {{
    width: 24px;
    height: 24px;
    border-radius: 50%;
    border: 1.5px solid {ACCENT};
    color: {ACCENT};
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}}
.narrative-section-title {{
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {INK};
    font-weight: 700;
}}
.narrative-text {{
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    color: {INK};
    line-height: 1.65;
    margin-left: 36px;
    white-space: pre-wrap;
}}
.narrative-fallback {{
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    color: {INK};
    line-height: 1.65;
    white-space: pre-wrap;
}}

/* --- Sensitivity card --- */
.sensitivity-card {{
    background: white;
    border: 1px solid {RULE};
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    margin-top: 1.25rem;
}}
.sensitivity-title {{
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {INK};
    font-weight: 700;
    margin-bottom: 0.85rem;
    padding-bottom: 0.85rem;
    border-bottom: 1px solid {RULE};
}}
.sensitivity-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 0;
    border-bottom: 1px solid {RULE};
}}
.sensitivity-row:last-child {{ border-bottom: none; }}
.sensitivity-dim {{
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: {INK};
}}
.sensitivity-desc {{
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    color: {INK_MUTED};
}}
.sensitivity-arrow {{
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    color: {INK_MUTED};
}}
.sensitivity-delta {{
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 12px;
    background: #E8F5E9;
    color: {GREEN};
}}

/* --- Comparison chips --- */
.band-chip {{
    display: inline-block;
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 3px 8px;
    border-radius: 3px;
    font-weight: 700;
}}

/* --- Section labels --- */
.section-label {{
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: {INK_MUTED};
    margin: 2rem 0 0.75rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid {RULE};
}}

/* --- Geo fallback warning --- */
.geo-warning {{
    background: #FFF9E6;
    border: 1px solid #E6D080;
    border-radius: 4px;
    padding: 0.6rem 0.85rem;
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    color: #6B4A00;
    margin-bottom: 0.75rem;
}}

/* --- Tooltips/help readability --- */
[data-testid="stTooltipIcon"] {{ color: {INK_FAINT}; }}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


# =============================================================================
# Session state initialization
# =============================================================================

if "comparison" not in st.session_state:
    st.session_state["comparison"] = []
if "last_result" not in st.session_state:
    st.session_state["last_result"] = None
if "last_inputs" not in st.session_state:
    st.session_state["last_inputs"] = None


# =============================================================================
# Helpers
# =============================================================================

def score_to_color(score: float) -> str:
    """Map a 0-100 score to a green-to-red gradient color."""
    if score >= 85:
        return GREEN
    elif score >= 70:
        return "#7CB342"
    elif score >= 55:
        return AMBER
    elif score >= 40:
        return ORANGE
    else:
        return ACCENT


def hex_to_rgba(hex_color: str, alpha: float = 0.15) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


DIM_LABELS_PERF = {
    "otd":            "On-Time Delivery",
    "quality":        "Quality",
    "responsiveness": "Responsiveness",
    "cost_stability": "Cost Stability",
}
DIM_LABELS_RISK = {
    "single_source": "Single-Source Exposure",
    "geo":           "Geographic Concentration",
    "financial":     "Financial Fragility",
    "lead_time":     "Lead Time Volatility",
    "redundancy":    "Operational Redundancy",
}


def perf_input_annotations(inputs: SupplierInputs, quality_ppm: float) -> dict:
    return {
        "otd":            f"{inputs.otd_pct:.0f}% OTD",
        "quality":        f"{quality_ppm:,.0f} PPM",
        "responsiveness": f"{inputs.avg_response_days:.1f} day resp.",
        "cost_stability": f"{inputs.ppv_pct:+.1f}% PPV",
    }


def risk_input_annotations(inputs: SupplierInputs, geo_tier: int, geo_label: str) -> dict:
    ss_text = "Single-source" if inputs.single_source else "Dual+"
    return {
        "single_source": f"{ss_text} • {inputs.backup_count} backup{'s' if inputs.backup_count != 1 else ''}",
        "geo":           f"{inputs.country} • Tier {geo_tier} ({geo_label})",
        "financial":     f"{inputs.supplier_size.value} • {inputs.price_volatility.value} vol.",
        "lead_time":     f"{inputs.lead_time_variance_pct:.0f}% variance",
        "redundancy":    "Multi-site" if inputs.multiple_sites else "Single site",
    }


# =============================================================================
# App header
# =============================================================================

st.markdown(
    f"""
    <div class="app-header">
        <div class="app-subtitle">Tool 04 · Sourcing Operations Portfolio</div>
        <div class="app-title">Supplier Performance &amp; Risk Scorecard</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# ZONE 1 — Mode strip
# =============================================================================

with st.container():
    st.markdown('<div class="mode-strip">', unsafe_allow_html=True)
    mc1, mc2, mc3 = st.columns([2, 2, 1.2])

    with mc1:
        st.markdown('<div class="mode-strip-label">Scoring Mode</div>', unsafe_allow_html=True)
        mode_value = st.radio(
            "Scoring mode",
            options=[m.value for m in ScoringMode],
            index=0,
            horizontal=True,
            label_visibility="collapsed",
            key="mode_radio",
        )
        scoring_mode = ScoringMode(mode_value)

    with mc2:
        st.markdown('<div class="mode-strip-label">Commodity Profile</div>', unsafe_allow_html=True)
        profile_value = st.selectbox(
            "Commodity profile",
            options=[p.value for p in CommodityProfile],
            index=0,
            label_visibility="collapsed",
            key="profile_select",
        )
        commodity_profile = CommodityProfile(profile_value)

    with mc3:
        st.markdown('<div class="mode-strip-label">Active Layer Weights</div>', unsafe_allow_html=True)
        lw = MODE_LAYER_WEIGHTS[scoring_mode]
        st.markdown(
            f'<div class="mode-weights">'
            f'PERF {int(lw["performance"]*100)}% · RISK {int(lw["risk"]*100)}%'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


# =============================================================================
# ZONE 2 — Input panel
# =============================================================================

st.markdown('<div class="section-label">Supplier Inputs</div>', unsafe_allow_html=True)

with st.container(border=True):
    # ---- Identity ----
    with st.expander("◆  Supplier Identity", expanded=True):
        ic1, ic2 = st.columns(2)
        with ic1:
            supplier_name = st.text_input("Supplier Name", value="Acme Aerospace Mfg.")
            commodity     = st.text_input("Commodity", value="Precision Machined Parts")
        with ic2:
            country_options = sorted(GEO_TIERS.keys()) + ["Other"]
            default_idx     = country_options.index("United States") if "United States" in country_options else 0
            country         = st.selectbox("Country", options=country_options, index=default_idx)
            if country == "Other":
                country = st.text_input("Specify country", value="")
            supplier_size_val = st.selectbox(
                "Supplier Size",
                options=[s.value for s in SupplierSize],
                index=1,
            )
            supplier_size = SupplierSize(supplier_size_val)

    # ---- Performance ----
    with st.expander("◆  Performance Inputs", expanded=True):
        pc1, pc2 = st.columns(2)
        with pc1:
            otd_pct = st.number_input(
                "On-Time Delivery (%)",
                min_value=0.0, max_value=100.0, value=95.0, step=0.1,
            )
            quality_unit_val = st.radio(
                "Quality Unit",
                options=[u.value for u in QualityUnit],
                index=1,
                horizontal=True,
                help="Enter % as whole value: 1 = 1%, 0.1 = 0.1%",
            )
            quality_unit = QualityUnit(quality_unit_val)
            if quality_unit == QualityUnit.PERCENT:
                quality_value = st.number_input(
                    "Defect Rate (%)",
                    min_value=0.0, max_value=100.0, value=0.05, step=0.01, format="%.4f",
                    help="Whole percent. 1 = 1%, 0.1 = 0.1%",
                )
            else:
                quality_value = st.number_input(
                    "Defect Rate (PPM)",
                    min_value=0.0, max_value=1_000_000.0, value=200.0, step=10.0,
                )
        with pc2:
            avg_response_days = st.number_input(
                "Avg Response Time (business days)",
                min_value=0.0, max_value=365.0, value=2.0, step=0.5,
                help="Avg days for supplier to respond to commercial inquiries (PO acks, RFQs, change requests).",
            )
            ppv_pct = st.number_input(
                "Purchase Price Variance (%)",
                min_value=-50.0, max_value=100.0, value=0.5, step=0.1,
                help="Positive = cost creep above baseline. Negative = savings.",
            )

    # ---- Risk ----
    with st.expander("◆  Risk & Resilience", expanded=True):
        rc1, rc2 = st.columns(2)
        with rc1:
            single_source = st.toggle("Single-source supplier", value=False)
            backup_help = (
                "If single-source: alternates currently in qualification. "
                "If dual+: qualified backup sources beyond the active set."
            )
            backup_count = st.number_input(
                "Backup / Alternate Sources",
                min_value=0, max_value=10, value=2, step=1,
                help=backup_help,
            )
            lead_time_variance_pct = st.number_input(
                "Lead Time Variance (%)",
                min_value=0.0, max_value=500.0, value=8.0, step=1.0,
                help="Variance between quoted lead time and actual delivery.",
            )
            multiple_sites = st.toggle("Multiple production sites", value=False)
        with rc2:
            financial_concern = st.toggle("Financial concern flagged", value=False)
            price_volatility_val = st.selectbox(
                "Price Volatility",
                options=[v.value for v in PriceVolatility],
                index=0,
            )
            price_volatility = PriceVolatility(price_volatility_val)
            spend_provided = st.toggle("Provide annual spend", value=False)
            if spend_provided:
                annual_spend_usd = st.number_input(
                    "Annual Spend (USD)",
                    min_value=0.0, value=500_000.0, step=10_000.0,
                    help="Drives spend criticality multiplier on single-source dimension. ≥ $250K = -10%, ≥ $1M = -20%.",
                )
            else:
                annual_spend_usd = None

    # ---- Compliance & Data Quality ----
    with st.expander("◆  Compliance & Data Quality", expanded=True):
        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown('<div class="mono" style="margin-bottom: 0.5rem;">Certifications</div>', unsafe_allow_html=True)
            as9100 = st.checkbox("AS9100 certified", value=True)
            itar   = st.checkbox("ITAR registered",  value=True)
            cmmc_level = st.selectbox("CMMC Level", options=[0, 1, 2, 3], index=2)
            nadcap = st.checkbox("NADCAP accredited", value=False)

            st.markdown('<div class="mono" style="margin-top: 1rem; margin-bottom: 0.5rem;">Applicability to This Scope</div>', unsafe_allow_html=True)
            itar_applicable   = st.checkbox("ITAR applicable",   value=True)
            dod_applicable    = st.checkbox("DoD work applicable", value=True)
            nadcap_applicable = st.checkbox("NADCAP processes",  value=False)
        with cc2:
            st.markdown('<div class="mono" style="margin-bottom: 0.5rem;">Data Confidence</div>', unsafe_allow_html=True)
            months_of_history = st.number_input(
                "Months of Performance History",
                min_value=0, max_value=60, value=18, step=1,
            )
            num_transactions = st.number_input(
                "Number of POs / Transactions",
                min_value=0, max_value=999, value=24, step=1,
            )
            data_source_val = st.selectbox(
                "Data Source",
                options=[d.value for d in DataSource],
                index=1,
            )
            data_source = DataSource(data_source_val)
            audit_known = st.toggle("Audit date known", value=True)
            if audit_known:
                months_since_audit = st.number_input(
                    "Months Since Last Audit",
                    min_value=0, max_value=120, value=12, step=1,
                )
            else:
                months_since_audit = None

    analyst_notes = st.text_area(
        "Analyst Notes (optional)",
        value="",
        height=80,
        placeholder="Context, recent issues, or program-specific factors. Surfaced in the AI narrative.",
    )

# ---- Primary action ----
score_clicked = st.button("Score Supplier", type="primary")


# =============================================================================
# Build inputs and validate
# =============================================================================

def build_inputs() -> SupplierInputs:
    return SupplierInputs(
        supplier_name=supplier_name,
        commodity=commodity,
        commodity_profile=commodity_profile,
        country=country,
        supplier_size=supplier_size,
        scoring_mode=scoring_mode,
        otd_pct=otd_pct,
        quality_value=quality_value,
        quality_unit=quality_unit,
        avg_response_days=avg_response_days,
        ppv_pct=ppv_pct,
        single_source=single_source,
        backup_count=int(backup_count),
        lead_time_variance_pct=lead_time_variance_pct,
        multiple_sites=multiple_sites,
        financial_concern=financial_concern,
        price_volatility=price_volatility,
        annual_spend_usd=annual_spend_usd,
        as9100=as9100,
        itar=itar,
        cmmc_level=int(cmmc_level),
        nadcap=nadcap,
        itar_applicable=itar_applicable,
        dod_applicable=dod_applicable,
        nadcap_applicable=nadcap_applicable,
        months_of_history=int(months_of_history),
        num_transactions=int(num_transactions),
        data_source=data_source,
        months_since_audit=int(months_since_audit) if months_since_audit is not None else None,
        analyst_notes=analyst_notes,
    )


if score_clicked:
    inputs = build_inputs()
    errors = inputs.validate()
    if errors:
        for e in errors:
            st.error(e)
    else:
        with st.spinner("Scoring supplier..."):
            try:
                analysis = get_full_analysis(inputs)
                st.session_state["last_result"] = analysis
                st.session_state["last_inputs"] = inputs
            except Exception as exc:
                st.error(f"Scoring failed: {exc}")
                st.session_state["last_result"] = None


# =============================================================================
# ZONE 3 — Output panel
# =============================================================================

analysis = st.session_state.get("last_result")
inputs   = st.session_state.get("last_inputs")

if analysis is not None and inputs is not None:
    score_result = analysis["score_result"]
    compliance_flags = analysis["compliance_flags"]
    rec_result   = analysis["rec_result"]
    narrative    = analysis["narrative"]

    composite    = score_result["composite_score"]
    perf_score   = score_result["performance_score"]
    risk_score   = score_result["risk_score"]
    band         = score_result["rating_band"]
    confidence   = score_result["confidence"]
    perf_detail  = score_result["performance_detail"]
    risk_detail  = score_result["risk_detail"]
    sensitivity  = score_result["sensitivity"]
    geo_fallback = score_result["geo_fallback"]

    st.markdown(
        f'<div class="section-label">Evaluation Results — {score_result["supplier_name"]}</div>',
        unsafe_allow_html=True,
    )

    # Geo fallback warning
    if geo_fallback:
        st.markdown(
            f'<div class="geo-warning">⚠ Country "{inputs.country}" not in geographic risk table. '
            f'Falling back to Tier 3 (Elevated). Verify country spelling or add to risk taxonomy.</div>',
            unsafe_allow_html=True,
        )

    # Cap callout
    if rec_result["cap_triggered"]:
        if rec_result["cap_escalated"]:
            callout_text = (
                f"Compliance cap override · Score-based: {rec_result['base_recommendation']} → "
                f"Final: {rec_result['final_recommendation']}"
            )
        else:
            callout_text = "This evaluation incorporates active compliance gaps."
        st.markdown(f'<div class="cap-callout">{callout_text}</div>', unsafe_allow_html=True)

    # ---- Row 1: Headline metric strip ----
    m1, m2, m3, m4 = st.columns([2.2, 1, 1, 1])

    with m1:
        composite_bg = hex_to_rgba(band["bg_color"], 1.0)
        st.markdown(
            f'''
            <div class="metric-tile metric-tile-hero" style="background: {composite_bg};">
                <div class="metric-label">Composite Score</div>
                <div class="metric-value metric-value-hero">{composite:.1f}<span class="metric-suffix">/ 100</span></div>
                <div class="rating-pill" style="background: {band["bg_color"]}; color: {band["text_color"]};">
                    {band["label"]}
                </div>
                <div class="action-line">{rec_result["final_recommendation"]}</div>
                <div class="metric-sublabel">
                    {score_result["scoring_mode"]} · PERF {int(score_result["layer_weights"]["performance"]*100)}% / RISK {int(score_result["layer_weights"]["risk"]*100)}%
                    · {score_result["commodity_profile"]}
                </div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

    with m2:
        st.markdown(
            f'''
            <div class="metric-tile">
                <div class="metric-label">Performance</div>
                <div class="metric-value" style="color: {score_to_color(perf_score)};">{perf_score:.1f}</div>
                <div class="metric-sublabel">Layer weight: {int(score_result["layer_weights"]["performance"]*100)}%</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

    with m3:
        st.markdown(
            f'''
            <div class="metric-tile">
                <div class="metric-label">Risk &amp; Resilience</div>
                <div class="metric-value" style="color: {score_to_color(risk_score)};">{risk_score:.1f}</div>
                <div class="metric-sublabel">Layer weight: {int(score_result["layer_weights"]["risk"]*100)}%</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

    with m4:
        conf_color = {"High": GREEN, "Medium": AMBER, "Low": RED}.get(confidence["confidence_label"], INK_MUTED)
        st.markdown(
            f'''
            <div class="metric-tile">
                <div class="metric-label">Score Confidence</div>
                <div class="metric-value" style="color: {conf_color};">{confidence["confidence_label"]}</div>
                <div class="metric-sublabel">{confidence["confidence_score"]:.0f} / 100 data quality</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

    # ---- Row 2: Two-layer breakdown ----
    st.markdown('<div class="section-label">Two-Layer Score Breakdown</div>', unsafe_allow_html=True)

    perf_dim_scores = perf_detail["dimension_scores"]
    perf_weights    = perf_detail["weights"]
    risk_dim_scores = risk_detail["dimension_scores"]
    risk_weights    = risk_detail["weights"]
    quality_ppm     = score_result["quality_ppm"]
    geo_tier        = risk_detail["geo_tier"]
    geo_label_text  = risk_detail["geo_tier_label"][0]

    perf_annots = perf_input_annotations(inputs, quality_ppm)
    risk_annots = risk_input_annotations(inputs, geo_tier, geo_label_text)

    def build_dim_bar_chart(dim_scores: dict, dim_weights: dict, labels: dict, annots: dict, layer_title: str):
        keys = list(dim_scores.keys())
        # Reverse for top-down reading
        keys_rev    = keys[::-1]
        labels_list = [labels[k] for k in keys_rev]
        scores_list = [dim_scores[k] for k in keys_rev]
        weights_list = [dim_weights[k] * 100 for k in keys_rev]
        colors_list = [score_to_color(s) for s in scores_list]
        annot_text  = [annots[k] for k in keys_rev]

        fig = go.Figure()

        # Underlay: weight bar (light gray)
        fig.add_trace(go.Bar(
            x=weights_list,
            y=labels_list,
            orientation="h",
            marker=dict(color="rgba(0,0,0,0.06)"),
            width=0.85,
            showlegend=False,
            hoverinfo="skip",
            offsetgroup=1,
        ))

        # Score bar
        fig.add_trace(go.Bar(
            x=scores_list,
            y=labels_list,
            orientation="h",
            marker=dict(color=colors_list),
            width=0.55,
            text=[f"{s:.0f}" for s in scores_list],
            textposition="outside",
            textfont=dict(family="Space Mono", size=12, color=INK),
            hovertemplate="<b>%{y}</b><br>Score: %{x:.1f}<br>%{customdata}<extra></extra>",
            customdata=annot_text,
            showlegend=False,
            offsetgroup=2,
        ))

        # Input annotations to the right of each row
        for i, (lbl, ann) in enumerate(zip(labels_list, annot_text)):
            fig.add_annotation(
                xref="paper", yref="y",
                x=1.02, y=lbl,
                text=f"<span style='color:{INK_MUTED}; font-family:Inter; font-size:11px;'>{ann}</span>",
                showarrow=False,
                xanchor="left",
            )

        fig.update_layout(
            barmode="overlay",
            height=max(220, 60 * len(keys) + 60),
            margin=dict(l=10, r=180, t=20, b=20),
            paper_bgcolor=CREAM,
            plot_bgcolor=CREAM,
            xaxis=dict(
                range=[0, 110],
                showgrid=True,
                gridcolor=RULE,
                zeroline=False,
                tickfont=dict(family="Space Mono", size=10, color=INK_FAINT),
                tickvals=[0, 25, 50, 75, 100],
            ),
            yaxis=dict(
                showgrid=False,
                tickfont=dict(family="Inter", size=13, color=INK),
            ),
        )
        return fig

    bc1, bc2 = st.columns(2)
    with bc1:
        st.markdown(
            f'''<div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:0.5rem;">
                <div class="mono" style="font-size:12px; color:{INK};">Performance Layer</div>
                <div class="mono" style="font-size:11px;">Score {perf_score:.1f} · {int(score_result["layer_weights"]["performance"]*100)}% weight</div>
            </div>''',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            build_dim_bar_chart(perf_dim_scores, perf_weights, DIM_LABELS_PERF, perf_annots, "Performance"),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    with bc2:
        st.markdown(
            f'''<div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:0.5rem;">
                <div class="mono" style="font-size:12px; color:{INK};">Risk &amp; Resilience Layer</div>
                <div class="mono" style="font-size:11px;">Score {risk_score:.1f} · {int(score_result["layer_weights"]["risk"]*100)}% weight</div>
            </div>''',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            build_dim_bar_chart(risk_dim_scores, risk_weights, DIM_LABELS_RISK, risk_annots, "Risk"),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    # ---- Score Lineage Sankey ----
    with st.expander("◆  Score Lineage — How Inputs Flow to Composite"):
        # Node order:
        # 0-3: Perf dimensions, 4-8: Risk dimensions
        # 9: Performance layer, 10: Risk layer
        # 11: Composite
        perf_keys = list(perf_dim_scores.keys())
        risk_keys = list(risk_dim_scores.keys())

        node_labels = (
            [DIM_LABELS_PERF[k] for k in perf_keys]
            + [DIM_LABELS_RISK[k] for k in risk_keys]
            + ["Performance Layer", "Risk Layer", "Composite Score"]
        )
        node_colors = (
            [score_to_color(perf_dim_scores[k]) for k in perf_keys]
            + [score_to_color(risk_dim_scores[k]) for k in risk_keys]
            + [score_to_color(perf_score), score_to_color(risk_score), score_to_color(composite)]
        )

        n_perf = len(perf_keys)
        n_risk = len(risk_keys)
        perf_layer_idx = n_perf + n_risk
        risk_layer_idx = perf_layer_idx + 1
        composite_idx  = risk_layer_idx + 1

        sources, targets, values, link_colors = [], [], [], []

        for i, k in enumerate(perf_keys):
            contrib = perf_dim_scores[k] * perf_weights[k]
            sources.append(i)
            targets.append(perf_layer_idx)
            values.append(max(0.1, contrib))
            link_colors.append(hex_to_rgba(score_to_color(perf_dim_scores[k]), 0.4))

        for i, k in enumerate(risk_keys):
            contrib = risk_dim_scores[k] * risk_weights[k]
            sources.append(n_perf + i)
            targets.append(risk_layer_idx)
            values.append(max(0.1, contrib))
            link_colors.append(hex_to_rgba(score_to_color(risk_dim_scores[k]), 0.4))

        layer_w = score_result["layer_weights"]
        sources.append(perf_layer_idx)
        targets.append(composite_idx)
        values.append(max(0.1, perf_score * layer_w["performance"]))
        link_colors.append(hex_to_rgba(score_to_color(perf_score), 0.5))

        sources.append(risk_layer_idx)
        targets.append(composite_idx)
        values.append(max(0.1, risk_score * layer_w["risk"]))
        link_colors.append(hex_to_rgba(score_to_color(risk_score), 0.5))

        sankey = go.Figure(go.Sankey(
            arrangement="snap",
            node=dict(
                pad=18,
                thickness=18,
                line=dict(color=RULE, width=0.5),
                label=node_labels,
                color=node_colors,
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color=link_colors,
            ),
        ))
        sankey.update_layout(
            height=420,
            margin=dict(l=10, r=10, t=20, b=20),
            paper_bgcolor=CREAM,
            font=dict(family="Inter", size=12, color=INK),
        )
        st.plotly_chart(sankey, use_container_width=True, config={"displayModeBar": False})
        st.markdown(
            f'<div style="font-family:Inter; font-size:12px; color:{INK_MUTED}; margin-top:0.5rem;">'
            f'Link thickness = weighted contribution to the next layer. Node color reflects underlying score.'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ---- Row 3: Compliance + Narrative ----
    st.markdown('<div class="section-label">Compliance Status &amp; Evaluation Brief</div>', unsafe_allow_html=True)
    fc, nc = st.columns([1, 1.5])

    with fc:
        st.markdown(
            f'<div class="mono" style="font-size:12px; color:{INK}; margin-bottom: 0.75rem;">Compliance Flags</div>',
            unsafe_allow_html=True,
        )
        flags_html = ""
        for f in compliance_flags:
            border_style = f"border: 2px solid {f.color}; border-left-width: 4px;" if f.status == "critical" else f"border: 1px solid #e4e2dc; border-left: 4px solid {f.color};"
            tag_bg = f.color if f.status == "critical" else "rgba(0,0,0,0.06)"
            tag_color = "white" if f.status == "critical" else "#5a5a5a"
            tag_html = f'<span style="font-family:Space Mono,monospace; font-size:9px; text-transform:uppercase; letter-spacing:0.1em; padding:2px 6px; border-radius:2px; background:{tag_bg}; color:{tag_color};">{f.tag}</span>' if f.tag else ""
            flags_html += f'''<div style="{border_style} border-radius:4px; padding:0.85rem 1rem; margin-bottom:0.6rem; display:flex; align-items:flex-start; gap:0.75rem;">
<div style="font-size:18px; line-height:1.2; flex-shrink:0; margin-top:1px; color:{f.color};">{f.icon}</div>
<div style="flex:1;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
<div style="font-family:Space Mono,monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.1em; color:#1a1a1a; font-weight:700;">{f.label}</div>
{tag_html}
</div>
<div style="font-family:Inter,sans-serif; font-size:13px; color:#5a5a5a; line-height:1.5;">{f.detail}</div>
</div>
</div>'''
        st.markdown(flags_html, unsafe_allow_html=True)

    with nc:
        st.markdown(
            f'<div class="mono" style="font-size:12px; color:{INK}; margin-bottom: 0.75rem;">AI Evaluation Brief</div>',
            unsafe_allow_html=True,
        )

        # Parse narrative into sections — regex split on numbered headers like "1. SUPPLIER SUMMARY"
        section_pattern = r'(?m)^\s*(\d+)\.\s+([A-Z][A-Z\s&]+?)\s*\n'
        narrative_text  = narrative or ""
        matches = list(re.finditer(section_pattern, narrative_text))

        narrative_inner = ""
        if matches and len(matches) >= 2:
            for i, m in enumerate(matches):
                num   = m.group(1)
                title = m.group(2).strip()
                start = m.end()
                end   = matches[i + 1].start() if i + 1 < len(matches) else len(narrative_text)
                body  = narrative_text[start:end].strip()
                narrative_inner += (
                    f'<div class="section">' 
                    f'<div class="section-head">' 
                    f'<div class="num">{int(num):02d}</div>' 
                    f'<div class="sec-title">{title}</div>' 
                    f'</div>' 
                    f'<div class="sec-body">{body}</div>' 
                    f'</div>'
                )
        else:
            narrative_inner = f'<div class="sec-body" style="white-space:pre-wrap;">{narrative_text}</div>'

        cap_callout_inner = ""
        if rec_result["cap_triggered"]:
            cap_callout_inner = (
                '<div class="cap-callout" style="margin: 0 1.75rem 1rem 1.75rem;">'
                'This brief incorporates active compliance gaps that affect the final recommendation.'
                '</div>'
            )

        narrative_html = f'''
<!DOCTYPE html><html><head><style>
body {{ margin:0; padding:0; font-family:Inter,sans-serif; background:transparent; }}
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
.card {{ background:#faf9f5; border:1px solid #e4e2dc; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.04),0 4px 12px rgba(0,0,0,0.03); overflow:hidden; }}
.card-header {{ display:flex; justify-content:space-between; align-items:center; padding:0.85rem 1.25rem; border-bottom:1px solid #e4e2dc; background:white; }}
.card-title {{ font-family:'Space Mono',monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.12em; color:#1a1a1a; font-weight:700; }}
.card-source {{ display:flex; align-items:center; gap:6px; font-family:'Space Mono',monospace; font-size:10px; text-transform:uppercase; letter-spacing:0.08em; color:#9a9a9a; }}
.dot {{ width:6px; height:6px; border-radius:50%; background:#c94a1e; }}
.card-body {{ padding:1.5rem 1.75rem; }}
.section {{ margin-bottom:1.5rem; padding-bottom:1.25rem; border-bottom:1px solid #e4e2dc; }}
.section:last-child {{ margin-bottom:0; padding-bottom:0; border-bottom:none; }}
.section-head {{ display:flex; align-items:center; gap:0.75rem; margin-bottom:0.75rem; }}
.num {{ width:24px; height:24px; border-radius:50%; border:1.5px solid #c94a1e; color:#c94a1e; font-family:'Space Mono',monospace; font-size:11px; font-weight:700; display:flex; align-items:center; justify-content:center; flex-shrink:0; }}
.sec-title {{ font-family:'Space Mono',monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.12em; color:#1a1a1a; font-weight:700; }}
.sec-body {{ font-family:'Inter',sans-serif; font-size:14px; color:#1a1a1a; line-height:1.65; margin-left:36px; white-space:pre-wrap; }}
.callout {{ background:#FFF9E6; border-left:4px solid #c94a1e; padding:0.85rem 1.25rem; margin-bottom:1rem; border-radius:0 4px 4px 0; font-family:'Space Mono',monospace; font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:#6B4A00; }}
</style></head><body>
<div class="card">
  <div class="card-header">
    <div class="card-title">Supplier Evaluation Brief</div>
    <div class="card-source"><div class="dot"></div>Generated by Claude</div>
  </div>
  {cap_callout_inner}
  <div class="card-body">{narrative_inner}</div>
</div>
</body></html>'''

        # Estimate height based on content length
        narrative_height = max(400, min(1200, 300 + len(narrative_text) // 3))
        components.html(narrative_html, height=narrative_height, scrolling=False)

        # ---- Sensitivity card (filtered to positive deltas only) ----
        positive_scenarios = [s for s in sensitivity if s.get("delta", 0) > 0]
        if positive_scenarios:
            rows_html = ""
            for s in positive_scenarios:
                rows_html += f'''
                <div class="sensitivity-row">
                    <div style="flex:1.2;">
                        <div class="sensitivity-dim">{s["dimension"]}</div>
                        <div class="sensitivity-desc">{s["description"]}</div>
                    </div>
                    <div style="flex:1; text-align:center;">
                        <span class="sensitivity-arrow">{s["current_composite"]:.1f} → {s["improved_composite"]:.1f}</span>
                    </div>
                    <div style="flex:0;">
                        <span class="sensitivity-delta">+{s["delta"]:.1f}</span>
                    </div>
                </div>
                '''
            st.markdown(
                f'''
                <div class="sensitivity-card">
                    <div class="sensitivity-title">What-If Analysis · Highest-leverage improvements</div>
                    {rows_html}
                </div>
                ''',
                unsafe_allow_html=True,
            )

    # ---- Add to comparison ----
    st.markdown('<div class="section-label">Comparison Table</div>', unsafe_allow_html=True)
    ac1, ac2, ac3 = st.columns([1, 1, 3])
    with ac1:
        existing_names = [c["score_result"]["supplier_name"] for c in st.session_state["comparison"]]
        can_add = (
            len(st.session_state["comparison"]) < 5
            and score_result["supplier_name"] not in existing_names
        )
        add_disabled_reason = ""
        if len(st.session_state["comparison"]) >= 5:
            add_disabled_reason = "Comparison full (5 max)"
        elif score_result["supplier_name"] in existing_names:
            add_disabled_reason = "Already in comparison"

        if st.button("Add to Comparison", disabled=not can_add, key="add_compare"):
            st.session_state["comparison"].append(analysis)
            st.rerun()
        if add_disabled_reason:
            st.markdown(
                f'<div style="font-family:Inter; font-size:11px; color:{INK_FAINT}; margin-top:0.25rem;">{add_disabled_reason}</div>',
                unsafe_allow_html=True,
            )
    with ac2:
        if st.session_state["comparison"]:
            if st.button("Clear Comparison Table", key="clear_compare"):
                st.session_state["comparison"] = []
                st.rerun()


# =============================================================================
# Comparison section (renders whenever 2+ suppliers are in comparison)
# =============================================================================

comparison_list = st.session_state.get("comparison", [])

if len(comparison_list) >= 2:
    st.markdown(
        f'<div class="section-label">Multi-Supplier Comparison · {len(comparison_list)} suppliers</div>',
        unsafe_allow_html=True,
    )

    # Band chips row
    chip_html = '<div style="display:flex; gap:0.6rem; flex-wrap:wrap; margin-bottom: 1rem;">'
    for c in comparison_list:
        sr = c["score_result"]
        b  = sr["rating_band"]
        chip_html += (
            f'<div style="display:flex; flex-direction:column; gap:4px;">'
            f'<div style="font-family:Inter; font-size:13px; font-weight:600; color:{INK};">{sr["supplier_name"]}</div>'
            f'<div class="band-chip" style="background:{b["bg_color"]}; color:{b["text_color"]};">'
            f'{b["label"]} · {sr["composite_score"]:.1f}'
            f'</div>'
            f'</div>'
        )
    chip_html += "</div>"
    st.markdown(chip_html, unsafe_allow_html=True)

    # Sort + remove controls
    sc1, sc2 = st.columns([1, 2])
    with sc1:
        sort_options = ["Composite (high → low)", "Composite (low → high)", "Performance", "Risk", "Original order"]
        sort_choice = st.selectbox("Sort by", options=sort_options, key="sort_compare")

    sorted_comparison = list(comparison_list)
    if sort_choice == "Composite (high → low)":
        sorted_comparison.sort(key=lambda c: c["score_result"]["composite_score"], reverse=True)
    elif sort_choice == "Composite (low → high)":
        sorted_comparison.sort(key=lambda c: c["score_result"]["composite_score"])
    elif sort_choice == "Performance":
        sorted_comparison.sort(key=lambda c: c["score_result"]["performance_score"], reverse=True)
    elif sort_choice == "Risk":
        sorted_comparison.sort(key=lambda c: c["score_result"]["risk_score"], reverse=True)

    # Build heatmap data
    row_specs = [
        ("Composite", lambda sr: sr["composite_score"]),
        ("Performance", lambda sr: sr["performance_score"]),
        ("Risk", lambda sr: sr["risk_score"]),
        ("OTD", lambda sr: sr["performance_detail"]["dimension_scores"]["otd"]),
        ("Quality", lambda sr: sr["performance_detail"]["dimension_scores"]["quality"]),
        ("Responsiveness", lambda sr: sr["performance_detail"]["dimension_scores"]["responsiveness"]),
        ("Cost Stability", lambda sr: sr["performance_detail"]["dimension_scores"]["cost_stability"]),
        ("Single Source", lambda sr: sr["risk_detail"]["dimension_scores"]["single_source"]),
        ("Geographic", lambda sr: sr["risk_detail"]["dimension_scores"]["geo"]),
        ("Financial", lambda sr: sr["risk_detail"]["dimension_scores"]["financial"]),
        ("Lead Time", lambda sr: sr["risk_detail"]["dimension_scores"]["lead_time"]),
        ("Redundancy", lambda sr: sr["risk_detail"]["dimension_scores"]["redundancy"]),
    ]

    supplier_names = [c["score_result"]["supplier_name"] for c in sorted_comparison]
    z_values = []
    text_values = []
    for label, getter in row_specs:
        row_vals = [getter(c["score_result"]) for c in sorted_comparison]
        z_values.append(row_vals)
        text_values.append([f"{v:.0f}" for v in row_vals])

    # Compliance row — number of warning/critical flags per supplier
    compliance_row = []
    compliance_text = []
    for c in sorted_comparison:
        criticals = sum(1 for f in c["compliance_flags"] if f.status == "critical")
        warnings  = sum(1 for f in c["compliance_flags"] if f.status == "warning")
        if criticals > 0:
            compliance_row.append(10.0)
            compliance_text.append(f"{criticals} CRIT")
        elif warnings > 0:
            compliance_row.append(55.0)
            compliance_text.append(f"{warnings} WARN")
        else:
            compliance_row.append(100.0)
            compliance_text.append("CLEAR")
    z_values.append(compliance_row)
    text_values.append(compliance_text)

    row_labels = [r[0] for r in row_specs] + ["Compliance"]

    # Reverse for top-down reading
    z_values_rev    = z_values[::-1]
    text_values_rev = text_values[::-1]
    row_labels_rev  = row_labels[::-1]

    heatmap = go.Figure(data=go.Heatmap(
        z=z_values_rev,
        x=supplier_names,
        y=row_labels_rev,
        text=text_values_rev,
        texttemplate="%{text}",
        textfont=dict(family="Space Mono", size=11, color=INK),
        colorscale=[
            [0.0, ACCENT],
            [0.4, "#F2A57C"],
            [0.55, AMBER],
            [0.7, "#9CC972"],
            [1.0, GREEN],
        ],
        zmin=0, zmax=100,
        showscale=True,
        colorbar=dict(
            title=dict(text="Score", font=dict(family="Space Mono", size=10, color=INK_MUTED)),
            tickfont=dict(family="Space Mono", size=10, color=INK_MUTED),
            thickness=10,
            len=0.7,
        ),
        xgap=2, ygap=2,
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:.1f}<extra></extra>",
    ))

    # Highlight best per row (lowest score among non-empty)
    n_cols = len(supplier_names)
    for ri, row in enumerate(z_values_rev):
        if max(row) > min(row):
            best_idx = row.index(max(row))
            heatmap.add_shape(
                type="rect",
                x0=best_idx - 0.5, x1=best_idx + 0.5,
                y0=ri - 0.5,        y1=ri + 0.5,
                line=dict(color=ACCENT, width=2.5),
                fillcolor="rgba(0,0,0,0)",
            )

    heatmap.update_layout(
        height=max(420, 36 * len(row_labels)),
        margin=dict(l=10, r=10, t=20, b=40),
        paper_bgcolor=CREAM,
        plot_bgcolor=CREAM,
        xaxis=dict(
            side="top",
            tickfont=dict(family="Inter", size=12, color=INK),
        ),
        yaxis=dict(
            tickfont=dict(family="Inter", size=12, color=INK),
        ),
    )
    st.plotly_chart(heatmap, use_container_width=True, config={"displayModeBar": False})

    # ---- Best fit by mode ----
    from scoring import compute_composite

    st.markdown(
        f'<div class="mono" style="font-size:11px; color:{INK_MUTED}; margin-top:1rem; margin-bottom:0.5rem;">Best Fit by Scoring Mode</div>',
        unsafe_allow_html=True,
    )
    mode_winners = {}
    for mode in ScoringMode:
        best_supplier = None
        best_score = -1
        for c in sorted_comparison:
            sr = c["score_result"]
            comp = compute_composite(sr["performance_score"], sr["risk_score"], mode)
            if comp > best_score:
                best_score = comp
                best_supplier = sr["supplier_name"]
        mode_winners[mode.value] = (best_supplier, best_score)

    mode_cards = ""
    for mode_name, (winner, score) in mode_winners.items():
        mode_cards += (
            f'<div style="flex:1; background:white; border:1px solid #e4e2dc; border-radius:6px; padding:0.85rem 1rem;">' 
            f'<div style="font-family:Space Mono,monospace; font-size:10px; text-transform:uppercase; letter-spacing:0.12em; color:#9a9a9a; margin-bottom:0.4rem;">{mode_name}</div>' 
            f'<div style="font-family:Inter,sans-serif; font-size:14px; font-weight:600; color:#1a1a1a;">{winner}</div>' 
            f'<div style="font-family:Space Mono,monospace; font-size:11px; color:#c94a1e; margin-top:0.2rem;">Composite {score:.1f}</div>' 
            f'</div>'
        )
    mode_html = f'<div style="display:flex; gap:1rem;">{mode_cards}</div>'
    st.markdown(mode_html, unsafe_allow_html=True)

    # ---- Comparative AI narrative ----
    st.markdown(
        f'<div class="mono" style="font-size:11px; color:{INK_MUTED}; margin-top:1.5rem; margin-bottom:0.5rem;">Comparative Analysis</div>',
        unsafe_allow_html=True,
    )

    cache_key = tuple(c["score_result"]["supplier_name"] for c in sorted_comparison) + (sort_choice,)
    if st.session_state.get("comp_narrative_key") != cache_key:
        with st.spinner("Generating comparative analysis..."):
            try:
                comp_narrative = generate_comparison_narrative(sorted_comparison)
            except Exception:
                comp_narrative = ""
        st.session_state["comp_narrative"] = comp_narrative
        st.session_state["comp_narrative_key"] = cache_key
    else:
        comp_narrative = st.session_state["comp_narrative"]

    if comp_narrative:
        st.markdown(
            f'''
            <div class="narrative-card">
                <div class="narrative-header">
                    <div class="narrative-title">Cross-Supplier Comparative Analysis</div>
                    <div class="narrative-source">
                        <div class="narrative-source-dot"></div>
                        Generated by Claude
                    </div>
                </div>
                <div class="narrative-body">
                    <div class="narrative-fallback">{comp_narrative}</div>
                </div>
            </div>
            ''',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="font-family:Inter; font-size:13px; color:{INK_MUTED};">'
            f'Comparative narrative unavailable. Individual supplier briefs above remain valid.</div>',
            unsafe_allow_html=True,
        )

    # ---- Individual remove controls ----
    st.markdown(
        f'<div class="mono" style="font-size:11px; color:{INK_MUTED}; margin-top:1.5rem; margin-bottom:0.5rem;">Manage Comparison</div>',
        unsafe_allow_html=True,
    )
    rm_cols = st.columns(min(len(comparison_list), 5))
    for i, c in enumerate(comparison_list):
        with rm_cols[i % len(rm_cols)]:
            name = c["score_result"]["supplier_name"]
            if st.button(f"✕  Remove {name}", key=f"rm_{i}_{name}"):
                st.session_state["comparison"].pop(i)
                st.session_state.pop("comp_narrative_key", None)
                st.rerun()


# =============================================================================
# Empty-state footer when nothing has been scored yet
# =============================================================================

if analysis is None:
    st.markdown(
        f'''
        <div style="text-align:center; padding: 3rem 1rem; color: {INK_FAINT}; font-family: Inter; font-size: 14px;">
            Configure supplier inputs above and click <strong>Score Supplier</strong> to begin.
        </div>
        ''',
        unsafe_allow_html=True,
    )
