# API reference

All methods of `MilestoneProof`. Write methods run through consensus and can
revert with a classified prefix; view methods are free and read-only.

Error prefixes (first token of the revert message):

| Prefix        | Meaning                                              | Retry?            |
| ------------- | ---------------------------------------------------- | ----------------- |
| `[EXPECTED]`  | the call is invalid for the current state/input      | fix the call      |
| `[EXTERNAL]`  | the evidence source is unusable (HTTP error, empty, oversized, non-UTF-8) | fix the source |
| `[TRANSIENT]` | the source is temporarily unavailable (5xx/408/429)  | retry later       |
| `[LLM_ERROR]` | the model output was unusable                        | retry / reword    |

## Write methods

### `create_engagement(title, description, milestones) -> str`

Creates an engagement; the caller becomes its client. Returns `"eng-<n>"`.

- `title`: str, 1..`max_title_len` chars, no control characters.
- `description`: str, 1..`max_description_len` chars, newlines/tabs allowed.
- `milestones`: list of objects with **exactly** the keys `title` and
  `criteria`:
  - `title`: str, 1..`max_milestone_title_len` chars; titles must be distinct
    after whitespace normalization (case-insensitive).
  - `criteria`: list of str, `min_criteria`..`max_criteria` entries, each
    1..`max_criterion_len` chars, distinct case-insensitively.

Ids are assigned in order: `M1..Mn`, and `C1..Ck` within each milestone.
Terms are frozen; the values feed `terms_hash`.

```json
{
  "title": "Developer portal documentation",
  "description": "Produce the public developer docs.",
  "milestones": [
    {"title": "API documentation", "criteria": ["Documents GET /users", "..."]},
    {"title": "Release packaging", "criteria": ["Declares a signed release tag"]}
  ]
}
```

### `claim_engagement(engagement_id) -> None`

Claims an OPEN engagement. Caller becomes the worker; must not be the client.
First caller wins. Commits `agreement_hash` (binds terms + both parties).

### `submit_milestone(engagement_id, milestone_id, url) -> str`

Submits a public HTTPS evidence URL for one milestone. Worker only. Returns
`"sub-<n>"`.

- engagement must be ACTIVE; milestone must exist and not be ACCEPTED;
  attempts per milestone are capped (`max_attempts`).
- a still-PENDING previous attempt becomes SUPERSEDED (kept, not erased).
- `url`: absolute HTTPS, public multi-label host, no credentials, no IP
  literal, at most `max_url_len` characters.

### `evaluate_submission(submission_id) -> None`

Evaluates a PENDING submission. Client or worker only. Takes **only** the id -
terms, parties, milestone, criteria and url are read from storage. Runs the
leader/validator consensus pipeline; on success the submission becomes
EVALUATED with the full verdict, the milestone status is updated, and the
engagement becomes COMPLETED when every milestone is ACCEPTED.

A failed/pending/cancelled transaction means *no evaluation yet*. It is not
the business outcome INCONCLUSIVE.

## View methods

### `get_engagement(engagement_id) -> dict`

```json
{
  "found": true,
  "id": "eng-1",
  "client": "0x...",
  "worker": "0x... or empty while OPEN",
  "title": "...",
  "description": "...",
  "terms_hash": "64 hex chars",
  "agreement_hash": "64 hex chars or empty while OPEN",
  "status": "OPEN | ACTIVE | COMPLETED",
  "milestone_ids": ["M1", "M2"],
  "milestones": [
    {"id": "M1", "title": "...", "status": "AWAITING", "attempt_count": 0, "criterion_count": 3}
  ]
}
```

Not found: `{"found": false, "id": "eng-9"}`.

### `get_milestone(engagement_id, milestone_id) -> dict`

```json
{
  "found": true,
  "id": "M1",
  "engagement_id": "eng-1",
  "title": "API documentation",
  "criteria": [{"id": "C1", "text": "..."}],
  "status": "AWAITING | ACCEPTED | CHANGES_REQUESTED | INCONCLUSIVE",
  "attempt_count": 1,
  "submission_ids": ["sub-1"]
}
```

### `get_submission(submission_id) -> dict`

```json
{
  "found": true,
  "submission_id": "sub-1",
  "engagement_id": "eng-1",
  "milestone_id": "M1",
  "attempt_index": 1,
  "worker": "0x...",
  "url": "https://...",
  "status": "PENDING | EVALUATED | SUPERSEDED",
  "agreement_hash": "64 hex chars",
  "evidence_hash": "64 hex chars or empty",
  "evidence_size": 0,
  "milestone_status": "ACCEPTED | CHANGES_REQUESTED | INCONCLUSIVE or empty",
  "evaluation_requested_by": "0x... once EVALUATED, else empty",
  "results": [
    {
      "criterion_id": "C1",
      "status": "MET | NOT_MET | UNVERIFIABLE",
      "reason_code": "MEETS_CRITERION | REQUIREMENT_NOT_MET | INSUFFICIENT_EVIDENCE",
      "evidence_excerpt": "literal quote or empty"
    }
  ]
}
```

Only `status == "EVALUATED"` carries a valid verdict.

### `get_submission_id(engagement_id, milestone_id, attempt_index) -> str`

1-based lookup of one attempt; `""` when absent. This is the authoritative way
to find the submission created by a `submit_milestone` transaction.

### `get_milestone_submissions(engagement_id, milestone_id) -> list`

Every submission of a milestone, in attempt order (each item as in
`get_submission`). `[]` when the milestone does not exist.

### `get_limits() -> dict`

Every application limit plus `schema_version`. Read this once and validate
client-side instead of hard-coding numbers:

```json
{
  "schema_version": 1,
  "min_milestones": 1, "max_milestones": 10,
  "min_criteria": 1, "max_criteria": 8,
  "max_attempts": 3,
  "max_title_len": 160, "max_description_len": 4000,
  "max_milestone_title_len": 120, "max_criterion_len": 600,
  "max_url_len": 2048, "max_content_bytes": 200000,
  "min_excerpt_len": 8, "max_excerpt_len": 280
}
```

## Client recipe

1. `get_limits()` once; validate locally.
2. `create_engagement` (client) → `claim_engagement` (worker).
3. Per milestone: `submit_milestone` (worker) → read the id back with
   `get_submission_id(eng, milestone, attempt)` → `evaluate_submission`
   (either party).
4. Render results from `get_submission` + `get_engagement`; identify records
   by id, never by wallet history.
