# Testing Guide - MegaDoc

Quick guide to run and test MegaDoc locally.

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Git (optional, for cloning)

## Step 1: Set Up Virtual Environment

### Windows
```cmd
python -m venv venv
venv\Scripts\activate
```

### Linux/Mac
```bash
python3 -m venv venv
source venv/bin/activate
```

## Step 2: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Note**: This may take a few minutes as it installs ML libraries (sentence-transformers, scikit-learn, etc.)

## Step 3: Set Environment Variables

Create a `.env` file in the project root (optional, but recommended):

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

Or create `.env` manually with:

```env
# Required
SECRET_KEY=your_secret_key_here

# Optional: For chat features (RAG page)
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_HTTP_REFERER=http://localhost:8080

# Optional: Security & Limits
MAX_FILE_SIZE=52428800
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW=60
```

**Generate Secret Key:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Step 4: Run the Application

### Option A: Direct Python (Recommended for Testing)

```bash
# Make sure you're in the project root directory
cd /path/to/DOCSsite

# Activate virtual environment (if not already active)
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac

# Run the app
python src/app.py
```

You should see:
```
+==============================================================+
|           DOCS TO MARKDOWN - AUTOMATION PLATFORM             |
+==============================================================+
|  Features:                                                   |
|  - Batch Processing       - Webhook Integration              |
|  - CLI Automation         - Secure Conversion                |
+--------------------------------------------------------------+
 * Running on http://127.0.0.1:8080
```

### Option B: Using Flask CLI

```bash
export FLASK_APP=src/app.py  # Linux/Mac
set FLASK_APP=src/app.py     # Windows

flask run --host=127.0.0.1 --port=8080 --debug
```

## Step 5: Test the Application

### Open in Browser

Visit: **http://localhost:8080**

### Test Pages

1. **Homepage** (`/`): Landing page with 3-step pipeline
2. **Convert** (`/convert`): Document conversion page
3. **RAG Chat** (`/rag`): Chat interface (requires OPENROUTER_API_KEY)
4. **Compare** (`/compare`): Document comparison
5. **Architecture** (`/architecture`): System architecture docs
6. **Stats** (`/stats`): Analytics dashboard

### Test API Endpoints

#### 1. Convert Document
```bash
curl -X POST http://localhost:8080/api/convert \
  -F "file=@test_document.pdf"
```

#### 2. Chat API (requires OPENROUTER_API_KEY)
```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Google Gemini 2.0 Flash",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

#### 3. Get Stats
```bash
curl http://localhost:8080/api/stats
```

## Testing Without OpenRouter API Key

**Document conversion works without OpenRouter API key!**

- ✅ `/convert` - Works
- ✅ `/compare` - Works
- ✅ `/stats` - Works
- ❌ `/rag` - Chat features disabled (shows error)
- ❌ `/api/chat` - Returns 503 error

## Common Issues

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'src'`

**Solution**: Make sure you're running from the project root:
```bash
cd C:\BOT\MegadocE\DocsSite
python src/app.py
```

### Port Already in Use

**Error**: `Address already in use`

**Solution**: Change port in `src/app.py`:
```python
app.run(debug=True, host="127.0.0.1", port=8081)  # Use different port
```

### Missing Dependencies

**Error**: `ModuleNotFoundError: No module named 'flask'`

**Solution**: Reinstall dependencies:
```bash
pip install -r requirements.txt
```

### OpenRouter API Errors

**Error**: `OpenRouter API not configured`

**Solution**: Either:
1. Set `OPENROUTER_API_KEY` in `.env` file
2. Or skip testing chat features (conversion still works)

## Quick Test Checklist

- [ ] Application starts without errors
- [ ] Homepage loads at http://localhost:8080
- [ ] Can upload a test PDF on `/convert`
- [ ] Conversion returns markdown content
- [ ] Stats page shows metrics
- [ ] Compare page loads (upload two files to test)

## Testing with Docker (Alternative)

If you prefer Docker:

```bash
# Build image
docker build -t megadoc:test .

# Run container
docker run -p 8080:8080 \
  -e SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") \
  -e OPENROUTER_API_KEY=your_key_here \
  megadoc:test
```

## Next Steps

- Read [README.md](README.md) for full documentation
- Check [docs/deployment.md](docs/deployment.md) for production deployment
- Review [docs/api.md](docs/api.md) for API reference

