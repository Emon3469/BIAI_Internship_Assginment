"""Database models and engine setup for the BIAI CRM system.

Uses SQLite for lightweight, portable storage. Two main tables:
- enquiries: Task 1 CRM enquiries with classification results
- corporate_leads: Task 2 pipeline leads with stage tracking

The database provides persistence so the API server can restart without
re-processing. Data is loaded from CSV on first run, then served from
the database on subsequent runs.
"""

from datetime import datetime, date
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, DateTime,
    Text, Boolean, Enum as SQLEnum, event
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import enum
import json
from pathlib import Path

DATABASE_URL = "sqlite:///biai_crm.db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class EnquiryCategory(str, enum.Enum):
    SALES_LEAD = "sales_lead"
    SUPPORT_ISSUE = "support_issue"
    SPAM = "spam"
    JOB_SEEKER = "job_seeker"
    GENERAL_INQUIRY = "general_inquiry"


class EnquiryPriority(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"  # for spam


class Language(str, enum.Enum):
    BANGLA = "bangla"
    BANGLISH = "banglish"
    ENGLISH = "english"
    MIXED = "mixed"


class PipelineStage(str, enum.Enum):
    NEW = "New"
    CONTACTED = "Contacted"
    MEETING = "Meeting"
    PROPOSAL = "Proposal"
    INVOICE_SENT = "Invoice sent"
    PAID = "Paid"
    LOST = "Lost"


class Enquiry(Base):
    """Task 1: CRM Enquiry model."""
    __tablename__ = "enquiries"

    id = Column(Integer, primary_key=True)
    original_id = Column(Integer, nullable=False)
    channel = Column(String(50), nullable=False)
    received_at = Column(DateTime, nullable=True)
    sender_name = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=True)
    message = Column(Text, nullable=False)
    # Classification fields
    category = Column(String(30), nullable=True)
    sub_category = Column(String(50), nullable=True)
    priority = Column(String(10), nullable=True)
    language = Column(String(10), nullable=True)
    confidence = Column(Float, default=0.0)
    reasoning = Column(Text, nullable=True)
    # Extracted information
    product_interest = Column(String(200), nullable=True)
    sender_role = Column(String(100), nullable=True)
    company_name = Column(String(200), nullable=True)
    is_corporate = Column(Boolean, default=False)
    estimated_deal_size = Column(String(20), nullable=True)
    # Duplicate tracking
    is_duplicate = Column(Boolean, default=False)
    duplicate_of_id = Column(Integer, nullable=True)
    # Follow-up
    needs_follow_up = Column(Boolean, default=True)
    suggested_action = Column(Text, nullable=True)
    auto_response = Column(Text, nullable=True)
    # ML confidence (from ensemble scorer)
    ml_confidence_json = Column(Text, nullable=True)  # JSON dict of category scores
    ml_top_category = Column(String(30), nullable=True)
    rule_ml_agreement = Column(Boolean, nullable=True)
    # Metadata
    processed_at = Column(DateTime, default=datetime.utcnow)


class CorporateLead(Base):
    """Task 2: Corporate Lead Pipeline model."""
    __tablename__ = "corporate_leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(String(10), nullable=False, unique=True)
    company = Column(String(200), nullable=False)
    industry = Column(String(100), nullable=True)
    contact_name = Column(String(200), nullable=True)
    contact_role = Column(String(200), nullable=True)
    contact_email = Column(String(200), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    source = Column(String(50), nullable=True)
    stage = Column(String(30), nullable=False)
    deal_value_bdt = Column(Float, default=0.0)
    last_contact = Column(Date, nullable=True)
    next_follow_up = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    # Cleaning metadata
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(String(10), nullable=True)
    is_overdue = Column(Boolean, default=False)
    days_overdue = Column(Integer, default=0)
    data_issues = Column(Text, nullable=True)  # JSON list of issues found
    suggested_stage = Column(String(30), nullable=True)
    suggested_action = Column(Text, nullable=True)
    risk_level = Column(String(10), nullable=True)  # high, medium, low
    # Metadata
    processed_at = Column(DateTime, default=datetime.utcnow)
    original_data = Column(Text, nullable=True)  # JSON of original row


class StageHistory(Base):
    """Tracks stage transitions for audit trail."""
    __tablename__ = "stage_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(String(10), nullable=False)
    from_stage = Column(String(30), nullable=False)
    to_stage = Column(String(30), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    changed_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_enquiries_to_db(results: list[dict], db: Session):
    """Persist classified enquiries to the database."""
    for r in results:
        rec_at = r.get("received_at")
        if isinstance(rec_at, str):
            try:
                rec_at = datetime.fromisoformat(rec_at)
            except ValueError:
                rec_at = None
        enquiry = Enquiry(
            original_id=r["original_id"],
            channel=r["channel"],
            received_at=rec_at,
            sender_name=r["sender_name"],
            phone=r.get("phone", ""),
            message=r["message"],
            category=r["category"],
            sub_category=r["sub_category"],
            priority=r["priority"],
            language=r["language"],
            confidence=r.get("confidence", 0),
            reasoning=r.get("reasoning", ""),
            product_interest=r.get("product_interest", ""),
            sender_role=r.get("sender_role", ""),
            company_name=r.get("company_name", ""),
            is_corporate=r.get("is_corporate", False),
            estimated_deal_size=r.get("estimated_deal_size", ""),
            is_duplicate=r.get("is_duplicate", False),
            duplicate_of_id=r.get("duplicate_of_id"),
            needs_follow_up=r.get("needs_follow_up", True),
            suggested_action=r.get("suggested_action", ""),
            auto_response=r.get("auto_response", ""),
            ml_confidence_json=json.dumps(r.get("ml_confidence", {})),
            ml_top_category=r.get("ml_top_category", ""),
            rule_ml_agreement=r.get("rule_ml_agreement"),
        )
        db.add(enquiry)
    db.commit()


def save_leads_to_db(df, db: Session):
    """Persist cleaned corporate leads to the database."""
    import pandas as pd
    for _, row in df.iterrows():
        lc = row.get("last_contact")
        if pd.notna(lc):
            if isinstance(lc, str):
                try:
                    lc = datetime.fromisoformat(lc).date()
                except ValueError:
                    lc = None
        else:
            lc = None

        nfu = row.get("next_follow_up")
        if pd.notna(nfu):
            if isinstance(nfu, str):
                try:
                    nfu = datetime.fromisoformat(nfu).date()
                except ValueError:
                    nfu = None
        else:
            nfu = None

        lead = CorporateLead(
            lead_id=str(row["lead_id"]),
            company=str(row.get("company", "")),
            industry=str(row.get("industry", "")),
            contact_name=str(row.get("contact_name", "")),
            contact_role=str(row.get("contact_role", "")),
            contact_email=str(row.get("contact_email", "")),
            contact_phone=str(row.get("contact_phone", "")),
            source=str(row.get("source", "")),
            stage=str(row.get("stage", "")),
            deal_value_bdt=float(row.get("deal_value_bdt", 0) or 0),
            last_contact=lc,
            next_follow_up=nfu,
            notes=str(row.get("notes", "")),
            is_duplicate=bool(row.get("is_duplicate", False)),
            duplicate_of=str(row.get("duplicate_of", "")) if pd.notna(row.get("duplicate_of")) else None,
            is_overdue=bool(row.get("is_overdue", False)),
            days_overdue=int(row.get("days_overdue", 0)),
            data_issues=str(row.get("data_issues", "[]")),
            suggested_stage=str(row.get("suggested_stage", "")) if pd.notna(row.get("suggested_stage")) else None,
            suggested_action=str(row.get("suggested_action", "")),
            risk_level=str(row.get("risk_level", "low")),
            original_data=str(row.get("original_data", "")),
        )
        db.add(lead)
    db.commit()
