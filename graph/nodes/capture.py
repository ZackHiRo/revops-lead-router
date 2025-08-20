from typing import Dict, Any
from graph.state import LeadState
from loguru import logger

REQUIRED_FIELDS = ["email", "company", "full_name"]

def capture(state: LeadState) -> LeadState:
    """Normalize and validate incoming lead payload."""
    logger.info(f"Starting capture for lead: {state.get('raw', {}).get('email', 'unknown')}")
    
    raw = state.get("raw", {})
    
    # Normalize common fields
    email = (raw.get("email") or raw.get("properties", {}).get("email", {}).get("value", "")).lower()
    company = raw.get("company") or raw.get("company_name") or raw.get("properties", {}).get("company")
    domain = (raw.get("website") or raw.get("domain") or "").replace("https://", "").replace("http://", "").split("/")[0]
    
    normalized = {
        "email": email,
        "company": company,
        "domain": domain,
        "full_name": raw.get("full_name") or f"{raw.get('first_name','')} {raw.get('last_name','')}".strip(),
        "country": raw.get("country"),
        "title": raw.get("title"),
        "source": raw.get("source")
    }
    
    # Validate required fields
    missing_fields = [field for field in REQUIRED_FIELDS if not normalized.get(field)]
    if missing_fields:
        state.setdefault("errors", []).append(f"Missing required fields: {missing_fields}")
    
    state["normalized"] = normalized
    state["lead_id"] = raw.get("id") or email
    
    logger.info(f"Capture completed for {state['lead_id']}")
    return state
