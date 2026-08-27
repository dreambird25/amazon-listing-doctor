# Amazon Listing Doctor — Evidence-first Edition

这是 [`buluslan/amazon-listing-doctor`](https://github.com/buluslan/amazon-listing-doctor) 的公共 Fork。它保留结构化输入、数据覆盖、字段检查、语义覆盖和行动清单，把 Listing 诊断改造成可追溯的证据分层流程。

本仓库不包含任何特定公司的内部代码、接口、表结构、账号、SKU、ASIN 或运行配置，可作为 ERP/运营系统的公共参考实现。

当前版本：**v1.0.1**。本版修复候选预检证据绑定与门禁语义，详见 [`CHANGELOG.md`](CHANGELOG.md)。

## 为什么改造

固定 CDQ/A9/COSMO/Alexa 分数不能证明 Amazon 是否接受 Listing，也不能预测关键词收录、排名、流量或 Rufus 推荐。新版采用以下权威链路：

```text
Listings Items 当前 attributes / issues
                ↓
Product Type Definitions 当前 Schema
                ↓
本地确定性约束校验
                ↓
Listings Items VALIDATION_PREVIEW（不持久化）
                ↓
内部内容与语义优化建议
```

Amazon 官方资料：

- [Retrieve a Product Type Definition](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/retrieve-a-product-type-definition)
- [Manage Product Listings with SP-API](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/manage-product-listings-guide)
- [SP-API release notes (`VALIDATION_PREVIEW`)](https://developer-docs.amazon.com/sp-api/docs/sp-api-release-notes)

## 五态结果

| 状态 | 含义 | 发布门禁 |
|---|---|---|
| `OFFICIAL_ERROR` | Amazon ERROR/INVALID 或当前 PTD 的确定性违反 | 阻止相同候选提交 |
| `OFFICIAL_WARNING` | Amazon WARNING 或需人工确认的官方证据 | 人工复核 |
| `HEURISTIC_ADVICE` | 图片、文案、意图或买家问题覆盖建议 | 永不自动阻止 |
| `NOT_EVALUATED` | 数据、Schema、权限或元数据不足 | 无法判断 |
| `SYSTEM_ERROR` | API、解析或检查异常 | 门禁未知 |

报告不会再把当前 Listing、候选 Payload 和最终发布判断混成一个结果，而是分别输出：

- `current_listing_gate`：当前 Listings Items issues 与当前内容的 PTD 结果。
- `candidate_preview_gate`：与具体候选 Payload 绑定的 `VALIDATION_PREVIEW` 结果。
- `release_decision`：结合 PUT/PATCH 范围后的保守发布判断。
- `official_validation_completeness`：官方证据链是否完整；已知 ERROR 不会被其他系统异常覆盖。

## 数据来源

数据可以来自多种渠道，不要求必须直接连接 SP-API：

- JSON 文件或用户粘贴的结构化内容。
- Excel、CSV、Seller Central 导出等表格文件。
- Amazon SP-API 的 Listings Items、Product Type Definitions 和 `VALIDATION_PREVIEW` 返回。
- ERP、数据仓库、数据库只读视图或其他内部/第三方 API。

不同来源先通过转换器、ERP 适配器或 Agent 映射成统一 JSON，再交给诊断脚本。当前脚本直接读取 JSON，不直接解析 `.xlsx`；Excel/CSV 需先转换或映射。

数据渠道不决定证据等级。只有可追溯的 Amazon issues、PTD Schema 和 `VALIDATION_PREVIEW` 才归类为官方证据；普通文件、人工输入和第三方数据仍可用于内容检查，但不能自动标记为 Amazon 官方通过。

## 快速使用

准备 JSON：

```json
{
  "scope": {
    "seller_id": "SELLER_ID",
    "marketplace_id": "MARKETPLACE_ID",
    "sku": "SELLER_SKU",
    "product_type": "PRODUCT_TYPE",
    "requirements": "LISTING",
    "parentage_level": "CHILD",
    "locale": "en_US"
  },
  "candidate": {
    "operation": "PUT",
    "requirements": "LISTING",
    "parentage_level": "CHILD",
    "payload_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "created_at": "2026-01-01T00:00:00Z"
  },
  "content": {
    "title": "Example title",
    "images": [{"is_main": true, "width": 1600, "height": 1600}]
  },
  "official": {
    "listing_issues": [],
    "validation_preview": {
      "ran": true,
      "mode": "VALIDATION_PREVIEW",
      "operation": "PUT",
      "payload_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "seller_id": "SELLER_ID",
      "marketplace_id": "MARKETPLACE_ID",
      "sku": "SELLER_SKU",
      "product_type": "PRODUCT_TYPE",
      "request_id": "REQUEST_ID",
      "submission_id": "PREVIEW_ID",
      "requested_at": "2026-01-01T00:00:01Z",
      "responded_at": "2026-01-01T00:00:02Z",
      "http_status": 200,
      "status": "VALID",
      "issues": []
    },
    "ptd": {
      "status": "FRESH",
      "schema_checksum": "SCHEMA_CHECKSUM",
      "constraints": {
        "item_name": [{"type": "MAX_LENGTH", "value": 125, "unit": "CODE_POINTS"}]
      }
    }
  },
  "data_as_of": "2026-01-01T00:00:00Z"
}
```

运行：

```bash
python scripts/diagnose_listing.py --file listing.json
```

脚本只使用 Python 标准库，不联网、不写数据。输入输出详见 [`references/report-contract.md`](references/report-contract.md)。需要自动接入 SP-API、Excel 或其他系统时，可在外部实现转换器或公开适配器契约，见 [`references/erp-integration.md`](references/erp-integration.md)。

`payload_sha256` 必须由接入方对实际候选 Payload 的规范化 JSON 计算；示例中的重复字符只是格式占位。只有 mode、PUT/PATCH、身份范围与两侧 hash 全部一致，`candidate_preview_gate` 才可能为 `PASS`。Amazon 返回的 `ACCEPTED` 属于真实提交响应，不是预检通过。

## 能做与不能做

可以：

- 汇总 Listings Items issues 与 validation preview。
- 按明确单位执行 PTD 的长度/数量约束。
- 显式表达缺数据和系统异常。
- 给出不参与发布门禁的图片与内容建议。
- 生成带证据、完成条件和复核方式的行动项。

不做：

- 不输出 CDQ/A9/COSMO/Alexa 伪官方分数。
- 不用固定字符数或固定五点数量代替当前 PTD。
- 不内置第三方账号抓取或 Seller Central 凭据。
- 不自动改写、PATCH、提交 Feed 或写生产数据库。
- 不承诺索引、排名、流量、转化或 Rufus 推荐结果。

## 从上游 0.4.x 迁移

这是破坏性改造：旧版评分脚本、静态类目属性表、第三方抓取和四维总览已移除。`scripts/compliance_report.py` 保留为兼容入口，但输出切换为五态证据报告。

## 验证

```bash
python -m unittest discover -s tests -v
python scripts/quick_validate.py
```

## 许可证与归属

本 Fork 沿用 MIT License，保留原项目 `Buluu@新西楼` 的版权与归属，详见 [`LICENSE`](LICENSE)。
