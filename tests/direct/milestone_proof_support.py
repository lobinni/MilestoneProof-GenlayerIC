"""Shared helpers for the Milestone Proof direct-mode tests.

Consensus model used by the attack tests
-----------------------------------------
Direct mode only executes the LEADER path; the validator is captured and has
to be invoked explicitly (``direct_vm.run_validator``). To model the real
protocol:

  1. the leader executes and proposes a verdict (``capture_leader``);
  2. the state is reverted: in the protocol, the leader's verdict is NOT
     applied until the validators accept it;
  3. a FORGED verdict is submitted to the validator, which must reject it;
  4. the submission must still be PENDING (nothing was stored).
"""

import copy
import hashlib
import json
import os
import sys

# Mutation/audit tooling can point the whole suite at a mutated COPY via this
# variable, so the real contract file is never modified.
CONTRACT = os.environ.get("MILESTONE_PROOF_CONTRACT", "contracts/milestone_proof.py")

URL = "https://evidence.example.org/milestone-one.md"
URL_2 = "https://evidence.example.org/milestone-one-v2.md"
URL_M2 = "https://evidence.example.org/milestone-two.md"

BODY_M1 = (
    "Milestone one evidence report\n"
    "\n"
    "The service exposes a GET /users endpoint returning JSON.\n"
    "Response payloads are documented with field-by-field tables.\n"
    "Test coverage reached 95% across the whole suite.\n"
)
BODY_M2 = (
    "Milestone two evidence report\n"
    "\n"
    "The deployed service is reachable at a public URL.\n"
    "The release is tagged v1.0.0 and signed by the maintainer.\n"
)

DEFAULT_MILESTONES = [
    {
        "title": "API documentation",
        "criteria": [
            "The evidence documents a GET /users endpoint",
            "The evidence documents the response payload fields",
            "Test coverage is above 90%",
        ],
    },
    {
        "title": "Release packaging",
        "criteria": [
            "The evidence references a public deployment URL",
            "The evidence declares a signed release tag",
        ],
    },
]

QUOTES_M1 = {
    "C1": "exposes a GET /users endpoint",
    "C2": "documented with field-by-field tables",
    "C3": "Test coverage reached 95%",
}

QUOTES_M2 = {
    "C1": "reachable at a public URL",
    "C2": "signed by the maintainer",
}


def hex_of(address) -> str:
    """Checksummed hex of a fixture address (fixtures are raw 20-byte values)."""
    if hasattr(address, "as_hex"):
        return address.as_hex
    from genlayer.py.types import Address  # importable once a contract was deployed

    return Address(address).as_hex


# Single source of truth for the limits the tests expect.
# test_milestone_proof_limits.py asserts that the contract constants and
# get_limits() equal this table, so a changed limit cannot leave stale numbers
# behind in the suite.
LIMITS = {
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


def numbered_criteria(count: int, length: int = 60) -> list:
    """``count`` distinct criteria of exactly ``length`` characters."""
    out = []
    for k in range(1, count + 1):
        prefix = "Requirement %d: " % k
        out.append(prefix + "x" * (length - len(prefix)))
    return out


def numbered_milestones(count: int, criteria_per: int = 1, length: int = 60) -> list:
    """``count`` milestones with distinct titles and distinct criteria."""
    out = []
    for k in range(1, count + 1):
        out.append(
            {
                "title": "Phase %d" % k,
                "criteria": [
                    "Phase %d requirement %d: " % (k, j)
                    + "x" * (length - len("Phase %d requirement %d: " % (k, j)))
                    for j in range(1, criteria_per + 1)
                ],
            }
        )
    return out


def requirement_quote(phase: int, k: int) -> str:
    return "Phase %d requirement %d is fully satisfied by this evidence." % (phase, k)


def document_for(milestones: list) -> str:
    """A deliverable that satisfies every criterion of the given milestones:
    one literal quote line per criterion."""
    lines = ["Evidence dossier.", ""]
    for m in milestones:
        for c in m["criteria"]:
            # embed the criterion's own words so the model has a literal quote
            lines.append(c + " -- confirmed in this document.")
    return "\n".join(lines) + "\n"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(obj) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def expected_terms_hash(title: str, description: str, milestones: list) -> str:
    """Independent re-implementation of the contract's terms hash."""
    terms = {
        "v": 1,
        "title": title,
        "description": description,
        "milestones": [
            {
                "id": "M%d" % (i + 1),
                "title": m["title"],
                "criteria": [
                    {"id": "C%d" % (j + 1), "text": t}
                    for j, t in enumerate(m["criteria"])
                ],
            }
            for i, m in enumerate(milestones)
        ],
    }
    return sha256_hex(canonical(terms))


def item(cid, status, quote=""):
    return {"criterion_id": cid, "status": status, "evidence_excerpt": quote}


def llm_payload(*items) -> str:
    return json.dumps({"results": list(items)})


def all_met(quotes=None, count=3):
    quotes = quotes or QUOTES_M1
    return [
        item("C%d" % k, "MET", quotes["C%d" % k]) for k in range(1, count + 1)
    ]


def mock_world(vm, body=BODY_M1, llm=None, status=200):
    """Reset the mocks: the web returns ``body`` and the LLM returns the
    results list ``llm`` (defaults to every criterion MET with its quote)."""
    vm.clear_mocks()
    if isinstance(body, str):
        body = body.encode("utf-8")
    vm.mock_web(r"evidence\\.example\\.org", {"status": status, "body": body})
    vm.mock_llm(r".*", llm_payload(*(llm if llm is not None else all_met())))


def module(vm):
    """Python module of the contract loaded in direct mode (pure functions)."""
    return sys.modules["_contract_milestone_proof"]


def new_engagement(
    vm, deploy, client, milestones=None, title="Docs build", description="Ship docs"
):
    contract = deploy(CONTRACT)
    vm.sender = client
    engagement_id = contract.create_engagement(
        title, description, milestones if milestones is not None else DEFAULT_MILESTONES
    )
    return contract, engagement_id


def active_engagement(vm, deploy, client, worker, milestones=None):
    """Created + claimed engagement. Returns (contract, engagement_id)."""
    contract, engagement_id = new_engagement(vm, deploy, client, milestones=milestones)
    vm.sender = worker
    contract.claim_engagement(engagement_id)
    return contract, engagement_id


def pending_submission(
    vm, deploy, client, worker, url=URL, milestones=None, milestone_id="M1"
):
    """Active engagement with one pending submission. Returns
    (contract, engagement_id, submission_id)."""
    contract, engagement_id = active_engagement(
        vm, deploy, client, worker, milestones=milestones
    )
    vm.sender = worker
    submission_id = contract.submit_milestone(engagement_id, milestone_id, url)
    return contract, engagement_id, submission_id


def capture_leader(vm, contract, sender, submission_id):
    """The leader proposes; the state is reverted until a validator accepts."""
    snap = vm.snapshot()
    vm.sender = sender
    contract.evaluate_submission(submission_id)
    captured = vm._captured_validators[-1]
    proposal = copy.deepcopy(captured[0])
    vm.revert(snap)
    vm._captured_validators.append(captured)
    return proposal


def validator_accepts(vm, proposal) -> bool:
    """Validator vote on a proposed (possibly forged) verdict."""
    return vm.run_validator(leader_result=proposal) is True


def assert_unapplied(contract, engagement_id, submission_id, milestone_id="M1"):
    """A rejected verdict never reaches storage."""
    submission = contract.get_submission(submission_id)
    assert submission["status"] == "PENDING", submission
    assert submission["milestone_status"] == ""
    assert submission["evidence_hash"] == ""
    assert submission["results"] == []
    assert contract.get_engagement(engagement_id)["status"] == "ACTIVE"
    assert contract.get_milestone(engagement_id, milestone_id)["status"] == "AWAITING"
