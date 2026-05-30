# Roadmap: Quorum Continuous Improvement Algorithm (CIA)

## Objective
To transform Quorum from a static voting engine into a self-evolving AI decision layer that automatically optimizes its model selection, reputation weights, and domain routing based on historical performance and automated judging.

---

## 🏗️ Core Architecture

### 1. Automated Judge Module (`core/judge.py`)
- **Purpose:** Provide "Virtual Ground Truth" for queries where human feedback is absent.
- **Mechanism:** Periodically scan `pending_outcomes`. Use a "Golden Model" (e.g., GPT-4o or Claude 3.5 Sonnet) to review dissenting responses in a `disputed` state.
- **Action:** Generate an automated `apply_feedback` call based on the Judge's evaluation.

### 2. Bayesian Reputation Calibration (`core/reputation.py`)
- **Purpose:** Move beyond simple weighted sums to probability-calibrated weights.
- **Mechanism:** Implement **Brier Score** tracking. Measure the distance between a model's self-reported confidence (or presence in a winning cluster) and the final ground truth.
- **Outcome:** Penalize "Confident Hallucinations" exponentially more than "Uncertain Errors."

### 3. Dynamic Council Optimizer (`core/optimizer.py`)
- **Purpose:** Automatically prune "dead weight" models from specific domains to save cost and latency.
- **Mechanism:** Track the **Contribution Rate** (CR) — the percentage of times a model's response joins the winning cluster per domain.
- **Action:** If CR falls below a threshold for a specific domain, the model is moved to a "Reserved" tier for that domain.

### 4. Embedding-Based Adaptive Router (`core/router.py`)
- **Purpose:** Replace regex-based routing with semantic classification that learns from feedback.
- **Mechanism:** Use local embeddings (MiniLM) to represent domain boundaries.
- **Action:** When the Judge or a Human corrects a domain classification, update the domain's "centroid" embedding to improve future routing.

---

## 📅 Implementation Roadmap

### Phase 1: Database & Data Schema
- [ ] Add `model_stats` table to `storage/db.py` to track Contribution Rate (CR) and latency trends.
- [ ] Add `calibration` table to track Brier scores and confidence alignment.
- [ ] Implement `get_domain_stats` for the Optimizer to consume.

### Phase 2: The Automated Judge
- [ ] Implement `Judge` class in `core/judge.py`.
- [ ] Create a "Self-Supervision" background task that triggers every X queries or every N hours.
- [ ] Integrate Judge feedback into the `ReputationManager`.

### Phase 3: Adaptive Calibration
- [ ] Update `VotingEngine` to incorporate Brier-calibrated weights.
- [ ] Implement "Negation Safety 2.0": Penalize models that agree with a consensus that is later proven false by the Judge.

### Phase 4: Dynamic Optimization
- [ ] Implement the `CouncilOptimizer`.
- [ ] Add CLI command `quorum optimize` to review and apply suggested model pruning.
- [ ] Integrate Optimizer suggestions into the `Engine.run` model selection logic.

---

## 🧪 Verification & Metrics

- **Consensus Drift:** Measure if the number of `disputed` flags decreases over time for the same prompt set.
- **Cost Efficiency:** Measure the average cost per query as the Optimizer prunes expensive, low-contribution models.
- **Accuracy Benchmarking:** Compare the council consensus against a static "Golden Set" of known correct answers before and after 100 "learning" queries.

---

## 🛡️ Safety & Guardrails
- **Judge-Human Conflict:** Human feedback *always* overrides Automated Judge feedback.
- **Diversity Minimums:** The Optimizer will never prune a council below a minimum size (e.g., 3 models) to ensure consensus remains possible.
- **Sanity Checks:** If the Judge's reputation becomes uncalibrated, the system will pause automated feedback and alert the user.
