"""
Smarty Pants Credit Policy — Deterministic Rules Engine
Encodes hard gates from the Credit Policy Manual + parametric pricing.
"""

CREDIT_POLICY_DOCUMENT = """
SMARTY PANTS CREDIT POLICY MANUAL — R&DTI BUSINESS LENDING
===========================================================

1. INTRODUCTION
This policy governs the origination, assessment, approval, servicing and collection
of advances made against expected Australian R&D Tax Incentive (R&DTI) refunds.
All lending decisions must comply with this policy. Deviations require written
approval from the Credit Committee.

2. TARGET MARKET & ELIGIBLE BORROWERS
- Australian incorporated companies (ACN registered with ASIC)
- Aggregated annual turnover under $20 million (eligible for refundable 43.5% offset)
- Minimum annual eligible R&D expenditure of $50,000
- R&D activities registered (or registrable) with AusIndustry/DISR
- No outstanding ATO tax debts that could offset the refund
- Company must have been trading for at least 6 months
- Directors must not be bankrupt or disqualified under the Corporations Act

3. CREDIT ASSESSMENT PROCESS
Assessment follows a two-layer approach:
Layer 1 — Deterministic Gates (auto-decline if any fail):
  - ABN/ACN validity check
  - Minimum R&D expenditure threshold ($50,000)
  - Maximum LVR cap (80%)
  - Company trading duration (minimum 6 months)
  - Director disqualification check

Layer 2 — AI-Assisted Assessment:
  - R&D eligibility quality scoring
  - Character-based lending assessment
  - Financial health analysis (via Xero/accounting data)
  - ATO audit risk prediction
  - Overall credit risk grading (A/B/C/D/E)

4. PARAMETERS & CREDIT CRITERIA
  - Maximum Loan-to-Value Ratio (LVR): 80% of expected refund
  - Loan Term: 1 to 12 months
  - Interest Rate: Base rate + risk premium (determined by credit grade)
  - Base rate: 8% p.a.
  - Risk premium: Grade A = +0%, B = +2%, C = +4%, D = +6%, E = decline
  - Establishment fee: 1.5% of advance amount
  - Minimum advance: $10,000
  - Maximum advance: $2,000,000

5. CREDIT SCORING & DECISIONING
Credit grades are assigned based on composite scoring:
  A (Excellent, 80-100): Strong financials, repeat borrower, clean R&D history
  B (Good, 60-79): Solid fundamentals, minor concerns, first-time borrower
  C (Acceptable, 40-59): Some financial stress, higher audit risk, viable R&D
  D (Marginal, 25-39): Significant concerns, requires additional security
  E (Decline, 0-24): Fails minimum criteria, unacceptable risk

6. APPROVAL & DECLINE
  - Grades A-B: Auto-approve (subject to hard gates passing)
  - Grade C: Refer to Credit Officer for manual review
  - Grade D: Refer to Credit Committee, requires additional security (PPSR, director guarantee)
  - Grade E: Auto-decline with written reasons

7. LOAN SERVICING
  - Disbursement via direct bank transfer within 2 business days of approval
  - PPSR registration over the R&D refund receivable
  - Monthly portfolio monitoring via accounting feed
  - Quarterly borrower health check for loans > 6 months

8. COLLECTIONS & DEFAULT
  - Refund arrives: automatic loan repayment + release of PPSR
  - Refund delayed > 30 days past expected: trigger review
  - Refund reduced by ATO: recalculate exposure, request top-up security if LVR > 90%
  - Borrower insolvency: enforce PPSR security, engage recovery process
  - Write-off after 180 days of non-recovery

9. FRAUD PREVENTION
  - Cross-reference R&D registration with AusIndustry public records
  - Verify director identities via KYC/AML checks
  - Flag applications with R&D spend > 60% of revenue as high-scrutiny
  - Monitor for duplicate applications across related entities

10. HARDSHIP OBLIGATIONS
  - Borrowers experiencing financial difficulty may request repayment variation
  - Assess on case-by-case basis within 21 days of request
  - Options include: term extension, interest-only period, partial repayment plan
"""


def apply_hard_rules(application: dict) -> dict:
    """
    Layer 1: Deterministic gates from the Credit Policy.
    Returns pass/fail for each rule and an overall gate result.
    """
    results = {"rules": [], "all_passed": True, "failed_rules": []}

    # Rule 1: ABN present and valid format (11 digits)
    abn = application.get("abn", "").replace(" ", "")
    abn_valid = len(abn) == 11 and abn.isdigit()
    results["rules"].append({
        "rule": "ABN Validity",
        "passed": abn_valid,
        "detail": f"ABN '{application.get('abn', 'N/A')}' — {'valid format' if abn_valid else 'invalid or missing'}"
    })

    # Rule 2: Minimum R&D expenditure ($50,000)
    rd_spend = application.get("rd_expenditure", 0)
    rd_ok = rd_spend >= 50000
    results["rules"].append({
        "rule": "Minimum R&D Expenditure",
        "passed": rd_ok,
        "detail": f"${rd_spend:,.0f} vs minimum $50,000 — {'PASS' if rd_ok else 'FAIL'}"
    })

    # Rule 3: Company turnover under $20M
    revenue = application.get("annual_revenue", 0)
    rev_ok = revenue < 20_000_000
    results["rules"].append({
        "rule": "Turnover Under $20M",
        "passed": rev_ok,
        "detail": f"${revenue:,.0f} — {'eligible for refundable offset' if rev_ok else 'exceeds $20M threshold'}"
    })

    # Rule 4: Trading duration >= 6 months
    months = application.get("trading_months", 0)
    age_ok = months >= 6
    results["rules"].append({
        "rule": "Minimum Trading Duration",
        "passed": age_ok,
        "detail": f"{months} months vs minimum 6 — {'PASS' if age_ok else 'FAIL'}"
    })

    # Rule 5: Requested LVR <= 80%
    expected_refund = rd_spend * 0.435
    requested = application.get("requested_amount", 0)
    lvr = (requested / expected_refund * 100) if expected_refund > 0 else 999
    lvr_ok = lvr <= 80
    results["rules"].append({
        "rule": "LVR Cap (80%)",
        "passed": lvr_ok,
        "detail": f"LVR {lvr:.1f}% (${requested:,.0f} / ${expected_refund:,.0f} expected refund) — {'within cap' if lvr_ok else 'exceeds 80% cap'}"
    })

    # Rule 6: R&D spend not > 60% of revenue (fraud flag)
    if revenue > 0:
        rd_ratio = rd_spend / revenue
        ratio_ok = rd_ratio <= 0.6
        results["rules"].append({
            "rule": "R&D/Revenue Ratio Check",
            "passed": ratio_ok,
            "detail": f"R&D is {rd_ratio:.0%} of revenue — {'normal' if ratio_ok else 'HIGH SCRUTINY: exceeds 60%'}"
        })
    else:
        results["rules"].append({
            "rule": "R&D/Revenue Ratio Check",
            "passed": False,
            "detail": "Revenue is $0 — cannot assess ratio"
        })

    for r in results["rules"]:
        if not r["passed"]:
            results["all_passed"] = False
            results["failed_rules"].append(r["rule"])

    return results


def compute_pricing(risk_grade: str, term_months: int, lvr_pct: float, advance_amount: float) -> dict:
    """Parametric pricing engine. Base rate + risk premium + establishment fee."""
    base_rate = 8.0
    premium_map = {"A": 0.0, "B": 2.0, "C": 4.0, "D": 6.0, "E": None}
    premium = premium_map.get(risk_grade)

    if premium is None:
        return {"approved": False, "reason": "Grade E — auto-decline per credit policy"}

    annual_rate = base_rate + premium
    monthly_rate = annual_rate / 12
    total_interest = advance_amount * (annual_rate / 100) * (term_months / 12)
    establishment_fee = advance_amount * 0.015
    total_cost = total_interest + establishment_fee
    total_repayment = advance_amount + total_cost

    return {
        "approved": True,
        "risk_grade": risk_grade,
        "base_rate_pct": base_rate,
        "risk_premium_pct": premium,
        "annual_rate_pct": annual_rate,
        "monthly_rate_pct": round(monthly_rate, 2),
        "term_months": term_months,
        "lvr_pct": round(lvr_pct, 1),
        "advance_amount": advance_amount,
        "establishment_fee": round(establishment_fee, 2),
        "total_interest": round(total_interest, 2),
        "total_cost": round(total_cost, 2),
        "total_repayment": round(total_repayment, 2),
    }
