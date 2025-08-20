# Revenue Ops Lead Router & Enricher

A sophisticated lead routing and enrichment system built with LangGraph, FastAPI, and modern AI/ML tools to automatically process, score, and route inbound leads to the right sales representatives.

## 🎯 Problem & Success Criteria

**Problem:** Inbound leads are inconsistently enriched and misrouted, delaying first touch and lowering win-rate.

**Success Metrics:**
- ≥95% correct owner routing (vs. hand-labeled ground truth)
- −40% median time-to-first-touch
- 100% idempotent lead processing (no dupes), safe fallbacks when APIs fail

## 🏗️ Architecture

```
[Webhook/API] → Capture → Enrich → Score → Route → Summarize → (AE/SDR Slack & CRM) → Nurture (if low-score)
                              ↘ Memory (Pinecone: similar accounts & outcomes)
```

- **LangGraph state machine** with typed dict state and deterministic edges
- **FastAPI** for webhook & admin endpoints
- **Pinecone** stores embeddings of past accounts + outcomes for similarity matching
- **Redis** for short-term job state/idempotency
- **Hybrid scoring** combining rules-based logic with LLM evaluation

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Clone and setup
git clone <your-repo>
cd revops-lead-router

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file:

```bash
OPENAI_API_KEY=your_openai_key
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX=revops-similar-accounts
REDIS_URL=redis://localhost:6379
HUBSPOT_API_KEY=your_hubspot_key
SLACK_BOT_TOKEN=your_slack_token
ROUTING_JSON=./infra/routing.json
SCORING_CONFIG=./prompts/scoring.md
```

### 3. Start Services

```bash
# Start Redis (if not running)
docker-compose up -d redis

# Start the application
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Submit a test lead
curl -X POST http://localhost:8000/webhooks/lead \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john.doe@acme.com",
    "company": "Acme Corp",
    "full_name": "John Doe",
    "title": "Director of Engineering",
    "source": "website"
  }'
```

## 📁 Project Structure

```
revops-lead-router/
├── app.py                      # FastAPI app + LangGraph runtime
├── graph/                      # LangGraph workflow nodes
│   ├── __init__.py
│   ├── state.py               # LeadState types
│   └── nodes/                 # Individual workflow nodes
│       ├── capture.py         # Normalize payload
│       ├── enrich.py          # Enrich with external data
│       ├── score.py           # Hybrid scoring
│       ├── route.py           # Territory routing
│       ├── summarize.py       # LLM summary + similar accounts
│       └── nurture.py         # Low-score nurturing
├── tools/                      # External service integrations
│   ├── hubspot.py             # CRM operations
│   ├── clearbit.py            # Data enrichment
│   ├── slack.py               # Notifications
│   ├── pinecone_store.py      # Vector similarity search
│   └── idempotency.py         # Redis-based deduplication
├── prompts/                    # LLM prompt templates
│   ├── scoring.md
│   └── summarize.md
├── infra/                      # Infrastructure configs
│   └── docker-compose.yml     # Redis setup
├── tests/                      # Test suite
│   ├── test_flow.py
│   └── fixtures/
│       └── leads_sample.json
└── requirements.txt
```

## 🔧 Configuration

### Routing Rules

Edit `infra/routing.json` to define territory assignments:

```json
{
  "US": "us-team@company.com",
  "CA": "canada-team@company.com",
  "UK": "emea-team@company.com",
  "DEFAULT": "general@company.com"
}
```

### Scoring Configuration

Modify `prompts/scoring.md` to adjust lead qualification criteria and LLM prompts.

## 🧪 Testing

### Run Tests

```bash
# Run the test suite
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=graph --cov=tools
```

### Test Data

The `tests/fixtures/leads_sample.json` contains 100 synthetic leads for testing routing accuracy and performance.

## 📊 Monitoring & Observability

- Each workflow node logs start/end times and duration
- Errors are captured in the state rather than raising exceptions
- Redis provides idempotency and job state tracking
- FastAPI includes built-in request/response logging

## 🚨 Error Handling & Fallbacks

- **Enrichment failures**: Proceed with rules-only scoring
- **CRM write failures**: Queue for retry
- **API timeouts**: Graceful degradation with cached data
- **Idempotency**: Always maintained to prevent duplicate processing

## 🔄 API Endpoints

- `POST /webhooks/lead` - Submit new leads for processing
- `GET /health` - Health check
- `GET /admin/leads/{lead_id}` - View lead processing state
- `POST /admin/retry/{lead_id}` - Retry failed lead processing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

[Your License Here]

## 🆘 Support

For questions or issues, please open a GitHub issue or contact the development team.
