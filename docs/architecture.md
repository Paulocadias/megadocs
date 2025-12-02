# Architecture

## System Overview

MegaDoc is built with a privacy-first, zero data retention architecture. All processing happens locally with no external API calls.

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTPS
       ▼
┌─────────────────────────────────┐
│      Flask Application          │
│  ┌───────────────────────────┐  │
│  │  Security Middleware      │  │
│  │  - Rate Limiting          │  │
│  │  - CSRF Protection        │  │
│  │  - Magic Byte Validation  │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Conversion Pipeline      │  │
│  │  - MarkItDown             │  │
│  │  - Format Detection       │  │
│  │  - Auto Cleanup           │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  RAG Pipeline             │  │
│  │  - Semantic Chunking      │  │
│  │  - Vector Embeddings      │  │
│  │  - DB Export              │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   SQLite    │  (Stats only)
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
- **Embeddings**: all-MiniLM-L6-v2 (384-dim)
- **Tokenizer**: tiktoken (cl100k_base)
- **Export**: ChromaDB, LanceDB, JSONL, FAISS

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

See [deployment.md](deployment.md) for full configuration guide.
