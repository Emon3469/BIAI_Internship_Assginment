"""FastAPI routes for BIAI CRM & Pipeline system.

Provides REST API endpoints for both Task 1 (CRM Enquiries) and 
Task 2 (Corporate Lead Pipeline). Ready for frontend integration.
"""

import json
import math
from pathlib import Path
from fastapi import APIRouter, HTTPException
from datetime import date

from .schemas import (
    EnquiryClassified, CRMSummary, ClassifyRequest,
    CorporateLeadCleaned, PipelineAnalytics,
    StageUpdateRequest, FollowUpUpdateRequest,
)

# Create routers
crm_router = APIRouter(prefix="/api/crm", tags=["CRM - Task 1"])
pipeline_router = APIRouter(prefix="/api/pipeline", tags=["Pipeline - Task 2"])

# In-memory data stores (populated at startup)
_crm_data: dict = {"results": [], "summary": {}}
_pipeline_data: dict = {"cleaned_data": None, "analytics": {}, "issues": [], "duplicates": []}


def _serialize_value(value):
    """Convert pandas and datetime scalars to JSON-compatible values."""
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _serialize_row(row) -> dict:
    return {column: _serialize_value(value) for column, value in row.items()}


def set_crm_data(results: list[dict], summary: dict):
    """Initialize CRM data store."""
    _crm_data["results"] = results
    _crm_data["summary"] = summary


def set_pipeline_data(data: dict):
    """Initialize pipeline data store."""
    _pipeline_data.update(data)


# ==================== TASK 1: CRM ROUTES ====================

@crm_router.get("/enquiries", response_model=list[EnquiryClassified])
async def get_all_enquiries():
    """Get all classified enquiries."""
    return _crm_data["results"]


@crm_router.get("/enquiries/{enquiry_id}", response_model=EnquiryClassified)
async def get_enquiry(enquiry_id: int):
    """Get a specific enquiry by ID."""
    for r in _crm_data["results"]:
        if r["original_id"] == enquiry_id:
            return r
    raise HTTPException(status_code=404, detail=f"Enquiry {enquiry_id} not found")


@crm_router.get("/enquiries/category/{category}")
async def get_enquiries_by_category(category: str):
    """Get enquiries filtered by category."""
    valid = ["sales_lead", "support_issue", "spam", "job_seeker", "general_inquiry"]
    if category not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {valid}")
    return [r for r in _crm_data["results"] if r["category"] == category]


@crm_router.get("/enquiries/priority/{priority}")
async def get_enquiries_by_priority(priority: str):
    """Get enquiries filtered by priority."""
    valid = ["high", "medium", "low", "none"]
    if priority not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid priority. Must be one of: {valid}")
    return [r for r in _crm_data["results"] if r["priority"] == priority]


@crm_router.get("/summary", response_model=CRMSummary)
async def get_crm_summary():
    """Get CRM dashboard summary."""
    return _crm_data["summary"]


@crm_router.get("/action-items")
async def get_action_items():
    """Get prioritized list of action items for the sales team."""
    return _crm_data["summary"].get("action_items", [])


@crm_router.get("/corporate-leads")
async def get_corporate_enquiries():
    """Get enquiries identified as corporate leads (high-value)."""
    return [r for r in _crm_data["results"] if r["is_corporate"]]


@crm_router.get("/duplicates")
async def get_duplicate_enquiries():
    """Get enquiries flagged as duplicates."""
    return [r for r in _crm_data["results"] if r["is_duplicate"]]


@crm_router.post("/classify", response_model=EnquiryClassified)
async def classify_new_enquiry(request: ClassifyRequest):
    """Classify a new incoming enquiry in real-time."""
    from src.task1_crm.classifier import classify_enquiry
    from src.task1_crm.text_processing import detect_language, normalize_phone
    
    result = classify_enquiry(
        enquiry_id=0,
        channel=request.channel,
        sender_name=request.sender_name,
        phone=request.phone,
        message=request.message,
    )
    
    language = detect_language(request.message)
    
    return EnquiryClassified(
        original_id=0,
        channel=request.channel,
        sender_name=request.sender_name,
        phone=normalize_phone(request.phone),
        message=request.message,
        category=result.category,
        sub_category=result.sub_category,
        priority=result.priority,
        language=language,
        product_interest=result.product_interest,
        sender_role=result.sender_role,
        company_name=result.company_name,
        is_corporate=result.is_corporate,
        estimated_deal_size=result.estimated_deal_size,
        needs_follow_up=result.needs_follow_up,
        suggested_action=result.suggested_action,
        auto_response=result.auto_response,
        confidence=result.confidence,
        reasoning=result.reasoning,
    )


# ==================== TASK 2: PIPELINE ROUTES ====================

@pipeline_router.get("/leads")
async def get_all_leads():
    """Get all corporate leads (cleaned)."""
    df = _pipeline_data.get("cleaned_data")
    if df is None:
        raise HTTPException(status_code=404, detail="Pipeline data not loaded")
    
    # Convert DataFrame to list of dicts, handling dates
    records = []
    for _, row in df.iterrows():
        records.append(_serialize_row(row))
    return records


@pipeline_router.get("/leads/active")
async def get_active_leads():
    """Get only active (non-duplicate) leads."""
    df = _pipeline_data.get("cleaned_data")
    if df is None:
        raise HTTPException(status_code=404, detail="Pipeline data not loaded")
    
    active = df[~df["is_duplicate"]]
    records = []
    for _, row in active.iterrows():
        records.append(_serialize_row(row))
    return records


@pipeline_router.get("/leads/{lead_id}")
async def get_lead(lead_id: str):
    """Get a specific lead by ID."""
    df = _pipeline_data.get("cleaned_data")
    if df is None:
        raise HTTPException(status_code=404, detail="Pipeline data not loaded")
    
    match = df[df["lead_id"] == lead_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    
    row = match.iloc[0]
    return _serialize_row(row)


@pipeline_router.get("/leads/stage/{stage}")
async def get_leads_by_stage(stage: str):
    """Get leads filtered by pipeline stage."""
    valid = ["New", "Contacted", "Meeting", "Proposal", "Invoice sent", "Paid", "Lost"]
    if stage not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {valid}")
    
    df = _pipeline_data.get("cleaned_data")
    if df is None:
        raise HTTPException(status_code=404, detail="Pipeline data not loaded")
    
    filtered = df[df["stage"] == stage]
    records = []
    for _, row in filtered.iterrows():
        records.append(_serialize_row(row))
    return records


@pipeline_router.get("/overdue")
async def get_overdue_leads():
    """Get all leads with overdue follow-ups."""
    df = _pipeline_data.get("cleaned_data")
    if df is None:
        raise HTTPException(status_code=404, detail="Pipeline data not loaded")
    
    overdue = df[df["is_overdue"] == True]
    records = []
    for _, row in overdue.iterrows():
        records.append(_serialize_row(row))
    return records


@pipeline_router.get("/analytics", response_model=PipelineAnalytics)
async def get_pipeline_analytics():
    """Get full pipeline analytics dashboard data."""
    analytics = _pipeline_data.get("analytics", {})
    if not analytics:
        raise HTTPException(status_code=404, detail="Analytics not available")
    return analytics


@pipeline_router.get("/issues")
async def get_data_issues():
    """Get all detected data quality issues."""
    return _pipeline_data.get("issues", [])


@pipeline_router.get("/duplicates")
async def get_pipeline_duplicates():
    """Get detected duplicate leads."""
    return _pipeline_data.get("duplicates", [])


@pipeline_router.get("/high-priority")
async def get_high_priority_actions():
    """Get high-priority action items requiring immediate attention."""
    analytics = _pipeline_data.get("analytics", {})
    return analytics.get("high_priority_actions", [])


@pipeline_router.put("/leads/{lead_id}/stage")
async def update_lead_stage(lead_id: str, request: StageUpdateRequest):
    """Update a lead's pipeline stage with transition validation."""
    from src.task2_pipeline.data_cleaner import validate_stage_transition, ALL_STAGES
    
    df = _pipeline_data.get("cleaned_data")
    if df is None:
        raise HTTPException(status_code=404, detail="Pipeline data not loaded")
    
    match = df[df["lead_id"] == lead_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    
    current_stage = str(match.iloc[0]["stage"]).strip()
    is_valid, reason = validate_stage_transition(current_stage, request.new_stage)
    
    if not is_valid:
        raise HTTPException(status_code=400, detail=reason)
    
    # Apply the update
    idx = match.index[0]
    df.at[idx, "stage"] = request.new_stage
    if request.notes:
        existing_notes = str(df.at[idx, "notes"])
        df.at[idx, "notes"] = f"{existing_notes} | Stage updated: {request.notes}"
    
    return {
        "lead_id": lead_id,
        "previous_stage": current_stage,
        "new_stage": request.new_stage,
        "transition": reason,
        "updated": True,
    }


@pipeline_router.put("/leads/{lead_id}/follow-up")
async def update_follow_up(lead_id: str, request: FollowUpUpdateRequest):
    """Update a lead's next follow-up date."""
    from datetime import date as date_type
    
    df = _pipeline_data.get("cleaned_data")
    if df is None:
        raise HTTPException(status_code=404, detail="Pipeline data not loaded")
    
    match = df[df["lead_id"] == lead_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    
    try:
        new_date = date_type.fromisoformat(request.next_follow_up)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    
    idx = match.index[0]
    df.at[idx, "next_follow_up"] = new_date
    if request.notes:
        existing_notes = str(df.at[idx, "notes"])
        df.at[idx, "notes"] = f"{existing_notes} | Follow-up updated: {request.notes}"
    
    return {
        "lead_id": lead_id,
        "next_follow_up": new_date.isoformat(),
        "updated": True,
    }


@pipeline_router.get("/auto-lost")
async def get_auto_lost_suggestions():
    """Get leads that should potentially be marked as Lost (silent 30+ days)."""
    from src.task2_pipeline.data_cleaner import detect_auto_lost
    
    df = _pipeline_data.get("cleaned_data")
    if df is None:
        raise HTTPException(status_code=404, detail="Pipeline data not loaded")
    
    return detect_auto_lost(df)
