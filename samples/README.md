# Samples

Runnable, self-contained material for trying the contract out. Nothing in this
directory is required by the contract itself.

| File                     | What it is                                                                                     |
| ------------------------ | ---------------------------------------------------------------------------------------------- |
| `sample_engagement.json` | A ready-made `create_engagement` payload (title, description, two milestones with criteria).   |
| `sample_deliverable.md`  | An evidence document that satisfies the `API documentation` milestone of the sample payload.   |
| `quickstart.py`          | Stdlib-only walkthrough: recomputes `terms_hash`, `agreement_hash` and `evidence_hash` locally. |

## Try it in one minute

```bash
python3 samples/quickstart.py
```

The script prints the ids the contract would assign (`M1..M2`, `C1..Ck`), the
SHA-256 commitments of the sample payload, and the exact JSON shape the model
must return for milestone `M1`. Use it as a ground-truth oracle for your own
client or tests.

## Try the full lifecycle (mocked world)

The host the samples point at (`evidence.example.org`) is intentionally not
real; the evaluation flow is exercised with mocks in the direct-mode tests:

```bash
pip install -r requirements.txt
pytest tests/direct -q
```

## Try it on a network

See `docs/TESTING.md` for GenLayer Studio (`gltest`) runs and
`docs/API.md` for the payload format of every method. To run a *live*
evaluation, publish `sample_deliverable.md` at a public HTTPS URL and pass it
to the integration suite:

```bash
MILESTONE_PROOF_LIVE_URL=https://your.host/sample_deliverable.md \
  gltest tests/integration/test_milestone_proof.py -k live -s
```
