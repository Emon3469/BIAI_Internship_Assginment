"""Corporate Lead Pipeline Engine for Task 2.

Orchestrates the full pipeline: load → clean → deduplicate → validate → analyze → output.
"""

import json
import pandas as pd
import numpy as np
from datetime import date, timedelta
from pathlib import Path

from .data_cleaner import (
    load_corporate_leads,
    detect_duplicates,
    validate_and_fix_dates,
    detect_overdue,
    detect_deal_value_outliers,
    validate_contact_info,
    analyze_stage_consistency,
    calculate_risk_level,
    suggest_next_action,
    detect_auto_lost,
    REFERENCE_DATE,
    STAGE_ORDER,
    END_STAGES,
    ALL_STAGES,
)


def process_pipeline(csv_path: str) -> dict:
    """Process the entire corporate leads pipeline.
    
    Returns a dict with cleaned data, issues, analytics, and recommendations.
    """
    # Step 1: Load raw data
    df = load_corporate_leads(csv_path)
    original_count = len(df)
    
    # Store original data for reference
    df["original_data"] = df.apply(lambda row: json.dumps(row.to_dict(), default=str), axis=1)
    
    # Step 2: Detect duplicates
    duplicates = detect_duplicates(df)
    duplicate_ids = {d["remove"] for d in duplicates}
    
    # Mark duplicates but don't remove yet (keep for reporting)
    df["is_duplicate"] = df["lead_id"].isin(duplicate_ids)
    df["duplicate_of"] = df["lead_id"].map(
        {d["remove"]: d["keep"] for d in duplicates}
    )
    
    # Step 3: Clean deal values
    df["deal_value_bdt"] = pd.to_numeric(df["deal_value_bdt"], errors="coerce").fillna(0)
    
    # Step 4: Validate and fix dates
    df, date_issues = validate_and_fix_dates(df)
    
    # Step 5: Detect overdue follow-ups
    df = detect_overdue(df)
    
    # Step 6: Validate contact info
    df, contact_issues = validate_contact_info(df)
    
    # Step 7: Detect deal value outliers
    outlier_issues = detect_deal_value_outliers(df)
    
    # Step 8: Analyze stage consistency
    stage_issues = analyze_stage_consistency(df)
    
    # Step 8.5: Detect leads that should be auto-Lost
    auto_lost = detect_auto_lost(df)
    
    # Combine all issues
    all_issues = date_issues + contact_issues + outlier_issues + stage_issues
    
    # Create issues lookup by lead_id
    issues_by_lead = {}
    for issue in all_issues:
        lid = issue["lead_id"]
        if lid not in issues_by_lead:
            issues_by_lead[lid] = []
        issues_by_lead[lid].append(issue)
    
    df["data_issues"] = df["lead_id"].map(
        lambda lid: json.dumps(issues_by_lead.get(lid, []))
    )
    
    # Step 9: Apply suggested stages from stage analysis
    stage_suggestions = {
        issue["lead_id"]: issue.get("suggested_stage")
        for issue in stage_issues
        if "suggested_stage" in issue
    }
    df["suggested_stage"] = df["lead_id"].map(stage_suggestions)
    
    # Step 10: Calculate risk levels and next actions
    df["risk_level"] = df.apply(calculate_risk_level, axis=1)
    df["suggested_action"] = df.apply(suggest_next_action, axis=1)
    
    # Step 11: Generate analytics
    analytics = generate_pipeline_analytics(df, duplicates, all_issues, auto_lost)
    
    return {
        "cleaned_data": df,
        "duplicates": duplicates,
        "issues": all_issues,
        "analytics": analytics,
        "auto_lost_suggestions": auto_lost,
    }


def generate_pipeline_analytics(
    df: pd.DataFrame, 
    duplicates: list[dict], 
    issues: list[dict],
    auto_lost: list[dict] | None = None,
) -> dict:
    """Generate comprehensive pipeline analytics."""
    # Filter active (non-duplicate) leads
    active = df[~df["is_duplicate"]].copy()
    
    # --- Funnel Analysis ---
    stage_counts = {}
    for stage in ALL_STAGES:
        count = len(active[active["stage"] == stage])
        stage_counts[stage] = count
    
    # --- Deal Value Analysis ---
    active_deals = active[active["deal_value_bdt"] > 0]
    total_pipeline_value = float(active_deals["deal_value_bdt"].sum())
    avg_deal_value = float(active_deals["deal_value_bdt"].mean()) if len(active_deals) > 0 else 0
    
    # Weighted pipeline (probability-weighted by stage)
    stage_probability = {
        "New": 0.10,
        "Contacted": 0.20,
        "Meeting": 0.40,
        "Proposal": 0.60,
        "Invoice sent": 0.80,
        "Paid": 1.00,
        "Lost": 0.00,
    }
    
    weighted_value = 0
    for _, row in active.iterrows():
        val = row.get("deal_value_bdt", 0) or 0
        prob = stage_probability.get(str(row.get("stage", "")), 0)
        weighted_value += val * prob
    
    # --- Overdue Analysis ---
    overdue_leads = active[active["is_overdue"] == True]
    overdue_count = len(overdue_leads)
    overdue_by_stage = {}
    for stage in STAGE_ORDER:
        count = len(overdue_leads[overdue_leads["stage"] == stage])
        if count > 0:
            overdue_by_stage[stage] = count
    
    # --- Source Analysis ---
    source_counts = active["source"].value_counts().to_dict()
    
    # --- Industry Analysis ---
    industry_counts = active["industry"].value_counts().to_dict()
    
    # --- Risk Distribution ---
    risk_counts = active["risk_level"].value_counts().to_dict()
    
    # --- High Priority Actions ---
    high_priority = []
    for _, row in active.iterrows():
        if row.get("risk_level") == "high" or (row.get("is_overdue") and row.get("days_overdue", 0) > 3):
            high_priority.append({
                "lead_id": row["lead_id"],
                "company": row["company"],
                "stage": row["stage"],
                "days_overdue": int(row.get("days_overdue", 0)),
                "deal_value": float(row.get("deal_value_bdt", 0)),
                "action": row.get("suggested_action", ""),
            })
    
    high_priority.sort(key=lambda x: x["days_overdue"], reverse=True)
    
    return {
        "reference_date": REFERENCE_DATE.isoformat(),
        "total_leads": len(df),
        "unique_leads": len(active),
        "duplicates_found": len(duplicates),
        "data_issues_count": len(issues),
        "funnel": stage_counts,
        "pipeline_value": {
            "total_bdt": total_pipeline_value,
            "weighted_bdt": weighted_value,
            "average_deal_bdt": avg_deal_value,
            "deals_with_value": len(active_deals),
        },
        "overdue": {
            "count": overdue_count,
            "by_stage": overdue_by_stage,
            "leads": [
                {
                    "lead_id": row["lead_id"],
                    "company": row["company"],
                    "stage": row["stage"],
                    "days_overdue": int(row["days_overdue"]),
                    "deal_value": float(row.get("deal_value_bdt", 0)),
                }
                for _, row in overdue_leads.iterrows()
            ],
        },
        "by_source": source_counts,
        "by_industry": industry_counts,
        "risk_distribution": risk_counts,
        "high_priority_actions": high_priority,
        "auto_lost_suggestions": auto_lost or [],
    }


def save_pipeline_results(results: dict, output_dir: str) -> dict:
    """Save pipeline processing results to files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    df = results["cleaned_data"]
    
    # Save cleaned CSV
    export_cols = [
        "lead_id", "company", "industry", "contact_name", "contact_role",
        "contact_email", "contact_phone", "source", "stage", "deal_value_bdt",
        "last_contact", "next_follow_up", "notes", "is_duplicate", "duplicate_of",
        "is_overdue", "days_overdue", "suggested_stage", "suggested_action",
        "risk_level", "data_issues",
    ]
    available_cols = [c for c in export_cols if c in df.columns]
    df[available_cols].to_csv(
        output_path / "corporate_leads_cleaned.csv", 
        index=False, encoding="utf-8-sig"
    )
    
    # Save active (non-duplicate) leads
    active = df[~df["is_duplicate"]]
    active[available_cols].to_csv(
        output_path / "corporate_leads_active.csv",
        index=False, encoding="utf-8-sig"
    )
    
    # Save issues report
    with open(output_path / "data_issues_report.json", "w", encoding="utf-8") as f:
        json.dump(results["issues"], f, indent=2, ensure_ascii=False, default=str)
    
    # Save duplicates report
    with open(output_path / "duplicates_report.json", "w", encoding="utf-8") as f:
        json.dump(results["duplicates"], f, indent=2, ensure_ascii=False, default=str)
    
    # Save analytics
    with open(output_path / "pipeline_analytics.json", "w", encoding="utf-8") as f:
        json.dump(results["analytics"], f, indent=2, ensure_ascii=False, default=str)
    
    return {
        "cleaned_csv": str(output_path / "corporate_leads_cleaned.csv"),
        "active_csv": str(output_path / "corporate_leads_active.csv"),
        "issues_json": str(output_path / "data_issues_report.json"),
        "duplicates_json": str(output_path / "duplicates_report.json"),
        "analytics_json": str(output_path / "pipeline_analytics.json"),
    }
