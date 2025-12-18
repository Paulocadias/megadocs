"""
Investigator Agent for MegaDoc.

LangGraph-based agent for mission-driven document analysis.
Implements an advanced workflow with:
- Conditional loops (self-correction if quality < threshold)
- Tool calling (web search for external context)
- Quality gates with retry logic
- Multi-step reasoning with state tracking

Architecture Pattern: StateGraph with conditional edges for production-grade AI workflows.
Career Impact: Differentiator for AI Lead roles - proves agentic workflow mastery.
"""

import time
import json
import logging
import re
import os
from typing import Dict, Any, List, Optional, TypedDict, Literal, Callable
from dataclasses import dataclass

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None

# Local imports
from openrouter_gateway import chat_completion_with_fallback, calculate_request_cost
from memory_store import get_memory_store
from chunker import chunk_document
from embedder import generate_embedding, generate_embeddings_batch, EMBEDDINGS_AVAILABLE

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================
QUALITY_THRESHOLD = 7  # Minimum quality score to proceed (1-10)
MAX_RETRIES = 2        # Maximum self-correction attempts
ENABLE_WEB_SEARCH = True  # Enable external context enrichment


# =============================================================================
# TOOL DEFINITIONS (For Tool Calling Pattern)
# =============================================================================
@dataclass
class Tool:
    """Tool definition for agent tool calling."""
    name: str
    description: str
    func: Callable


class AgentTools:
    """
    Collection of tools available to the agent.

    Demonstrates multi-provider resilience pattern with graceful degradation:
    1. Tavily (best for AI, 1000 free/month) - requires TAVILY_API_KEY
    2. Serper (Google results, 2500 free) - requires SERPER_API_KEY
    3. DuckDuckGo (always free, limited) - no key required
    """

    @staticmethod
    def web_search(query: str) -> Dict[str, Any]:
        """
        Search the web with multi-provider fallback chain.

        Provider priority:
        1. Tavily API (best for RAG/AI apps)
        2. Serper API (Google results)
        3. DuckDuckGo (free fallback)
        """
        import requests

        # Try Tavily first (best for AI applications)
        tavily_key = os.environ.get('TAVILY_API_KEY')
        if tavily_key:
            result = AgentTools._search_tavily(query, tavily_key)
            if result['success']:
                return result
            logger.warning("Tavily search failed, trying next provider...")

        # Try Serper (Google results)
        serper_key = os.environ.get('SERPER_API_KEY')
        if serper_key:
            result = AgentTools._search_serper(query, serper_key)
            if result['success']:
                return result
            logger.warning("Serper search failed, trying next provider...")

        # Fallback to DuckDuckGo (always available)
        return AgentTools._search_duckduckgo(query)

    @staticmethod
    def _search_tavily(query: str, api_key: str) -> Dict[str, Any]:
        """
        Tavily Search API - Best for AI/RAG applications.
        Free tier: 1000 searches/month
        Sign up: https://tavily.com
        """
        import requests

        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "include_raw_content": False,
                    "max_results": 5
                },
                timeout=10
            )
            data = response.json()

            if response.status_code != 200:
                return {"success": False, "error": data.get("error", "Tavily API error"), "results": []}

            results = []

            # Get AI-generated answer if available
            if data.get("answer"):
                results.append({
                    "source": "Tavily AI",
                    "text": data["answer"],
                    "url": "",
                    "type": "ai_summary"
                })

            # Get search results
            for item in data.get("results", [])[:4]:
                results.append({
                    "source": item.get("title", "Web"),
                    "text": item.get("content", "")[:500],
                    "url": item.get("url", ""),
                    "type": "web_result"
                })

            return {
                "success": True,
                "results": results,
                "query": query,
                "provider": "tavily"
            }

        except Exception as e:
            logger.warning(f"Tavily search failed: {e}")
            return {"success": False, "error": str(e), "results": []}

    @staticmethod
    def _search_serper(query: str, api_key: str) -> Dict[str, Any]:
        """
        Serper API - Google Search results.
        Free tier: 2500 searches
        Sign up: https://serper.dev
        """
        import requests

        try:
            response = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 5},
                timeout=10
            )
            data = response.json()

            if response.status_code != 200:
                return {"success": False, "error": "Serper API error", "results": []}

            results = []

            # Get knowledge graph if available
            if data.get("knowledgeGraph"):
                kg = data["knowledgeGraph"]
                if kg.get("description"):
                    results.append({
                        "source": kg.get("title", "Knowledge Graph"),
                        "text": kg["description"],
                        "url": kg.get("website", ""),
                        "type": "knowledge_graph"
                    })

            # Get organic results
            for item in data.get("organic", [])[:4]:
                results.append({
                    "source": item.get("title", "Web"),
                    "text": item.get("snippet", ""),
                    "url": item.get("link", ""),
                    "type": "web_result"
                })

            return {
                "success": True,
                "results": results,
                "query": query,
                "provider": "serper"
            }

        except Exception as e:
            logger.warning(f"Serper search failed: {e}")
            return {"success": False, "error": str(e), "results": []}

    @staticmethod
    def _search_duckduckgo(query: str) -> Dict[str, Any]:
        """
        DuckDuckGo Instant Answer API - Free fallback.
        No API key required, but limited results (Wikipedia-style).
        """
        import requests

        try:
            response = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1},
                timeout=5
            )
            data = response.json()

            results = []

            # Get abstract if available
            if data.get("AbstractText"):
                results.append({
                    "source": data.get("AbstractSource", "Wikipedia"),
                    "text": data["AbstractText"],
                    "url": data.get("AbstractURL", ""),
                    "type": "abstract"
                })

            # Get related topics
            for topic in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "source": "DuckDuckGo",
                        "text": topic["Text"],
                        "url": topic.get("FirstURL", ""),
                        "type": "related"
                    })

            return {
                "success": len(results) > 0,
                "results": results,
                "query": query,
                "provider": "duckduckgo"
            }

        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "provider": "duckduckgo"
            }

    @staticmethod
    def calculate(expression: str) -> Dict[str, Any]:
        """Safely evaluate numerical expressions."""
        try:
            # Only allow safe operations
            allowed = set('0123456789+-*/().% ')
            if not all(c in allowed for c in expression):
                return {"success": False, "error": "Invalid characters"}

            result = eval(expression)  # Safe due to character whitelist
            return {"success": True, "result": result, "expression": expression}
        except Exception as e:
            return {"success": False, "error": str(e)}


# =============================================================================
# STATE DEFINITION
# =============================================================================
class InvestigatorState(TypedDict, total=False):
    """
    State for the Investigator Agent workflow.

    Enhanced with:
    - Iteration tracking for self-correction loops
    - Tool results for enrichment
    - Quality gates for conditional routing
    """
    # Input
    mission: str
    session_id: str

    # Processing state
    documents: List[str]
    sub_tasks: List[str]
    retrieved_context: List[Dict[str, Any]]
    analysis: str
    validation: Dict[str, Any]

    # Tool calling state
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    external_context: List[Dict[str, Any]]

    # Self-correction state (KEY DIFFERENTIATOR)
    iteration: int
    quality_score: float
    should_retry: bool
    retry_feedback: str
    previous_analyses: List[str]

    # Output
    final_report: Dict[str, Any]

    # Telemetry
    steps_completed: List[str]
    step_latencies: Dict[str, int]
    step_tokens: Dict[str, Dict[str, int]]
    total_cost: float
    total_savings: float
    errors: List[str]


class InvestigatorAgent:
    """
    Mission-driven document investigation agent with self-correction.

    Advanced Architecture Pattern (Demonstrates AI Lead Skills):
    ┌─────────────────────────────────────────────────────────────────┐
    │                    INVESTIGATOR AGENT v2.0                       │
    │                                                                   │
    │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
    │  │Decomposer│ -> │Retriever │ -> │ Enricher │ -> │ Analyzer │  │
    │  │(plan)    │    │(RAG)     │    │(tools)   │    │(reason)  │  │
    │  └──────────┘    └──────────┘    └──────────┘    └────┬─────┘  │
    │                                                        │        │
    │                                    ┌───────────────────┘        │
    │                                    ▼                            │
    │                              ┌──────────┐                       │
    │                              │Validator │                       │
    │                              │(quality) │                       │
    │                              └────┬─────┘                       │
    │                                   │                             │
    │                      ┌────────────┴────────────┐                │
    │                      ▼                         ▼                │
    │               [quality >= 7]           [quality < 7]            │
    │                      │                         │                │
    │                      ▼                         ▼                │
    │                 ┌────────┐              ┌───────────┐           │
    │                 │  END   │              │  RETRY    │ (max 2x)  │
    │                 │(report)│              │(feedback) │───────┐   │
    │                 └────────┘              └───────────┘       │   │
    │                                               ▲             │   │
    │                                               └─────────────┘   │
    └─────────────────────────────────────────────────────────────────┘

    Features:
    - Conditional loops: Retry analysis if quality < threshold
    - Tool calling: Web search for external context enrichment
    - Self-correction: Uses validator feedback to improve analysis
    - Quality gates: Ensures output meets minimum standards

    Usage:
        agent = InvestigatorAgent(session_id="user123")
        result = agent.run("Identify all legal risks in this contract")
    """

    def __init__(self, session_id: str, model: str = "Google Gemini 2.0 Flash"):
        """
        Initialize the Investigator Agent.

        Args:
            session_id: User session ID for document retrieval
            model: LLM model to use for reasoning
        """
        self.session_id = session_id
        self.model = model
        self.memory_store = get_memory_store()
        self.tools = AgentTools()

        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph not available - agent will use fallback mode")

    def _get_documents(self) -> List[Dict[str, Any]]:
        """Get uploaded documents from memory store."""
        items = self.memory_store.get_items(self.session_id)
        return items if items else []

    def _get_combined_content(self) -> str:
        """Get combined document content for context."""
        return self.memory_store.get_combined_content(self.session_id)

    def _chunk_and_embed_documents(self) -> List[Dict[str, Any]]:
        """Chunk documents and generate embeddings for semantic search."""
        documents = self._get_documents()
        all_chunks = []

        for doc in documents:
            content = doc.get('content', '')
            filename = doc.get('filename', 'unknown')

            # Chunk the document
            result = chunk_document(content, chunk_size=256, chunk_overlap=30, strategy="semantic_window")

            if 'error' not in result:
                for chunk in result['chunks']:
                    chunk['source'] = filename
                    all_chunks.append({
                        'text': chunk['text'],
                        'source': filename,
                        'index': chunk['index'],
                        'token_count': chunk['token_count']
                    })

        # Generate embeddings for all chunks
        if all_chunks:
            texts = [c['text'] for c in all_chunks]
            embeddings = generate_embeddings_batch(texts)

            for i, chunk in enumerate(all_chunks):
                chunk['embedding'] = embeddings[i]['embedding']

        return all_chunks

    def _semantic_search(self, query: str, chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """Find most relevant chunks using cosine similarity."""
        if not chunks:
            return []

        # Generate query embedding
        query_result = generate_embedding(query)
        query_embedding = query_result['embedding']

        # Calculate cosine similarity with each chunk
        import math

        def cosine_similarity(a: List[float], b: List[float]) -> float:
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot_product / (norm_a * norm_b)

        # Score and rank chunks
        scored_chunks = []
        for chunk in chunks:
            if 'embedding' in chunk:
                score = cosine_similarity(query_embedding, chunk['embedding'])
                scored_chunks.append({
                    **chunk,
                    'relevance_score': score
                })

        # Sort by relevance and return top_k
        scored_chunks.sort(key=lambda x: x['relevance_score'], reverse=True)
        return scored_chunks[:top_k]

    def _call_llm(self, system_prompt: str, user_message: str) -> Dict[str, Any]:
        """Call LLM with fallback support."""
        messages = [{"role": "user", "content": user_message}]

        result = chat_completion_with_fallback(
            model=self.model,
            messages=messages,
            context=None,  # Context is included in the system prompt
            domain="general"
        )

        # Handle error case
        if 'error' in result:
            return {
                'response': f"Error: {result.get('message', result.get('error', 'Unknown error'))}",
                'error': True,
                'latency_ms': result.get('latency_ms', 0),
                'cost': 0.0,
                'savings': 0.0,
                'usage': {}
            }

        return result

    # =========================================================================
    # AGENT NODES
    # =========================================================================

    def node_decompose(self, state: InvestigatorState) -> Dict[str, Any]:
        """
        Decomposer Node: Break mission into actionable sub-tasks.

        Input: mission
        Output: sub_tasks (list of specific investigation tasks)
        """
        start_time = time.time()
        mission = state.get('mission', '')

        system_prompt = """You are a Strategic Investigation Planner. Your job is to break down investigation missions into specific, actionable sub-tasks.

RULES:
1. Create 3-5 focused sub-tasks that together cover the mission
2. Each sub-task should be specific and searchable
3. Order tasks from most critical to least critical
4. Focus on what needs to be FOUND in the documents

OUTPUT FORMAT (JSON):
{
    "sub_tasks": [
        "Find all [specific thing] in the documents",
        "Identify any [specific pattern or issue]",
        "Extract [specific information]",
        "Check for [specific concern]"
    ],
    "reasoning": "Brief explanation of the decomposition strategy"
}"""

        user_message = f"""Mission: {mission}

Break this mission into 3-5 specific investigation sub-tasks. Return JSON only."""

        result = self._call_llm(system_prompt, user_message)
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse sub-tasks from response
        sub_tasks = []
        try:
            response_text = result.get('response', '')
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                parsed = json.loads(json_match.group())
                sub_tasks = parsed.get('sub_tasks', [])
        except (json.JSONDecodeError, AttributeError):
            # Fallback: create generic sub-tasks
            sub_tasks = [
                f"Find relevant information about: {mission}",
                f"Identify key points related to: {mission}",
                f"Extract specific details for: {mission}"
            ]

        return {
            'sub_tasks': sub_tasks,
            'steps_completed': ['decompose'],
            'step_latencies': {'decompose': latency_ms},
            'step_tokens': {'decompose': result.get('usage', {})},
            'total_cost': result.get('cost', 0.0),
            'total_savings': result.get('savings', 0.0)
        }

    def node_retrieve(self, state: InvestigatorState) -> Dict[str, Any]:
        """
        Retriever Node: Get relevant chunks from documents using semantic search.
        Falls back to using all document content when semantic embeddings aren't available.

        Input: sub_tasks
        Output: retrieved_context (relevant chunks with sources)
        """
        start_time = time.time()
        sub_tasks = state.get('sub_tasks', [])

        # Get and chunk documents
        chunks = self._chunk_and_embed_documents()

        if not chunks:
            return {
                'retrieved_context': [],
                'steps_completed': state.get('steps_completed', []) + ['retrieve'],
                'step_latencies': {**state.get('step_latencies', {}), 'retrieve': int((time.time() - start_time) * 1000)},
                'errors': state.get('errors', []) + ['No documents found in session']
            }

        all_retrieved = []
        seen_texts = set()

        # Check if semantic embeddings are available
        if EMBEDDINGS_AVAILABLE:
            # Use semantic search for each sub-task
            for task in sub_tasks:
                relevant = self._semantic_search(task, chunks, top_k=3)
                for chunk in relevant:
                    text_key = chunk['text'][:100]
                    if text_key not in seen_texts:
                        seen_texts.add(text_key)
                        all_retrieved.append({
                            'text': chunk['text'],
                            'source': chunk['source'],
                            'relevance_score': chunk['relevance_score'],
                            'matched_task': task
                        })
            # Sort by relevance and limit
            all_retrieved.sort(key=lambda x: x['relevance_score'], reverse=True)
            all_retrieved = all_retrieved[:10]
        else:
            # Fallback: Use all document content (no semantic search)
            # This ensures the investigator works even without sentence-transformers
            logger.info("Semantic embeddings not available - using full document content")
            for chunk in chunks:
                text_key = chunk['text'][:100]
                if text_key not in seen_texts:
                    seen_texts.add(text_key)
                    all_retrieved.append({
                        'text': chunk['text'],
                        'source': chunk['source'],
                        'relevance_score': 1.0,  # All chunks equally relevant
                        'matched_task': 'full_content'
                    })
            # Limit to first 15 chunks (more context since no semantic filtering)
            all_retrieved = all_retrieved[:15]

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            'retrieved_context': all_retrieved,
            'steps_completed': state.get('steps_completed', []) + ['retrieve'],
            'step_latencies': {**state.get('step_latencies', {}), 'retrieve': latency_ms},
            'step_tokens': {**state.get('step_tokens', {}), 'retrieve': {'chunks_processed': len(chunks), 'chunks_retrieved': len(all_retrieved), 'semantic_mode': EMBEDDINGS_AVAILABLE}}
        }

    def node_enrich(self, state: InvestigatorState) -> Dict[str, Any]:
        """
        Enricher Node: Use tools to gather external context.

        This demonstrates the TOOL CALLING pattern - a key differentiator for AI leads.
        The agent decides what tools to call based on the mission and context gaps.

        Input: mission, sub_tasks, retrieved_context
        Output: external_context, tool_results
        """
        start_time = time.time()
        mission = state.get('mission', '')
        sub_tasks = state.get('sub_tasks', [])

        tool_results = []
        external_context = []

        if not ENABLE_WEB_SEARCH:
            return {
                'tool_results': [],
                'external_context': [],
                'steps_completed': state.get('steps_completed', []) + ['enrich'],
                'step_latencies': {**state.get('step_latencies', {}), 'enrich': 0}
            }

        # Intelligently decide if web search would help
        # (In production, this would be an LLM decision)
        search_triggers = [
            'legal', 'compliance', 'regulation', 'law', 'standard',
            'industry', 'best practice', 'benchmark', 'compare'
        ]
        should_search = any(trigger in mission.lower() for trigger in search_triggers)

        if should_search:
            # Generate search query from mission
            search_query = f"{mission} legal compliance requirements"
            search_result = self.tools.web_search(search_query)

            tool_results.append({
                'tool': 'web_search',
                'query': search_query,
                'success': search_result['success'],
                'results_count': len(search_result.get('results', []))
            })

            if search_result['success']:
                for result in search_result.get('results', []):
                    external_context.append({
                        'text': result['text'],
                        'source': f"[Web: {result['source']}]",
                        'url': result.get('url', ''),
                        'type': 'external'
                    })

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            'tool_results': tool_results,
            'external_context': external_context,
            'tool_calls': [{'tool': 'web_search', 'executed': should_search}],
            'steps_completed': state.get('steps_completed', []) + ['enrich'],
            'step_latencies': {**state.get('step_latencies', {}), 'enrich': latency_ms}
        }

    def node_analyze(self, state: InvestigatorState) -> Dict[str, Any]:
        """
        Analyzer Node: Reason over retrieved context to find insights.

        ENHANCED: Now includes self-correction via retry_feedback from validator.

        Input: mission, sub_tasks, retrieved_context, external_context, retry_feedback
        Output: analysis (structured findings)
        """
        start_time = time.time()
        mission = state.get('mission', '')
        sub_tasks = state.get('sub_tasks', [])
        context = state.get('retrieved_context', [])
        external_context = state.get('external_context', [])
        retry_feedback = state.get('retry_feedback', '')
        iteration = state.get('iteration', 1)
        previous_analyses = state.get('previous_analyses', [])

        # Build context string from documents
        context_str = "\n\n".join([
            f"[Source: {c['source']}]\n{c['text']}"
            for c in context
        ])

        # Add external context if available
        external_str = ""
        if external_context:
            external_str = "\n\nEXTERNAL CONTEXT (from web search):\n" + "\n\n".join([
                f"[Source: {c['source']}]\n{c['text']}"
                for c in external_context
            ])

        if not context_str:
            context_str = "No relevant context found in documents."

        # Build retry feedback section if this is a retry iteration
        retry_section = ""
        if retry_feedback and iteration > 1:
            retry_section = f"""

IMPORTANT - SELF-CORRECTION REQUIRED (Iteration {iteration}):
Your previous analysis had quality issues. The validator provided this feedback:
{retry_feedback}

Previous analysis to improve upon:
{previous_analyses[-1] if previous_analyses else 'N/A'}

Please address ALL the issues mentioned above in your new analysis.
"""

        system_prompt = """You are an Expert Document Analyst. Your job is to analyze document content and extract findings based on the mission.

RULES:
1. ONLY use information from the provided context (document + external)
2. Cite sources for each finding (use [Source: filename] or [Source: Web])
3. Rate severity/importance: high, medium, low
4. Be specific and actionable
5. If information is missing, explicitly state what's not found
6. If this is a RETRY, carefully address the feedback provided

OUTPUT FORMAT (JSON):
{
    "summary": "2-3 sentence executive summary",
    "findings": [
        {
            "finding": "Specific finding description",
            "source": "filename.pdf",
            "location": "Section/page if identifiable",
            "severity": "high|medium|low",
            "recommendation": "Suggested action"
        }
    ],
    "gaps": ["List of information not found in documents"],
    "confidence": "high|medium|low"
}"""

        user_message = f"""MISSION: {mission}

SUB-TASKS INVESTIGATED:
{chr(10).join(f"- {t}" for t in sub_tasks)}

DOCUMENT CONTEXT:
{context_str}{external_str}{retry_section}

Analyze this context and extract findings. Return JSON only."""

        result = self._call_llm(system_prompt, user_message)
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse analysis from response
        analysis = result.get('response', '')

        # Track previous analyses for self-correction
        new_previous = previous_analyses + [analysis] if iteration > 1 else [analysis]

        # Step name includes iteration for telemetry
        step_name = f"analyze_iter_{iteration}"

        return {
            'analysis': analysis,
            'previous_analyses': new_previous,
            'iteration': iteration,  # Preserve iteration count
            'steps_completed': state.get('steps_completed', []) + [step_name],
            'step_latencies': {**state.get('step_latencies', {}), step_name: latency_ms},
            'step_tokens': {**state.get('step_tokens', {}), step_name: result.get('usage', {})},
            'total_cost': state.get('total_cost', 0.0) + result.get('cost', 0.0),
            'total_savings': state.get('total_savings', 0.0) + result.get('savings', 0.0)
        }

    def node_validate(self, state: InvestigatorState) -> Dict[str, Any]:
        """
        Validator Node: Check for hallucinations and quality issues.

        ENHANCED: Now acts as a QUALITY GATE that can trigger retry loops.

        Input: analysis, retrieved_context, iteration
        Output: validation, should_retry, retry_feedback, quality_score
        """
        start_time = time.time()
        analysis = state.get('analysis', '')
        context = state.get('retrieved_context', [])
        mission = state.get('mission', '')
        iteration = state.get('iteration', 1)

        # Build context for validation
        context_texts = [c['text'] for c in context]
        context_summary = "\n".join(context_texts[:5])  # First 5 chunks for validation

        system_prompt = """You are a Quality Assurance AI. Your job is to validate analysis for accuracy and hallucinations.

RULES:
1. Check if each finding is supported by the source context
2. Flag any claims not backed by evidence
3. Verify source citations are accurate
4. Rate overall quality and reliability

OUTPUT FORMAT (JSON):
{
    "quality_score": 1-10,
    "hallucination_risk": "low|medium|high",
    "issues": [
        {
            "type": "unsupported_claim|missing_citation|factual_error",
            "description": "What the issue is",
            "suggestion": "How to fix it"
        }
    ],
    "verified_findings_count": 0,
    "total_findings_count": 0,
    "recommendation": "proceed|revise|reject"
}"""

        user_message = f"""ANALYSIS TO VALIDATE:
{analysis}

SOURCE CONTEXT AVAILABLE:
{context_summary[:2000]}

Validate this analysis for accuracy and hallucinations. Return JSON only."""

        result = self._call_llm(system_prompt, user_message)
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse validation result
        validation = {}
        try:
            response_text = result.get('response', '')
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                validation = json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            validation = {
                'quality_score': 5,
                'hallucination_risk': 'unknown',
                'recommendation': 'proceed'
            }

        # QUALITY GATE: Determine if we should retry
        quality_score = validation.get('quality_score', 5)
        issues = validation.get('issues', [])
        should_retry = quality_score < QUALITY_THRESHOLD and iteration < MAX_RETRIES

        # Build feedback for retry
        retry_feedback = ""
        if should_retry:
            issue_descriptions = [f"- {issue.get('type', 'Issue')}: {issue.get('description', 'Unknown')}"
                                  for issue in issues]
            retry_feedback = f"""Quality score: {quality_score}/10 (threshold: {QUALITY_THRESHOLD})
Issues found:
{chr(10).join(issue_descriptions) if issue_descriptions else '- General quality below threshold'}

Suggestions:
{chr(10).join(f"- {issue.get('suggestion', 'Improve analysis')}" for issue in issues)}"""

        # Parse analysis JSON for final report
        analysis_data = {}
        try:
            json_match = re.search(r'\{[\s\S]*\}', analysis)
            if json_match:
                analysis_data = json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            analysis_data = {'summary': analysis[:500], 'findings': [], 'gaps': []}

        # Build final report
        total_cost = state.get('total_cost', 0.0) + result.get('cost', 0.0)
        total_savings = state.get('total_savings', 0.0) + result.get('savings', 0.0)
        gpt4_cost = total_cost + total_savings
        savings_percent = (total_savings / gpt4_cost * 100) if gpt4_cost > 0 else 0

        # Include tool results in report
        tool_results = state.get('tool_results', [])
        external_context = state.get('external_context', [])

        final_report = {
            'mission': mission,
            'summary': analysis_data.get('summary', 'Analysis complete'),
            'findings': analysis_data.get('findings', []),
            'gaps': analysis_data.get('gaps', []),
            'confidence': analysis_data.get('confidence', 'medium'),
            'sources': list(set(c['source'] for c in context)),
            'external_sources': [c.get('url', c.get('source', '')) for c in external_context],
            'quality': validation,
            'iterations': iteration,
            'retried': iteration > 1,
            'steps_completed': len(state.get('steps_completed', [])) + 1,
            'total_latency_ms': sum(state.get('step_latencies', {}).values()) + latency_ms,
            'cost': round(total_cost, 6),
            'gpt4_cost': round(gpt4_cost, 6),
            'savings': round(total_savings, 6),
            'savings_percent': round(savings_percent, 2),
            'tools_used': [t.get('tool') for t in tool_results if t.get('success')]
        }

        # Step name includes iteration for telemetry
        step_name = f"validate_iter_{iteration}"

        return {
            'validation': validation,
            'quality_score': quality_score,
            'should_retry': should_retry,
            'retry_feedback': retry_feedback,
            'iteration': iteration + 1 if should_retry else iteration,  # Increment for next iteration
            'final_report': final_report,
            'steps_completed': state.get('steps_completed', []) + [step_name],
            'step_latencies': {**state.get('step_latencies', {}), step_name: latency_ms},
            'step_tokens': {**state.get('step_tokens', {}), step_name: result.get('usage', {})},
            'total_cost': total_cost,
            'total_savings': total_savings
        }

    # =========================================================================
    # GRAPH BUILDING (WITH CONDITIONAL LOOPS)
    # =========================================================================

    def _should_retry(self, state: InvestigatorState) -> Literal["analyze", "end"]:
        """
        Conditional edge: Decide whether to retry analysis or end.

        This is the KEY DIFFERENTIATOR - shows understanding of:
        - Conditional routing in state machines
        - Quality gates with feedback loops
        - Self-correction patterns in AI systems
        """
        should_retry = state.get('should_retry', False)
        iteration = state.get('iteration', 1)

        if should_retry and iteration <= MAX_RETRIES:
            logger.info(f"Quality gate failed (iter {iteration}). Retrying analysis...")
            return "analyze"
        else:
            if iteration > 1:
                logger.info(f"Analysis improved after {iteration - 1} retry(s)")
            return "end"

    def build_graph(self) -> Optional[StateGraph]:
        """
        Build the LangGraph workflow with conditional loops.

        Graph Structure:
        decompose -> retrieve -> enrich -> analyze -> validate
                                              ^           |
                                              |           v
                                              +----- [retry?] ----> END

        The conditional edge from validate either:
        - Routes back to analyze (if quality < threshold && retries < max)
        - Routes to END (if quality >= threshold || retries exhausted)
        """
        if not LANGGRAPH_AVAILABLE:
            return None

        # Create the graph
        graph = StateGraph(InvestigatorState)

        # Add nodes (5-node workflow with tool calling)
        graph.add_node("decompose", self.node_decompose)
        graph.add_node("retrieve", self.node_retrieve)
        graph.add_node("enrich", self.node_enrich)  # NEW: Tool calling node
        graph.add_node("analyze", self.node_analyze)
        graph.add_node("validate", self.node_validate)

        # Add edges (with conditional loop)
        graph.set_entry_point("decompose")
        graph.add_edge("decompose", "retrieve")
        graph.add_edge("retrieve", "enrich")
        graph.add_edge("enrich", "analyze")
        graph.add_edge("analyze", "validate")

        # CONDITIONAL EDGE: The magic happens here
        # validate -> analyze (retry) OR validate -> END (success/max retries)
        graph.add_conditional_edges(
            "validate",
            self._should_retry,
            {
                "analyze": "analyze",  # Loop back to re-analyze with feedback
                "end": END             # Proceed to output
            }
        )

        return graph.compile()

    # =========================================================================
    # MAIN EXECUTION
    # =========================================================================

    def run(self, mission: str) -> Dict[str, Any]:
        """
        Execute the investigation workflow.

        Args:
            mission: The investigation mission (e.g., "Identify all legal risks")

        Returns:
            Dictionary with:
            - success: bool
            - report: Structured findings
            - steps_completed: Number of steps completed
            - total_latency_ms: Total execution time
            - cost: Actual cost
            - savings_percent: Savings vs GPT-4
            - _debug: Detailed telemetry
        """
        start_time = time.time()

        # Check for documents
        docs = self._get_documents()
        if not docs:
            return {
                'success': False,
                'error': 'No documents uploaded. Please upload documents first.',
                'steps_completed': 0,
                'total_latency_ms': 0
            }

        # Initial state (enhanced with self-correction and tool calling)
        initial_state: InvestigatorState = {
            # Input
            'mission': mission,
            'session_id': self.session_id,
            'documents': [d.get('filename', 'unknown') for d in docs],

            # Processing state
            'sub_tasks': [],
            'retrieved_context': [],
            'analysis': '',
            'validation': {},

            # Tool calling state
            'tool_calls': [],
            'tool_results': [],
            'external_context': [],

            # Self-correction state
            'iteration': 1,
            'quality_score': 0.0,
            'should_retry': False,
            'retry_feedback': '',
            'previous_analyses': [],

            # Output
            'final_report': {},

            # Telemetry
            'steps_completed': [],
            'step_latencies': {},
            'step_tokens': {},
            'total_cost': 0.0,
            'total_savings': 0.0,
            'errors': []
        }

        try:
            if LANGGRAPH_AVAILABLE:
                # Use LangGraph
                graph = self.build_graph()
                if graph:
                    final_state = graph.invoke(initial_state)
                else:
                    # Fallback to manual execution
                    final_state = self._run_manual(initial_state)
            else:
                # Fallback to manual execution
                final_state = self._run_manual(initial_state)

            total_latency_ms = int((time.time() - start_time) * 1000)

            # Build comprehensive debug info for the panel
            final_iteration = final_state.get('iteration', 1)
            quality_score = final_state.get('quality_score', 0)
            tool_results = final_state.get('tool_results', [])

            return {
                'success': True,
                'report': final_state.get('final_report', {}),
                'steps_completed': len(final_state.get('steps_completed', [])),
                'total_latency_ms': total_latency_ms,
                'cost': final_state.get('total_cost', 0.0),
                'savings_percent': final_state.get('final_report', {}).get('savings_percent', 0.0),
                '_debug': {
                    # Step execution trace
                    'agent_steps': final_state.get('steps_completed', []),
                    'agent_step_latencies': final_state.get('step_latencies', {}),
                    'agent_step_tokens': final_state.get('step_tokens', {}),

                    # Document analysis
                    'documents_analyzed': final_state.get('documents', []),
                    'chunks_retrieved': len(final_state.get('retrieved_context', [])),

                    # Self-correction metrics (KEY DIFFERENTIATOR)
                    'iterations': final_iteration,
                    'retried': final_iteration > 1,
                    'quality_score': quality_score,
                    'quality_threshold': QUALITY_THRESHOLD,
                    'max_retries': MAX_RETRIES,

                    # Tool calling metrics
                    'tools_enabled': ENABLE_WEB_SEARCH,
                    'tool_calls': final_state.get('tool_calls', []),
                    'tool_results': tool_results,
                    'external_context_count': len(final_state.get('external_context', [])),

                    # Errors
                    'errors': final_state.get('errors', [])
                }
            }

        except Exception as e:
            logger.exception(f"Investigation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'steps_completed': 0,
                'total_latency_ms': int((time.time() - start_time) * 1000)
            }

    def _run_manual(self, state: InvestigatorState) -> InvestigatorState:
        """
        Fallback manual execution without LangGraph.

        Implements the same logic as the graph:
        decompose -> retrieve -> enrich -> analyze -> validate -> [retry?]
        """
        # Decompose
        result = self.node_decompose(state)
        state = {**state, **result}

        # Retrieve
        result = self.node_retrieve(state)
        state = {**state, **result}

        # Enrich (tool calling)
        result = self.node_enrich(state)
        state = {**state, **result}

        # Analyze -> Validate loop (with self-correction)
        for iteration in range(1, MAX_RETRIES + 2):  # +2 for initial + max retries
            state['iteration'] = iteration

            # Analyze
            result = self.node_analyze(state)
            state = {**state, **result}

            # Validate
            result = self.node_validate(state)
            state = {**state, **result}

            # Check quality gate
            if not state.get('should_retry', False):
                break

            logger.info(f"Quality gate failed (iter {iteration}). Retrying with feedback...")

        return state


# Export for type hints
__all__ = ['InvestigatorAgent', 'InvestigatorState']
