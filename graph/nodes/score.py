from graph.state import LeadState
from tools.llm import score_lead_with_rubric
from loguru import logger

HARD_RULES = {
    "min_headcount": 20,
    "allowed_countries": ["US", "CA", "UK", "DE", "FR", "MA"],
    "blocked_free_email": True,
}

def rule_score(state: LeadState) -> float:
    """Calculate base score using hard-coded business rules."""
    e = state.get("enrichment", {})
    norm = state.get("normalized", {})
    score = 0.0
    
    # Headcount scoring
    headcount = e.get("company", {}).get("employees", 0)
    if headcount >= HARD_RULES["min_headcount"]:
        score += 0.3
        if headcount >= 100:
            score += 0.1  # Bonus for larger companies
    
    # Industry scoring (ICP)
    industry = e.get("company", {}).get("industry", "").lower()
    icp_industries = {"saas", "fintech", "ecommerce", "healthtech", "edtech"}
    if industry in icp_industries:
        score += 0.2
    
    # Title scoring (buying authority)
    title = (norm.get("title") or "").lower()
    buying_roles = ["head", "lead", "director", "vp", "cxo", "chief", "manager"]
    if any(role in title for role in buying_roles):
        score += 0.2
    
    # Country scoring
    country = (norm.get("country") or "").upper()
    if country in HARD_RULES["allowed_countries"]:
        score += 0.1
    
    # Free email penalty
    if HARD_RULES["blocked_free_email"]:
        email = norm.get("email", "")
        free_domains = ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com")
        if email.endswith(free_domains):
            score -= 0.4
    
    # Technology stack bonus
    tech_stack = e.get("company", {}).get("tech", [])
    if tech_stack:
        score += 0.1
    
    return max(0.0, min(1.0, score))

def score(state: LeadState) -> LeadState:
    """Score lead using hybrid approach: rules + LLM."""
    logger.info(f"Starting scoring for lead: {state.get('lead_id', 'unknown')}")
    
    # Calculate base score from rules
    base_score = rule_score(state)
    logger.info(f"Rule-based score: {base_score:.3f}")
    
    try:
        # Get LLM-based score and reasoning
        llm_score, reasons = score_lead_with_rubric(state, base_hint=base_score)
        logger.info(f"LLM score: {llm_score:.3f}")
        
        # Combine scores (50/50 weight)
        final_score = max(0.0, min(1.0, 0.5 * base_score + 0.5 * llm_score))
        
        state["score"] = final_score
        state["score_reasons"] = reasons
        
        logger.info(f"Final score: {final_score:.3f} for {state.get('lead_id')}")
        
    except Exception as e:
        error_msg = f"LLM scoring failed: {str(e)}"
        logger.error(error_msg)
        state.setdefault("errors", []).append(error_msg)
        
        # Fallback to rule-based score only
        state["score"] = base_score
        state["score_reasons"] = ["Rule-based scoring only (LLM failed)"]
    
    return state
