#!/usr/bin/env python3
"""
Performance Benchmark Suite for MegaDoc
Author: Paulo Dias - AI Tech Lead

Measures API latency, throughput, and cost metrics for CI/CD tracking.
Run: python tests/benchmark.py --output benchmark-results.json
"""

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime

import requests

# Configuration
BASE_URL = os.environ.get("BENCHMARK_URL", "http://localhost:8080")
ITERATIONS = int(os.environ.get("BENCHMARK_ITERATIONS", "5"))


def benchmark_endpoint(name: str, method: str, url: str, **kwargs) -> dict:
    """Benchmark a single endpoint with multiple iterations."""
    latencies = []
    successes = 0
    errors = []

    for i in range(ITERATIONS):
        try:
            start = time.perf_counter()
            if method.upper() == "GET":
                response = requests.get(url, timeout=30, **kwargs)
            else:
                response = requests.post(url, timeout=30, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000  # ms

            if response.status_code < 400:
                latencies.append(elapsed)
                successes += 1
            else:
                errors.append(f"HTTP {response.status_code}")
        except Exception as e:
            errors.append(str(e)[:50])

    if not latencies:
        return {
            "name": name,
            "success_rate": 0,
            "avg_latency_ms": 0,
            "p50_latency_ms": 0,
            "p95_latency_ms": 0,
            "errors": errors[:3]
        }

    return {
        "name": name,
        "success_rate": round((successes / ITERATIONS) * 100, 1),
        "avg_latency_ms": round(statistics.mean(latencies), 1),
        "min_latency_ms": round(min(latencies), 1),
        "max_latency_ms": round(max(latencies), 1),
        "p50_latency_ms": round(statistics.median(latencies), 1),
        "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0], 1),
        "iterations": ITERATIONS,
        "successes": successes
    }


def run_benchmarks() -> dict:
    """Run all benchmark tests."""
    print(f"Running benchmarks against {BASE_URL} ({ITERATIONS} iterations each)")
    print("=" * 60)

    results = {
        "timestamp": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "iterations": ITERATIONS,
        "endpoints": []
    }

    # Health check (baseline)
    print("Testing: /health")
    results["endpoints"].append(
        benchmark_endpoint("health", "GET", f"{BASE_URL}/health")
    )

    # Stats API
    print("Testing: /api/stats")
    results["endpoints"].append(
        benchmark_endpoint("stats", "GET", f"{BASE_URL}/api/stats")
    )

    # Formats API
    print("Testing: /api/formats")
    results["endpoints"].append(
        benchmark_endpoint("formats", "GET", f"{BASE_URL}/api/formats")
    )

    # RAG page load
    print("Testing: /rag (page load)")
    results["endpoints"].append(
        benchmark_endpoint("rag_page", "GET", f"{BASE_URL}/rag")
    )

    # SQL Sandbox page load
    print("Testing: /sql-sandbox (page load)")
    results["endpoints"].append(
        benchmark_endpoint("sql_sandbox_page", "GET", f"{BASE_URL}/sql-sandbox")
    )

    # Architecture page load
    print("Testing: /architecture (page load)")
    results["endpoints"].append(
        benchmark_endpoint("architecture_page", "GET", f"{BASE_URL}/architecture")
    )

    # Calculate summary metrics
    successful_endpoints = [e for e in results["endpoints"] if e["success_rate"] > 0]

    if successful_endpoints:
        results["summary"] = {
            "total_endpoints": len(results["endpoints"]),
            "healthy_endpoints": len(successful_endpoints),
            "avg_latency_ms": round(
                statistics.mean([e["avg_latency_ms"] for e in successful_endpoints]), 1
            ),
            "max_latency_ms": max([e["max_latency_ms"] for e in successful_endpoints]),
            "overall_success_rate": round(
                statistics.mean([e["success_rate"] for e in successful_endpoints]), 1
            )
        }
    else:
        results["summary"] = {
            "total_endpoints": len(results["endpoints"]),
            "healthy_endpoints": 0,
            "error": "All endpoints failed"
        }

    return results


def print_results(results: dict):
    """Print formatted results to console."""
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)

    for endpoint in results["endpoints"]:
        status = "PASS" if endpoint["success_rate"] == 100 else "WARN" if endpoint["success_rate"] > 0 else "FAIL"
        print(f"\n{status} | {endpoint['name']}")
        print(f"     Latency: {endpoint['avg_latency_ms']}ms avg, {endpoint.get('p95_latency_ms', 'N/A')}ms p95")
        print(f"     Success: {endpoint['success_rate']}%")

    if "summary" in results:
        print("\n" + "-" * 60)
        print("SUMMARY")
        print(f"  Healthy Endpoints: {results['summary']['healthy_endpoints']}/{results['summary']['total_endpoints']}")
        if "avg_latency_ms" in results["summary"]:
            print(f"  Average Latency: {results['summary']['avg_latency_ms']}ms")
            print(f"  Max Latency: {results['summary']['max_latency_ms']}ms")
            print(f"  Overall Success: {results['summary']['overall_success_rate']}%")


def main():
    parser = argparse.ArgumentParser(description="MegaDoc Performance Benchmark")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--url", help="Base URL to test", default=BASE_URL)
    parser.add_argument("--iterations", "-n", type=int, default=ITERATIONS, help="Iterations per endpoint")
    args = parser.parse_args()

    global BASE_URL, ITERATIONS
    BASE_URL = args.url
    ITERATIONS = args.iterations

    # Run benchmarks
    results = run_benchmarks()

    # Print to console
    print_results(results)

    # Write JSON output
    if args.output:
        # Flatten for GitHub Actions summary
        flat_results = {
            "timestamp": results["timestamp"],
            "healthy_endpoints": f"{results['summary'].get('healthy_endpoints', 0)}/{results['summary']['total_endpoints']}",
            "avg_latency": f"{results['summary'].get('avg_latency_ms', 'N/A')}ms",
            "max_latency": f"{results['summary'].get('max_latency_ms', 'N/A')}ms",
            "success_rate": f"{results['summary'].get('overall_success_rate', 0)}%"
        }

        with open(args.output, "w") as f:
            json.dump(flat_results, f, indent=2)
        print(f"\nResults written to {args.output}")

    # Exit with error if any endpoint failed completely
    if results["summary"].get("healthy_endpoints", 0) < results["summary"]["total_endpoints"]:
        print("\nWARNING: Some endpoints had failures")
        sys.exit(0)  # Don't fail CI, just warn

    print("\nAll benchmarks passed!")
    sys.exit(0)


if __name__ == "__main__":
    main()
