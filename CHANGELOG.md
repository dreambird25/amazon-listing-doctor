# 版本更迭记录

本项目采用语义化版本。版本记录描述公共契约和行为变化，不登记任何接入方私有实现或数据。

## [未发布]

### 仓库归属

- 仓库从 GitHub Fork 网络中独立，保留完整 Git 历史以及 README 中的上游项目链接。
- 保留原 MIT 版权声明，增加 `dreambird25` 及贡献者对修改与新增代码的版权声明，并新增 `NOTICE.md` 说明来源与归属。

## [1.5.0] - 2026-08-28

### 双摘要契约

- `executive_summary` 升级到 `1.2`，新增独立的 `content_quality` 与 `official_evidence` 对象，并保留 `quality_primary_*`、`official_primary_*` 兼容字段。
- 普通官方证据缺失、过期或追踪不足不再覆盖内容质量原因；适用的 `OFFICIAL_ERROR` 仍可作为操作主因并保持官方门禁不变。
- 私有批量质量快照固定读取内容质量 lane，同时单独输出非识别性的官方原因/行动 code，避免 Golden Set 把快照缺口当成文案问题。

### 默认用户输出

- 简洁 Markdown 拆成“内容质量”和“Amazon 官方证据状态”两个区块，分别展示理由、行动和完成条件。
- 中文将 `INCOMPLETE` 展示为“官方证据未完成”，并明确说明它不代表 Listing 内容不完整。
- 行为测试增加到 108 个，覆盖官方快照缺失不遮蔽内容原因、双区块渲染和批量质量 lane 隔离。

## [1.4.1] - 2026-08-27

### 契约加固

- 精确改写 Literal 改为显式分隔符白名单，拒绝控制字符、换行、Tab、Emoji、商标符号、百分号和 CommonMark 横线分隔线；每个唯一 Fact Binding 必须恰好使用一次。
- Recommendation 与维度评级建立确定性约束；`NOT_EVALUATED` 只能请求补证据且不得携带 Evidence，`STRONG` 不得声明缺失证据。
- 官方报告哈希改为顶层与 Finding 规范字段白名单，并绑定 Listing Snapshot、Preview 与官方 Scope 追溯摘要；展示语言和渲染字段不再改变验证语义，Detailed JSON 支持重复渲染后再次重验。
- 私有批量回归的 HMAC key 至少需要 32 个 UTF-8 字节，样本引用与建议文本使用不同版本化 Domain。

### 验证边界

- README 明确 30 条私有 Listing 只验证了官方门禁与安全降级；v1.4 质量策略仍主要由合成行为测试验证，人工 Quality Golden Set 尚在建设。
- 行为测试增加到 105 个，覆盖不安全 Literal、重复 Fact Binding、评级/建议冲突、未评估证据、哈希白名单、HMAC key/domain 与 Detailed JSON 幂等重验。

## [1.4.0] - 2026-08-27

### 质量证据契约

- 语义评估升级为 `assessment_version=1.3`，强制绑定 `assessment_locale`、`evidence_policy_version=1.0` 和不早于官方报告 `data_as_of` 的评估时间。
- 七个质量维度引入独立 Evidence Policy：图片维度必须引用图片路径，跨字段一致性必须引用至少两个内容模块，语言本地化必须匹配 scope locale 和可见文本；其他维度也有对应最低证据路径。
- 合并时要求官方报告包含 `scope`、`release_reasons`、`data_as_of` 和自校验 `official_report_sha256`，避免缺少关键证据时仍生成质量结论。

### 确定性改写与分数比较

- 精确建议改为类型化 `fact_bindings + suggested_template`；输出只能由已绑定原始标量值与标点/空格确定性拼接。自由 `rendered_fact`、未绑定单位和带字母/数字的模板常量均被拒绝。
- 默认简洁行动与完成条件改为由质量维度派生的稳定 code 及本地化文案；模型自由 `action/completion_criterion` 仅在详细审计视图保留，不再将未绑定产品声明带入默认操作指令。
- `FULL` 仅表示七维结构完整；新增 `structurally_comparable`、`comparison_rule` 和 `comparison_cohort_sha256`。两个分数只有同为 `FULL` 且模型、Prompt、契约、评分规则、证据政策、目标、Marketplace、Product Type、requirements、parentage 和 Locale 组成的队列哈希一致时才能比较。

### 输出与私有回归

- Detailed Markdown 显示事实绑定的原始值、字段路径和值哈希；Detailed JSON 不再盲信内嵌 summary，会重验评估并重新派生结论，无效时移除质量载荷并标记 `INVALID_ASSESSMENT`。
- 批量工具区分 `observation`、`golden-official` 和 `golden-quality`；Golden 模式必须提供至少一个预期值。默认样本引用改为无识别性行号，需要跨次稳定引用时由私有环境通过 `LISTING_DOCTOR_SAMPLE_REF_KEY` 生成 HMAC-SHA-256。建议文本指纹也只在同一私有 key 下生成 HMAC，不输出可词典反查的普通哈希。
- 行为测试增加到 98 个，新增维度路径误绑、空文本证据、Locale/时间错绑、队列哈希、未评估事实注入、自由渲染事实、Detailed JSON 篡改与严格 Golden 模式回归。

## [1.3.2] - 2026-08-27

### 结论与官方证据

- `REVIEW` 时依据 `release_reasons` 先选择当前 Listing、候选 Preview 或本地 PTD 证据通道；适用于当前 Listing 的 `OFFICIAL_ERROR` 不再被候选警告或内容建议遮蔽。
- 简洁官方原因只接受 `INPUT / LISTINGS_ITEMS / PTD / VALIDATION_PREVIEW` 来源，排除明确不适用的 finding，并保留真实 `finding_source`。
- 默认身份升级为 `Marketplace + Seller SKU + ASIN`；非全部通过时显示候选 Preview 与本地校验门禁。

### 语义评估绑定

- 评估契约升级为 `assessment_version=1.2`，强制绑定 `CURRENT / CANDIDATE`、scope fingerprint、content hash、official report hash 和 evidence manifest hash。
- 确定性引擎为当前与候选内容生成只含字段路径/值哈希的证据清单；每个评级证据必须匹配清单中的路径与值。
- 精确 `suggested_value` 新增 `fact_bindings`，要求建议中的每个产品事实绑定到已评估、已验证的字段路径和值哈希。

### 评分、详细视图与回归

- 分数明确为“已评估维度平均分”：七维齐全为 `FULL/comparable=true`，五或六维为 `PARTIAL/comparable=false`，少于五维为 `NOT_SCORED`；新增 `dimension_mask` 和 `weak_dimensions`。
- 首要质量行动先按 `HIGH / MEDIUM / LOW` 排序，再用主要原因维度作平局条件。
- 详细 Markdown 视图现在包含默认简洁结论、官方 findings、七维评级/证据、建议、局限和完整评估哈希追溯。
- 私有 Golden Dataset 新增 `--mode quality-summary`，回归 verdict、评分覆盖、弱项维度、首要原因/行动和精确建议权限；输出仍只包含聚合统计与哈希样本引用。
- 行为测试增加到 87 个，新增绑定篡改、证据清单、完整/部分评分、弱项保留、官方来源过滤、行动优先级、详细视图和质量批量回归覆盖。

## [1.3.1] - 2026-08-27

### 默认用户结论

- 新增 `executive_summary`，默认输出 ASIN、当前官方状态、发布决策、官方验证完整度、内容质量分、主要原因、首要行动和可选建议值。
- `render_report.py` 默认使用 `--view concise`；需要完整 findings、稳定 code 和 Amazon 原始信息时使用 `--view detailed`。
- 内容质量分采用透明固定规则：`STRONG=10`、`ADEQUATE=7`、`WEAK=3`，仅对已评估维度取平均并保留一位小数；七维中少于五维可评估时明确返回 `NOT_SCORED`。
- 分数标记为 `INTERNAL_HEURISTIC` 和 `official=false`，不改变任何官方门禁，不代表 Amazon 官方评分，也不预测排名、流量或转化。

### 建议约束

- 精确改写值必须声明目标属性、当前问题，并逐项绑定已评估维度中同字段、同值的直接证据；未评估维度不得生成精确改写。
- 存在适用于当前 Listing/候选的官方错误、证据异常或警告时，默认摘要优先展示该官方问题与行动，内容优化不会遮蔽它。
- 建议值始终属于人工复核建议，仍须通过适用 PTD 与绑定候选 Payload 的 `VALIDATION_PREVIEW`。

### 验证

- 行为测试增加到 77 个，覆盖评分公式与阈值、分数与官方门禁隔离、默认简洁渲染、无效摘要安全降级、官方问题适用性与优先级、详细视图兼容和建议值证据约束。

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
