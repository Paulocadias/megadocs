"""
OpenRouter Model Gateway for unified LLM inference.
Implements vendor-agnostic gateway pattern for hot-swapping between providers.

v3.0 Features:
- Dynamic pricing from OpenRouter API
- Cost calculation per request
- Savings tracking vs GPT-4 baseline
"""

import os
import time
import logging
import requests
from typing import Dict, Any, Optional, List
from config import Config

logger = logging.getLogger(__name__)

# ============================================================================
# PRICING SYSTEM (v3.0) - Cost tracking for CFO Hook
# ============================================================================

# Cache for model pricing (refreshed every hour)
_pricing_cache: Dict[str, Dict[str, float]] = {}
_pricing_cache_timestamp: float = 0
PRICING_CACHE_TTL = 3600  # 1 hour

# GPT-4 baseline for savings calculation (per 1M tokens)
# Source: OpenRouter pricing for gpt-4-turbo
GPT4_BASELINE_PRICING = {
    "prompt": 10.0,      # $10 per 1M input tokens
    "completion": 30.0   # $30 per 1M output tokens
}


def fetch_model_pricing() -> Dict[str, Dict[str, float]]:
    """
    Fetch current model pricing from OpenRouter API.

    Returns:
        Dictionary mapping model_id to pricing info:
        {
            "google/gemini-2.0-flash-001": {
                "prompt": 0.10,      # $ per 1M input tokens
                "completion": 0.40   # $ per 1M output tokens
            }
        }

    Raises:
        requests.RequestException: If API call fails
    """
    global _pricing_cache, _pricing_cache_timestamp

    # Check cache
    current_time = time.time()
    if _pricing_cache and (current_time - _pricing_cache_timestamp) < PRICING_CACHE_TTL:
        return _pricing_cache

    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        pricing_map = {}
        for model in data.get("data", []):
            model_id = model.get("id", "")
            pricing = model.get("pricing", {})

            # Convert string prices to float, multiply by 1M for per-1M-token rates
            prompt_price = float(pricing.get("prompt", "0")) * 1_000_000
            completion_price = float(pricing.get("completion", "0")) * 1_000_000

            pricing_map[model_id] = {
                "prompt": prompt_price,
                "completion": completion_price
            }

        # Update cache
        _pricing_cache = pricing_map
        _pricing_cache_timestamp = current_time
        logger.info(f"Pricing cache updated: {len(pricing_map)} models")

        return pricing_map

    except Exception as e:
        logger.warning(f"Failed to fetch pricing from OpenRouter: {e}")
        # Return cached data if available, else empty
        return _pricing_cache if _pricing_cache else {}


def get_model_pricing(model_id: str) -> Dict[str, float]:
    """
    Get pricing for a specific model.

    Args:
        model_id: OpenRouter model ID (e.g., "google/gemini-2.0-flash-001")

    Returns:
        Dictionary with "prompt" and "completion" prices per 1M tokens
    """
    pricing = fetch_model_pricing()
    return pricing.get(model_id, {"prompt": 0.0, "completion": 0.0})


def calculate_request_cost(
    model_id: str,
    input_tokens: int,
    output_tokens: int
) -> Dict[str, float]:
    """
    Calculate cost for a request based on token usage.

    Args:
        model_id: OpenRouter model ID
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Dictionary with:
        - actual_cost: Cost using the selected model
        - gpt4_cost: What it would have cost with GPT-4
        - savings: Amount saved vs GPT-4
        - savings_percent: Percentage saved vs GPT-4
    """
    pricing = get_model_pricing(model_id)

    # Calculate actual cost (price is per 1M tokens)
    input_cost = (input_tokens / 1_000_000) * pricing.get("prompt", 0.0)
    output_cost = (output_tokens / 1_000_000) * pricing.get("completion", 0.0)
    actual_cost = input_cost + output_cost

    # Calculate GPT-4 baseline cost
    gpt4_input_cost = (input_tokens / 1_000_000) * GPT4_BASELINE_PRICING["prompt"]
    gpt4_output_cost = (output_tokens / 1_000_000) * GPT4_BASELINE_PRICING["completion"]
    gpt4_cost = gpt4_input_cost + gpt4_output_cost

    # Calculate savings
    savings = gpt4_cost - actual_cost
    savings_percent = (savings / gpt4_cost * 100) if gpt4_cost > 0 else 0.0

    return {
        "actual_cost": round(actual_cost, 6),
        "gpt4_cost": round(gpt4_cost, 6),
        "savings": round(savings, 6),
        "savings_percent": round(savings_percent, 2)
    }


# ============================================================================
# MODEL CONFIGURATION
# ============================================================================

# Model mapping: UI names to OpenRouter model IDs
# PAID models (no :free suffix) = NO rate limits with credits
# FREE models (:free suffix) = 20 req/min, limited daily quota
# Source: https://openrouter.ai/docs/api/reference/limits
MODEL_MAP = {
    # PAID models - use these with credits ($17+ in account)
    "Google Gemini 2.0 Flash": "google/gemini-2.0-flash-001",         # $0.10/1M - Fast, reliable
    "DeepSeek V3": "deepseek/deepseek-chat",                          # $0.14/1M - Best value
    "DeepSeek R1": "deepseek/deepseek-r1",                            # $0.55/1M - Strong reasoning
    "Meta Llama 3.3 70B": "meta-llama/llama-3.3-70b-instruct",        # $0.10/1M - Good balance
    "Mistral Small": "mistralai/mistral-small-24b-instruct-2501",     # $0.10/1M - Fast
    # FREE models (rate limited) - fallback only
    "Google Gemini Flash (Free)": "google/gemini-2.0-flash-exp:free", # Free but rate limited
    "DeepSeek (Free)": "deepseek/deepseek-chat-v3-0324:free",         # Free but rate limited
}

# Fallback order when primary model fails
# Paid models first (no rate limits), then free as last resort
FALLBACK_ORDER = [
    "DeepSeek V3",                  # Best value, reliable
    "Google Gemini 2.0 Flash",      # Fast, cheap
    "Meta Llama 3.3 70B",           # Good alternative
    "Mistral Small",                # Fast fallback
    "DeepSeek R1",                  # Strong reasoning
    "Google Gemini Flash (Free)",   # Free fallback (rate limited)
    "DeepSeek (Free)",              # Free fallback (rate limited)
]

# Domain-based system prompts for dynamic context injection
DOMAIN_PROMPTS = {
    "general": """You are a RAG (Retrieval-Augmented Generation) assistant analyzing document content provided below.

CRITICAL RULES - YOU MUST FOLLOW THESE:
1. You can ONLY answer questions using information from the CONTEXT section below
2. If the answer is NOT in the context, respond EXACTLY: "I cannot find this information in the provided documents."
3. NEVER use your training knowledge - only the context provided
4. NEVER make up, invent, hallucinate, or speculate beyond what is explicitly written in the context
5. If partially covered, answer only what the documents support and clearly note what is missing
6. Always reference which document the information comes from when answering

Your entire knowledge for this conversation is LIMITED to the content below. Anything not in the CONTEXT does not exist for you.""",
    "legal": """You are a Legal AI Assistant. Your responses must:
- Cite sources explicitly. Always reference the specific document section or clause.
- Do not interpret beyond what is explicitly stated in the context.
- Zero hallucination tolerance. If information is not in the context, state "Not found in provided documents."
- Use precise legal terminology.
- Flag any potential compliance risks or ambiguities.""",
    "medical": """You are a Clinical AI Assistant. Your responses must:
- Use standard medical terminology (SNOMED CT, ICD-10 where applicable).
- Prioritize patient safety guidelines and evidence-based practices.
- Never provide definitive diagnoses - only support diagnostic processes.
- Flag urgent safety concerns immediately.
- Maintain HIPAA compliance in all responses.
- When uncertain, recommend consulting with a licensed healthcare provider.""",
    "technical": """You are a Technical Engineering AI Assistant. Your responses must:
- Focus on specifications, error codes, and procedural steps.
- Provide exact part numbers, model numbers, and technical parameters when available.
- Prioritize accuracy over creativity.
- Use technical diagrams and schematics when referenced.
- Flag potential safety hazards or operational risks.
- Provide step-by-step troubleshooting procedures when applicable."""
}

# Default system prompt (general domain)
SYSTEM_PROMPT = DOMAIN_PROMPTS["general"]


def get_domain_prompt(domain: str = "general") -> str:
    """
    Get system prompt for specified domain.
    
    Args:
        domain: Domain identifier (general, legal, medical, technical)
        
    Returns:
        Domain-specific system prompt
    """
    return DOMAIN_PROMPTS.get(domain.lower(), DOMAIN_PROMPTS["general"])


def get_model_id(ui_model_name: str) -> str:
    """
    Map UI model name to OpenRouter model ID.
    
    Args:
        ui_model_name: User-friendly model name from UI
        
    Returns:
        OpenRouter model ID
    """
    return MODEL_MAP.get(ui_model_name, MODEL_MAP["Google Gemini 2.0 Flash"])


def chat_completion(
    model: str,
    messages: List[Dict[str, str]],
    context: Optional[str] = None,
    domain: str = "general"
) -> Dict[str, Any]:
    """
    Send chat completion request to OpenRouter with domain-specific prompting.
    
    Args:
        model: UI model name (e.g., "Google Gemini 2.0 Flash")
        messages: List of message dicts with "role" and "content"
        context: Optional context text to include in system message
        domain: Domain identifier (general, legal, medical, technical) for dynamic prompt injection
        
    Returns:
        Dictionary with response, latency_ms, cost, and model info
        
    Raises:
        ValueError: If API key is missing
        requests.HTTPError: For HTTP errors (429, 500, etc.)
    """
    api_key = Config.OPENROUTER_API_KEY
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not configured")
    
    # Map UI model name to OpenRouter ID
    model_id = get_model_id(model)
    
    # Get domain-specific system prompt (ADR-005: Domain Injection Pattern)
    domain_prompt = get_domain_prompt(domain)
    
    # Build messages with domain-specific system prompt
    system_message = domain_prompt
    if context:
        # Use clear markers to delineate context boundaries
        system_message = f"""{domain_prompt}

=== DOCUMENT CONTEXT START ===
{context}
=== DOCUMENT CONTEXT END ===

Remember: You can ONLY answer based on the content between the CONTEXT markers above. If the information is not there, say so."""
    
    # Prepare request payload
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_message}
        ] + messages
    }
    
    # Prepare headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": Config.OPENROUTER_HTTP_REFERER or "https://megadoc.paulocadias.com",
        "X-Title": "MegaDoc Portfolio"
    }
    
    # Track latency
    start_time = time.time()
    
    try:
        response = requests.post(
            Config.OPENROUTER_API_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Handle rate limiting (429)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "3"))
            logger.warning(f"OpenRouter rate limit hit. Retry after {retry_after}s")
            return {
                "error": "Rate Limited",
                "error_type": "rate_limit",
                "retry_after": retry_after,
                "latency_ms": latency_ms,
                "retryable": True
            }

        # Handle 404 (model not found/unavailable)
        if response.status_code == 404:
            logger.warning(f"OpenRouter model not found or unavailable: {model_id}")
            return {
                "error": "Model Unavailable",
                "error_type": "model_unavailable",
                "latency_ms": latency_ms,
                "retryable": True
            }

        # Handle server errors (5xx)
        if response.status_code >= 500:
            logger.warning(f"OpenRouter server error: {response.status_code}")
            return {
                "error": f"Server Error ({response.status_code})",
                "error_type": "server_error",
                "latency_ms": latency_ms,
                "retryable": True
            }

        # Handle other client errors (4xx)
        if response.status_code >= 400:
            error_detail = response.json().get("error", {}).get("message", response.text[:200])
            logger.error(f"OpenRouter client error {response.status_code}: {error_detail}")
            return {
                "error": f"API Error: {error_detail}",
                "error_type": "client_error",
                "latency_ms": latency_ms,
                "retryable": False
            }
        
        # Parse response
        data = response.json()

        # Extract content and metadata
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")

        # Extract usage/cost info if available
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # Calculate cost and savings (v3.0)
        cost_info = calculate_request_cost(model_id, input_tokens, output_tokens)

        # Log savings for visibility
        if cost_info["savings"] > 0:
            logger.info(
                f"Cost tracking: Model={model}, Cost=${cost_info['actual_cost']:.6f}, "
                f"Savings vs GPT-4=${cost_info['savings']:.6f} ({cost_info['savings_percent']:.1f}%)"
            )

        return {
            "response": content,
            "latency_ms": latency_ms,
            "cost": cost_info["actual_cost"],
            "gpt4_cost": cost_info["gpt4_cost"],
            "savings": cost_info["savings"],
            "savings_percent": cost_info["savings_percent"],
            "model": model,
            "model_id": model_id,
            "usage": usage
        }
        
    except requests.exceptions.Timeout:
        logger.error("OpenRouter request timeout")
        raise requests.exceptions.RequestException("Request timeout")
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenRouter request failed: {e}")
        raise


def chat_completion_with_fallback(
    model: str,
    messages: List[Dict[str, str]],
    context: Optional[str] = None,
    domain: str = "general",
    max_fallbacks: int = 5
) -> Dict[str, Any]:
    """
    Chat completion with automatic fallback on retryable errors.

    Tries the requested model first, then falls back to alternative models
    if the error is retryable (rate limit, model unavailable, server errors).

    Args:
        model: Primary UI model name
        messages: List of message dicts
        context: Optional context text
        domain: Domain identifier
        max_fallbacks: Maximum number of fallback attempts (default 5 for better resilience)

    Returns:
        Dictionary with response and metadata, includes 'fallback_used' if applicable
    """
    # Try primary model first
    try:
        result = chat_completion(model=model, messages=messages, context=context, domain=domain)
    except requests.exceptions.RequestException as e:
        logger.error(f"Primary model {model} request failed: {e}")
        result = {"error": str(e), "retryable": True}

    # Check if we should try fallbacks
    is_retryable = result.get("retryable", False)
    has_error = "error" in result

    # If success or non-retryable error, return immediately
    if not has_error or not is_retryable:
        return result

    # Retryable error - try fallback models
    error_type = result.get("error_type", "unknown")
    logger.warning(f"Primary model {model} failed ({error_type}), trying fallbacks...")

    # Build fallback list, excluding the primary model
    fallbacks = [m for m in FALLBACK_ORDER if m != model][:max_fallbacks]
    models_tried = [model]

    for i, fallback_model in enumerate(fallbacks):
        logger.info(f"Fallback attempt {i+1}/{len(fallbacks)}: {fallback_model}")
        models_tried.append(fallback_model)

        # Small delay between attempts (longer for server errors)
        delay = 1.0 if error_type == "server_error" else 0.5
        time.sleep(delay)

        try:
            result = chat_completion(
                model=fallback_model,
                messages=messages,
                context=context,
                domain=domain
            )
        except requests.exceptions.RequestException as e:
            logger.warning(f"Fallback {fallback_model} request failed: {e}")
            continue

        # Check if this fallback succeeded
        if "error" not in result:
            # Success with fallback!
            result["fallback_used"] = True
            result["original_model"] = model
            result["fallback_model"] = fallback_model
            result["models_tried"] = models_tried
            logger.info(f"Fallback successful with {fallback_model}")
            return result

        # Check if this error is also retryable
        if not result.get("retryable", False):
            # Non-retryable error, stop trying
            logger.error(f"Fallback {fallback_model} returned non-retryable error: {result.get('error')}")
            result["models_tried"] = models_tried
            return result

        logger.warning(f"Fallback {fallback_model} also failed: {result.get('error')}")

    # All fallbacks exhausted
    logger.error(f"All {len(models_tried)} models exhausted")
    return {
        "error": "All Models Unavailable",
        "error_type": "all_failed",
        "message": "All available models are currently unavailable. Please try again in a few minutes.",
        "retry_after": 60,
        "models_tried": models_tried,
        "retryable": False
    }


def image_to_text_description(
    image_base64: str
) -> str:
    """
    Convert image to detailed text description for RAG indexing.
    
    This function takes an image and generates a comprehensive technical description
    that can be indexed and searched just like text documents. This enables
    multi-modal RAG where images and text are treated uniformly.
    
    Args:
        image_base64: Base64-encoded image data (with data URI prefix)
        
    Returns:
        Detailed text description of the image
        
    Raises:
        ValueError: If API key is missing
        requests.HTTPError: For HTTP errors (429, 500, etc.)
    """
    api_key = Config.OPENROUTER_API_KEY
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not configured")
    
    # System prompt for detailed technical description
    system_prompt = """You are an Industrial Documentation AI. Describe this image in extreme technical detail for use in a RAG (Retrieval-Augmented Generation) system.

Your description will be used to:
1. Index the image for semantic search
2. Answer questions about the image content
3. Match queries to relevant visual information

Include in your description:
- All visible text labels, numbers, and codes
- Equipment condition and visible defects
- Safety warnings or hazard indicators
- Component types and their states
- Any technical specifications visible
- Environmental context

Write in clear, searchable prose. Be comprehensive and precise."""
    
    # Build messages with image
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Describe this industrial image in extreme technical detail. Include all visible text, equipment condition, defects, safety warnings, and technical specifications. This description will be used for RAG retrieval."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_base64
                    }
                }
            ]
        }
    ]
    
    # Prepare headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": Config.OPENROUTER_HTTP_REFERER or "https://megadoc.paulocadias.com",
        "X-Title": "MegaDoc Portfolio"
    }

    # Model fallback chain: paid first, then free
    models_to_try = [
        "google/gemini-2.0-flash-001",       # Paid - no rate limits
        "google/gemini-2.0-flash-exp:free",  # Free fallback
    ]

    last_error = None
    for model in models_to_try:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt}
            ] + messages
        }

        try:
            response = requests.post(
                Config.OPENROUTER_API_URL,
                json=payload,
                headers=headers,
                timeout=30
            )

            # Handle rate limiting (429) - try next model
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "3"))
                logger.warning(f"Rate limit hit for {model}, trying fallback...")
                last_error = requests.exceptions.HTTPError(f"Rate limit: retry after {retry_after}s", response=response)
                continue  # Try next model

            # Handle other errors
            response.raise_for_status()

            # Parse response
            data = response.json()

            # Extract content
            choice = data.get("choices", [{}])[0]
            description = choice.get("message", {}).get("content", "")

            if not description:
                logger.warning(f"Empty response from {model}, trying fallback...")
                continue  # Try next model

            logger.info(f"Image description generated using {model}")
            return description

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout for {model}, trying fallback...")
            last_error = requests.exceptions.RequestException("Request timeout")
            continue  # Try next model
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed for {model}: {e}, trying fallback...")
            last_error = e
            continue  # Try next model

    # All models failed
    logger.error(f"All vision models failed: {last_error}")
    raise last_error or requests.exceptions.RequestException("All vision models exhausted")


def analyze_image(
    image_base64: str,
    context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze image for industrial defects using Gemini Vision.
    
    Args:
        image_base64: Base64-encoded image data (with data URI prefix)
        context: Optional equipment context (e.g., "Packaging Line A")
        
    Returns:
        Dictionary with analysis result, latency_ms, and metadata
        
    Raises:
        ValueError: If API key is missing
        requests.HTTPError: For HTTP errors (429, 500, etc.)
    """
    api_key = Config.OPENROUTER_API_KEY
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not configured")
    
    # Industrial maintenance system prompt
    system_prompt = """You are an Industrial Maintenance AI Expert. Analyze the image for defects including:
- Rust and corrosion
- Cracks and structural damage
- Leaks (fluid, air, gas)
- Safety hazards (exposed wires, missing guards)
- Wear and tear indicators
- Alignment issues

Output a structured JSON with these exact fields:
{
  "defect_type": "string (e.g., 'Rust', 'Crack', 'Leak', 'Safety Hazard')",
  "severity": "Low|Med|High",
  "recommended_action": "string (specific maintenance action)",
  "safety_risk": "boolean",
  "urgency": "Low|Medium|High",
  "estimated_downtime_hours": "number or null"
}

Be precise and actionable. Focus on safety-critical issues first."""
    
    # Build messages with image
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"Analyze this equipment image{f' from {context}' if context else ''} for defects and safety issues. Provide structured JSON output."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_base64  # OpenRouter accepts data URIs directly
                    }
                }
            ]
        }
    ]
    
    # Prepare headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": Config.OPENROUTER_HTTP_REFERER or "https://megadoc.paulocadias.com",
        "X-Title": "MegaDoc Portfolio"
    }

    # Model fallback chain: paid first, then free
    models_to_try = [
        "google/gemini-2.0-flash-001",       # Paid - no rate limits
        "google/gemini-2.0-flash-exp:free",  # Free fallback
    ]

    # Track latency
    start_time = time.time()
    last_error = None
    used_model = models_to_try[0]

    for model in models_to_try:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt}
            ] + messages
        }

        try:
            response = requests.post(
                Config.OPENROUTER_API_URL,
                json=payload,
                headers=headers,
                timeout=30
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Handle rate limiting (429) - try next model
            if response.status_code == 429:
                logger.warning(f"Rate limit hit for {model}, trying fallback...")
                last_error = {"error": "Queue Full", "retry_after": 3, "latency_ms": latency_ms}
                continue  # Try next model

            # Handle other errors
            response.raise_for_status()

            # Parse response
            data = response.json()

            # Extract content
            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")

            if not content:
                logger.warning(f"Empty response from {model}, trying fallback...")
                continue  # Try next model

            used_model = model
            logger.info(f"Vision analysis using {model}")
            break  # Success - exit loop

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout for {model}, trying fallback...")
            last_error = {"error": "Timeout", "latency_ms": int((time.time() - start_time) * 1000)}
            continue
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed for {model}: {e}, trying fallback...")
            last_error = {"error": str(e), "latency_ms": int((time.time() - start_time) * 1000)}
            continue
    else:
        # All models failed - return last error
        logger.error(f"All vision models failed")
        return last_error or {"error": "All models failed", "latency_ms": int((time.time() - start_time) * 1000)}

    latency_ms = int((time.time() - start_time) * 1000)

    # Try to parse JSON from response
    import json
    import re
    try:
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group(1))
        else:
            # Try to find JSON object directly
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(0))
            else:
                # Fallback: create structured response from text
                analysis = {
                    "defect_type": "Unknown",
                    "severity": "Med",
                    "recommended_action": content[:200],
                    "safety_risk": "safety" in content.lower() or "hazard" in content.lower(),
                    "urgency": "Medium",
                    "estimated_downtime_hours": None
                }
    except (json.JSONDecodeError, AttributeError):
        # Fallback if JSON parsing fails
        analysis = {
            "defect_type": "Analysis Error",
            "severity": "Med",
            "recommended_action": "Manual inspection required",
            "safety_risk": False,
            "urgency": "Low",
            "estimated_downtime_hours": None,
            "raw_response": content[:500]
        }

    return {
        "analysis": analysis,
        "latency_ms": latency_ms,
        "cost": 0.0,
        "model": used_model
    }

