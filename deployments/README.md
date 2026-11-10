# Deployments

One JSON file per network records the deployed instance. A record is only
meaningful together with verification - an address alone proves nothing about
which source produced it.

## Recorded deployments

| Network                             | Chain id | Contract       | Address                                        | Explorer |
| ----------------------------------- | -------- | -------------- | ---------------------------------------------- | -------- |
| GenLayer Studio (`studionet`)       | 61999    | `MilestoneProof` | `0x8ADE76f942b221c799c9529449a9B8feFbd419BF` | [explorer-studio.genlayer.com](https://explorer-studio.genlayer.com/address/0x8ADE76f942b221c799c9529449a9B8feFbd419BF) |

Full record with hashes and verification commands: [`studionet.json`](./studionet.json).

## Verifying the Studio deployment

1. **Hash the source you believe is deployed:**

   ```bash
   sha256sum contracts/milestone_proof.py
   # 8369b6a8b802df66fc26c235cf5cca639ddefb204fb53c9eb1313208a6cd221f
   ```

2. **Pull the on-chain code and compare** (GenLayer CLI):

   ```bash
   genlayer code 0x8ADE76f942b221c799c9529449a9B8feFbd419BF | sha256sum
   genlayer schema 0x8ADE76f942b221c799c9529449a9B8feFbd419BF
   ```

   Both hashes must be equal and the schema must show the 10 public methods
   (4 write + 6 view) listed in `docs/API.md`.

3. **Read `get_limits()` on the deployment** and check it equals the table in
   the README / `docs/API.md`:

   ```bash
   python3 tools/inspect_deployment.py --network studionet
   ```

4. **Run the read-only live probes** (free view calls against the real
   instance):

   ```bash
   MILESTONE_PROOF_LIVE=1 python3 -m pytest tests/integration/test_deployed_contract.py -q
   ```

Only when (2) and (3) pass can the address be considered to match the source
in this repository.

## Adding another network

Deploy with the GenLayer CLI, then add `<network>.json` here with the same
shape as `studionet.json`, run the four verification steps, and extend the
table above.
