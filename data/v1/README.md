# Change2Task Public Task Corpus v1

This directory contains the task-only public release corresponding to the
900 paired task sets reported in the Change2Task paper.

It contains no coding-agent evaluation outputs, solved/unsolved labels, model
identities, prompts or responses, token usage, timing, cost, resource telemetry,
agreement statistics, or RQ summaries.

## Contents

- `task_pairs/bug_fix.jsonl`: 500 task pairs.
- `task_pairs/feature_addition.jsonl`: 100 task pairs.
- `task_pairs/test_generation.jsonl`: 100 task pairs.
- `task_pairs/api_migration.jsonl`: 100 task pairs.
- `task_pairs/security_repair.jsonl`: 100 task pairs.
- `schema.json`: machine-readable public record schema.
- `manifest.json`: counts, hashes, source distribution, and release policy.
- `sources.json`: official source URLs and license/provenance notes.
- `repository_licenses.json`: license-file inventory at every pinned modern base.
- `THIRD_PARTY_NOTICES.md`: redistribution and upstream-license boundaries.
- `AUDIT.md`: release integrity and privacy review.
- `CHECKSUMS.sha256`: SHA-256 for every other file in this directory.

Each JSONL row contains one provenance-linked pair:

- `historical_task`: the public benchmark task at its historical revision;
- `change2task_task`: the reconstructed task on a healthy modern revision.

The public `pair_id` combines task family and frozen case identity. It is the
release uniqueness key. The same upstream source case can legitimately appear
under two different task families with different task contracts.

## Counts

The corpus contains exactly 900 unique pair IDs across 252 public GitHub
repository slugs and 12 public benchmark collections/releases.

The modern task side includes a portable challenge/restoration operation for
every record. For 860 records cleared by the release license gate, patch content
is embedded. In 859
of those records, consumers create the challenge with `git apply` and restore
it with `git apply --reverse`; one recovered Test Generation record uses the
opposite directions.

Forty rows remain in the 900-pair corpus as reference-only metadata with patch
hashes. Patch and verifier content is omitted for 30 FEA-Bench rows, two
SWE-Bench++ rows, five rows from Business Source License repositories, and
three PyMigBench rows whose pinned repositories have no detected license.

## Portable paths

Machine-specific artifact references were resolved before release. No
`/Users/...`, private workspace, run, handoff, or cache path is needed to read
the dataset.

Portable task selectors use:

- `{REPO_ROOT}` for repository-root paths;
- `{USER_HOME}` for user-home paths appearing in public issue text;
- `{JAVA_HOME}` where a verifier requires a Java installation.

Consumers should expand placeholders for their execution environment.

Literal absolute paths that are part of an upstream source-code patch remain
unchanged because modifying patch content would invalidate the task.

## Privacy

The export uses a strict field allowlist. Personal email addresses in task
statements are replaced with `<EMAIL_REDACTED>`. User-home paths in task
statements and verifier selectors are replaced with portable placeholders.

Patches and test patches are preserved from public repositories because they
are executable task content. The release scan found no complete private-key
block, GitHub token, AWS access key, local Change2Task workspace path, or model
credential.

## Licensing

The repository MIT license covers Change2Task-authored packaging, schema,
documentation, and metadata. It does not relicense third-party issue text,
patches, tests, or source snippets.

Every record identifies its public repository and source collection. Those
materials remain subject to the corresponding benchmark terms and upstream
repository license. Review `sources.json` and `THIRD_PARTY_NOTICES.md` before
redistribution or commercial use. In particular, SWE-Bench++ uses custom
non-commercial terms, and FEA-Bench does not provide a blanket dataset license
for all repository material.

`repository_licenses.json` is an informational pinned-revision scan, not legal
advice. It reports 246 repositories with a classified root license, three with
a license declared in project metadata, and three with no license file or
declaration at the pinned base.

## Validation

From the repository root:

```bash
python scripts/validate_public_dataset.py data/v1
sha256sum -c data/v1/CHECKSUMS.sha256
```

## Citation

```bibtex
@article{qi2026change2task,
  title   = {Change2Task: From Repository Changes to Executable Coding Agent Tasks and Environments},
  author  = {Haomin Qi and Xingliang Wang and Xuanqi Gao and Baihui Sang and Xin Zhang and Minghua Ma and Pengfei Gao and Yu Kang and Qingwei Lin and Saravan Rajmohan and Dongmei Zhang and Qi Zhang},
  journal = {arXiv preprint arXiv:2607.28591},
  year    = {2026},
  url     = {https://arxiv.org/abs/2607.28591}
}
```
