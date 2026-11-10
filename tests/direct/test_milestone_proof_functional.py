"""Functional tests: lifecycle, permissions, views and state transitions.

Run:  pytest tests/direct/test_milestone_proof_functional.py -q
Requires the genlayer-test pytest plugin (see requirements.txt).
"""

import hashlib
import json

import pytest
from genlayer.vm import UserError

from .milestone_proof_support import (
    BODY_M1,
    BODY_M2,
    DEFAULT_MILESTONES,
    LIMITS,
    QUOTES_M1,
    QUOTES_M2,
    URL,
    URL_2,
    URL_M2,
    active_engagement,
    expected_terms_hash,
    hex_of,
    item,
    mock_world,
    new_engagement,
    numbered_milestones,
    pending_submission,
)


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_create_returns_counter_id(direct_vm, direct_deploy, direct_alice):
    contract, engagement_id = new_engagement(direct_vm, direct_deploy, direct_alice)
    assert engagement_id == "eng-1"


def test_create_stores_terms_and_milestones(direct_vm, direct_deploy, direct_alice):
    contract, engagement_id = new_engagement(direct_vm, direct_deploy, direct_alice)
    engagement = contract.get_engagement(engagement_id)
    assert engagement["found"] is True
    assert engagement["client"] == hex_of(direct_alice)
    assert engagement["worker"] == ""
    assert engagement["status"] == "OPEN"
    assert engagement["title"] == "Docs build"
    assert engagement["milestone_ids"] == ["M1", "M2"]
    assert [m["id"] for m in engagement["milestones"]] == ["M1", "M2"]
    assert [m["status"] for m in engagement["milestones"]] == ["AWAITING", "AWAITING"]
    assert engagement["terms_hash"] == expected_terms_hash(
        "Docs build", "Ship docs", DEFAULT_MILESTONES
    )
    assert engagement["agreement_hash"] == ""

    m1 = contract.get_milestone(engagement_id, "M1")
    assert m1["found"] is True
    assert m1["engagement_id"] == engagement_id
    assert m1["title"] == "API documentation"
    assert m1["criteria"] == [
        {"id": "C1", "text": DEFAULT_MILESTONES[0]["criteria"][0]},
        {"id": "C2", "text": DEFAULT_MILESTONES[0]["criteria"][1]},
        {"id": "C3", "text": DEFAULT_MILESTONES[0]["criteria"][2]},
    ]
    assert m1["attempt_count"] == 0
    assert m1["submission_ids"] == []


def test_create_second_engagement_increments_id(
    direct_vm, direct_deploy, direct_alice
):
    contract, first = new_engagement(direct_vm, direct_deploy, direct_alice)
    direct_vm.sender = direct_alice
    second = contract.create_engagement("Other", "Other work", DEFAULT_MILESTONES)
    assert (first, second) == ("eng-1", "eng-2")
    # milestones are namespaced per engagement
    assert contract.get_milestone(first, "M1")["engagement_id"] == first
    assert contract.get_milestone(second, "M1")["engagement_id"] == second


def test_create_single_milestone(direct_vm, direct_deploy, direct_alice):
    contract, engagement_id = new_engagement(
        direct_vm, direct_deploy, direct_alice, milestones=numbered_milestones(1)
    )
    assert contract.get_engagement(engagement_id)["milestone_ids"] == ["M1"]


def test_get_engagement_not_found(direct_vm, direct_deploy, direct_alice):
    contract, _ = new_engagement(direct_vm, direct_deploy, direct_alice)
    assert contract.get_engagement("eng-99") == {"found": False, "id": "eng-99"}


def test_get_milestone_not_found(direct_vm, direct_deploy, direct_alice):
    contract, engagement_id = new_engagement(direct_vm, direct_deploy, direct_alice)
    assert contract.get_milestone(engagement_id, "M9") == {
        "found": False,
        "id": "M9",
    }
    assert contract.get_milestone("eng-99", "M1") == {"found": False, "id": "M1"}


# ---------------------------------------------------------------------------
# Claiming
# ---------------------------------------------------------------------------


def test_claim_commits_agreement(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id = active_engagement(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    engagement = contract.get_engagement(engagement_id)
    assert engagement["status"] == "ACTIVE"
    assert engagement["worker"] == hex_of(direct_bob)
    assert len(engagement["agreement_hash"]) == 64
    assert engagement["agreement_hash"] != engagement["terms_hash"]


def test_claim_rejects_client(direct_vm, direct_deploy, direct_alice):
    contract, engagement_id = new_engagement(direct_vm, direct_deploy, direct_alice)
    direct_vm.sender = direct_alice
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.claim_engagement(engagement_id)


def test_claim_rejects_second_worker(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract, engagement_id = active_engagement(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    direct_vm.sender = direct_charlie
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.claim_engagement(engagement_id)


def test_claim_unknown_engagement(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy("contracts/milestone_proof.py")
    direct_vm.sender = direct_bob
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.claim_engagement("eng-42")


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------


def test_submit_returns_counter_id(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    assert submission_id == "sub-1"
    submission = contract.get_submission(submission_id)
    assert submission["status"] == "PENDING"
    assert submission["attempt_index"] == 1
    assert submission["milestone_id"] == "M1"
    assert submission["worker"] == hex_of(direct_bob)
    assert submission["url"] == URL
    milestone = contract.get_milestone(engagement_id, "M1")
    assert milestone["attempt_count"] == 1
    assert milestone["submission_ids"] == ["sub-1"]


def test_submit_rejects_open_engagement(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id = new_engagement(direct_vm, direct_deploy, direct_alice)
    direct_vm.sender = direct_bob
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.submit_milestone(engagement_id, "M1", URL)


def test_submit_rejects_non_worker(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id = active_engagement(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    direct_vm.sender = direct_alice  # the client is not the worker
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.submit_milestone(engagement_id, "M1", URL)


def test_submit_rejects_unknown_milestone(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id = active_engagement(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    direct_vm.sender = direct_bob
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.submit_milestone(engagement_id, "M5", URL)


def test_pending_submission_is_superseded_by_new_attempt(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, first_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    direct_vm.sender = direct_bob
    second_id = contract.submit_milestone(engagement_id, "M1", URL_2)
    assert contract.get_submission(first_id)["status"] == "SUPERSEDED"
    assert contract.get_submission(second_id)["status"] == "PENDING"
    assert contract.get_submission(second_id)["attempt_index"] == 2
    assert contract.get_milestone(engagement_id, "M1")["submission_ids"] == [
        first_id,
        second_id,
    ]


def test_get_submission_id_is_one_based(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    assert contract.get_submission_id(engagement_id, "M1", 1) == submission_id
    assert contract.get_submission_id(engagement_id, "M1", 0) == ""
    assert contract.get_submission_id(engagement_id, "M1", 2) == ""
    assert contract.get_submission_id("eng-99", "M1", 1) == ""


# ---------------------------------------------------------------------------
# Evaluation (leader path with mocked world)
# ---------------------------------------------------------------------------


def test_evaluate_stores_full_verdict(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm)
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)

    submission = contract.get_submission(submission_id)
    assert submission["status"] == "EVALUATED"
    assert submission["milestone_status"] == "ACCEPTED"
    assert submission["evaluation_requested_by"] == hex_of(direct_alice)
    assert submission["evidence_hash"] == hashlib.sha256(
        BODY_M1.encode("utf-8")
    ).hexdigest()
    assert submission["evidence_size"] == len(BODY_M1.encode("utf-8"))
    assert [r["criterion_id"] for r in submission["results"]] == ["C1", "C2", "C3"]
    assert {r["status"] for r in submission["results"]} == {"MET"}
    assert {r["reason_code"] for r in submission["results"]} == {"MEETS_CRITERION"}
    assert submission["results"][0]["evidence_excerpt"] == QUOTES_M1["C1"]

    assert contract.get_milestone(engagement_id, "M1")["status"] == "ACCEPTED"
    # engagement stays ACTIVE while M2 is unresolved
    assert contract.get_engagement(engagement_id)["status"] == "ACTIVE"


def test_evaluate_by_worker(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm)
    direct_vm.sender = direct_bob
    contract.evaluate_submission(submission_id)
    assert contract.get_submission(submission_id)["status"] == "EVALUATED"


def test_engagement_completes_when_every_milestone_accepted(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm)
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)

    direct_vm.sender = direct_bob
    second = contract.submit_milestone(engagement_id, "M2", URL_M2)
    direct_vm.clear_mocks()
    direct_vm.mock_web(
        r"evidence\\.example\\.org", {"status": 200, "body": BODY_M2.encode("utf-8")}
    )
    direct_vm.mock_llm(
        r".*",
        json.dumps(
            {
                "results": [
                    item("C1", "MET", QUOTES_M2["C1"]),
                    item("C2", "MET", QUOTES_M2["C2"]),
                ]
            }
        ),
    )
    direct_vm.sender = direct_alice
    contract.evaluate_submission(second)
    assert contract.get_milestone(engagement_id, "M2")["status"] == "ACCEPTED"
    assert contract.get_engagement(engagement_id)["status"] == "COMPLETED"


def test_completed_engagement_rejects_submissions(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm,
        direct_deploy,
        direct_alice,
        direct_bob,
        milestones=numbered_milestones(1),
    )
    mock_world(direct_vm, body=BODY_M1.encode("utf-8"))
    direct_vm.mock_llm(r".*", json.dumps({"results": [item("C1", "MET", QUOTES_M1["C1"])]}))
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)
    assert contract.get_engagement(engagement_id)["status"] == "COMPLETED"
    direct_vm.sender = direct_bob
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.submit_milestone(engagement_id, "M1", URL_2)


def test_not_met_leads_to_changes_requested(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(
        direct_vm,
        llm=[
            item("C1", "MET", QUOTES_M1["C1"]),
            item("C2", "NOT_MET"),
            item("C3", "MET", QUOTES_M1["C3"]),
        ],
    )
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)
    submission = contract.get_submission(submission_id)
    assert submission["milestone_status"] == "CHANGES_REQUESTED"
    assert submission["results"][1]["reason_code"] == "REQUIREMENT_NOT_MET"
    assert contract.get_milestone(engagement_id, "M1")["status"] == "CHANGES_REQUESTED"
    assert contract.get_engagement(engagement_id)["status"] == "ACTIVE"


def test_unverifiable_leads_to_inconclusive(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(
        direct_vm,
        llm=[
            item("C1", "MET", QUOTES_M1["C1"]),
            item("C2", "UNVERIFIABLE"),
            item("C3", "NOT_MET"),
        ],
    )
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)
    submission = contract.get_submission(submission_id)
    # INCONCLUSIVE dominates CHANGES_REQUESTED
    assert submission["milestone_status"] == "INCONCLUSIVE"
    assert submission["results"][1]["reason_code"] == "INSUFFICIENT_EVIDENCE"


def test_met_without_literal_quote_is_downgraded(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(
        direct_vm,
        llm=[
            item("C1", "MET", "THIS SENTENCE IS NOT IN THE DOCUMENT"),
            item("C2", "MET", QUOTES_M1["C2"]),
            item("C3", "MET", QUOTES_M1["C3"]),
        ],
    )
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)
    submission = contract.get_submission(submission_id)
    # fabricated approval cannot pass: downgraded to UNVERIFIABLE -> INCONCLUSIVE
    assert submission["results"][0]["status"] == "UNVERIFIABLE"
    assert submission["results"][0]["evidence_excerpt"] == ""
    assert submission["milestone_status"] == "INCONCLUSIVE"


def test_changes_requested_allows_new_attempt(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm, llm=[item("C1", "NOT_MET"), item("C2", "NOT_MET"), item("C3", "NOT_MET")])
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)

    direct_vm.sender = direct_bob
    second_id = contract.submit_milestone(engagement_id, "M1", URL_2)
    assert contract.get_submission(submission_id)["status"] == "EVALUATED"  # kept
    assert contract.get_submission(second_id)["status"] == "PENDING"
    assert contract.get_milestone(engagement_id, "M1")["attempt_count"] == 2


def test_attempt_cap_enforced(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, _ = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    direct_vm.sender = direct_bob
    contract.submit_milestone(engagement_id, "M1", URL_2)
    contract.submit_milestone(engagement_id, "M1", URL)
    assert contract.get_milestone(engagement_id, "M1")["attempt_count"] == 3
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.submit_milestone(engagement_id, "M1", URL_2)


def test_evaluate_rejects_foreign_caller(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm)
    direct_vm.sender = direct_charlie
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.evaluate_submission(submission_id)


def test_evaluate_rejects_non_pending(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm)
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.evaluate_submission(submission_id)


def test_evaluate_rejects_superseded(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, first_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    direct_vm.sender = direct_bob
    contract.submit_milestone(engagement_id, "M1", URL_2)
    mock_world(direct_vm)
    direct_vm.sender = direct_alice
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.evaluate_submission(first_id)


def test_accepted_milestone_rejects_new_attempts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm)
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)
    direct_vm.sender = direct_bob
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.submit_milestone(engagement_id, "M1", URL_2)


# ---------------------------------------------------------------------------
# Web/LLM failure classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("http_status", [500, 502, 408, 429])
def test_transient_http_errors(
    direct_vm, direct_deploy, direct_alice, direct_bob, http_status
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm, status=http_status)
    direct_vm.sender = direct_alice
    with pytest.raises(UserError, match=r"\[TRANSIENT\]"):
        contract.evaluate_submission(submission_id)


@pytest.mark.parametrize("http_status", [400, 403, 404])
def test_external_http_errors(
    direct_vm, direct_deploy, direct_alice, direct_bob, http_status
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm, status=http_status)
    direct_vm.sender = direct_alice
    with pytest.raises(UserError, match=r"\[EXTERNAL\]"):
        contract.evaluate_submission(submission_id)


def test_empty_body_is_external(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm, body=b"")
    direct_vm.sender = direct_alice
    with pytest.raises(UserError, match=r"\[EXTERNAL\]"):
        contract.evaluate_submission(submission_id)


def test_non_utf8_body_is_external(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm, body=b"\xff\xfe\x00\x01 binary")
    direct_vm.sender = direct_alice
    with pytest.raises(UserError, match=r"\[EXTERNAL\]"):
        contract.evaluate_submission(submission_id)


def test_broken_llm_output_is_llm_error(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    direct_vm.mock_web(
        r"evidence\\.example\\.org", {"status": 200, "body": BODY_M1.encode("utf-8")}
    )
    direct_vm.mock_llm(r".*", "this is not json at all")
    direct_vm.sender = direct_alice
    with pytest.raises(UserError, match=r"\[LLM_ERROR\]"):
        contract.evaluate_submission(submission_id)


# ---------------------------------------------------------------------------
# Views and limits
# ---------------------------------------------------------------------------


def test_get_milestone_submissions_order(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, first_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    direct_vm.sender = direct_bob
    second_id = contract.submit_milestone(engagement_id, "M1", URL_2)
    submissions = contract.get_milestone_submissions(engagement_id, "M1")
    assert [s["submission_id"] for s in submissions] == [first_id, second_id]
    assert contract.get_milestone_submissions(engagement_id, "M9") == []


def test_get_submission_not_found(direct_vm, direct_deploy, direct_alice):
    contract, _ = new_engagement(direct_vm, direct_deploy, direct_alice)
    assert contract.get_submission("sub-77") == {
        "found": False,
        "submission_id": "sub-77",
    }


def test_get_limits_matches_table(direct_vm, direct_deploy, direct_alice):
    contract, _ = new_engagement(direct_vm, direct_deploy, direct_alice)
    assert contract.get_limits() == LIMITS


def test_get_engagement_milestone_summary(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    engagement = contract.get_engagement(engagement_id)
    summary = {m["id"]: m for m in engagement["milestones"]}
    assert summary["M1"]["attempt_count"] == 1
    assert summary["M1"]["criterion_count"] == 3
    assert summary["M2"]["attempt_count"] == 0
    assert summary["M2"]["criterion_count"] == 2
