"""
Model performance tracking for AI/RAG pipelines.
Monitors embedding quality, token usage, and chunking efficiency.
"""

import time
import statistics
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from pathlib import Path
from threading import Lock
from datetime import datetime
import json

# Metrics storage path
MODEL_METRICS_FILE = Path(__file__).parent.parent / "data" / "model_metrics.json"
MODEL_METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)

_lock = Lock()

@dataclass
class ModelMetric:
    """Metric for a single AI model operation."""
    timestamp: str
    operation: str  # 'embedding', 'chunking', 'token_count'
    model_name: str
    input_size_chars: int
    output_size_items: int  # embeddings or chunks count
    duration_seconds: float
    tokens_processed: int = 0

class ModelMetricsEngine:
    """Engine for tracking AI model performance."""
    
    def __init__(self):
        self._metrics: List[ModelMetric] = []
        self._load_metrics()
        
    def _load_metrics(self):
        """Load metrics from disk."""
        if MODEL_METRICS_FILE.exists():
            try:
                with open(MODEL_METRICS_FILE, 'r') as f:
                    data = json.load(f)
                    self._metrics = [ModelMetric(**m) for m in data]
            except Exception:
                self._metrics = []
                
    def _save_metrics(self):
        """Save metrics to disk."""
        with _lock:
            with open(MODEL_METRICS_FILE, 'w') as f:
                json.dump([asdict(m) for m in self._metrics], f)

    def track_operation(self, operation: str, model: str, input_size: int, 
                       output_size: int, duration: float, tokens: int = 0):
        """
        Track an AI model operation.
        
        Args:
            operation: Type of operation (embedding, chunking, etc.)
            model: Name of the model used
            input_size: Size of input in characters
            output_size: Size of output (vectors, chunks)
            duration: Processing time in seconds
            tokens: Number of tokens processed
        """
        metric = ModelMetric(
            timestamp=datetime.now().isoformat(),
            operation=operation,
            model_name=model,
            input_size_chars=input_size,
            output_size_items=output_size,
            duration_seconds=duration,
            tokens_processed=tokens
        )
        
        self._metrics.append(metric)
        
        # Keep only last 1000 metrics
        if len(self._metrics) > 1000:
            self._metrics = self._metrics[-1000:]
            
        self._save_metrics()
        
    def get_performance_report(self) -> Dict:
        """
        Generate model performance report.
        
        Returns:
            dict: Performance metrics and insights
        """
        if not self._metrics:
            return {"status": "no_data"}
            
        ops = {}
        for m in self._metrics:
            if m.operation not in ops:
                ops[m.operation] = []
            ops[m.operation].append(m)
            
        report = {}
        for op_name, metrics in ops.items():
            durations = [m.duration_seconds for m in metrics]
            tokens = [m.tokens_processed for m in metrics]
            
            report[op_name] = {
                "count": len(metrics),
                "avg_latency": round(statistics.mean(durations), 4),
                "p95_latency": round(statistics.quantiles(durations, n=20)[18], 4) if len(durations) >= 20 else max(durations),
                "total_tokens": sum(tokens),
                "avg_tokens_per_req": round(statistics.mean(tokens), 1) if tokens else 0,
                "throughput_tokens_sec": round(sum(tokens) / sum(durations), 1) if sum(durations) > 0 else 0
            }
            
        return {
            "period_start": self._metrics[0].timestamp,
            "period_end": self._metrics[-1].timestamp,
            "operations": report
        }

# Global model metrics instance
model_metrics = ModelMetricsEngine()
