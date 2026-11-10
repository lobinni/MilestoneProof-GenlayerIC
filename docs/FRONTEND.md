# Frontend separation

This repository is **contract-only**. That is deliberate: when a program asks
for "the Intelligent Contract", the submission is exactly
`contracts/milestone_proof.py` - no UI, no app server, no build pipeline. Any
frontend lives in its own repository and talks to the deployment over the
network.

## What to submit

| Artifact                         | Include? | Why                                            |
| -------------------------------- | -------- | ---------------------------------------------- |
| `contracts/milestone_proof.py`   | always   | the complete deployable deliverable            |
| `deployments/`                   | recommended | network records: address, source hash, verification |
| `README.md`, `docs/`             | optional | reviewer-facing documentation                  |
| `tests/`, `samples/`             | optional | proof the contract is exercisable              |
| `requirements.txt`, `pytest.ini`, `gltest.config.yaml` | optional | pins the toolchain used in tests |
| any frontend / UI code           | **never**| keep it in a separate repository               |

Minimal package (built by a script so it can never drift):

```bash
bash tools/package_submission.sh          # builds ./milestone-proof-submission/
sha256sum contracts/milestone_proof.py    # record the source commitment
```

To publish the project to GitHub staging ONLY the contract tree (no web
files), follow `docs/GITHUB.md`.

## The integration contract for a separate frontend

A frontend needs exactly four kinds of information, all available on chain:

1. **Limits** - call `get_limits()` once at startup; validate forms with it
   (counts, character lengths, URL length). Do not hard-code the numbers.
2. **Writes** - `create_engagement`, `claim_engagement`, `submit_milestone`,
   `evaluate_submission` via the GenLayer JS SDK (`genlayer-js`) with the
   connected wallet.
3. **Reads** - `get_engagement` / `get_milestone` / `get_submission` /
   `get_submission_id` / `get_milestone_submissions` for rendering.
4. **Outcome interpretation** - a receipt holds a valid verdict only when
   `status === "EVALUATED"`. A pending or reverted transaction is *no
   evaluation yet*, never the business outcome `INCONCLUSIVE`.

Payload shapes for every method: `docs/API.md`. Hashing rules if the frontend
wants to pre-compute commitments: `docs/DESIGN.md` §5 and
`samples/quickstart.py` (stdlib reference implementation).

## Recommended repository split

```
milestone-proof/            <- this repository (submit from here)
  contracts/milestone_proof.py
  tests/ docs/ samples/ ...

milestone-proof-app/        <- separate repository (never submitted)
  Next.js / Vite app using genlayer-js
  reads contract address + ABI schema from its own config
```

The app repository should pin the deployed contract address and the
`sha256sum` of the contract source it was built against, so reviewers can
match UI behavior to the exact on-chain code (see "Deploying" in the README).

## UX guidance distilled from the contract

- Show the four engagement states as a pipeline: OPEN → ACTIVE → (per
  milestone) AWAITING → ACCEPTED / CHANGES_REQUESTED / INCONCLUSIVE →
  COMPLETED.
- Surface the evidence: per criterion, show status, the fixed reason code and
  the literal quote; show `evidence_hash` next to the URL so anyone can verify
  what bytes were judged.
- Disable `RESUBMIT` once a milestone is ACCEPTED or attempts are exhausted
  (read `attempt_count` + `max_attempts`).
- Never let users "pick" criterion ids or statuses in an evaluation form -
  `evaluate_submission` takes only the submission id by design.
