"""Performance benchmarks for VotingEngine to measure time and memory usage."""
import time
import memory_profiler  # type: ignore
from typing import Dict, List
from core.voting import VotingEngine
import json


def generate_test_responses(n_models: int, consensus_ratio: float = 0.8) -> Dict[str, str]:
    """Generate test responses with controlled consensus."""
    responses: Dict[str, str] = {}
    consensus_text = "The answer is 42. This is the correct response to the question."
    dissenting_texts = [
        "I believe the answer is 43, which I think is more accurate.",
        "After careful analysis, the correct answer should be 45.",
        "Based on my calculations, the answer is 47.",
    ]
    
    n_consensus = int(n_models * consensus_ratio)
    for i in range(n_models):
        model_id = f"model_{i:02d}"
        if i < n_consensus:
            responses[model_id] = consensus_text
        else:
            responses[model_id] = dissenting_texts[i % len(dissenting_texts)]
    return responses


@memory_profiler.profile
def benchmark_voting_scale() -> None:
    """Benchmark voting engine with increasing numbers of models."""
    engine = VotingEngine()
    model_counts = [5, 10, 20, 50, 100]
    results: List[Dict] = []
    
    print("\n=== Scalability Benchmark: Varying Model Counts ===\n")
    print(f"{'Models':>6} | {'Time(ms)':>8} | {'Clusters':>8} | {'Confidence':>10}")
    print("-" * 50)
    
    for n_models in model_counts:
        responses = generate_test_responses(n_models)
        start_time = time.perf_counter()
        result = engine.aggregate(responses, "factual")
        end_time = time.perf_counter()
        
        elapsed_ms = (end_time - start_time) * 1000
        n_clusters = len([c for c in result.get("clusters", [])]) if "clusters" in result else "N/A"
        print(f"{n_models:>6} | {elapsed_ms:>8.2f} | {n_clusters:>8} | {result['confidence']:>10.3f}")
        
        results.append({
            "models": n_models,
            "time_ms": elapsed_ms,
            "confidence": result["confidence"],
            "disputed": result["disputed_flag"],
        })
    
    with open("benchmark_scalability.json", "w") as f:
        json.dump(results, f, indent=2)


@memory_profiler.profile
def benchmark_edge_cases() -> None:
    """Benchmark edge case performance."""
    engine = VotingEngine()
    print("\n=== Edge Case Benchmarks ===\n")
    
    # Case 1: All models completely disagree
    responses_all_diff: Dict[str, str] = {
        "model_00": "Apple is the answer",
        "model_01": "Banana is correct",
        "model_02": "Citrus is the right choice",
        "model_03": "Date is the answer I think",
        "model_04": "Elderberry makes sense",
    }
    
    start = time.perf_counter()
    result = engine.aggregate(responses_all_diff, "factual")
    elapsed = (time.perf_counter() - start) * 1000
    print(f"All models disagree: {elapsed:.2f}ms, disputed={result['disputed_flag']}")
    
    # Case 2: All models agree completely
    responses_all_same = {f"model_{i:02d}": "The consensus answer is clear." for i in range(50)}
    start = time.perf_counter()
    result = engine.aggregate(responses_all_same, "factual")
    elapsed = (time.perf_counter() - start) * 1000
    print(f"All models agree (50): {elapsed:.2f}ms, confidence={result['confidence']:.3f}")
    
    # Case 3: Long responses
    long_text = "This is a very long response " * 100  # ~2000 characters
    responses_long = {f"model_{i:02d}": long_text for i in range(10)}
    start = time.perf_counter()
    result = engine.aggregate(responses_long, "factual")
    elapsed = (time.perf_counter() - start) * 1000
    print(f"Long responses (10): {elapsed:.2f}ms, confidence={result['confidence']:.3f}")


if __name__ == "__main__":
    benchmark_voting_scale()
    benchmark_edge_cases()
