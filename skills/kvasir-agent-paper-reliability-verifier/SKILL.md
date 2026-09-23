---
name: ka-paper-reliability
description: Verify paper identity, publication acceptance and source reliability using official evidence, then record a traceable paper evidence card.
---

# Paper reliability

1. Establish title, authors, identifier and version. Prefer the publisher, proceedings, official venue or paper repository over search snippets.
2. Verify acceptance separately from citation counts, venue rank and preprint availability. Label missing or conflicting evidence explicitly.
3. Use the relevant venue guide only when needed: [OpenReview](subskills/openreview-accepted-venue/GUIDE.md), [ACL Anthology](subskills/acl-anthology-accepted-venue/GUIDE.md), or [DBLP](subskills/dblp-accepted-venue/GUIDE.md). Supporting scripts live beside these guides.
4. Record the official URLs, checked date, claims supported and unresolved fields. Treat citation counts as dated observations, not proof of quality.
5. Use `ka_paper_reliability_verify` with bounded inputs and timeout controls from its advertised schema. A dry run validates the planned operation only. Fetch needed paper artifacts with `ka_paper_fetch` and record actual reading with `ka_record_literature_reading_note`.
6. Return a concise reliability assessment with sources and uncertainty. This process does not establish that the paper's scientific conclusions are true.

[Detailed evidence conventions](references/legacy-playbook.md) are reference material; current MCP schemas define the APIs.
