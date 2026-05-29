# Quorum Consensus Engine — Deep Algorithm Review

This report focuses on Quorum’s **consensus algorithm** (routing → council execution → voting → reputation loop) and details the high-performance enhancements implemented in May 2026.

---

## 1) Core Algorithm (V2)

### 1.1 Speculative Tiered Execution
Quorum uses a "Local First" strategy but avoids the latency traps of slow local models.
1. **Staggered Start:** Starts Tier 1 (Local).
2. **Timeout:** If Tier 1 hasn't reached consensus within a timeout (default 2.5s), Tier 2 (Cheap) is launched in parallel.
3. **Consensus Harvesting:** As soon as any combination of models reaches the confidence threshold, execution stops.

### 1.2 Domain-Aware Voting
Consensus isn't "one size fits all."
- **Code/Logic:** High precision mode. Requires strong overlap to agree.
- **Prose/Creative:** High recall mode. Allows for different wording that means the same thing.

### 1.3 Hybrid Semantic Clustering
1. **Canonical Extraction:** Fast-paths Yes/No, A/B/C/D, and Numeric results.
2. **Semantic Embeddings:** Uses `all-MiniLM-L6-v2` locally or `text-embedding-3-small` remotely.
3. **Cohesion Pruning:** Calculates average-link similarity within clusters to prevent "bridge" responses from merging unrelated ideas.

---

## 2) Reputation & Learning

### 2.1 Non-Linear Update Logic
Quorum learns which models to trust. Reputation is now weighted by tier:
- **Premium (GPT-4/Claude-3.5):** 2.0x weight. Their hallucinations are penalized twice as hard; their correct answers are rewarded twice as much.
- **Cheap (Groq/DeepSeek):** 1.0x weight.
- **Local (Ollama):** 0.5x weight. Prevents uncalibrated local models from dominating the engine's long-term reputation profile.

### 2.2 Feedback Loop
1. **Tentative Outcomes:** Written to `pending_outcomes` after every query.
2. **Human-in-the-loop:** `quorum feedback <id> --score 1` confirms the consensus.
3. **Calibration:** Feedback scales the tentative deltas. A score of `-1.0` flips the reputation (penalizes those who agreed with the consensus).

---

## 3) Performance Benchmarks

Quorum is designed for low overhead. Aggregation of **100 models** completes in **<70ms** with less than **1MB** of memory overhead. The system scales sub-quadratically due to early cluster assignment and optimized tokenization.

---

## 4) Future Roadmap

- **Deliberation Round:** If a dispute is detected, council members will be given the top dissenting responses and asked to "re-evaluate" their position.
- **Streaming Consensus:** Sending a "Best Guess" consensus to the client while slower premium models are still generating.
- **Redis Semantic Cache:** Skipping the council entirely for semantically identical prompts.
