# Listing 诊断证据模型

## 证据优先级

1. 当前 Seller SKU 的 Listings Items `issues` 与 `VALIDATION_PREVIEW`。
2. 与 `sellerId + marketplaceId + productType + requirements + parentageLevel` 对应、checksum 可追溯且仍有效的 PTD Schema。
3. 卖家 Listing 当前 `attributes`、`summaries` 和状态快照。
4. Catalog Items 目录合并内容，仅作对照，不代表卖家贡献值。
5. 内部确定性启发式，例如图片清晰度、内容重复、关键词分层。
6. Agent 语义判断，例如意图覆盖与买家问题覆盖。

上层证据覆盖下层建议。同一属性已有 Amazon ERROR 时，不再降级为普通文案建议。

## 五态

### OFFICIAL_ERROR

- Listings Items issue `severity=ERROR`。
- `VALIDATION_PREVIEW` 返回 `INVALID` 或 ERROR issue。
- 当前可用 PTD 按明确单位（`CODE_POINTS`、`UTF8_BYTES`、`ITEMS`）确定违反约束。

保留 code、属性名、原始消息、来源、Schema checksum/版本或 submissionId。

### OFFICIAL_WARNING

- Amazon 返回 `severity=WARNING`。
- 正在使用 stale-within-grace Schema，或官方条件约束无法本地完整求值而需人工确认。

### HEURISTIC_ADVICE

可能改善可读性、信息覆盖或内容质量，但不能证明会改善索引、排名、CTR、CVR 或 Rufus 推荐。例如图片 500–999px、非正方形、内容重复、场景或买家问题覆盖不足。

### NOT_EVALUATED

字段未提供、图片只有 URL、PTD 不可用、没有运行官方预检、权限不足或数据仍在回补。列出补齐什么可以解锁判断。

### SYSTEM_ERROR

API 超时/限流/授权失败、Schema 下载或 checksum 失败、JSON 解析或检查模块异常。它表示无法判断，不表示 Listing 必然违规；发布门禁必须为 `UNKNOWN`。

## 门禁

| 条件 | 结论 |
|---|---|
| 官方检查链路存在 `SYSTEM_ERROR` | `UNKNOWN` |
| 任一 `OFFICIAL_ERROR` | `BLOCK` |
| 无 ERROR、有 `OFFICIAL_WARNING` | `REVIEW` |
| 官方预检完整且通过 | `PASS_OFFICIAL_CHECKS` |
| 未运行官方预检 | `NOT_EVALUATED` |

`HEURISTIC_ADVICE` 不参与门禁。`PASS_OFFICIAL_CHECKS` 也不保证真实提交已生效。

## 语义建议

意图覆盖按 `use_case / audience / goal / constraint` 组织。买家问题按场景、人群、兼容性、耐用、易用、规格、对比和价值顾虑组织。每条结论引用 Listing 直接证据；没有证据时只列“待补信息”，不代替商品作答。
