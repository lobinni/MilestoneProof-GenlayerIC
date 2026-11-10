#!/usr/bin/env python3
"""Offline quickstart for Milestone Proof - no dependencies, no network.

This script does NOT deploy or call the contract. It walks through the exact
data the contract works with so you can verify the hashing scheme end to end
with nothing but the Python 3.9+ standard library:

  1. loads sample_engagement.json and assigns the contract ids (M1..M2, C1..Ck)
  2. computes terms_hash exactly like _terms_hash() in the contract does
  3. computes agreement_hash for two example addresses (like claim_engagement)
  4. hashes sample_deliverable.md exactly like the validators do
  5. prints the JSON shape the model must return for milestone M1

Use it as a ground-truth oracle when you build a client, a frontend or new
tests. Run:  python3 samples/quickstart.py
"""

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def canonical(obj) -> bytes:
    """Canonical serialization: JSON, sorted keys, no spaces, ASCII escapes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    with open(os.path.join(HERE, "sample_engagement.json"), "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    # 1) contract-side id assignment (creation order, never wallet-derived)
    milestones = []
    for i, m in enumerate(payload["milestones"]):
        milestones.append(
            {
                "id": "M%d" % (i + 1),
                "title": m["title"],
                "criteria": [
                    {"id": "C%d" % (j + 1), "text": c}
                    for j, c in enumerate(m["criteria"])
                ],
            }
        )

    # 2) terms_hash - the frozen terms commitment (create_engagement)
    terms = {
        "v": 1,
        "title": payload["title"],
        "description": payload["description"],
        "milestones": milestones,
    }
    terms_hash = sha256_hex(canonical(terms))

    # 3) agreement_hash - binds terms + both parties (claim_engagement)
    agreement = {
        "v": 1,
        "engagement_id": "eng-1",
        "client": "0x" + "aa" * 20,  # example client address
        "worker": "0x" + "bb" * 20,  # example worker address
        "terms_hash": terms_hash,
    }
    agreement_hash = sha256_hex(canonical(agreement))

    # 4) evidence_hash - what every validator computes, independently
    with open(os.path.join(HERE, "sample_deliverable.md"), "rb") as fh:
        body = fh.read()
    evidence_hash = sha256_hex(body)

    print("== Milestone Proof - offline quickstart ==")
    print()
    print("engagement_id : eng-1")
    print("milestones    : %s" % ", ".join(m["id"] for m in milestones))
    for m in milestones:
        print("  %s %-22s criteria: %s" % (m["id"], m["title"], ", ".join(c["id"] for c in m["criteria"])))
    print()
    print("terms_hash     :", terms_hash)
    print("agreement_hash :", agreement_hash)
    print()
    print("evidence file  : sample_deliverable.md")
    print("evidence_bytes :", len(body))
    print("evidence_hash  :", evidence_hash)
    print()
    model_output = {
        "results": [
            {
                "criterion_id": c["id"],
                "status": "MET|NOT_MET|UNVERIFIABLE",
                "evidence_excerpt": "<verbatim quote, 8..280 chars, or ''>",
            }
            for c in milestones[0]["criteria"]
        ]
    }
    print("model must return (milestone M1):")
    print(json.dumps(model_output, indent=2))
    print()
    print("Next step: run the real flow with the direct-mode tests:")
    print("  pip install -r requirements.txt")
    print("  pytest tests/direct -q")


if __name__ == "__main__":
    main()
