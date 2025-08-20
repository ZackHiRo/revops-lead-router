import os
import json
from graph.state import LeadState
from tools.hubspot import find_owner_by_rules, create_or_update_contact
from loguru import logger

# Load routing configuration
ROUTING_CONFIG_PATH = os.getenv("ROUTING_JSON", "./infra/routing.json")

def load_routing_rules():
    """Load routing rules from configuration file."""
    try:
        with open(ROUTING_CONFIG_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Routing config not found at {ROUTING_CONFIG_PATH}, using defaults")
        return {
            "US": "us-team@company.com",
            "CA": "canada-team@company.com", 
            "UK": "emea-team@company.com",
            "DEFAULT": "general@company.com"
        }
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in routing config {ROUTING_CONFIG_PATH}")
        return {"DEFAULT": "general@company.com"}

def route(state: LeadState) -> LeadState:
    """Route lead to appropriate sales owner and create CRM record."""
    logger.info(f"Starting routing for lead: {state.get('lead_id', 'unknown')}")
    
    try:
        # Load routing rules
        routes = load_routing_rules()
        
        # Find owner based on rules
        owner = find_owner_by_rules(
            state.get("normalized", {}), 
            state.get("enrichment", {}), 
            routes
        )
        
        state["owner"] = owner
        logger.info(f"Assigned owner: {owner}")
        
        # Create or update CRM record
        try:
            crm_record = create_or_update_contact(state)
            state["crm_record_id"] = crm_record.get("id") if crm_record else None
            
            if state["crm_record_id"]:
                logger.info(f"CRM record created/updated: {state['crm_record_id']}")
            else:
                logger.warning("CRM record creation failed")
                
        except Exception as e:
            error_msg = f"CRM operation failed: {str(e)}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            state["crm_record_id"] = None
        
        # Set routing reason
        country = state.get("normalized", {}).get("country", "unknown")
        state["route_reason"] = f"Matched territory {country} → {owner}"
        
        logger.info(f"Routing completed for {state.get('lead_id')}")
        
    except Exception as e:
        error_msg = f"Routing failed: {str(e)}"
        logger.error(error_msg)
        state.setdefault("errors", []).append(error_msg)
        
        # Fallback to default owner
        routes = load_routing_rules()
        state["owner"] = routes.get("DEFAULT", "unassigned@company.com")
        state["route_reason"] = "Fallback to default owner due to routing error"
    
    return state
