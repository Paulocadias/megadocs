"""
Smart Model Router for cost optimization.

Routes prompts to appropriate AI models based on complexity analysis:
- Simple prompts (greetings, summaries) -> Fast, cheap models (Gemini Flash)
- Complex prompts (analysis, reasoning) -> Powerful models (Gemini Pro)

Usage:
    from router import get_router

    router = get_router()
    decision = router.route("Summarize this document")
    # decision.model = "Google Gemini 2.0 Flash" (simple task)

    decision = router.route("Analyze the legal implications of...")
    # decision.model = "Google Gemini 2.5 Pro" (complex task)
"""

import re
import os
import logging
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to load YAML config, fall back to defaults
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logger.warning("PyYAML not installed, using default router configuration")


class ComplexityLevel(Enum):
    """Prompt complexity levels."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    model: str                              # Selected model name
    complexity: ComplexityLevel             # Detected complexity
    confidence: float                       # 0.0 - 1.0
    reasoning: str                          # Why this model was selected
    fallback_model: Optional[str] = None    # Model to use if primary fails
    signals: List[str] = field(default_factory=list)  # Signals that influenced decision

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "model": self.model,
            "complexity": self.complexity.value,
            "confidence": round(self.confidence, 2),
            "reasoning": self.reasoning,
            "fallback_model": self.fallback_model,
            "signals": self.signals
        }


class ModelRouter:
    """
    Intelligent model router based on prompt complexity.

    Analyzes prompts using multiple signals:
    - Word count
    - Pattern matching (simple vs complex indicators)
    - Domain detection
    - Technical term density
    - Context size
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize router with configuration.

        Args:
            config_path: Path to models.yaml config file (optional)
        """
        self.config = self._load_config(config_path)
        self._compile_patterns()
        logger.info("ModelRouter initialized")

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load routing configuration from YAML or use defaults."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "models.yaml"

        if YAML_AVAILABLE and Path(config_path).exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    logger.info(f"Loaded router config from {config_path}")
                    return config
            except Exception as e:
                logger.warning(f"Failed to load config: {e}, using defaults")

        return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """Default configuration if models.yaml not found."""
        return {
            "models": {
                "simple": {
                    "primary": "Google Gemini 2.0 Flash",
                    "fallback": "Meta Llama 3.3 70B",
                    "description": "Fast responses for simple queries"
                },
                "moderate": {
                    "primary": "DeepSeek V3",
                    "fallback": "Google Gemini 2.0 Flash",
                    "description": "Balanced performance for standard queries"
                },
                "complex": {
                    "primary": "Google Gemini 2.5 Pro",
                    "fallback": "DeepSeek V3",
                    "description": "High capability for complex analysis"
                }
            },
            "thresholds": {
                "simple_max_words": 50,
                "complex_min_words": 150,
                "technical_term_threshold": 4
            },
            "patterns": {
                "simple_indicators": [
                    r"^(what|who|when|where|how many|how much)\b",
                    r"^(summarize|summary)\b",
                    r"^(list|enumerate)\b",
                    r"^(define|definition)\b",
                    r"^(explain briefly|quick)\b",
                    r"^(hi|hello|hey|thanks|thank you)\b",
                    r"^(yes|no|ok|okay)\b"
                ],
                "complex_indicators": [
                    r"\b(analyze|analysis|evaluate|assessment)\b",
                    r"\b(compare|contrast|differentiate)\b",
                    r"\b(implications|consequences|impact)\b",
                    r"\b(trade-?offs?|pros and cons)\b",
                    r"\b(legal|compliance|regulatory|statute)\b",
                    r"\b(medical|clinical|diagnosis|treatment)\b",
                    r"\b(multi-?step|detailed|comprehensive|thorough)\b",
                    r"\b(why|reasoning|rationale|justify)\b",
                    r"\b(strategy|strategic|recommend)\b"
                ]
            },
            "domain_overrides": {
                "legal": {"min_complexity": "moderate"},
                "medical": {"min_complexity": "moderate"}
            }
        }

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        patterns = self.config.get("patterns", {})

        self._simple_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in patterns.get("simple_indicators", [])
        ]

        self._complex_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in patterns.get("complex_indicators", [])
        ]

        # Technical terms pattern
        self._technical_pattern = re.compile(
            r'\b(API|SDK|algorithm|implementation|architecture|'
            r'optimization|latency|throughput|scalability|'
            r'compliance|regulation|jurisdiction|'
            r'diagnosis|prognosis|contraindication|'
            r'encryption|authentication|authorization)\b',
            re.IGNORECASE
        )

    def route(
        self,
        prompt: str,
        domain: str = "general",
        context_length: int = 0,
        force_model: Optional[str] = None
    ) -> RoutingDecision:
        """
        Determine best model for the given prompt.

        Args:
            prompt: User's message/question
            domain: Domain profile (general, legal, medical, technical)
            context_length: Length of RAG context in characters
            force_model: If set, bypass routing and use this model

        Returns:
            RoutingDecision with selected model and metadata
        """
        # Allow explicit model override
        if force_model:
            return RoutingDecision(
                model=force_model,
                complexity=ComplexityLevel.MODERATE,
                confidence=1.0,
                reasoning="Model explicitly specified by user",
                fallback_model=None,
                signals=["user_override"]
            )

        # Analyze complexity
        complexity, confidence, signals = self._analyze_complexity(
            prompt, domain, context_length
        )

        # Apply domain overrides
        complexity = self._apply_domain_override(complexity, domain)

        # Get model for complexity level
        models = self.config["models"].get(
            complexity.value,
            self.config["models"]["moderate"]
        )

        return RoutingDecision(
            model=models["primary"],
            complexity=complexity,
            confidence=confidence,
            reasoning=self._generate_reasoning(complexity, signals),
            fallback_model=models.get("fallback"),
            signals=signals
        )

    def _analyze_complexity(
        self,
        prompt: str,
        domain: str,
        context_length: int
    ) -> Tuple[ComplexityLevel, float, List[str]]:
        """
        Analyze prompt complexity using multiple signals.

        Returns:
            Tuple of (ComplexityLevel, confidence_score, signals_list)
        """
        score = 0.0
        signals = []
        thresholds = self.config.get("thresholds", {})

        # Signal 1: Word count
        word_count = len(prompt.split())
        simple_max = thresholds.get("simple_max_words", 50)
        complex_min = thresholds.get("complex_min_words", 150)

        if word_count <= simple_max:
            score -= 1.0
            signals.append(f"short_prompt({word_count}w)")
        elif word_count >= complex_min:
            score += 1.5
            signals.append(f"long_prompt({word_count}w)")

        # Signal 2: Simple pattern matching
        prompt_lower = prompt.lower()
        for pattern in self._simple_patterns:
            if pattern.search(prompt_lower):
                score -= 0.6
                signals.append("simple_pattern")
                break

        # Signal 3: Complex pattern matching
        complex_matches = 0
        for pattern in self._complex_patterns:
            if pattern.search(prompt_lower):
                complex_matches += 1
                score += 0.5

        if complex_matches > 0:
            signals.append(f"complex_patterns({complex_matches})")

        # Signal 4: Technical terms
        tech_terms = len(self._technical_pattern.findall(prompt))
        tech_threshold = thresholds.get("technical_term_threshold", 4)

        if tech_terms >= tech_threshold:
            score += 0.8
            signals.append(f"technical_terms({tech_terms})")

        # Signal 5: Question complexity (multiple questions = complex)
        question_marks = prompt.count('?')
        if question_marks >= 3:
            score += 0.5
            signals.append(f"multi_question({question_marks})")

        # Signal 6: Context size (large context = harder task)
        if context_length > 15000:
            score += 0.5
            signals.append("large_context")
        elif context_length > 30000:
            score += 1.0
            signals.append("very_large_context")

        # Map score to complexity level
        if score <= -0.5:
            return ComplexityLevel.SIMPLE, min(0.9, 0.6 + abs(score) * 0.1), signals
        elif score < 1.5:
            return ComplexityLevel.MODERATE, 0.7, signals
        else:
            return ComplexityLevel.COMPLEX, min(0.95, 0.6 + score * 0.08), signals

    def _apply_domain_override(
        self,
        complexity: ComplexityLevel,
        domain: str
    ) -> ComplexityLevel:
        """Apply domain-specific minimum complexity rules."""
        overrides = self.config.get("domain_overrides", {})
        domain_config = overrides.get(domain.lower(), {})

        min_complexity = domain_config.get("min_complexity")
        if min_complexity:
            min_level = ComplexityLevel(min_complexity)
            # Ensure complexity is at least the minimum for this domain
            if complexity.value < min_level.value:
                return min_level

        return complexity

    def _generate_reasoning(
        self,
        complexity: ComplexityLevel,
        signals: List[str]
    ) -> str:
        """Generate human-readable reasoning for routing decision."""
        signal_summary = ", ".join(signals[:3]) if signals else "default"

        if complexity == ComplexityLevel.SIMPLE:
            return f"Simple query detected ({signal_summary}); using fast model"
        elif complexity == ComplexityLevel.MODERATE:
            return f"Standard query ({signal_summary}); balanced model selected"
        else:
            return f"Complex analysis required ({signal_summary}); using high-capability model"

    def get_available_models(self) -> Dict[str, List[str]]:
        """Get all available models by complexity level."""
        result = {}
        for level, config in self.config.get("models", {}).items():
            result[level] = [config["primary"]]
            if config.get("fallback"):
                result[level].append(config["fallback"])
        return result


# Singleton instance
_router: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    """Get singleton ModelRouter instance."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def reset_router() -> None:
    """Reset singleton router (useful for testing or config reload)."""
    global _router
    _router = None
