"""Pydantic schemas for the API layer."""

from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional


# --- Task 1: CRM Enquiry Schemas ---

class EnquiryBase(BaseModel):
    channel: str
    sender_name: str
    phone: Optional[str] = ""
    message: str


class EnquiryClassified(EnquiryBase):
    original_id: int
    received_at: Optional[str] = None
    category: str
    sub_category: str
    priority: str
    language: str
    product_interest: str = ""
    sender_role: str = ""
    company_name: str = ""
    is_corporate: bool = False
    estimated_deal_size: str = ""
    is_duplicate: bool = False
    duplicate_of_id: Optional[int] = None
    needs_follow_up: bool = True
    suggested_action: str = ""
    auto_response: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    ml_confidence: Optional[dict] = None
    ml_top_category: Optional[str] = None
    rule_ml_agreement: Optional[bool] = None
    needs_review: bool = False
    review_reason: Optional[str] = None


class CRMSummary(BaseModel):
    total_enquiries: int
    unique_enquiries: int
    duplicates: int
    by_category: dict
    by_priority: dict
    by_channel: dict
    by_language: dict
    corporate_leads: list[dict]
    action_items: list[dict]
    sales_leads_count: int
    support_issues_count: int
    spam_count: int


class ClassifyRequest(BaseModel):
    """Request to classify a single new enquiry."""
    channel: str = Field(..., description="Channel: WhatsApp, Facebook, Website, Phone")
    sender_name: str = Field(..., description="Name of the sender")
    phone: str = Field("", description="Phone number")
    message: str = Field(..., description="Message content in any language")


# --- Task 2: Corporate Lead Schemas ---

class CorporateLeadBase(BaseModel):
    lead_id: str
    company: str
    industry: Optional[str] = ""
    contact_name: Optional[str] = ""
    contact_role: Optional[str] = ""
    contact_email: Optional[str] = ""
    contact_phone: Optional[str] = ""
    source: Optional[str] = ""
    stage: str
    deal_value_bdt: float = 0.0
    last_contact: Optional[str] = None
    next_follow_up: Optional[str] = None
    notes: Optional[str] = ""


class CorporateLeadCleaned(CorporateLeadBase):
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    is_overdue: bool = False
    days_overdue: int = 0
    suggested_stage: Optional[str] = None
    suggested_action: str = ""
    risk_level: str = "low"
    data_issues: str = "[]"


class PipelineAnalytics(BaseModel):
    reference_date: str
    total_leads: int
    unique_leads: int
    duplicates_found: int
    data_issues_count: int
    funnel: dict
    pipeline_value: dict
    overdue: dict
    by_source: dict
    by_industry: dict
    risk_distribution: dict
    high_priority_actions: list[dict]
    auto_lost_suggestions: list[dict] = []


class StageUpdateRequest(BaseModel):
    """Request to update a lead's stage."""
    lead_id: str
    new_stage: str = Field(..., description="One of: New, Contacted, Meeting, Proposal, Invoice sent, Paid, Lost")
    notes: Optional[str] = Field(None, description="Optional note about the update")


class FollowUpUpdateRequest(BaseModel):
    """Request to update a lead's follow-up date."""
    lead_id: str
    next_follow_up: str = Field(..., description="Next follow-up date in YYYY-MM-DD format")
    notes: Optional[str] = None
