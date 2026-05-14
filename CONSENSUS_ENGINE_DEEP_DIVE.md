# Quorum Consensus Engine — Deep Algorithm Review & Improvement Report

This report focuses on Quorum’s **consensus algorithm** (routing → council execution → voting → reputation loop) and highlights where the methodology can be significantly improved without breaking the current UX/API contract.

**Scope:** `core/engine.py`, `core/voting.py`, `core/router.py`, `storage/db.py`, CLI/REST surfaces.

---

## 1) What Quorum’s consensus algorithm does today (V1)

### 1.1 Execution pipeline
1. **Domain routing** (`core/router.py`) chooses a domain using word-boundary keyword hits (or caller-provided `--domain`).
2. **Tiered council execution** (`core/engine.py`) runs models in tiers (`local → cheap → premium`) until:
   - the computed consensus confidence meets the tier threshold, or
   - the accumulated estimated cost reaches the query budget.
3. **Voting v1** (`core/voting.py`) clusters responses by **token-level Jaccard similarity** using greedy single-link clustering.
4. **Consensus selection** chooses the highest-weight cluster (reputation-weighted); returns the “anchor” answer from within that cluster.
5. **Reputation loop** persists “pending outcomes” for later confirmation via `quorum feedback`.

This is a strong baseline: it is fast, cheap, and makes disagreement visible.

---

## 2) The biggest algorithmic failure modes (and why they matter)

### 2.1 Lexical similarity ≠ semantic agreement (critical)
`core/voting.py` tokenizes with `\w+` and uses Jaccard overlap. This breaks on:
- **Negation**: “X is true” vs “X is not true” share most tokens.
- **Paraphrases**: “Because A, therefore B” vs “B follows from A” may share few tokens.
- **Numeric disagreement**: two answers that only differ by one number can still be nearly identical lexically.

**Impact:** false “consensus” and false “dispute” are both possible, depending on wording.

### 2.2 Greedy single-link clustering chains unrelated answers (high)
Single-link means: if A ~ B and B ~ C, then A, B, C cluster together even if A !~ C.

With a low `cluster_threshold` (0.25), “bridge” responses can incorrectly merge clusters.

**Impact:** one verbose answer that mentions multiple options can glue everything into a single “consensus cluster”.

### 2.3 Confidence is under-specified (high)
Confidence is currently:

`cluster_weight(top_cluster) / total_weight`

But this ignores:
- **cluster cohesion** (are the cluster members truly similar?)
- **separation** (is the #2 cluster close behind?)
- **abstentions** (models that say “I don’t know”)
- **correlated models** (multiple models from the same family/provider behave similarly)

**Impact:** confidence can be inflated or depressed for the wrong reasons.

### 2.4 Reputation weights are unbounded and not calibrated (medium)
Reputation is a cumulative additive score per `(model, domain)`.

Problems:
- it can grow unbounded, letting one high-score model dominate confidence.
- negative scores collapse to a fixed floor (0.1), so “known-bad” models still influence votes.
- it does not model *difficulty* or *task type*, only domain.

**Impact:** long-run drift toward over-trusting a single model; poor transfer between easy/hard queries.

### 2.5 Training on ambiguous outcomes degrades learning (fixed)
If the engine records outcomes when `disputed_flag=True`, it can punish “dissenters” even when there is no stable consensus.

**Status:** fixed by only recording pending outcomes when the result is not disputed.

---

## 3) High-leverage improvements (recommended roadmap)

Below are improvements ordered by **(value / complexity)**.

### Improvement A — Better clustering without adding any ML (low complexity, high value)
Goal: keep V1 cheap, but reduce obvious clustering errors.

1. **Stopword + negation handling**
   - Remove common stopwords.
   - Preserve a negation feature: if a response contains `not`, `never`, `no`, treat it as a signal.

2. **Switch clustering to average-link (or require cluster cohesion)**
   - Compute pairwise similarities.
   - Build a graph with edges above threshold.
   - Extract connected components *but require* that the average within-cluster similarity exceeds a cohesion threshold.
   - If cohesion is low, mark disputed.

3. **Vote on canonical “answer key” when possible**
   - For short answers (booleans, numbers, multiple choice), first extract a canonical label.
   - Cluster/vote on that label, not the entire text.

Success criteria:
- fewer false cluster merges in adversarial “bridge” prompts.
- stable `disputed_flag` on purposely contradictory answers.

### Improvement B — Two-stage voting: lexical first, semantic only on dispute (medium complexity, huge value)
Goal: preserve low cost most of the time.

Algorithm:
1. Run current V1 voting.
2. If `disputed_flag=False` and confidence ≥ threshold → accept.
3. If disputed or low confidence → run a **judge** (cheap) to:
   - cluster semantically,
   - identify contradictions,
   - optionally produce a *short* consensus synthesis.

Key detail: keep the output schema the same. Populate `disputed` with judge clustering summary instead of raw dumps.

Success criteria:
- semantic contradictions (“X” vs “not X”) reliably produce disputed results.
- fewer cases of “Models disagreed” when models are paraphrasing the same point.

### Improvement C — Deliberation round only for controversial cases (medium complexity)
Goal: reduce disagreements that are caused by ambiguity, not true uncertainty.

When disputed:
1. ask each model to critique the strongest opposing response.
2. ask each model to update its answer (or explicitly abstain).
3. re-run voting.

This mirrors “structured deliberation” used in strong multi-agent systems.

Success criteria:
- increased convergence rate on queries with initially shallow disagreement.
- the disputed zone becomes shorter and more actionable.

### Improvement D — Calibrated confidence (medium)
Add additional metrics (without changing the existing fields):
- `agreement_ratio` (unweighted)
- `top2_gap` (difference between top and second cluster weight)
- `cohesion` (avg similarity within top cluster)
- `entropy` (vote distribution)

Then produce a calibrated `confidence` from these signals.

Success criteria:
- confidence correlates with real correctness on a fixed eval set.
- lower “overconfident wrong” frequency.

### Improvement E — Reputation as a bounded reliability model (medium)
Replace raw additive scores with a bounded mapping:

`weight = clamp(sigmoid(score / T) * scale, min_w, max_w)`

Or use an Elo-like update on confirmed feedback.

Success criteria:
- no single model can dominate without consistent confirmations.
- stable behavior over long runs.

### Improvement F — Correlation-aware ensembling (high)
Treat models from the same provider/family as correlated.

Approach:
- compute historical agreement rates between models.
- downweight highly correlated pairs.
- select councils with maximal diversity per budget.

Success criteria:
- better robustness when multiple “similar” models share the same blind spot.

---

## 4) Concrete bugs / design issues to address next

### 4.1 Output labelling mismatch in disputed mode
In `core/voting.py`, disputed mode labels the winning cluster as `minority`. This is confusing: it is the *leading cluster*, not a minority.

Recommended change:
- rename votes to `leader` (top cluster), `outlier` (non-top cluster), and keep `anchor/consensus/dissent` for non-disputed mode.

### 4.2 Budget enforcement is reactive
The engine stops after `total_cost >= budget`, which can overshoot.

Recommended change:
- estimate worst-case tier cost before running a tier (prompt tokens × max_tokens × pricing).
- if estimate would exceed remaining budget, skip that tier or reduce max_tokens.

---

## 5) Suggested implementation plan (minimal breakage)

1. Implement Improvement A (better clustering + canonical extraction) inside `core/voting.py`.
2. Add Improvement B as `VotingEngineV2` (judge-on-dispute) behind a config flag.
3. Add confidence calibration metrics but keep existing schema stable.
4. Evolve reputation into bounded reliability.
5. Add deliberation round for controversial cases.

---

## 6) Backward compatibility notes

All improvements can keep the current API stable by:
- leaving the output keys unchanged (`consensus`, `confidence`, `disputed`, `disputed_flag`, `agents`, `domain`, `cost`, `query_id`)
- optionally adding new fields only under `quorum` (OpenAI-compatible route already has a `quorum` envelope)

