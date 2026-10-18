# Maintenance and historical provenance

Current maintainer: [Omkar](https://github.com/omkark2404). Current repository: https://github.com/omkark2404/finops-copilot .

The historical clone instructions referenced another account/repository. They were corrected to this maintained repository. That correction is a setup/branding change, not a claim that Omkar originally wrote all imported code. On 17 October 2026, the maintainer confirmed that this project started from someone else’s repository. The exact original source URL, applicable source license, and relationship between the accounts remain unverified; the maintainer must establish them before asserting original sole authorship or relicensing.

Observable history is preserved: main's initial commit 8c1900d (February 10, 2026) and master's cddf8be (September 13, 2026) contain identical initial source trees. f7fb9d5 and acddf65 also match. Their author metadata uses the name Omkar and an example-domain email. GitHub reports this repository as non-fork, which does not rule out an ordinary source import. These facts do not establish motive or original authorship.

Do not rewrite dates, remove required attribution or reassign another author's history. Configure a verified email/noreply address for future personal commits. Changes in the audit-remediation branch were prepared with AI assistance and should be reviewed and understood by the maintainer. Cite actual subsequent commits when explaining personal contributions; imported features are not automatically personal additions.

Interview template: “I started from [verified source and version], retained its required attribution, then personally changed [commit-backed change], [change] and [change]. Here are the tests and remaining limitations.” Do not fill placeholders with unsupported claims.

## Maintainer confirmation, 17 October 2026

The maintainer selected “Someone else’s repository” when asked about origin, then confirmed they do not have its original URL. This establishes a declared external starting point, not the identity of the original author or a license grant. The old clone section is recoverable with `git show a6fdbeb:README.md`; it is a historical source clue, not independently established attribution. No original project LICENSE was found in the audited reachable source trees.

Source/license clearance remains blocked. Do not claim sole original authorship, attach a blanket MIT license, or remove applicable upstream notices. If the original source or permission is recovered, retain its actual attribution even when its name differs from the current maintainer's branding.

A truthful explanation now is: “I started from an existing repository whose original URL I no longer have. This branch contains AI-assisted repairs to authorization, data validation, analytics and the UI. The public evaluation and tests are reproducible; source-license verification is still pending.” Describe only changes you have personally reviewed and can defend.

## Public matching source located during follow-up

A public matching repository was found: https://github.com/kg3478/Cloudspend_Intelligence . Its checked root tree is `7c452c3d547645eabf048f1f7c793d0ca2ab7c20`. Comparing Git blob IDs against the audited local commit `a6fdbeb32e287d05761ad76a8d9538656beb3721` found 67 common paths and **27 byte-identical files**, including `backend/app/agents.py`, `anomaly.py`, `forecasting.py`, `ingestion.py`, `models.py` and `schemas.py`.

The file-level evidence is retained in [shared-source-evidence.json](evaluation/shared-source-evidence.json). This establishes shared source, not original ownership, the exact imported revision, copying direction or reuse permission. The maintainer's confirmation of an external starting point is separate evidence. The earlier clone URL returned 404; a different current repository under the same account is not proof of a GitHub rename.

The matching public tree has no LICENSE/NOTICE/COPYING file and GitHub reports no detected license. Its README line 10 displays an MIT badge and line 264 asserts MIT with a link to the absent LICENSE file. That assertion is retained as evidence, but the referenced full license/copyright notice was not found. Do not infer a complete verified license grant or copyright holder from the absence of a detected license alone. Obtain the applicable terms or permission before assigning a project-wide license.

This source reference is provenance/third-party credit, not current application ownership metadata. It must not be replaced with Omkar's username as if he authored the imported source. Current maintenance and the remediated application branding remain Omkar / omkark2404.
