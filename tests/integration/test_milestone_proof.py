"""Integration tests for real multi-validator consensus.

These run against GenLayer Studio (localnet) or Studionet with the gltest
runner - NOT with pytest. They need a running network; they are collected
here so that `gltest` can execute them.

Run (Studio running locally or Studionet configured in gltest.config.yaml):

    gltest tests/integration/test_milestone_proof.py -v -s

Optional live evaluation test (real HTTPS fetch + real LLM judging):

    MILESTONE_PROOF_LIVE_URL=https://your-evidence.example/doc.md \
        gltest tests/integration/test_milestone_proof.py -k live -s

The deterministic writes (create/claim/submit) need no mocks and always run.
The consensus evaluation tests require either mock validators (Studio
supports `mock_web_response`/`mock_llm_response` on validator configs) or a
live URL reachable from every validator.
"""

import json
import os

from gltest import get_contract_factory, get_validator_factory
from gltest.assertions import tx_execution_succeeded
from gltest.types import MockedLLMResponse, MockedWebResponse

EVIDENCE_BODY = (
    "Milestone one evidence report\n"
    "\n"
    "The service exposes a GET /users endpoint returning JSON.\n"
    "Response payloads are documented with field-by-field tables.\n"
    "Test coverage reached 95% across the whole suite.\n"
)

MILESTONES = [
    {
        "title": "API documentation",
        "criteria": [
            "The evidence documents a GET /users endpoint",
            "The evidence documents the response payload fields",
            "The evidence states the measured test coverage",
        ],
    },
    {
        "title": "Release packaging",
        "criteria": ["The evidence declares a signed release tag"],
    },
]

LIVE_URL = os.environ.get("MILESTONE_PROOF_LIVE_URL")
EVIDENCE_URL = "https://evidence.example.org/milestone-one.md"


def _factory():
    return get_contract_factory("MilestoneProof")


def _deploy():
    contract = _factory().deploy()
    return contract


def _llm_results():
    return json.dumps(
        {
            "results": [
                {
                    "criterion_id": "C1",
                    "status": "MET",
                    "evidence_excerpt": "exposes a GET /users endpoint",
                },
                {
                    "criterion_id": "C2",
                    "status": "MET",
                    "evidence_excerpt": "documented with field-by-field tables",
                },
                {
                    "criterion_id": "C3",
                    "status": "MET",
                    "evidence_excerpt": "Test coverage reached 95%",
                },
            ]
        }
    )


def _mock_context():
    """Five validators with identical mocked web + LLM, for Studio runs."""
    mock_web: MockedWebResponse = {
        "nondet_web_request": {
            EVIDENCE_URL: {"method": "GET", "status": 200, "body": EVIDENCE_BODY}
        }
    }
    mock_llm: MockedLLMResponse = {"nondet_exec_prompt": {}}
    validators = get_validator_factory().batch_create_mock_validators(
        count=5, mock_web_response=mock_web, mock_llm_response=mock_llm
    )
    return {"validators": [v.to_dict() for v in validators]}


def test_create_and_read_engagement():
    contract = _deploy()
    tx = contract.create_engagement(
        args=["Docs build", "Ship the integration docs", MILESTONES]
    ).transact()
    assert tx_execution_succeeded(tx)

    engagement = contract.get_engagement(args=["eng-1"]).call()
    assert engagement["found"] is True
    assert engagement["status"] == "OPEN"
    assert engagement["milestone_ids"] == ["M1", "M2"]
    assert len(engagement["agreement_hash"]) == 0

    milestone = contract.get_milestone(args=["eng-1", "M1"]).call()
    assert milestone["title"] == "API documentation"
    assert [c["id"] for c in milestone["criteria"]] == ["C1", "C2", "C3"]


def test_claim_binds_worker_and_terms():
    contract = _deploy()
    contract.create_engagement(args=["Docs build", "Ship the docs", MILESTONES]).transact()
    tx = contract.claim_engagement(args=["eng-1"]).transact()
    assert tx_execution_succeeded(tx)
    engagement = contract.get_engagement(args=["eng-1"]).call()
    assert engagement["status"] == "ACTIVE"
    assert len(engagement["agreement_hash"]) == 64


def test_submit_milestone_returns_receipt():
    contract = _deploy()
    contract.create_engagement(args=["Docs build", "Ship the docs", MILESTONES]).transact()
    contract.claim_engagement(args=["eng-1"]).transact()
    tx = contract.submit_milestone(args=["eng-1", "M1", EVIDENCE_URL]).transact()
    assert tx_execution_succeeded(tx)
    submission = contract.get_submission(args=["sub-1"]).call()
    assert submission["status"] == "PENDING"
    assert submission["attempt_index"] == 1


def test_invalid_input_reverts():
    contract = _deploy()
    tx = contract.create_engagement(args=["", "no title", MILESTONES]).transact()
    assert not tx_execution_succeeded(tx)


def test_get_limits_on_network():
    contract = _deploy()
    limits = contract.get_limits(args=[]).call()
    assert limits["max_milestones"] == 10
    assert limits["max_criteria"] == 8
    assert limits["max_attempts"] == 3
    assert limits["schema_version"] == 1


def test_evaluation_consensus_with_mock_validators():
    """End-to-end consensus on Studio with mocked web + LLM.

    The leader fetches EVIDENCE_URL (mocked), judges it (mocked LLM) and every
    validator re-fetches and re-judges; the verdict is stored only because all
    decisive fields match exactly.
    """
    context = _mock_context()
    contract = _factory().deploy(transaction_context=context)
    contract.create_engagement(
        args=["Docs build", "Ship the docs", MILESTONES]
    ).transact(transaction_context=context)
    contract.claim_engagement(args=["eng-1"]).transact(transaction_context=context)
    contract.submit_milestone(args=["eng-1", "M1", EVIDENCE_URL]).transact(
        transaction_context=context
    )
    tx = contract.evaluate_submission(args=["sub-1"]).transact(
        transaction_context=context
    )
    assert tx_execution_succeeded(tx)
    submission = contract.get_submission(args=["sub-1"]).call()
    assert submission["status"] in ("PENDING", "EVALUATED")


def test_evaluation_live_url():
    """Optional live test: requires MILESTONE_PROOF_LIVE_URL pointing at a
    public HTTPS document that satisfies the M1 criteria above."""
    if not LIVE_URL:
        import pytest

        pytest.skip("set MILESTONE_PROOF_LIVE_URL to run the live evaluation")
    contract = _deploy()
    contract.create_engagement(args=["Docs build", "Ship the docs", MILESTONES]).transact()
    contract.claim_engagement(args=["eng-1"]).transact()
    contract.submit_milestone(args=["eng-1", "M1", LIVE_URL]).transact()
    tx = contract.evaluate_submission(args=["sub-1"]).transact()
    assert tx_execution_succeeded(tx)
    submission = contract.get_submission(args=["sub-1"]).call()
    assert submission["status"] == "EVALUATED"
    assert len(submission["evidence_hash"]) == 64
    assert submission["milestone_status"] in (
        "ACCEPTED",
        "CHANGES_REQUESTED",
        "INCONCLUSIVE",
    )
    assert [r["criterion_id"] for r in submission["results"]] == ["C1", "C2", "C3"]
