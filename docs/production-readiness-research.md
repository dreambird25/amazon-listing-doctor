# Amazon Listing 生产预检：官方证据语义与落地边界

> 研究日期：2026-08-27
> 资料边界：仅使用 Amazon SP-API 官方文档、Amazon 官方 OpenAPI 模型和 JSON Schema 官方规范。
> 数据边界：本文不含任何真实卖家、SKU、ASIN、商品内容、接口地址或鉴权信息。

## 1. 研究结论

生产可用的 Listing 诊断不能依赖单一信号，应把以下证据分开保存和判定：

1. **当前 Listing 快照**：通过 `getListingsItem` 获取指定卖家 SKU 在指定商城的当前属性、状态和 issues。
2. **候选 Payload 本地校验**：使用与卖家、商城、Product Type、需求集、父子层级和版本一致的 Product Type Definition（PTD）完整 JSON Schema 校验。
3. **候选 Payload 官方预览**：对少量、高价值变更调用 `putListingsItem` 或 `patchListingsItem` 的 `mode=VALIDATION_PREVIEW`，以 Amazon 返回的 `status` 和 `issues` 为准。
4. **实际提交后的确认**：正式提交成功后，仍需通过 `getListingsItem` 或 `LISTINGS_ITEM_ISSUES_CHANGE` / `LISTINGS_ITEM_STATUS_CHANGE` 获取后续异步处理结果。

其中第 1、2、3 项可以构成不写入 Listing 的生产预检；第 4 项是实际发布后的闭环。Amazon 明确区分同步问题与实际接受后才出现的异步问题，因此 `VALIDATION_PREVIEW=VALID` 不能替代发布后确认。[Amazon：Manage Listings Issues](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/manage-listings-issues)

## 2. Listings Items `VALIDATION_PREVIEW`

### 2.1 官方事实

`putListingsItem` 和 `patchListingsItem` 在查询参数中设置 `mode=VALIDATION_PREVIEW` 时，会验证候选 Listing 数据但不将数据持久化到 Amazon 目录。该能力适用于卖家和供应商，并覆盖所有商城。[Amazon 公告：Validation Preview](https://developer-docs.amazon.com/sp-api/lang-en_US/changelog/update-listings-items-api-v2021-08-01-now-supports-previewing-errors)

两种操作的绑定字段如下：

| 维度 | `putListingsItem` | `patchListingsItem` |
|---|---|---|
| 路径身份 | `sellerId` + `sku` | `sellerId` + `sku` |
| 商城 | 查询参数 `marketplaceIds` | 查询参数 `marketplaceIds` |
| Product Type | Body `productType` | Body `productType` |
| 候选内容 | Body `attributes` | Body `patches` |
| 需求集 | Body 可带 `requirements` | Body 没有 `requirements` 字段 |
| 模式 | Query `mode=VALIDATION_PREVIEW` | Query `mode=VALIDATION_PREVIEW` |
| 问题语言 | Query `issueLocale` | Query `issueLocale` |
| 返回数据 | `issues`；Preview 时可请求 `identifiers` | `issues`；Preview 时可请求 `identifiers` |

字段定义来自最新的 [`putListingsItem` API Reference](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/putlistingsitem) 和 [`patchListingsItem` API Reference](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/patchlistingsitem)。`PUT` 是创建或完整更新；`PATCH` 只修改顶层 Listing 属性，不能直接 patch 嵌套属性。

`putListingsItem.requirements` 的官方值为：

- `LISTING`：产品事实和销售条款；
- `LISTING_PRODUCT_ONLY`：仅产品事实；
- `LISTING_OFFER_ONLY`：仅销售条款。

`patchListingsItem` 请求没有 `requirements` 字段，因此不能在报告中伪造一个“Amazon 实际收到的 PATCH requirements”。用于 PATCH 本地校验的 PTD `requirements` / `requirementsEnforced` 是诊断器选择的 Schema scope，必须单独记录为本地校验上下文。

### 2.2 `status` 的严格语义

Amazon 官方 OpenAPI 模型定义 `ListingsItemSubmissionResponse.status`：

| 状态 | 官方语义 | 可否据此声称已发布 |
|---|---|---|
| `VALID` | 提交数据有效；只在 `VALIDATION_PREVIEW` 返回 | 不可，Preview 不持久化 |
| `INVALID` | 提交无效，未被接受处理 | 不可 |
| `ACCEPTED` | 提交已被接受处理 | 仍不可声称最终成功，可能存在后续异步问题 |

来源：[Amazon 官方 Listings Items OpenAPI 模型](https://github.com/amzn/selling-partner-api-models/blob/main/models/listings-items-api-model/listingsItems_2021-08-01.json)。

同一模型定义 issue severity：

- `ERROR`：阻止提交处理，例如验证错误；
- `WARNING`：应审查，但未阻止提交处理；
- `INFO`：需要审查的附加信息。

因此生产门禁必须读取 JSON 响应中的 `status` 和 `issues`，不能把 HTTP `200` 直接等同为通过。API Reference 对 HTTP `200` 的表述只是“请求已被理解”，并要求继续查看响应以确定是否被接受。[Amazon：putListingsItem](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/putlistingsitem)

### 2.3 限流与生产适用范围

当前 API Reference 给出的默认普通操作限流为：

- `putListingsItem`：5 requests/second，burst 10；
- `patchListingsItem`：5 requests/second，burst 5。

但 Amazon 对 `VALIDATION_PREVIEW` 单独规定 `putListingsItem` 和 `patchListingsItem` 均为 **1 request/second**。[Amazon 公告：Validation Preview](https://developer-docs.amazon.com/sp-api/lang-en_US/changelog/update-listings-items-api-v2021-08-01-now-supports-previewing-errors)

Amazon 最新问题管理指南进一步说明：Preview 限流较低，适合测试少量 Listing，**不设计为高吞吐生产工作流**。[Amazon：Manage Listings Issues](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/manage-listings-issues)

API 可能为特定卖家授予不同限额；客户端应在可用时读取 `x-amzn-RateLimit-Limit`，并正确处理 `429`，而不是把文档默认值硬编码为永恒上限。[Amazon：putListingsItem](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/putlistingsitem)

### 2.4 本仓库的生产推导

以下不是 Amazon API 的原生承诺，而是基于上述官方事实得出的实现约束：

- `VALIDATION_PREVIEW` 应作为低频、高价值候选变更的官方预检证据，不能对全量 Listing 每次诊断都强制调用。
- 批量内容先做本地完整 PTD JSON Schema 校验；进入人工确认或发布候选阶段时再调用 Preview。
- 只有 `status=VALID` 且不存在 `ERROR`，才可将“候选官方预览门禁”标为通过；`WARNING` 必须保留但不应自动升级为官方阻断。
- Preview 结果必须绑定 `seller_id + marketplace_id + sku + product_type + payload_hash + captured_at`。否则无法证明响应对应哪一个候选 Payload。
- `VALID` 只能命名为“预览有效”，不能命名为“Listing 已发布”“当前 Listing 健康”或“未来无异步问题”。

## 3. Product Type Definitions（PTD）

### 3.1 Schema scope 是结论的一部分

`getDefinitionsProductType` 返回的 Schema 受以下输入约束：

| Scope 字段 | 官方语义 |
|---|---|
| `productType` | Amazon Product Type 名称 |
| `sellerId` | 可选；提供后 Schema 可包含卖家特定要求和值，例如关联品牌和符合条件卖家的 B2B 属性 |
| `marketplaceIds` | 必填；当前限制一个商城 |
| `productTypeVersion` | 默认 `LATEST`；也可请求 `RELEASE_CANDIDATE`，若没有预发布版本则返回 `LATEST` |
| `requirements` | `LISTING`、`LISTING_PRODUCT_ONLY` 或 `LISTING_OFFER_ONLY` |
| `requirementsEnforced` | `ENFORCED` 或 `NOT_ENFORCED` |
| `locale` | 展示标签和其他 presentation details 的语言；默认第一个商城的默认语言 |
| `parentageLevel` | `NONE`、`CHILD` 或 `PARENT`；提供后会解析该父子层级相关的条件，返回更小的 Schema |

来源：[Amazon：getDefinitionsProductType API Reference](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/getdefinitionsproducttype)、[Amazon：Retrieve a Product Type Definition](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/retrieve-a-product-type-definition)。

`requirementsEnforced=ENFORCED` 会强制必填和条件必填属性，适合完整 Payload；`NOT_ENFORCED` 不强制完整必填集合，适合单属性等部分 Payload 的结构校验。它不表示 Amazon 放弃其他业务验证。[Amazon 官方 PTD OpenAPI 模型](https://github.com/amzn/selling-partner-api-models/blob/main/models/product-type-definitions-api-model/definitionsProductTypes_2020-09-01.json)

`parentageLevel` 的语义：

- `NONE`：独立 Listing，排除变体相关属性；
- `CHILD`：变体子体，并要求 `parent_sku`；
- `PARENT`：变体父体容器；
- 省略时：返回包含完整条件逻辑的 Schema。

### 3.2 版本和缓存

PTD 响应包含 `productTypeVersion`，其中有 `version`、`latest`、`releaseCandidate`；Schema 和 Meta-Schema 链接同时带 checksum。官方文档说明下载链接有效期为七天。[Amazon：Retrieve a Product Type Definition](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/retrieve-a-product-type-definition)

**仓库推导：** 每次正式诊断都应在报告中记录 PTD scope、`productTypeVersion.version`、`latest`、`releaseCandidate`、Schema checksum、Meta-Schema checksum 和获取时间。缓存可以按 checksum 去重，但不能只持久化七天临时 URL，也不能只记录 `LATEST` 而丢失实际版本。

### 3.3 JSON Schema 的正确适用方式

Amazon 明确要求 Listing Payload 符合 PTD 提供的 JSON Schema，并要求检查必填、条件必填以及 Schema 中的 `allOf` 动态条件。[Amazon：Manage Listings Issues](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/manage-listings-issues)

PTD 使用 JSON Schema Draft 2019-09，并包含 Amazon 自定义 vocabulary。Amazon 的官方 C# 示例要求：

- 在本地预加载 Amazon Meta-Schema，不能依靠 Web 自动解析 Meta-Schema 名称；
- 使用支持 Draft 2019-09 的验证器；
- 为 Amazon 自定义关键字实现验证，例如 `maxUniqueItems`、`minUtf8ByteLength`、`maxUtf8ByteLength`；
- `maxUniqueItems` 需要结合 `selectors` 判断数组元素的唯一组合。

来源：[Amazon：C# Example of Meta-Schema v1](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/product-type-definition-meta-schema-v1-example-c)、[Amazon：Retrieve a Product Type Definition](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/retrieve-a-product-type-definition)。JSON Schema Draft 2019-09 的通用语义以 [JSON Schema 官方规范](https://json-schema.org/draft/2019-09) 为准。

**仓库推导：** 只提取 `minLength`、`maxLength`、`minItems`、`maxItems` 的“轻量 PTD 检查”不能宣称完整 Schema 合规。除非验证器覆盖标准 Draft 2019-09 关键字、条件分支和 Amazon 自定义 vocabulary，否则报告必须明确标记 `LIGHTWEIGHT_SUBSET` 或 `NOT_EVALUATED`。

## 4. 当前 Listing issues 快照

### 4.1 官方事实

`getListingsItem` 的资源身份是 `sellerId + sku`，并要求指定 `marketplaceIds`。它返回的是卖家 Listing，不是仅凭 ASIN 定位的 Amazon Catalog Item。[Amazon：getListingsItem API Reference](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/getlistingsitem)

`includedData` 默认只有 `summaries`。可请求的数据集包括：

- `summaries`
- `attributes`
- `issues`
- `offers`
- `fulfillmentAvailability`
- `procurement`
- `relationships`
- `productTypes`

要取得当前问题详情，必须显式包含 `includedData=issues`。[Amazon：getListingsItem API Reference](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/getlistingsitem)

当前教程说明：卖家可在同一区域的一次 `getListingsItem` 请求中查询最多 12 个商城；供应商不支持该多商城能力。不同商城仍必须作为独立结论处理，不能把一个商城的状态套用到另一个商城。[Amazon：Retrieve details about a listing](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/retrieve-details-about-a-listing)

Amazon 将问题分为：

- 同步问题：初始提交被拒绝时立即返回；
- 异步问题：初始验证通过、下游处理时产生。

已存在 Listing 的 issue 详情可以由 `getListingsItem` / `searchListingsItems` 的 `includedData=issues` 获取。`LISTINGS_ITEM_ISSUES_CHANGE` 在问题创建、修复或更新时提供近实时通知，再由消费者调用 Listings Items API 获取详情。[Amazon：Manage Listings Issues](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/manage-listings-issues)

官方 `Issue` 模型包含 `code`、`message`、`severity`、`attributeNames`、`categories`、`enforcements` 和 `marketplaceIds`，但没有 issue 自身的采集时间字段。[Amazon 官方 Listings Items OpenAPI 模型](https://github.com/amzn/selling-partner-api-models/blob/main/models/listings-items-api-model/listingsItems_2021-08-01.json)

### 4.2 本仓库的生产推导

- 当前 Listing 门禁必须使用 `seller_id + marketplace_id + sku`，ASIN 只能作为目录关联标识，不能代替卖家 Listing 身份。
- 若入口只有 ASIN，可先通过 `searchListingsItems` 在指定 seller 下查找对应 SKU，但必须处理一对多或无结果，不能任意选择一个 SKU。[Amazon：searchListingsItems API Reference](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/searchlistingsitems)
- 每次快照必须由调用方补充 `captured_at`、HTTP request ID（如可用）和 scope。`summary.lastUpdatedDate` 不能被解释为每一条 issue 的更新时间，因为官方没有作出这种字段语义承诺。
- 没有 `includedData=issues`、调用失败或快照过旧时，应报告 `NOT_EVALUATED` / `SYSTEM_ERROR`，不能把 issues 缺失等同为“无问题”。
- 对持续运行系统，优先订阅 `LISTINGS_ITEM_ISSUES_CHANGE`，在通知后定向读取详情；定时全量轮询只是补偿机制。

### 4.3 v1.3.0 私有只读实践

2026-08-27 使用固定随机种子抽取 30 条私有 Listing，由独立 Luna 子代理只调用读取接口并在内存中运行 v1.2 基线；v1.3 修改和审查修复完成后，再以相同种子、偏移和只读流程重放当前引擎。样本覆盖多个北美/欧洲 Marketplace、17 个 Product Type 以及独立/子体 Listing。v1.3 的 30 条均成功、重复运行门禁全部一致、`SYSTEM_ERROR=0`，门禁与完整度聚合分布和 v1.2 基线一致，证明新契约未破坏 legacy 只读输入。

实践同时发现：legacy issues 存在记录时，另一问题视图可能仍为空；只提供 legacy issues 而缺少身份、`includedData`、request ID 和时效绑定时，即使 issues 数组为空也不能宣称“无官方问题”；未提供 PTD、候选 Payload 与 Preview 时，候选门禁必须全部保持 `NOT_EVALUATED`。这些是本仓库的实测接入事实，不被解释为 Amazon API 的普遍一致性承诺。原始 Listing、标识、文案、图片、Issue code/message 和接口响应均未落盘或提交。

## 5. 可用于生产的证据合同

建议每次诊断至少保存以下脱敏后的结构化元数据：

```json
{
  "listing_scope": {
    "seller_ref": "stable-redacted-ref",
    "marketplace_id": "marketplace-id",
    "sku_ref": "stable-redacted-ref",
    "product_type": "PRODUCT_TYPE",
    "parentage_level": "NONE"
  },
  "current_snapshot": {
    "captured_at": "RFC3339 timestamp",
    "included_data": ["summaries", "attributes", "issues", "productTypes"],
    "source": "GET_LISTINGS_ITEM"
  },
  "ptd_scope": {
    "requirements": "LISTING",
    "requirements_enforced": "ENFORCED",
    "locale": "locale",
    "version": "opaque-version",
    "latest": true,
    "release_candidate": false,
    "schema_checksum": "checksum",
    "meta_schema_checksum": "checksum"
  },
  "candidate": {
    "operation": "PUT_OR_PATCH",
    "payload_hash": "sha256",
    "current_content_separate": true,
    "local_schema_validation": "VALID_OR_INVALID",
    "local_validation_coverage": "FULL_JSON_SCHEMA_OR_LIGHTWEIGHT_SUBSET",
    "validator_attestation": {
      "validator_version": "version",
      "schema_draft": "2019-09",
      "amazon_vocabulary": true,
      "schema_checksum": "checksum",
      "meta_schema_checksum": "checksum",
      "validated_at": "RFC3339 timestamp"
    }
  },
  "validation_preview": {
    "captured_at": "RFC3339 timestamp",
    "status": "VALID_OR_INVALID",
    "submission_ref": "stable-redacted-ref",
    "issues": []
  }
}
```

正式报告可以展示 issue code、severity、categories 和脱敏后的 attribute names，但公开仓库中的测试夹具不得包含真实 `sellerId`、SKU、ASIN、submissionId、商品文案、图片 URL、价格、库存或完整 SP-API 响应。

## 6. 建议的生产判定矩阵

以下矩阵属于仓库设计，而不是 Amazon 官方状态枚举：

| 条件 | 当前 Listing 门禁 | 候选预览门禁 | 发布建议 |
|---|---|---|---|
| 当前快照有 `ERROR` | `BLOCKED` | 独立判断 | 先修复当前问题或明确豁免 |
| Preview `INVALID` 或有 `ERROR` | 不改变当前快照 | `BLOCKED` | 禁止提交候选 |
| Preview `VALID` 且仅有 `WARNING` / `INFO` | 不改变当前快照 | `PASS_WITH_WARNINGS` | 人工/规则审查后可提交 |
| Preview `VALID` 且无 issues | 不改变当前快照 | `PASS` | 可进入发布确认，不代表已发布 |
| Preview 未调用 | 不改变当前快照 | `NOT_EVALUATED` | 不得宣称官方预检通过 |
| API/鉴权/限流/超时失败 | `SYSTEM_ERROR` 或保留旧快照并标记过期 | `SYSTEM_ERROR` | 不得降级成通过 |
| 本地校验仅覆盖轻量子集 | 独立判断 | `PARTIALLY_EVALUATED` | 不得宣称完整 PTD 合规 |

## 7. 实施验收清单

- [ ] 以 `seller + marketplace + sku` 为 Listing 主身份；ASIN 仅作关联。
- [ ] PTD scope 完整绑定 seller、marketplace、product type、requirements、requirementsEnforced、locale、parentageLevel 和实际 version/checksum。
- [ ] 使用 Draft 2019-09 验证器并支持 Amazon 自定义 vocabulary；否则明确标记轻量覆盖。
- [ ] Preview 请求保存候选 payload hash，并严格区分 `VALID`、`INVALID`、`ACCEPTED`。
- [ ] HTTP `200` 不直接作为门禁通过。
- [ ] Preview 采用 1 request/second 的独立限流器，读取实际 rate-limit header 并处理 `429`。
- [ ] 当前快照显式请求 `includedData=issues`，记录采集时间。
- [ ] 诊断、Preview 和正式提交是不同权限；诊断流程不自动写 Listing。
- [ ] 发布后通过通知或定向查询闭环异步 issues/status。
- [ ] 公共测试只提交合成或不可逆脱敏数据，不提交真实商品响应。
- [ ] 私有 Golden Dataset 固定随机种子并重复运行；公开结果只保留聚合结论。

## 8. 官方来源索引

- [Listings Items：putListingsItem](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/putlistingsitem)
- [Listings Items：patchListingsItem](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/patchlistingsitem)
- [Listings Items：getListingsItem](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/getlistingsitem)
- [Listings Items：searchListingsItems](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/searchlistingsitems)
- [Validation Preview 公告](https://developer-docs.amazon.com/sp-api/lang-en_US/changelog/update-listings-items-api-v2021-08-01-now-supports-previewing-errors)
- [Preview PUT 教程](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/preview-errors-before-creating-a-listing)
- [Preview PATCH 教程](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/preview-errors-before-partially-updating-a-listing)
- [Manage Listings Issues](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/manage-listings-issues)
- [Building Listings Management Workflows](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/building-listings-management-workflows-guide)
- [Product Type Definition API Reference](https://developer-docs.amazon.com/sp-api/lang-en_EN/reference/getdefinitionsproducttype)
- [Retrieve a Product Type Definition](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/retrieve-a-product-type-definition)
- [Amazon Product Type Definitions Meta-Schema](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/product-type-definition-meta-schema)
- [Amazon Meta-Schema 验证示例](https://developer-docs.amazon.com/sp-api/lang-en_US/docs/product-type-definition-meta-schema-v1-example-c)
- [Amazon 官方 Listings Items OpenAPI 模型](https://github.com/amzn/selling-partner-api-models/blob/main/models/listings-items-api-model/listingsItems_2021-08-01.json)
- [Amazon 官方 PTD OpenAPI 模型](https://github.com/amzn/selling-partner-api-models/blob/main/models/product-type-definitions-api-model/definitionsProductTypes_2020-09-01.json)
- [JSON Schema Draft 2019-09](https://json-schema.org/draft/2019-09)
