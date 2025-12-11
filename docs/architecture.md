# Architecture

## System Overview

MegaDoc is an enterprise AI platform with privacy-first design, multi-modal document processing, and intelligent cost optimization. The architecture supports both offline operation and cloud-native deployment.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            User Interface                                │
│  Landing → Document Upload → RAG Chat → SQL Sandbox → Investigation      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ HTTPS
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         API Gateway Layer                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐   │
│  │Rate Limiting│  │CSRF Protect │  │Magic Bytes  │  │ X-Ray Trace  │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
┌───────────────┐    ┌───────────────────┐    ┌───────────────────┐
│  Conversion   │    │   RAG Pipeline    │    │  SQL Sandbox      │
│  - MarkItDown │    │  - Chunking       │    │  - BYOD Upload    │
│  - Vision AI  │    │  - Embeddings     │    │  - Read-Only Mode │
│  - Cleanup    │    │  - Vector Search  │    │  - Query Timeout  │
└───────────────┘    └────────┬──────────┘    └───────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────────────┐
│ Smart Router  │    │ Domain Inject │    │ Investigator Agent    │
│ - Complexity  │    │ - Legal       │    │ - LangGraph State     │
│ - Cost Opt    │    │ - Medical     │    │ - Self-Correction     │
│ - Free-tier   │    │ - Technical   │    │ - Tool Calling        │
└───────┬───────┘    └───────────────┘    └───────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    Multi-Model Gateway (OpenRouter)            │
│  Gemini 2.0 Flash | DeepSeek V3 | Llama 3.3 | Free Tier      │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────┐
│   SQLite    │  (Stats, Cost Tracking, Metrics)
└─────────────┘
```

## Core Principles

### 1. Zero Data Retention
- Files deleted immediately after conversion
- No file storage, no file history
- Only aggregate statistics retained
- No PII or sensitive data logged

### 2. Privacy by Design
- 100% offline processing
- No external API calls
- No third-party services
- Air-gapped deployment ready

### 3. Security First
- OWASP Top 10 compliance
- Defense in depth
- Fail-safe defaults
- Least privilege

## Components

### Conversion Engine
- **Library**: markitdown
- **Formats**: 15+ document types
- **Output**: Markdown or Plain Text
- **Performance**: <2s for most documents

### RAG Pipeline
- **Chunking**: Token-aware semantic splitting
- **Embeddings**: all-MiniLM-L6-v2 (384-dim) or Jina (768-dim)
- **Tokenizer**: tiktoken (cl100k_base)
- **Export**: ChromaDB, LanceDB, JSONL, FAISS

### SQL Sandbox (BYOD)
The Universal SQL Builder enables "Bring Your Own Database" with strict security:

**Ingestion Strategies:**
| Format | Strategy | Implementation |
|--------|----------|----------------|
| `.db`, `.sqlite` | Native SQLite | Direct read-only URI mode |
| `.sql` | Dump Rehydration | Temp DB from `executescript()` |
| `.csv`, `.xlsx` | Spreadsheet Translation | Pandas normalization → SQLite |

**Security Boundaries:**
- **Read-Only Mode**: `?mode=ro&uri=true` connection string
- **Upload Limit**: 50MB max file size
- **Query Timeout**: 5 second hard limit
- **Row Limit**: 1000 rows max per query
- **DML Blocking**: INSERT/UPDATE/DELETE operations rejected
- **Session Isolation**: Per-user ephemeral database instances
- **No Persistence**: Database cleared on session end

**Attack Mitigations:**
| Attack Vector | Mitigation |
|---------------|------------|
| SQL Injection | LLM generates SQL, but executed read-only |
| Data Exfiltration | Row limits + session isolation |
| DoS via Complex Queries | 5s timeout + query complexity analysis |
| Schema Manipulation | Read-only mode blocks all DDL |
| File System Access | ATTACH blocked, URI mode only |

### Investigator Agent v2.0
LangGraph-based agentic workflow with self-correction:

**Pipeline Architecture:**
```
Decompose → Retrieve → Enrich → Analyze → Validate
                                    ↑         │
                                    └─ retry ─┘ (if quality < 7)
```

**Features:**
- **StateGraph**: Conditional edges for routing decisions
- **Quality Gates**: Validation node scores 1-10, threshold 7
- **Self-Correction**: Max 2 retries with validator feedback
- **Tool Calling**: Multi-provider web search (Tavily → Serper → DuckDuckGo)
- **X-Ray Integration**: Per-step latency and token tracking

**Enterprise Use Cases:**

| Use Case | Mission Example | Industry |
|----------|-----------------|----------|
| **M&A Due Diligence** | "Identify all liability clauses and indemnification gaps in this contract" | Legal, Finance |
| **Compliance Audit** | "Find GDPR violations and data retention policy gaps" | Healthcare, Tech |
| **Risk Assessment** | "Extract all financial risk indicators and compare to industry benchmarks" | Insurance, Banking |
| **Contract Review** | "Summarize key terms, flag unusual clauses, and identify missing sections" | Legal, Procurement |
| **Third-Party Due Diligence** | "Evaluate vendor compliance with ISO 27001 requirements" | Enterprise, Security |
| **Policy Analysis** | "Compare this employee handbook against current employment law" | HR, Legal |
| **AML Investigation** | "Identify suspicious patterns and flag high-risk transactions" | Banking, FinTech |
| **Technical Documentation** | "Extract API specifications and identify missing documentation" | Engineering |

**Why Agentic vs Simple RAG:**

| Scenario | Simple RAG | Investigator Agent |
|----------|------------|-------------------|
| "What is the termination clause?" | ✅ Single retrieval | Overkill |
| "Find all legal risks in this contract" | ❌ Miss context | ✅ Multi-step analysis |
| "Compare against compliance requirements" | ❌ No external context | ✅ Web search + analysis |
| "Ensure analysis is accurate" | ❌ No validation | ✅ Quality gate + retry |

**Industry Adoption Patterns (2024-2025):**
- Thomson Reuters CoCounsel: Agentic AI for deposition analysis and compliance
- KPMG Law + Google Cloud: Multi-agent platforms for contract lifecycle management
- Taylor Wessing + Legora: Automated due diligence and drafting support
- Organizations report **90% reduction** in document review processing time

### Security Layer
- **Rate Limiting**: Token bucket algorithm
- **CSRF**: Session-based tokens
- **Validation**: Magic byte + extension check
- **Headers**: CSP, X-Frame-Options, XSS-Protection
- **Monitoring**: Request tracking, abuse detection

### Analytics
- **Database**: SQLite (local)
- **Metrics**: Prometheus-compatible
- **Dashboard**: Real-time Chart.js visualizations
- **Privacy**: Aggregate data only

## Deployment Options

### Docker (Recommended)
- Single container deployment
- No internet required for operation
- Automatic health checks
- Resource limits enforced

### Google Cloud Run (Serverless)
- Auto-scaling based on traffic
- Pay-per-use pricing model
- Zero-downtime deployments
- Automatic SSL certificates
- Built-in load balancing
- Container-based deployment

## Security Features

### Input Validation
1. **File Size**: Triple validation (client, header, actual)
2. **Magic Bytes**: Content verification
3. **Extension**: Whitelist-based
4. **Filename**: Sanitized with werkzeug

### Rate Limiting
- **Per IP**: 20 requests/minute
- **Concurrent**: Max 10 simultaneous
- **Abuse**: Auto-block after threshold
- **Headers**: Remaining, reset time

### CSRF Protection
- Session-based tokens
- SameSite cookies
- Origin validation
- Token rotation

### Response Security
- CSP headers
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- Referrer-Policy: strict-origin

## Performance

### Optimization
- Async file I/O
- Connection pooling
- Response compression
- Static file caching

### Monitoring
- Request ID tracking
- Response time logging
- Error rate tracking
- Resource usage metrics

### Scalability
- Stateless design
- Horizontal scaling ready
- Load balancer compatible
- Database connection pooling

## Data Flow

### Document Conversion
```
1. Client uploads file
2. Validate size + format
3. Check rate limit
4. Verify CSRF token
5. Save to temp directory
6. Convert with MarkItDown
7. Delete original file
8. Return Markdown/Text
9. Log statistics (aggregate)
```

### RAG Pipeline
```
1. Convert document
2. Analyze structure
3. Chunk semantically
4. Count tokens
5. Generate embeddings
6. Export to format
7. Cleanup temp files
8. Return results
```

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, Flask |
| Conversion | markitdown |
| Embeddings | sentence-transformers |
| Tokenizer | tiktoken |
| Database | SQLite |
| Server | Gunicorn (Cloud Run) |
| Container | Docker |
| CI/CD | GitHub Actions |

## Configuration

All configuration via environment variables (`.env`):
- `SECRET_KEY`: Flask session key
- `MAX_FILE_SIZE`: Upload limit
- `RATE_LIMIT_REQUESTS`: Requests per window
- `RATE_LIMIT_WINDOW`: Time window (seconds)
- `MAX_CONCURRENT`: Concurrent limit
- `OPENROUTER_API_KEY`: Multi-model AI gateway
- `TAVILY_API_KEY`: Premium web search for Agent
- `SERPER_API_KEY`: Google search for Agent

See [deployment.md](deployment.md) for full configuration guide.

## Vector Store Configuration

MegaDoc supports multiple vector databases with a pluggable architecture:

| Store | Use Case | Configuration |
|-------|----------|---------------|
| **ChromaDB** | Development, small datasets | Default, no config needed |
| **LanceDB** | Local production, ML workloads | `VECTOR_STORE=lancedb` |
| **Qdrant** | Cloud production, high throughput | `QDRANT_URL`, `QDRANT_API_KEY` |
| **PostgreSQL** | Enterprise with pgvector | `POSTGRES_URL` with pgvector extension |

**Switching Stores:**
```python
# In memory_store.py
VECTOR_STORE = os.environ.get('VECTOR_STORE', 'chromadb')

# Stores implement common interface:
class VectorStore(Protocol):
    def add(self, texts: List[str], embeddings: List[List[float]], metadata: List[dict]) -> None
    def search(self, query_embedding: List[float], k: int = 5) -> List[dict]
    def clear(self) -> None
```

## Technical Decisions

### Flask vs FastAPI: Why Flask?

| Factor | Flask | FastAPI |
|--------|-------|---------|
| **Ecosystem Maturity** | ✅ Battle-tested, 13+ years | Newer (2018) |
| **Template Rendering** | ✅ Native Jinja2 | Requires extra setup |
| **Session Management** | ✅ Built-in secure cookies | Manual JWT needed |
| **Deployment Simplicity** | ✅ Any WSGI server | Requires ASGI (Uvicorn) |
| **AI/ML Integration** | ✅ Sync-first matches LLM APIs | Async not needed for OpenRouter |
| **Team Familiarity** | ✅ Standard in enterprise | Less common in legacy orgs |

**Decision Rationale:**
- MegaDoc is a document processing platform, not an API-only service
- Flask's template system enables the hybrid SPA/MPA architecture
- LLM API calls are inherently blocking (waiting for inference)
- Enterprise deployments often require WSGI compatibility (Cloud Run, Gunicorn)
- Session-based auth matches the ephemeral document workflow

**When FastAPI Would Be Better:**
- Pure API service with no frontend
- Need OpenAPI docs generation (MegaDoc has custom Swagger)
- High-concurrency WebSocket workloads
- Team already using Pydantic extensively

### Cost Optimization Strategy

**The 85% Savings Methodology:**
```
┌─────────────────────────────────────────────────────────┐
│              Cost per 1M tokens comparison               │
├─────────────────────────────────────────────────────────┤
│ GPT-4 Turbo      │ $10.00 input / $30.00 output        │
│ GPT-4o           │ $2.50 input / $10.00 output         │
│ Gemini 2.0 Flash │ $0.10 input / $0.40 output ← Default │
│ DeepSeek V3      │ $0.27 input / $1.10 output          │
│ Free Tier Models │ $0.00                    ← Fallback │
└─────────────────────────────────────────────────────────┘
```

**Smart Router Logic:**
1. Analyze query complexity (keywords, length, domain)
2. Simple queries → Free-tier models (Llama, Gemini Free)
3. Complex queries → Paid efficient models (Gemini Flash, DeepSeek)
4. Never route to GPT-4 unless explicitly requested
5. Track actual cost vs GPT-4 baseline per request
