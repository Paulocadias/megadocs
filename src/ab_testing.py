"""
A/B Testing and Feature Flag Framework.
Enables data-driven experimentation and safe feature rollouts.
"""

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path
from threading import Lock
from datetime import datetime

# Experiments storage path
EXPERIMENTS_FILE = Path(__file__).parent.parent / "data" / "experiments.json"
EXPERIMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)

_lock = Lock()

@dataclass
class Experiment:
    """Definition of an A/B test experiment."""
    id: str
    name: str
    description: str
    variants: List[str]  # e.g., ["control", "variant_a"]
    weights: List[float]  # e.g., [0.5, 0.5]
    is_active: bool
    start_date: str
    end_date: Optional[str] = None
    metrics: Dict[str, Dict[str, int]] = None  # {variant: {metric: count}}

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {v: {"assignments": 0, "conversions": 0, "errors": 0} for v in self.variants}

class ExperimentEngine:
    """Engine for managing experiments and feature flags."""
    
    def __init__(self):
        self._experiments: Dict[str, Experiment] = {}
        self._load_experiments()
        
    def _load_experiments(self):
        """Load experiments from disk."""
        if EXPERIMENTS_FILE.exists():
            try:
                with open(EXPERIMENTS_FILE, 'r') as f:
                    data = json.load(f)
                    for exp_id, exp_data in data.items():
                        self._experiments[exp_id] = Experiment(**exp_data)
            except Exception:
                self._experiments = {}
                
    def _save_experiments(self):
        """Save experiments to disk."""
        with _lock:
            with open(EXPERIMENTS_FILE, 'w') as f:
                data = {k: asdict(v) for k, v in self._experiments.items()}
                json.dump(data, f, indent=2)

    def create_experiment(self, id: str, name: str, description: str, 
                         variants: List[str] = None, weights: List[float] = None):
        """Create a new experiment."""
        if variants is None:
            variants = ["control", "treatment"]
        if weights is None:
            weights = [0.5, 0.5]
            
        exp = Experiment(
            id=id,
            name=name,
            description=description,
            variants=variants,
            weights=weights,
            is_active=True,
            start_date=datetime.now().isoformat()
        )
        self._experiments[id] = exp
        self._save_experiments()
        return exp

    def get_assignment(self, experiment_id: str, user_id: str) -> str:
        """
        Get variant assignment for a user.
        Deterministic based on user_id hash.
        """
        exp = self._experiments.get(experiment_id)
        if not exp or not exp.is_active:
            return "control"
            
        # Deterministic hash
        hash_input = f"{experiment_id}:{user_id}"
        hash_val = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        normalized_hash = (hash_val % 100) / 100.0
        
        # Determine variant based on weights
        cumulative_weight = 0.0
        for i, weight in enumerate(exp.weights):
            cumulative_weight += weight
            if normalized_hash < cumulative_weight:
                variant = exp.variants[i]
                
                # Track assignment
                with _lock:
                    exp.metrics[variant]["assignments"] += 1
                
                return variant
                
        return exp.variants[0]  # Fallback to control

    def track_metric(self, experiment_id: str, variant: str, metric: str):
        """Track a conversion/success metric for a variant."""
        exp = self._experiments.get(experiment_id)
        if exp and exp.is_active and variant in exp.metrics:
            with _lock:
                if metric in exp.metrics[variant]:
                    exp.metrics[variant][metric] += 1
                else:
                    exp.metrics[variant][metric] = 1
            self._save_experiments()

    def get_results(self, experiment_id: str) -> Dict:
        """Get results for an experiment."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return {}
            
        results = {}
        for variant, metrics in exp.metrics.items():
            assignments = metrics.get("assignments", 0)
            conversions = metrics.get("conversions", 0)
            conversion_rate = (conversions / assignments * 100) if assignments > 0 else 0
            
            results[variant] = {
                "assignments": assignments,
                "conversions": conversions,
                "conversion_rate": round(conversion_rate, 2)
            }
            
        return {
            "experiment": exp.name,
            "status": "active" if exp.is_active else "completed",
            "results": results
        }

# Global experiment engine
experiments = ExperimentEngine()
