"""
Smarty Pants — R&D Tax Incentive Lending Platform POC
Single-process Streamlit app with AI-powered credit assessment.
"""

import streamlit as st
import json, re, os
from dotenv import load_dotenv
load_dotenv()
from ai_engine import SmartPantsAI, _extract_json
from credit_policy import apply_hard_rules, compute_pricing, CREDIT_POLICY_DOCUMENT
from database import Database

# ── Keys from .env only ──
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SB_URL = os.environ.get("SUPABASE_URL", "")
SB_KEY = os.environ.get("SUPABASE_KEY", "")

# ── Page Config ──
st.set_page_config(page_title="Smarty Pants — AI Lending Engine", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

# ── Custom CSS ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;700&display=swap');
.main-title {
    font-family: 'Inter', sans-serif; font-size: 2.4rem; font-weight: 700;
    background: linear-gradient(135deg, #00d4ff 0%, #7b2ff7 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0;
}
.sub-title { font-family: 'Inter', sans-serif; font-size: 1rem; color: #8b949e; margin-top: -8px; margin-bottom: 24px; }
.pipeline-step {
    border: 1px solid #30363d; border-radius: 10px; padding: 16px 20px; margin: 10px 0; background: #161b22;
}
.pipeline-step.active { border-color: #00d4ff; box-shadow: 0 0 12px rgba(0,212,255,0.08); }
.pipeline-step.done  { border-color: #238636; }
.step-header { font-family: 'Inter', sans-serif; font-size: 1.05rem; font-weight: 600; color: #f0f6fc; }
.step-badge {
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    font-size: 0.75rem; font-weight: 600; font-family: 'JetBrains Mono', monospace;
}
.badge-pass { background: #238636; color: #fff; }
.badge-fail { background: #da3633; color: #fff; }
.ai-output {
    font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; line-height: 1.7;
    background: #0d1117; border: 1px solid #21262d; border-radius: 8px; padding: 16px; color: #c9d1d9; white-space: pre-wrap;
}
.metric-card {
    background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 16px 20px; text-align: center;
}
.metric-value { font-family: 'JetBrains Mono', monospace; font-size: 1.8rem; font-weight: 700; }
.metric-label { font-size: 0.8rem; color: #8b949e; margin-top: 4px; }
.grade-a { color: #3fb950; } .grade-b { color: #58a6ff; }
.grade-c { color: #d29922; } .grade-d { color: #f78166; } .grade-e { color: #da3633; }
.score-bar { height: 8px; border-radius: 4px; background: #21262d; margin: 4px 0 12px 0; }
.score-fill { height: 100%; border-radius: 4px; }
.sidebar-status {
    font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;
    padding: 8px 12px; border-radius: 6px; background: #0d1117; border: 1px solid #21262d; margin: 4px 0;
}
div[data-testid="stExpander"] { border: 1px solid #21262d; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ──
def score_color(s):
    if s >= 70: return "#3fb950"
    if s >= 40: return "#d29922"
    return "#da3633"

def grade_class(g): return f"grade-{g.lower()}" if g else "grade-c"

def render_score_bar(label, score, mx=100):
    pct = min(score / mx * 100, 100); c = score_color(score)
    st.markdown(f'<div style="display:flex;justify-content:space-between;font-size:0.85rem;"><span>{label}</span>'
                f'<span style="font-family:\'JetBrains Mono\',monospace;color:{c};font-weight:600;">{score}/{mx}</span></div>'
                f'<div class="score-bar"><div class="score-fill" style="width:{pct}%;background:{c};"></div></div>', unsafe_allow_html=True)

def stream_to_ui(stream_ctx, placeholder):
    full = ""
    with stream_ctx as stream:
        for text in stream.text_stream:
            full += text
            placeholder.markdown(f'<div class="ai-output">{full}▊</div>', unsafe_allow_html=True)
    placeholder.markdown(f'<div class="ai-output">{full}</div>', unsafe_allow_html=True)
    return full

# ── Session State ──
PAGES = ["📋 Application", "🧠 AI Engine", "💰 Pricing", "📊 Dashboard"]
if "current_page" not in st.session_state:
    st.session_state.current_page = PAGES[0]

defaults = {
    "company_data": {}, "hard_rules_result": {}, "eligibility_result": {},
    "credit_risk_result": {}, "audit_risk_result": {}, "pricing_result": {},
    "decision_result": {}, "pipeline_run": False,
    "raw_eligibility": "", "raw_credit": "", "raw_audit": "", "raw_decision": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── DB ──
db = Database(SB_URL or None, SB_KEY or None)

# ── Sidebar ──
with st.sidebar:
    st.markdown('<div class="main-title">🧠 Smarty Pants</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">AI Credit Engine v0.1</div>', unsafe_allow_html=True)
    st.divider()

    page = st.radio("Navigation", PAGES, index=PAGES.index(st.session_state.current_page))
    st.session_state.current_page = page

    st.divider()
    st.markdown("##### Engine Status")
    st.markdown(f'<div class="sidebar-status">{"🟢" if API_KEY else "🔴"} Claude AI: {"ONLINE" if API_KEY else "SET ANTHROPIC_API_KEY in .env"}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sidebar-status">{"🟢" if SB_URL else "🟡"} Supabase: {"CONNECTED" if SB_URL else "IN-MEMORY"}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-status">🟢 Rules Engine: LOADED</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-status">🟢 Pricing Engine: READY</div>', unsafe_allow_html=True)

    st.divider()
    with st.expander("📜 Credit Policy"):
        st.code(CREDIT_POLICY_DOCUMENT, language="text")

# ── Header ──
st.markdown('<div class="main-title">Smarty Pants</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">R&D Tax Incentive Lending — AI-Powered Credit Assessment POC</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════
# PAGE: APPLICATION
# ═══════════════════════════════════════
if page == "📋 Application":
    st.markdown("### New Advance Application")
    st.caption("Pre-filled with sample data for demo. Edit anything and hit Submit.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Company Details")
        company_name = st.text_input("Company Name", "NovaTech Solutions Pty Ltd")
        abn = st.text_input("ABN (11 digits)", "51 824 753 556")
        industry = st.selectbox("Industry", ["Software / SaaS", "Biotechnology", "Clean Energy", "Advanced Manufacturing", "AgriTech", "MedTech", "Mining / Resources", "Construction Tech", "Other"])
        employees = st.number_input("Employees", min_value=1, value=18, step=1)
        trading_months = st.number_input("Months Trading", min_value=0, value=30, step=1)
        previous_claims = st.selectbox("Previous R&DTI Claims?", ["No — first time", "Yes — 1 prior claim", "Yes — 2+ prior claims"])
    with c2:
        st.markdown("##### Financials")
        annual_revenue = st.number_input("Annual Revenue (AUD)", min_value=0, value=2_400_000, step=50_000, format="%d")
        rd_expenditure = st.number_input("R&D Expenditure (AUD)", min_value=0, value=680_000, step=10_000, format="%d")
        expected_refund = rd_expenditure * 0.435
        st.metric("Expected Refund (43.5%)", f"${expected_refund:,.0f}")
        requested_amount = st.number_input("Requested Advance (AUD)", min_value=0, max_value=max(int(expected_refund), 1), value=min(int(expected_refund * 0.7), max(int(expected_refund), 1)), step=5_000, format="%d")
        lvr = (requested_amount / expected_refund * 100) if expected_refund > 0 else 0
        st.metric("LVR", f"{lvr:.1f}%", delta="Within cap" if lvr <= 80 else "EXCEEDS 80%")

    st.markdown("##### R&D Activity Description")
    rd_description = st.text_area("Describe the R&D activities", height=170, value="""NovaTech is developing a novel real-time anomaly detection system for industrial IoT sensor networks. The core technical uncertainty lies in achieving sub-100ms detection latency across heterogeneous sensor types while maintaining a false positive rate below 0.1%.

Our approach involves a new hybrid architecture combining edge-deployed lightweight transformer models with a centralised federated learning system. We hypothesise that a novel attention mechanism optimised for time-series sensor data can achieve detection accuracy comparable to centralised models within edge compute constraints.

Systematic experimentation involves: (1) designing and testing attention mechanism variants, (2) evaluating federated aggregation strategies for non-IID sensor data, (3) measuring latency/accuracy trade-offs across edge hardware. Each experiment cycle informs the next architecture iteration.""")

    if st.button("🚀 Submit & Run AI Pipeline", type="primary", use_container_width=True):
        if not API_KEY:
            st.error("ANTHROPIC_API_KEY not found. Add it to your `.env` file and restart.")
        elif not rd_description.strip():
            st.error("Provide an R&D activity description.")
        else:
            st.session_state.company_data = dict(
                company_name=company_name, abn=abn, industry=industry, employees=employees,
                trading_months=trading_months, previous_claims=previous_claims,
                annual_revenue=annual_revenue, rd_expenditure=rd_expenditure,
                rd_description=rd_description, requested_amount=requested_amount,
            )
            st.session_state.pipeline_run = True
            for k in ["hard_rules_result", "eligibility_result", "credit_risk_result",
                       "audit_risk_result", "pricing_result", "decision_result"]:
                st.session_state[k] = {}
            for k in ["raw_eligibility", "raw_credit", "raw_audit", "raw_decision"]:
                st.session_state[k] = ""
            # Auto-navigate to AI Engine page
            st.session_state.current_page = "🧠 AI Engine"
            st.rerun()

# ═══════════════════════════════════════
# PAGE: AI ENGINE
# ═══════════════════════════════════════
elif page == "🧠 AI Engine":
    if not st.session_state.pipeline_run:
        st.markdown("### AI Assessment Pipeline")
        st.info("Submit an application from the **📋 Application** page to run the pipeline.")
        st.markdown("#### Pipeline Architecture")
        cols = st.columns(5)
        for i, (ic, nm, ds) in enumerate([
            ("⚙️","Hard Rules","Deterministic"), ("🔬","R&D Eligibility","Claude AI"),
            ("📊","Credit Risk","Claude AI"), ("🔍","Audit Risk","Claude AI"), ("📝","Decision","Claude AI"),
        ]):
            with cols[i]:
                st.markdown(f'<div class="metric-card"><div style="font-size:1.8rem;">{ic}</div>'
                            f'<div style="font-size:0.85rem;font-weight:600;margin-top:6px;">{nm}</div>'
                            f'<div style="font-size:0.7rem;color:#8b949e;">{ds}</div></div>', unsafe_allow_html=True)
    else:
        cd = st.session_state.company_data
        ai = SmartPantsAI(API_KEY)
        st.markdown(f"### Pipeline — {cd.get('company_name','')}")

        # ── STEP 0: HARD RULES ──
        st.markdown('<div class="pipeline-step done"><div class="step-header">⚙️ Step 0 — Deterministic Hard Rules</div></div>', unsafe_allow_html=True)
        if not st.session_state.hard_rules_result:
            st.session_state.hard_rules_result = apply_hard_rules(cd)
        hr = st.session_state.hard_rules_result
        for r in hr["rules"]:
            badge = "badge-pass" if r["passed"] else "badge-fail"
            st.markdown(f'<span class="step-badge {badge}">{"PASS" if r["passed"] else "FAIL"}</span> **{r["rule"]}** — {r["detail"]}', unsafe_allow_html=True)
        if hr["all_passed"]:
            st.success("All hard rules passed → proceeding to AI assessment.")
        else:
            st.error(f"FAILED: {', '.join(hr['failed_rules'])}. Continuing for demo.")
        st.divider()

        # ── STEP 1: ELIGIBILITY ──
        st.markdown('<div class="pipeline-step active"><div class="step-header">🔬 Step 1 — R&D Eligibility Assessment</div></div>', unsafe_allow_html=True)
        if not st.session_state.eligibility_result:
            with st.status("Claude is analysing R&D eligibility...", expanded=True) as status:
                ph = st.empty()
                raw = stream_to_ui(ai.stream_eligibility(cd["rd_description"], cd.get("industry", "")), ph)
                st.session_state.raw_eligibility = raw
                st.session_state.eligibility_result = _extract_json(raw) or {}
                status.update(label="R&D eligibility complete", state="complete")
        else:
            with st.expander("View AI reasoning", expanded=False):
                st.markdown(f'<div class="ai-output">{st.session_state.raw_eligibility}</div>', unsafe_allow_html=True)
        el = st.session_state.eligibility_result
        if el:
            ec = st.columns(4)
            for i, (k, lb) in enumerate([("technical_uncertainty_score","Tech Uncertainty"),("hypothesis_score","Hypothesis"),("systematic_progression_score","Systematic Progression"),("new_knowledge_score","New Knowledge")]):
                with ec[i]: render_score_bar(lb, el.get(k, 0))
            mc = st.columns(3)
            ov = el.get('overall_eligibility_score', 0)
            with mc[0]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:{score_color(ov)}">{ov}</div><div class="metric-label">Eligibility Score</div></div>', unsafe_allow_html=True)
            rec = el.get('recommendation','N/A')
            with mc[1]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="font-size:1.1rem;color:#58a6ff;">{rec}</div><div class="metric-label">Recommendation</div></div>', unsafe_allow_html=True)
            er = el.get('exclusion_risk','N/A'); erc = {"low":"#3fb950","medium":"#d29922","high":"#da3633"}.get(er,"#8b949e")
            with mc[2]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="font-size:1.1rem;color:{erc};">{er}</div><div class="metric-label">Exclusion Risk</div></div>', unsafe_allow_html=True)
        st.divider()

        # ── STEP 2: CREDIT RISK ──
        st.markdown('<div class="pipeline-step active"><div class="step-header">📊 Step 2 — Credit Risk Assessment</div></div>', unsafe_allow_html=True)
        if not st.session_state.credit_risk_result:
            with st.status("Claude is assessing credit risk...", expanded=True) as status:
                ph = st.empty()
                raw = stream_to_ui(ai.stream_credit_risk(cd, el), ph)
                st.session_state.raw_credit = raw
                st.session_state.credit_risk_result = _extract_json(raw) or {}
                status.update(label="Credit risk complete", state="complete")
        else:
            with st.expander("View AI reasoning", expanded=False):
                st.markdown(f'<div class="ai-output">{st.session_state.raw_credit}</div>', unsafe_allow_html=True)
        cr = st.session_state.credit_risk_result
        if cr:
            cc = st.columns(4)
            for i, (k, lb) in enumerate([("financial_health_score","Financial Health"),("refund_certainty_score","Refund Certainty"),("character_score","Character"),("concentration_risk_score","Concentration Risk")]):
                with cc[i]: render_score_bar(lb, cr.get(k, 0))
            gc = st.columns(3)
            grade = cr.get('credit_grade','?')
            with gc[0]: st.markdown(f'<div class="metric-card"><div class="metric-value {grade_class(grade)}" style="font-size:3rem;">{grade}</div><div class="metric-label">Credit Grade</div></div>', unsafe_allow_html=True)
            cs = cr.get('composite_score', 0)
            with gc[1]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:{score_color(cs)}">{cs}</div><div class="metric-label">Composite Score</div></div>', unsafe_allow_html=True)
            dec = cr.get('decision','N/A').replace('_',' ').title()
            with gc[2]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="font-size:0.95rem;color:#58a6ff;">{dec}</div><div class="metric-label">Decision Route</div></div>', unsafe_allow_html=True)
        st.divider()

        # ── STEP 3: AUDIT RISK ──
        st.markdown('<div class="pipeline-step active"><div class="step-header">🔍 Step 3 — ATO Audit Risk Prediction</div></div>', unsafe_allow_html=True)
        if not st.session_state.audit_risk_result:
            with st.status("Claude is predicting audit risk...", expanded=True) as status:
                ph = st.empty()
                raw = stream_to_ui(ai.stream_audit_risk(cd, el), ph)
                st.session_state.raw_audit = raw
                st.session_state.audit_risk_result = _extract_json(raw) or {}
                status.update(label="Audit risk complete", state="complete")
        else:
            with st.expander("View AI reasoning", expanded=False):
                st.markdown(f'<div class="ai-output">{st.session_state.raw_audit}</div>', unsafe_allow_html=True)
        ar = st.session_state.audit_risk_result
        if ar:
            ac = st.columns(3)
            ap = ar.get('audit_probability_pct', 0)
            with ac[0]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:{score_color(100-ap)}">{ap}%</div><div class="metric-label">Audit Probability</div></div>', unsafe_allow_html=True)
            rl = ar.get('risk_level','N/A'); rlc = {"low":"#3fb950","medium":"#d29922","high":"#f78166","very_high":"#da3633"}.get(rl,"#8b949e")
            with ac[1]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="font-size:1.2rem;color:{rlc};">{rl.replace("_"," ").upper()}</div><div class="metric-label">Risk Level</div></div>', unsafe_allow_html=True)
            imp = ar.get('impact_on_refund','N/A').replace('_',' ').title()
            with ac[2]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="font-size:0.95rem;color:#58a6ff;">{imp}</div><div class="metric-label">Refund Impact</div></div>', unsafe_allow_html=True)
        st.divider()

        # ── Pre-compute pricing for decision ──
        if cr:
            g = cr.get('credit_grade','C'); erf = cd.get('rd_expenditure',0)*0.435
            lv = (cd.get('requested_amount',0)/erf*100) if erf>0 else 80
            st.session_state.pricing_result = compute_pricing(g, 9, lv, cd.get('requested_amount',0))

        # ── STEP 4: DECISION ──
        st.markdown('<div class="pipeline-step active"><div class="step-header">📝 Step 4 — Final Credit Decision</div></div>', unsafe_allow_html=True)
        if not st.session_state.decision_result:
            with st.status("Claude is writing the credit decision...", expanded=True) as status:
                ph = st.empty()
                raw = stream_to_ui(ai.stream_decision_narrative(cd, hr, el, cr, ar, st.session_state.pricing_result), ph)
                st.session_state.raw_decision = raw
                st.session_state.decision_result = _extract_json(raw) or {}
                status.update(label="Decision complete", state="complete")
        else:
            with st.expander("View AI reasoning", expanded=False):
                st.markdown(f'<div class="ai-output">{st.session_state.raw_decision}</div>', unsafe_allow_html=True)
        dr = st.session_state.decision_result
        if dr:
            fd = dr.get('final_decision','N/A')
            fdc = {"approved":"#3fb950","conditionally_approved":"#58a6ff","referred":"#d29922","declined":"#da3633"}.get(fd,"#8b949e")
            st.markdown(f'''<div class="metric-card" style="border:2px solid {fdc};margin:16px 0;">
                <div style="font-size:0.85rem;color:#8b949e;margin-bottom:8px;">FINAL DECISION</div>
                <div class="metric-value" style="color:{fdc};font-size:2rem;">{fd.replace('_',' ').upper()}</div>
                <div style="margin-top:12px;font-size:0.9rem;color:#c9d1d9;">{dr.get('executive_summary','')}</div>
            </div>''', unsafe_allow_html=True)
            if dr.get("conditions"):
                st.markdown("**Conditions:**")
                for c in dr["conditions"]: st.markdown(f"- {c}")
            if dr.get("watchpoints"):
                st.markdown("**Watchpoints:**")
                for w in dr["watchpoints"]: st.markdown(f"- {w}")

        # Save + Reset
        if dr and db.available:
            st.divider()
            if st.button("💾 Save to Supabase", use_container_width=True):
                save_data = {**cd, "hard_rules_result": hr, "eligibility_result": el,
                    "credit_risk_result": cr, "audit_risk_result": ar,
                    "pricing_result": st.session_state.pricing_result, "decision_result": dr, "status": fd}
                result = db.save_application(save_data)
                st.success(f"Saved (ID: {result.get('id','OK')})") if result else st.error("Save failed.")
        st.divider()
        if st.button("🔄 New Application", use_container_width=True):
            for k in defaults:
                st.session_state[k] = defaults[k]
            st.session_state.current_page = "📋 Application"
            st.rerun()

# ═══════════════════════════════════════
# PAGE: PRICING
# ═══════════════════════════════════════
elif page == "💰 Pricing":
    st.markdown("### Parametric Loan Pricing Engine")
    if not st.session_state.credit_risk_result:
        st.info("Run the AI pipeline first for risk-adjusted rates, or explore defaults below.")
    cd = st.session_state.company_data; cr = st.session_state.credit_risk_result
    rd_s = cd.get("rd_expenditure", 500_000); exp_r = rd_s * 0.435
    bg = cr.get("credit_grade", "B") if cr else "B"

    st.markdown("##### Adjust Parameters")
    p1, p2 = st.columns(2)
    with p1:
        p_grade = st.select_slider("Credit Grade", ["A","B","C","D","E"], value=bg)
        p_term = st.slider("Term (months)", 1, 12, 9)
        p_lvr = st.slider("Target LVR (%)", 10, 80, 70, 5)
    with p2:
        mx_adv = max(int(exp_r * 0.8), 10_001)
        p_adv = st.slider("Advance (AUD)", 10_000, mx_adv, min(int(exp_r * p_lvr/100), mx_adv), 5_000)
        st.metric("Expected Refund", f"${exp_r:,.0f}")
        alvr = (p_adv/exp_r*100) if exp_r>0 else 0
        st.metric("Actual LVR", f"{alvr:.1f}%")

    pricing = compute_pricing(p_grade, p_term, alvr, p_adv)
    if not pricing.get("approved"):
        st.error(f"❌ {pricing.get('reason','Declined')}")
    else:
        st.divider()
        pc = st.columns(4)
        with pc[0]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#58a6ff;">{pricing["annual_rate_pct"]}%</div><div class="metric-label">Annual Rate</div></div>', unsafe_allow_html=True)
        with pc[1]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#58a6ff;">${pricing["total_interest"]:,.0f}</div><div class="metric-label">Total Interest</div></div>', unsafe_allow_html=True)
        with pc[2]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#d29922;">${pricing["establishment_fee"]:,.0f}</div><div class="metric-label">Est. Fee (1.5%)</div></div>', unsafe_allow_html=True)
        with pc[3]: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#3fb950;">${pricing["total_repayment"]:,.0f}</div><div class="metric-label">Total Repayment</div></div>', unsafe_allow_html=True)
        st.divider()
        st.markdown("##### Breakdown")
        st.dataframe({
            "Parameter": ["Base Rate","Risk Premium (Grade "+p_grade+")","All-in Rate","Term","Advance","Interest","Est. Fee","Total Cost","Total Repayment"],
            "Value": [f"{pricing['base_rate_pct']}% p.a.", f"+{pricing['risk_premium_pct']}%", f"{pricing['annual_rate_pct']}% p.a.",
                      f"{pricing['term_months']}m", f"${pricing['advance_amount']:,.2f}", f"${pricing['total_interest']:,.2f}",
                      f"${pricing['establishment_fee']:,.2f}", f"${pricing['total_cost']:,.2f}", f"${pricing['total_repayment']:,.2f}"],
        }, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════
elif page == "📊 Dashboard":
    st.markdown("### Portfolio Dashboard")
    if not db.available:
        st.info("Connect Supabase via `.env` to view the portfolio dashboard. Set `SUPABASE_URL` and `SUPABASE_KEY`.")
    else:
        stats = db.get_stats()
        if stats["total"] == 0:
            st.info("No applications yet. Run an assessment and save it.")
        else:
            dc = st.columns(4)
            with dc[0]: st.metric("Applications", stats["total"])
            with dc[1]: st.metric("Approved", stats["approved"])
            with dc[2]: st.metric("Declined", stats["declined"])
            with dc[3]: st.metric("Total Advanced", f"${stats['total_advanced']:,.0f}")
            st.divider()
            for app in stats.get("applications", []):
                dra = app.get("decision_result", {}) or {}
                fda = dra.get("final_decision", "pending")
                ico = {"approved":"🟢","conditionally_approved":"🔵","referred":"🟡","declined":"🔴"}.get(fda,"⚪")
                with st.expander(f"{ico} {app.get('company_name','?')} — ${app.get('requested_amount',0):,.0f} — {fda.replace('_',' ').upper()}"):
                    x1,x2,x3 = st.columns(3)
                    ela = app.get("eligibility_result",{}) or {}
                    cra = app.get("credit_risk_result",{}) or {}
                    ara = app.get("audit_risk_result",{}) or {}
                    with x1: st.metric("Eligibility", f"{ela.get('overall_eligibility_score','?')}/100")
                    with x2: st.metric("Grade", cra.get("credit_grade","?"))
                    with x3: st.metric("Audit Risk", f"{ara.get('audit_probability_pct','?')}%")
                    if dra.get("executive_summary"): st.caption(dra["executive_summary"])
