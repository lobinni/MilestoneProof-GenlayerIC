"""Limit tests: exact boundaries for every application limit.

For each limit: the maximum is accepted, maximum + 1 (or minimum - 1) is
rejected, and character-vs-byte semantics are checked. Also verifies that
get_limits() returns exactly the contract constants.

Run:  pytest tests/direct/test_milestone_proof_limits.py -q
"""

import pytest
from genlayer.vm import UserError

from .milestone_proof_support import (
    CONTRACT,
    LIMITS as LIMITS_TABLE,
    active_engagement,
    item,
    mock_world,
    numbered_criteria,
    numbered_milestones,
    pending_submission,
    sha256_hex,
)

MAX_MS = LIMITS_TABLE["max_milestones"]
MAX_CR = LIMITS_TABLE["max_criteria"]
MAX_ATTEMPTS = LIMITS_TABLE["max_attempts"]


def _create(contract, vm, sender, milestones, title="t", description="d"):
    vm.sender = sender
    return contract.create_engagement(title, description, milestones)


def _one_milestone(criteria):
    return [{"title": "only", "criteria": criteria}]


# ---------------------------------------------------------------------------
# get_limits
# ---------------------------------------------------------------------------


def test_get_limits_equals_constants(direct_vm, direct_deploy):
    assert direct_deploy(CONTRACT).get_limits() == LIMITS_TABLE


def test_limits_match_module_constants(direct_vm, direct_deploy):
    """The constants block and get_limits() can never drift apart."""
    from .milestone_proof_support import module

    contract = direct_deploy(CONTRACT)
    mod = module(direct_vm)
    assert contract.get_limits()["max_milestones"] == mod.MAX_MILESTONES
    assert contract.get_limits()["max_criteria"] == mod.MAX_CRITERIA
    assert contract.get_limits()["max_attempts"] == mod.MAX_ATTEMPTS
    assert contract.get_limits()["max_content_bytes"] == mod.MAX_CONTENT_BYTES
    assert contract.get_limits()["max_excerpt_len"] == mod.MAX_EXCERPT_LEN
    assert contract.get_limits()["min_excerpt_len"] == mod.MIN_EXCERPT_LEN


# ---------------------------------------------------------------------------
# Milestone count
# ---------------------------------------------------------------------------


def test_max_milestones_accepted(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    engagement_id = _create(contract, direct_vm, direct_alice, numbered_milestones(MAX_MS))
    ids = contract.get_engagement(engagement_id)["milestone_ids"]
    # ordering with double digits: M10 must be LAST, never sorted before M2
    assert ids == ["M%d" % k for k in range(1, MAX_MS + 1)]
    assert ids[-1] == "M10"


def test_too_many_milestones_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        _create(contract, direct_vm, direct_alice, numbered_milestones(MAX_MS + 1))


# ---------------------------------------------------------------------------
# Criteria count per milestone
# ---------------------------------------------------------------------------


def test_max_criteria_accepted(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    engagement_id = _create(
        contract, direct_vm, direct_alice, _one_milestone(numbered_criteria(MAX_CR))
    )
    ms = contract.get_milestone(engagement_id, "M1")
    assert [c["id"] for c in ms["criteria"]] == ["C%d" % k for k in range(1, MAX_CR + 1)]


def test_too_many_criteria_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        _create(
            contract, direct_vm, direct_alice, _one_milestone(numbered_criteria(MAX_CR + 1))
        )


# ---------------------------------------------------------------------------
# Text lengths (characters, not bytes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,max_len",
    [
        ("title", 160),
        ("description", 4000),
    ],
)
def test_engagement_text_boundaries(
    direct_vm, direct_deploy, direct_alice, field, max_len
):
    contract = direct_deploy(CONTRACT)
    kwargs = {"title": "t", "description": "d", field: "x" * max_len}
    engagement_id = _create(
        contract,
        direct_vm,
        direct_alice,
        numbered_milestones(1),
        title=kwargs["title"],
        description=kwargs["description"],
    )
    assert engagement_id == "eng-1"

    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        kwargs[field] = "x" * (max_len + 1)
        _create(
            contract,
            direct_vm,
            direct_alice,
            numbered_milestones(1),
            title=kwargs["title"],
            description=kwargs["description"],
        )


def test_milestone_title_boundary(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    ok = [{"title": "m" * 120, "criteria": ["c"]}]
    assert _create(contract, direct_vm, direct_alice, ok) == "eng-1"
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        _create(contract, direct_vm, direct_alice, [{"title": "m" * 121, "criteria": ["c"]}])


def test_criterion_length_boundary(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT)
    ok = [{"title": "t", "criteria": ["c" * 600]}]
    assert _create(contract, direct_vm, direct_alice, ok) == "eng-1"
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        _create(contract, direct_vm, direct_alice, [{"title": "t", "criteria": ["c" * 601]}])


def test_characters_not_bytes(direct_vm, direct_deploy, direct_alice):
    """A 160-character title of 4-byte emoji is 640 bytes of calldata and is
    still accepted: text limits count characters."""
    contract = direct_deploy(CONTRACT)
    title = "\U0001f600" * 160  # 160 characters, 640 bytes
    assert len(title.encode("utf-8")) == 640
    engagement_id = _create(contract, direct_vm, direct_alice, numbered_milestones(1), title=title)
    assert contract.get_engagement(engagement_id)["title"] == title
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        _create(contract, direct_vm, direct_alice, numbered_milestones(1), title=title + "x")


# ---------------------------------------------------------------------------
# URL length
# ---------------------------------------------------------------------------


def test_url_length_boundary(direct_vm, direct_deploy, direct_alice, direct_bob):
    base = "https://evidence.example.org/"
    path_ok = "p" * (2048 - len(base))
    path_over = "p" * (2049 - len(base))
    contract, engagement_id = active_engagement(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    direct_vm.sender = direct_bob
    assert len(base + path_ok) == 2048
    submission_id = contract.submit_milestone(engagement_id, "M1", base + path_ok)
    assert submission_id == "sub-1"
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.submit_milestone(engagement_id, "M1", base + path_over)


# ---------------------------------------------------------------------------
# Attempts per milestone
# ---------------------------------------------------------------------------


def test_attempt_boundary(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, _ = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    direct_vm.sender = direct_bob
    for _ in range(MAX_ATTEMPTS - 1):
        contract.submit_milestone(engagement_id, "M1", "https://evidence.example.org/a")
    assert contract.get_milestone(engagement_id, "M1")["attempt_count"] == MAX_ATTEMPTS
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        contract.submit_milestone(engagement_id, "M1", "https://evidence.example.org/b")
    # other milestones are unaffected
    other = contract.submit_milestone(engagement_id, "M2", "https://evidence.example.org/c")
    assert contract.get_submission(other)["attempt_index"] == 1


# ---------------------------------------------------------------------------
# Content bytes / excerpt limits (evaluation path)
# ---------------------------------------------------------------------------


def test_max_content_bytes_accepted(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    quote = "exposes a GET /users endpoint"
    filler = "lorem ipsum dolor sit amet " * ((200000 - len(quote) - 2) // 27 + 1)
    body = (quote + "\n" + filler)[:200000]
    assert len(body.encode("utf-8")) <= 200000
    llm = [
        item("C1", "MET", quote),
        item("C2", "UNVERIFIABLE"),
        item("C3", "UNVERIFIABLE"),
    ]
    mock_world(direct_vm, body=body.encode("utf-8"), llm=llm)
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)
    submission = contract.get_submission(submission_id)
    assert submission["status"] == "EVALUATED"
    assert submission["evidence_hash"] == sha256_hex(body.encode("utf-8"))


def test_over_max_content_bytes_rejected(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    mock_world(direct_vm, body=b"x" * 200001)
    direct_vm.sender = direct_alice
    with pytest.raises(UserError, match=r"\[EXTERNAL\]"):
        contract.evaluate_submission(submission_id)


def test_max_excerpt_boundary(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    quote280 = "Q" + "u" * 279  # exactly max_excerpt_len
    body = "start " + quote280 + " end\n" + BODY_M1_EXTRA
    llm = [
        item("C1", "MET", quote280),
        item("C2", "MET", QUOTE_C2),
        item("C3", "MET", QUOTE_C3),
    ]
    mock_world(direct_vm, body=body.encode("utf-8"), llm=llm)
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)
    results = contract.get_submission(submission_id)["results"]
    assert results[0]["status"] == "MET"
    assert len(results[0]["evidence_excerpt"]) == 280


BODY_M1_EXTRA = (
    "The service exposes a GET /users endpoint returning JSON.\n"
    "Response payloads are documented with field-by-field tables.\n"
    "Test coverage reached 95% across the whole suite.\n"
)
QUOTE_C2 = "documented with field-by-field tables"
QUOTE_C3 = "Test coverage reached 95%"


def test_long_model_quote_is_truncated_to_limit(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    """A model quote longer than max_excerpt_len is cut to the limit; if the
    truncated quote remains literal, the result stays valid."""
    contract, engagement_id, submission_id = pending_submission(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    long_quote = "exposes a GET /users endpoint " + "z" * 400
    body = "The service " + long_quote + "\n" + BODY_M1_EXTRA
    llm = [
        item("C1", "MET", long_quote),
        item("C2", "MET", QUOTE_C2),
        item("C3", "MET", QUOTE_C3),
    ]
    mock_world(direct_vm, body=body.encode("utf-8"), llm=llm)
    direct_vm.sender = direct_alice
    contract.evaluate_submission(submission_id)
    results = contract.get_submission(submission_id)["results"]
    assert len(results[0]["evidence_excerpt"]) == 280
