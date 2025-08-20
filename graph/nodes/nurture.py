from graph.state import LeadState
from loguru import logger

def nurture(state: LeadState) -> LeadState:
    """Handle low-scoring leads by adding them to nurturing sequences."""
    logger.info(f"Starting nurture process for lead: {state.get('lead_id', 'unknown')}")
    
    try:
        # Set the decided path
        state["decided_path"] = "nurture"
        
        # Add to low-touch sequence
        # This could integrate with marketing automation tools like HubSpot, Marketo, etc.
        nurture_data = {
            "sequence_name": "low_score_nurture",
            "entry_date": "now",
            "revisit_date": "30_days",
            "score": state.get("score", 0),
            "reasons": state.get("score_reasons", [])
        }
        
        state["nurture_data"] = nurture_data
        
        # Create a task in CRM for follow-up
        # This would typically call the CRM API to create a task
        task_data = {
            "type": "nurture_followup",
            "due_date": "30_days",
            "description": f"Re-evaluate lead {state.get('lead_id')} after nurturing period",
            "assigned_to": "marketing@company.com"
        }
        
        state["nurture_task"] = task_data
        
        # Schedule automated email sequence
        # This could integrate with email marketing platforms
        email_sequence = {
            "sequence": "low_score_education",
            "emails": [
                {"day": 1, "subject": "Welcome to our community"},
                {"day": 7, "subject": "Industry insights and trends"},
                {"day": 21, "subject": "Case study: How we helped similar companies"}
            ]
        }
        
        state["email_sequence"] = email_sequence
        
        logger.info(f"Nurture process completed for {state.get('lead_id')}")
        
    except Exception as e:
        error_msg = f"Nurture process failed: {str(e)}"
        logger.error(error_msg)
        state.setdefault("errors", []).append(error_msg)
        
        # Ensure basic nurture state is set
        state["decided_path"] = "nurture"
        state["nurture_data"] = {"sequence_name": "fallback_nurture"}
    
    return state
