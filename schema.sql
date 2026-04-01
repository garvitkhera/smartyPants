-- Run this in Supabase SQL Editor to create the applications table

CREATE TABLE IF NOT EXISTS applications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    company_name TEXT NOT NULL,
    abn TEXT,
    industry TEXT,
    annual_revenue NUMERIC DEFAULT 0,
    rd_expenditure NUMERIC DEFAULT 0,
    rd_description TEXT,
    requested_amount NUMERIC DEFAULT 0,
    trading_months INTEGER DEFAULT 0,
    employees INTEGER DEFAULT 0,
    previous_claims TEXT,
    hard_rules_result JSONB DEFAULT '{}',
    eligibility_result JSONB DEFAULT '{}',
    credit_risk_result JSONB DEFAULT '{}',
    audit_risk_result JSONB DEFAULT '{}',
    pricing_result JSONB DEFAULT '{}',
    decision_result JSONB DEFAULT '{}',
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (allow all for POC - tighten for production)
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all for POC" ON applications FOR ALL USING (true) WITH CHECK (true);
