# 版本更迭记录

本项目采用语义化版本。版本记录描述公共契约和行为变化，不登记任何接入方私有实现或数据。

## [未发布]

### 仓库归属

- 仓库从 GitHub Fork 网络中独立，保留完整 Git 历史以及 README 中的上游项目链接。
- 保留原 MIT 版权声明，增加 `dreambird25` 及贡献者对修改与新增代码的版权声明，并新增 `NOTICE.md` 说明来源与归属。

## [1.6.0] - 2026-08-30

### 图片证据边界

- Evidence Policy 升级到 1.2；`image_information_coverage` 只有绑定实际查看画面后记录的 `images[N].visual_observation` 才能评分。
- 图片 URL、主图标记、宽高、背景和水印等定位或技术元数据不再冒充图片内容证据；缺少画面观察时必须返回 `NOT_EVALUATED + EVIDENCE_GAP`。

### 私有批量观察与 UTF-8 输出

- 新增 `quality-observation` 模式：接收私有 `input + assessment`，无须人工期望标签即可聚合质量结论、评分覆盖、维度评级、弱项、候选值可用性和合并失败；输出不含产品正文、原始标识、评估自由文本或原始合并错误。
- `diagnose_listing.py`、`merge_report.py`、`render_report.py` 与 `evaluate_batch.py` 新增显式 `--output`，由 Python 直接写 UTF-8 文件，避免 Windows Shell 重定向损坏中文。

### 实践与验证

- 使用 100 条北美与欧洲私有只读 Listing 完成无标签质量观察；确定性报告与语义合并全部完成，实践暴露出的 URL-only 图片证据缺口已成为合成回归规则。
- 无标签观察只证明行为与安全降级，不作为人工 Golden 标签；原始记录、身份、单条结果和产品正文均未进入公共仓库。
- 行为测试增加到 129 个，覆盖图片画面证据边界、无标签质量聚合、隐私安全失败输出及四个核心 CLI 的显式 UTF-8 文件写入。

## [1.5.5] - 2026-08-28

### 用户报告信息密度

- 默认简洁报告新增“原始值 / 候选值”对照表；原始值只来自语义评估已绑定的 Listing 证据。
- 精确候选值继续要求通过 Fact Binding 与确定性模板校验；没有可靠候选时明确显示“暂未生成候选值”，不使用自由生成内容填充。
- 详细 Markdown 将七维质量明细和优化建议改为高密度表格，集中展示评级、原始证据、候选值、行动和完成标准。

### 验证

- 新增原始值与候选值派生、无候选降级提示、简洁对照表和详细表格回归测试。

## [1.5.4] - 2026-08-28

### 内容证据来源分层

- 输入与质量上下文新增 `content_evidence`，绑定来源类型、内容范围、覆盖度和缺失字段语义；明确区分 Listings Items 卖家贡献、Catalog 上下文、买家前台、文件/粘贴内容和候选 Payload。
- Listings Items 属性不再可被默认表述为买家前台内容。简洁报告增加中文证据范围与覆盖度，卖家贡献会明确标注“不等同买家前台”。
- 七维完整评分同时要求七维均已评估且内容来源覆盖完整；部分或未知来源最多生成部分评分，避免不同范围的分数直接比较。

### 缺失结论证据约束

- 语义评估升级为 `assessment_version=1.4` 与 Evidence Policy 1.1，每个维度必须声明 `OBSERVED_CONTENT`、`OBSERVED_ABSENCE` 或 `EVIDENCE_GAP`。
- “缺少要点/描述”等缺失结论只有在来源覆盖完整且明确表示未观察到字段时才能成立；API 投影不全、页面未完整加载或来源范围未知时必须降级为未评估/证据不足。
- 比较 Cohort 新增内容来源、范围、覆盖度和缺失字段语义，防止把卖家贡献评分与买家前台评分混为同一口径。

### 验证

- 行为测试增加到 125 个，新增缺失结论来源证明、部分来源拒绝、Listings Items 冒充前台的拒绝、证据范围渲染和两类历史误判的合成回归覆盖。
- 使用 5 条仓库外的开发环境只读样本完成私有实践：4 条卖家贡献范围、1 条买家前台范围，5/5 语义结果成功合并；两类历史误判均按真实证据范围得到纠正。仓库不保存样本标识或原始内容。

## [1.5.3] - 2026-08-28

### 语义证据防幻觉

- `clarity_and_readability` 声称存在替换字符、乱码、编码痕迹、调试堆栈或日志残留时，合并器要求绑定文本实际包含可疑字符或技术序列；正常文本不能再支撑此类弱项。
- 明确区分字符/字节限制与内容可读性。候选长度预检通过只证明对应候选字段满足该次长度验证，不推翻或替代其他字段的内容质量判断。

### 多语言评估

- 模型能够理解目标语言时必须完成基础本地化评估；缺少独立母语人工终审只记录为限制，不再被当作 Listing 证据缺失。
- `localization_quality=NOT_EVALUATED` 仍可用于模型确实不支持该语言或缺少目标站点可见文本的情况。

### 验证

- 行为测试增加到 119 个，新增无证据编码/控制字符/技术残留声明拒绝、否定句与转折/双重否定边界、合法多语言字符不误判、真实乱码与替换字符接受、母语审校缺失理由拒绝，以及候选预检通过后复核当前问题的测试。

## [1.5.2] - 2026-08-28

### 隔离式语义质检

- 语义质检默认在新鲜、短上下文的子代理中执行；运行环境不支持子代理时，要求使用独立进程或隔离上下文阶段。
- 父环境负责鉴权、只读采集、规范化和完整性记录；语义工作器只接收仓库外的单个规范化文件与公共 Skill 资源，不接触凭据、私有拓扑或原始响应归档。

### 本机开发数据适配

- 明确支持集成项目通过本机回环 dev API 补齐 Listings Items 与 Catalog Items 证据。
- dev 适配器必须绑定开发 Profile 和开发数据库，复用真实开发鉴权，仅允许无副作用读取；生产访问默认禁用且不由本 Skill 隐式授权。

## [1.5.1] - 2026-08-28

### 私有数据交接

- 明确由受控父环境先通过无副作用的 Listings Items/Catalog Items GET 适配器补齐证据，再把仓库外的私有规范化文件交给子代理；子代理不接触凭据，也不调用同步、落库、Preview 或提交入口。
- 私有实践区分审计文件与用户报告：Seller Listing 身份、稳定 code、原始 Amazon 消息和证据哈希只保留在私有审计文件。

### 中文用户报告

- 默认中文简洁 Markdown 不再追加 `FULL`、`NEEDS_IMPROVEMENT`、`NOT_EVALUATED`、`COMPLETE` 等英文状态，也不展示稳定错误码或 Amazon 原始外语消息。
- 内部稳定 code 与原始消息继续保留在 `--view detailed` 审计视图，不改变机器契约、官方门禁或确定性判断。
- 行为测试增加到 109 个，新增中文简洁视图不泄露机器状态 code 的覆盖。

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
