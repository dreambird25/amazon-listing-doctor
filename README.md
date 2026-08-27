# Amazon Listing Doctor

一个可直接被 Codex 发现的 Amazon Listing 诊断 Skill。它把 Amazon 官方证据、内容质量判断、缺失数据和系统异常分开，生成可追溯、可复核的报告。

这是 [`buluslan/amazon-listing-doctor`](https://github.com/buluslan/amazon-listing-doctor) 的公共 Fork，不包含任何特定公司的内部代码、接口、表结构、账号、SKU、ASIN 或运行配置。

当前版本：**v1.2.0**。本版完成生产证据绑定与真实只读场景回放，详见 [`CHANGELOG.md`](CHANGELOG.md)。

## 它回答三个不同问题

| 层级 | 输出 | 能否参与官方发布判断 |
|---|---|---|
| 官方证据 | 当前 Listing、候选预检、发布决策和证据完整度 | 可以，但只限已绑定的官方证据范围 |
| 内容质量 | 七个维度的 `STRONG / ADEQUATE / WEAK / NOT_EVALUATED` | 不参与官方门禁 |
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

v1.2.0 可以安全用于人工诊断、ERP 辅助门禁，以及自动阻止已正确绑定的 Amazon `ERROR`。它会对旧 Payload 的 Preview ERROR、过期证据、范围不一致、PATCH 缺当前快照等情况安全降级，不会伪装成通过。

无人值守自动放行仍需由接入系统补齐：完整 Draft 2019-09 + Amazon vocabulary PTD 校验、Preview 独立限流、授权提交和提交后 issues/status 对账。Amazon 明确说明 Preview 适合少量 Listing，不是高吞吐生产主链路。官方依据见 [`生产就绪研究`](docs/production-readiness-research.md)，接入门禁见 [`production-readiness.md`](.agents/skills/amazon-listing-doctor/references/production-readiness.md)。

本版使用真实只读 Listing 接口完成过端到端实践。实践发现“已知 Amazon ERROR 与另一结构化视图暂时不同步”的情况，因此公开回归样本要求保留 `BLOCK + INCOMPLETE`。仓库只保存 [`listing-practice-sanitized.json`](.agents/skills/amazon-listing-doctor/examples/listing-practice-sanitized.json)：所有身份、文案、Issue code、时间和尺寸均已替换，不含原始产品信息。

示例输入位于 [`examples`](.agents/skills/amazon-listing-doctor/examples/README.md)。

## 开发者与 ERP 入口

根目录保留稳定 CLI：

```bash
python scripts/diagnose_listing.py --file .agents/skills/amazon-listing-doctor/examples/listing-valid.json
```

核心脚本位于 Skill 内部，根 CLI 只是兼容入口。脚本只使用 Python 标准库，不联网、不写数据。

本地 PTD 引擎只执行当前支持的长度/数量约束，并通过 `ptd_validation_coverage` 明示 `LIGHTWEIGHT_SUBSET`；它不冒充完整 PTD Schema 校验。因此即使绑定同一 Payload 的 `VALIDATION_PREVIEW` 通过，内置引擎的 `release_decision` 仍为 `REVIEW`；Preview 只证明候选预检有效，不证明已发布或无人值守放行条件已满足。

内容质量由 Agent 按固定七维契约生成，再由确定性脚本验证和合并：

```bash
python .agents/skills/amazon-listing-doctor/scripts/merge_report.py \
  --official-report official-report.json \
  --semantic-assessment .agents/skills/amazon-listing-doctor/examples/semantic-assessment.json
```

相关契约：

- [`report-contract.md`](.agents/skills/amazon-listing-doctor/references/report-contract.md)：官方诊断输入输出。
- [`evidence-model.md`](.agents/skills/amazon-listing-doctor/references/evidence-model.md)：五态证据和三层门禁。
- [`quality-assessment.md`](.agents/skills/amazon-listing-doctor/references/quality-assessment.md)：七维内容质量 Schema 和 verdict 派生。
- [`erp-integration.md`](.agents/skills/amazon-listing-doctor/references/erp-integration.md)：公共适配器边界。
- [`production-readiness.md`](.agents/skills/amazon-listing-doctor/references/production-readiness.md)：生产证据、限流、自动化和发布闭环边界。

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
