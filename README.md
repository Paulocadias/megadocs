# MegaDoc - Enterprise Document Intelligence Platform

[![CI](https://github.com/Paulocadias/megadocs/actions/workflows/ci.yml/badge.svg)](https://github.com/Paulocadias/megadocs/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A production-grade **Multi-Modal AI Platform** for document processing, RAG-powered chat, and enterprise-ready AI workflows. Transform documents and images into searchable content, chat with your data using domain-aware AI models, and prepare data for RAG pipelines.

**Live Demo**: [https://megadocs.paulocadias.com](https://megadocs.paulocadias.com)

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
- **Serverless**: Google Cloud Run with auto-scaling

---

## Quick Start

### Docker (Recommended)
```bash
docker pull paulocadias/megadoc:latest
docker run -p 8080:8080 paulocadias/megadoc
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
curl -X POST -F "file=@document.pdf" https://megadocs.paulocadias.com/api/convert

# Convert with sanitization
curl -X POST \
  -F "file=@document.pdf" \
  -F "redact_emails=true" \
  -F "strip_metadata=true" \
  https://megadocs.paulocadias.com/api/convert
```

### Chat with Documents
```bash
curl -X POST https://megadocs.paulocadias.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Google Gemini 2.0 Flash",
    "messages": [{"role": "user", "content": "Summarize this document"}],
    "context": "Document content here...",
    "domain": "legal"
  }'
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
│   ├── security.py            # CSRF, rate limiting, auth
│   ├── analytics.py           # Usage analytics & metrics
│   ├── health.py              # Health checks & monitoring
│   └── templates/             # Jinja2 HTML templates
├── static/                    # CSS, JS, images
├── tests/                     # Test suite (unit, integration)
├── docs/                      # Technical documentation
├── .github/workflows/         # CI/CD pipeline
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
**Live Demo**: [https://megadocs.paulocadias.com](https://megadocs.paulocadias.com)

