from typing import TypedDict, Optional, List, Dict, Any

class LeadState(TypedDict, total=False):
    """State shape for the lead processing workflow."""
    lead_id: str
    raw: Dict[str, Any]              # original webhook payload
    normalized: Dict[str, Any]       # email, domain, company, title, country, etc.
    enrichment: Dict[str, Any]       # firmographics, technographics, headcount...
    score: float
    score_reasons: List[str]
    owner: Optional[str]             # userId / email in CRM
    route_reason: str
    similar_accounts: List[Dict[str, Any]]
    crm_record_id: Optional[str]
    notifications: List[str]         # Slack message ids
    errors: List[str]
    decided_path: str                # "qualify" | "nurture" | "manual_review"
