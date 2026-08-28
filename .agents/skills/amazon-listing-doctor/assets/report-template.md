# Listing 诊断报告

## 默认简洁结论

- Marketplace / Seller SKU / ASIN：分别展示；ASIN 缺失时为 `-`
### 内容质量

- 已评估维度平均分：`N.N / 10` 或“未评分”，并注明“内部启发式评分，非 Amazon 官方评分”
- 评分覆盖：`FULL / PARTIAL / NOT_SCORED`；`FULL` 仅表示七维结构完整
- 比较条件：只有两份报告均为 `FULL` 且 `comparison_cohort_sha256` 相同时才可比
- 已评估维度：`N / 7`
- 弱项维度：列出所有 `WEAK`，不得被高平均分隐藏
- 内容质量结论：展示标签 + 稳定 verdict
- 内容质量原因：一个有直接 Listing 证据的理由
- 内容优化行动：一个可检查完成条件的行动
- 建议改为：仅在目标维度已评估，且输出可由已绑定原始标量值与标点/空格确定性生成时展示

### Amazon 官方证据状态

- 当前 Listing：展示标签 + 稳定 gate
- 发布决策：展示标签 + 稳定 gate
- 官方证据完整性：展示标签 + `COMPLETE / INCOMPLETE`
- 官方状态原因与行动：只描述 Amazon 官方问题或证据缺口
- `INCOMPLETE` 必须注明“Amazon 当前状态尚未确认”，不得写成 Listing 内容不完整

默认简洁结论不能隐藏官方 `BLOCK`、`UNKNOWN` 或 `INCOMPLETE`，也不能让普通官方证据缺口遮蔽内容质量原因。适用的 `OFFICIAL_ERROR` 必须在官方证据区明确展示并继续阻断操作。需要审计证据时，详细视图必须包含简洁结论、官方 findings、七维明细、建议、局限和评估追溯。

## 结论

- 当前 Listing：`BLOCK / REVIEW / NO_KNOWN_OFFICIAL_ISSUES / NOT_EVALUATED / UNKNOWN`
- 候选预检：`BLOCK / REVIEW / PASS / NOT_EVALUATED / UNKNOWN`
- 候选本地校验：`BLOCK / REVIEW / PASS / NOT_EVALUATED / UNKNOWN`
- 发布决策：`BLOCK / REVIEW / PASS / NOT_EVALUATED / UNKNOWN`
- 官方证据完整性：`COMPLETE / INCOMPLETE`
- 当前快照 / 候选 Preview / 本地 PTD 覆盖：分别列出 `official_evidence_coverage`
- 内容质量：`STRONG / ADEQUATE / NEEDS_IMPROVEMENT / PARTIALLY_EVALUATED / NOT_EVALUATED`
- 内容证据完整度：`COMPLETE / PARTIAL / NONE`
- 业务表现：`NOT_EVALUATED`
- 官方预检：已完成 / 未完成 / 执行异常
- 最重要行动：最多三项，先官方 ERROR，再 WARNING，最后优化建议

## 诊断对象

- 店铺 / Marketplace / Seller SKU：
- ASIN / Product Type / Requirements / Parentage / Locale：
- Candidate operation / Payload SHA-256 / Request fingerprint / Touched attributes：
- Preview request ID / submission ID / 请求与响应时间：
- Listing snapshot request ID / includedData / 获取与过期时间：
- PTD scope / version flags / Schema + Meta-Schema checksum / 获取与过期时间：
- 数据截止时间：
- 数据来源：
- 内容校验目标：`CURRENT / CANDIDATE`
- 报告展示语言：

## 数据覆盖

列出标题、亮点、五点、描述、后台词、图片、Listings issues、PTD 和 validation preview 的可用性。缺失项说明会影响哪个判断。

## 官方发现

分别列出当前 Listing 与候选 Preview 的 `OFFICIAL_ERROR`、`OFFICIAL_WARNING`：code、原始 severity、属性、Amazon 原始消息、Schema checksum/版本或 submissionId、修复完成条件和复核方式。

## 内部优化建议

按七个质量维度列出 rating、Evidence Policy rule code、理由和 Listing 原文或图片元数据证据。精确改写还要列出每个事实绑定的原始值、字段路径和值哈希。逐项列出 `HEURISTIC_ADVICE`，明确“不参与发布门禁”。不得承诺排名、流量或推荐结果。

## 未评估与系统异常

列出 `NOT_EVALUATED` 与 `SYSTEM_ERROR`，说明补齐数据或恢复检查所需动作。系统异常不能写成通过。

## 行动与复核

| 优先级 | 行动 | 证据 | 完成条件 | 复核方式 | 改判条件 |
|---|---|---|---|---|---|

展示层可以翻译标签和标题，但必须同时保留稳定 gate/status/code 与 Amazon 原始消息。“候选预检通过”和“满足当前自动放行证据条件”不得改写为“发布成功”。
