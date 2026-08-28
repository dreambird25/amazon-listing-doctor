# Amazon Listing Doctor

一个可直接被 Codex 发现的 Amazon Listing 诊断 Skill。它把 Amazon 官方证据、内容质量判断、缺失数据和系统异常分开，生成可追溯、可复核的报告。

这是 [`buluslan/amazon-listing-doctor`](https://github.com/buluslan/amazon-listing-doctor) 的公共 Fork，不包含任何特定公司的内部代码、接口、表结构、账号、SKU、ASIN 或运行配置。

当前版本：**v1.5.0**。本版将内容质量结论与 Amazon 官方证据状态拆成两个独立摘要，避免把快照缺失、时效或追踪字段不足误写成 Listing 内容不完整；适用的官方错误仍会明确阻断操作，详见 [`CHANGELOG.md`](CHANGELOG.md)。

## 它回答三个不同问题

| 层级 | 输出 | 能否参与官方发布判断 |
|---|---|---|
| 官方证据 | 当前 Listing、候选预检、发布决策和证据完整度 | 可以，但只限已绑定的官方证据范围 |
| 内容质量 | 七维评级及透明的内部 10 分制评分 | 不参与官方门禁 |
| 业务表现 | `performance_verdict=NOT_EVALUATED` | 需要销量、流量、转化、退货等真实指标后另行评估 |

它不会输出 Amazon 官方 CDQ 分、A9 收录分、COSMO 分或 Rufus 推荐概率，也不会用内容诊断承诺排名、流量或转化。

## 作为 Codex Skill 使用

### 方式一：克隆后直接使用

```bash
git clone https://github.com/dreambird25/amazon-listing-doctor.git
cd amazon-listing-doctor
codex
```

Skill 位于：

```text
.agents/skills/amazon-listing-doctor/
```

Codex 会按官方的 repo-scoped Skill 规则自动发现它。随后可显式调用：

```text
$amazon-listing-doctor 检查 .agents/skills/amazon-listing-doctor/examples/listing-valid.json，分别给出官方结论、内容质量和未评估项
```

也可以在 Codex 中运行 `$skill-installer`，要求它从以下仓库目录安装为个人 Skill：

```text
https://github.com/dreambird25/amazon-listing-doctor/tree/main/.agents/skills/amazon-listing-doctor
```

安装与发现规则见 [OpenAI 官方 Build skills 文档](https://developers.openai.com/codex/skills)。

## 用户可以提供什么

| 输入 | 可得到的结果 |
|---|---|
| 完整规范化 JSON | 官方证据诊断 + 内容质量评估 |
| Excel/CSV/Seller Central 导出 | 先映射字段；有官方 evidence 列时可做官方诊断，否则只做内容质量 |
| 粘贴的标题、五点、描述和图片信息 | 内容质量评估；官方门禁为 `NOT_EVALUATED` |
| 只有 ASIN 或商品链接 | 只能识别诊断对象，不能凭 ASIN 推断卖家贡献、PTD 或预检结果；需要补 Listing 内容或官方导出 |

当前公共版本不直接登录 Seller Central，也不直接调用 SP-API。用户、ERP 或转换器负责提供规范化证据。数据可以来自文件、Excel/CSV、Listings Items、Product Type Definitions、`VALIDATION_PREVIEW`、ERP 或只读数据视图；数据渠道本身不决定证据等级。

## 生产使用结论

v1.5.0 可以安全用于人工诊断、ERP 辅助门禁，以及自动阻止已正确绑定的 Amazon `ERROR`。它会对旧 Payload 的 Preview ERROR、过期证据、范围不一致、PATCH 缺当前快照等情况安全降级，不会伪装成通过。默认报告分别展示内容质量原因/行动和官方证据原因/行动，普通证据缺口不再覆盖内容质量结论。

无人值守自动放行仍需由接入系统补齐：完整 Draft 2019-09 + Amazon vocabulary PTD 校验、Preview 独立限流、授权提交和提交后 issues/status 对账。Amazon 明确说明 Preview 适合少量 Listing，不是高吞吐生产主链路。官方依据见 [`生产就绪研究`](docs/production-readiness-research.md)，接入门禁见 [`production-readiness.md`](.agents/skills/amazon-listing-doctor/references/production-readiness.md)。

官方门禁曾使用固定随机种子的 30 条私有只读 Listing 验证，覆盖多个北美/欧洲站点和 Product Type；重复运行结果一致且没有引擎系统异常。该实践没有校准 v1.4 的质量 Evidence Policy、图片质量评级、比较 Cohort 或精确改写，当前这些质量能力主要由合成行为测试验证，真实人工 Quality Golden Set 仍在建设。公开仓库不保存任何私有记录、标识、单条引用或原始响应。

示例输入位于 [`examples`](.agents/skills/amazon-listing-doctor/examples/README.md)。

## 开发者与 ERP 入口

根目录保留稳定 CLI：

```bash
python scripts/diagnose_listing.py --file .agents/skills/amazon-listing-doctor/examples/listing-valid.json
```

核心脚本位于 Skill 内部，根 CLI 只是兼容入口。脚本只使用 Python 标准库，不联网、不写数据。

运行确定性 CLI 不需要 OpenAI API Key。通过 Codex 使用七维语义质量评估时，使用用户当前 Agent 环境；公共仓库不保存模型密钥。若其他系统自行调用模型，凭据和模型网关属于接入方私有配置。

本地 PTD 引擎只执行当前支持的长度/数量约束，并通过 `ptd_validation_coverage` 明示 `LIGHTWEIGHT_SUBSET`；它不冒充完整 PTD Schema 校验。接入方可提供与 Schema checksum、Meta-Schema checksum、候选 Payload hash、校验器版本和时间绑定的外部完整校验证据，使模式升级为 `FULL_JSON_SCHEMA`。裸 `true` 不会被信任。

无人值守证据还要求 PTD 使用 `requirementsEnforced=ENFORCED`；`NOT_ENFORCED` 即使外部 Schema 校验为 valid，也只能进入人工复核。

中文报告与私有批量回归：

```bash
python scripts/render_report.py --report official-report.json --lang zh-CN --format markdown
python scripts/render_report.py --report merged-report.json --lang zh-CN --format markdown --view detailed
python scripts/evaluate_batch.py --file private-observation.jsonl --mode observation
python scripts/evaluate_batch.py --file private-golden-dataset.jsonl --mode golden-official
python scripts/evaluate_batch.py --file private-quality-golden.jsonl --mode golden-quality
```

第一条命令默认输出简洁用户结论；`--view detailed` 输出完整审计报告，Markdown 与 JSON 都会重验内嵌语义评估，重复渲染仍可再次验证。`scope.locale` 决定 Listing 校验语言；`report_locale`/`--lang` 只决定展示语言。候选 Preview 的 `PASS` 展示为“候选预检通过”，绝不写成“发布成功”。批量工具的观测模式不要求标签，Golden 模式缺少预期值则直接失败；未配置私有 HMAC key 时仅输出无识别性行号。启用 HMAC 时，`LISTING_DOCTOR_SAMPLE_REF_KEY` 至少为 32 个 UTF-8 字节，样本引用与建议文本使用不同 HMAC Domain。

内容质量由 Agent 按固定七维契约生成，再由确定性脚本验证和合并：

```bash
python .agents/skills/amazon-listing-doctor/scripts/merge_report.py \
  --official-report official-report.json \
  --semantic-assessment .agents/skills/amazon-listing-doctor/examples/semantic-assessment.json
```

默认简洁层的形态如下（占位数据）：

```text
Marketplace：MARKETPLACE_ID
Seller SKU：SELLER_SKU
ASIN：ASIN_PLACEHOLDER

内容质量
已评估维度平均分：8.0 / 10（内部启发式评分，非 Amazon 官方评分）
评分覆盖：FULL（7/7，结构完整）
弱项维度：清晰度与可读性、图片信息覆盖
内容质量原因：标题没有清楚表达已经验证的容量信息。
内容优化行动：仅使用已绑定的 Listing 事实改善表达清晰度。
建议改为：Example Brand Bottle, 24 oz

Amazon 官方证据状态
当前 Listing：未评估
发布决策：发布条件未评估
官方证据完整性：未完成
说明：官方证据未完成只表示尚不能确认 Amazon 当前状态，不代表 Listing 内容不完整。
```

评分规则固定为 `STRONG=10`、`ADEQUATE=7`、`WEAK=3`，只对已评估维度求平均并保留一位小数；七维齐全为 `FULL/structurally_comparable=true`，五或六维为 `PARTIAL`，少于五维为 `NOT_SCORED`。两个分数只有在同为 `FULL` 且 `comparison_cohort_sha256` 一致时才允许比较；单份报告不自称“已可比”。高平均分不会隐藏 `WEAK` 维度。建议优先级必须匹配评级：`WEAK` 只允许 HIGH/MEDIUM，`ADEQUATE` 只允许 MEDIUM/LOW，`STRONG` 最多 LOW；`NOT_EVALUATED` 只能请求补充证据。适用于当前 Listing 或候选的 `OFFICIAL_ERROR` 仍是操作阻断项；普通官方警告、未评估和证据异常在独立官方证据区展示，不再替代内容质量原因。语义评估必须绑定目标内容、Locale、时间与官方报告哈希，且每个维度满足对应证据政策。默认简洁行动由维度映射为稳定 code，不直接展示可能带未绑定事实的自由模型文案。精确改写只能使用已绑定原始标量值以及空格、逗号、短横线、长横线、斜杠、冒号和圆括号；每个事实默认恰好使用一次，容量单位等事实也必须单独绑定。

相关契约：

- [`report-contract.md`](.agents/skills/amazon-listing-doctor/references/report-contract.md)：官方诊断输入输出。
- [`evidence-model.md`](.agents/skills/amazon-listing-doctor/references/evidence-model.md)：五态证据和四层门禁。
- [`quality-assessment.md`](.agents/skills/amazon-listing-doctor/references/quality-assessment.md)：七维内容质量 Schema 和 verdict 派生。
- [`erp-integration.md`](.agents/skills/amazon-listing-doctor/references/erp-integration.md)：公共适配器边界。
- [`production-readiness.md`](.agents/skills/amazon-listing-doctor/references/production-readiness.md)：生产证据、限流、自动化和发布闭环边界。
- [`private-golden-dataset.md`](.agents/skills/amazon-listing-doctor/references/private-golden-dataset.md)：私有样本实践、脱敏和回归方法。
- [`localization-calibration.md`](.agents/skills/amazon-listing-doctor/references/localization-calibration.md)：多语言内容质量校准边界。

## 安全边界

- 诊断不会执行真实 PATCH、Feed 提交、生产数据库写入或自动发布。
- `VALIDATION_PREVIEW` 只有在 mode、PUT/PATCH、身份范围、Payload SHA-256、请求指纹和时间均一致时才能通过相同候选。
- `ACCEPTED` 属于真实提交响应，不是预检通过。
- 内容质量建议始终是 `HEURISTIC_ADVICE`，不改变官方门禁。
- 公共示例只使用占位数据，不保存账号、凭据或真实商品标识。

## 验证

```bash
python -m unittest discover -s tests -v
python scripts/quick_validate.py
```

## 许可证与归属

本 Fork 沿用 MIT License，保留原项目 `Buluu@新西楼` 的版权与归属，详见 [`LICENSE`](LICENSE)。
