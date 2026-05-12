# Resource manifest tiering for paper-like idea revisions

Use this reference when a user asks to revise a research idea's download list, resource checklist, or manifest after reading the surrounding idea / protocol / paper files.

## Trigger

- The user asks to mark which resources are required for the main paper vs appendix / optional work.
- A download list mixes models, datasets, benchmarks, baselines, implementation dependencies, and related-work sources.
- The surrounding manuscript has been split into active root docs plus `backup/`, `audits/`, and `archive/` folders.

## Workflow

1. Read the active idea root Markdown files first.
   - Include root-level active docs such as `paper_main.md`, `experiment_protocol.md`, `implementation_spec.md`, `reviewer_risk_register.md`, `related_work_notes.md`, and appendix method docs.
   - Exclude `backup/`, `audits/`, and `archive/` from the source-of-truth pass unless the user explicitly asks for historical recovery.

2. Extract resource mentions by role, not by raw frequency.
   - Main paper models / calibration domains / downstream tasks / main baselines.
   - Phase-0 sanity resources.
   - Implementation dependencies.
   - Appendix checks, legacy controls, reasoning appendix assets, systems appendix assets, and optional appendix extensions.
   - Related-work sources that support positioning but are not directly downloaded experiment assets.

3. Edit the manifest rather than creating a separate parallel list.
   - Add a `层级` / tier column to each table.
   - Keep the manifest compact and readable.
   - Prefer labels such as:
     - `正文必需`
     - `Phase 0 必需`
     - `正文实现必需`
     - `正文参考定位`
     - `附录必需`
     - `legacy 附录必需`
     - `reasoning 附录必需`
     - `附录可选`
     - `参考定位`
   - If a row has two roles, mark both, e.g. `正文必需 / Phase 0 必需` or `正文参考定位 / 附录必需`.

4. Preserve manuscript intent.
   - Do not promote appendix or optional resources to main-paper requirements unless the active docs require them.
   - Do not demote main benchmark resources because they are expensive or gated; mark the tier and leave access constraints for execution notes.
   - For related-work-only papers / repos, use `正文参考定位` or `参考定位` rather than `正文必需` unless the main experiment actually depends on them.

5. Verify mechanically after editing.
   - Reread the manifest.
   - Check every table has the tier column and consistent pipe counts.
   - Check required main resources from the active docs appear with a main tier marker.
   - Check appendix / legacy / optional resources appear with the appropriate appendix tier marker.
   - Scan for the user's forbidden wording constraints when they apply.
   - Run `git diff --check` on the manifest.

6. Leave a durable audit when the revision affects planning or reproducibility.
   - Record source docs reviewed, tier counts, checks performed, manifest hash, and backup path.
   - In CodexScientist mode, store the audit under `idea/audits/` and use `cs_artifact_record` for a milestone when appropriate.

## Pitfalls

- Do not use historical backups as the source of truth for current resource tiers.
- Do not treat a related-work citation as a downloadable experiment dependency.
- Do not leave mixed old headers such as `用途 / 名称 / 链接` if the table now needs tier semantics.
- Do not add a second manifest that can drift from the canonical download list.
