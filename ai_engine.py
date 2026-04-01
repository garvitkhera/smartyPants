"""
Smarty Pants AI Engine — Claude-powered credit assessment pipeline.
4-step pipeline: Eligibility → Risk → Audit Risk → Credit Decision
"""

import json
import re
from anthropic import Anthropic
from credit_policy import CREDIT_POLICY_DOCUMENT


def _extract_json(text: str) -> dict | None:
    """Extract JSON object from Claude's response (handles code blocks)."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


class SmartPantsAI:
    MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    # ---- STEP 1: R&D ELIGIBILITY ----

    def stream_eligibility(self, rd_description: str, industry: str = ""):
        prompt = f"""Analyse this R&D activity description against the four ATO eligibility criteria for core R&D activities:

1. **Technical Uncertainty** — Genuine technical uncertainty not resolvable by existing knowledge?
2. **Hypothesis-Driven** — Was a hypothesis formulated?
3. **Systematic Progression** — Systematic work: experiment → observation → evaluation → conclusion?
4. **New Knowledge** — Aims to generate new knowledge (improved materials, products, processes)?

Also assess EXCLUSION risks (routine development, simple adaptation, cosmetic changes, quality control).

**Industry:** {industry or 'Not specified'}

**R&D Activity Description:**
{rd_description}

---

Write 2-3 sentence analysis per criterion. Assess exclusion risks. Then output JSON:

```json
{{
  "technical_uncertainty_score": <0-100>,
  "hypothesis_score": <0-100>,
  "systematic_progression_score": <0-100>,
  "new_knowledge_score": <0-100>,
  "exclusion_risk": "<low|medium|high>",
  "overall_eligibility_score": <0-100>,
  "eligible": true/false,
  "confidence": "<high|medium|low>",
  "key_strengths": ["..."],
  "key_concerns": ["..."],
  "recommendation": "<eligible|likely_eligible|borderline|likely_ineligible|ineligible>"
}}
```"""
        return self.client.messages.stream(
            model=self.MODEL, max_tokens=1500, temperature=0.2,
            system="You are a precise Australian R&DTI eligibility assessor. Thorough but concise. Always output valid JSON in a code block at the end.",
            messages=[{"role": "user", "content": prompt}],
        )

    # ---- STEP 2: CREDIT RISK ----

    def stream_credit_risk(self, company_data: dict, eligibility_result: dict):
        rd = company_data.get('rd_expenditure', 0)
        rev = max(company_data.get('annual_revenue', 1), 1)
        prompt = f"""You are a credit risk analyst for Smarty Pants, an R&D lending platform.
Security is the borrower's expected R&DTI refund from the Australian government.

**Company Profile:**
- Name: {company_data.get('company_name', 'N/A')}
- Industry: {company_data.get('industry', 'N/A')}
- Revenue: ${rev:,.0f}
- R&D Spend: ${rd:,.0f} ({rd/rev*100:.1f}% of revenue)
- Trading: {company_data.get('trading_months', 0)} months
- Employees: {company_data.get('employees', 'N/A')}
- Previous R&DTI Claims: {company_data.get('previous_claims', 'N/A')}
- Requested Advance: ${company_data.get('requested_amount', 0):,.0f}
- Expected Refund (43.5%): ${rd * 0.435:,.0f}

**R&D Eligibility Score:** {eligibility_result.get('overall_eligibility_score', 'N/A')}/100

**Credit Policy Grading:**
A (80-100): Strong financials, repeat borrower, clean history
B (60-79): Solid, minor concerns, first-time OK
C (40-59): Some stress, higher audit risk
D (25-39): Significant concerns, needs extra security
E (0-24): Auto-decline

Assess: Financial Health, Refund Certainty, Character, Concentration Risk.
Assign Credit Grade (A-E). Write analysis, then JSON:

```json
{{
  "financial_health_score": <0-100>,
  "refund_certainty_score": <0-100>,
  "character_score": <0-100>,
  "concentration_risk_score": <0-100>,
  "composite_score": <0-100>,
  "credit_grade": "<A|B|C|D|E>",
  "risk_factors": ["..."],
  "mitigants": ["..."],
  "decision": "<auto_approve|refer_credit_officer|refer_committee|auto_decline>",
  "conditions": ["..."]
}}
```"""
        return self.client.messages.stream(
            model=self.MODEL, max_tokens=1500, temperature=0.2,
            system="You are a meticulous credit risk analyst. Assess conservatively but fairly. Always output valid JSON at the end.",
            messages=[{"role": "user", "content": prompt}],
        )

    # ---- STEP 3: AUDIT RISK ----

    def stream_audit_risk(self, company_data: dict, eligibility_result: dict):
        rd = company_data.get('rd_expenditure', 0)
        rev = max(company_data.get('annual_revenue', 1), 1)
        prompt = f"""You are an ATO audit risk prediction model for R&DTI claims.

**Claim Profile:**
- Industry: {company_data.get('industry', 'N/A')}
- R&D Spend: ${rd:,.0f}
- Revenue: ${rev:,.0f}
- R&D/Revenue: {rd/rev*100:.1f}%
- Company Age: {company_data.get('trading_months', 0)} months
- Previous Claims: {company_data.get('previous_claims', 'N/A')}
- Eligibility Score: {eligibility_result.get('overall_eligibility_score', 'N/A')}/100
- Eligibility Concerns: {eligibility_result.get('key_concerns', [])}

Known ATO audit triggers: R&D spend >50% of revenue, first-time large claims, software R&D, routine-looking activities, high adjustment-rate industries.

Write brief risk analysis, then JSON:

```json
{{
  "audit_probability_pct": <0-100>,
  "risk_level": "<low|medium|high|very_high>",
  "primary_triggers": ["..."],
  "estimated_adjustment_risk_pct": <0-100>,
  "mitigation_recommendations": ["..."],
  "impact_on_refund": "<none|minor_reduction|significant_reduction|full_disallowance>"
}}
```"""
        return self.client.messages.stream(
            model=self.MODEL, max_tokens=1000, temperature=0.2,
            system="You are an ATO audit risk prediction model. Be precise with probabilities. Output valid JSON at the end.",
            messages=[{"role": "user", "content": prompt}],
        )

    # ---- STEP 4: DECISION NARRATIVE ----

    def stream_decision_narrative(self, company_data, hard_rules, eligibility, credit_risk, audit_risk, pricing):
        prompt = f"""You are the Senior Credit Officer at Smarty Pants. Write the final credit decision.

**APPLICATION:**
Company: {company_data.get('company_name', 'N/A')} | Advance: ${company_data.get('requested_amount', 0):,.0f}

**PIPELINE RESULTS:**
Hard Rules: {'PASSED' if hard_rules.get('all_passed') else 'FAILED: ' + ', '.join(hard_rules.get('failed_rules', []))}
R&D Eligibility: {eligibility.get('overall_eligibility_score', 'N/A')}/100 ({eligibility.get('recommendation', 'N/A')})
Credit Grade: {credit_risk.get('credit_grade', 'N/A')} (Score: {credit_risk.get('composite_score', 'N/A')}/100)
Route: {credit_risk.get('decision', 'N/A')}
Audit Risk: {audit_risk.get('risk_level', 'N/A')} ({audit_risk.get('audit_probability_pct', 'N/A')}%)
Pricing: {pricing.get('annual_rate_pct', 'N/A')}% p.a. over {pricing.get('term_months', 'N/A')} months
Risk Factors: {credit_risk.get('risk_factors', [])}
Mitigants: {credit_risk.get('mitigants', [])}
Conditions: {credit_risk.get('conditions', [])}

Write: executive summary (2-3 sentences), key rationale, conditions, watchpoints. Then JSON:

```json
{{
  "final_decision": "<approved|conditionally_approved|referred|declined>",
  "executive_summary": "...",
  "conditions": ["..."],
  "watchpoints": ["..."],
  "confidence_level": "<high|medium|low>"
}}
```"""
        return self.client.messages.stream(
            model=self.MODEL, max_tokens=1200, temperature=0.3,
            system="You are a senior credit officer. Write clear, professional decision narratives. Output valid JSON at the end.",
            messages=[{"role": "user", "content": prompt}],
        )
