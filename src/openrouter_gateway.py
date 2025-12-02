"""
OpenRouter Model Gateway for unified LLM inference.
Implements vendor-agnostic gateway pattern for hot-swapping between providers.
"""

import os
import time
import logging
import requests
from typing import Dict, Any, Optional, List
from config import Config

logger = logging.getLogger(__name__)

# Model mapping: UI names to OpenRouter model IDs (free tier models - updated Dec 2025)
# With $10+ credits: 1000 req/day on free models, no limits on paid models
MODEL_MAP = {
    "Google Gemini 2.5 Pro": "google/gemini-2.5-pro-exp-03-25:free",  # Most powerful free model
    "Google Gemini 2.0 Flash": "google/gemini-2.0-flash-exp:free",    # Fast, good for chat
    "DeepSeek V3": "deepseek/deepseek-chat-v3-0324:free",             # Excellent for coding
    "DeepSeek R1": "deepseek/deepseek-r1:free",                       # Strong reasoning
    "Meta Llama 3.3 70B": "meta-llama/llama-3.3-70b-instruct:free",   # Large, capable
    "Qwen QwQ 32B": "qwen/qwq-32b:free"                               # Good reasoning model
}

# Domain-based system prompts for dynamic context injection
DOMAIN_PROMPTS = {
    "general": """You are a RAG (Retrieval-Augmented Generation) assistant. Your responses must:
- Answer ONLY based on the provided context documents
- If information is not in the context, clearly state "I cannot find this information in the provided documents"
- NEVER make up, invent, or speculate beyond what is explicitly written in the context
- When answering, reference which document the information comes from
- Be clear, concise, and factual
- If asked about something partially covered, answer only what the documents support and note what is missing""",
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
        system_message = f"{domain_prompt}\n\nContext:\n{context}"
    
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
        "HTTP-Referer": Config.OPENROUTER_HTTP_REFERER or "https://megadocs.paulocadias.com",
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
                "error": "Queue Full",
                "retry_after": retry_after,
                "latency_ms": latency_ms
            }
        
        # Handle other errors
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        
        # Extract content and metadata
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        
        # Extract usage/cost info if available
        usage = data.get("usage", {})
        cost = 0.0  # OpenRouter may provide cost in response
        
        return {
            "response": content,
            "latency_ms": latency_ms,
            "cost": cost,
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
    
    # Prepare request payload
    payload = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + messages
    }
    
    # Prepare headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": Config.OPENROUTER_HTTP_REFERER or "https://megadocs.paulocadias.com",
        "X-Title": "MegaDoc Portfolio"
    }
    
    try:
        response = requests.post(
            Config.OPENROUTER_API_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        # Handle rate limiting (429)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "3"))
            logger.warning(f"OpenRouter rate limit hit for image description. Retry after {retry_after}s")
            raise requests.exceptions.HTTPError(f"Rate limit: retry after {retry_after}s", response=response)
        
        # Handle other errors
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        
        # Extract content
        choice = data.get("choices", [{}])[0]
        description = choice.get("message", {}).get("content", "")
        
        if not description:
            raise ValueError("Empty description returned from vision model")
        
        return description
        
    except requests.exceptions.Timeout:
        logger.error("OpenRouter image description request timeout")
        raise requests.exceptions.RequestException("Request timeout")
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenRouter image description request failed: {e}")
        raise


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
    
    # Prepare request payload
    payload = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + messages
    }
    
    # Prepare headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": Config.OPENROUTER_HTTP_REFERER or "https://megadocs.paulocadias.com",
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
            logger.warning(f"OpenRouter rate limit hit for vision. Retry after {retry_after}s")
            return {
                "error": "Queue Full",
                "retry_after": retry_after,
                "latency_ms": latency_ms
            }
        
        # Handle other errors
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        
        # Extract content
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        
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
            "model": "google/gemini-2.0-flash-exp:free"
        }
        
    except requests.exceptions.Timeout:
        logger.error("OpenRouter vision request timeout")
        raise requests.exceptions.RequestException("Request timeout")
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenRouter vision request failed: {e}")
        raise

