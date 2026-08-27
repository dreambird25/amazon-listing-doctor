# 版本更迭记录

本项目采用语义化版本。版本记录描述公共契约和行为变化，不登记任何接入方私有实现或数据。

## [1.1.0] - 2026-08-27

### 新增

- 将唯一 Skill 本体迁入 `.agents/skills/amazon-listing-doctor/`，克隆仓库后可按 Codex repo-scoped Skill 规则自动发现。
- 新增七维内容质量契约，统一使用 `STRONG / ADEQUATE / WEAK / NOT_EVALUATED` 并要求直接证据。
- 新增 `merge_report.py`，确定性验证语义评估并派生 `quality_verdict`、证据完整度和固定的 `performance_verdict=NOT_EVALUATED`。
- 新增 `ptd_validation_coverage`，明确本地 PTD 引擎只是 `LIGHTWEIGHT_SUBSET`，不冒充完整 Schema 校验。
- 新增完整通过、官方阻断、证据不足和语义评估示例，测试直接校验示例的预期门禁。
- README 增加 Skill 安装、调用、输入来源、仅有 ASIN 时的边界，以及 Skill/CLI 两类入口。

### 兼容性

- 根目录 `scripts/diagnose_listing.py` 保留为兼容 CLI，核心实现的唯一来源迁入 Skill 目录。
- `scripts/compliance_report.py` 继续转发兼容 CLI。
- 当前版本仍不包含 Plugin manifest、MCP Server 或实时 SP-API 认证。

### 验证

- 行为测试由 19 个增加到 27 个，覆盖标准示例、七维质量 Schema、证据要求、报告契约和 verdict 派生。

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
