from graph.state import LeadState
from tools.clearbit import enrich_domain_person
from loguru import logger

def enrich(state: LeadState) -> LeadState:
    """Enrich lead data with external sources (Clearbit, Apollo, etc.)."""
    logger.info(f"Starting enrichment for lead: {state.get('lead_id', 'unknown')}")
    
    norm = state.get("normalized", {})
    
    if not norm.get("domain") and not norm.get("email"):
        logger.warning("No domain or email available for enrichment")
        state["enrichment"] = {}
        return state
    
    try:
        data = enrich_domain_person(
            domain=norm.get("domain"), 
            email=norm.get("email")
        )
        state["enrichment"] = data
        logger.info(f"Enrichment completed successfully for {state.get('lead_id')}")
        
    except Exception as e:
        error_msg = f"Enrichment failed: {str(e)}"
        logger.error(error_msg)
        state.setdefault("errors", []).append(error_msg)
        state["enrichment"] = {}
    
    return state
