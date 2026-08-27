# Amazon Listing Doctor

一个可直接被 Codex 发现的 Amazon Listing 诊断 Skill。它把 Amazon 官方证据、内容质量判断、缺失数据和系统异常分开，生成可追溯、可复核的报告。

这是 [`buluslan/amazon-listing-doctor`](https://github.com/buluslan/amazon-listing-doctor) 的公共 Fork，不包含任何特定公司的内部代码、接口、表结构、账号、SKU、ASIN 或运行配置。

当前版本：**v1.3.2**。本版将默认简洁结论与 Marketplace、Seller SKU、内容/官方报告哈希和字段证据清单绑定，并区分完整可比评分与部分不可比平均分，详见 [`CHANGELOG.md`](CHANGELOG.md)。

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

v1.3.2 可以安全用于人工诊断、ERP 辅助门禁，以及自动阻止已正确绑定的 Amazon `ERROR`。它会对旧 Payload 的 Preview ERROR、过期证据、范围不一致、PATCH 缺当前快照等情况安全降级，不会伪装成通过。

无人值守自动放行仍需由接入系统补齐：完整 Draft 2019-09 + Amazon vocabulary PTD 校验、Preview 独立限流、授权提交和提交后 issues/status 对账。Amazon 明确说明 Preview 适合少量 Listing，不是高吞吐生产主链路。官方依据见 [`生产就绪研究`](docs/production-readiness-research.md)，接入门禁见 [`production-readiness.md`](.agents/skills/amazon-listing-doctor/references/production-readiness.md)。

本版使用固定随机种子对 30 条私有 Listing 做了只读实践，覆盖多个北美/欧洲站点和 Product Type。30 条重复运行的门禁均一致且没有引擎系统异常；实践同时确认 legacy issues 与另一问题视图可能不同步，且没有可追溯快照、PTD 和候选 Preview 时必须安全降级为不完整证据。公开仓库不保存这 30 条记录、标识或原始响应，只保留合成示例和不可逆脱敏回归样本。

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
python scripts/evaluate_batch.py --file private-golden-dataset.jsonl
python scripts/evaluate_batch.py --file private-quality-golden.jsonl --mode quality-summary
```

第一条命令默认输出简洁用户结论；`--view detailed` 输出完整审计报告。`scope.locale` 决定 Listing 校验语言；`report_locale`/`--lang` 只决定展示语言。候选 Preview 的 `PASS` 展示为“候选预检通过”，绝不写成“发布成功”。批量回归只输出聚合门禁和哈希化样本引用，不回显原始 Listing 内容。

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
发布决策：需要人工复核
已评估维度平均分：8.0 / 10（内部启发式评分，非 Amazon 官方评分）
评分覆盖：FULL（7/7，可横向比较）
弱项维度：清晰度与可读性、图片信息覆盖
主要原因：标题没有清楚表达已经验证的容量信息。
建议行动：重写标题并保留已验证事实。
建议改为：Example Brand Bottle, 24 oz
```

评分规则固定为 `STRONG=10`、`ADEQUATE=7`、`WEAK=3`，只对已评估维度求平均并保留一位小数；七维齐全才是 `FULL/comparable=true`，五或六维是 `PARTIAL/comparable=false`，少于五维为 `NOT_SCORED`。高平均分不会隐藏 `WEAK` 维度。存在适用于当前 Listing/候选的官方错误、证据异常或警告时，它优先成为首要原因与行动。语义评估必须绑定目标内容与官方报告哈希；精确改写还必须逐个事实匹配证据清单中的字段路径与值哈希，不能凭常识编造属性。

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
