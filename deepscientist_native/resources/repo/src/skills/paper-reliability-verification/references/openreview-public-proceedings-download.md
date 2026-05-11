# OpenReview public proceedings discovery and PDF download notes

Use this reference when a task asks for all queryable/downloadable papers from an OpenReview-hosted conference matching a topic, especially ICLR/ICML/COLM/TMLR-style venues.

## Practical workflow

1. Inspect the venue domain/group before assuming submissions are public:
   ```python
   import openreview
   c = openreview.api.OpenReviewClient(baseurl='https://api2.openreview.net')
   g = c.get_group('ICLR.cc/2026/Conference')
   print(g.content.get('public_submissions'))
   print(g.content.get('submission_venue_id'))
   print(g.content.get('decision_heading_map'))
   ```
2. For public API2 venues with accepted papers, query accepted public notes with:
   ```python
   notes = c.get_all_notes(content={'venueid': 'ICLR.cc/2026/Conference'}, details=None)
   ```
   Then filter title/abstract/keywords/TLDR locally. Do not rely on only title search when the topic can appear in keywords or abstract.
3. For venues that are configured but not publicly exposed, probe several public-note routes and record zero counts rather than fabricating absence:
   ```python
   c.get_notes(invitation='ICML.cc/2026/Conference/-/Submission', limit=1)
   c.get_notes(content={'venueid': 'ICML.cc/2026/Conference/Submission'}, limit=1)
   c.get_notes(content={'venue': 'ICML 2026 spotlight'}, invitation='ICML.cc/2026/Conference/-/Submission', limit=1)
   c.get_notes(content={'venue': 'ICML 2026 regular'}, invitation='ICML.cc/2026/Conference/-/Submission', limit=1)
   ```
   Also check the conference virtual papers page; if it has no paper links and OpenReview public queries return zero, say that no public downloadable entries were available at the time checked.
4. If the user asks for “all queryable” papers across a conference/year/topic, supplement official OpenReview/virtual-page discovery with arXiv title/abstract/comment searches such as `all:"ICLR 2026" AND all:"peer review"`, `all:"ICLR 2026" AND all:"reviewer"`, `all:"ICLR 2026" AND all:"novelty assessment"`, and equivalent ICML queries. arXiv may surface directly relevant conference-related reports that are not exact-title matches in accepted OpenReview notes.
   - Before labeling an arXiv-only hit as an accepted conference paper, exact-title check the public OpenReview accepted notes for that venue. If absent or the arXiv metadata lacks an acceptance comment, download only when topically relevant and label it conservatively as `VENUE YEAR-related (arXiv report; not confirmed as accepted paper in public OpenReview accepted notes)`.
   - Record this distinction in the manifest so later users can separate confirmed accepted papers from conference-related reports.
5. Download PDFs from `note.content['pdf']['value']` when present. Prefer `https://openreview.net` + the stored `/pdf/<hash>.pdf` value, and fall back to `https://openreview.net/pdf?id=<note_id>` if the direct route is not a valid PDF. For arXiv-only hits, download `https://arxiv.org/pdf/<versioned_id>` first, then fall back to extensionless/unversioned arXiv PDF URLs.
6. Name files with the paper title, sanitizing only path-breaking characters (`/`, `\\`, NUL). Preserve punctuation such as colons if the filesystem allows it.
7. Create a manifest with source URL, OpenReview forum or arXiv abs URL, venue/source label, inclusion rationale, file path, size, and SHA256.
8. Before finalizing, run `ls -lh <download_dir>` and parse the manifest back to verify every downloaded entry exists, starts with `%PDF-`, and matches recorded size/SHA256. Treat the manifest as the single source of truth: if exploratory scripts accidentally download extra PDFs, move unmanifested files to a timestamped quarantine directory outside the target root before final verification, rather than leaving them beside the approved set.
9. If the user asks for exhaustive searching until no more results are found, implement an explicit no-new-results stopping rule (for example, “stop after 5 consecutive rounds with no new qualifying entries”). Log each round's search surface and outcome in the manifest or notes, and only stop after the required consecutive negative rounds have completed.

## Filtering cautions

- Exclude false positives where `review` means systematic review, product review, code review, previous-frame review, reviewer-style LLM judge for a non-paper task, RL peer mechanisms unrelated to academic paper peer review, reviewer nomination/policy analysis without an agent/LLM review component, or generic “source code available for review” text.
- Include direct peer-review agent/LLM topics: automated peer review, paper quality estimation, LLM-written review detection, peer-review archives/dynamics, reviewer-flagged paper inconsistency benchmarks, scholarly novelty assessment for peer review, and academic rebuttal agents when the workflow explicitly models reviewer state or peer-review rebuttal.
- For broad tasks spanning multiple venues, record both positive downloads and negative/closed-source venue checks in the manifest so the user can audit coverage.
- When using a classifier/filter script, never include agent-written fields such as `rationale`, `search_query`, or source labels in the text being matched. Those fields often contain terms like `peer review`, `LLM`, and `agent` and can cause every venue paper to be misclassified as relevant. Match only paper-provided metadata (title, abstract, keywords, venue/comment metadata).
- OpenReview `/notes/search` and Semantic Scholar can rate-limit quickly (`429`) during broad discovery. Prefer venue-local OpenReview note downloads plus local filtering first, and use arXiv API searches as the robust fallback for public conference-related reports.

## Verification snippet

Run `ls -lh <download_dir>` first, then run a manifest-backed verification script. This version also catches accidental extra PDFs in the target root that are not represented in the manifest.

```python
from pathlib import Path
import json, re, hashlib
root = Path('/path/to/download_dir')
manifest = root / 'manifest.md'
text = manifest.read_text(encoding='utf-8')
m = re.search(r'```json\n(.*?)\n```', text, re.S)
entries = json.loads(m.group(1))
expected = {Path(e['path']).resolve() for e in entries if e.get('downloaded', True)}
for e in entries:
    if not e.get('downloaded', True):
        continue
    p = Path(e['path'])
    assert p.exists(), p
    data = p.read_bytes()
    assert data[:5] == b'%PDF-', p
    assert len(data) == e['size'], p
    assert hashlib.sha256(data).hexdigest() == e['sha256'], p
extras = {p.resolve() for p in root.glob('*.pdf')} - expected
assert not extras, sorted(map(str, extras))
```
