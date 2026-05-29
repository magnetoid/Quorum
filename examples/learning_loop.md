# Quorum Learning Loop: From Hallucination to Expertise

Quorum doesn't just ask models for answers; it **evaluates their performance over time.** This document illustrates how the reputation loop turns a generic council into a domain-expert panel.

---

## 1. The Initial State: Zero-Knowledge
When you first install Quorum, all models have a baseline reputation.
- `gpt-4o`: 1.0
- `claude-3-5-sonnet`: 1.0
- `ollama/llama3.2`: 1.0

## 2. The Feedback Cycle

### Step A: The Query
You ask a complex technical question:
`quorum ask "Explain the trade-offs of Raft vs Paxos." --domain architecture`

### Step B: The Voting
- **Model A & B** agree on a detailed consensus.
- **Model C** hallucinates a non-existent protocol feature.
- **Quorum** selects the A/B consensus and records a **Pending Outcome**.

### Step C: Human Confirmation
You verify the answer is correct and run:
`quorum feedback <query_id> --score 1.0`

### Step D: Non-Linear Reputation Update
Quorum applies the deltas based on the model's tier:
- **Model A (Premium)**: +2.0 reputation (expert confirmation).
- **Model B (Cheap)**: +1.0 reputation.
- **Model C (Dissent)**: -2.0 reputation (penalized for hallucination).

---

## 3. The Result: Domain Expertise

After 50 technical queries, your `architecture` domain reputation might look like this:
```bash
quorum models --stats
```
| Model | Score (Architecture) |
| :--- | :--- |
| **claude-3-5-sonnet** | **+24.5** (Reliable Expert) |
| **gpt-4o** | **+18.0** |
| **ollama/llama3.2** | **-5.0** (Frequently Dissents) |

## 4. Why This Matters
In the next query, the **Expert** (`claude-3-5-sonnet`) has significantly more "voting power." Even if two cheaper models disagree, the engine will favor the high-reputation expert, drastically reducing the hallucination rate for your specific use cases.
