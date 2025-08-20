
# Project 1 — Revenue Ops Lead Router & Enricher
**Stack:** Python · LangGraph · FastAPI · Pinecone · HubSpot (or Salesforce) · Clearbit/Apollo (or custom enricher) · Slack · Redis

## 1) Problem & Success Criteria
**Problem.** Inbound leads are inconsistently enriched and misrouted, delaying first touch and lowering win-rate.

**Success.**
- ≥95% correct owner routing (vs. hand-labeled ground truth)
- −40% median time-to-first-touch
- 100% idempotent lead processing (no dupes), safe fallbacks when APIs fail

## 2) Architecture
```
[Webhook/API] → Capture → Enrich → Score → Route → Summarize → (AE/SDR Slack & CRM) → Nurture (if low-score)
                              ↘ Memory (Pinecone: similar accounts & outcomes)
```
**LangGraph state machine** (typed dict state, deterministic edges with guards). **FastAPI** for webhook & admin endpoints. **Pinecone** stores embeddings of past accounts + outcomes; used in `Summarize` for “similar accounts” context. **Redis** for short-term job state/idempotency.

### State Shape (Typed)
```python
from typing import TypedDict, Optional, List, Dict, Any

class LeadState(TypedDict, total=False):
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
```

## 3) Repo Layout
```
revops-lead-router/
  app.py                      # FastAPI app + LangGraph runtime
  graph/
    __init__.py
    state.py                  # LeadState types
    nodes/
      capture.py
      enrich.py
      score.py
      route.py
      summarize.py
      nurture.py
  tools/
    hubspot.py                # CRUD lead/contact, owner lookup
    clearbit.py               # enrichment provider interface (mockable)
    slack.py
    pinecone_store.py
    idempotency.py            # Redis-based request keys
  prompts/
    scoring.md
    summarize.md
  infra/
    docker-compose.yml        # redis, local dev
  tests/
    test_flow.py
    fixtures/
      leads_sample.json
  requirements.txt
  README.md
```

## 4) Requirements (minimal)
```
fastapi==0.112.*
uvicorn[standard]==0.30.*
langgraph==0.2.*
httpx==0.27.*
redis==5.*
pinecone-client==5.*
openai==1.*
python-dotenv==1.*
loguru==0.7.*
pydantic==2.*
```
*(Add `hubspot-api-client`, `slack_sdk` if you prefer official SDKs; otherwise call via REST with `httpx`.)*

## 5) Environment Variables
```
OPENAI_API_KEY=
PINECONE_API_KEY=
PINECONE_INDEX=revops-similar-accounts
REDIS_URL=redis://localhost:6379
HUBSPOT_API_KEY=
SLACK_BOT_TOKEN=
ROUTING_JSON=./infra/routing.json         # territory map
SCORING_CONFIG=./prompts/scoring.md       # hybrid rule+LLM rubric
```

## 6) Core Graph Wiring (starter)
```python
# app.py
import os
from fastapi import FastAPI, Request
from loguru import logger
from langgraph.graph import StateGraph, START, END
from graph.state import LeadState
from graph.nodes.capture import capture
from graph.nodes.enrich import enrich
from graph.nodes.score import score
from graph.nodes.route import route
from graph.nodes.summarize import summarize
from graph.nodes.nurture import nurture
from tools.idempotency import Idem

app = FastAPI(title="RevOps Lead Router")

# Build the graph
workflow = StateGraph(LeadState)
workflow.add_node("capture", capture)
workflow.add_node("enrich", enrich)
workflow.add_node("score", score)
workflow.add_node("route", route)
workflow.add_node("summarize", summarize)
workflow.add_node("nurture", nurture)

workflow.add_edge(START, "capture")
workflow.add_edge("capture", "enrich")
workflow.add_edge("enrich", "score")

# Conditional branch: qualify vs nurture vs manual
from langgraph.graph.message import add_messages

def branch_decision(state: LeadState) -> str:
    if state.get("score", 0) >= 0.7 and state.get("owner"):
        return "route"
    if state.get("score", 0) < 0.4:
        state["decided_path"] = "nurture"
        return "nurture"
    state["decided_path"] = "manual_review"
    return "summarize"

workflow.add_conditional_edges("score", branch_decision, {"route": "route", "nurture": "nurture", "summarize": "summarize"})
workflow.add_edge("route", "summarize")
workflow.add_edge("summarize", END)
workflow.add_edge("nurture", END)

app_graph = workflow.compile()
idem = Idem()

@app.post("/webhooks/lead")
async def ingest_lead(req: Request):
    payload = await req.json()
    key = payload.get("event_id") or payload.get("email")
    if not idem.check_and_set(key):
        return {"status": "duplicate_ignored"}
    result = app_graph.invoke({"raw": payload, "errors": [], "notifications": []})
    return {"status": "ok", "state": result}

@app.get("/health")
def health():
    return {"ok": True}
```

### Node: Capture (normalize payload)
```python
# graph/nodes/capture.py
from typing import Dict, Any
from graph.state import LeadState

REQUIRED_FIELDS = ["email", "company", "full_name"]

def capture(state: LeadState) -> LeadState:
    raw = state.get("raw", {})
    # Normalize common fields
    email = (raw.get("email") or raw.get("properties", {}).get("email", {}).get("value", "")).lower()
    company = raw.get("company") or raw.get("company_name") or raw.get("properties", {}).get("company")
    domain = (raw.get("website") or raw.get("domain") or "").replace("https://", "").replace("http://", "").split("/")[0]
    normalized = {
        "email": email,
        "company": company,
        "domain": domain,
        "full_name": raw.get("full_name") or f"{raw.get('first_name','')} {raw.get('last_name','')}",
        "country": raw.get("country"),
        "title": raw.get("title"),
        "source": raw.get("source")
    }
    state["normalized"] = normalized
    state["lead_id"] = raw.get("id") or email
    return state
```

### Node: Enrich (Clearbit/Apollo; mockable)
```python
# graph/nodes/enrich.py
from graph.state import LeadState
from tools.clearbit import enrich_domain_person

def enrich(state: LeadState) -> LeadState:
    norm = state["normalized"]
    try:
        data = enrich_domain_person(domain=norm.get("domain"), email=norm.get("email"))
        state["enrichment"] = data
    except Exception as e:
        state.setdefault("errors", []).append(f"enrich_failed: {e}")
        state["enrichment"] = {}
    return state
```

### Node: Score (hybrid rules + LLM rubric)
```python
# graph/nodes/score.py
from graph.state import LeadState
from tools.llm import score_lead_with_rubric

HARD_RULES = {
    "min_headcount": 20,
    "allowed_countries": ["US","CA","UK","DE","FR","MA"],
    "blocked_free_email": True,
}

def rule_score(state: LeadState) -> float:
    e = state.get("enrichment", {})
    score = 0.0
    # Headcount
    if (e.get("company", {}).get("employees") or 0) >= HARD_RULES["min_headcount"]:
        score += 0.3
    # ICP industry
    if e.get("company", {}).get("industry") in {"SaaS","FinTech","Ecommerce"}:
        score += 0.2
    # Title contains buying roles
    if any(k in (state["normalized"].get("title") or "").lower() for k in ["head", "lead", "director", "vp", "cxo"]):
        score += 0.2
    # Free email penalty
    if HARD_RULES["blocked_free_email"] and state["normalized"].get("email", "").endswith(("gmail.com","yahoo.com","outlook.com")):
        score -= 0.4
    return max(0.0, min(1.0, score))

def score(state: LeadState) -> LeadState:
    base = rule_score(state)
    llm_score, reasons = score_lead_with_rubric(state, base_hint=base)
    final = max(0.0, min(1.0, 0.5*base + 0.5*llm_score))
    state["score"] = final
    state["score_reasons"] = reasons
    return state
```

### Node: Route (territory map + owner fallback)
```python
# graph/nodes/route.py
import json
from graph.state import LeadState
from tools.hubspot import find_owner_by_rules, create_or_update_contact

with open(os.getenv("ROUTING_JSON","./infra/routing.json"), "r") as f:
    ROUTES = json.load(f)


def route(state: LeadState) -> LeadState:
    owner = find_owner_by_rules(state["normalized"], state.get("enrichment", {}), ROUTES)
    state["owner"] = owner
    rec = create_or_update_contact(state)
    state["crm_record_id"] = rec.get("id") if rec else None
    state["route_reason"] = f"Matched territory {owner}"
    return state
```

### Node: Summarize (LLM + Pinecone similar accounts)
```python
# graph/nodes/summarize.py
from tools.pinecone_store import similar_accounts
from tools.llm import summarize_for_ae
from graph.state import LeadState

def summarize(state: LeadState) -> LeadState:
    sims = similar_accounts(state)
    state["similar_accounts"] = sims
    note = summarize_for_ae(state, sims)
    # Optional: post to Slack & attach to CRM
    return state
```

### Node: Nurture (low score → add to sequence)
```python
# graph/nodes/nurture.py
from graph.state import LeadState

def nurture(state: LeadState) -> LeadState:
    # Add to low-touch sequence, create a task in CRM, schedule revisit in 30 days
    return state
```

## 7) Tool Stubs

**Idempotency (Redis)**
```python
# tools/idempotency.py
import time
import redis
import os

class Idem:
    def __init__(self):
        self.r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379"))
    def check_and_set(self, key: str, ttl=3600) -> bool:
        return self.r.set(name=f"idem:{key}", value=int(time.time()), ex=ttl, nx=True) is True
```

**Enrichment provider**
```python
# tools/clearbit.py
import httpx, os

async def _get(url, params=None, headers=None):
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, params=params, headers=headers)
        r.raise_for_status(); return r.json()

def enrich_domain_person(domain: str, email: str):
    # Replace with Clearbit/Apollo/People Data Labs, etc. Here we return a mocked structure.
    return {
        "company": {"domain": domain, "employees": 120, "industry": "SaaS", "tech": ["AWS","Snowflake"]},
        "person": {"email": email, "seniority": "director"}
    }
```

**HubSpot (simplified)**
```python
# tools/hubspot.py
import httpx, os
API = "https://api.hubapi.com"
KEY = os.getenv("HUBSPOT_API_KEY","test")

def find_owner_by_rules(normalized, enrichment, routes) -> str:
    country = (normalized.get("country") or "").upper()
    industry = (enrichment.get("company",{}).get("industry") or "").lower()
    # Example: territory by country → team, else default
    return routes.get(country) or routes.get("DEFAULT","unassigned@company.com")

def create_or_update_contact(state):
    # Upsert contact in HubSpot; return minimal shape
    return {"id": "12345"}
```

**Pinecone memory**
```python
# tools/pinecone_store.py
from typing import List, Dict, Any

def similar_accounts(state) -> List[Dict[str, Any]]:
    # Query Pinecone with company vector (domain + industry + headcount). Return top-3 examples.
    return [
      {"account":"Acme Inc","outcome":"Won","reason":"Same industry & size"},
      {"account":"BetaCo","outcome":"Lost","reason":"Budget timing"}
    ]
```

**LLM helpers**
```python
# tools/llm.py
from typing import Tuple, List

RUBRIC = """
You are a B2B lead qualifier. Score 0–1. Consider ICP, seniority, use-case fit.
Return JSON {"score": float, "reasons": [..]}.
"""

def score_lead_with_rubric(state, base_hint=0.0) -> Tuple[float, List[str]]:
    # Call your model provider here; for now, return a deterministic mock using base_hint.
    reasons = ["ICP match: SaaS", "Seniority: Director"] if base_hint>0.2 else ["Insufficient headcount"]
    return min(1.0, base_hint + 0.4), reasons


def summarize_for_ae(state, sims) -> str:
    # Compose a crisp one-pager; include similar accounts as social proof.
    return "Summary for AE with key signals and next-best action."
```

## 8) Prompts
`prompts/scoring.md`
```
Role: Senior RevOps Analyst.
Task: Score this lead 0–1. Use strict ICP (SaaS/FinTech/Ecom), headcount≥20, director+ titles.
Return JSON: {score: float, reasons: string[]}. No prose.
Lead JSON: {{lead_json}}
```

`prompts/summarize.md`
```
Create a 6–8 bullet summary for the AE: who they are, why now, similar wins, next step.
```

## 9) Testing & Evaluation
- **Offline:** run `tests/test_flow.py` over `fixtures/leads_sample.json` (100 synthetic leads with labels). Report accuracy of routing and average runtime.
- **Online:** shadow mode writing to a sandbox CRM pipeline for a week; compare time-to-first-touch and owner correctness.

## 10) Observability & Fallbacks
- Log each node start/end and duration; attach `errors[]` in state rather than raising, unless fatal.
- If enrichment fails → proceed with rules-only score; if CRM write fails → queue retry; always keep idempotency key.