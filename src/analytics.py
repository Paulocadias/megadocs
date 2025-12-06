"""
Performance analytics module for document processing optimization.
Tracks detailed metrics on conversion performance, quality, and resource usage.
"""

import time
import statistics
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime
import json
from pathlib import Path
from threading import Lock

# Analytics storage path
ANALYTICS_FILE = Path(__file__).parent.parent / "data" / "analytics.json"
ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)

_lock = Lock()

@dataclass
class ConversionMetric:
    """Metric for a single document conversion."""
    timestamp: str
    file_type: str
    file_size_bytes: int
    duration_seconds: float
    success: bool
    error_type: Optional[str] = None
    chunks_generated: int = 0
    embedding_duration: float = 0.0

class AnalyticsEngine:
    """Engine for tracking and analyzing system performance."""
    
    def __init__(self):
        self._metrics: List[ConversionMetric] = []
        self._load_metrics()
        
    def _load_metrics(self):
        """Load metrics from disk."""
        if ANALYTICS_FILE.exists():
            try:
                with open(ANALYTICS_FILE, 'r') as f:
                    data = json.load(f)
                    self._metrics = [ConversionMetric(**m) for m in data]
            except Exception:
                self._metrics = []
                
    def _save_metrics(self):
        """Save metrics to disk."""
        with _lock:
            with open(ANALYTICS_FILE, 'w') as f:
                json.dump([asdict(m) for m in self._metrics], f)

    def track_conversion(self, file_type: str, size: int, duration: float, 
                        success: bool = True, error: str = None, 
                        chunks: int = 0, embed_time: float = 0.0):
        """
        Track a conversion event.
        
        Args:
            file_type: File extension
            size: File size in bytes
            duration: Processing time in seconds
            success: Whether conversion succeeded
            error: Error message if failed
            chunks: Number of RAG chunks generated
            embed_time: Time taken for embedding generation
        """
        metric = ConversionMetric(
            timestamp=datetime.now().isoformat(),
            file_type=file_type,
            file_size_bytes=size,
            duration_seconds=duration,
            success=success,
            error_type=error,
            chunks_generated=chunks,
            embedding_duration=embed_time
        )
        
        self._metrics.append(metric)
        
        # Keep only last 1000 metrics to prevent unlimited growth
        if len(self._metrics) > 1000:
            self._metrics = self._metrics[-1000:]
            
        self._save_metrics()
        
    def get_performance_report(self) -> Dict:
        """
        Generate performance analysis report.
        
        Returns:
            dict: Performance metrics and insights
        """
        if not self._metrics:
            return {"status": "no_data"}
            
        # Filter successful conversions
        successful = [m for m in self._metrics if m.success]
        failed = [m for m in self._metrics if not m.success]
        
        if not successful:
            return {
                "total_attempts": len(self._metrics),
                "failure_rate": 100.0
            }
            
        # Calculate latency stats
        durations = [m.duration_seconds for m in successful]
        avg_latency = statistics.mean(durations)
        p95_latency = statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
        
        # Calculate throughput (bytes/sec)
        throughputs = [m.file_size_bytes / max(m.duration_seconds, 0.001) for m in successful]
        avg_throughput = statistics.mean(throughputs)
        
        # Analyze by file type
        by_type = {}
        for m in successful:
            if m.file_type not in by_type:
                by_type[m.file_type] = []
            by_type[m.file_type].append(m.duration_seconds)
            
        type_performance = {
            t: {
                "avg_latency": round(statistics.mean(d), 3),
                "count": len(d)
            }
            for t, d in by_type.items()
        }
        
        return {
            "period_start": self._metrics[0].timestamp,
            "period_end": self._metrics[-1].timestamp,
            "total_processed": len(self._metrics),
            "success_rate": round(len(successful) / len(self._metrics) * 100, 1),
            "latency": {
                "avg_seconds": round(avg_latency, 3),
                "p95_seconds": round(p95_latency, 3),
                "min_seconds": round(min(durations), 3),
                "max_seconds": round(max(durations), 3)
            },
            "throughput": {
                "avg_mb_per_sec": round(avg_throughput / (1024*1024), 2)
            },
            "type_performance": type_performance,
            "rag_metrics": {
                "total_chunks": sum(m.chunks_generated for m in successful),
                "avg_embedding_time": round(statistics.mean([m.embedding_duration for m in successful if m.embedding_duration > 0] or [0]), 3)
            }
        }

# Global analytics instance
analytics = AnalyticsEngine()
