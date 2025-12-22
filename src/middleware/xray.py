"""
X-Ray Middleware for request tracing and observability.

Provides detailed telemetry for chat requests including:
- Time to First Token (TTFT)
- Total request latency
- Gateway latency
- Token usage (input/output)
- Model information
- Estimated cost

Usage:
    @bp.route("/api/chat", methods=["POST"])
    @security_check
    @xray_trace
    def api_chat():
        ...
        result = chat_completion(...)
        update_xray_from_gateway(result)
        ...

Debug data is injected when:
- Query parameter ?debug=1 is present
- Header X-Debug: 1 is set
"""

import time
import functools
import logging
import json
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass, asdict, field
from flask import request, g, Response

logger = logging.getLogger(__name__)


@dataclass
class XRayTrace:
    """Telemetry data captured by X-Ray middleware."""
    request_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    endpoint: str = ""
    method: str = ""
    ttft_ms: Optional[int] = None
    total_latency_ms: int = 0
    gateway_latency_ms: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    model: str = ""
    model_id: str = ""
    estimated_cost: float = 0.0
    # v3.0: Cost tracking for CFO Hook
    gpt4_cost: float = 0.0
    savings: float = 0.0
    savings_percent: float = 0.0
    domain: str = "general"
    context_length: int = 0
    error: Optional[str] = None
    # v3.1: Agent telemetry
    agent_type: Optional[str] = None
    agent_steps: Optional[list] = None
    agent_step_latencies: Optional[Dict[str, int]] = None
    agent_step_tokens: Optional[Dict[str, Any]] = None
    agent_documents_analyzed: Optional[list] = None
    agent_chunks_retrieved: int = 0
    # v3.2: Vector search telemetry
    vector_results_count: int = 0
    vector_search_empty: bool = False  # Warning flag when no results
    # v3.2: Quality gate metrics (for Investigator Agent)
    quality_score: Optional[float] = None
    quality_threshold: int = 7
    iterations: int = 1
    retried: bool = False
    max_retries: int = 2
    # v3.2: Tool calling metrics
    tools_enabled: bool = False
    tool_calls: Optional[list] = None
    tool_results: Optional[list] = None
    external_context_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary, excluding None values."""
        result = asdict(self)
        return {k: v for k, v in result.items() if v is not None}


def xray_trace(f: Callable) -> Callable:
    """
    Decorator to capture telemetry for request tracing.

    Injects _debug object into JSON response when:
    - Query parameter ?debug=1 is present, OR
    - X-Debug: 1 header is set

    The decorator captures:
    - Total request latency
    - Gateway call latency (via update_xray_from_gateway)
    - Token usage and costs
    - Model information

    For blocking calls (non-streaming), TTFT equals total latency.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Initialize trace in flask.g
        g.xray = XRayTrace(
            request_id=getattr(request, 'request_id', 'UNKNOWN'),
            timestamp=datetime.utcnow().isoformat() + 'Z',
            endpoint=request.path,
            method=request.method
        )

        start_time = time.time()

        try:
            # Execute original function
            response = f(*args, **kwargs)

            # Calculate total latency
            g.xray.total_latency_ms = int((time.time() - start_time) * 1000)

            # For blocking calls, TTFT equals total latency
            if g.xray.ttft_ms is None:
                g.xray.ttft_ms = g.xray.total_latency_ms

            # Inject debug data if requested
            if _should_include_debug():
                response = _inject_debug_data(response, g.xray)

            # Log trace for observability
            logger.debug(
                f"X-Ray trace: {g.xray.endpoint} - {g.xray.total_latency_ms}ms - {g.xray.model}",
                extra={'request_id': g.xray.request_id, 'xray': g.xray.to_dict()}
            )

            return response

        except Exception as e:
            g.xray.error = str(e)
            g.xray.total_latency_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"X-Ray trace error: {e}",
                extra={'request_id': g.xray.request_id, 'xray': g.xray.to_dict()}
            )
            raise

    return decorated_function


def update_xray_from_gateway(result: Dict[str, Any], domain: str = "general", context_length: int = 0) -> None:
    """
    Update XRay trace with data from OpenRouter gateway response.

    Call this after chat_completion() in routes.py:
        result = chat_completion(model=model, messages=messages, context=context, domain=domain)
        update_xray_from_gateway(result, domain=domain, context_length=len(context))

    Args:
        result: Response dict from chat_completion()
        domain: Domain profile used (general, legal, medical, technical)
        context_length: Length of context string in characters
    """
    if not hasattr(g, 'xray'):
        return

    g.xray.gateway_latency_ms = result.get('latency_ms', 0)
    g.xray.model = result.get('model', '')
    g.xray.model_id = result.get('model_id', '')
    g.xray.estimated_cost = result.get('cost', 0.0)
    g.xray.domain = domain
    g.xray.context_length = context_length

    # v3.0: Cost tracking for CFO Hook
    g.xray.gpt4_cost = result.get('gpt4_cost', 0.0)
    g.xray.savings = result.get('savings', 0.0)
    g.xray.savings_percent = result.get('savings_percent', 0.0)

    # Extract token usage
    usage = result.get('usage', {})
    g.xray.tokens_input = usage.get('prompt_tokens', 0)
    g.xray.tokens_output = usage.get('completion_tokens', 0)
    g.xray.tokens_total = usage.get('total_tokens', 0)

    # If we have gateway latency, use it as TTFT (more accurate than total)
    if g.xray.gateway_latency_ms > 0:
        g.xray.ttft_ms = g.xray.gateway_latency_ms


def _should_include_debug() -> bool:
    """Check if debug data should be included in response."""
    return (
        request.args.get('debug') == '1' or
        request.headers.get('X-Debug') == '1'
    )


def _inject_debug_data(response: Any, trace: XRayTrace) -> Any:
    """
    Inject _debug object into JSON response.

    Handles both:
    - Flask Response objects with JSON data
    - Tuple responses (data, status_code)
    """
    try:
        # Handle tuple response (data, status_code)
        if isinstance(response, tuple):
            data, status_code = response[0], response[1]
            if hasattr(data, 'get_json'):
                json_data = data.get_json()
                if json_data and isinstance(json_data, dict):
                    json_data['_debug'] = trace.to_dict()
                    return Response(
                        json.dumps(json_data),
                        status=status_code,
                        mimetype='application/json'
                    ), status_code
            return response

        # Handle Flask Response object
        if isinstance(response, Response):
            try:
                json_data = response.get_json()
                if json_data and isinstance(json_data, dict):
                    json_data['_debug'] = trace.to_dict()
                    response.set_data(json.dumps(json_data))
            except Exception:
                pass
            return response

        return response

    except Exception as e:
        logger.warning(f"Failed to inject debug data: {e}")
        return response


def get_current_trace() -> Optional[XRayTrace]:
    """
    Get the current request's X-Ray trace.

    Useful for accessing trace data from other parts of the application.

    Returns:
        XRayTrace if available, None otherwise
    """
    return getattr(g, 'xray', None)


def update_xray_from_agent(result: Dict[str, Any], agent_type: str = "investigator") -> None:
    """
    Update XRay trace with data from agent execution.

    Call this after agent.run() in routes.py:
        result = agent.run(mission)
        update_xray_from_agent(result, agent_type="investigator")

    Args:
        result: Response dict from agent.run()
        agent_type: Type of agent (investigator, researcher, etc.)
    """
    if not hasattr(g, 'xray'):
        return

    g.xray.agent_type = agent_type
    g.xray.estimated_cost = result.get('cost', 0.0)

    # Get report data
    report = result.get('report', {})
    g.xray.savings = report.get('savings', 0.0)
    g.xray.savings_percent = result.get('savings_percent', 0.0)
    g.xray.gpt4_cost = report.get('gpt4_cost', 0.0)

    # Get debug data if available
    debug = result.get('_debug', {})
    g.xray.agent_steps = debug.get('agent_steps', [])
    g.xray.agent_step_latencies = debug.get('agent_step_latencies', {})
    g.xray.agent_step_tokens = debug.get('agent_step_tokens', {})
    g.xray.agent_documents_analyzed = debug.get('documents_analyzed', [])
    g.xray.agent_chunks_retrieved = debug.get('chunks_retrieved', 0)

    # v3.2: Vector search telemetry
    g.xray.vector_results_count = debug.get('chunks_retrieved', 0)
    g.xray.vector_search_empty = debug.get('chunks_retrieved', 0) == 0

    # v3.2: Quality gate metrics
    g.xray.quality_score = debug.get('quality_score')
    g.xray.quality_threshold = debug.get('quality_threshold', 7)
    g.xray.iterations = debug.get('iterations', 1)
    g.xray.retried = debug.get('retried', False)
    g.xray.max_retries = debug.get('max_retries', 2)

    # v3.2: Tool calling metrics
    g.xray.tools_enabled = debug.get('tools_enabled', False)
    g.xray.tool_calls = debug.get('tool_calls', [])
    g.xray.tool_results = debug.get('tool_results', [])
    g.xray.external_context_count = debug.get('external_context_count', 0)


def update_xray_vector_search(results_count: int) -> None:
    """
    Update XRay trace with vector search results.

    Call this after vector search in RAG chat:
        results = memory_store.search(query_embedding, k=5)
        update_xray_vector_search(len(results))

    Args:
        results_count: Number of results returned from vector search
    """
    if not hasattr(g, 'xray'):
        return

    g.xray.vector_results_count = results_count
    g.xray.vector_search_empty = results_count == 0

    # Log warning if empty (helps diagnose RAG issues)
    if results_count == 0:
        logger.warning(
            "Vector search returned no results - check document upload",
            extra={'request_id': g.xray.request_id}
        )
