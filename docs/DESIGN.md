# Design

This document is the behavior reference for `contracts/milestone_proof.py`
(class `MilestoneProof`). It defines the domain model, the state machines, the
consensus design and the exact data layout. If the code and this document
disagree, the code wins - but then one of them has a bug worth reporting.

## 1. Domain model

Three persistent record types plus two derived value types.

### Engagement

An agreement between one **client** (the creator) and one **worker** (the
first claimer). Terms - title, description, milestones and criteria - are
fixed at creation and never change afterwards.

| Field           | Type                | Meaning                                             |
| --------------- | ------------------- | --------------------------------------------------- |
| id              | str (`eng-<n>`)     | counter-based, never wallet-derived                  |
| client          | Address             | `gl.message.sender_address` at creation             |
| worker          | Address             | zero until claimed                                  |
| title           | str                 | cleaned (see §4)                                    |
| description     | str                 | cleaned; newlines and tabs allowed                  |
| milestone_ids   | DynArray[str]       | `M1..Mn` in creation order                          |
| terms_hash      | str                 | SHA-256 of the canonical terms (see §5)             |
| agreement_hash  | str                 | "" until claimed, then binds terms + parties        |
| status          | str                 | OPEN → ACTIVE → COMPLETED                           |

### Milestone

Stored separately (key `<engagement_id>/<milestone_id>`) so criteria carry
exactly one level of nesting.

| Field          | Type                   | Meaning                                       |
| -------------- | ---------------------- | --------------------------------------------- |
| id             | str (`M<k>`)           | position in the engagement                    |
| engagement_id  | str                    | back-reference                                |
| title          | str                    | cleaned                                       |
| criteria       | DynArray[Criterion]    | `C1..Ck`, frozen at creation                  |
| status         | str                    | AWAITING / ACCEPTED / CHANGES_REQUESTED / INCONCLUSIVE |
| attempt_count  | u32                    | submissions so far (capped, see Limits)       |
| submission_ids | DynArray[str]          | attempt history in order                      |

### Submission

One evidence URL, one evaluation. Records are keyed by `sub-<n>` and never
overwritten; a superseded or evaluated submission is history.

| Field            | Type                         | Meaning                                   |
| ---------------- | ---------------------------- | ----------------------------------------- |
| submission_id    | str (`sub-<n>`)              | counter-based                             |
| engagement_id    | str                          | binding                                   |
| milestone_id     | str                          | binding                                   |
| attempt_index    | u32                          | 1-based within the milestone              |
| worker           | Address                      | must equal the engagement worker          |
| url              | str                          | cleaned HTTPS URL                         |
| status           | str                          | PENDING / EVALUATED / SUPERSEDED          |
| requested_by     | Address                      | set when evaluated                        |
| agreement_hash   | str                          | snapshot for binding checks               |
| evidence_hash    | str                          | SHA-256 of the judged bytes               |
| evidence_size    | u32                          | byte length of the judged payload         |
| milestone_status | str                          | derived outcome ("" while pending)        |
| results          | DynArray[CriterionResult]    | per-criterion verdict + literal quote     |

### Derived value types

- `Criterion { id, text }` - frozen acceptance rule.
- `CriterionResult { criterion_id, status, reason_code, evidence_excerpt }` -
  one stored verdict row.

## 2. State machines

### Engagement

```
OPEN ──claim_engagement (worker ≠ client)──► ACTIVE
ACTIVE ──every milestone ACCEPTED──► COMPLETED (terminal)
```

COMPLETED is **derived** in `evaluate_submission` after each stored verdict:
code scans every milestone; any status other than ACCEPTED keeps the
engagement ACTIVE. No method sets COMPLETED directly.

### Milestone

```
AWAITING ──stored verdict──► ACCEPTED | CHANGES_REQUESTED | INCONCLUSIVE
CHANGES_REQUESTED ──new submission──► AWAITING (attempt + 1)
INCONCLUSIVE      ──new submission──► AWAITING (attempt + 1)
ACCEPTED (terminal for that milestone: further submissions revert)
```

`milestone_status` is derived from the criterion statuses by
`_derive_milestone_status` - never taken from the model:

1. any `UNVERIFIABLE` → INCONCLUSIVE
2. else any `NOT_MET` → CHANGES_REQUESTED
3. else all `MET` (and at least one criterion) → ACCEPTED

### Submission

```
PENDING ──stored verdict──► EVALUATED (terminal)
PENDING ──new attempt for the same milestone──► SUPERSEDED (terminal)
```

A SUPERSEDED submission keeps its row but can never be evaluated.

## 3. Consensus design

`evaluate_submission` runs the non-deterministic work inside
`gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`.

### Leader

1. Reads authoritative data from storage **before** the non-deterministic
   block (url, agreement hash, milestone title, criteria snapshot).
2. Fetches the URL independently, computes `evidence_hash` (SHA-256 of the
   exact bytes) and `evidence_size`.
3. Builds the fixed prompt (criteria and content are delimited *data*; the
   content is neutralized so it cannot forge the delimiters - see §6).
4. Asks the model for JSON, parses defensively, then **normalizes**:
   - exactly one result per original criterion, in order (else `[LLM_ERROR]`);
   - `reason_code` is set from the status by the contract;
   - `MET` without a substantive literal quote is downgraded to
     `UNVERIFIABLE` (never approves without evidence);
   - non-literal `NOT_MET` quotes are dropped.
5. Derives `milestone_status` from the statuses and proposes the full verdict
   (`VERDICT_KEYS`).

### Validator

A validator does **not** trust the proposal. It:

1. verifies structure, exact key sets, types and all bindings to storage
   (`_check_verdict_structure`);
2. re-runs the whole pipeline itself: fetches the URL, hashes the bytes,
   evaluates every criterion;
3. requires `evidence_hash` and `evidence_size` to match its own;
4. requires every leader quote to appear literally in **its own** fetched
   content, with the quote rules per status;
5. requires the status and reason code of **every** criterion to match its own
   evaluation exactly.

Only then the verdict is applied. Defense in depth: the verdict is
structurally re-checked once more right before storage.

### Error consensus

If the leader's run raises, the validator re-runs and compares error classes:
`[EXPECTED]` and `[EXTERNAL]` messages must match exactly; `[TRANSIENT]` only
needs the same class (one node may hit a 500 while another hits a 429).
Anything else means disagreement - nothing is stored.

## 4. Input hygiene (deterministic)

- Text is trimmed, must be non-empty, bounded per field, and free of control
  characters (newlines/tabs allowed only in the description).
- Criteria are distinct per milestone, case-insensitive, after whitespace
  normalization. Milestone titles are likewise distinct.
- URLs must be absolute HTTPS with a public multi-label host: no credentials,
  no IP literals, no single-label or reserved TLDs, and valid label syntax.
- Identifiers are counters (`eng-1`, `M1`, `C1`, `sub-1`), never derived from
  wallets or content, so records are unambiguous and enumerable.

## 5. Commitments (hashes)

All canonical JSON: sorted keys, no spaces, ASCII escapes, UTF-8.

- `terms_hash` = SHA-256 of `{v, title, description, milestones: [{id, title, criteria: [{id, text}]}]}`.
- `agreement_hash` = SHA-256 of `{v, engagement_id, client(hex), worker(hex), terms_hash}`.
- `evidence_hash` = SHA-256 of the exact fetched response bytes.

`samples/quickstart.py` reproduces all three with only the standard library;
the direct tests recompute them independently.

## 6. Prompt design (injection containment)

The model prompt is a fixed template. Worker-controlled content sits between
`<<DELIVERABLE>>` and `<<END_DELIVERABLE>>` and is pre-neutralized
(`"<<"` → `"< <"`) so the document can never contain the real closing marker.
The prompt states explicitly that the delimited block is untrusted data, never
instructions. Criteria and the milestone title are likewise data. The model
only chooses a status and a quote per criterion; the contract assigns reason
codes, applies quote rules, and derives the outcome. See
`docs/SECURITY.md` for what this does not defend against.

## 7. What actually bounds the limits

The constants are application choices; the real ceiling on a network is the
validators' model context window - the entire evidence payload plus all
criteria of a milestone go into one prompt - plus calldata/transaction limits
and gas. Worst-case single evaluation here: an 8-criterion milestone over a
200,000-byte payload produces a prompt of roughly 210,000 characters. Measure
on your target network before relying on the upper values, and prefer short,
objective criteria.
