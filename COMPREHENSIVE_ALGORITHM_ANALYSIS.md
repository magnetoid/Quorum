# Comprehensive Quorum Consensus Engine Analysis
**Date: May 29, 2026**
**Version: 2.0 (High Performance)**

## Executive Summary
This document provides a comprehensive analysis of the Quorum consensus engine V2. Following the May 2026 refactor, the engine has transitioned to a **Speculative Tiered Execution** model with **Hybrid Semantic Clustering** and **Domain-Aware Thresholds**. All 91 core tests pass with 100% reliability.

---

## 1. V2 Algorithm Architecture

### 1.1 Speculative Execution Model
Quorum V2 eliminates the "slowest model" bottleneck through speculative parallelism.
1. **Tier 1 (Local/Fast)** is launched immediately.
2. If consensus is not reached within `QUORUM_TIER_STAGGER_SECONDS` (default 2.5s), **Tier 2 (Cheap)** is launched.
3. If still no consensus, **Tier 3 (Premium)** follows.
4. **Harvesting:** As soon as any subset of responses crosses the domain's confidence threshold, the engine harvests the result and shuts down pending tasks.

### 1.2 Hybrid Semantic Clustering (V2)
1. **Canonical Label Matching**: Fast-path for Yes/No, Choices, and Numbers.
2. **Semantic Embedding**: Uses local `sentence-transformers` or remote `OpenAI Embeddings` as a fallback.
3. **Cohesion Pruning**: After clustering, the engine calculates the average pairwise similarity. If a cluster's cohesion is lower than the `cluster_threshold`, it is pruned to prevent "bridge" responses from creating false consensus.

### 1.3 Domain-Aware Adaptive Thresholds
The voting engine dynamically adjusts its sensitivity based on the `domain`:
- **Code/Logic**: Cluster Threshold 0.4, Dispute Confidence 0.75.
- **Creative/Prose**: Cluster Threshold 0.15, Dispute Confidence 0.50.
- **Default/Factual**: Cluster Threshold 0.25, Dispute Confidence 0.66.

---

## 2. Telemetry & Performance

### 2.1 Latency Tracking
Every agent response now includes a `latency` field (float seconds). This allows the Router to identify and deprioritize models that are consistently slower than their tier average.

### 2.2 Memory & CPU
- **Baseline Memory**: ~23MiB.
- **Semantic Mode (Local)**: ~500MiB (loads `all-MiniLM-L6-v2`).
- **Semantic Mode (Remote)**: ~25MiB (no local model loaded).
- **Aggregation Speed**: <70ms for 100-model councils.

---

## 3. Reputation Loop (Non-Linear Learning)

Reputation is no longer a simple +/- 1.0 delta. It is now weighted by the model's tier:
- **Premium Models**: 2.0x weight. High-stake models have high-impact reputation changes.
- **Standard Models**: 1.0x weight.
- **Local Models**: 0.5x weight. Prevents uncalibrated local models from skewing the engine's long-term expert profiles.

---

## 4. Prioritized Roadmap (Next Generation)

### 🔴 Phase A: Deliberation Round
**Problem**: Models sometimes disagree due to minor semantic misunderstandings.
**Fix**: If a `disputed_flag` is raised, send the top 2 dissenting responses back to each council member and ask for a "re-evaluation."

### 🔴 Phase B: Organizational Semantic Cache
**Problem**: Large teams often ask the same architectural or legal questions.
**Fix**: Implement a Redis-backed semantic cache that returns the previous council's consensus if the new prompt is 95%+ semantically identical.

### 🔴 Phase C: Automated Council Pruning
**Problem**: Some models might be "dead weight" for specific domains.
**Fix**: Use the new latency and cost telemetry to automatically remove models that consistently fail to contribute to the winning cluster.
