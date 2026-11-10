# Security model

## The one-sentence invariant

> No verification verdict is stored unless the validators have independently
> checked every decisive field of the submission, using the same agreement
> terms (from contract storage) and evidence they fetched themselves.

Every stored field is either **compared** by each validator or **derived** by
deterministic code from compared fields. There is no third category.

## Guarantees

1. **Terms are frozen.** Criteria, milestone titles and parties are set at
   creation/claim time and never mutated. `terms_hash` and `agreement_hash`
   commit to them (SHA-256 over canonical JSON).
2. **Independent evidence.** Each validator fetches the URL itself and hashes
   the exact bytes. A leader cannot point the validators at different content
   than it judged: hash and size must match.
3. **Exact per-criterion agreement.** Status *and* reason code of every
   criterion must match the validator's own run. Agreeing on the milestone
   status alone is not enough.
4. **Complete and ordered results.** The verdict must cover exactly the
   original `C1..Ck` of that milestone, in order - nothing missing, duplicated,
   extra or renamed.
5. **Quotes must be literal.** `MET` requires a verbatim quote (8..280 chars,
   or the whole short document) that appears in the validator's own fetched
   content. A fabricated quote - or a MET with none - is downgraded to
   `UNVERIFIABLE`, and a forged one is rejected outright.
6. **Derived outcomes.** `milestone_status` and engagement completion are
   computed from criterion statuses by contract code. The model never supplies
   scores, summaries or final answers.
7. **Keyed, append-only records.** Submissions are counter-keyed, bound to
   engagement + milestone + attempt + agreement hash, and never overwritten.
   SUPERSEDED attempts are kept for audit.
8. **Fail safe.** HTTP errors, empty/oversized/non-UTF-8 payloads and unusable
   model output abort the transaction and store nothing. `[TRANSIENT]` is
   retryable; `[EXTERNAL]` means the source; `[EXPECTED]` means the caller.

## Prompt-injection posture

The prompt is a fixed template. Evidence content is delimited and neutralized
(`<<` → `< <`), so the document cannot forge the closing marker, and it is
labelled as untrusted data. The model's only influence is a per-criterion
(status, quote) choice that the contract then constrains.

This is defense in depth, **not immunity**: a model fooled *identically on
every node* while still quoting a real sentence of the document can approve a
criterion that does not genuinely hold. A quote proves presence in the
document, never relevance to the criterion. Write criteria that are objective
and falsifiable - "documents a GET /users endpoint" is checkable; "the API is
well designed" is not.

## Trust assumptions

- GenLayer validator consensus is honest (standard assumption of the network).
- The evidence URL is stable while consensus runs; a document that changes
  between leader and validator fetches simply fails consensus (hashes differ)
  and nothing is stored - it does not produce a wrong verdict.
- The evidence host is reachable from every validator.

## Known limitations

- **Limits are unmeasured on a live network.** Model context windows, calldata
  acceptance, gas and the real cross-model disagreement rate bound what is
  practical at the maximum sizes. Start with soft limits below the ceilings.
- **Up to 280 characters per criterion** (plus statuses) are stored on chain
  publicly per evaluated attempt, at most `max_criteria` quotes per
  submission. The raw document is never stored - only its SHA-256 and size.
- **SSRF scope.** The contract rejects non-HTTPS schemes, credentials, IP
  literals and reserved TLDs, but cannot decide whether a public-looking DNS
  name resolves to a private address. Node-level egress policy must block
  that.
- **No adjudication of taste.** Criteria that a text-only judge cannot decide
  yield `UNVERIFIABLE` by design; the contract reports, it does not arbitrate.
- **No economic layer.** There is deliberately no escrow, fee or stake in the
  contract; incentives and settlement belong to a separate layer.

## Reporting

If you find a case where a malformed or forged verdict reaches storage, or a
check above can be bypassed, please open a security issue with a reproduction
against `tests/direct` (the harness makes forging one line of code).
