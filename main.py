"""BIAI CRM & Corporate Lead Pipeline — Main Application.

Starts FastAPI server with both Task 1 (CRM) and Task 2 (Pipeline) endpoints.
Processes data on startup and serves results via REST API.

Usage:
    python main.py                    # Start API server on port 8000
    python main.py --process-only     # Process data and save to files only
    python main.py --port 3000        # Start on custom port
"""

import sys
import os
import json
import argparse
import asyncio
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="BIAI CRM & Lead Pipeline",
        description=(
            "AI-powered CRM system for enquiry classification (Task 1) "
            "and corporate lead pipeline management (Task 2)."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS middleware for frontend integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import and include routers
    from src.api.routes import crm_router, pipeline_router
    app.include_router(crm_router)
    app.include_router(pipeline_router)
    
    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "healthy"}

    out_dir = PROJECT_ROOT / "out"
    if out_dir.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(out_dir), html=True), name="frontend")
    else:
        @app.get("/", tags=["Health"])
        async def root():
            return {
                "status": "running",
                "service": "BIAI CRM & Lead Pipeline",
                "version": "1.0.0",
                "endpoints": {
                    "docs": "/docs",
                    "crm_enquiries": "/api/crm/enquiries",
                    "crm_summary": "/api/crm/summary",
                    "crm_classify": "/api/crm/classify",
                    "pipeline_leads": "/api/pipeline/leads",
                    "pipeline_analytics": "/api/pipeline/analytics",
                    "pipeline_overdue": "/api/pipeline/overdue",
                },
            }
    
    return app


def process_data(output_dir: str = "outputs") -> dict:
    """Process both tasks and return results."""
    from src.task1_crm.engine import process_all_enquiries, generate_crm_summary, save_results
    from src.task2_pipeline.engine import process_pipeline, save_pipeline_results
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # ---- Task 1: CRM Enquiries ----
    print("=" * 60)
    print("TASK 1: Processing CRM Enquiries...")
    print("=" * 60)
    
    crm_csv = str(PROJECT_ROOT / "task1-crm" / "sample-enquiries.csv")
    crm_results = process_all_enquiries(crm_csv)
    crm_summary = generate_crm_summary(crm_results)
    crm_files = save_results(crm_results, crm_summary, str(output_path / "task1"))
    
    print(f"\n[OK] Processed {crm_summary['total_enquiries']} enquiries")
    print(f"  - Sales leads: {crm_summary['sales_leads_count']}")
    print(f"  - Support issues: {crm_summary['support_issues_count']}")
    print(f"  - Spam: {crm_summary['spam_count']}")
    print(f"  - Duplicates found: {crm_summary['duplicates']}")
    print(f"  - Files saved to: {output_path / 'task1'}")
    
    # ---- Task 2: Corporate Lead Pipeline ----
    print("\n" + "=" * 60)
    print("TASK 2: Processing Corporate Lead Pipeline...")
    print("=" * 60)
    
    pipeline_csv = str(PROJECT_ROOT / "task2-corporate-leads" / "corporate-leads.csv")
    pipeline_results = process_pipeline(pipeline_csv)
    pipeline_files = save_pipeline_results(pipeline_results, str(output_path / "task2"))
    
    analytics = pipeline_results["analytics"]
    print(f"\n[OK] Processed {analytics['total_leads']} leads")
    print(f"  - Unique leads: {analytics['unique_leads']}")
    print(f"  - Duplicates: {analytics['duplicates_found']}")
    print(f"  - Data issues: {analytics['data_issues_count']}")
    print(f"  - Overdue follow-ups: {analytics['overdue']['count']}")
    print(f"  - Total pipeline value: {analytics['pipeline_value']['total_bdt']:,.0f} BDT")
    print(f"  - Weighted pipeline: {analytics['pipeline_value']['weighted_bdt']:,.0f} BDT")
    print(f"  - Files saved to: {output_path / 'task2'}")
    
    # Print funnel
    print("\n  Pipeline Funnel:")
    for stage, count in analytics["funnel"].items():
        bar = "#" * count
        print(f"    {stage:15s} | {bar} {count}")
    
    # Print high priority actions
    if analytics["high_priority_actions"]:
        print(f"\n  [!] High Priority Actions ({len(analytics['high_priority_actions'])}):")
        for action in analytics["high_priority_actions"][:5]:
            print(f"    [{action['lead_id']}] {action['company']} - {action['action']}")
    
    return {
        "crm": {"results": crm_results, "summary": crm_summary, "files": crm_files},
        "pipeline": pipeline_results,
        "pipeline_files": pipeline_files,
    }


def initialize_runtime_data(data: dict) -> None:
    """Load processed data into the API and persist it to SQLite."""
    from src.api.routes import set_crm_data, set_pipeline_data
    set_crm_data(data["crm"]["results"], data["crm"]["summary"])
    set_pipeline_data(data["pipeline"])

    from src.database.models import init_db, SessionLocal, save_enquiries_to_db, save_leads_to_db
    init_db()
    db = SessionLocal()
    try:
        save_enquiries_to_db(data["crm"]["results"], db)
        save_leads_to_db(data["pipeline"]["cleaned_data"], db)
        print("[OK] Data persisted to SQLite database (biai_crm.db)")
    except Exception as e:
        print(f"[!] Database persistence skipped: {e}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="BIAI CRM & Lead Pipeline System")
    parser.add_argument("--process-only", action="store_true", 
                       help="Process data and save to files without starting server")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server host")
    parser.add_argument("--output", type=str, default="outputs", help="Output directory")
    args = parser.parse_args()
    
    if args.process_only:
        data = process_data(args.output)
        print("\n[OK] Processing complete. Files saved to:", args.output)
        return

    app = create_app()

    async def initialize_in_background() -> None:
        try:
            data = await asyncio.to_thread(process_data, args.output)
            initialize_runtime_data(data)
        except Exception as exc:
            print(f"[ERROR] Startup data processing failed: {exc}")

    @app.on_event("startup")
    async def start_data_processing() -> None:
        asyncio.create_task(initialize_in_background())

    port = int(os.environ.get("PORT", args.port))
    host = os.environ.get("HOST", args.host)
    print(f"\n{'=' * 60}")
    print(f"Server starting on http://{host}:{port}")
    print(f"API docs: http://{host}:{port}/docs")
    print(f"{'=' * 60}\n")
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
