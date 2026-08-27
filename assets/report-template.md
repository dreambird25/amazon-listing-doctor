# Listing 诊断报告

## 结论

- 当前 Listing：`BLOCK / REVIEW / NO_KNOWN_OFFICIAL_ISSUES / NOT_EVALUATED / UNKNOWN`
- 候选预检：`BLOCK / REVIEW / PASS / NOT_EVALUATED / UNKNOWN`
- 发布决策：`BLOCK / REVIEW / PASS / NOT_EVALUATED / UNKNOWN`
- 官方验证完整度：`COMPLETE / INCOMPLETE`
- 官方预检：已完成 / 未完成 / 执行异常
- 最重要行动：最多三项，先官方 ERROR，再 WARNING，最后优化建议

## 诊断对象

- 店铺 / Marketplace / Seller SKU：
- ASIN / Product Type / Requirements / Parentage / Locale：
- Candidate operation / Payload SHA-256 / Touched attributes：
- Preview request ID / submission ID / 请求与响应时间：
- 数据截止时间：
- 数据来源：

## 数据覆盖

列出标题、亮点、五点、描述、后台词、图片、Listings issues、PTD 和 validation preview 的可用性。缺失项说明会影响哪个判断。

## 官方发现

分别列出当前 Listing 与候选 Preview 的 `OFFICIAL_ERROR`、`OFFICIAL_WARNING`：code、原始 severity、属性、Amazon 原始消息、Schema checksum/版本或 submissionId、修复完成条件和复核方式。

## 内部优化建议

逐项列出 `HEURISTIC_ADVICE`，明确“不参与发布门禁”，并引用 Listing 原文或图片元数据。不得承诺排名、流量或推荐结果。

## 未评估与系统异常

列出 `NOT_EVALUATED` 与 `SYSTEM_ERROR`，说明补齐数据或恢复检查所需动作。系统异常不能写成通过。

## 行动与复核

| 优先级 | 行动 | 证据 | 完成条件 | 复核方式 | 改判条件 |
|---|---|---|---|---|---|
