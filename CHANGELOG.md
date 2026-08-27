# 版本更迭记录

本项目采用语义化版本。版本记录描述公共契约和行为变化，不登记任何接入方私有实现或数据。

## [1.0.1] - 2026-08-27

### 修复

- 仅将 `VALIDATION_PREVIEW` 的 `VALID` 视为预检通过；`ACCEPTED` 现在返回 `SYSTEM_ERROR / PREVIEW_MODE_MISMATCH`。
- Amazon issue 的 `severity=INFO` 映射为 `OFFICIAL_WARNING`，并在 evidence 中保留原始 severity。
- 拆分 `current_listing_gate`、`candidate_preview_gate` 与 `release_decision`，避免当前历史问题和候选预检相互覆盖。
- 使用 mode、PUT/PATCH、Listing 身份范围及候选/Preview `payload_sha256` 绑定预检证据；缺失追踪字段或 hash 不一致时不得通过。
- 门禁优先保留已知 `OFFICIAL_ERROR`；其他官方证据异常通过 `official_validation_completeness=INCOMPLETE` 单独表达。
- PATCH 候选必须声明 `touched_attributes`，局部预检不得被解释为完整 Listing 通过。
- 图片已提供但未标识主图时输出 `NOT_EVALUATED / MAIN_IMAGE_NOT_IDENTIFIED`。

### 兼容性

- 保留旧 `gate` 字段：当 `release_decision=PASS` 时仍输出 `PASS_OFFICIAL_CHECKS`，其他值与 `release_decision` 一致。
- 完成预检的输入契约新增候选范围、Payload hash、身份回显、request/submission ID、HTTP 状态和请求/响应时间；旧的最简 Preview 对象会安全降级为 `UNKNOWN`，不会误通过。

### 验证

- 行为测试由 9 个增加到 19 个，覆盖上述 P0 证据组合与门禁场景。

## [1.0.0] - 2026-08-27

### 变更

- 将上游 CDQ/A9/COSMO/Alexa 聚合评分改造为五态证据模型。
- 以 Listings Items issues、PTD 约束和 `VALIDATION_PREVIEW` 作为官方证据来源。
- 移除第三方抓取、静态类目评分和自动写入能力，建立只读公共参考实现。
