"""CRM Enquiry Processing Engine for Task 1.

Processes all 20 enquiries: cleans data, detects language, classifies,
detects duplicates, and generates actionable CRM records.
"""

import pandas as pd
import json
from datetime import datetime
from pathlib import Path

from .text_processing import (
    normalize_text, key_text, detect_language,
    text_similarity, normalize_phone,
)
from .classifier import classify_enquiry, ClassificationResult


def load_enquiries(csv_path: str) -> pd.DataFrame:
    """Load and clean enquiry data from CSV."""
    df = pd.read_csv(csv_path)
    
    # Normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    
    # Clean text fields
    df["message"] = df["message"].fillna("").apply(normalize_text)
    df["sender_name"] = df["sender_name"].fillna("Unknown").apply(normalize_text)
    df["channel"] = df["channel"].fillna("Unknown").apply(normalize_text)
    
    # Clean phone numbers
    df["phone"] = df["phone"].astype(object).fillna("").astype(str).apply(normalize_phone)
    
    # Parse timestamps
    df["received_at"] = pd.to_datetime(df["received_at"], errors="coerce")
    
    return df


def detect_duplicate_enquiries(df: pd.DataFrame) -> dict[int, int]:
    """Detect duplicate enquiries based on sender + message similarity.
    
    Returns dict mapping duplicate_id -> original_id.
    """
    duplicates = {}
    
    for i in range(len(df)):
        if i in duplicates:
            continue
        for j in range(i + 1, len(df)):
            if j in duplicates:
                continue
            
            # Same phone number
            same_phone = (
                df.iloc[i]["phone"] and 
                df.iloc[j]["phone"] and 
                df.iloc[i]["phone"] == df.iloc[j]["phone"]
            )
            
            # Similar sender name
            name_sim = text_similarity(
                key_text(df.iloc[i]["sender_name"]),
                key_text(df.iloc[j]["sender_name"]),
            )
            
            # Similar message content
            msg_sim = text_similarity(
                key_text(df.iloc[i]["message"]),
                key_text(df.iloc[j]["message"]),
            )
            
            # Duplicate if same sender and similar topic
            if (same_phone or name_sim > 0.7) and msg_sim > 0.3:
                duplicates[j] = i  # j is duplicate of i (earlier one is original)
    
    return duplicates


def process_all_enquiries(csv_path: str) -> list[dict]:
    """Process all enquiries and return classified results.
    
    Returns list of dicts ready for database insertion or JSON output.
    """
    df = load_enquiries(csv_path)
    
    # Detect duplicates
    duplicates = detect_duplicate_enquiries(df)
    
    results = []
    for idx, row in df.iterrows():
        # Classify the enquiry
        result = classify_enquiry(
            enquiry_id=int(row["id"]),
            channel=row["channel"],
            sender_name=row["sender_name"],
            phone=row.get("phone", ""),
            message=row["message"],
        )
        
        # Detect language
        language = detect_language(row["message"])
        
        # Check if this is a duplicate
        is_dup = idx in duplicates
        dup_of = int(df.iloc[duplicates[idx]]["id"]) if is_dup else None
        
        record = {
            "original_id": int(row["id"]),
            "channel": row["channel"],
            "received_at": row["received_at"].isoformat() if pd.notna(row["received_at"]) else None,
            "sender_name": row["sender_name"],
            "phone": row.get("phone", ""),
            "message": row["message"],
            "category": result.category,
            "sub_category": result.sub_category,
            "priority": result.priority,
            "language": language,
            "product_interest": result.product_interest,
            "sender_role": result.sender_role,
            "company_name": result.company_name,
            "is_corporate": result.is_corporate,
            "estimated_deal_size": result.estimated_deal_size,
            "is_duplicate": is_dup,
            "duplicate_of_id": dup_of,
            "needs_follow_up": result.needs_follow_up,
            "suggested_action": result.suggested_action,
            "auto_response": result.auto_response,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
        }
        results.append(record)

    # --- ML Confidence Layer (adapted from datathon notebooks) ---
    # Train ensemble on the rule-based labels for confidence validation
    from .feature_extraction import EnsembleConfidenceScorer

    texts = [r["message"] for r in results]
    labels = [r["category"] for r in results]

    scorer = EnsembleConfidenceScorer()
    scorer.fit(texts, labels)

    for r in results:
        ml_scores = scorer.predict_confidence(r["message"])
        ml_top = max(ml_scores, key=ml_scores.get)
        r["ml_confidence"] = ml_scores
        r["ml_top_category"] = ml_top
        r["rule_ml_agreement"] = ml_top == r["category"]
        # Boost confidence when both agree
        if r["rule_ml_agreement"]:
            r["confidence"] = min(0.98, r["confidence"] + 0.10)
        # Flag for review when they disagree
        if not r["rule_ml_agreement"]:
            r["needs_review"] = True
            r["review_reason"] = f"Rule-based: {r['category']}, ML suggests: {ml_top}"

    return results


def generate_crm_summary(results: list[dict]) -> dict:
    """Generate summary statistics for the CRM dashboard."""
    total = len(results)
    categories = {}
    priorities = {}
    channels = {}
    languages = {}
    corporate_leads = []
    action_items = []
    
    for r in results:
        # Category counts
        cat = r["category"]
        categories[cat] = categories.get(cat, 0) + 1
        
        # Priority counts
        pri = r["priority"]
        priorities[pri] = priorities.get(pri, 0) + 1
        
        # Channel counts
        ch = r["channel"]
        channels[ch] = channels.get(ch, 0) + 1
        
        # Language counts
        lang = r["language"]
        languages[lang] = languages.get(lang, 0) + 1
        
        # Track corporate leads
        if r["is_corporate"]:
            corporate_leads.append({
                "id": r["original_id"],
                "sender": r["sender_name"],
                "company": r["company_name"],
                "deal_size": r["estimated_deal_size"],
                "product": r["product_interest"],
            })
        
        # Track action items
        if r["needs_follow_up"] and not r["is_duplicate"]:
            action_items.append({
                "id": r["original_id"],
                "priority": r["priority"],
                "sender": r["sender_name"],
                "action": r["suggested_action"],
                "category": r["category"],
            })
    
    # Sort action items by priority
    priority_order = {"high": 0, "medium": 1, "low": 2, "none": 3}
    action_items.sort(key=lambda x: priority_order.get(x["priority"], 3))
    
    # Count duplicates and unique
    duplicates = sum(1 for r in results if r["is_duplicate"])
    
    return {
        "total_enquiries": total,
        "unique_enquiries": total - duplicates,
        "duplicates": duplicates,
        "by_category": categories,
        "by_priority": priorities,
        "by_channel": channels,
        "by_language": languages,
        "corporate_leads": corporate_leads,
        "action_items": action_items,
        "sales_leads_count": categories.get("sales_lead", 0),
        "support_issues_count": categories.get("support_issue", 0),
        "spam_count": categories.get("spam", 0),
    }


def save_results(results: list[dict], summary: dict, output_dir: str):
    """Save processed results to JSON and CSV files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save detailed results as JSON
    with open(output_path / "crm_enquiries_classified.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    # Save as CSV for easy viewing
    df = pd.DataFrame(results)
    df.to_csv(output_path / "crm_enquiries_classified.csv", index=False, encoding="utf-8-sig")
    
    # Save summary
    with open(output_path / "crm_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    
    return {
        "enquiries_json": str(output_path / "crm_enquiries_classified.json"),
        "enquiries_csv": str(output_path / "crm_enquiries_classified.csv"),
        "summary_json": str(output_path / "crm_summary.json"),
    }
