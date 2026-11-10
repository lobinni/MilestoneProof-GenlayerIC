"""Read-only tests against the recorded live deployment.

These exercise the REAL deployed contract (default: the Studionet instance in
deployments/studionet.json) using only free view calls. They are skipped
unless explicitly enabled, so `gltest tests/integration` and plain CI runs are
unaffected.

Run against the recorded Studio deployment:

    pip install genlayer-py
    MILESTONE_PROOF_LIVE=1 python3 -m pytest tests/integration/test_deployed_contract.py -q

Target another address/network:

    MILESTONE_PROOF_LIVE=1 \\
    MILESTONE_PROOF_NETWORK=studionet \\
    MILESTONE_PROOF_ADDRESS=0x... \\
    python3 -m pytest tests/integration/test_deployed_contract.py -q
"""

import json
import os

import pytest

LIVE = os.environ.get("MILESTONE_PROOF_LIVE") == "1"
NETWORK = os.environ.get("MILESTONE_PROOF_NETWORK", "studionet")
ADDRESS = os.environ.get(
    "MILESTONE_PROOF_ADDRESS", "0x8ADE76f942b221c799c9529449a9B8feFbd419BF"
)

pytestmark = pytest.mark.skipif(
    not LIVE, reason="set MILESTONE_PROOF_LIVE=1 to run against the live network"
)

EXPECTED_LIMITS = {
    "schema_version": 1,
    "min_milestones": 1,
    "max_milestones": 10,
    "min_criteria": 1,
    "max_criteria": 8,
    "max_attempts": 3,
    "max_title_len": 160,
    "max_description_len": 4000,
    "max_milestone_title_len": 120,
    "max_criterion_len": 600,
    "max_url_len": 2048,
    "max_content_bytes": 200000,
    "min_excerpt_len": 8,
    "max_excerpt_len": 280,
}


def _decode(value):
    return json.loads(value) if isinstance(value, str) else value


@pytest.fixture(scope="module")
def client():
    from genlayer_py import create_client
    from genlayer_py import chains

    chain = getattr(chains, NETWORK)
    return create_client(chain=chain)


def _read(client, function, args):
    return _decode(client.read_contract(address=ADDRESS, function_name=function, args=args))


def test_get_limits_matches_repository_constants(client):
    limits = _read(client, "get_limits", [])
    assert limits == EXPECTED_LIMITS, "deployment differs from the documented limits"


def test_absent_engagement_reports_not_found(client):
    result = _read(client, "get_engagement", ["eng-999999999"])
    assert result == {"found": False, "id": "eng-999999999"}


def test_absent_milestone_reports_not_found(client):
    result = _read(client, "get_milestone", ["eng-999999999", "M1"])
    assert result == {"found": False, "id": "M1"}


def test_absent_submission_reports_not_found(client):
    result = _read(client, "get_submission", ["sub-999999999"])
    assert result == {"found": False, "submission_id": "sub-999999999"}


def test_absent_submission_id_lookup_returns_empty_string(client):
    assert _read(client, "get_submission_id", ["eng-999999999", "M1", 1]) == ""


def test_absent_milestone_submissions_returns_empty_list(client):
    assert _read(client, "get_milestone_submissions", ["eng-999999999", "M1"]) == []


def test_first_engagement_shape_if_present(client):
    """If eng-1 exists on the deployment, its public shape must be intact."""
    engagement = _read(client, "get_engagement", ["eng-1"])
    if not engagement.get("found"):
        pytest.skip("no engagements recorded on this deployment yet")
    for key in (
        "id",
        "client",
        "worker",
        "title",
        "description",
        "terms_hash",
        "agreement_hash",
        "status",
        "milestone_ids",
        "milestones",
    ):
        assert key in engagement, key
    assert engagement["status"] in ("OPEN", "ACTIVE", "COMPLETED")
    assert len(engagement["terms_hash"]) == 64
    assert len(engagement["milestone_ids"]) == len(engagement["milestones"])
