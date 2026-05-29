# Learning loop (preview, v0.2)

> **Status:** design preview. The reputation update math described here is not yet implemented in `core/reputation.py`. This document captures the intended behavior so reviewers can validate the design before code lands. The reputation **read** path (weighting consensus votes) already works; the **write** path (updating scores from outcomes) is what's pending.

## Flow

1. User runs `quorum ask "Q" --domain finance` → council answers, voting picks consensus.
2. Each council member that lands in the consensus cluster receives a tentative `+1` for `(model, finance)`. Dissenters receive a tentative `-1`. *Tentative* means held in memory and not yet persisted.
3. If the user later runs `quorum feedback {query_id} --score +1`, the tentative scores are confirmed and written to `reputation` table.
4. If the user runs `quorum feedback {query_id} --score -1`, the signs are **flipped** (consensus members were wrong; dissenters were right) before persisting.
5. If no feedback comes in within a configurable window (default 24h), the tentative scores decay to zero — passive consensus alone gets a weak signal, not free credit.
6. Future queries in `finance` weight votes by accumulated reputation. This already works (`core/voting.py:VotingEngine.aggregate` accepts a `reputation_weights` dict).

## Self-healing

A provider that errors on >50% of `quorum doctor` pings within a 24h window is auto-disabled in `config.yaml` (`enabled: false`). The next `quorum doctor` shows it as `[dim](auto-disabled — re-enable manually)[/dim]`. Re-enable with `quorum config` → Providers → toggle.

## Why this design

- **Implicit feedback by default.** Most users will never run `quorum feedback`. Tentative reputation updates from consensus participation give the system *some* signal even without explicit user action.
- **Explicit feedback overrides.** When a user does grade a query, that signal is treated as ground truth (within the `+1`/`-1` envelope) and overrides the passive drift.
- **Per-domain.** A model that excels at `code` may be weak at `legal`. Reputation is keyed on `(model, domain)` so a single weak performance doesn't poison the model's standing elsewhere.
- **Decay.** Reputation accumulated months ago should weigh less than recent outcomes. Apply a multiplicative decay (default `0.99` per day) so the system can change its mind as model providers update.
- **Floor.** No model's weight ever drops below `0.1` — otherwise a new model entering the council starts at zero and never gets a fair chance to demonstrate it's improved.
