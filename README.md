# MegaDoc - Enterprise AI Platform

[![CI/CD](https://github.com/Paulocadias/megadocs/actions/workflows/pipeline.yml/badge.svg)](https://github.com/Paulocadias/megadocs/actions/workflows/pipeline.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Cost Savings](https://img.shields.io/badge/Cost%20Savings-85%25%20vs%20GPT--4-green.svg)](#cost-optimization)

## Why MegaDoc?

**Cut AI costs by 85%** while maintaining GPT-4 quality. MegaDoc is a production-ready AI platform that proves enterprise AI doesn't have to break the budget.

| Metric | Value | How |
|--------|-------|-----|
| **Cost Reduction** | 85-98% vs GPT-4 | Smart model routing + free-tier optimization |
| **Response Quality** | Comparable to GPT-4 | Domain-aware prompts + context injection |
| **Security** | Enterprise-grade | Zero data retention, input validation, guardrails |
| **Deployment** | One command | `docker-compose up` → production-ready |

**Live Demo**: [https://megadoc.paulocadias.com](https://megadoc.paulocadias.com)

---

## Cost Optimization

### The 85% Savings Methodology

MegaDoc achieves **85-98% cost savings** compared to GPT-4 through intelligent model routing:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Cost Comparison (per 1M tokens)              │
├─────────────────────────────────────────────────────────────────┤
│  GPT-4 Turbo        │  $10.00 input / $30.00 output            │
│  GPT-4o             │  $2.50 input / $10.00 output             │
│  Gemini 2.0 Flash   │  $0.10 input / $0.40 output   ← Default  │
│  DeepSeek V3        │  $0.27 input / $1.10 output              │
│  Free Tier Models   │  $0.00                        ← Fallback │
└─────────────────────────────────────────────────────────────────┘
```

**How it works:**
1. **Smart Router** analyzes query complexity (keywords, length, domain)
2. Routes simple queries → free-tier models (Gemini Flash Free, Llama)
3. Routes complex queries → paid efficient models (Gemini Flash, DeepSeek)
4. Never routes to GPT-4 unless explicitly requested
5. **X-Ray telemetry** tracks actual cost per request

**Real savings tracked in production:**
- Every API response includes `_debug.savings_percent` when `?debug=1` enabled
- Dashboard shows cumulative "Dollars Saved vs GPT-4"
- Typical savings: **$0.01-0.02 saved per chat request**

---

## Features

### Document Intelligence
- **Universal Ingestion**: PDF, Word, Excel, PowerPoint, Images (JPG, PNG) to unified text
- **Multi-Modal Vision**: Images analyzed via AI vision models and converted to searchable descriptions
- **Sanitization**: PII redaction, metadata stripping, macro removal

### Domain-Aware RAG Chat
- **Multi-Model Gateway**: Switch between AI providers (Gemini, DeepSeek, Llama) without code changes
- **Domain Profiles**: Legal, Medical, Technical, General - each with specialized system prompts
- **Context-Aware**: Chat with your uploaded documents using semantic search

### Enterprise Architecture
- **Privacy-First**: Ephemeral session storage with automatic cleanup (30 min TTL)
- **Security**: Rate limiting, CSRF protection, magic byte validation, input sanitization
- **Guardrails**: Input/Output guards with injection detection and hallucination checks
- **Cloud Native**: GCP Compute Engine with nginx reverse proxy

### v2.0 Enterprise Hardening

#### F1: Observability (X-Ray Middleware)
- **Request Tracing**: TTFT (Time To First Token), latency, and token usage metrics
- **Debug Panel**: Collapsible UI showing real-time performance data
- **Enable**: Add `?debug=1` query param or `X-Debug: 1` header

#### F2: Cost Optimization (Smart Router)
- **Intelligent Routing**: Automatic model selection based on query complexity
- **Complexity Analysis**: Routes simple queries to free-tier models, complex to premium
- **Configuration**: External `config/models.yaml` for routing rules
- **UI Toggle**: "Smart" model option in RAG chat interface

#### F3: Reliability (Eval Suite)
- **Safety Testing**: 30 adversarial prompts across 12 attack categories
- **Attack Categories**: Jailbreak, prompt injection, PII extraction, harmful content, role manipulation, context manipulation, domain bypass, hallucination trigger, multi-turn, data leakage, output manipulation, overflow
- **CI Integration**: Automated PR safety checks via GitHub Actions
- **Run**: `pytest tests/evals/ -v -m eval`

#### F4: Universal SQL Sandbox (BYOD)
- **Bring Your Own Database**: Upload and query databases with natural language
- **Supported Formats**: SQLite (.db, .sqlite), SQL dumps (.sql), CSV, Excel (.xlsx)
- **Security**: Read-only connections, 5s query timeout, 1000 row limit, 50MB upload limit
- **Architect View**: Glass-box panel showing generated SQL, schema, and execution logs
- **Routes**: `/sql-sandbox`, `/api/sql/upload`, `/api/sql/query`, `/api/sql/schema`, `/api/sql/clear`

#### AI Assistant (Platform-Wide)
- **3-Tier Response System**: Direct stats queries, knowledge base lookup, LLM fallback
- **Floating Chat Widget**: Available on all pages for instant help
- **Live Stats Access**: Real-time platform metrics without LLM dependency
- **Rate Limit Resilient**: Graceful fallback when OpenRouter limits reached

---

## Quick Start

### One-Command Startup (Recommended)
```bash
git clone https://github.com/Paulocadias/megadocs.git
cd megadocs

# Optional: Configure API key for AI chat
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# Start the platform
docker-compose up -d
```
Visit http://localhost:8080

### Local Development
```bash
git clone https://github.com/Paulocadias/megadocs.git
cd megadocs
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Optional: Set API key for chat features
export OPENROUTER_API_KEY=your_key_here

python src/app.py
```

---

## API Usage

### Document Conversion
```bash
# Convert PDF to Markdown
curl -X POST -F "file=@document.pdf" https://megadoc.paulocadias.com/api/convert

# Convert with sanitization
curl -X POST \
  -F "file=@document.pdf" \
  -F "redact_emails=true" \
  -F "strip_metadata=true" \
  https://megadoc.paulocadias.com/api/convert
```

### Chat with Documents
```bash
curl -X POST https://megadoc.paulocadias.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Google Gemini 2.0 Flash",
    "messages": [{"role": "user", "content": "Summarize this document"}],
    "context": "Document content here...",
    "domain": "legal"
  }'
```

### SQL Sandbox (BYOD)
```bash
# Upload a database file
curl -X POST -F "file=@database.sqlite" \
  https://megadoc.paulocadias.com/api/sql/upload

# Query with natural language
curl -X POST https://megadoc.paulocadias.com/api/sql/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many users registered last month?"}'

# Get schema
curl https://megadoc.paulocadias.com/api/sql/schema

# Clear session
curl -X POST https://megadoc.paulocadias.com/api/sql/clear
```

---

## Supported Formats

| Category | Extensions |
|----------|------------|
| Documents | `.pdf`, `.docx`, `.doc`, `.txt` |
| Spreadsheets | `.xlsx`, `.xls`, `.csv` |
| Presentations | `.pptx`, `.ppt` |
| Images | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp` |
| Web | `.html`, `.htm`, `.json`, `.xml` |
| E-books | `.epub` |
| Databases (SQL Sandbox) | `.db`, `.sqlite`, `.sqlite3`, `.sql` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                          │
│  Landing → Document Upload → RAG Chat → Export               │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                         │
│  Rate Limiting │ CSRF Protection │ Input Validation          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Document Processing                         │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │ Converter │→ │  Chunker  │→ │ Embedder  │               │
│  └───────────┘  └───────────┘  └───────────┘               │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                 Multi-Model Gateway                          │
│  Gemini │ DeepSeek │ Llama │ Domain Injection               │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

- **Vendor-Agnostic**: Hot-swap AI providers without code changes
- **Domain Injection**: Runtime system prompt injection per domain profile
- **Ephemeral Storage**: No persistent document storage, TTL-based cleanup
- **Guardrails Layer**: Input/Output validation at every inference

### CI/CD Pipeline (Enterprise Grade)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GitHub Actions Pipeline                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Push ──┬──→ 🛡️ Security Scan ──┬──→ 📦 Build ──→ 🎭 Staging ──→ 🚀 Prod   │
│         │    (gitleaks/bandit)   │                      │            │       │
│         ├──→ 🔍 Quality Gate ────┤                      │      [Manual Gate] │
│         │    (flake8/black)      │                      │            │       │
│         └──→ 🧪 Test Matrix ─────┘                      └────────────┘       │
│              (unit/integration)                                              │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Security: Secret scanning, code analysis, dependency audit                  │
│  Deployment: GCP VM with nginx + Let's Encrypt SSL auto-renewal             │
│  Gate: Staging must pass before Production (+ manual approval option)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Pipeline Features:**
- **DevSecOps**: gitleaks (secrets), bandit (code security), safety (CVE scan)
- **Multi-Stage Testing**: Unit, Integration, Smoke tests in parallel
- **Zero-Downtime Deploy**: PID-based process management with health checks
- **HTTPS Auto-Config**: Let's Encrypt certificate with auto-renewal

---

## Project Structure

```
megadocs/
├── src/                       # Application source code
│   ├── app.py                 # Flask entry point
│   ├── routes.py              # API endpoints & web routes
│   ├── converter.py           # Document conversion engine
│   ├── chunker.py             # RAG text chunking
│   ├── embedder.py            # Vector embeddings
│   ├── openrouter_gateway.py  # Multi-model AI gateway
│   ├── router.py              # Smart model routing (F2)
│   ├── sql_sandbox.py         # BYOD SQL engine (F4)
│   ├── assistant.py           # AI Assistant with 3-tier response
│   ├── stats.py               # Platform statistics & metrics
│   ├── security.py            # CSRF, rate limiting, auth
│   ├── health.py              # Health checks & monitoring
│   ├── middleware/            # X-Ray tracing middleware (F1)
│   │   └── xray.py            # @xray_trace decorator
│   └── templates/             # Jinja2 HTML templates
│       ├── sql_sandbox.html   # SQL Sandbox UI
│       ├── stats.html         # Operations Dashboard
│       └── includes/          # Shared components
│           ├── chat_widget.html  # Floating AI Assistant
│           └── debug_panel.html  # Debug metrics panel
├── config/                    # External configuration
│   └── models.yaml            # Smart router model config
├── static/                    # CSS, JS, images
├── tests/                     # Test suite
│   └── evals/                 # Safety eval suite (F3)
│       ├── adversarial_prompts.py  # 30 attack test cases
│       └── run_safety_evals.py     # SafetyEvaluator
├── docs/                      # Technical documentation
├── .github/workflows/         # CI/CD pipeline
│   ├── pipeline.yml           # Main CI/CD workflow
│   └── evals.yml              # Safety eval workflow
├── Dockerfile                 # Container configuration
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask secret key | Yes |
| `OPENROUTER_API_KEY` | API key for chat features | No |
| `MAX_FILE_SIZE` | Max upload size (default: 50MB) | No |
| `RATE_LIMIT_REQUESTS` | Requests per window (default: 200) | No |

---

## Deployment

### Google Cloud Run
```bash
gcloud run deploy megadoc \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

### Docker Compose
```yaml
services:
  megadoc:
    image: paulocadias/megadoc:latest
    ports:
      - "8080:8080"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
```

---

## Tech Stack

- **Backend**: Python 3.11+, Flask
- **Document Processing**: markitdown, sentence-transformers
- **AI Gateway**: OpenRouter (multi-model)
- **Frontend**: Bootstrap 5, Vanilla JS
- **Deployment**: Docker, Google Cloud Run
- **Testing**: pytest, coverage

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Author**: [Paulo Cadias](https://github.com/Paulocadias)
**Live Demo**: [https://megadoc.paulocadias.com](https://megadoc.paulocadias.com)

