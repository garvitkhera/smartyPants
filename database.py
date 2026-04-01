"""
Smarty Pants Database — Supabase integration for persistence.
Gracefully degrades if Supabase is not configured.
"""

import json
from datetime import datetime


class Database:
    def __init__(self, url: str | None = None, key: str | None = None):
        self.client = None
        self.available = False
        if url and key:
            try:
                from supabase import create_client
                self.client = create_client(url, key)
                self.available = True
            except Exception as e:
                print(f"Supabase init failed: {e}")

    def save_application(self, data: dict) -> dict | None:
        if not self.available:
            return None
        try:
            row = {
                "company_name": data.get("company_name", ""),
                "abn": data.get("abn", ""),
                "industry": data.get("industry", ""),
                "annual_revenue": data.get("annual_revenue", 0),
                "rd_expenditure": data.get("rd_expenditure", 0),
                "rd_description": data.get("rd_description", ""),
                "requested_amount": data.get("requested_amount", 0),
                "trading_months": data.get("trading_months", 0),
                "employees": data.get("employees", 0),
                "previous_claims": data.get("previous_claims", "No"),
                "hard_rules_result": json.dumps(data.get("hard_rules_result", {})),
                "eligibility_result": json.dumps(data.get("eligibility_result", {})),
                "credit_risk_result": json.dumps(data.get("credit_risk_result", {})),
                "audit_risk_result": json.dumps(data.get("audit_risk_result", {})),
                "pricing_result": json.dumps(data.get("pricing_result", {})),
                "decision_result": json.dumps(data.get("decision_result", {})),
                "status": data.get("status", "assessed"),
            }
            result = self.client.table("applications").insert(row).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Save failed: {e}")
            return None

    def get_applications(self, limit: int = 50) -> list:
        if not self.available:
            return []
        try:
            result = (
                self.client.table("applications")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = result.data or []
            for r in rows:
                for field in ["hard_rules_result", "eligibility_result", "credit_risk_result",
                              "audit_risk_result", "pricing_result", "decision_result"]:
                    if isinstance(r.get(field), str):
                        try:
                            r[field] = json.loads(r[field])
                        except (json.JSONDecodeError, TypeError):
                            pass
            return rows
        except Exception as e:
            print(f"Fetch failed: {e}")
            return []

    def get_stats(self) -> dict:
        apps = self.get_applications(limit=200)
        if not apps:
            return {"total": 0, "approved": 0, "declined": 0, "referred": 0, "total_advanced": 0}
        total = len(apps)
        approved = sum(1 for a in apps if a.get("decision_result", {}).get("final_decision") in ("approved", "conditionally_approved"))
        declined = sum(1 for a in apps if a.get("decision_result", {}).get("final_decision") == "declined")
        referred = sum(1 for a in apps if a.get("decision_result", {}).get("final_decision") == "referred")
        total_advanced = sum(a.get("requested_amount", 0) for a in apps if a.get("decision_result", {}).get("final_decision") in ("approved", "conditionally_approved"))
        return {
            "total": total,
            "approved": approved,
            "declined": declined,
            "referred": referred,
            "total_advanced": total_advanced,
            "applications": apps,
        }
