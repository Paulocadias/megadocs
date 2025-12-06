"""
Mock OpenRouter API Gateway for testing.

This module provides mock responses for the OpenRouter API,
allowing tests to run without making actual API calls.
"""
import json
import time
from typing import Dict, List, Optional, Any
from unittest.mock import MagicMock


# ============================================================================
# Mock Response Data
# ============================================================================

MOCK_MODELS = {
    "google/gemini-2.0-flash-exp:free": {
        "name": "Google Gemini 2.0 Flash",
        "latency_ms": 150,
        "cost_per_1k_tokens": 0.0001,
    },
    "deepseek/deepseek-chat:free": {
        "name": "DeepSeek V3",
        "latency_ms": 200,
        "cost_per_1k_tokens": 0.0002,
    },
    "meta-llama/llama-3.2-3b-instruct:free": {
        "name": "Llama 3.2 3B",
        "latency_ms": 100,
        "cost_per_1k_tokens": 0.00005,
    },
}

DOMAIN_RESPONSES = {
    "general": "I'm a helpful assistant. Based on the provided context: ",
    "legal": "LEGAL ANALYSIS: Based on the document provided, the following legal considerations apply: ",
    "medical": "MEDICAL ASSESSMENT: The clinical information indicates: ",
    "technical": "TECHNICAL SPECIFICATION: The system documentation shows: ",
}


# ============================================================================
# Mock Response Generators
# ============================================================================

def mock_chat_response(
    model: str = "google/gemini-2.0-flash-exp:free",
    domain: str = "general",
    context: str = "",
    user_message: str = ""
) -> Dict[str, Any]:
    """Generate a mock chat completion response."""

    model_info = MOCK_MODELS.get(model, MOCK_MODELS["google/gemini-2.0-flash-exp:free"])
    domain_prefix = DOMAIN_RESPONSES.get(domain, DOMAIN_RESPONSES["general"])

    # Generate contextual response
    if context:
        response_content = f"{domain_prefix}The document discusses important topics. "
        response_content += f"In response to your question about '{user_message[:50]}...': "
        response_content += "This is a mocked response for testing purposes."
    else:
        response_content = f"{domain_prefix}This is a test response without document context."

    return {
        "id": f"chatcmpl-test-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response_content
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": len(context.split()) + len(user_message.split()),
            "completion_tokens": len(response_content.split()),
            "total_tokens": len(context.split()) + len(user_message.split()) + len(response_content.split())
        }
    }


def mock_rate_limit_response() -> Dict[str, Any]:
    """Generate a mock rate limit (429) response."""
    return {
        "error": {
            "message": "Rate limit exceeded. Please retry after 60 seconds.",
            "type": "rate_limit_error",
            "code": 429
        }
    }


def mock_server_error_response() -> Dict[str, Any]:
    """Generate a mock server error (500) response."""
    return {
        "error": {
            "message": "Internal server error. Please try again later.",
            "type": "server_error",
            "code": 500
        }
    }


def mock_vision_response(image_description: str = "A document image") -> Dict[str, Any]:
    """Generate a mock vision API response for image analysis."""
    return {
        "id": f"chatcmpl-vision-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "google/gemini-2.0-flash-exp:free",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": f"Image Analysis: {image_description}. The image appears to contain text and visual elements suitable for document processing."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 30,
            "total_tokens": 80
        }
    }


# ============================================================================
# Mock Gateway Class
# ============================================================================

class MockOpenRouterGateway:
    """
    Mock implementation of the OpenRouter Gateway for testing.

    Usage:
        gateway = MockOpenRouterGateway()
        response = gateway.chat(model="google/gemini-2.0-flash-exp:free", messages=[...])
    """

    def __init__(
        self,
        should_fail: bool = False,
        should_rate_limit: bool = False,
        latency_ms: int = 0
    ):
        self.should_fail = should_fail
        self.should_rate_limit = should_rate_limit
        self.latency_ms = latency_ms
        self.call_count = 0
        self.last_request = None

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        context: str = "",
        domain: str = "general",
        **kwargs
    ) -> Dict[str, Any]:
        """Mock chat completion."""
        self.call_count += 1
        self.last_request = {
            "model": model,
            "messages": messages,
            "context": context,
            "domain": domain,
            **kwargs
        }

        # Simulate latency
        if self.latency_ms > 0:
            time.sleep(self.latency_ms / 1000)

        # Return error responses if configured
        if self.should_rate_limit:
            return {"success": False, "error": mock_rate_limit_response()["error"]}

        if self.should_fail:
            return {"success": False, "error": mock_server_error_response()["error"]}

        # Get user message from messages
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        response = mock_chat_response(
            model=model,
            domain=domain,
            context=context,
            user_message=user_message
        )

        return {
            "success": True,
            "response": response["choices"][0]["message"]["content"],
            "model": model,
            "latency_ms": self.latency_ms or MOCK_MODELS.get(model, {}).get("latency_ms", 100),
            "cost": response["usage"]["total_tokens"] * 0.00001,
            "usage": response["usage"]
        }

    def analyze_image(self, image_data: bytes, prompt: str = "") -> Dict[str, Any]:
        """Mock image analysis."""
        self.call_count += 1

        if self.should_fail:
            return {"success": False, "error": "Image analysis failed"}

        response = mock_vision_response()
        return {
            "success": True,
            "description": response["choices"][0]["message"]["content"],
            "model": "google/gemini-2.0-flash-exp:free"
        }

    def get_available_models(self) -> List[Dict[str, str]]:
        """Return list of available models."""
        return [
            {"id": model_id, **info}
            for model_id, info in MOCK_MODELS.items()
        ]

    def reset(self):
        """Reset mock state."""
        self.call_count = 0
        self.last_request = None
        self.should_fail = False
        self.should_rate_limit = False


# ============================================================================
# Pytest Fixture Helper
# ============================================================================

def create_mock_openrouter_fixture(mocker, **kwargs):
    """
    Helper function to create a mock OpenRouter fixture.

    Usage in conftest.py:
        @pytest.fixture
        def mock_openrouter(mocker):
            return create_mock_openrouter_fixture(mocker)
    """
    gateway = MockOpenRouterGateway(**kwargs)
    mocker.patch('openrouter_gateway.OpenRouterGateway', return_value=gateway)
    return gateway
