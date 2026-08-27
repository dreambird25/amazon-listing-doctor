# 版本更迭记录

本项目采用语义化版本。版本记录描述公共契约和行为变化，不登记任何接入方私有实现或数据。

## [1.3.0] - 2026-08-27

### 生产适配

- 拆分 `current_content` 与 `candidate.content`，新增 `candidate_local_validation_gate`，避免候选 PTD 结果污染当前 Listing 门禁。
- 支持 `attributes` 完整数组、`language_tag`、`marketplace_id` 和适配器声明的 `attribute_aliases`；不再只取数组首项或依赖固定字段名。
- 新增外部完整 PTD Validator 证据契约。只有绑定 Draft 2019-09/Amazon vocabulary 能力、Schema/Meta-Schema checksum、候选 Payload hash、校验器版本和时间的对象才能设置 `FULL_JSON_SCHEMA`；裸布尔值无效。
- 七维语义质量契约升级为 `assessment_version=1.1`，强制记录 `assessment_model`、`prompt_version` 和带时区的 `assessed_at`。

### 报告与实践

- 新增独立 `report_locale`、`zh-CN`/`en` 资源包和 Markdown/JSON 渲染器；稳定 code 与 Amazon 原始消息保持不变，中文 `PASS` 不描述为发布成功。
- 新增私有 Golden Dataset 批量工具，只输出聚合分布、确定性和哈希化样本引用。
- 由独立 Luna 子代理使用固定随机种子完成 30 条私有 Listing 只读实践，并在最终 v1.3 工作树按相同样本重放；v1.3 重复运行稳定、无系统异常，聚合门禁与 v1.2 基线一致。实践还验证缺失证据安全降级，并发现不同 issue 视图可能不同步。未提交任何原始 Listing 数据或标识。

### 验证

- 行为测试增加到 65 个，覆盖真实属性别名/数组、多语言范围、当前/候选隔离、完整 Schema 证据绑定、中文渲染和私有批量输出边界。

## [1.2.0] - 2026-08-27

### 生产门禁

- 未绑定当前候选的 Preview ERROR/WARNING 保留为证据，但标记 `applies_to_candidate=false`，不再用旧 Payload、其他 SKU 或错误 operation 阻断当前候选。
- PATCH 即使 Preview 为 `VALID`，缺少可追溯当前 Listings Items 快照时也只能 `REVIEW`，不得自动放行。
- 新增 `listing_snapshot` 契约，绑定 seller、marketplace、SKU、request ID、`included_data`、issues 和获取/过期时间；旧 `listing_issues` 安全降级为不完整证据。
- 快照或 PTD 错绑/过期时，其官方 findings 保留但标记 `applies_to_current=false`，不再误拦当前 Listing scope。
- PTD 强制绑定 seller、marketplace、Product Type/version、requirements、requirements enforcement、parentage、locale、Schema/Meta-Schema checksum、版本标志和时间。
- 内置 PTD 子集检查不再允许 `release_decision=PASS`；绑定 Preview 可通过候选门禁，但发布仍要求外部完整 PTD JSON Schema 校验。
- Preview 增加请求指纹、有效期和时间顺序校验；PUT 要求回显 request requirements，PATCH 按 Amazon 官方模型不伪造该请求字段。
- 严格校验图片布尔元数据、主图唯一性和 PATCH `touched_attributes` 字符串类型。
- CLI 增加退出码 `3` 表示“已知官方 ERROR + 系统异常”，避免只看退出码的集成隐藏 blocker。

### 实践与研究

- 使用真实只读 Listing 接口完成端到端回放，验证已知官方 ERROR 与不完整结构化视图并存时必须输出 `BLOCK + INCOMPLETE`。
- 新增不可逆脱敏的 `listing-practice-sanitized.json`；未提交测试 ASIN、真实文案、店铺、SKU、Issue code、图片或接口响应。
- 新增 Amazon 官方文档/OpenAPI/JSON Schema 一手资料研究和生产接入指南，明确 Preview 低吞吐、完整 PTD 校验和提交后对账边界。

### 验证

- 行为测试增加到 48 个，并将 GitHub Actions 扩展为 Python 3.10、3.11、3.12、3.13 矩阵。

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
