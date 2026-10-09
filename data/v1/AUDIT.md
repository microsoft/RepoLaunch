# Public Release Audit

Audit date: 2026-10-09

## Scope

The audit covers only the public task corpus in this directory. Experimental
agent runs and RQ evaluation results are outside the release.

## Integrity checks

- 900 JSONL records and 900 unique public `pair_id` values.
- Family counts: 500 Bug Fix and 100 each for Feature Addition, Test
  Generation, API Migration, and Security Repair.
- 252 unique public GitHub repository slugs.
- 12 registered public source collections/releases.
- 860 records contain materialized challenge/test artifacts.
- Forty records are reference-only and contain no copied task statement,
  verifier, or patch content from the restricted source.
- Every record has non-empty task text, base revision, task contract, and
  content hashes.
- Every embedded unified diff parses successfully.
- Every record follows the strict task-only field allowlist.
- SHA-256 checksums cover every release file except the checksum file itself.

## Evaluation-data exclusion

The public schema excludes:

- agent names, model names, and provider routes;
- construction-attempt histories and route-level experiment labels;
- A/B execution order;
- agent patches, transcripts, and model responses;
- solved/unsolved outcomes and matched-result quadrants;
- fidelity scores and semantic judgments;
- token, cache-token, time, cost, CPU, memory, and disk telemetry;
- RQ summaries, receipts, checkpoints, and run identifiers.

Target tests, regression tests, verifier commands, challenge patches, and
restoration patches are retained because they define the executable task rather
than an agent's evaluation outcome.

## Privacy and secret review

- Known Change2Task workstation, cache, run, handoff, and artifact paths: none.
- User-home paths in task text or selectors: replaced with portable
  placeholders.
- Email addresses in task statements: replaced with `<EMAIL_REDACTED>`.
- GitHub personal-access-token patterns: none.
- AWS access-key patterns: none.
- Complete PEM private-key blocks: none.
- Local model credentials or company-route metadata: none.

Some public source-code patches contain strings such as
`-----BEGIN PRIVATE KEY-----` because they modify secret-detection logic. The
audit verifies that no complete PEM private-key block is present.

Literal fixture emails, localhost values, and absolute paths inside public
source-code patches are preserved when they are required patch content.

## Materialization

All previously path-referenced challenge patches were copied into the public
JSONL records. No local artifact path is required at consumption time.

Challenge and restoration use the same materialized patch with opposite apply
modes. In 859 embedded records the modes are forward/reverse. One recovered Test
Generation record is reverse/forward. Both modes are explicit in every
materialized record and avoid dependence on machine-local gold-patch paths.

Forty records are reference-only: 30 FEA-Bench rows, two SWE-Bench++ rows, five
rows from Business Source License repositories, and three rows with no license
file or project declaration at the pinned upstream base. Their patch hashes are
retained for integrity, but copied task text, verifier data, and patch content
are not redistributed.
