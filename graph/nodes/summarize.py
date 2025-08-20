from graph.state import LeadState
from tools.pinecone_store import similar_accounts
from tools.llm import summarize_for_ae
from loguru import logger

def summarize(state: LeadState) -> LeadState:
    """Generate lead summary and find similar accounts for context."""
    logger.info(f"Starting summarization for lead: {state.get('lead_id', 'unknown')}")
    
    try:
        # Find similar accounts using vector similarity
        similar_accounts_list = similar_accounts(state)
        state["similar_accounts"] = similar_accounts_list
        
        logger.info(f"Found {len(similar_accounts_list)} similar accounts")
        
        # Generate LLM summary for sales team
        try:
            summary = summarize_for_ae(state, similar_accounts_list)
            logger.info("LLM summary generated successfully")
            
            # Store summary in state (could be sent to Slack/CRM)
            state["summary"] = summary
            
        except Exception as e:
            error_msg = f"LLM summarization failed: {str(e)}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            
            # Fallback to basic summary
            state["summary"] = f"Lead: {state.get('normalized', {}).get('full_name')} from {state.get('normalized', {}).get('company')} (Score: {state.get('score', 0):.2f})"
        
        # Optional: Send to Slack or CRM
        # await send_to_slack(state)
        # await attach_to_crm(state)
        
        logger.info(f"Summarization completed for {state.get('lead_id')}")
        
    except Exception as e:
        error_msg = f"Summarization failed: {str(e)}"
        logger.error(error_msg)
        state.setdefault("errors", []).append(error_msg)
        
        # Ensure we have at least basic state
        state["similar_accounts"] = []
        state["summary"] = "Summary generation failed"
    
    return state
