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
| **Agentic Workflows** | LangGraph StateGraph with self-correction loops |
| **Cost Optimization** | 85% savings via intelligent model routing |
| **Observability** | X-Ray middleware (TTFT, latency, token tracking) |
| **Crash Prevention** | Circuit breaker, memory guards, request limiting |
| **CI/CD** | 11-stage pipeline with security scans and benchmarks |

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │            FLASK APPLICATION            │
                    └─────────────────────────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────┐            ┌─────────────────┐            ┌─────────────────┐
│   Document    │            │    RAG Chat     │            │   Investigator  │
│   Converter   │            │    Pipeline     │            │      Agent      │
│               │            │                 │            │                 │
│  PDF/DOCX/    │            │  ChromaDB +     │            │  LangGraph +    │
│  HTML → MD    │            │  OpenRouter     │            │  Web Search     │
└───────────────┘            └─────────────────┘            └─────────────────┘
        │                              │                              │
        └──────────────────────────────┼──────────────────────────────┘
                                       │
                    ┌─────────────────────────────────────────┐
                    │           MIDDLEWARE LAYER              │
                    │  • X-Ray Observability                  │
                    │  • Crash Prevention (Circuit Breaker)   │
                    │  • Smart Router (Model Selection)       │
                    └─────────────────────────────────────────┘
                                       │
                    ┌─────────────────────────────────────────┐
                    │           OPENROUTER GATEWAY            │
                    │  Gemini Flash │ DeepSeek │ Claude       │
                    └─────────────────────────────────────────┘
```

---

## Key Features

### Intelligent Model Routing
Routes queries to optimal models based on complexity, achieving 85% cost savings:

```python
# Simple queries → Free tier (Gemini Flash)
# Complex queries → Premium models (GPT-4, Claude)
router.route(query) → optimal_model
```

### Agentic Investigator
5-stage LangGraph pipeline with self-correction:

```
Decompose → Retrieve → Enrich → Analyze → Validate
     ↑                                    │
     └────── Self-correction loop ────────┘
             (if quality < 7/10)
```

### Crash Prevention System
Protects the 1GB free-tier VM from overload:

- **Concurrent Limiter**: Max 5 requests, 2 heavy operations
- **Circuit Breaker**: Opens after 5 failures, resets in 60s
- **Memory Guard**: Triggers GC at 80%, rejects at 92%

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Flask 3.0, Gunicorn |
| **AI/ML** | LangGraph, LangChain, OpenRouter |
| **Vector DB** | ChromaDB, LanceDB |
| **Observability** | Custom X-Ray middleware, Prometheus metrics |
| **CI/CD** | GitHub Actions (11 stages) |
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
| `/api/rag/chat` | POST | RAG-powered chat with documents |
| `/api/investigate` | POST | Agentic research workflow |
| `/api/sql/query` | POST | SQL Sandbox queries |
| `/health` | GET | Health check with system status |
| `/api/system/status` | GET | Crash prevention metrics |

---

## Project Structure

```
megadocs/
├── src/
│   ├── app.py              # Flask application factory
│   ├── routes.py           # API endpoints
│   ├── agents/             # LangGraph agentic workflows
│   │   └── investigator.py # 5-stage research agent
│   ├── middleware/         # Request processing
│   │   ├── xray.py         # Observability middleware
│   │   └── crash_prevention.py  # Circuit breaker + memory guard
│   ├── openrouter_gateway.py    # Multi-model AI gateway
│   └── templates/          # Jinja2 templates
├── tests/                  # Pytest test suites
├── .github/workflows/      # CI/CD pipelines
├── docs/                   # Documentation
└── docker-compose.yml      # Container orchestration
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
