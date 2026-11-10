# Testing guide

Four suites, three runners, zero overlap:

| Suite               | Runner        | What it covers                                            | Needs                  |
| ------------------- | ------------- | --------------------------------------------------------- | ---------------------- |
| `tests/offline`     | `pytest`      | the contract's pure logic (hashing, validation, derivation, prompt, verdict structure) against an independent oracle - 100 tests, runs anywhere | Python >= 3.9 + pytest only |
| `tests/direct`      | `pytest`      | everything: lifecycle, validation, consensus attacks, limits | `genlayer-test` plugin (Python 3.12) |
| `tests/integration/test_milestone_proof.py` | `gltest` | real multi-validator consensus; deploys fresh instances on Studio | a running network |
| `tests/integration/test_deployed_contract.py` | `pytest`  | read-only probes against the RECORDED live deployment | `genlayer-py` + reachable network |

## Zero-setup: offline suite

```bash
python3 -m pytest tests/offline -q     # no GenVM, no genlayer packages, no downloads
```

The contract is imported with a minimal `genlayer` stub and every pure
function is exercised against an independently written oracle (the oracle
shares no code with the contract, so drift in either direction fails a test):
hashing, text/URL hygiene, status derivation, quote rules, the fixed prompt
(including marker-injection neutralization), model-output normalization and
the validator's structural gate with ~25 forged verdicts.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Python 3.12
pip install -r requirements.txt
```

The first run downloads a GenVM runner bundle (~135 MB) into
`~/.cache/gltest-direct`. On a slow connection this can take a while; a
truncated download is fixed by deleting the partial file in that cache and
re-running.

## Direct mode (pytest)

```bash
pytest tests/direct -q
```

Direct mode executes the **leader path** in an in-memory GenVM with mocked
non-determinism. The plugin provides fixtures:

| Fixture                                 | Purpose                                  |
| --------------------------------------- | ---------------------------------------- |
| `direct_vm`                             | VM context + cheatcodes (below)          |
| `direct_deploy`                         | deploy a contract file                   |
| `direct_alice` / `direct_bob` / `direct_charlie` | test addresses                  |

Cheatcodes used by the suite:

```python
direct_vm.sender = direct_alice                        # caller of the next call
direct_vm.mock_web(r"evidence\\.example\\.org", {"status": 200, "body": b"..."})
direct_vm.mock_llm(r".*", '{"results": [...]}')        # matched against the prompt
direct_vm.clear_mocks()
```

### How the consensus attack tests work

Direct mode only runs the leader. To model the real protocol
(`tests/direct/milestone_proof_support.py`):

```python
snap = vm.snapshot()
contract.evaluate_submission(submission_id)   # leader proposes
proposal = copy.deepcopy(vm._captured_validators[-1][0])
vm.revert(snap)                                # leader state NOT applied
assert vm.run_validator(leader_result=forged) is False   # validator must reject
```

So a test can hand any *forged* verdict to the validator and then assert that
nothing reached storage (`assert_unapplied`).

### Suite map

| File                                     | Focus                                                              |
| ---------------------------------------- | ------------------------------------------------------------------ |
| `test_milestone_proof_functional.py`     | lifecycle, permissions, supersede/retry, completion, error classes |
| `test_milestone_proof_validation.py`     | input shapes: text hygiene, milestone shape, URL rules             |
| `test_milestone_proof_consensus.py`      | forged verdicts: bindings, order, quotes, derived status, tampering |
| `test_milestone_proof_limits.py`         | exact boundaries for every limit + characters-vs-bytes             |
| `../offline/test_pure_functions.py`      | pure-logic oracle, runs without GenVM (see above)                  |

### Adding a test

1. Reuse the harness: `pending_submission(...)` gets you an active engagement
   with one pending submission in one line.
2. Mock the world with `mock_world(direct_vm, body=..., llm=[...])` where
   `llm` is a list of `item(cid, status, quote)`.
3. For attacks: `proposal = capture_leader(...)`, mutate a deep copy, assert
   `validator_accepts(...) is False` and `assert_unapplied(...)`.

### Pointing the suite at a modified contract

The whole suite reads the contract path from an environment variable, which is
how mutation-style checks work without touching the real file:

```bash
MILESTONE_PROOF_CONTRACT=/tmp/mutated_milestone_proof.py pytest tests/direct -q
```

## Integration mode (gltest)

`tests/integration/test_milestone_proof.py` runs against GenLayer Studio with
the gltest runner (configuration in `gltest.config.yaml`):

```bash
# Studio running locally (genlayer CLI: `genlayer up`)
gltest tests/integration/test_milestone_proof.py -v -s

# hosted Studionet
gltest --network studionet tests/integration/test_milestone_proof.py -v -s
```

The suite covers deployment, schema-level input reverts, the deterministic
write flow and a consensus evaluation with mocked validators. An optional live
evaluation (real HTTPS + real models) is enabled by:

```bash
MILESTONE_PROOF_LIVE_URL=https://your.host/evidence.md \
  gltest tests/integration/test_milestone_proof.py -k live -s
```

Publish `samples/sample_deliverable.md` somewhere public and point the
variable at it for a realistic ACCEPTED path.

## Live deployment probes

The recorded deployment (`deployments/studionet.json`, address
`0x8ADE76f942b221c799c9529449a9B8feFbd419BF`) can be probed without deploying
anything and without an account - all calls are free view reads:

```bash
pip install genlayer-py
MILESTONE_PROOF_LIVE=1 python3 -m pytest tests/integration/test_deployed_contract.py -q
```

The suite asserts that the on-chain `get_limits()` equals the repository
constants and that every "not found" view answers with a well-formed
`found: false` payload instead of reverting. Override the target with
`MILESTONE_PROOF_NETWORK` / `MILESTONE_PROOF_ADDRESS`. A quick human-readable
equivalent without pytest:

```bash
python3 tools/inspect_deployment.py --network studionet --probe eng-1
```

Both commands exit non-zero on a mismatch, so they work as deployment gates in
CI.

## Linting

```bash
genvm-lint check contracts/milestone_proof.py
```

Expected: lint passes and the schema shows 10 methods (4 write, 6 view).
