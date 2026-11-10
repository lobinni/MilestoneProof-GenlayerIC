# Milestone Proof

An [Intelligent Contract](https://docs.genlayer.com/developers/intelligent-contracts) for [GenLayer](https://www.genlayer.com) that turns milestone-based work engagements into verifiable outcomes.

A client publishes an engagement made of ordered **milestones**, each with acceptance criteria that are frozen before any work starts. A worker claims the engagement and, per milestone, delivers a public HTTPS URL as evidence. GenLayer's validators then evaluate the delivered content **against exactly those criteria**, and the verdict is stored per criterion with literal evidence quotes and the SHA-256 of the exact bytes that were judged. The engagement completes when every milestone is `ACCEPTED`.

No payments, tokens, escrow, fees, reputation or arbitration are part of it.

> **Submission packaging.** The deployable artifact is `contracts/milestone_proof.py` (one file, one contract class). `tests/`, `docs/` and `samples/` are developer material. There is **no frontend in this repository**: see `docs/FRONTEND.md` for how to build one separately and what exactly to submit. When a submission requires only the Intelligent Contract, package `contracts/` alone (see [Submitting](#submitting)).

> **Status:** deployed on **GenLayer Studio** at
> [`0x8ADE76f942b221c799c9529449a9B8feFbd419BF`](https://explorer-studio.genlayer.com/address/0x8ADE76f942b221c799c9529449a9B8feFbd419BF)
> (record + verification steps: [deployments/](deployments/README.md)). Tested
> against the direct-mode model (`genlayer-test`) with a mocked-consensus
> suite, plus an offline pure-logic oracle (100 tests) and read-only probes
> against the live deployment. Model behavior at the largest limits is
> **unmeasured** on a network (see [Limits](#limits)).

## Deployments

| Network           | Chain id | Contract address                               | Record                                      |
| ----------------- | -------- | ---------------------------------------------- | ------------------------------------------- |
| GenLayer Studio   | 61999    | `0x8ADE76f942b221c799c9529449a9B8feFbd419BF`   | [deployments/studionet.json](deployments/studionet.json) · [explorer](https://explorer-studio.genlayer.com/address/0x8ADE76f942b221c799c9529449a9B8feFbd419BF) |

Verify that an address really runs this source before trusting it:

```bash
sha256sum contracts/milestone_proof.py        # 8369b6a8b802df66...6cd221f
python3 tools/inspect_deployment.py           # get_limits() must match the table below
MILESTONE_PROOF_LIVE=1 python3 -m pytest tests/integration/test_deployed_contract.py -q
```

Full procedure: [deployments/README.md](deployments/README.md).

## How it works

```
create_engagement ─► OPEN ──claim_engagement──► ACTIVE
                                                   │
                       submit_milestone (per milestone, per attempt)
                                                   │
                                   evaluate_submission (consensus)
                          ┌────────────────┬───────┴─────────┐
                       ACCEPTED      CHANGES_REQUESTED   INCONCLUSIVE
                  (milestone done)   (new attempt,     (new attempt,
                                       up to max)        up to max)

        every milestone ACCEPTED ────────────────────────────► COMPLETED
```

`evaluate_submission(submission_id)` takes **only** the submission id. Terms, parties, milestone and criteria always come from contract storage.

The security property the contract is built around:

> No verification verdict is stored unless the validators have independently checked every decisive field of the submission, using the same agreement terms and evidence they fetched themselves.

- **Independent evidence.** Every validator fetches the URL itself, hashes the exact bytes (SHA-256) and must obtain the same `evidence_hash` and size as the leader.
- **Exact per-criterion agreement.** Each criterion's `status` (`MET` / `NOT_MET` / `UNVERIFIABLE`) and `reason_code` must match the validator's own evaluation. Agreeing only on the milestone status is not enough.
- **Complete and ordered.** The verdict must cover exactly the original criteria `C1..Ck` of that milestone, in list order, with nothing missing, duplicated, extra or renamed.
- **Evidence you can check.** A `MET` needs a quote that appears literally in the deliverable (between `min_excerpt_len` and `max_excerpt_len` characters, or the whole short document). Without it the criterion is downgraded to `UNVERIFIABLE`, so an invented approval cannot become `ACCEPTED`.
- **Derived, never trusted.** The milestone status and the engagement completion are computed by code from criterion statuses. There is no score, threshold or free-text summary.
- **Unambiguous records.** Submissions are keyed by contract-generated ids, bound to their engagement, milestone, attempt index and agreement hash, and never overwritten.
- **Fail safe.** HTTP errors, empty/oversized/non-UTF-8 content and unusable model output abort the transaction and store nothing. `INCONCLUSIVE` is a completed business outcome, not an error.

Full details: [docs/DESIGN.md](docs/DESIGN.md).

## Limits

Defined in one block at the top of the contract, enforced on-chain and returned by `get_limits()`. They are application-level choices, **not GenLayer protocol limits**.

| Limit                                | `get_limits()` key        | Value     | Unit                                |
| ------------------------------------ | ------------------------- | --------- | ----------------------------------- |
| Milestones per engagement            | min/max_milestones        | 1 / 10    | count (distinct titles)             |
| Criteria per milestone               | min/max_criteria          | 1 / 8     | count (distinct, case-insensitive)  |
| Attempts per milestone               | max_attempts              | 3         | count                               |
| Engagement title                     | max_title_len             | 160       | characters                          |
| Description (newlines/tabs allowed)  | max_description_len       | 4,000     | characters                          |
| Milestone title                      | max_milestone_title_len   | 120       | characters                          |
| Each criterion                       | max_criterion_len         | 600       | characters                          |
| Evidence URL                         | max_url_len               | 2,048     | characters                          |
| Evidence payload (fetched)           | max_content_bytes         | 200,000   | bytes (UTF-8)                       |
| Evidence quote                       | min/max_excerpt_len       | 8 / 280   | characters                          |

- Text limits count **characters**, not bytes: a 4,000-character description of emoji is 16,000 bytes of calldata. `max_content_bytes` counts bytes of the fetched response, which must be valid UTF-8.
- **The ceilings were tested for logic, not on a live network.** The validators' model context window, calldata acceptance, gas and the real cross-model disagreement rate bound what is practical. Recommendation: read `get_limits()` from your SDK, start with lower *soft* limits and raise them as you measure real validators. Prefer short, objective, independently checkable criteria. Each ceiling is a single constant and can be changed without touching the logic.

## Public interface

| Method                 | Kind  | Arguments                                                              | Returns                          |
| ---------------------- | ----- | ---------------------------------------------------------------------- | -------------------------------- |
| create_engagement      | write | title: str, description: str, milestones: list                         | engagement_id ("eng-\<n\>")      |
| claim_engagement       | write | engagement_id: str                                                     | -                                |
| submit_milestone       | write | engagement_id: str, milestone_id: str, url: str                        | submission_id ("sub-\<n\>")      |
| evaluate_submission    | write | submission_id: str                                                     | -                                |
| get_engagement         | view  | engagement_id: str                                                     | engagement dict (found: false…)  |
| get_milestone          | view  | engagement_id: str, milestone_id: str                                  | milestone dict (found: false…)   |
| get_submission         | view  | submission_id: str                                                     | submission dict (found: false…)  |
| get_submission_id      | view  | engagement_id: str, milestone_id: str, attempt_index: int              | submission id or ""              |
| get_milestone_submissions | view | engagement_id: str, milestone_id: str                              | list of submission dicts         |
| get_limits             | view  | -                                                                      | every limit (+ schema_version)   |

Write calls revert with a message prefix: `[EXPECTED]` (invalid call), `[EXTERNAL]` (source problem), `[TRANSIENT]` (source temporarily unavailable) or `[LLM_ERROR]` (unusable model output). Full payload shapes: [docs/API.md](docs/API.md).

## Repository layout

```
contracts/milestone_proof.py    The contract (class MilestoneProof) - the deliverable
deployments/                    One record per network (address, hash, verification)
tests/offline/                  Pure-logic tests with an independent oracle (no GenVM needed)
tests/direct/                   Direct-mode tests: functional, validation, consensus attacks, limits
tests/integration/              Studio consensus tests + read-only live probes for the deployment
samples/                        Ready-made payloads + stdlib-only quickstart (hashing oracle)
tools/inspect_deployment.py     Read-only inspector for a live deployment
tools/package_submission.sh     Builds the contract-only submission tree
docs/DESIGN.md                  Design and behavior reference
docs/API.md                     Method-by-method payload reference
docs/TESTING.md                 How to run every suite and add tests
docs/SECURITY.md                Threat model and known limitations
docs/FRONTEND.md                How to build a frontend separately; what to submit
docs/GITHUB.md                  Publishing only the contract tree to GitHub
requirements.txt                Pinned toolchain (lint + tests)
gltest.config.yaml              Network config for the integration runner
```

## Getting started

Requirements: Python 3.12 and internet access (the GenVM runner is downloaded on first use into `~/.cache/gltest-direct`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

genvm-lint check contracts/milestone_proof.py     # lint + schema validation (10 methods)
pytest tests/direct -q                            # direct-mode suite (mocked web + LLM)
```

Right now, with zero installs beyond pytest, you can already run the offline
logic suite and the hashing oracle:

```bash
python3 -m pytest tests/offline -q    # 100 pure-logic tests, no GenVM needed
python3 samples/quickstart.py         # stdlib-only hashing walkthrough
```

## Verification

| Check                          | Command                                            | Notes                                             |
| ------------------------------ | -------------------------------------------------- | ------------------------------------------------- |
| Official linter + schema       | `genvm-lint check contracts/milestone_proof.py`    | 10 methods (6 view, 4 write)                      |
| Offline logic oracle           | `pytest tests/offline -q`                          | 100 tests, pure functions, independent oracle, no GenVM |
| Direct-mode functional         | `pytest tests/direct -q`                           | lifecycle, permissions, views, error classes       |
| Consensus attacks              | same suite (`..._consensus.py`)                    | forged/tampered verdicts must be rejected          |
| Limit boundaries               | same suite (`..._limits.py`)                       | exact max accepted, max+1 rejected                 |
| Studio / real consensus        | `gltest tests/integration/test_milestone_proof.py -v -s` | deploys fresh instances on Studio; optional live-URL evaluation |
| Live deployment probes         | `MILESTONE_PROOF_LIVE=1 python3 -m pytest tests/integration/test_deployed_contract.py -q` | read-only view calls against the Studio deployment |

All non-network suites pass on the checked-in revision (offline: 100/100;
direct: written against `genlayer-test` 0.29.2).

See [docs/TESTING.md](docs/TESTING.md) for details.

## Deploying

Deployment is intentionally not scripted. Use the official GenLayer CLI (`npm install -g genlayer`, then `genlayer deploy`), then verify the deployment:

1. Compute the commitment of the source you deployed: `sha256sum contracts/milestone_proof.py`.
2. Retrieve the deployed code with `genlayer code <address>` and `genlayer schema <address>` and confirm that hash and the 10-method schema match.
3. Call `get_limits()` on the deployment and confirm it returns the table above.
4. Run the integration suite against Studio.

## Submitting

When a submission asks for **only the Intelligent Contract**, one file is the
answer; the script below assembles it with the supporting evidence and never
includes a frontend file:

```bash
bash tools/package_submission.sh      # builds ./milestone-proof-submission/
sha256sum contracts/milestone_proof.py
```

To publish the project itself as a pure contract repository (staging only
`contracts/`, `tests/`, `docs/`, `samples/`, `deployments/`, `tools/` and the
pinned toolchain), follow [docs/GITHUB.md](docs/GITHUB.md). See
[docs/FRONTEND.md](docs/FRONTEND.md) for the recommended front/back split and
the integration contract between the two.

## Known limitations

- **Limits are unmeasured on a network** (model context, calldata, gas, disagreement rate): see [Limits](#limits).
- Prompt-injection resistance is defense in depth, not immunity: a model fooled identically on every node can still approve a criterion that quotes a real sentence of the document.
- A quote proves presence in the document, not relevance to the criterion.
- Up to 280 characters per criterion of the evidence are stored publicly on chain; the raw document is not.
- The contract cannot decide whether a DNS name resolves to a private address; node-level network policy must block that.

The complete list: [docs/SECURITY.md](docs/SECURITY.md).
