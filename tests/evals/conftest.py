"""
Pytest fixtures for safety evaluations.

Provides shared fixtures for eval tests including
evaluator instances, API configuration, and test data.
"""

import os
import pytest
from typing import Generator

# Import after adding src to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "eval: mark test as safety evaluation"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


@pytest.fixture(scope="session")
def eval_base_url() -> str:
    """
    Get the base URL for evaluation tests.

    Priority:
    1. EVAL_BASE_URL environment variable
    2. Default to localhost:8080
    """
    return os.environ.get("EVAL_BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def api_key() -> str:
    """Get OpenRouter API key from environment."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        pytest.skip("OPENROUTER_API_KEY not set")
    return key


@pytest.fixture(scope="module")
def evaluator(eval_base_url):
    """
    Create SafetyEvaluator instance for tests.

    Scoped to module to reuse across test functions.
    """
    from run_safety_evals import SafetyEvaluator
    return SafetyEvaluator(base_url=eval_base_url)


@pytest.fixture
def sample_refusal_response() -> str:
    """Sample response containing refusal keywords for testing."""
    return (
        "I'm sorry, but I cannot assist with that request. "
        "This type of content is inappropriate and potentially harmful. "
        "I'm designed to be helpful while following safety guidelines."
    )


@pytest.fixture
def sample_compliant_response() -> str:
    """Sample response that doesn't contain refusal keywords."""
    return (
        "Based on the provided documents, here is the information you requested. "
        "The technical specifications indicate the following parameters..."
    )


@pytest.fixture(scope="session")
def test_context() -> str:
    """Standard test context for evaluation requests."""
    return (
        "This is a test document for safety evaluation. "
        "It contains general information for testing purposes only. "
        "No sensitive data is included in this evaluation context."
    )
