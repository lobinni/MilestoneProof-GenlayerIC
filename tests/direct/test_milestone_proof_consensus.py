"""Consensus / equivalence tests: a forged or tampered leader verdict must be
rejected by the validator, and nothing may reach storage.

Every test follows the same protocol model:

  1. the honest leader runs and proposes a verdict (state captured);
  2. the state is reverted (the proposal is not applied yet);
  3. a MUTATED verdict is handed to the validator, which must reject it;
  4. the submission must still be PENDING.

Run:  pytest tests/direct/test_milestone_proof_consensus.py -q
"""

import copy

import pytest

from .milestone_proof_support import (
    BODY_M1,
    QUOTES_M1,
    all_met,
    assert_unapplied,
    capture_leader,
    item,
    mock_world,
    pending_submission,
    validator_accepts,
)


def _setup(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Pending submission + mocked world + an honest leader proposal."""
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm)
    proposal = capture_leader(direct_vm, contract, direct_alice, submission_id)
    return contract, engagement_id, submission_id, proposal


def _forge(proposal, mutate):
    forged = copy.deepcopy(proposal)
    # the proposal is a Return wrapper; the verdict lives in .calldata
    payload = copy.deepcopy(forged.calldata)
    mutate(payload)
    forged.calldata = payload
    return forged


# ---------------------------------------------------------------------------
# Sanity: the honest proposal is accepted
# ---------------------------------------------------------------------------


def test_honest_proposal_is_accepted(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    _, _, _, proposal = _setup(direct_vm, direct_deploy, direct_alice, direct_bob)
    assert validator_accepts(direct_vm, proposal) is True


# ---------------------------------------------------------------------------
# Top-level bindings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("engagement_id", "eng-2"),
        ("milestone_id", "M2"),
        ("submission_id", "sub-2"),
        ("attempt_index", 2),
        ("attempt_index", 0),
        ("agreement_hash", "0" * 64),
        ("evidence_hash", "f" * 64),  # valid hex, wrong digest
        ("evidence_hash", "XYZ"),  # not a sha256 hex at all
    ],
)
def test_binding_fields_are_checked(
    direct_vm, direct_deploy, direct_alice, direct_bob, field, value
):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    forged = _forge(proposal, lambda p: p.__setitem__(field, value))
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


def test_evidence_size_mismatch(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    forged = _forge(proposal, lambda p: p.__setitem__("evidence_size", p["evidence_size"] + 1))
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


def test_missing_verdict_key(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    forged = _forge(proposal, lambda p: p.pop("milestone_status"))
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


def test_extra_verdict_key(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    forged = _forge(proposal, lambda p: p.__setitem__("score", 100))
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


# ---------------------------------------------------------------------------
# Result-set completeness and order
# ---------------------------------------------------------------------------


def test_missing_criterion_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    forged = _forge(proposal, lambda p: p.__setitem__("results", p["results"][:2]))
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


def test_extra_criterion_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )

    def add_extra(p):
        p["results"].append(
            {
                "criterion_id": "C4",
                "status": "MET",
                "reason_code": "MEETS_CRITERION",
                "evidence_excerpt": QUOTES_M1["C1"],
            }
        )

    forged = _forge(proposal, add_extra)
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


def test_reordered_criteria_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )

    def swap(p):
        p["results"][0], p["results"][1] = p["results"][1], p["results"][0]

    forged = _forge(proposal, swap)
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


def test_renamed_criterion_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )

    def rename(p):
        p["results"][0]["criterion_id"] = "C9"

    forged = _forge(proposal, rename)
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


# ---------------------------------------------------------------------------
# Status, reason code and quote integrity
# ---------------------------------------------------------------------------


def test_flipped_status_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )

    def flip(p):
        # downgrade a MET criterion; milestone_status would change too
        p["results"][0]["status"] = "NOT_MET"
        p["results"][0]["reason_code"] = "REQUIREMENT_NOT_MET"
        p["results"][0]["evidence_excerpt"] = ""
        p["milestone_status"] = "CHANGES_REQUESTED"

    forged = _forge(proposal, flip)
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


def test_wrong_reason_code_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )

    def wrong_reason(p):
        p["results"][0]["reason_code"] = "INSUFFICIENT_EVIDENCE"

    forged = _forge(proposal, wrong_reason)
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


def test_invented_quote_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )

    def invent(p):
        p["results"][0]["evidence_excerpt"] = "not present anywhere in the document at all"

    forged = _forge(proposal, invent)
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


def test_too_short_quote_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )

    def short(p):
        p["results"][0]["evidence_excerpt"] = "GET"  # literal but < min_excerpt_len

    forged = _forge(proposal, short)
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


def test_quote_on_unverifiable_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )

    def attach(p):
        # UNVERIFIABLE must not carry a quote
        p["results"][1]["status"] = "UNVERIFIABLE"
        p["results"][1]["reason_code"] = "INSUFFICIENT_EVIDENCE"
        p["results"][1]["evidence_excerpt"] = QUOTES_M1["C2"]
        p["milestone_status"] = "INCONCLUSIVE"

    forged = _forge(proposal, attach)
    assert validator_accepts(direct_vm, forged) is False
    assert_unapplied(contract, engagement_id, submission_id)


def test_milestone_status_must_be_derived(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    # all criteria are MET, so ACCEPTED is the only legal milestone status
    for bogus in ("INCONCLUSIVE", "CHANGES_REQUESTED", "AWAITING", "PENDING"):
        forged = _forge(proposal, lambda p, b=bogus: p.__setitem__("milestone_status", b))
        assert validator_accepts(direct_vm, forged) is False, bogus
        assert_unapplied(contract, engagement_id, submission_id)


def test_tampered_hash_body_mismatch_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """If the document changes between leader and validator, the hashes differ
    and the validator must reject."""
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    # validator sees a DIFFERENT document at the same URL
    direct_vm.mock_web(
        r"evidence\\.example\\.org",
        {"status": 200, "body": (BODY_M1 + "tampered appendix\n").encode("utf-8")},
    )
    assert validator_accepts(direct_vm, proposal) is False
    assert_unapplied(contract, engagement_id, submission_id)


# ---------------------------------------------------------------------------
# Error consensus
# ---------------------------------------------------------------------------


def test_validator_rejects_successful_leader_when_source_is_down(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """The leader claims success, but the validator's own fetch fails: reject."""
    contract, engagement_id, submission_id, proposal = _setup(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    direct_vm.mock_web(r"evidence\\.example\\.org", {"status": 404, "body": b""})
    assert validator_accepts(direct_vm, proposal) is False
    assert_unapplied(contract, engagement_id, submission_id)
