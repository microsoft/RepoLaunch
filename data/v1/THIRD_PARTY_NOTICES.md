# Third-Party Data and License Notices

Change2Task task pairs are derived from public benchmark records and public
GitHub repositories. This release does not claim ownership of third-party issue
text, patches, tests, source snippets, CVE descriptions, or repository history.

The Change2Task-authored schema, export tooling, documentation, and metadata are
distributed under the repository MIT license. Third-party task material remains
under its original terms.

The source registry in `sources.json` records the official project URLs and
license status verified on 2026-10-09. Important boundaries include:

- SWE-bench tooling is MIT, while embedded upstream patches and tests retain
  source repository licenses.
- SWE-bench-Live declares MIT for its release, with source repository licenses
  still applicable to collected repository material.
- SWE-bench Pro explicitly leaves task content under the licenses of its source
  repositories.
- SWE-rebench V2 PRs declares CC BY 4.0 for the dataset and MIT for tooling and
  asks users to respect its per-instance repository-license metadata.
- FEA-Bench publishes essential metadata under repository-specific terms and
  does not provide a blanket license for all task material.
- SWE-Bench++ uses custom non-commercial research, academic, and educational
  terms in addition to source repository terms.
- PyMigBench declares MIT for its release.
- PatchEval declares Apache-2.0 for its release.
- Vul4J separates a CC BY 4.0 dataset from GPL-3.0 tooling.
- VJBench's artifact repository is BSD-3-Clause, but the subject repositories
  do not share one blanket license.

Users are responsible for checking the license of each record's
`repository.url` at the pinned commit before redistribution, model training,
commercial use, or publication of derived artifacts.

The pinned-base license inventory found no license file or project declaration
for `huntwelch/mongobot`, `pgjones/faster_than_flask_article`, and
`snemes/malware-analysis`. Their three dataset rows therefore omit copied patch
and test-patch content and are published as reference-only metadata. The
records retain repository URLs, commits, task contracts, changed paths, and
content hashes so that authorized users can reconstruct them from their lawful
source.

The release applies the same reference-only treatment to 30 FEA-Bench rows,
two SWE-Bench++ rows, three `sdv-dev/SDV` rows, and two `hashicorp/consul`
rows. The first two groups follow source dataset redistribution restrictions;
the latter repositories use Business Source License 1.1 at their pinned bases.

No task in this release should be interpreted as granting trademark, patent, or
other rights beyond those provided by the applicable upstream licenses.
