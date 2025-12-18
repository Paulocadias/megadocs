# API Documentation

## Base URL
- **Production**: https://megadocs.paulocadias.com
- **Local**: http://localhost:8080

## Authentication

### Standard API
No authentication required. Rate limited to 20 requests/minute per IP.

### API Keys (Higher Limits)
Request an API key via `/contact` for higher rate limits.

**Usage:**
```bash
curl -H "X-API-Key: your-key-here" -X POST -F "file=@doc.pdf" https://megadocs.paulocadias.com/api/convert
```

## Endpoints

### POST /api/convert
Convert a document to Markdown or Plain Text.

**Parameters:**
- `file` (required): File to convert
- `output_format` (optional): `markdown` (default) or `text`

**Response:**
```json
{
  "success": true,
  "filename": "document.md",
  "content": "# Title\n\nContent...",
  "format": "markdown",
  "request_id": "A1B2C3D4"
}
```

**Error Response:**
```json
{
  "error": "File too large (max 50MB)",
  "request_id": "A1B2C3D4"
}
```

### GET /api/stats
Get system statistics and analytics.

**Response:**
```json
{
  "total_conversions": 1234,
  "today_conversions": 45,
  "success_rate": 98.5,
  "uptime_hours": 720,
  "conversions_by_day": [...],
  "file_types": {...}
}
```

### GET /api/formats
List all supported file formats.

**Response:**
```json
{
  "formats": [
    {"extension": ".pdf", "category": "Documents"},
    {"extension": ".docx", "category": "Documents"},
    ...
  ]
}
```

### POST /api/batch/convert
Convert multiple files from a ZIP archive.

**Parameters:**
- `file` (required): ZIP file containing documents
- `webhook_url` (optional): URL to receive completion notification

**Response:**
```json
{
  "batch_id": "batch_123",
  "status": "processing",
  "files_count": 5
}
```

## RAG Pipeline Endpoints

### POST /api/analyze
Analyze document structure.

### POST /api/chunk
Chunk document for RAG.

**Parameters:**
- `text` (required): Text to chunk
- `chunk_size` (optional): Max tokens per chunk (default: 512)
- `overlap` (optional): Overlap tokens (default: 50)

### POST /api/embed
Generate vector embeddings.

**Parameters:**
- `text` (required): Text to embed

**Response:**
```json
{
  "embeddings": [0.123, -0.456, ...],
  "dimensions": 384,
  "model": "all-MiniLM-L6-v2"
}
```

### POST /api/export/vectordb
Export to vector database format.

**Parameters:**
- `text` (required): Text content
- `format` (required): `chromadb`, `lancedb`, or `jsonl`

### POST /api/pipeline
Full RAG pipeline in one call.

**Parameters:**
- `file` (required): Document file
- `chunk_size` (optional): Tokens per chunk
- `format` (optional): Export format

## Investigator Agent (Agentic Workflows)

### POST /api/investigate
Execute autonomous multi-step investigation on uploaded documents. Uses LangGraph StateGraph for orchestrated reasoning.

**Security & Rate Limiting:**
- Protected by `@security_check` decorator (rate limiting, IP validation)
- Protected by `@xray_trace` decorator (full telemetry tracking)
- Standard rate limit: 20 requests/minute per IP
- Session-based document access (requires prior document upload)
- Input validation: mission max 500 characters

**Parameters:**
- `mission` (required): Investigation goal (e.g., "Identify all legal risks in this contract")
- `model` (optional): LLM model to use (default: "Google Gemini 2.0 Flash")

**Workflow Pipeline (5-7 steps):**
1. **Decompose** - Break mission into sub-tasks
2. **Retrieve** - Fetch relevant document chunks via vector search
3. **Enrich** - Optional external context via web search tools
4. **Analyze** - Deep reasoning over retrieved context
5. **Validate** - Quality gate with self-correction (quality < 7 triggers retry, max 2x)

**Request:**
```json
POST /api/investigate
Content-Type: application/json

{
  "mission": "Identify all legal risks and liability clauses in this contract"
}
```

**Response:**
```json
{
  "success": true,
  "report": {
    "summary": "Found 5 legal risks...",
    "findings": [
      {
        "risk": "Unlimited liability clause",
        "location": "Section 4.2",
        "severity": "high",
        "source": "contract.pdf:page4"
      },
      {
        "risk": "Non-compete too broad",
        "location": "Section 7.1",
        "severity": "medium",
        "source": "contract.pdf:page7"
      }
    ],
    "quality": {
      "quality_score": 8.5,
      "threshold": 7
    }
  },
  "steps_completed": 5,
  "total_latency_ms": 4500,
  "cost": 0.0023,
  "savings_percent": 94.2,
  "request_id": "A1B2C3D4"
}
```

**Debug Mode (add `?debug=1` or `X-Debug: 1` header):**
```json
{
  "success": true,
  "report": {...},
  "_debug": {
    "agent_steps": ["decompose", "retrieve", "enrich", "analyze", "validate"],
    "agent_step_latencies": {
      "decompose": 800,
      "retrieve": 200,
      "enrich": 1000,
      "analyze": 2500,
      "validate": 1000
    },
    "documents_analyzed": ["contract.pdf"],
    "chunks_retrieved": 12,
    "tool_calls": ["tavily_search"],
    "retried": false,
    "quality_score": 8.5,
    "quality_threshold": 7
  }
}
```

**Error Responses:**
| Code | Error | Description |
|------|-------|-------------|
| 400 | "Mission is required" | Empty mission parameter |
| 400 | "Mission too long" | Exceeds 500 character limit |
| 400 | "JSON body required" | Invalid content type |
| 429 | "Rate limit exceeded" | Too many requests |
| 500 | "Internal server error" | Agent execution failed |

**Prerequisites:**
Upload documents first via `/api/convert` with `inject_memory=true` before calling investigate.

## Rate Limits

| Limit Type | Standard | With API Key |
|------------|----------|--------------|
| Requests/minute | 20 | 100 |
| Max file size | 50 MB | 100 MB |
| Concurrent requests | 10 | 20 |

## HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid file, format) |
| 403 | Forbidden (CSRF, IP blocked) |
| 413 | Payload Too Large (>50MB) |
| 429 | Too Many Requests (rate limit) |
| 500 | Server Error |
| 503 | Service Unavailable (capacity) |

## Response Headers

All responses include:
- `X-Request-ID`: Unique request identifier
- `X-Response-Time`: Processing time
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Seconds until reset

## Examples

See [examples.md](examples.md) for code samples in Python, JavaScript, cURL, and more.
