"""
Shared pytest fixtures for MegaDoc test suite.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_config():
    """Test configuration overrides."""
    return {
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key-do-not-use-in-production",
        "MAX_CONTENT_LENGTH": 10 * 1024 * 1024,  # 10MB for tests
        "RATE_LIMIT_REQUESTS": 100,  # Higher limit for tests
        "RATE_LIMIT_WINDOW": 60,
        "ADMIN_PASSWORD": "testadmin",
        "OPENROUTER_API_KEY": "test-api-key",
    }


# ============================================================================
# Application Fixtures
# ============================================================================

@pytest.fixture
def app(test_config):
    """Create Flask application for testing."""
    # Mock heavy ML dependencies before import
    with patch.dict(sys.modules, {
        'sentence_transformers': MagicMock(),
        'tiktoken': MagicMock(),
        'chromadb': MagicMock(),
        'lancedb': MagicMock(),
    }):
        from app import create_app

        application = create_app()
        application.config.update(test_config)

        # Create application context
        with application.app_context():
            yield application


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Flask CLI test runner."""
    return app.test_cli_runner()


@pytest.fixture
def auth_client(client):
    """Authenticated admin client."""
    # Set admin session
    with client.session_transaction() as session:
        session['admin_authenticated'] = True
    return client


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_openrouter(mocker):
    """Mock OpenRouter API responses."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "google/gemini-2.0-flash",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a test response from the mocked OpenRouter API."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }

    return mocker.patch(
        'openrouter_gateway.requests.post',
        return_value=mock_response
    )


@pytest.fixture
def mock_openrouter_rate_limited(mocker):
    """Mock OpenRouter API rate limit response (429)."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.json.return_value = {
        "error": {
            "message": "Rate limit exceeded",
            "type": "rate_limit_error"
        }
    }
    mock_response.headers = {"Retry-After": "60"}

    return mocker.patch(
        'openrouter_gateway.requests.post',
        return_value=mock_response
    )


@pytest.fixture
def mock_openrouter_error(mocker):
    """Mock OpenRouter API error response (500)."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {
        "error": {
            "message": "Internal server error",
            "type": "server_error"
        }
    }

    return mocker.patch(
        'openrouter_gateway.requests.post',
        return_value=mock_response
    )


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def sample_files():
    """Paths to test fixture files."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    return {
        'pdf': fixtures_dir / 'sample.pdf',
        'docx': fixtures_dir / 'sample.docx',
        'txt': fixtures_dir / 'sample.txt',
        'csv': fixtures_dir / 'sample.csv',
        'image': fixtures_dir / 'sample_image.jpg',
        'html': fixtures_dir / 'sample.html',
    }


@pytest.fixture
def sample_text():
    """Sample text content for testing."""
    return """# Sample Document

This is a sample document for testing the MegaDoc conversion pipeline.

## Features

- Document conversion
- RAG pipeline
- Multi-model chat

## Conclusion

This document demonstrates the core functionality.
"""


@pytest.fixture
def sample_chunks():
    """Sample chunked text for RAG testing."""
    return [
        {
            "content": "This is the first chunk of text for testing.",
            "metadata": {"chunk_id": 0, "source": "test"}
        },
        {
            "content": "This is the second chunk with different content.",
            "metadata": {"chunk_id": 1, "source": "test"}
        },
        {
            "content": "Final chunk contains conclusion and summary.",
            "metadata": {"chunk_id": 2, "source": "test"}
        }
    ]


@pytest.fixture
def sample_embeddings():
    """Sample 384-dimensional embeddings for testing."""
    import random
    random.seed(42)
    return [
        [random.uniform(-1, 1) for _ in range(384)]
        for _ in range(3)
    ]


# ============================================================================
# File Upload Fixtures
# ============================================================================

@pytest.fixture
def txt_file_data():
    """Create a text file for upload testing."""
    return (
        b"This is a test document.\n"
        b"It contains multiple lines.\n"
        b"Used for conversion testing.\n"
    )


@pytest.fixture
def html_file_data():
    """Create an HTML file for upload testing."""
    return b"""<!DOCTYPE html>
<html>
<head><title>Test Document</title></head>
<body>
<h1>Test Heading</h1>
<p>This is a test paragraph.</p>
<ul>
<li>Item 1</li>
<li>Item 2</li>
</ul>
</body>
</html>"""


@pytest.fixture
def json_file_data():
    """Create a JSON file for upload testing."""
    return b'{"title": "Test", "content": "This is test content", "items": [1, 2, 3]}'


@pytest.fixture
def oversized_file_data():
    """Create an oversized file for limit testing."""
    # 60MB of data (exceeds 50MB limit)
    return b"x" * (60 * 1024 * 1024)


# ============================================================================
# Utility Functions
# ============================================================================

@pytest.fixture
def create_test_file(tmp_path):
    """Factory fixture to create test files."""
    def _create_file(filename: str, content: bytes) -> Path:
        file_path = tmp_path / filename
        file_path.write_bytes(content)
        return file_path
    return _create_file


# ============================================================================
# Markers Registration
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (no I/O)")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
