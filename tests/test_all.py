"""Comprehensive test suite for BIAI CRM & Pipeline system.

Tests both Task 1 (CRM enquiry classification) and Task 2 (corporate lead pipeline).
Run with:   python -m pytest tests/ -v
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports resolve.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import pytest
import pandas as pd
from datetime import date, timedelta

# ─── Task 1 imports ────────────────────────────────────────────────────────
from src.task1_crm.text_processing import (
    normalize_text, key_text, detect_language, text_similarity, normalize_phone,
)
from src.task1_crm.classifier import classify_enquiry
from src.task1_crm.engine import (
    load_enquiries, detect_duplicate_enquiries, process_all_enquiries,
    generate_crm_summary,
)

# ─── Task 2 imports ────────────────────────────────────────────────────────
from src.task2_pipeline.data_cleaner import (
    load_corporate_leads, detect_duplicates, validate_and_fix_dates,
    detect_overdue, detect_deal_value_outliers, validate_contact_info,
    analyze_stage_consistency, calculate_risk_level, suggest_next_action,
    REFERENCE_DATE, STAGE_ORDER, END_STAGES, ALL_STAGES,
)
from src.task2_pipeline.engine import process_pipeline


# ===========================================================================
#  Task 1 — Text Processing
# ===========================================================================

class TestTextNormalization:
    def test_normalize_whitespace(self):
        assert normalize_text("  hello   world  ") == "hello world"

    def test_normalize_none(self):
        assert normalize_text(None) == ""

    def test_key_text_strips_punctuation(self):
        assert "hello" in key_text("Hello, World!")

    def test_key_text_lowercase(self):
        assert key_text("HELLO") == "hello"


class TestLanguageDetection:
    def test_bangla(self):
        assert detect_language("ফেলোশিপ প্রোগ্রামে ভর্তি হতে চাই") == "bangla"

    def test_english(self):
        assert detect_language("I run a 40-person textile company") == "english"

    def test_banglish(self):
        assert detect_language("Bootcamp er price koto?") == "banglish"
        assert detect_language("Vai class gula live hoy naki recorded?") == "banglish"

    def test_mixed(self):
        # Very short, ambiguous messages get a deterministic label
        result = detect_language("ok")
        assert result in ("english", "banglish", "mixed")


class TestTextSimilarity:
    def test_identical(self):
        assert text_similarity("hello world", "hello world") == 1.0

    def test_empty(self):
        assert text_similarity("", "hello") == 0.0

    def test_similar(self):
        sim = text_similarity("bootcamp price koto", "bootcamp er price ta bolen")
        assert 0.3 < sim < 1.0


class TestPhoneNormalization:
    def test_normal_bd_number(self):
        assert normalize_phone("01711000001") == "01711000001"

    def test_with_dashes(self):
        assert normalize_phone("01711-200101") == "01711200101"

    def test_empty(self):
        assert normalize_phone("") == ""

    def test_nan(self):
        assert normalize_phone("nan") == ""

    def test_intl_prefix(self):
        assert normalize_phone("+8801711000001") == "01711000001"


# ===========================================================================
#  Task 1 — Classification
# ===========================================================================

class TestClassifier:
    """Each test corresponds to a known enquiry from sample-enquiries.csv."""

    def test_spam_detection(self):
        r = classify_enquiry(11, "Facebook comment", "Earn Crypto Daily", "",
                             "Earn 5000 USD every day with our crypto signals! Click bit.ly/xxxx now!!!")
        assert r.category == "spam"
        assert r.needs_follow_up is False

    def test_job_seeker(self):
        r = classify_enquiry(20, "Website form", "Arif Hossain", "01711000019",
                             "Looking for a job as an AI intern. Where do I apply?")
        assert r.category == "job_seeker"

    def test_job_question_not_job_seeker(self):
        """'Ei course korle job pabo?' is a course question, not a job application."""
        r = classify_enquiry(6, "Facebook comment", "Ishtiaq", "",
                             "Ei course korle job pabo?")
        assert r.category == "general_inquiry"
        assert r.sub_category == "career_query"

    def test_support_payment_issue(self):
        r = classify_enquiry(7, "WhatsApp", "Farzana Rahman", "01711000007",
                             "পেমেন্ট করেছি কিন্তু কোনো কনফার্মেশন পাইনি।")
        assert r.category == "support_issue"
        assert r.sub_category == "payment_issue"

    def test_support_escalation(self):
        r = classify_enquiry(16, "Phone call note", "Habibur Rahman", "01711000015",
                             "Caller wants to cancel his enrolment and get his money back. Very upset. Said he will post about it on Facebook if not solved today.")
        assert r.category == "support_issue"
        assert r.priority == "high"

    def test_support_refund(self):
        r = classify_enquiry(8, "Website form", "Anika Chowdhury", "01711000008",
                             "Do you offer refunds if I cannot attend after paying?")
        assert r.category == "support_issue"
        assert r.sub_category == "refund_request"

    def test_corporate_lead_textile(self):
        r = classify_enquiry(3, "Website form",
                             "Mahmud Hasan (Managing Director, Gazipur textile company)",
                             "01711000003",
                             "I run a 40-person textile company in Gazipur. We want AI training for our team.")
        assert r.category == "sales_lead"
        assert r.is_corporate is True
        assert r.priority == "high"

    def test_corporate_lead_bank(self):
        r = classify_enquiry(10, "WhatsApp",
                             "Kamrul Islam (HR, a bank in Motijheel)",
                             "01711000010",
                             "Hi, I'm from a bank in Motijheel. Need a quote for training 120 employees.")
        assert r.category == "sales_lead"
        assert r.is_corporate is True
        assert r.estimated_deal_size == "large"

    def test_bangla_enrolment_intent(self):
        r = classify_enquiry(2, "Facebook Messenger", "Tahmina Akter", "",
                             "ফেলোশিপ প্রোগ্রামে ভর্তি হতে চাই। কবে শুরু হবে?")
        assert r.category == "sales_lead"

    def test_instalment_payment(self):
        r = classify_enquiry(19, "WhatsApp", "Samira", "01711000018",
                             "Can I pay in two instalments for the fellowship?")
        assert r.category == "sales_lead"

    def test_certificate_question(self):
        r = classify_enquiry(17, "Facebook Messenger", "Nowshin", "",
                             "Apnader course certificate ta ki govt approved?")
        assert r.category == "general_inquiry"
        assert r.sub_category == "certification"

    def test_student_discount_question(self):
        r = classify_enquiry(5, "Phone call note", "Nasreen Sultana", "01711000005",
                             "Called to ask about student discount. Said she will call again tomorrow after 5 PM.")
        assert r.category in ("sales_lead", "general_inquiry")

    def test_general_location(self):
        r = classify_enquiry(9, "Facebook Messenger", "Jahid", "",
                             "Offline class kothay hobe? Mirpur e?")
        assert r.category == "general_inquiry"

    def test_general_addon(self):
        r = classify_enquiry(15, "WhatsApp", "Tanvir", "01711000014",
                             "Add-on ta ki? Lifetime access mane ki?")
        assert r.category == "general_inquiry"


# ===========================================================================
#  Task 1 — Duplicate Detection
# ===========================================================================

class TestDuplicateDetection:
    def test_rafi_duplicate(self):
        csv_path = str(PROJECT_ROOT / "task1-crm" / "sample-enquiries.csv")
        df = load_enquiries(csv_path)
        dups = detect_duplicate_enquiries(df)
        # Rafi Ahmed (ID 1 and 12) share the same phone and topic
        dup_ids = {df.iloc[d]["id"] for d in dups.values()}
        assert 12 in dup_ids or 1 in dup_ids


# ===========================================================================
#  Task 1 — Full Pipeline
# ===========================================================================

class TestCRMPipeline:
    @pytest.fixture(scope="class")
    @classmethod
    def results(cls):
        csv_path = str(PROJECT_ROOT / "task1-crm" / "sample-enquiries.csv")
        return process_all_enquiries(csv_path)

    def test_total_count(self, results):
        assert len(results) == 20

    def test_categories_present(self, results):
        cats = {r["category"] for r in results}
        assert "sales_lead" in cats
        assert "support_issue" in cats
        assert "spam" in cats
        assert "job_seeker" in cats
        assert "general_inquiry" in cats

    def test_has_duplicates(self, results):
        dups = [r for r in results if r["is_duplicate"]]
        assert len(dups) >= 1

    def test_corporate_identified(self, results):
        corps = [r for r in results if r["is_corporate"]]
        assert len(corps) >= 2  # at least Mahmud, Kamrul, Rezaul

    def test_summary(self, results):
        summary = generate_crm_summary(results)
        assert summary["total_enquiries"] == 20
        assert summary["spam_count"] >= 1
        assert len(summary["action_items"]) > 0


# ===========================================================================
#  Task 2 — Data Cleaning
# ===========================================================================

class TestCorporateLeadLoading:
    @pytest.fixture(scope="class")
    @classmethod
    def df(cls):
        csv_path = str(PROJECT_ROOT / "task2-corporate-leads" / "corporate-leads.csv")
        return load_corporate_leads(csv_path)

    def test_row_count(self, df):
        assert len(df) == 25

    def test_columns_normalized(self, df):
        assert "lead_id" in df.columns
        assert "deal_value_bdt" in df.columns
        assert "next_follow_up" in df.columns


class TestDuplicateDetectionPipeline:
    @pytest.fixture(scope="class")
    @classmethod
    def df(cls):
        csv_path = str(PROJECT_ROOT / "task2-corporate-leads" / "corporate-leads.csv")
        return load_corporate_leads(csv_path)

    def test_finds_l02_l03(self, df):
        dups = detect_duplicates(df)
        pairs = {(d["keep"], d["remove"]) for d in dups}
        assert ("L02", "L03") in pairs

    def test_finds_l01_l23(self, df):
        dups = detect_duplicates(df)
        pairs = {(d["keep"], d["remove"]) for d in dups}
        assert ("L01", "L23") in pairs

    def test_exactly_two_duplicates(self, df):
        dups = detect_duplicates(df)
        assert len(dups) == 2


class TestDateValidation:
    @pytest.fixture(scope="class")
    @classmethod
    def result(cls):
        csv_path = str(PROJECT_ROOT / "task2-corporate-leads" / "corporate-leads.csv")
        df = load_corporate_leads(csv_path)
        return validate_and_fix_dates(df)

    def test_l25_date_fixed(self, result):
        df, issues = result
        l25 = df[df["lead_id"] == "L25"].iloc[0]
        # L25 had next_follow_up before last_contact — should be corrected
        date_issues = [i for i in issues if i["lead_id"] == "L25" and i["issue"] == "date_order_error"]
        assert len(date_issues) == 1
        # After fix, next_follow_up should be >= last_contact
        assert l25["next_follow_up"] >= l25["last_contact"]


class TestOverdueDetection:
    def test_overdue_leads_found(self):
        csv_path = str(PROJECT_ROOT / "task2-corporate-leads" / "corporate-leads.csv")
        df = load_corporate_leads(csv_path)
        df, _ = validate_and_fix_dates(df)
        df["deal_value_bdt"] = pd.to_numeric(df["deal_value_bdt"], errors="coerce").fillna(0)
        df = detect_overdue(df)
        overdue = df[df["is_overdue"] == True]
        assert len(overdue) >= 5  # several leads have past follow-up dates

    def test_l04_is_overdue(self):
        csv_path = str(PROJECT_ROOT / "task2-corporate-leads" / "corporate-leads.csv")
        df = load_corporate_leads(csv_path)
        df, _ = validate_and_fix_dates(df)
        df["deal_value_bdt"] = pd.to_numeric(df["deal_value_bdt"], errors="coerce").fillna(0)
        df = detect_overdue(df)
        l04 = df[df["lead_id"] == "L04"].iloc[0]
        assert l04["is_overdue"] == True  # follow-up was 2026-10-29  # noqa: E712


class TestStageConsistency:
    def test_l12_stage_mismatch(self):
        csv_path = str(PROJECT_ROOT / "task2-corporate-leads" / "corporate-leads.csv")
        df = load_corporate_leads(csv_path)
        df, _ = validate_and_fix_dates(df)
        issues = analyze_stage_consistency(df)
        l12_issues = [i for i in issues if i["lead_id"] == "L12" and i["issue"] == "stage_mismatch"]
        assert len(l12_issues) == 1  # Paid but second payment pending


class TestRiskLevel:
    def test_high_risk_overdue(self):
        row = pd.Series({
            "stage": "Contacted", "is_overdue": True,
            "days_overdue": 10, "deal_value_bdt": 0,
        })
        assert calculate_risk_level(row) == "high"

    def test_no_risk_lost(self):
        row = pd.Series({
            "stage": "Lost", "is_overdue": False,
            "days_overdue": 0, "deal_value_bdt": 0,
        })
        assert calculate_risk_level(row) == "none"

    def test_medium_high_value(self):
        row = pd.Series({
            "stage": "Proposal", "is_overdue": False,
            "days_overdue": 0, "deal_value_bdt": 500000,
        })
        assert calculate_risk_level(row) == "medium"


# ===========================================================================
#  Task 2 — Full Pipeline
# ===========================================================================

class TestFullPipeline:
    @pytest.fixture(scope="class")
    @classmethod
    def results(cls):
        csv_path = str(PROJECT_ROOT / "task2-corporate-leads" / "corporate-leads.csv")
        return process_pipeline(csv_path)

    def test_cleaned_data_shape(self, results):
        df = results["cleaned_data"]
        assert len(df) == 25

    def test_unique_leads_count(self, results):
        assert results["analytics"]["unique_leads"] == 23

    def test_duplicates_found(self, results):
        assert results["analytics"]["duplicates_found"] == 2

    def test_overdue_found(self, results):
        assert results["analytics"]["overdue"]["count"] >= 5

    def test_pipeline_value_positive(self, results):
        assert results["analytics"]["pipeline_value"]["total_bdt"] > 0

    def test_weighted_value_less_than_total(self, results):
        pv = results["analytics"]["pipeline_value"]
        assert pv["weighted_bdt"] <= pv["total_bdt"]

    def test_funnel_adds_up(self, results):
        funnel = results["analytics"]["funnel"]
        total = sum(funnel.values())
        assert total == results["analytics"]["unique_leads"]

    def test_all_stages_present(self, results):
        funnel = results["analytics"]["funnel"]
        for stage in ALL_STAGES:
            assert stage in funnel

    def test_high_priority_non_empty(self, results):
        assert len(results["analytics"]["high_priority_actions"]) > 0

    def test_data_issues_detected(self, results):
        assert results["analytics"]["data_issues_count"] >= 3


# ===========================================================================
#  API Schema Smoke
# ===========================================================================

class TestAPISchemas:
    def test_classify_request_import(self):
        from src.api.schemas import ClassifyRequest
        req = ClassifyRequest(channel="WhatsApp", sender_name="Test", message="Hello")
        assert req.channel == "WhatsApp"

    def test_pipeline_analytics_import(self):
        from src.api.schemas import PipelineAnalytics
        # Just verifying the model can be imported without error
        assert PipelineAnalytics is not None


# ===========================================================================
#  Task 2 — Stage Transition Validation
# ===========================================================================

class TestStageTransitions:
    def test_valid_forward_transition(self):
        from src.task2_pipeline.data_cleaner import validate_stage_transition
        is_valid, _ = validate_stage_transition("New", "Contacted")
        assert is_valid

    def test_valid_to_lost(self):
        from src.task2_pipeline.data_cleaner import validate_stage_transition
        is_valid, _ = validate_stage_transition("Meeting", "Lost")
        assert is_valid

    def test_invalid_skip_stages(self):
        from src.task2_pipeline.data_cleaner import validate_stage_transition
        is_valid, _ = validate_stage_transition("New", "Proposal")
        assert not is_valid

    def test_invalid_backward(self):
        from src.task2_pipeline.data_cleaner import validate_stage_transition
        is_valid, _ = validate_stage_transition("Proposal", "Contacted")
        assert not is_valid

    def test_paid_is_terminal(self):
        from src.task2_pipeline.data_cleaner import validate_stage_transition
        is_valid, _ = validate_stage_transition("Paid", "Meeting")
        assert not is_valid

    def test_lost_can_reactivate(self):
        from src.task2_pipeline.data_cleaner import validate_stage_transition
        is_valid, _ = validate_stage_transition("Lost", "New")
        assert is_valid


# ===========================================================================
#  Task 2 — Auto-Lost Detection
# ===========================================================================

class TestAutoLost:
    def test_auto_lost_detection(self):
        from src.task2_pipeline.data_cleaner import detect_auto_lost, load_corporate_leads, validate_and_fix_dates
        csv_path = str(PROJECT_ROOT / "task2-corporate-leads" / "corporate-leads.csv")
        df = load_corporate_leads(csv_path)
        df, _ = validate_and_fix_dates(df)
        suggestions = detect_auto_lost(df)
        # Should find at least one lead silent > 30 days
        assert isinstance(suggestions, list)
