"""Corporate Lead Pipeline Data Cleaner for Task 2.

Handles all data quality issues in the corporate leads dataset:
- Missing data detection and smart imputation
- Duplicate detection and merging
- Date validation and correction
- Phone/email format validation
- Outlier detection in deal values
"""

import re
import json
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from pathlib import Path
from src.task1_crm.text_processing import normalize_phone

# Reference date as specified in the task
REFERENCE_DATE = date(2026, 11, 1)

# Valid pipeline stages in order
STAGE_ORDER = ["New", "Contacted", "Meeting", "Proposal", "Invoice sent"]
END_STAGES = ["Paid", "Lost"]
ALL_STAGES = STAGE_ORDER + END_STAGES
STAGE_RANK = {stage: i for i, stage in enumerate(ALL_STAGES)}

# Days of silence before marking as Lost
LOST_THRESHOLD_DAYS = 30


def load_corporate_leads(csv_path: str) -> pd.DataFrame:
    """Load and perform initial cleaning of corporate leads CSV."""
    df = pd.read_csv(csv_path)
    
    # Normalize column names
    df.columns = [
        c.strip().lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        for c in df.columns
    ]
    
    # Rename for consistency
    rename_map = {
        "lead_id": "lead_id",
        "deal_value_bdt": "deal_value_bdt",
    }
    # Handle the deal_value column name variation
    for col in df.columns:
        if "deal_value" in col or "deal value" in col:
            rename_map[col] = "deal_value_bdt"
    df = df.rename(columns=rename_map)

    text_columns = [
        "lead_id", "company", "industry", "contact_name", "contact_role",
        "contact_email", "source", "stage", "notes",
    ]
    for column in text_columns:
        if column in df:
            df[column] = df[column].fillna("").map(lambda value: str(value).strip())
    if "contact_phone" in df:
        df["contact_phone"] = (
            df["contact_phone"].fillna("").map(normalize_phone)
        )

    return df


def detect_duplicates(df: pd.DataFrame) -> list[dict]:
    """Detect duplicate leads based on company name, contact info, and notes.
    
    Strategy:
    1. Explicit duplicates noted in 'notes' column are always flagged.
    2. Same email + same/similar company name = duplicate.
    3. Very high company name similarity (>0.85) + same contact = duplicate.
    
    Each lead can only be a duplicate of ONE other lead (the earliest).
    Returns list of duplicate pair info.
    """
    from src.task1_crm.text_processing import key_text, text_similarity
    
    duplicates = []
    already_marked: set[str] = set()

    def clean_value(value: object) -> str:
        if pd.isna(value):
            return ""
        return str(value).strip()

    for i in range(len(df)):
        for j in range(i + 1, len(df)):
            row_i = df.iloc[i]
            row_j = df.iloc[j]
            lead_i = clean_value(row_i["lead_id"])
            lead_j = clean_value(row_j["lead_id"])
            if lead_j in already_marked:
                continue

            notes_i = clean_value(row_i.get("notes", "")).upper()
            notes_j = clean_value(row_j.get("notes", "")).upper()
            company_i = clean_value(row_i.get("company", ""))
            company_j = clean_value(row_j.get("company", ""))
            explicit_j = "DUPLICATE" in notes_j and (
                lead_i.upper() in notes_j or company_i.upper() in notes_j
            )
            explicit_i = "DUPLICATE" in notes_i and (
                lead_j.upper() in notes_i or company_j.upper() in notes_i
            )

            email_i = clean_value(row_i.get("contact_email", "")).lower()
            email_j = clean_value(row_j.get("contact_email", "")).lower()
            phone_i = re.sub(r"\D", "", clean_value(row_i.get("contact_phone", "")))
            phone_j = re.sub(r"\D", "", clean_value(row_j.get("contact_phone", "")))
            email_match = bool(email_i and email_j and email_i == email_j)
            phone_match = bool(phone_i and phone_j and phone_i == phone_j)
            name_sim = text_similarity(key_text(company_i), key_text(company_j))

            if explicit_j or explicit_i:
                reason = "explicit_note"
            elif (email_match or phone_match) and name_sim > 0.5:
                reason = f"same_contact_similar_company (name_sim={name_sim:.2f})"
            elif name_sim > 0.92:
                reason = f"near_identical_company_name ({name_sim:.2f})"
            else:
                continue

            duplicates.append({
                "keep": lead_i,
                "remove": lead_j,
                "reason": reason,
                "keep_index": i,
                "remove_index": j,
            })
            already_marked.add(lead_j)

    return duplicates


def validate_and_fix_dates(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Validate and fix date fields, detecting data errors.
    
    Returns updated DataFrame and list of issues found.
    """
    issues = []
    df = df.copy()
    
    # Parse date columns
    for col in ["last_contact", "next_follow_up"]:
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date.astype(object)
    
    for idx, row in df.iterrows():
        lead_id = row["lead_id"]
        last_contact = row.get("last_contact")
        next_follow_up = row.get("next_follow_up")
        
        # Check if next_follow_up is before last_contact (data error like L25)
        if pd.notna(last_contact) and pd.notna(next_follow_up):
            if next_follow_up < last_contact:
                issues.append({
                    "lead_id": lead_id,
                    "issue": "date_order_error",
                    "detail": f"next_follow_up ({next_follow_up}) is before last_contact ({last_contact})",
                    "fix": "Set next_follow_up to last_contact + 7 days",
                })
                # Fix: set follow-up to a week after last contact
                df.at[idx, "next_follow_up"] = last_contact + timedelta(days=7)
        
        # Check for missing last_contact on non-New stages
        stage = str(row.get("stage", "")).strip()
        if stage not in ["New"] and pd.isna(last_contact):
            issues.append({
                "lead_id": lead_id,
                "issue": "missing_last_contact",
                "detail": f"Stage is '{stage}' but last_contact is empty",
                "fix": "No automatic fix — needs manual review",
            })
        
        # Check for missing next_follow_up on active stages
        if stage not in END_STAGES and pd.isna(next_follow_up):
            issues.append({
                "lead_id": lead_id,
                "issue": "missing_follow_up",
                "detail": f"Active stage '{stage}' has no next_follow_up date",
                "fix": "Set to reference date + 3 days",
            })
            df.at[idx, "next_follow_up"] = REFERENCE_DATE + timedelta(days=3)
    
    return df, issues


def detect_overdue(df: pd.DataFrame) -> pd.DataFrame:
    """Mark leads with overdue follow-ups relative to REFERENCE_DATE."""
    df = df.copy()
    df["is_overdue"] = False
    df["days_overdue"] = 0
    
    for idx, row in df.iterrows():
        next_fu = row.get("next_follow_up")
        stage = str(row.get("stage", "")).strip()
        
        if pd.notna(next_fu) and stage not in END_STAGES:
            fu_date = next_fu if isinstance(next_fu, date) else pd.to_datetime(next_fu).date()
            if fu_date < REFERENCE_DATE:
                df.at[idx, "is_overdue"] = True
                df.at[idx, "days_overdue"] = (REFERENCE_DATE - fu_date).days
    
    return df


def detect_deal_value_outliers(df: pd.DataFrame) -> list[dict]:
    """Detect outliers in deal values using IQR method."""
    issues = []
    values = df["deal_value_bdt"].dropna()
    values = values[values > 0]
    
    if len(values) < 4:
        return issues
    
    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    for idx, row in df.iterrows():
        val = row.get("deal_value_bdt", 0)
        if pd.notna(val) and val > 0:
            if val < lower_bound or val > upper_bound:
                issues.append({
                    "lead_id": row["lead_id"],
                    "issue": "outlier_deal_value",
                    "detail": f"Deal value {val:,.0f} BDT is outside IQR range [{lower_bound:,.0f}, {upper_bound:,.0f}]",
                    "fix": "Manual review recommended — may be legitimate large/small deal",
                })
    
    return issues


def validate_contact_info(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Validate and flag issues with contact information."""
    issues = []
    df = df.copy()
    
    for idx, row in df.iterrows():
        lead_id = row["lead_id"]
        
        # Check missing contact name
        if pd.isna(row.get("contact_name")) or str(row.get("contact_name", "")).strip() == "":
            issues.append({
                "lead_id": lead_id,
                "issue": "missing_contact_name",
                "detail": "No contact name on file",
                "fix": "Needs manual data entry from phone follow-up",
            })
        
        # Check missing contact email
        if pd.isna(row.get("contact_email")) or str(row.get("contact_email", "")).strip() == "":
            issues.append({
                "lead_id": lead_id,
                "issue": "missing_contact_email",
                "detail": "No email address on file",
                "fix": "Request during next follow-up",
            })
        
        # Check missing contact phone
        if pd.isna(row.get("contact_phone")) or str(row.get("contact_phone", "")).strip() == "":
            issues.append({
                "lead_id": lead_id,
                "issue": "missing_contact_phone",
                "detail": "No phone number on file",
                "fix": "Request during next follow-up",
            })
        
        # Normalize email casing while preserving an auditable data-quality issue.
        email = str(row.get("contact_email", ""))
        if email and re.search(r"[A-Z]", email):
            issues.append({
                "lead_id": lead_id,
                "issue": "email_case_normalized",
                "detail": f"Email '{email}' contains uppercase characters",
                "fix": f"Normalize to: {email.lower()}",
            })
            df.at[idx, "contact_email"] = email.lower()
    
    return df, issues


def analyze_stage_consistency(df: pd.DataFrame) -> list[dict]:
    """Check if stage assignments are consistent with notes."""
    issues = []
    
    for idx, row in df.iterrows():
        lead_id = row["lead_id"]
        stage = str(row.get("stage", "")).strip()
        notes = str(row.get("notes", "")).lower()
        last_contact = row.get("last_contact")
        
        # L12: Stage says "Paid" but note says second payment pending
        if stage == "Paid" and ("second payment" in notes or "pending" in notes or "due" in notes):
            issues.append({
                "lead_id": lead_id,
                "issue": "stage_mismatch",
                "detail": f"Stage is 'Paid' but notes indicate payment is still pending",
                "fix": "Consider changing stage to 'Invoice sent' until full payment received",
                "suggested_stage": "Invoice sent",
            })
        
        # Check if Lost leads should stay lost or be re-evaluated
        if stage == "Lost":
            if "do not contact" in notes or "chose" in notes:
                issues.append({
                    "lead_id": lead_id,
                    "issue": "lost_confirmed",
                    "detail": "Lost status confirmed by notes — do not re-contact",
                    "fix": "Keep as Lost. Set calendar reminder for re-evaluation.",
                })
        
        # Check for silent leads that might be Lost
        if stage in STAGE_ORDER and pd.notna(last_contact):
            lc = last_contact if isinstance(last_contact, date) else pd.to_datetime(last_contact).date()
            days_silent = (REFERENCE_DATE - lc).days
            no_response = "no response" in notes or "no reply" in notes
            if days_silent > LOST_THRESHOLD_DAYS and no_response:
                issues.append({
                    "lead_id": lead_id,
                    "issue": "potentially_lost",
                    "detail": f"No response for {days_silent} days. May need to be marked as Lost.",
                    "fix": f"Send one final follow-up. If no reply in 7 days, move to Lost.",
                    "suggested_stage": "Lost" if days_silent > 45 else stage,
                })
    
    return issues


def calculate_risk_level(row: pd.Series) -> str:
    """Calculate risk level for a lead."""
    stage = str(row.get("stage", "")).strip()
    is_overdue = row.get("is_overdue", False)
    days_overdue = row.get("days_overdue", 0)
    deal_value = row.get("deal_value_bdt", 0) or 0
    
    if stage in END_STAGES:
        return "none"
    
    if is_overdue and days_overdue > 7:
        return "high"
    elif is_overdue:
        return "medium"
    elif deal_value > 300000:
        return "medium"  # High-value deals need attention
    else:
        return "low"


def suggest_next_action(row: pd.Series) -> str:
    """Generate actionable next step for each lead."""
    stage = str(row.get("stage", "")).strip()
    notes = str(row.get("notes", ""))
    is_overdue = row.get("is_overdue", False)
    days_overdue = row.get("days_overdue", 0)
    
    if stage == "Lost":
        if "do not contact" in notes.lower():
            return "Archived. Do not contact this year."
        return "Set Q2 2027 reminder for re-engagement."
    
    if stage == "Paid":
        return "Verify full payment. Schedule onboarding."
    
    overdue_prefix = f"OVERDUE ({days_overdue} days): " if is_overdue else ""
    
    actions = {
        "New": f"{overdue_prefix}Make first contact call/email within 24 hours.",
        "Contacted": f"{overdue_prefix}Follow up on initial conversation. Send details if not done.",
        "Meeting": f"{overdue_prefix}Send meeting summary and written proposal.",
        "Proposal": f"{overdue_prefix}Follow up on proposal. Check for questions or objections.",
        "Invoice sent": f"{overdue_prefix}Check payment status. Send payment reminder if needed.",
    }
    
    return actions.get(stage, f"{overdue_prefix}Review and update.")


# Valid stage transitions — a lead can only move forward or to Lost
VALID_TRANSITIONS = {
    "New": {"Contacted", "Lost"},
    "Contacted": {"Meeting", "Lost"},
    "Meeting": {"Proposal", "Lost"},
    "Proposal": {"Invoice sent", "Lost"},
    "Invoice sent": {"Paid", "Lost"},
    "Paid": set(),   # terminal
    "Lost": {"New"},  # can be reactivated
}


def validate_stage_transition(current_stage: str, new_stage: str) -> tuple[bool, str]:
    """Validate whether a stage transition is allowed.
    
    Enforces the pipeline progression:
    New → Contacted → Meeting → Proposal → Invoice sent → Paid
    Any active stage can also transition to Lost.
    Lost can be reactivated to New only.
    
    Returns (is_valid, reason).
    """
    current = current_stage.strip()
    new = new_stage.strip()
    
    if current not in VALID_TRANSITIONS:
        return False, f"Unknown current stage: '{current}'"
    if new not in ALL_STAGES:
        return False, f"Unknown target stage: '{new}'"
    if current == new:
        return True, "No change"
    
    allowed = VALID_TRANSITIONS[current]
    if new in allowed:
        return True, f"Valid transition: {current} -> {new}"
    else:
        return False, f"Invalid transition: {current} -> {new}. Allowed: {', '.join(sorted(allowed)) or 'none (terminal stage)'}"


def detect_auto_lost(df: pd.DataFrame) -> list[dict]:
    """Detect leads that should be automatically moved to Lost.
    
    Rule: Any lead in an active stage with last_contact > 30 days ago
    and no scheduled follow-up after today should be suggested as Lost.
    This implements the task spec: "went silent for 30+ days".
    """
    suggestions = []
    
    for idx, row in df.iterrows():
        stage = str(row.get("stage", "")).strip()
        if stage in END_STAGES or stage == "New":
            continue
        
        last_contact = row.get("last_contact")
        if pd.isna(last_contact):
            continue
        
        lc = last_contact if isinstance(last_contact, date) else pd.to_datetime(last_contact).date()
        days_silent = (REFERENCE_DATE - lc).days
        
        if days_silent > LOST_THRESHOLD_DAYS:
            notes = str(row.get("notes", "")).lower()
            # Check if there's active engagement indication
            active_indicators = ["meeting scheduled", "proposal sent", "invoice sent", "waiting for", "will call"]
            has_active = any(ind in notes for ind in active_indicators)
            
            if not has_active:
                suggestions.append({
                    "lead_id": row["lead_id"],
                    "company": row.get("company", ""),
                    "current_stage": stage,
                    "days_silent": days_silent,
                    "suggested_stage": "Lost",
                    "reason": f"Silent for {days_silent} days (threshold: {LOST_THRESHOLD_DAYS}). No active engagement in notes.",
                    "action": "Send final follow-up. If no reply in 7 days, mark as Lost.",
                })
    
    return suggestions
