# Paper Reliability Verifier Skill

给 AI scientist / 文献调研 agent 使用的论文可靠性验证 skill。它把“查到论文”改成“查到论文 + 生成可审计证据卡”。

## 包含内容

- `SKILL.md`：agent 执行规范。
- `scripts/verifier.py`：可直接调用的 Python verifier。
- `schemas/paper_evidence_card.schema.json`：输出 schema。
- `configs/sources.yaml`：数据源策略。
- `data/curated_venue_ranks.sample.csv`：旧版 CCF/CORE venue 本地表样例。
- `data/journal_rank_overrides.sample.csv`：旧版 journal 本地表样例。
- `paper_ranking/conference_ranking.csv`：会议分级精简快照 fallback。
- `paper_ranking/journal_ranking.csv`：期刊分区精简快照 fallback。
- `prompts/reliability_verifier_prompt.md`：LLM verifier prompt。
- `subskills/acl-anthology-accepted-venue/SKILL.md`：ACL Anthology Python package / local metadata 子 skill，用于 NLP/CL 论文录用 venue 查询。
- `subskills/openreview-accepted-venue/SKILL.md`：OpenReview 子 skill，用于 ICLR/TMLR/COLM 等 venue 的录用状态和 oral/spotlight/poster 查询。
- `subskills/dblp-accepted-venue/SKILL.md`：DBLP publication search 子 skill，用于自动识别已录用 venue/journal。
- `refs/references.md`：官方文档链接与 caveats。

## 安装

```bash
pip install -r requirements.txt
export OPENALEX_MAILTO="your_email@institution.edu"
export SEMANTIC_SCHOLAR_API_KEY=""   # optional
```

## 单篇验证

```bash
python scripts/verifier.py --doi "10.1038/nature12373" --out examples/card.json
```

## 批量验证

```bash
python scripts/verifier.py --input examples/input_dois.txt --out examples/cards.jsonl
```

## OpenReview / ACL Anthology / DBLP / Crossref 自动识别录用 venue / journal

如果未显式传入 `--accepted-venue`，脚本可以先按显式 `--openreview-venue-id` 查询 OpenReview（适用于 ICLR/TMLR/COLM 等），然后默认尝试 ACL Anthology（适用于 ACL/EMNLP/NAACL/EACL/AACL/TACL/CL 等 NLP/CL 论文），再尝试 DBLP publication search，最后用 Crossref Works API 作为保守的 DOI/题名元数据 fallback：

```bash
python scripts/verifier.py \
  --title "Learned Incremental Representations for Parsing" \
  --year 2022 \
  --arxiv-url "https://arxiv.org/abs/xxxx.xxxxx"
```

如果只有论文题名和 arXiv 链接、但不能确认是否已被会议/期刊录用，不要把 arXiv 当作已录用来源；传入 `--title`（可加 `--year`）触发 ACL Anthology / DBLP 的题名检索，`--arxiv-url` 只记录到 `paper.source_ids.arxiv_url` 作为来源线索。

OpenReview 已知 venue 示例：

```bash
python scripts/verifier.py \
  --title "Graph Neural Networks for Learning Equivariant Representations of Neural Networks" \
  --year 2024 \
  --openreview-venue-id ICLR.cc/2024/Conference
```

OpenReview 命中后会填充 `accepted_publication.openreview.presentation_type`，例如 `oral` / `spotlight` / `poster`。注意：录用状态和 oral/poster 是两个层级；oral/poster 不是 OpenReview 的统一固定字段，脚本会同时解析最终 `venue` label 和 `Decision` note。

ACL Anthology 命中后会填充输出中的：

```json
"accepted_publication": {
  "status": "acl_anthology_confirmed",
  "venue_name": "Annual Meeting of the Association for Computational Linguistics",
  "venue_type": "conference",
  "acronym": "ACL",
  "evidence_source": "ACL Anthology local metadata: title_year_match"
}
```

随后继续用本地 `paper_ranking/conference_ranking.csv` 或 `journal_ranking.csv` 做 CCF/CORE/中科院分区/JCR 查表。ACL Anthology 的 `volume_title` 会保留 Findings、workshop、short/demo 等 track 信息；ACL Anthology Findings 按其父 ACL-family venue 做 ranking，可在父 venue 为 top-tier 时进入 `strong_evidence`，但 workshop、short/demo、shared-task 等仍保留非主轨警告。若 DBLP 只命中 `CoRR`，则标记为 preprint，不当作会议/期刊录用。若 ACL Anthology/DBLP 低相似或歧义，则保留 warning，不虚构 venue。Crossref fallback 只把 `journal-article` 和 `proceedings-article` 等 publisher DOI 元数据作为 `crossref_confirmed`，`posted-content` / arXiv / bioRxiv / medRxiv 仍标为 preprint，不做正式 venue ranking。

Crossref fallback 会保留 `accepted_publication.crossref`，包括 DOI、title、type、container/event、ISSN/ISBN、publisher、`is-referenced-by-count`、`update-to` 和 `relation`。如需测试 OpenReview/ACL/DBLP 之外的 Crossref DOI 路由，可禁用前置路由：

```bash
python scripts/verifier.py --doi "10.xxxx/yyyy" --no-acl-anthology --no-dblp
```

禁用 ACL Anthology：

```bash
python scripts/verifier.py --title "paper title" --no-acl-anthology
```

禁用 OpenReview：

```bash
python scripts/verifier.py --title "paper title" --no-openreview
```

禁用 DBLP：

```bash
python scripts/verifier.py --title "paper title" --no-dblp
```

禁用 Crossref acceptance fallback：

```bash
python scripts/verifier.py --title "paper title" --no-crossref
```

## 已确认录用 venue / journal 的分区分级验证

生产使用时，会议分级和期刊分区快照固定从这里读取：

```text
/home/xu/project/ds_dev/paper_reliability_verifier_skill/paper_ranking
```

需要包含：

```text
conference_ranking.csv
journal_ranking.csv
```

如果该目录不存在，脚本会 fallback 到本 skill 内的：

```text
paper_ranking/conference_ranking.csv
paper_ranking/journal_ranking.csv
```

也可以临时设置：

```bash
export PAPER_RANKING_DIR=/path/to/paper_ranking
```

当你已经确认论文被某会议录用：

```bash
python scripts/verifier.py \
  --title "paper title" \
  --accepted-venue "AAAI Conference on Artificial Intelligence" \
  --accepted-type conference \
  --accepted-acronym AAAI
```

当你已经确认论文被某期刊录用：

```bash
python scripts/verifier.py \
  --doi "10.xxxx/yyyy" \
  --accepted-venue "ACM Computing Surveys" \
  --accepted-type journal
```

当前版本已实现显式确认、OpenReview、ACL Anthology、DBLP、Crossref 五条录用 venue/journal 路由；若仍无法确认，则输出保留 `accepted_publication` 接口和 warning，后续可以继续接 OpenAlex、出版社页面或会议 accepted-paper list。

## 注意

样例 CCF/CORE/Journal 表不是完整官方榜单。生产使用时应替换为你们维护的、带版本号和日期的本地快照。
