"""
MegaDoc Assistant - RAG-based chatbot with live stats access
Uses OpenRouter free models with strict context-only responses
"""

import os
import json
import sqlite3
from pathlib import Path
from typing import Optional
import requests

# OpenRouter config
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Free/fast models on OpenRouter
FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemma-2-9b-it:free",
    "qwen/qwen-2-7b-instruct:free",
]

SYSTEM_PROMPT = """You are the MegaDoc Assistant, a helpful AI that answers questions about the MegaDoc document conversion platform.

CRITICAL: For questions about statistics, conversions, or numbers - ALWAYS check the LIVE PLATFORM STATISTICS section first and report those exact numbers.

RULES:
1. For statistics questions: Use the EXACT numbers from LIVE PLATFORM STATISTICS section
2. For feature questions: Use the KNOWLEDGE BASE documentation
3. If you can't find the answer, say "I don't have that information"
4. Be concise and direct
5. NEVER make up numbers - only use what's provided

You have access to:
- LIVE PLATFORM STATISTICS: Real-time data about document conversions
- KNOWLEDGE BASE: Documentation about MegaDoc features, API, architecture
"""

def get_live_stats() -> dict:
    """Get live statistics from the database"""
    db_path = Path(__file__).parent.parent / "data" / "stats.db"

    if not db_path.exists():
        return {"error": "Database not available"}

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        stats = {}

        # Total conversions (all are successful since they're recorded on completion)
        cursor.execute("SELECT COUNT(*) FROM conversions")
        stats["total_conversions"] = cursor.fetchone()[0]
        stats["successful_conversions"] = stats["total_conversions"]
        stats["failed_conversions"] = 0  # Failures aren't logged in this schema

        # File types
        cursor.execute("""
            SELECT file_type, COUNT(*) as count
            FROM conversions
            GROUP BY file_type
            ORDER BY count DESC
            LIMIT 5
        """)
        stats["top_file_types"] = [{"type": row[0], "count": row[1]} for row in cursor.fetchall()]

        # Today's conversions
        cursor.execute("""
            SELECT COUNT(*) FROM conversions
            WHERE date(created_at) = date('now')
        """)
        stats["today_conversions"] = cursor.fetchone()[0]

        # Total file size processed
        cursor.execute("SELECT SUM(file_size) FROM conversions")
        total_size = cursor.fetchone()[0] or 0
        stats["total_bytes_processed"] = total_size
        stats["total_mb_processed"] = round(total_size / (1024 * 1024), 2) if total_size else 0

        # Average file size
        cursor.execute("SELECT AVG(file_size) FROM conversions WHERE file_size > 0")
        avg_size = cursor.fetchone()[0]
        stats["avg_file_size_kb"] = round(avg_size / 1024, 2) if avg_size else 0

        # Success rate (100% since only successful conversions are logged)
        stats["success_rate"] = 100.0 if stats["total_conversions"] > 0 else 0

        conn.close()
        return stats

    except Exception as e:
        return {"error": str(e)}

def load_docs_context() -> str:
    """Load key documentation as context"""
    docs_dir = Path(__file__).parent.parent / "docs"
    readme = Path(__file__).parent.parent / "README.md"

    context_parts = []

    # Load README (most important)
    if readme.exists():
        with open(readme, 'r', encoding='utf-8') as f:
            content = f.read()[:4000]  # Limit size
            context_parts.append(f"## README\n{content}")

    # Load key docs
    key_docs = ["api.md", "architecture.md", "security.md"]
    for doc in key_docs:
        doc_path = docs_dir / doc
        if doc_path.exists():
            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()[:2000]  # Limit per doc
                context_parts.append(f"## {doc}\n{content}")

    return "\n\n".join(context_parts)

def is_stats_question(question: str) -> bool:
    """Check if question is about statistics"""
    stats_keywords = [
        "stats", "statistics", "how many", "documents processed",
        "conversions", "converted", "success rate", "failed",
        "processing time", "file types", "today", "total",
        "numbers", "metrics", "count", "average"
    ]
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in stats_keywords)

# Common questions with pre-defined answers (fallback when LLM unavailable)
COMMON_QUESTIONS = {
    "what is megadoc": """MegaDoc is a multi-modal AI document conversion platform that transforms various document formats into clean, AI-ready Markdown.

**Key Features:**
- Convert PDF, DOCX, HTML, images, and more to Markdown
- Optimized for RAG (Retrieval-Augmented Generation) pipelines
- Multi-model AI gateway for intelligent processing
- Real-time statistics and analytics
- Secure, ephemeral session storage (no data persistence)

Visit the main page to try it out!""",

    "api": """MegaDoc provides a REST API for document conversion:

**Endpoint:** POST /api/convert
**Supported formats:** PDF, DOCX, HTML, TXT, images (PNG, JPG)

**Example:**
```
curl -X POST /api/convert -F "file=@document.pdf"
```

Check /api/docs for full API documentation.""",

    "file types": """MegaDoc supports these file formats:

**Documents:** PDF, DOCX, DOC, ODT, RTF
**Web:** HTML, HTM
**Text:** TXT, MD, CSV
**Images:** PNG, JPG, JPEG, GIF, WEBP
**Other:** JSON, XML

All converted to clean Markdown for AI applications.""",

    "rag": """MegaDoc is optimized for RAG (Retrieval-Augmented Generation) pipelines:

1. **Document Chunking** - Smart text segmentation
2. **Embeddings** - Vector generation for semantic search
3. **Clean Output** - AI-ready Markdown format
4. **Metadata** - Source tracking and context preservation

Perfect for building knowledge bases and AI assistants!""",
}

def get_common_answer(question: str) -> Optional[str]:
    """Check if question matches common questions"""
    question_lower = question.lower()
    for key, answer in COMMON_QUESTIONS.items():
        if key in question_lower:
            return answer
    return None

def format_stats_response(stats: dict) -> str:
    """Format stats into a friendly response"""
    if "error" in stats:
        return f"Sorry, I couldn't retrieve the statistics: {stats['error']}"

    # Build file types string
    file_types_str = ""
    if stats.get("top_file_types"):
        types = [f"{ft['type']} ({ft['count']})" for ft in stats["top_file_types"]]
        file_types_str = ", ".join(types)

    return f"""Here are the live MegaDoc platform statistics:

**Total Documents Processed:** {stats.get('total_conversions', 0):,}
**Today's Conversions:** {stats.get('today_conversions', 0):,}
**Success Rate:** {stats.get('success_rate', 0)}%
**Total Data Processed:** {stats.get('total_mb_processed', 0)} MB
**Average File Size:** {stats.get('avg_file_size_kb', 0)} KB
**Top File Types:** {file_types_str or 'No data yet'}

These are real-time statistics from our database!"""

def ask_assistant(question: str, model: Optional[str] = None) -> dict:
    """
    Ask the MegaDoc Assistant a question

    Args:
        question: User's question
        model: Optional model override (defaults to free model)

    Returns:
        dict with answer or error
    """
    # Get live stats first (needed for stats questions OR context)
    live_stats = get_live_stats()

    # For stats questions, return stats directly without LLM
    if is_stats_question(question):
        return {
            "answer": format_stats_response(live_stats),
            "model": "direct-stats",
            "stats_included": True,
            "tokens_used": {}
        }

    # Check for common questions (fast, no LLM needed)
    common_answer = get_common_answer(question)
    if common_answer:
        return {
            "answer": common_answer,
            "model": "knowledge-base",
            "stats_included": False,
            "tokens_used": {}
        }

    if not OPENROUTER_API_KEY:
        return {"error": "OpenRouter API key not configured"}
    stats_context = f"""
## LIVE PLATFORM STATISTICS (Real-time data)
- Total documents processed: {live_stats.get('total_conversions', 'N/A')}
- Successful conversions: {live_stats.get('successful_conversions', 'N/A')}
- Failed conversions: {live_stats.get('failed_conversions', 'N/A')}
- Success rate: {live_stats.get('success_rate', 'N/A')}%
- Today's conversions: {live_stats.get('today_conversions', 'N/A')}
- Average processing time: {live_stats.get('avg_processing_time_ms', 'N/A')}ms
- Top file types: {json.dumps(live_stats.get('top_file_types', []))}
"""

    # Load documentation context
    docs_context = load_docs_context()

    # Build full context (LIVE STATS first for better visibility)
    full_context = f"""
{SYSTEM_PROMPT}

=== LIVE PLATFORM STATISTICS (READ THIS FIRST FOR STATS QUESTIONS) ===
{stats_context}

=== KNOWLEDGE BASE ===
{docs_context}
"""

    # Select model
    selected_model = model if model else FREE_MODELS[0]

    # Call OpenRouter
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "https://megadocs.paulocadias.com"),
    }

    payload = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": full_context},
            {"role": "user", "content": question}
        ],
        "max_tokens": 500,
        "temperature": 0.3,  # Lower temperature for factual responses
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        return {
            "answer": answer,
            "model": selected_model,
            "stats_included": True,
            "tokens_used": data.get("usage", {})
        }

    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"API error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

# CLI interface for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "How many documents have been processed?"

    print(f"Question: {question}\n")
    result = ask_assistant(question)

    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Answer: {result['answer']}")
        print(f"\nModel: {result['model']}")
