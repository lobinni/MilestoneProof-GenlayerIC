"""Input validation tests: every malformed call must revert with [EXPECTED].

Boundary *counts* for the limits live in test_milestone_proof_limits.py; this
suite checks types, shapes and content rules.

Run:  pytest tests/direct/test_milestone_proof_validation.py -q
"""

import pytest
from genlayer.vm import UserError

from .milestone_proof_support import (
    DEFAULT_MILESTONES,
    URL,
    active_engagement,
    new_engagement,
    pending_submission,
)

CONTRACT_PATH = "contracts/milestone_proof.py"


def create(contract, vm, sender, **kwargs):
    vm.sender = sender
    args = {
        "title": "Docs build",
        "description": "Ship docs",
        "milestones": DEFAULT_MILESTONES,
    }
    args.update(kwargs)
    return contract.create_engagement(args["title"], args["description"], args["milestones"])


# ---------------------------------------------------------------------------
# Title / description
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("title", ["", "   ", "\t\n"])
def test_title_must_not_be_empty(direct_vm, direct_deploy, direct_alice, title):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(contract, direct_vm, direct_alice, title=title)


@pytest.mark.parametrize("title", [None, 7, ["x"], {"x": 1}])
def test_title_must_be_a_string(direct_vm, direct_deploy, direct_alice, title):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(contract, direct_vm, direct_alice, title=title)


def test_title_max_length(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    # exactly 160 characters is accepted
    engagement_id = create(contract, direct_vm, direct_alice, title="T" * 160)
    assert engagement_id == "eng-1"


def test_title_over_length(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(contract, direct_vm, direct_alice, title="T" * 161)


@pytest.mark.parametrize("title", ["has\nnewline", "has\ttab", "carriage\rreturn"])
def test_title_rejects_control_characters(
    direct_vm, direct_deploy, direct_alice, title
):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(contract, direct_vm, direct_alice, title=title)


def test_description_allows_newlines(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    engagement_id = create(
        contract, direct_vm, direct_alice, description="line one\nline two\tok"
    )
    assert contract.get_engagement(engagement_id)["found"] is True


def test_description_over_length(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(contract, direct_vm, direct_alice, description="d" * 4001)


# ---------------------------------------------------------------------------
# Milestones shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("milestones", [None, "x", 42, {"title": "t"}])
def test_milestones_must_be_a_list(direct_vm, direct_deploy, direct_alice, milestones):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(contract, direct_vm, direct_alice, milestones=milestones)


def test_milestones_empty_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(contract, direct_vm, direct_alice, milestones=[])


def test_milestone_must_be_an_object(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(contract, direct_vm, direct_alice, milestones=["not-a-dict"])


@pytest.mark.parametrize(
    "milestone",
    [
        {"title": "t"},  # missing criteria
        {"criteria": ["c"]},  # missing title
        {"title": "t", "criteria": ["c"], "extra": 1},  # extra key
        {"Title": "t", "criteria": ["c"]},  # wrong key casing
    ],
)
def test_milestone_keys_are_exact(direct_vm, direct_deploy, direct_alice, milestone):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(contract, direct_vm, direct_alice, milestones=[milestone])


def test_milestone_titles_must_be_distinct(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    milestones = [
        {"title": "Phase One", "criteria": ["c one"]},
        {"title": "  phase   one ", "criteria": ["c two"]},  # same after normalizing
    ]
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(contract, direct_vm, direct_alice, milestones=milestones)


def test_milestone_title_over_length(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(
            contract,
            direct_vm,
            direct_alice,
            milestones=[{"title": "m" * 121, "criteria": ["c"]}],
        )


# ---------------------------------------------------------------------------
# Criteria
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("criteria", [None, "c", 3, {"c": 1}])
def test_criteria_must_be_a_list(direct_vm, direct_deploy, direct_alice, criteria):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(
            contract,
            direct_vm,
            direct_alice,
            milestones=[{"title": "t", "criteria": criteria}],
        )


def test_criteria_empty_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(
            contract, direct_vm, direct_alice, milestones=[{"title": "t", "criteria": []}]
        )


def test_criteria_must_be_distinct_case_insensitive(
    direct_vm, direct_deploy, direct_alice
):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(
            contract,
            direct_vm,
            direct_alice,
            milestones=[
                {"title": "t", "criteria": ["Same Thing", "  same   thing "]}
            ],
        )


@pytest.mark.parametrize("criterion", [None, 5, ["c"], {"c": 1}, "", "   "])
def test_criterion_must_be_non_empty_string(
    direct_vm, direct_deploy, direct_alice, criterion
):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(
            contract,
            direct_vm,
            direct_alice,
            milestones=[{"title": "t", "criteria": [criterion]}],
        )


def test_criterion_over_length(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(
            contract,
            direct_vm,
            direct_alice,
            milestones=[{"title": "t", "criteria": ["c" * 601]}],
        )


@pytest.mark.parametrize("criterion", ["with\nnewline", "with\ttab"])
def test_criterion_rejects_control_characters(
    direct_vm, direct_deploy, direct_alice, criterion
):
    contract = direct_deploy(CONTRACT_PATH)
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        create(
            contract,
            direct_vm,
            direct_alice,
            milestones=[{"title": "t", "criteria": [criterion]}],
        )


# ---------------------------------------------------------------------------
# URLs (submissions)
# ---------------------------------------------------------------------------


def _submit_with_url(vm, deploy, client, worker, url):
    contract, engagement_id = active_engagement(vm, deploy, client, worker)
    vm.sender = worker
    return contract.submit_milestone(engagement_id, "M1", url)


@pytest.mark.parametrize(
    "url",
    [
        "http://evidence.example.org/x",  # not https
        "ftp://evidence.example.org/x",
        "evidence.example.org/x",  # no scheme
        "https://",  # no host
        "https:///path-only",
        "https://user:pw@evidence.example.org/x",  # credentials
        "https://user@evidence.example.org/x",
        "https://127.0.0.1/x",  # IPv4 literal
        "https://[::1]/x",  # IPv6 literal
        "https://localhost/x",  # reserved
        "https://service.internal/x",
        "https://host.test/x",
        "https://singlelabel/x",  # one label only
        "https://example.c/x",  # single-char tld
        "https://example.123/x",  # numeric tld
        "https://ex_ample.com/x",  # underscore in label
        "https://-example.com/x",  # leading dash
        "https://example-.com/x",  # trailing dash
        "https://exa mple.com/x",  # space
        "https://example..com/x",  # empty label
        "",  # empty
        "   ",
        "https://evidence.example.org/" + "p" * 3000,  # over MAX_URL_LEN
    ],
)
def test_submit_rejects_bad_urls(
    direct_vm, direct_deploy, direct_alice, direct_bob, url
):
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        _submit_with_url(direct_vm, direct_deploy, direct_alice, direct_bob, url)


@pytest.mark.parametrize("url", [None, 5, ["https://x.co"], {"u": 1}])
def test_submit_rejects_non_string_urls(
    direct_vm, direct_deploy, direct_alice, direct_bob, url
):
    with pytest.raises(UserError, match=r"\[EXPECTED\]"):
        _submit_with_url(direct_vm, direct_deploy, direct_alice, direct_bob, url)


@pytest.mark.parametrize(
    "url",
    [
        URL,
        "https://evidence.example.org:8443/path?q=1#frag",  # port + query + fragment
        "https://xn--nxasmq6b.example.org/x",  # punycode tld label
        "https://deep.sub.domain.example.org/a/b/c",
        "https://evidence.example.org/%20%41",  # percent-encoded
    ],
)
def test_submit_accepts_public_https_urls(
    direct_vm, direct_deploy, direct_alice, direct_bob, url
):
    submission_id = _submit_with_url(
        direct_vm, direct_deploy, direct_alice, direct_bob, url
    )
    assert submission_id == "sub-1"


# ---------------------------------------------------------------------------
# Id arguments
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["get_engagement", "get_milestone", "get_submission"])
def test_view_of_missing_ids_reports_not_found(
    direct_vm, direct_deploy, direct_alice, method
):
    contract, engagement_id = new_engagement(direct_vm, direct_deploy, direct_alice)
    view = getattr(contract, method)
    if method == "get_milestone":
        result = view(engagement_id, "M8")
        assert result["found"] is False
    else:
        assert view("missing-id")["found"] is False
