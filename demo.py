"""Interactive demo script for the BIAI CRM & Pipeline system.

Run this to see the system in action with formatted console output.
No server required — processes data directly and prints results.

Usage:  python demo.py
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.task1_crm.engine import process_all_enquiries, generate_crm_summary
from src.task2_pipeline.engine import process_pipeline


def print_header(title: str):
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_section(title: str):
    print(f"\n--- {title} ---")


def demo_task1():
    print_header("TASK 1: AI-Powered CRM Enquiry Classifier")

    csv = str(PROJECT_ROOT / "task1-crm" / "sample-enquiries.csv")
    results = process_all_enquiries(csv)
    summary = generate_crm_summary(results)

    # Overview
    print_section("Overview")
    print(f"  Total enquiries processed : {summary['total_enquiries']}")
    print(f"  Unique enquiries          : {summary['unique_enquiries']}")
    print(f"  Duplicates detected       : {summary['duplicates']}")

    # Category breakdown
    print_section("Classification Breakdown")
    cats = summary["by_category"]
    labels = {
        "sales_lead":      "Sales Leads      ",
        "general_inquiry": "General Inquiries",
        "support_issue":   "Support Issues   ",
        "spam":            "Spam             ",
        "job_seeker":      "Job Seekers      ",
    }
    for key, label in labels.items():
        count = cats.get(key, 0)
        bar = "#" * count
        print(f"  {label} : {bar} {count}")

    # Language distribution
    print_section("Language Distribution")
    for lang, count in summary["by_language"].items():
        print(f"  {lang:10s} : {count}")

    # Channel distribution
    print_section("Channel Distribution")
    for ch, count in summary["by_channel"].items():
        print(f"  {ch:22s} : {count}")

    # Corporate leads identified
    print_section("Corporate Leads Identified (High Value)")
    for corp in summary["corporate_leads"]:
        print(f"  [ID {corp['id']:2d}] {corp['sender']}")
        print(f"         Company: {corp['company']}")
        print(f"         Product: {corp['product'] or 'TBD'} | Deal Size: {corp['deal_size']}")

    # Prioritised action items
    print_section("Prioritised Action Queue (Top 10)")
    for i, item in enumerate(summary["action_items"][:10], 1):
        pri = item["priority"].upper()
        print(f"  {i:2d}. [{pri:6s}] ID {item['id']:2d} - {item['sender']}")
        print(f"      Action: {item['action']}")

    # Show each classification
    print_section("All 20 Enquiries - Detailed Classification")
    print(f"  {'ID':>3s}  {'Category':<18s} {'SubCategory':<24s} {'Pri':<7s} {'Lang':<10s} {'Corp':<5s} {'Dup':<4s} Sender")
    print(f"  {'---':>3s}  {'--------':<18s} {'-----------':<24s} {'---':<7s} {'----':<10s} {'----':<5s} {'---':<4s} ------")
    for r in results:
        oid = r["original_id"]
        cat = r["category"]
        sub = r["sub_category"]
        pri = r["priority"]
        lang = r["language"]
        corp = "Yes" if r["is_corporate"] else ""
        dup = "Yes" if r["is_duplicate"] else ""
        name = r["sender_name"][:30]
        print(f"  {oid:3d}  {cat:<18s} {sub:<24s} {pri:<7s} {lang:<10s} {corp:<5s} {dup:<4s} {name}")

    return results, summary


def demo_task2():
    print_header("TASK 2: Corporate Lead Pipeline Manager")

    csv = str(PROJECT_ROOT / "task2-corporate-leads" / "corporate-leads.csv")
    result = process_pipeline(csv)
    analytics = result["analytics"]
    df = result["cleaned_data"]
    active = df[~df["is_duplicate"]]

    # Overview
    print_section("Overview")
    print(f"  Reference date            : {analytics['reference_date']}")
    print(f"  Total leads loaded        : {analytics['total_leads']}")
    print(f"  Duplicates removed        : {analytics['duplicates_found']}")
    print(f"  Active unique leads       : {analytics['unique_leads']}")
    print(f"  Data issues detected      : {analytics['data_issues_count']}")

    # Pipeline funnel
    print_section("Pipeline Funnel")
    funnel = analytics["funnel"]
    max_count = max(funnel.values()) if funnel.values() else 1
    for stage, count in funnel.items():
        bar = "#" * count
        pct = count / analytics["unique_leads"] * 100 if analytics["unique_leads"] else 0
        print(f"  {stage:15s} | {bar:<12s} {count:2d}  ({pct:.0f}%)")

    # Deal value summary
    print_section("Pipeline Value (BDT)")
    pv = analytics["pipeline_value"]
    print(f"  Total pipeline value      : {pv['total_bdt']:>12,.0f} BDT")
    print(f"  Weighted (stage-adjusted) : {pv['weighted_bdt']:>12,.0f} BDT")
    print(f"  Average deal value        : {pv['average_deal_bdt']:>12,.0f} BDT")
    print(f"  Leads with agreed value   : {pv['deals_with_value']}")

    # Overdue follow-ups
    print_section(f"Overdue Follow-ups ({analytics['overdue']['count']} leads)")
    for lead in analytics["overdue"]["leads"]:
        val_str = f" | Value: {lead['deal_value']:,.0f} BDT" if lead["deal_value"] > 0 else ""
        print(f"  [{lead['lead_id']}] {lead['company']:<30s} Stage: {lead['stage']:<15s} {lead['days_overdue']:>2d} days overdue{val_str}")

    # Duplicates found
    print_section("Duplicates Detected & Merged")
    for dup in result["duplicates"]:
        keep_row = df[df["lead_id"] == dup["keep"]].iloc[0]
        rem_row = df[df["lead_id"] == dup["remove"]].iloc[0]
        print(f"  KEEP   {dup['keep']}: {keep_row['company']}")
        print(f"  REMOVE {dup['remove']}: {rem_row['company']}")
        print(f"  Reason: {dup['reason']}")
        print()

    # Data quality issues
    print_section(f"Data Quality Issues ({analytics['data_issues_count']})")
    for issue in result["issues"]:
        print(f"  [{issue['lead_id']}] {issue['issue']}: {issue['detail']}")
        print(f"         Fix: {issue['fix']}")

    # Risk distribution
    print_section("Risk Distribution")
    for level, count in analytics["risk_distribution"].items():
        bar = "#" * count
        print(f"  {level:7s} : {bar} {count}")

    # High priority action items
    print_section(f"High Priority Actions ({len(analytics['high_priority_actions'])})")
    for action in analytics["high_priority_actions"]:
        val_str = f" | {action['deal_value']:,.0f} BDT" if action["deal_value"] > 0 else ""
        print(f"  [{action['lead_id']}] {action['company']:<25s} {action['stage']:<15s} {action['days_overdue']:>2d}d overdue{val_str}")
        print(f"         -> {action['action']}")

    # Source analysis
    print_section("Leads by Source")
    for src, count in analytics["by_source"].items():
        print(f"  {src:15s} : {count}")

    # Industry analysis
    print_section("Leads by Industry")
    for ind, count in analytics["by_industry"].items():
        print(f"  {ind:15s} : {count}")

    # Full active pipeline view
    print_section("Active Pipeline - All Leads")
    print(f"  {'ID':<5s} {'Company':<28s} {'Stage':<15s} {'Value':>10s} {'Follow-up':>11s} {'Overdue':>8s} {'Risk':<7s}")
    print(f"  {'--':<5s} {'-------':<28s} {'-----':<15s} {'-----':>10s} {'---------':>11s} {'-------':>8s} {'----':<7s}")
    for _, row in active.iterrows():
        lid = str(row["lead_id"])
        comp = str(row["company"])[:27]
        stage = str(row["stage"])
        val = f"{row['deal_value_bdt']:,.0f}" if row["deal_value_bdt"] > 0 else "-"
        fu = str(row["next_follow_up"]) if row.get("next_follow_up") and str(row.get("next_follow_up")) != "None" else "-"
        od = f"{int(row['days_overdue'])}d" if row.get("is_overdue") else "-"
        risk = str(row.get("risk_level", ""))
        print(f"  {lid:<5s} {comp:<28s} {stage:<15s} {val:>10s} {fu:>11s} {od:>8s} {risk:<7s}")

    return result, analytics


def main():
    print()
    print("*" * 72)
    print("*  BIAI CRM & Corporate Lead Pipeline - AI-Powered Demo           *")
    print("*  All data is fictional. Reference date: 1 November 2026.        *")
    print("*" * 72)

    crm_results, crm_summary = demo_task1()
    pipeline_result, pipeline_analytics = demo_task2()

    print_header("DEMO COMPLETE")
    print()
    print("  Start the API server:  python main.py")
    print("  Run tests:             python -m pytest tests/ -v")
    print("  API documentation:     http://localhost:8000/docs")
    print()
    print("  Output files saved to: outputs/task1/ and outputs/task2/")
    print()


if __name__ == "__main__":
    main()
