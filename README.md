# MegaDoc - Enterprise Document Intelligence Platform

A production-grade document conversion platform with RAG pipeline, vector embeddings, and zero data retention architecture. Built as an AI Tech Lead portfolio demonstration showcasing enterprise-level security and scalable document processing.

**Live at**: https://megadocs.paulocadias.com

## Features

### Document Conversion
- **Instant Conversion**: Upload a file, get Markdown back immediately
- **Output Format Choice**: Export as Markdown (.md) or clean Plain Text (.txt)
- **Multiple Formats**: PDF, Word, Excel, PowerPoint, Images, and more

### RAG Pipeline
- **Semantic Chunking**: Token-aware splitting with tiktoken (cl100k_base)
- **Vector Embeddings**: 384-dimensional embeddings (all-MiniLM-L6-v2)
- **Vector DB Export**: ChromaDB, LanceDB, JSONL, FAISS-ready formats
- **Full Pipeline API**: Convert → Chunk → Embed in single API call

### Enterprise Architecture
- **Zero Data Retention**: Files deleted immediately after processing
- **Privacy by Design**: No external API calls, 100% offline processing
- **MCP Server**: Model Context Protocol integration for Claude agents
- **Batch Processing**: ZIP uploads with async webhook notifications

### Security (OWASP Top 10)
- **Rate Limiting**: 20 requests/minute per IP
- **CSRF Protection**: Session-based token validation
- **Magic Byte Validation**: Verify file content matches extension
- **Brute Force Protection**: Auto-block after abuse threshold
- **Security Headers**: CSP, X-Frame-Options, XSS-Protection

## Supported File Formats

| Category | Extensions |
|----------|------------|
| Documents | `.pdf`, `.docx`, `.doc`, `.txt` |
| Spreadsheets | `.xlsx`, `.xls`, `.csv` |
| Presentations | `.pptx`, `.ppt` |
| Images | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp` |
| Web | `.html`, `.htm`, `.json`, `.xml` |
| E-books | `.epub` |

## Architecture & Standards

### Tech Stack
- **Backend**: Python 3 + Flask
- **Conversion**: markitdown
- **Database**: SQLite (statistics & contact requests)
- **Hosting**: DreamHost Shared Hosting (Passenger WSGI)
- **Frontend**: Vanilla HTML/CSS/JS (no framework needed)

### Directory Structure
```
DocsSite/
├── src/
│   ├── app.py              # Flask application factory
│   ├── routes.py           # Route handlers (blueprints)
│   ├── converter.py        # MarkItDown wrapper
│   ├── embedder.py         # Vector embeddings (all-MiniLM-L6-v2)
│   ├── stats.py            # SQLite statistics module
│   ├── security.py         # Security middleware
│   ├── config.py           # Configuration management
│   ├── mcp_server.py       # MCP server for Claude agents
│   └── templates/
│       ├── landing.html    # Portfolio landing page (/)
│       ├── index.html      # Converter tool (/convert)
│       ├── architecture.html # System architecture
│       ├── use_cases.html  # Enterprise use cases
│       ├── admin.html      # Admin dashboard
│       ├── api-docs.html   # API documentation
│       └── contact.html    # API access request form
├── static/
│   └── style.css
├── data/
│   └── stats.db            # SQLite database (auto-created)
├── passenger_wsgi.py       # DreamHost entry point
├── requirements.txt
├── .htaccess               # Apache configuration
├── README.md
└── projectplan.md
```

### Security Features

| Feature | Description |
|---------|-------------|
| Rate Limiting | 20 requests/minute per IP |
| Concurrency Limit | Max 10 simultaneous conversions |
| File Size Limit | Maximum 50MB (triple validation) |
| Magic Byte Validation | Verify file content matches extension |
| CSRF Protection | Session-based token validation |
| Security Headers | CSP, X-Frame-Options, XSS-Protection |
| Honeypot Detection | Hidden field to catch bots |
| IP Blocking | Auto-block after abuse threshold |
| Request Tracking | Unique ID for every request |
| Secure Filenames | Sanitized using werkzeug |
| Auto Cleanup | Files deleted immediately after conversion |
| Capacity Tracking | Track users left out when over capacity |

### File Size Validation (Triple Check)

The system validates file size at three levels to ensure strict enforcement:

1. **Client-side (JavaScript)**: Prevents upload attempt, shows file size in error
2. **Content-Length Header**: Server checks HTTP header before reading file
3. **Actual File Size**: Server verifies actual bytes after reading

```
User selects file → JS check (50MB) → Server Content-Length check → Server actual size check
```

### SEO Features

| Feature | Description |
|---------|-------------|
| Open Graph | Facebook/LinkedIn sharing optimization |
| Twitter Cards | Twitter sharing optimization |
| JSON-LD | Structured data for search engines |
| Canonical URL | Prevent duplicate content issues |
| Meta Tags | Description, keywords, robots directives |
| Inline SVG Favicon | No external file needed, works on all pages |

### Accessibility Features

| Feature | Description |
|---------|-------------|
| Keyboard Navigation | Upload area supports Enter/Space keys |
| ARIA Labels | Screen reader support for upload area |
| Focus Indicators | Visible focus states on all interactive elements |
| Color Contrast | WCAG 2.1 compliant color ratios |

### Code Patterns
- Type hints on all functions
- Request validation on all endpoints
- Proper error responses (JSON for API, HTML for web)
- Structured logging with request IDs
- Thread-safe statistics persistence

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main upload page |
| POST | `/convert` | Convert file (web form) |
| POST | `/api/convert` | Convert file (API - returns JSON) |
| GET | `/api/stats` | Public statistics |
| GET | `/api/formats` | Supported formats list |
| GET | `/api/docs` | API documentation page |
| GET | `/admin` | Admin dashboard |
| GET | `/contact` | API access request form |
| POST | `/contact` | Submit API access request |
| GET | `/health` | Health check |
| GET | `/security-info` | Security features info |

## API Usage

### Convert a File (cURL)
```bash
# Convert to Markdown (default)
curl -X POST -F "file=@document.pdf" https://paulocadias.com/api/convert

# Convert to Plain Text
curl -X POST -F "file=@document.pdf" -F "output_format=text" https://paulocadias.com/api/convert
```

### Response
```json
{
  "success": true,
  "filename": "document.md",
  "content": "# Document Title\n\nContent here...",
  "format": "markdown",
  "request_id": "A1B2C3D4"
}
```

### Output Formats

| Format | Value | Extension | Description |
|--------|-------|-----------|-------------|
| Markdown | `markdown` (default) | `.md` | Formatted with headers, lists, links |
| Plain Text | `text` | `.txt` | Clean formatted text without markup |

**Plain Text Conversion Process:**
```
Document → MarkItDown → Markdown → Strip MD Syntax → Plain Text
```

The Plain Text converter:
- Removes headers (`#`, `##`, etc.) but keeps text
- Strips bold/italic (`**`, `*`, `__`, `_`)
- Converts links `[text](url)` to just `text`
- Removes images, keeps alt text
- Converts bullet lists to `•` symbols
- Cleans blockquotes and code blocks
- Normalizes whitespace

### Get Statistics
```bash
curl https://paulocadias.com/api/stats
```

### Python Example
```python
import requests

url = "https://paulocadias.com/api/convert"

# Convert to Markdown (default)
files = {'file': open('document.pdf', 'rb')}
response = requests.post(url, files=files)
data = response.json()

if data['success']:
    print(data['content'])  # Markdown content

# Convert to Plain Text
files = {'file': open('document.pdf', 'rb')}
data = {'output_format': 'text'}
response = requests.post(url, files=files, data=data)

if response.json()['success']:
    print(response.json()['content'])  # Plain text content
```

### JavaScript Example
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('output_format', 'text'); // or 'markdown'

const response = await fetch('/api/convert', {
    method: 'POST',
    body: formData
});

const data = await response.json();
if (data.success) {
    console.log(data.content);
    console.log(data.format); // 'text' or 'markdown'
}
```

## Rate Limits

| Limit Type | Value | Window |
|------------|-------|--------|
| Requests per IP | 20 | 1 minute |
| Max file size | 50 MB | Per request |

### Rate Limit Headers
- `X-RateLimit-Remaining`: Requests remaining in window
- `X-RateLimit-Reset`: Seconds until limit resets
- `Retry-After`: Seconds to wait (on 429)

## Error Handling

### HTTP Status Codes

| Code | Description | When |
|------|-------------|------|
| 200 | Success | Conversion completed |
| 400 | Bad Request | Invalid filename, unsupported format, honeypot triggered |
| 403 | Forbidden | CSRF token invalid, IP blocked |
| 413 | Payload Too Large | File exceeds 50MB limit |
| 429 | Too Many Requests | Rate limit exceeded (20/min) |
| 500 | Server Error | Conversion failed |
| 503 | Service Unavailable | System at capacity (10 concurrent) |

### Error Response Format
```json
{
  "error": "Human-readable error message",
  "request_id": "A1B2C3D4"
}
```

### Response Headers

All responses include these headers:

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Unique ID for tracking/debugging |
| `X-Response-Time` | Processing time (e.g., "0.523s") |
| `X-RateLimit-Remaining` | Requests left in window |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Content-Security-Policy` | CSP rules |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

## Source Code
**Repository**: [https://github.com/Paulocadias/DOCSsite](https://github.com/Paulocadias/DOCSsite)

## Deployment

### Option 1: Google Cloud Platform (Free Tier) - Recommended
Optimized for `e2-micro` (Always Free).

1. **Clone Repository**:
   ```bash
   git clone https://github.com/Paulocadias/DOCSsite.git
   cd DOCSsite
   ```

2. **Run Deployment Script**:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```
   This script automatically:
   - Installs Docker & Git
   - Sets up Swap (1GB) for memory safety
   - Configures Firewall (UFW) & Fail2Ban
   - Generates `.env` with secure keys
   - Builds and runs the Docker container

### Option 2: DreamHost Shared Hosting
(Legacy support via Passenger WSGI)

### Prerequisites
1. DreamHost shared hosting account
2. Domain configured (paulocadias.com)
3. Passenger enabled for the domain

### Setup Steps

1. **Enable Passenger** in DreamHost panel:
   - Go to Manage Domains
   - Edit paulocadias.com
   - Enable Passenger (Python)

2. **SSH into server**:
   ```bash
   ssh user@paulocadias.com
   ```

3. **Create virtual environment**:
   ```bash
   cd ~/paulocadias.com
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Upload files** to `~/paulocadias.com/`

5. **Restart Passenger**:
   ```bash
   touch tmp/restart.txt
   ```

### Environment Variables
Set in `.env` file (never commit this):

| Variable | Description | Default |
|----------|-------------|---------|
| `MAX_FILE_SIZE` | Max upload size in bytes | `52428800` (50MB) |
| `SECRET_KEY` | Flask secret key | (auto-generated) |
| `RATE_LIMIT_REQUESTS` | Requests per window | `20` |
| `RATE_LIMIT_WINDOW` | Window in seconds | `60` |
| `ABUSE_THRESHOLD` | Requests before block | `100` |
| `ABUSE_BLOCK_DURATION` | Block duration in seconds | `3600` |
| `MAX_CONCURRENT` | Max simultaneous conversions | `10` |

## Local Development

```bash
# Clone repo
git clone https://github.com/Paulocadias/DOCSsite.git
cd DOCSsite

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
python src/app.py
```

Visit http://localhost:8080

## License

Private repository - All rights reserved

---
&copy; 2025 paulocadias.com
