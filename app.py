import os
import time
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv

# Import our modules
from graph.state import LeadState
from graph.nodes.capture import capture
from graph.nodes.enrich import enrich
from graph.nodes.score import score
from graph.nodes.route import route
from graph.nodes.summarize import summarize
from graph.nodes.nurture import nurture
from tools.idempotency import Idem
from tools.slack import send_lead_notification, send_high_priority_alert

# Load environment variables
load_dotenv()

# Configure logging
logger.add("logs/app.log", rotation="1 day", retention="7 days", level="INFO")

# Initialize FastAPI app
app = FastAPI(
    title="Revenue Ops Lead Router & Enricher",
    description="AI-powered lead routing and enrichment system",
    version="1.0.0"
)

# Build the LangGraph workflow
def build_workflow():
    """Build the lead processing workflow."""
    workflow = StateGraph(LeadState)
    
    # Add nodes
    workflow.add_node("capture", capture)
    workflow.add_node("enrich", enrich)
    workflow.add_node("score", score)
    workflow.add_node("route", route)
    workflow.add_node("summarize", summarize)
    workflow.add_node("nurture", nurture)
    
    # Add edges
    workflow.add_edge(START, "capture")
    workflow.add_edge("capture", "enrich")
    workflow.add_edge("enrich", "score")
    
    # Conditional branching based on score and owner assignment
    def branch_decision(state: LeadState) -> str:
        score_val = state.get("score", 0)
        owner = state.get("owner")
        
        if score_val >= 0.7 and owner:
            logger.info(f"High-scoring lead with owner, proceeding to route: {score_val}")
            return "route"
        elif score_val < 0.4:
            logger.info(f"Low-scoring lead, sending to nurture: {score_val}")
            state["decided_path"] = "nurture"
            return "nurture"
        else:
            logger.info(f"Medium-scoring lead, manual review required: {score_val}")
            state["decided_path"] = "manual_review"
            return "summarize"
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "score", 
        branch_decision, 
        {
            "route": "route", 
            "nurture": "nurture", 
            "summarize": "summarize"
        }
    )
    
    # Add remaining edges
    workflow.add_edge("route", "summarize")
    workflow.add_edge("summarize", END)
    workflow.add_edge("nurture", END)
    
    return workflow.compile()

# Initialize workflow and idempotency
app_graph = build_workflow()
idem = Idem()

@app.post("/webhooks/lead")
async def ingest_lead(req: Request):
    """
    Main webhook endpoint for lead ingestion.
    
    Expected payload:
    {
        "email": "john.doe@company.com",
        "company": "Company Name",
        "full_name": "John Doe",
        "title": "Director of Engineering",
        "source": "website",
        "country": "US"
    }
    """
    start_time = time.time()
    
    try:
        # Parse request
        payload = await req.json()
        logger.info(f"Received lead webhook: {payload.get('email', 'unknown')}")
        
        # Check idempotency
        key = payload.get("event_id") or payload.get("email") or str(time.time())
        if not idem.check_and_set(key):
            logger.warning(f"Duplicate lead ignored: {key}")
            return JSONResponse(
                status_code=200,
                content={"status": "duplicate_ignored", "message": "Lead already processed"}
            )
        
        # Initialize state
        initial_state = {
            "raw": payload,
            "errors": [],
            "notifications": [],
            "score_reasons": []
        }
        
        # Execute workflow
        logger.info(f"Starting workflow execution for lead: {key}")
        result = app_graph.invoke(initial_state)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Send notifications based on score
        try:
            if result.get("score", 0) >= 0.8:
                # High-priority lead - send alert
                slack_ts = send_high_priority_alert(result)
                if slack_ts:
                    result["notifications"].append(f"high_priority_slack:{slack_ts}")
            else:
                # Regular lead notification
                slack_ts = send_lead_notification(result)
                if slack_ts:
                    result["notifications"].append(f"slack:{slack_ts}")
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            result.setdefault("errors", []).append(f"slack_notification_failed: {e}")
        
        # Log completion
        logger.info(f"Lead processing completed in {processing_time:.2f}s: {result.get('lead_id', 'unknown')}")
        
        # Return success response
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "lead_id": result.get("lead_id"),
                "processing_time": processing_time,
                "score": result.get("score"),
                "owner": result.get("owner"),
                "path": result.get("decided_path"),
                "crm_id": result.get("crm_record_id")
            }
        )
        
    except Exception as e:
        logger.error(f"Lead processing failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "services": {
            "redis": "connected" if idem.r else "disconnected",
            "workflow": "ready"
        }
    }

@app.get("/admin/leads/{lead_id}")
async def get_lead_status(lead_id: str):
    """Get lead processing status (for debugging)."""
    try:
        # In a real implementation, you'd query a database
        # For now, return basic info
        return {
            "lead_id": lead_id,
            "status": "processed",
            "message": "Lead status endpoint - implement database query"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/retry/{lead_id}")
async def retry_lead(lead_id: str):
    """Retry failed lead processing."""
    try:
        # In a real implementation, you'd implement retry logic
        return {
            "lead_id": lead_id,
            "status": "retry_initiated",
            "message": "Retry endpoint - implement retry logic"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
def get_metrics():
    """Get system metrics."""
    return {
        "total_leads_processed": "implement_counter",
        "average_processing_time": "implement_timing",
        "success_rate": "implement_calculation",
        "active_owners": "implement_owner_stats"
    }

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    logger.info("Starting Revenue Ops Lead Router & Enricher")
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
