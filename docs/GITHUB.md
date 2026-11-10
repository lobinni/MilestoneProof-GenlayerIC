# Publishing to GitHub

This project is a **pure Intelligent Contract repository** - contract, tests,
docs, samples, deployment records. No frontend is part of it. The commands
below stage exactly the contract tree, so the hosted repository is always
submission-clean.

## 1. Sanity pass first

```bash
python3 -m pytest tests/offline -q        # 100 pure-logic tests, no GenVM
sha256sum contracts/milestone_proof.py    # must match deployments/studionet.json
```

## 2. Initialize and stage ONLY the contract project

```bash
git init

# stage the Intelligent Contract deliverable and its supporting material,
# explicitly (pathspec = what the repo will ever contain):
git add contracts tests docs samples deployments tools \
        README.md requirements.txt pytest.ini gltest.config.yaml .gitignore

# confirm nothing web-related slipped in:
git status --short      # must NOT list src/, index.html, package.json, ...
```

## 3. Commit, branch, remote, push

```bash
git commit -m "MilestoneProof: consensus-verified milestone work agreements (GenLayer Intelligent Contract)

- contracts/milestone_proof.py: 10-method contract (4 writes, 6 views)
- four test tiers: offline oracle (100 tests), direct mode (mocked consensus), Studio integration, live-deployment probes
- deployment record for Studionet: 0x8ADE76f942b221c799c9529449a9B8feFbd419BF
- docs: DESIGN / API / TESTING / SECURITY / FRONTEND; samples + hashing quickstart"

git branch -M main
git remote add origin git@github.com:YOUR_USER/milestone-proof.git
git push -u origin main
```

Alternative with the GitHub CLI (creates the repo first):

```bash
gh repo create milestone-proof --public --source=. --remote=origin
git push -u origin main
```

## 4. Tag the audited/deployed revision

The Studionet deployment was made from the source whose SHA-256 is recorded
in `deployments/studionet.json`. Tag it so reviewers can check out exactly
that revision:

```bash
git tag -a studionet-1 -m "Deployed on GenLayer Studio at 0x8ADE76f942b221c799c9529449a9B8feFbd419BF"
git push origin studionet-1
```

## 5. When a program asks for "the contract only"

Either point them at the repository (it already is contract-only), or emit a
minimal bundle:

```bash
bash tools/package_submission.sh           # builds ./milestone-proof-submission/
```

That archive contains `contracts/` plus `docs/`, `tests/`, `samples/`,
`deployments/` and the pinned toolchain - never a frontend file.
