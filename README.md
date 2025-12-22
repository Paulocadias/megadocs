# MegaDoc - Enterprise AI Platform

[![CI/CD](https://github.com/Paulocadias/megadocs/actions/workflows/pipeline.yml/badge.svg)](https://github.com/Paulocadias/megadocs/actions/workflows/pipeline.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0-black.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-purple.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Production-ready AI platform demonstrating enterprise patterns: RAG pipelines, agentic workflows, observability, and cost optimization.

**Live Demo**: [https://megadoc.paulocadias.com](https://megadoc.paulocadias.com)

---

## What This Demonstrates

| Capability | Implementation |
|------------|----------------|
| **RAG Pipeline** | ChromaDB + domain-aware retrieval (Legal, Medical, Technical) |
| **SQL Sandbox** | Natural language to SQL with read-only enforcement |
| **Agentic Workflows** | LangGraph StateGraph with self-correction loops |
| **Cost Optimization** | 99% savings via intelligent model routing (Gemini Flash) |
| **Observability** | X-Ray middleware (TTFT, latency, token tracking) |
| **Security** | Cloudflare DDoS, OWASP headers, Circuit Breaker |
| **Crash Prevention** | Circuit breaker, memory guards, request limiting |
| **CI/CD** | 11-stage pipeline with security scans and Dependabot |

---

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │            FLASK APPLICATION            │
                         └─────────────────────────────────────────┘
                                            │
     ┌──────────────────┬───────────────────┼───────────────────┬──────────────────┐
     │                  │                   │                   │                  │
     ▼                  ▼                   ▼                   ▼                  ▼
┌──────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────┐
│ Document │    │  RAG Chat   │    │    SQL      │    │Investigator │    │  MCP     │
│Converter │    │  Pipeline   │    │  Sandbox    │    │   Agent     │    │ Server   │
│          │    │             │    │             │    │             │    │          │
│ PDF/DOCX │    │ ChromaDB +  │    │ NL → SQL +  │    │ LangGraph + │    │ Claude   │
│ HTML→MD  │    │ OpenRouter  │    │ Read-Only   │    │ Web Search  │    │ Desktop  │
└──────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └──────────┘
     │                  │                   │                   │                  │
     └──────────────────┴───────────────────┼───────────────────┴──────────────────┘
                                            │
                         ┌─────────────────────────────────────────┐
                         │           MIDDLEWARE LAYER              │
                         │  • X-Ray Observability                  │
                         │  • Crash Prevention (Circuit Breaker)   │
                         │  • Security Headers (OWASP)             │
                         └─────────────────────────────────────────┘
                                            │
                         ┌─────────────────────────────────────────┐
                         │           OPENROUTER GATEWAY            │
                         │  Gemini 2.0 Flash │ Gemini 2.5 Pro      │
                         └─────────────────────────────────────────┘
```

---

## Key Features

### Intelligent Model Routing
Routes queries to optimal models based on complexity, achieving 99% cost savings:

```python
# All queries → Gemini 2.0 Flash (free tier, high quality)
# Complex analysis → Gemini 2.5 Pro (premium, when needed)
# Cost: $0.07 vs $7.11 GPT-4 equivalent = 99% savings
```

### Agentic Investigator
5-stage LangGraph pipeline with self-correction:

```
Decompose → Retrieve → Enrich → Analyze → Validate
     ↑                                    │
     └────── Self-correction loop ────────┘
             (if quality < 7/10)
```

### SQL Sandbox
Natural language to SQL with security-first design:

- **Upload**: SQLite DB, SQL dump, CSV, Excel files
- **NL to SQL**: AI converts questions to SQL queries
- **Read-Only**: DML statements blocked, LIMIT enforced
- **Schema Explorer**: Visual table/column browser

### Crash Prevention System
Protects the 1GB free-tier VM from overload:

- **Concurrent Limiter**: Max 5 requests, 2 heavy operations
- **Circuit Breaker**: Opens after 5 failures, resets in 60s
- **Memory Guard**: Triggers GC at 80%, rejects at 92%

### Security Features
Enterprise-grade protection:

- **Cloudflare**: DDoS protection, WAF, SSL termination
- **OWASP Headers**: CSP, HSTS, X-Frame-Options, XSS Protection
- **Input Validation**: Honeypot fields, CSRF tokens
- **Dependency Scanning**: Dependabot + CodeRabbit reviews

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Flask 3.0, Gunicorn |
| **AI/ML** | LangGraph, LangChain, OpenRouter, Gemini |
| **Vector DB** | ChromaDB (embeddings), SQLite (SQL Sandbox) |
| **Security** | Cloudflare, pybreaker (Circuit Breaker) |
| **Observability** | Custom X-Ray middleware |
| **CI/CD** | GitHub Actions, Dependabot, CodeRabbit |
| **Infrastructure** | GCP e2-micro (free tier), Docker |

---

## Quick Start

```bash
# Clone
git clone https://github.com/Paulocadias/megadocs.git
cd megadocs

# Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Add your OPENROUTER_API_KEY

# Run
python src/app.py
# → http://localhost:8080
```

### Docker

```bash
docker-compose up -d
# → http://localhost:5000
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/convert` | POST | Convert documents to Markdown |
| `/api/chat` | POST | RAG-powered chat with documents |
| `/api/investigate` | POST | Agentic research workflow |
| `/api/sql/upload` | POST | Upload database files |
| `/api/sql/query` | POST | Execute SQL queries |
| `/api/sql/schema` | GET | Get database schema |
| `/api/stats` | GET | Platform statistics |
| `/health` | GET | Health check with system status |
| `/api/system/status` | GET | Circuit breaker & memory metrics |

---

## Project Structure

```
megadocs/
├── src/
│   ├── app.py                   # Flask application factory
│   ├── routes.py                # API endpoints
│   ├── sql_sandbox.py           # SQL Sandbox (NL→SQL, read-only)
│   ├── agents/
│   │   └── investigator.py      # 5-stage LangGraph agent
│   ├── middleware/
│   │   ├── xray.py              # Observability middleware
│   │   └── crash_prevention.py  # Circuit breaker + memory guard
│   ├── openrouter_gateway.py    # Multi-model AI gateway
│   └── templates/               # Jinja2 templates
├── tests/                       # Pytest test suites
├── .github/
│   ├── workflows/pipeline.yml   # CI/CD (11 stages)
│   └── dependabot.yml           # Dependency updates
├── .coderabbit.yaml             # AI code review config
└── docker-compose.yml           # Container orchestration
```

---

## CI/CD Pipeline

11-stage enterprise pipeline:

```
Quality Gate → Security Scan → Test Matrix → Smoke Test
      ↓
Docker Scan → Performance Benchmark → Build Release
      ↓
Deploy Production → Notify
```

---

## Environment Variables

```bash
# Required
OPENROUTER_API_KEY=your_key_here

# Optional
SECRET_KEY=your_secret_key
GEMINI_API_KEY=for_evaluations
TAVILY_API_KEY=for_web_search
```

---

## Author

**Paulo Dias** - AI Tech Lead & Solutions Architect

- LinkedIn: [paulocadias](https://linkedin.com/in/paulocadias)
- GitHub: [Paulocadias](https://github.com/Paulocadias)

---

## License

MIT License - see [LICENSE](LICENSE) for details.
