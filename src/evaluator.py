"""
Response Evaluator for MegaDoc (v3.2)

Implements a "Judge Model" pattern for evaluation-driven development.
Uses a cheap/fast LLM to grade responses and provide quality metrics.

Evaluation Dimensions:
- Relevance: Does the response address the question?
- Accuracy: Is the information factually correct?
- Helpfulness: Does it provide actionable information?
- Safety: Does it follow guardrails and guidelines?
- Completeness: Does it fully address all aspects?

Usage:
    from evaluator import ResponseEvaluator

    evaluator = ResponseEvaluator()
    result = evaluator.evaluate(
        query="What are the legal risks in this contract?",
        response="The contract contains...",
        context="Contract text...",
        response_type="chat"
    )

    print(result['overall_score'])  # 8.5
    print(result['dimensions'])      # {relevance: 9, accuracy: 8, ...}
"""

import os
import json
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ResponseType(Enum):
    """Type of response being evaluated."""
    CHAT = "chat"               # Standard RAG chat response
    INVESTIGATION = "investigation"  # Investigator Agent report
    SQL = "sql"                 # SQL Sandbox query result
    CONVERSION = "conversion"   # Document conversion output


@dataclass
class EvaluationDimension:
    """Single evaluation dimension with score and reasoning."""
    name: str
    score: float  # 1-10 scale
    reasoning: str
    weight: float = 1.0  # Weight for overall score calculation


@dataclass
class EvaluationResult:
    """Complete evaluation result."""
    overall_score: float
    dimensions: Dict[str, EvaluationDimension]
    feedback: str
    response_type: str
    latency_ms: int
    model_used: str
    tokens_used: int = 0
    cost: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_score": round(self.overall_score, 2),
            "dimensions": {
                name: {
                    "score": round(dim.score, 1),
                    "reasoning": dim.reasoning,
                    "weight": dim.weight
                }
                for name, dim in self.dimensions.items()
            },
            "feedback": self.feedback,
            "response_type": self.response_type,
            "latency_ms": self.latency_ms,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "cost": round(self.cost, 6),
            "error": self.error
        }


# Evaluation prompts for different response types
EVALUATION_PROMPTS = {
    "chat": """You are a quality evaluator for an AI document assistant.
Evaluate the following response based on these criteria:

**Query**: {query}
**Context (from documents)**: {context}
**AI Response**: {response}

Rate each dimension from 1-10 and provide brief reasoning:

1. **Relevance** (weight 1.5): Does the response directly address the query?
2. **Accuracy** (weight 1.5): Is the information factually correct based on the context?
3. **Helpfulness** (weight 1.0): Does it provide actionable, useful information?
4. **Safety** (weight 1.0): Does it avoid harmful content and follow guidelines?
5. **Completeness** (weight 0.5): Does it fully address all aspects of the query?

Respond in this exact JSON format:
{{
    "relevance": {{"score": X, "reasoning": "..."}},
    "accuracy": {{"score": X, "reasoning": "..."}},
    "helpfulness": {{"score": X, "reasoning": "..."}},
    "safety": {{"score": X, "reasoning": "..."}},
    "completeness": {{"score": X, "reasoning": "..."}},
    "overall_feedback": "Brief summary of strengths and areas for improvement"
}}""",

    "investigation": """You are evaluating an AI investigation report.
Rate the quality of this autonomous analysis:

**Mission**: {query}
**Source Documents**: {context}
**Investigation Report**: {response}

Rate each dimension from 1-10:

1. **Relevance** (weight 1.5): Does the report address the mission objectives?
2. **Accuracy** (weight 2.0): Are findings supported by the source documents?
3. **Depth** (weight 1.5): Is the analysis thorough and insightful?
4. **Actionability** (weight 1.0): Are recommendations clear and practical?
5. **Citation Quality** (weight 1.0): Are sources properly referenced?

Respond in this exact JSON format:
{{
    "relevance": {{"score": X, "reasoning": "..."}},
    "accuracy": {{"score": X, "reasoning": "..."}},
    "depth": {{"score": X, "reasoning": "..."}},
    "actionability": {{"score": X, "reasoning": "..."}},
    "citation_quality": {{"score": X, "reasoning": "..."}},
    "overall_feedback": "Brief summary of report quality"
}}""",

    "sql": """You are evaluating an AI-generated SQL response.

**User Question**: {query}
**Database Schema**: {context}
**Generated SQL & Results**: {response}

Rate each dimension from 1-10:

1. **Query Correctness** (weight 2.0): Does the SQL correctly answer the question?
2. **Efficiency** (weight 1.0): Is the query reasonably optimized?
3. **Safety** (weight 1.5): Does it avoid dangerous operations (DML, injection)?
4. **Explanation Quality** (weight 1.0): Is the response clearly explained?

Respond in this exact JSON format:
{{
    "query_correctness": {{"score": X, "reasoning": "..."}},
    "efficiency": {{"score": X, "reasoning": "..."}},
    "safety": {{"score": X, "reasoning": "..."}},
    "explanation_quality": {{"score": X, "reasoning": "..."}},
    "overall_feedback": "Brief summary"
}}"""
}

# Dimension weights by response type
DIMENSION_WEIGHTS = {
    "chat": {
        "relevance": 1.5,
        "accuracy": 1.5,
        "helpfulness": 1.0,
        "safety": 1.0,
        "completeness": 0.5
    },
    "investigation": {
        "relevance": 1.5,
        "accuracy": 2.0,
        "depth": 1.5,
        "actionability": 1.0,
        "citation_quality": 1.0
    },
    "sql": {
        "query_correctness": 2.0,
        "efficiency": 1.0,
        "safety": 1.5,
        "explanation_quality": 1.0
    }
}


class ResponseEvaluator:
    """
    Evaluates AI responses using a judge model.

    Uses a fast, cheap model to grade responses on multiple dimensions,
    enabling quality tracking and self-improvement loops.
    """

    # Judge model - use cheapest available
    JUDGE_MODEL = "Google Gemini 2.0 Flash"
    FALLBACK_JUDGE = "Mistral Small 3.1"

    def __init__(self, model: str = None):
        """
        Initialize evaluator.

        Args:
            model: Override judge model (default: Gemini Flash)
        """
        self.model = model or self.JUDGE_MODEL
        self._import_gateway()

    def _import_gateway(self):
        """Lazy import to avoid circular dependencies."""
        try:
            from openrouter_gateway import chat_completion_with_fallback, calculate_request_cost
            self._chat_completion = chat_completion_with_fallback
            self._calculate_cost = calculate_request_cost
        except ImportError as e:
            logger.error(f"Failed to import openrouter_gateway: {e}")
            self._chat_completion = None
            self._calculate_cost = None

    def evaluate(
        self,
        query: str,
        response: str,
        context: str = "",
        response_type: str = "chat"
    ) -> EvaluationResult:
        """
        Evaluate an AI response.

        Args:
            query: Original user query/mission
            response: AI-generated response to evaluate
            context: Source context (documents, schema, etc.)
            response_type: Type of response (chat, investigation, sql)

        Returns:
            EvaluationResult with scores and feedback
        """
        start_time = time.time()

        # Validate response type
        if response_type not in EVALUATION_PROMPTS:
            response_type = "chat"

        # Build evaluation prompt
        prompt_template = EVALUATION_PROMPTS[response_type]
        eval_prompt = prompt_template.format(
            query=query[:2000],  # Truncate to avoid token limits
            context=context[:3000] if context else "No context provided",
            response=response[:3000]
        )

        # Call judge model
        if not self._chat_completion:
            return self._error_result(
                "Evaluator not available - gateway import failed",
                response_type,
                int((time.time() - start_time) * 1000)
            )

        try:
            result = self._chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": eval_prompt}],
                context=None,
                domain="general"
            )
        except Exception as e:
            logger.error(f"Judge model call failed: {e}")
            return self._error_result(
                str(e),
                response_type,
                int((time.time() - start_time) * 1000)
            )

        latency_ms = int((time.time() - start_time) * 1000)

        # Check for errors
        if "error" in result:
            return self._error_result(
                result.get("error", "Unknown error"),
                response_type,
                latency_ms
            )

        # Parse evaluation response
        eval_response = result.get("response", "")
        model_used = result.get("model", self.model)
        tokens_used = result.get("tokens_total", 0)

        try:
            parsed = self._parse_evaluation(eval_response, response_type)
        except Exception as e:
            logger.warning(f"Failed to parse evaluation: {e}")
            return self._fallback_evaluation(
                eval_response,
                response_type,
                latency_ms,
                model_used,
                tokens_used
            )

        # Calculate weighted overall score
        weights = DIMENSION_WEIGHTS.get(response_type, DIMENSION_WEIGHTS["chat"])
        dimensions = {}
        total_weighted = 0.0
        total_weight = 0.0

        for dim_name, dim_data in parsed.get("dimensions", {}).items():
            weight = weights.get(dim_name, 1.0)
            dimensions[dim_name] = EvaluationDimension(
                name=dim_name,
                score=dim_data.get("score", 5.0),
                reasoning=dim_data.get("reasoning", ""),
                weight=weight
            )
            total_weighted += dim_data.get("score", 5.0) * weight
            total_weight += weight

        overall_score = total_weighted / total_weight if total_weight > 0 else 5.0

        # Calculate cost
        cost = 0.0
        if self._calculate_cost:
            try:
                cost = self._calculate_cost(
                    model_used,
                    result.get("tokens_input", 0),
                    result.get("tokens_output", 0)
                )
            except Exception:
                pass

        return EvaluationResult(
            overall_score=overall_score,
            dimensions=dimensions,
            feedback=parsed.get("overall_feedback", ""),
            response_type=response_type,
            latency_ms=latency_ms,
            model_used=model_used,
            tokens_used=tokens_used,
            cost=cost
        )

    def _parse_evaluation(
        self,
        response: str,
        response_type: str
    ) -> Dict[str, Any]:
        """Parse JSON evaluation from judge model response."""
        # Try to extract JSON from response
        response = response.strip()

        # Handle markdown code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()

        # Parse JSON
        data = json.loads(response)

        # Extract dimensions
        dimensions = {}
        expected_dims = DIMENSION_WEIGHTS.get(response_type, DIMENSION_WEIGHTS["chat"]).keys()

        for dim in expected_dims:
            if dim in data:
                dim_data = data[dim]
                if isinstance(dim_data, dict):
                    dimensions[dim] = {
                        "score": float(dim_data.get("score", 5)),
                        "reasoning": str(dim_data.get("reasoning", ""))
                    }
                elif isinstance(dim_data, (int, float)):
                    dimensions[dim] = {"score": float(dim_data), "reasoning": ""}

        return {
            "dimensions": dimensions,
            "overall_feedback": data.get("overall_feedback", "")
        }

    def _fallback_evaluation(
        self,
        raw_response: str,
        response_type: str,
        latency_ms: int,
        model_used: str,
        tokens_used: int
    ) -> EvaluationResult:
        """Create fallback evaluation when parsing fails."""
        # Try to extract any numeric scores from response
        import re
        scores = re.findall(r'(\d+(?:\.\d+)?)\s*/\s*10', raw_response)
        avg_score = sum(float(s) for s in scores) / len(scores) if scores else 5.0

        weights = DIMENSION_WEIGHTS.get(response_type, DIMENSION_WEIGHTS["chat"])
        dimensions = {
            name: EvaluationDimension(
                name=name,
                score=avg_score,
                reasoning="Parsed from unstructured response",
                weight=weight
            )
            for name, weight in weights.items()
        }

        return EvaluationResult(
            overall_score=avg_score,
            dimensions=dimensions,
            feedback=raw_response[:500],
            response_type=response_type,
            latency_ms=latency_ms,
            model_used=model_used,
            tokens_used=tokens_used,
            error="Fallback evaluation - JSON parsing failed"
        )

    def _error_result(
        self,
        error: str,
        response_type: str,
        latency_ms: int
    ) -> EvaluationResult:
        """Create error result."""
        weights = DIMENSION_WEIGHTS.get(response_type, DIMENSION_WEIGHTS["chat"])
        dimensions = {
            name: EvaluationDimension(
                name=name,
                score=0.0,
                reasoning="Evaluation failed",
                weight=weight
            )
            for name, weight in weights.items()
        }

        return EvaluationResult(
            overall_score=0.0,
            dimensions=dimensions,
            feedback="Evaluation failed",
            response_type=response_type,
            latency_ms=latency_ms,
            model_used=self.model,
            error=error
        )

    def batch_evaluate(
        self,
        items: List[Dict[str, Any]],
        response_type: str = "chat"
    ) -> List[EvaluationResult]:
        """
        Evaluate multiple responses.

        Args:
            items: List of dicts with query, response, context keys
            response_type: Type for all items

        Returns:
            List of EvaluationResults
        """
        results = []
        for item in items:
            result = self.evaluate(
                query=item.get("query", ""),
                response=item.get("response", ""),
                context=item.get("context", ""),
                response_type=response_type
            )
            results.append(result)
            # Small delay to avoid rate limits
            time.sleep(0.5)

        return results


# Convenience function for single evaluation
def evaluate_response(
    query: str,
    response: str,
    context: str = "",
    response_type: str = "chat"
) -> Dict[str, Any]:
    """
    Convenience function to evaluate a single response.

    Returns dict instead of EvaluationResult for easier JSON handling.
    """
    evaluator = ResponseEvaluator()
    result = evaluator.evaluate(query, response, context, response_type)
    return result.to_dict()


# Quality threshold check
def passes_quality_gate(
    evaluation: EvaluationResult,
    threshold: float = 7.0
) -> bool:
    """
    Check if evaluation passes quality threshold.

    Args:
        evaluation: EvaluationResult to check
        threshold: Minimum acceptable score (default 7.0)

    Returns:
        True if passes, False otherwise
    """
    if evaluation.error:
        return False
    return evaluation.overall_score >= threshold
